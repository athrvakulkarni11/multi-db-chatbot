"""
LLM Service — Local LLM integration via Ollama
"""
import requests
import json
from config import OLLAMA_BASE_URL, OLLAMA_MODEL
import logging

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        self._model_history: list[str] = [OLLAMA_MODEL]

    def switch_model(self, model_name: str) -> dict:
        """Switch to a different Ollama model."""
        old_model = self.model
        self.model = model_name
        if model_name not in self._model_history:
            self._model_history.append(model_name)
        health = self.check_health()
        if not health.get("model_ready", False):
            logger.warning(f"Model '{model_name}' not found in Ollama. You may need to pull it.")
        logger.info(f"Switched model: {old_model} -> {model_name}")
        return {
            "previous_model": old_model,
            "current_model": model_name,
            "model_ready": health.get("model_ready", False),
            "available_models": health.get("models_available", [])
        }

    def get_available_models(self) -> list[str]:
        """List all models available in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return []

    def pull_model(self, model_name: str) -> dict:
        """Pull a model from Ollama registry."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600  # Models can be large
            )
            return {"status": "success", "model": model_name}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def check_health(self) -> dict:
        """Check if Ollama is running and the model is available."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                has_model = any(self.model in name for name in model_names)
                return {
                    "status": "connected",
                    "models_available": model_names,
                    "configured_model": self.model,
                    "model_ready": has_model
                }
            return {"status": "error", "detail": f"HTTP {resp.status_code}"}
        except requests.ConnectionError:
            return {"status": "disconnected", "detail": "Cannot connect to Ollama. Make sure it's running."}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def generate(self, prompt: str, system_prompt: str = None, temperature: float = 0.7,
                 max_tokens: int = 2048) -> str:
        """Generate a response from the local LLM."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def chat(self, messages: list[dict], temperature: float = 0.7,
             max_tokens: int = 2048) -> str:
        """Send a chat conversation to the LLM."""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except requests.ConnectionError:
            return "⚠️ Cannot connect to Ollama. Please make sure Ollama is running on your machine."
        except requests.Timeout:
            return "⚠️ The LLM took too long to respond. Please try a shorter message."
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"⚠️ LLM Error: {str(e)}"

    def generate_stream(self, prompt: str, system_prompt: str = None, temperature: float = 0.7):
        """Stream a response from the LLM (generator)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat_stream(messages, temperature=temperature)

    def chat_stream(self, messages: list[dict], temperature: float = 0.7):
        """Stream a chat conversation (generator)."""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature
                }
            }
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=120
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done", False):
                        break
        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            yield f"⚠️ LLM Error: {str(e)}"

    def extract_importance(self, text: str) -> float:
        """Use the LLM to rate the importance of a memory (0.0-1.0)."""
        prompt = f"""Rate the importance of remembering the following information on a scale from 0.0 to 1.0.
0.0 = trivial/generic (like greetings)
0.5 = moderately useful (general preferences)
1.0 = critically important (personal facts, specific instructions)

Information: "{text}"

Respond with ONLY a number between 0.0 and 1.0, nothing else."""

        try:
            response = self.generate(prompt, temperature=0.1, max_tokens=10)
            score = float(response.strip())
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            return 0.5

    def summarize_conversation(self, messages: list[dict]) -> str:
        """Summarize a conversation for memory consolidation."""
        conversation_text = "\n".join([
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages[:20]
        ])

        prompt = f"""Summarize the key facts, preferences, and important information from this conversation.
Focus on things worth remembering for future conversations.
Be concise but include all important details.

Conversation:
{conversation_text}

Summary:"""

        return self.generate(prompt, temperature=0.3, max_tokens=500)

    def extract_memories(self, user_message: str, assistant_response: str) -> list[str]:
        """Extract memorable facts from a conversation exchange."""
        prompt = f"""You are a memory extraction module for a specific user. Your job is to extract HIGHLY PERSONAL and USEFUL episodic facts about the USER from the exchange below.

RULES for Memory Extraction:
1. ONLY extract facts about the User (e.g., their name, their job, their specific preferences, their current projects, their thoughts/opinions).
2. NEVER extract general encyclopedic statements (e.g., "AI has three variants", "The World Cup is in India").
3. NEVER extract Assistant meta-talk (e.g., "I am an AI", "Cannot connect to Ollama", "Here are the extracted facts").
4. If the exchange does not contain any new personal facts about the User, you MUST respond exactly with the word "NONE".
5. Write each extracted fact on a new line without numbers or bullet points.

User said: {user_message}
Assistant replied: {assistant_response}

User Facts (or NONE):"""

        response = self.generate(prompt, temperature=0.1, max_tokens=200)
        if "NONE" in response.upper():
            return []
        
        memories = [line.strip().lstrip("- •").strip() 
                   for line in response.strip().split("\n") 
                   if line.strip() and len(line.strip()) > 10]
        return memories[:5]  # Cap at 5 memories per exchange
