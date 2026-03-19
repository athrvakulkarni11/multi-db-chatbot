"""
Tool/Plugin System — Gives the LLM callable tools

The LLM can detect when a tool is needed and invoke it.
Currently supports: web search.
"""
import json
import re
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class Tool:
    """Base class for all tools."""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    def execute(self, **kwargs) -> str:
        raise NotImplementedError


class WebSearchTool(Tool):
    name = "web_search"
    description = "Searches the web for real-time information. Use this to find current events, factual information, or answers to questions."
    parameters = {"query": "The search query to search the web for"}

    def execute(self, query: str = "", **kwargs) -> str:
        if not query:
            return "No query provided."
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            data = {"q": query}
            # DuckDuckGo HTML light version provides easy parsing without JS
            res = requests.post("https://lite.duckduckgo.com/lite/", data=data, headers=headers, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            
            results = []
            for tr in soup.find_all('tr'):
                result_td = tr.find('td', class_='result-snippet')
                if result_td:
                    snippet = result_td.get_text(strip=True)
                    # Try to find title
                    title_elem = tr.previous_sibling
                    title = "Result"
                    if title_elem and title_elem.name == 'tr':
                        a_tag = title_elem.find('a', class_='result-url')
                        if a_tag:
                            title = a_tag.get_text(strip=True)
                    
                    results.append(f"Title: {title}\nSnippet: {snippet}")
                    if len(results) >= 5:
                        break
                        
            if not results:
                return "No useful results found on the web."
            
            return "Web Search Results:\n\n" + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return f"Error executing web search: {str(e)}"


class ToolRegistry:
    """Registry that manages all available tools and handles LLM tool calling."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all built-in tools."""
        for tool_class in [WebSearchTool]:
            tool = tool_class()
            self.tools[tool.name] = tool

    def register(self, tool: Tool):
        """Register a custom tool."""
        self.tools[tool.name] = tool

    def get_tool_descriptions(self) -> str:
        """Generate a description string for the LLM system prompt."""
        lines = ["You have access to the following tools. To use a tool, respond with a JSON block like:"]
        lines.append('```tool\n{"tool": "tool_name", "params": {"key": "value"}}\n```')
        lines.append("\nAvailable tools:")
        for name, tool in self.tools.items():
            params_str = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items()) if tool.parameters else "none"
            lines.append(f"- **{name}**: {tool.description}")
            lines.append(f"  Parameters: {params_str}")
        return "\n".join(lines)

    def detect_and_execute(self, llm_response: str) -> tuple[bool, str, str]:
        """
        Detect if the LLM response contains a tool call and execute it.
        
        Returns: (tool_was_called, tool_result, remaining_response)
        """
        # Look for tool call pattern in response
        patterns = [
            r'```tool\s*\n(.*?)\n```',
            r'\{["\']?tool["\']?\s*:\s*["\'](\w+)["\'].*?\}',
        ]

        for pattern in patterns:
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                try:
                    # Parse the tool call
                    tool_json = match.group(1) if '```' in pattern else match.group(0)
                    tool_data = json.loads(tool_json)
                    tool_name = tool_data.get("tool", "")
                    params = tool_data.get("params", {})

                    if tool_name in self.tools:
                        logger.info(f"Executing tool: {tool_name} with params: {params}")
                        result = self.tools[tool_name].execute(**params)

                        # Remove tool call from response and append result
                        clean_response = llm_response[:match.start()] + llm_response[match.end():]
                        clean_response = clean_response.strip()

                        return True, result, clean_response
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug(f"Tool parse error: {e}")

        return False, "", llm_response

    def get_tools_list(self) -> list[dict]:
        """Get a serializable list of all tools for the API."""
        return [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for name, tool in self.tools.items()
        ]
