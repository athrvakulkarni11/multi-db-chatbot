"""
Advanced AI Service — Knowledge Graph, Sentiment, Topic Clustering, 
Follow-up Suggestions, Document Summarization, Conversation Export
"""
import json
import re
import uuid
from collections import Counter
from datetime import datetime
from models.database import MessageDB, MemoryDB, ConversationDB, AnalyticsDB
from services.llm_service import LLMService
from services.embedding_service import EmbeddingService
import numpy as np
import logging

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Extracts entities and relationships from text to build a knowledge graph."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self.nodes: dict[str, dict] = {}  # {id: {label, type, count}}
        self.edges: list[dict] = []  # [{source, target, relationship}]

    def extract_entities(self, text: str) -> dict:
        """Extract entities and relationships from text using LLM."""
        prompt = f"""Extract entities and their relationships from the following text.
Return JSON format exactly like this (no other text):
{{"entities": [{{"name": "entity_name", "type": "PERSON|PLACE|ORG|CONCEPT|TECH|EVENT|OTHER"}}], "relationships": [{{"source": "entity1", "target": "entity2", "relation": "relationship_type"}}]}}

Text: "{text[:1000]}"

JSON:"""
        try:
            response = self.llm.generate(prompt, temperature=0.2, max_tokens=500)
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Entity extraction parse error: {e}")
        return {"entities": [], "relationships": []}

    def add_from_text(self, text: str):
        """Extract and add entities/relationships from text."""
        data = self.extract_entities(text)
        
        for entity in data.get("entities", []):
            name = entity.get("name", "").strip()
            if not name or len(name) < 2:
                continue
            node_id = name.lower().replace(" ", "_")
            if node_id in self.nodes:
                self.nodes[node_id]["count"] += 1
            else:
                self.nodes[node_id] = {
                    "id": node_id,
                    "label": name,
                    "type": entity.get("type", "OTHER"),
                    "count": 1
                }

        for rel in data.get("relationships", []):
            source = rel.get("source", "").strip().lower().replace(" ", "_")
            target = rel.get("target", "").strip().lower().replace(" ", "_")
            if source and target and source in self.nodes and target in self.nodes:
                self.edges.append({
                    "source": source,
                    "target": target,
                    "relation": rel.get("relation", "related_to")
                })

    def get_graph(self) -> dict:
        """Return the full knowledge graph."""
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges
        }

    def build_from_memories(self):
        """Build knowledge graph from all stored memories."""
        memories = MemoryDB.list_all(limit=200)
        for mem in memories:
            self.add_from_text(mem["content"])
        logger.info(f"Built knowledge graph: {len(self.nodes)} nodes, {len(self.edges)} edges")


class SentimentService:
    """Tracks sentiment/mood across conversations."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def analyze_sentiment(self, text: str) -> dict:
        """Analyze the sentiment of a text."""
        prompt = f"""Analyze the sentiment of the following text.
Respond with ONLY valid JSON in this exact format (no other text):
{{"sentiment": "positive|negative|neutral|mixed", "score": 0.0, "emotions": ["emotion1", "emotion2"]}}

Score ranges: -1.0 (very negative) to 1.0 (very positive), 0 is neutral.

Text: "{text[:500]}"

JSON:"""
        try:
            response = self.llm.generate(prompt, temperature=0.1, max_tokens=100)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "sentiment": data.get("sentiment", "neutral"),
                    "score": float(data.get("score", 0)),
                    "emotions": data.get("emotions", [])
                }
        except Exception as e:
            logger.debug(f"Sentiment analysis error: {e}")
        return {"sentiment": "neutral", "score": 0.0, "emotions": []}

    def get_conversation_sentiment(self, conversation_id: str) -> list[dict]:
        """Get sentiment timeline for a conversation."""
        messages = MessageDB.get_by_conversation(conversation_id, limit=50)
        timeline = []
        for msg in messages:
            if msg["role"] == "user":
                sentiment = self.analyze_sentiment(msg["content"])
                timeline.append({
                    "message_id": msg["id"],
                    "content_preview": msg["content"][:80],
                    "created_at": msg["created_at"],
                    **sentiment
                })
        return timeline


class TopicClusterService:
    """Clusters memories and documents by topic using embeddings."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding = embedding_service

    def cluster_memories(self, memories: list[dict], n_clusters: int = 5) -> list[dict]:
        """Cluster memories by semantic similarity using k-means-like approach."""
        if len(memories) < 3:
            return [{"cluster_id": 0, "label": "All", "memories": memories}]

        texts = [m["content"] for m in memories]
        embeddings = self.embedding.embed_texts(texts)

        n_clusters = min(n_clusters, len(memories) // 2, 8)
        if n_clusters < 2:
            return [{"cluster_id": 0, "label": "All", "memories": memories}]

        # Simple k-means clustering
        labels = self._kmeans(embeddings, n_clusters)

        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            mem_copy = dict(memories[i])
            clusters[label].append(mem_copy)

        # Generate cluster labels from content
        result = []
        for cluster_id, cluster_memories in sorted(clusters.items()):
            # Use the most common words as label
            all_text = " ".join(m["content"] for m in cluster_memories)
            words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
            stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'what',
                          'when', 'where', 'which', 'their', 'they', 'them', 'than',
                          'about', 'would', 'could', 'should', 'there', 'these',
                          'those', 'some', 'other', 'into', 'more', 'also', 'very',
                          'just', 'like', 'user', 'assistant', 'preferences'}
            filtered = [w for w in words if w not in stop_words]
            common = Counter(filtered).most_common(3)
            label = ", ".join(w for w, _ in common) if common else f"Topic {cluster_id + 1}"

            result.append({
                "cluster_id": cluster_id,
                "label": label.title(),
                "count": len(cluster_memories),
                "memories": cluster_memories
            })

        return result

    def _kmeans(self, embeddings: np.ndarray, k: int, max_iter: int = 20) -> list[int]:
        """Simple k-means implementation."""
        n = len(embeddings)
        # Initialize centroids randomly
        indices = np.random.choice(n, k, replace=False)
        centroids = embeddings[indices].copy()

        labels = [0] * n
        for _ in range(max_iter):
            # Assign points to nearest centroid
            new_labels = []
            for emb in embeddings:
                distances = [np.linalg.norm(emb - c) for c in centroids]
                new_labels.append(int(np.argmin(distances)))

            if new_labels == labels:
                break
            labels = new_labels

            # Update centroids
            for j in range(k):
                cluster_points = [embeddings[i] for i in range(n) if labels[i] == j]
                if cluster_points:
                    centroids[j] = np.mean(cluster_points, axis=0)

        return labels


