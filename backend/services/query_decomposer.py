"""
Query Decomposition Engine — Breaks complex queries into sub-queries for better RAG

When a user asks a complex question, this decomposes it into simpler
sub-queries, retrieves context for each, and synthesizes a final answer.
"""
import json
import re
from services.llm_service import LLMService
import logging

logger = logging.getLogger(__name__)


class QueryDecomposer:
    """
    Decomposes complex queries into sub-queries for multi-hop retrieval.
    
    Example:
        Query: "Compare the machine learning approach in doc A vs doc B"
        Sub-queries:
          1. "What is the machine learning approach in doc A?"
          2. "What is the machine learning approach in doc B?"
          3. "How do these approaches compare?"
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def should_decompose(self, query: str) -> bool:
        """Heuristic to decide if a query needs decomposition."""
        complexity_indicators = [
            "compare", "difference between", "vs", "versus",
            "how does.*relate to", "what are the.*and.*",
            "explain.*and.*", "summarize all", "list all",
            "multiple", "both", "each", "every"
        ]
        query_lower = query.lower()
        # Long queries or ones with comparison words
        if len(query.split()) > 15:
            return True
        for indicator in complexity_indicators:
            if re.search(indicator, query_lower):
                return True
        return False

    def decompose(self, query: str) -> list[str]:
        """Break a complex query into simpler sub-queries using the LLM."""
        prompt = f"""Break this complex question into 2-4 simpler, independent sub-questions that can each be answered separately. The sub-questions should cover all aspects of the original question.

Question: "{query}"

Return ONLY the sub-questions, one per line, no numbering or bullets. If the question is already simple, return it unchanged."""

        try:
            response = self.llm.generate(prompt, temperature=0.3, max_tokens=300)
            sub_queries = [
                q.strip().lstrip("0123456789.-) ").strip()
                for q in response.strip().split("\n")
                if q.strip() and len(q.strip()) > 10
            ]
            if sub_queries:
                logger.info(f"Decomposed query into {len(sub_queries)} sub-queries")
                return sub_queries[:4]  # Max 4
        except Exception as e:
            logger.debug(f"Query decomposition error: {e}")

        return [query]  # Return original if decomposition fails

    def synthesize_answer(self, original_query: str, sub_results: list[dict]) -> str:
        """Synthesize a final answer from sub-query results."""
        context_parts = []
        for i, result in enumerate(sub_results):
            context_parts.append(f"Sub-question {i+1}: {result['query']}")
            context_parts.append(f"Context found: {result['context']}")
            context_parts.append("")

        synthesis_context = "\n".join(context_parts)

        prompt = f"""Based on the following research, provide a comprehensive answer to the original question.

CRITICAL INSTRUCTIONS:
1. ONLY use the research results provided below.
2. If the answer is not in the research, say "I do not have enough information."
3. DO NOT hallucinate or guess.

Original question: "{original_query}"

Research results:
{synthesis_context}

Comprehensive answer:"""

        try:
            return self.llm.generate(prompt, temperature=0.5, max_tokens=1000)
        except Exception:
            return "Unable to synthesize answer from sub-queries."
