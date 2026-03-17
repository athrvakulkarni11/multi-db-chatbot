"""
Chat Service — Orchestrates conversation flow with memory and document context
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

SYSTEM_PROMPT = """You are NeuroChat, an intelligent AI assistant with persistent memory and document knowledge.

You have access to relevant memories from past conversations and indexed documents.
Use this context naturally in your responses — don't explicitly mention "my memory" or "from documents" 
unless the user asks about it.

Be helpful, thoughtful, and conversational. Remember details the user has shared with you.
When answering questions from documents, cite the source when possible.

{context_section}"""


class ChatService:
    def __init__(self, llm_service: LLMService, memory_service: MemoryService,
                 document_service: DocumentService):
        self.llm = llm_service
        self.memory = memory_service
        self.documents = document_service
        self.followup_service = None  # Injected at runtime
        self.sentiment_service = None  # Injected at runtime

    def chat(self, message: str, conversation_id: str = None) -> dict:
        """Process a chat message with full context retrieval."""
        # Get or create conversation
        if conversation_id:
            conversation = ConversationDB.get(conversation_id)
            if not conversation:
                conversation = ConversationDB.create(conversation_id, "New Conversation")
        else:
            conversation_id = str(uuid.uuid4())
            # Generate title from first message
            title = message[:60] + "..." if len(message) > 60 else message
            conversation = ConversationDB.create(conversation_id, title)

        # Save user message
        user_msg_id = str(uuid.uuid4())
        MessageDB.create(user_msg_id, conversation_id, "user", message)

        # Retrieve relevant memories
        relevant_memories = self.memory.get_relevant_context(message)

        # Search documents for relevant context
        doc_results = self.documents.search_documents(message, top_k=3)

        # Build context section
        context_parts = []

        if relevant_memories:
            memory_text = "\n".join([
                f"- {m['content']}" for m in relevant_memories
            ])
            context_parts.append(f"Relevant memories:\n{memory_text}")

        if doc_results:
            doc_text = "\n".join([
                f"- From '{r['document_name']}': {r['content'][:300]}"
                for r in doc_results
            ])
            context_parts.append(f"Relevant document context:\n{doc_text}")

        context_section = "\n\n".join(context_parts) if context_parts else "No additional context available."

        # Build conversation history
        history = MessageDB.get_by_conversation(conversation_id, limit=20)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(context_section=context_section)}
        ]

        # Add conversation history (last N messages)
        for msg in history[-10:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Generate response
        response = self.llm.chat(messages)

        # Save assistant message
        assistant_msg_id = str(uuid.uuid4())
        MessageDB.create(assistant_msg_id, conversation_id, "assistant", response, 
                        metadata={"memories_used": len(relevant_memories),
                                  "documents_used": len(doc_results)})

        # Auto-extract memories from this exchange (in background-safe manner)
        try:
            self.memory.auto_extract_memories(message, response, conversation_id)
        except Exception as e:
            logger.error(f"Memory extraction error: {e}")

        # Check if consolidation is needed
        msg_count = MessageDB.count_by_conversation(conversation_id)
        if msg_count > 0 and msg_count % MEMORY_CONSOLIDATION_THRESHOLD == 0:
            try:
                all_msgs = MessageDB.get_by_conversation(conversation_id, limit=50)
                self.memory.consolidate_memories(conversation_id, all_msgs)
            except Exception as e:
                logger.error(f"Memory consolidation error: {e}")

        # Log analytics
        AnalyticsDB.log_event("chat_message", {
            "conversation_id": conversation_id,
            "memories_used": len(relevant_memories),
            "documents_used": len(doc_results)
        })

        # Generate follow-up suggestions
        suggestions = []
        if self.followup_service:
            try:
                suggestions = self.followup_service.suggest_followups(message, response)
            except Exception as e:
                logger.debug(f"Follow-up suggestion error: {e}")

        # Analyze sentiment
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

        # Retrieve context
        relevant_memories = self.memory.get_relevant_context(message)
        doc_results = self.documents.search_documents(message, top_k=3)

        context_parts = []
        if relevant_memories:
            memory_text = "\n".join([f"- {m['content']}" for m in relevant_memories])
            context_parts.append(f"Relevant memories:\n{memory_text}")
        if doc_results:
            doc_text = "\n".join([
                f"- From '{r['document_name']}': {r['content'][:300]}"
                for r in doc_results
            ])
            context_parts.append(f"Relevant document context:\n{doc_text}")

        context_section = "\n\n".join(context_parts) if context_parts else "No additional context available."

        # Build messages
        history = MessageDB.get_by_conversation(conversation_id, limit=20)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(context_section=context_section)}
        ]
        for msg in history[-10:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Stream response
        full_response = ""
        for chunk in self.llm.chat_stream(messages):
            full_response += chunk
            yield {"type": "chunk", "content": chunk, "conversation_id": conversation_id}

        # Save complete response
        assistant_msg_id = str(uuid.uuid4())
        MessageDB.create(assistant_msg_id, conversation_id, "assistant", full_response)

        # Extract memories
        try:
            self.memory.auto_extract_memories(message, full_response, conversation_id)
        except Exception:
            pass

        # Generate follow-up suggestions
        suggestions = []
        if self.followup_service:
            try:
                suggestions = self.followup_service.suggest_followups(message, full_response)
            except Exception:
                pass

        # Send final metadata
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
        """Get all conversations."""
        return ConversationDB.list_all()

    def get_conversation(self, conversation_id: str) -> dict:
        """Get a conversation with its messages."""
        conv = ConversationDB.get(conversation_id)
        if conv:
            messages = MessageDB.get_by_conversation(conversation_id)
            conv["messages"] = messages
        return conv

    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and its messages."""
        ConversationDB.delete(conversation_id)
        AnalyticsDB.log_event("conversation_deleted", {"conversation_id": conversation_id})

    def rename_conversation(self, conversation_id: str, title: str) -> dict:
        """Rename a conversation."""
        return ConversationDB.update(conversation_id, title=title)
