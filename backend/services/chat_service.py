"""
Chat Service — Orchestrates conversation flow with memory, document context,
tool calling, and query decomposition
"""
import uuid
import json
from datetime import datetime
from models.database import ConversationDB, MessageDB, AnalyticsDB
from services.llm_service import LLMService
from services.memory_service import MemoryService
from services.document_service import DocumentService
from config import MEMORY_CONSOLIDATION_THRESHOLD
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NeuroChat, an intelligent AI assistant with persistent memory, document knowledge, and tool capabilities.

You have access to relevant memories from past conversations and indexed documents.
Use this context naturally in your responses — don't explicitly mention "my memory" or "from documents" 
unless the user asks about it.

CRITICAL INSTRUCTIONS:
1. ONLY answer questions using the facts provided in the context below. 
2. If the provided context does NOT contain the answer, you MUST explicitly state that you do not know. 
3. NEVER make up information, invent facts, or guess outside of the provided context. 
4. Cite the source document name when answering from documents.

Be helpful, thoughtful, and conversational. Remember details the user has shared with you.

{tool_section}

{context_section}"""


class ChatService:
    def __init__(self, llm_service: LLMService, memory_service: MemoryService,
                 document_service: DocumentService):
        self.llm = llm_service
        self.memory = memory_service
        self.documents = document_service
        self.followup_service = None   # Injected at runtime
        self.sentiment_service = None  # Injected at runtime
        self.tool_registry = None      # Injected at runtime
        self.query_decomposer = None   # Injected at runtime

    def _build_context(self, message: str, conversation_id: str = None):
        """Build context from memories and documents."""
        relevant_memories = self.memory.get_relevant_context(message)
        doc_results = self.documents.search_documents(message, top_k=5)

        context_parts = []
        if relevant_memories:
            memory_text = "\n".join([f"- {m['content']}" for m in relevant_memories])
            context_parts.append(f"Relevant memories:\n{memory_text}")

        if doc_results:
            doc_text = "\n".join([
                f"- From '{r['document_name']}': {r['content']}"
                for r in doc_results
            ])
            context_parts.append(f"Relevant document context:\n{doc_text}")

        context_section = "\n\n".join(context_parts) if context_parts else "No additional context available."

        # Tool descriptions
        tool_section = ""
        if self.tool_registry:
            tool_section = self.tool_registry.get_tool_descriptions()

        return relevant_memories, doc_results, context_section, tool_section

    def _process_tool_calls(self, response: str) -> str:
        """If the LLM output contains a tool call, execute it and re-prompt."""
        if not self.tool_registry:
            return response

        max_tool_rounds = 3
        for _ in range(max_tool_rounds):
            tool_called, tool_result, clean_response = self.tool_registry.detect_and_execute(response)
            if not tool_called:
                break

            # Re-prompt the LLM with the tool result
            tool_prompt = f"""{clean_response}

Tool result:
{tool_result}

