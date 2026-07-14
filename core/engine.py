import json
from typing import Optional
from pathlib import Path
import requests


SETTINGS_FILE = Path(__file__).parent.parent / "memory" / "settings.md"
CURRENT_SESSION_FILE = Path(__file__).parent.parent / "memory" / "current_session"


def _read_settings() -> dict:
    prefs = {}
    if SETTINGS_FILE.exists():
        for line in SETTINGS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, val = line.partition(":")
                prefs[key.strip()] = val.strip()
    return prefs


def _get_lm_studio_url() -> str:
    return _read_settings().get("fc_base_url", "http://localhost:1234")


def _get_api_key() -> str:
    return _read_settings().get("fc_api_key", "sk-lm-PHYEPjg2:mVmPUGvdDo0PYzbjsYYK")


def _get_model() -> str:
    return _read_settings().get("fc_model", "functiongemma-270m-it")


def _get_forward_model() -> str:
    return "qwen3-0.6b-heretic-abliterated-uncensored"


def _get_forward_base_url() -> str:
    return _read_settings().get("llm_base_url", "http://localhost:1234")


def _get_forward_api_key() -> str:
    return _read_settings().get("llm_api_key", "sk-lm-PHYEPjg2:mVmPUGvdDo0PYzbjsYYK")


def _build_system_prompt() -> str:
    return (
        "You are Cardinal, an AI assistant with tools.\n"
        "Directives:\n"
        "- Use tool calls to fetch dynamic information or perform state changes.\n"
        "- Never answer from internal knowledge. Base responses on tool outputs.\n"
        "- For conversation or complex reasoning, forward to the 'llm' tool."
    )


_SYSTEM_PROMPT = _build_system_prompt()


class CardinalSystemEngine:
    def __init__(self):
        self.session_id: Optional[str] = None

    def _build_input(self, user_input: str) -> str:
        return user_input

    def process_request(self, user_input: str, session_id: str = "") -> dict:
        self.session_id = session_id or None

        CURRENT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        CURRENT_SESSION_FILE.write_text(self.session_id or "", encoding="utf-8")

        lm_studio_url = _get_lm_studio_url()
        api_key = _get_api_key()
        model = _get_model()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "model": model,
            "input": self._build_input(user_input),
            "system_prompt": _SYSTEM_PROMPT,
            "integrations": ["mcp/cardinal-system"],
            "context_length": 8192,
            "temperature": 0.3,
            "max_output_tokens": 2000,
        }

        try:
            resp = requests.post(
                f"{lm_studio_url}/api/v1/chat",
                json=payload,
                headers=headers,
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to LM Studio at " + lm_studio_url}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "LM Studio request timed out"}
        except Exception as e:
            return {"success": False, "error": f"LM Studio error: {e}"}

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

        return {
            "success": True,
            "is_chat": True,
            "response": response_text,
            "results": tool_results,
            "stats": stats,
            "raw_output": json.dumps(output_items, ensure_ascii=False),
        }
