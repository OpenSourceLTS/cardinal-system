import json
from typing import Optional
import requests

from . import history
from .manifest import discover_tools


# Dynamically builds the system prompt from manifest.json of every registered tool.
# This keeps the prompt in sync when tools are added or removed.
def _build_system_prompt() -> str:
    tools = discover_tools()
    names = ", ".join(t.get("name", "") for t in tools)
    first_example = ""
    for t in tools:
        ex = t.get("manifest", {}).get("example", {})
        if ex and ex.get("verb") and ex.get("target"):
            first_example = f'{t["name"]} with verb={ex["verb"]} target={ex["target"]}'
            break
    parts = [
        f"You are an autonomous AI assistant connected to the Cardinal system via MCP.",
        f"Available Tools: {names}",
        "Directives:",
        "- ACTION REQUIRED: You MUST use tool calls to fetch dynamic information or perform state changes for every request.",
        "- NO ASSUMPTIONS: Never assume a request is already handled. Never answer from internal knowledge or hallucinate.",
        "- EXECUTION: Always call the relevant tool(s) to fulfill the user's intent, and base your final response strictly on tool outputs."
    ]
    if first_example:
        parts.append(f'Example: for "what time is it" -> call {first_example}')
    return " ".join(parts)


_SYSTEM_PROMPT = _build_system_prompt()

# LM Studio API configuration
LM_STUDIO_URL = "http://localhost:1234"
LM_STUDIO_API_KEY = "sk-lm-PHYEPjg2:mVmPUGvdDo0PYzbjsYYK"
MODEL = "gemma-3-270m-it"


# Sends user input to LM Studio's native API with MCP integration.
# The model decides which tools to call; results come back inline.
class CardinalSystemEngine:
    def __init__(self):
        self.session_id: Optional[str] = None

    # Prepends conversation history (English-only for assistant replies)
    # so the model has context from previous turns.
    def _build_input(self, user_input: str) -> str:
        if not self.session_id:
            return user_input
        hist = history.load(self.session_id)
        ctx = history.format_context(hist)
        if ctx:
            return f"{ctx} {user_input}"
        return user_input

    def process_request(self, user_input: str, session_id: str = "") -> dict:
        self.session_id = session_id or None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LM_STUDIO_API_KEY}",
        }

        payload = {
            "model": MODEL,
            "input": self._build_input(user_input),
            "system_prompt": _SYSTEM_PROMPT,
            "integrations": ["mcp/cardinal-system"],
            "context_length": 8192,
            "temperature": 0.3,
            "max_output_tokens": 2000,
        }

        try:
            resp = requests.post(
                f"{LM_STUDIO_URL}/api/v1/chat",
                json=payload,
                headers=headers,
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to LM Studio at " + LM_STUDIO_URL}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "LM Studio request timed out"}
        except Exception as e:
            return {"success": False, "error": f"LM Studio error: {e}"}

        # Separate text messages from tool call results
        output_items = data.get("output", [])
        texts = []
        tool_results = []
        for item in output_items:
            if item.get("type") == "message":
                texts.append(item.get("content", ""))
            elif item.get("type") == "tool_call":
                tool_results.append({
                    "tool": item.get("tool", ""),
                    "arguments": item.get("arguments", {}),
                    "output": item.get("output", ""),
                })

        response_text = " ".join(texts).strip()
        stats = data.get("stats", {})

        if self.session_id:
            pass  # History saving is handled by web_server.py

        return {
            "success": True,
            "is_chat": True,
            "response": response_text,
            "results": tool_results,
            "stats": stats,
            "raw_output": json.dumps(output_items, ensure_ascii=False),
        }