Now incorporate this tool result into your response to the user. Be natural and conversational."""
            response = self.llm.generate(tool_prompt, temperature=0.5, max_tokens=1024)

        return response

    def _handle_decomposition(self, message: str, context_section: str) -> str:
        """Handle query decomposition for complex questions."""
        if not self.query_decomposer or not self.query_decomposer.should_decompose(message):
            return None

        sub_queries = self.query_decomposer.decompose(message)
        if len(sub_queries) <= 1:
            return None

        logger.info(f"Decomposed query into {len(sub_queries)} sub-queries")

        sub_results = []
        for sq in sub_queries:
            # Get context for each sub-query
            mem_results = self.memory.search_memories(sq, top_k=2)
            doc_results = self.documents.search_documents(sq, top_k=2)

            context_bits = []
            for m in mem_results:
                context_bits.append(m["content"])
            for d in doc_results:
                context_bits.append(f"[{d['document_name']}] {d['content']}")

            sub_results.append({
                "query": sq,
                "context": "\n".join(context_bits) if context_bits else "No relevant context found."
            })

        return self.query_decomposer.synthesize_answer(message, sub_results)

    def chat(self, message: str, conversation_id: str = None) -> dict:
        """Process a chat message with full context retrieval, tools, and decomposition."""
        # Get or create conversation
        if conversation_id:
            conversation = ConversationDB.get(conversation_id)
            if not conversation:
                conversation = ConversationDB.create(conversation_id, "New Conversation")
        else:
            conversation_id = str(uuid.uuid4())
            title = message[:60] + "..." if len(message) > 60 else message
            conversation = ConversationDB.create(conversation_id, title)

        # Save user message
        user_msg_id = str(uuid.uuid4())
        MessageDB.create(user_msg_id, conversation_id, "user", message)

        # Build context
        relevant_memories, doc_results, context_section, tool_section = self._build_context(message)

        # Try query decomposition for complex questions
        decomposed_answer = self._handle_decomposition(message, context_section)

        if decomposed_answer:
            response = decomposed_answer
        else:
            # Normal flow: build history + get LLM response
            history = MessageDB.get_by_conversation(conversation_id, limit=20)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT.format(
                    context_section=context_section, tool_section=tool_section
                )}
            ]
            for msg in history[-10:]:
                if msg["role"] in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            response = self.llm.chat(messages)

            # Process any tool calls
            response = self._process_tool_calls(response)

        # Save assistant message
        assistant_msg_id = str(uuid.uuid4())
        MessageDB.create(assistant_msg_id, conversation_id, "assistant", response,
                        metadata={"memories_used": len(relevant_memories),
                                  "documents_used": len(doc_results),
                                  "decomposed": decomposed_answer is not None})

        # Auto-extract memories
        try:
            self.memory.auto_extract_memories(message, response, conversation_id)
        except Exception as e:
            logger.error(f"Memory extraction error: {e}")

        # Consolidation check
        msg_count = MessageDB.count_by_conversation(conversation_id)
        if msg_count > 0 and msg_count % MEMORY_CONSOLIDATION_THRESHOLD == 0:
            try:
                all_msgs = MessageDB.get_by_conversation(conversation_id, limit=50)
                self.memory.consolidate_memories(conversation_id, all_msgs)
            except Exception as e:
                logger.error(f"Memory consolidation error: {e}")

        # Analytics
        AnalyticsDB.log_event("chat_message", {
            "conversation_id": conversation_id,
            "memories_used": len(relevant_memories),
            "documents_used": len(doc_results)
        })

        # Follow-up suggestions
        suggestions = []
        if self.followup_service:
            try:
                suggestions = self.followup_service.suggest_followups(message, response)
            except Exception as e:
                logger.debug(f"Follow-up suggestion error: {e}")

        # Sentiment
        sentiment = None
        if self.sentiment_service:
            try:
                sentiment = self.sentiment_service.analyze_sentiment(message)
            except Exception as e:
                logger.debug(f"Sentiment analysis error: {e}")

        return {
            "message": response,
            "conversation_id": conversation_id,
            "sources": doc_results,
            "memories_used": [
                {"id": m["id"], "content": m["content"][:100], "score": m.get("score", 0)}
                for m in relevant_memories
            ],
            "suggestions": suggestions,
            "sentiment": sentiment
        }

    def chat_stream(self, message: str, conversation_id: str = None):
        """Stream a chat response (generator)."""
        if conversation_id:
            conversation = ConversationDB.get(conversation_id)
            if not conversation:
                conversation = ConversationDB.create(conversation_id, "New Conversation")
        else:
            conversation_id = str(uuid.uuid4())
            title = message[:60] + "..." if len(message) > 60 else message
            conversation = ConversationDB.create(conversation_id, title)

        user_msg_id = str(uuid.uuid4())
        MessageDB.create(user_msg_id, conversation_id, "user", message)

        relevant_memories, doc_results, context_section, tool_section = self._build_context(message)

        # Build messages
        history = MessageDB.get_by_conversation(conversation_id, limit=20)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(
                context_section=context_section, tool_section=tool_section
            )}
        ]
        for msg in history[-10:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Stream response
        full_response = ""
        for chunk in self.llm.chat_stream(messages):
            full_response += chunk
            yield {"type": "chunk", "content": chunk, "conversation_id": conversation_id}

        # Process tool calls on complete response
        processed = self._process_tool_calls(full_response)
        if processed != full_response:
            # Send tool result as additional content
            tool_addition = processed[len(full_response):] if processed.startswith(full_response) else processed
            if tool_addition:
                yield {"type": "chunk", "content": "\n\n" + tool_addition, "conversation_id": conversation_id}
            full_response = processed

        # Save complete response
        assistant_msg_id = str(uuid.uuid4())
        MessageDB.create(assistant_msg_id, conversation_id, "assistant", full_response)

        # Extract memories
        try:
            self.memory.auto_extract_memories(message, full_response, conversation_id)
        except Exception:
            pass

        # Follow-up suggestions
        suggestions = []
        if self.followup_service:
            try:
                suggestions = self.followup_service.suggest_followups(message, full_response)
            except Exception:
                pass

        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "sources": doc_results,
            "memories_used": [
                {"id": m["id"], "content": m["content"][:100], "score": m.get("score", 0)}
                for m in relevant_memories
            ],
            "suggestions": suggestions
        }

    def get_conversations(self) -> list[dict]:
        return ConversationDB.list_all()

    def get_conversation(self, conversation_id: str) -> dict:
        conv = ConversationDB.get(conversation_id)
        if conv:
            messages = MessageDB.get_by_conversation(conversation_id)
            conv["messages"] = messages
        return conv

    def delete_conversation(self, conversation_id: str):
        ConversationDB.delete(conversation_id)
        AnalyticsDB.log_event("conversation_deleted", {"conversation_id": conversation_id})

    def rename_conversation(self, conversation_id: str, title: str) -> dict:
        return ConversationDB.update(conversation_id, title=title)
