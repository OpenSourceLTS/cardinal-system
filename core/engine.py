import json
import re
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
    return _read_settings().get("fc_model", "functiongemma-finetuned")


def _get_forward_model() -> str:
    return _read_settings().get("llm_model", "qwen3-0.6b-heretic-abliterated-uncensored")


def _get_forward_base_url() -> str:
    return _read_settings().get("llm_base_url", "http://localhost:1235")


def _get_forward_api_key() -> str:
    return _read_settings().get("llm_api_key", "sk-lm-PHYEPjg2:mVmPUGvdDo0PYzbjsYYK")


def _build_tools_spec() -> list[dict]:
    from core.manifest import discover_tools as _discover_tools

    specs = []
    for t in _discover_tools():
        vp = t.get("manifest", {}).get("a@p", {})
        all_targets = []
        for entries in vp.values():
            for e in entries:
                tg = e[0] if e else ""
                if tg and tg not in all_targets:
                    all_targets.append(tg)
        props = {
            "action": {"type": "string", "enum": t["actions"]},
            "target": {"type": "string"},
            "payload": {"type": "string"},
        }
        if all_targets:
            props["target"] = {"type": "string", "enum": all_targets}
        specs.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": ["action"],
                },
            },
        })
    return specs


_TOOLS_SPEC = _build_tools_spec()

_SYSTEM_PROMPT = (
    "You are Cardinal, an AI assistant with tools.\n"
    "Directives:\n"
    "- Use tool calls to fetch dynamic information or perform state changes.\n"
    "- Never answer from internal knowledge. Base responses on tool outputs.\n"
    "- For conversation or complex reasoning, forward to the 'llm' tool."
)

# FunctionGemma native format regex
_FG_CALL_RE = re.compile(
    r"<start_function_call>call:(?P<tool>\w+)\{(?P<args>[^}]*)\}<end_function_call>"
)


def _parse_fg(text: str) -> list[dict]:
    calls = []
    for match in _FG_CALL_RE.finditer(text):
        tool = match.group("tool")
        args = {}
        for part in match.group("args").split(","):
            part = part.strip()
            if ":" not in part:
                continue
            k, _, v = part.partition(":")
            args[k.strip()] = v.strip().replace("<escape>", "")
        calls.append({"tool": tool, "arguments": args})
    return calls


def _chat_completion(
    messages: list[dict],
    model: str,
    base_url: str,
    api_key: str,
    tools: Optional[list] = None,
) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    if tools is not None:
        payload["tools"] = tools
    resp = requests.post(
        f"{base_url}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"] or ""
    return content


class CardinalSystemEngine:
    def __init__(self):
        self.session_id: Optional[str] = None

    def process_request(self, user_input: str, session_id: str = "") -> dict:
        self.session_id = session_id or None

        CURRENT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        CURRENT_SESSION_FILE.write_text(self.session_id or "", encoding="utf-8")

        url = _get_lm_studio_url()
        key = _get_api_key()
        model = _get_model()

        try:
            messages = [
                {"role": "developer", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]
            output = _chat_completion(messages, model, url, key, tools=_TOOLS_SPEC)
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to LM Studio at " + url}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "LM Studio request timed out"}
        except Exception as e:
            return {"success": False, "error": f"LM Studio error: {e}"}

        fg_calls = _parse_fg(output)

        if not fg_calls:
            return {
                "success": True,
                "response": output,
                "results": [],
            }

        from core.mcp_server import _execute_structured

        tool_results = []
        for call in fg_calls:
            tool_name = call["tool"]
            args = call["arguments"]
            payload = args.get("payload", "")
            if payload == "$prev":
                payload = ""
            result = _execute_structured(
                tool_name,
                args.get("action", ""),
                args.get("target", ""),
                payload,
            )
            tool_results.append({
                "tool": tool_name,
                "arguments": args,
                "output": result.get("output", ""),
                "error": result.get("error"),
            })

        for i, call in enumerate(fg_calls):
            if call["tool"] == "llm" and tool_results[i].get("output"):
                return {
                    "success": True,
                    "response": tool_results[i]["output"],
                    "results": tool_results,
                }

        has_errors = any(r.get("error") for r in tool_results)
        if has_errors:
            errors = [r["error"] for r in tool_results if r.get("error")]
            return {
                "success": False,
                "response": "\n".join(errors),
                "results": tool_results,
            }

        # Return raw tool result (FG is a dispatcher, not a chat model)
        return {
            "success": True,
            "response": tool_results[0].get("output", str(tool_results)),
            "results": tool_results,
        }
