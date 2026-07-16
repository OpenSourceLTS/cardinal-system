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
    return _read_settings().get("fc_model", "functiongemma-finetuned@f16")


def _get_forward_model() -> str:
    return "qwen3-0.6b-heretic-abliterated-uncensored"


def _get_forward_base_url() -> str:
    return "http://localhost:1235"


def _get_forward_api_key() -> str:
    return "sk-lm-PHYEPjg2:mVmPUGvdDo0PYzbjsYYK"


def _build_tools_spec() -> list[dict]:
    from core.manifest import discover_tools

    specs = []
    for data in discover_tools():
        functions = data.get("functions", {})
        for func_name, fn_def in functions.items():
            params_schema = fn_def.get("parameters", {})
            properties = {}
            required = fn_def.get("required", [])
            for pname, pdef in params_schema.items():
                prop = {"type": pdef.get("type", "STRING")}
                if "description" in pdef:
                    prop["description"] = pdef["description"]
                if "enum" in pdef:
                    prop["enum"] = pdef["enum"]
                properties[pname] = prop
            specs.append({
                "type": "function",
                "function": {
                    "name": func_name,
                    "description": fn_def.get("description", data.get("description", "")),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": properties,
                    },
                },
            })
            if required:
                specs[-1]["function"]["parameters"]["required"] = list(required)
    return specs


_TOOLS_SPEC = _build_tools_spec()

_USER_SETTINGS = {"timezone", "time_format", "spoken_lang"}


def _build_system_prompt() -> str:
    prefs = _read_settings()
    parts = ["You are Cardinal, an AI assistant."]
    user_prefs = {k: v for k, v in prefs.items() if k in _USER_SETTINGS}
    if user_prefs:
        pair_str = "; ".join(f"{k}={v}" for k, v in user_prefs.items())
        parts.append(f"User preferences: {pair_str}")
    return "\n".join(parts)


_FG_CALL_RE = re.compile(
    r"<start_function_call>call:(?P<tool>\w+)\{(?P<args>[^}]*)\}<end_function_call>"
)


def _parse_fg(text: str) -> list[dict]:
    calls = []
    for match in _FG_CALL_RE.finditer(text):
        func_name = match.group("tool")
        args = {}
        raw_args = match.group("args").strip()
        if raw_args:
            for part in raw_args.split(","):
                part = part.strip()
                if ":" not in part:
                    continue
                k, _, v = part.partition(":")
                args[k.strip()] = v.strip().replace("<escape>", "")
        calls.append({"function": func_name, "arguments": args})
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
                {"role": "developer", "content": _build_system_prompt()},
                {"role": "user", "content": user_input},
            ]
            output = _chat_completion(messages, model, url, key, tools=_TOOLS_SPEC)
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to LM Studio at " + url}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "LM Studio request timed out"}
        except Exception as e:
            return {"success": False, "error": f"LM Studio error: {e}"}

        from core.manifest import resolve_function_call

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
            func_name = call["function"]
            args = call["arguments"]
            tool, action, target, payload = resolve_function_call(func_name, args)
            if not tool:
                tool_results.append({
                    "tool": func_name,
                    "arguments": args,
                    "output": "",
                    "error": f"Unknown function: '{func_name}'",
                })
                continue
            result = _execute_structured(tool, action, target, payload)
            tool_results.append({
                "tool": func_name,
                "arguments": args,
                "output": result.get("output", ""),
                "error": result.get("error"),
            })

        for i, call in enumerate(fg_calls):
            func_name = call["function"]
            if func_name == "forward_to_ai" and tool_results[i].get("output"):
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

        return {
            "success": True,
            "response": tool_results[0].get("output", str(tool_results)),
            "results": tool_results,
        }