class FollowUpService:
    """Generates smart follow-up question suggestions."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def suggest_followups(self, user_message: str, assistant_response: str,
                          context: str = "") -> list[str]:
        """Generate 3 follow-up question suggestions."""
        prompt = f"""Based on this conversation exchange, suggest exactly 3 follow-up questions the user might want to ask next.
Make them specific, diverse, and useful. Return ONLY the 3 questions, one per line, no numbering or bullets.

User: {user_message[:300]}
Assistant: {assistant_response[:500]}

3 follow-up questions:"""
        try:
            response = self.llm.generate(prompt, temperature=0.7, max_tokens=200)
            questions = [q.strip().lstrip("0123456789.-) ").strip()
                        for q in response.strip().split("\n")
                        if q.strip() and len(q.strip()) > 10]
            return questions[:3]
        except Exception as e:
            logger.debug(f"Follow-up generation error: {e}")
        return []


class DocumentSummaryService:
    """Auto-summarizes uploaded documents."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def summarize_document(self, text: str, filename: str = "") -> dict:
        """Generate a comprehensive summary of a document."""
        # Use first ~3000 chars for summary (LLM context limits)
        excerpt = text[:3000]

        prompt = f"""Analyze this document and provide a structured summary.
Return ONLY valid JSON in this exact format:
{{"summary": "2-3 sentence overview", "key_points": ["point1", "point2", "point3"], "topics": ["topic1", "topic2"], "word_count": 0}}

Document ({filename}):
{excerpt}

JSON:"""
        try:
            response = self.llm.generate(prompt, temperature=0.3, max_tokens=500)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                data["word_count"] = len(text.split())
                return data
        except Exception as e:
            logger.debug(f"Document summary error: {e}")

        return {
            "summary": f"Document '{filename}' containing {len(text.split())} words.",
            "key_points": [],
            "topics": [],
            "word_count": len(text.split())
        }


class ConversationExportService:
    """Exports conversations in various formats."""

    @staticmethod
    def export_markdown(conversation_id: str) -> str:
        """Export a conversation as Markdown."""
        conv = ConversationDB.get(conversation_id)
        if not conv:
            return ""

        messages = MessageDB.get_by_conversation(conversation_id, limit=1000)

        lines = [
            f"# {conv['title']}",
            f"*Exported on {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}*",
            f"*Messages: {len(messages)}*",
            "",
            "---",
            ""
        ]

        for msg in messages:
            if msg["role"] == "user":
                lines.append(f"### 🧑 User")
            elif msg["role"] == "assistant":
                lines.append(f"### 🤖 NeuroChat")
            else:
                continue

            lines.append("")
            lines.append(msg["content"])
            lines.append("")
            time_str = msg.get("created_at", "")
            if time_str:
                lines.append(f"*{time_str}*")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def export_json(conversation_id: str) -> dict:
        """Export a conversation as JSON."""
        conv = ConversationDB.get(conversation_id)
        if not conv:
            return {}

        messages = MessageDB.get_by_conversation(conversation_id, limit=1000)

        return {
            "conversation": {
                "id": conv["id"],
                "title": conv["title"],
                "created_at": conv["created_at"],
                "updated_at": conv["updated_at"],
                "message_count": len(messages)
            },
            "messages": [
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["created_at"]
                }
                for msg in messages
                if msg["role"] in ("user", "assistant")
            ],
            "exported_at": datetime.utcnow().isoformat()
        }
