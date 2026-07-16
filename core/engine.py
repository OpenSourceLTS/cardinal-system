import json
import re
import random
from typing import Optional
from pathlib import Path
import requests


SETTINGS_FILE = Path(__file__).parent.parent / "memory" / "settings.md"
CURRENT_SESSION_FILE = Path(__file__).parent.parent / "memory" / "current_session"


_MAX_TOOLS = 8


_TOOL_KEYWORDS = {
    "get_time": ["time", "clock", "what time", "current time", "hour"],
    "get_date": ["date", "what date", "current date", "today date", "todays date"],
    "get_datetime": ["date and time", "datetime", "current date and time"],
    "get_day_of_week": ["day of week", "what day", "weekday", "day of the week"],
    "get_timezone_info": ["timezone", "time zone", "what timezone"],
    "get_moon_phase": ["moon", "lunar", "moon phase"],
    "get_season": ["season", "what season"],
    "list_alarms": ["alarms", "list alarm", "show alarm", "my alarms", "what alarms"],
    "set_alarm": ["set alarm", "create alarm", "new alarm", "add alarm", "wake"],
    "delete_alarm": ["delete alarm", "remove alarm", "cancel alarm", "dismiss alarm"],
    "list_timers": ["timers", "list timer", "show timer", "my timers"],
    "set_timer": ["set timer", "create timer", "new timer", "start timer", "countdown"],
    "delete_timer": ["delete timer", "remove timer", "cancel timer"],
    "get_stopwatch_status": ["stopwatch", "stop watch", "elapsed"],
    "control_stopwatch": ["start stopwatch", "stop stopwatch", "reset stopwatch"],
    "list_events": ["events", "list event", "show event", "my events", "calendar"],
    "schedule_event": ["schedule", "create event", "new event", "add event", "appointment", "meeting", "remind"],
    "delete_event": ["delete event", "remove event", "cancel event"],
    "calculate_time_until": ["time until", "how long until", "hours until", "minutes until", "countdown to"],
    "calculate_time_since": ["time since", "how long since", "hours since", "since"],
    "calculate_date_offset": ["days from", "weeks from", "date offset", "after", "before", "from today", "from now"],
    "calculate_duration": ["duration", "between dates", "how many days", "how long between"],
    "check_leap_year": ["leap year", "is leap"],
    "list_notes": ["notes", "list note", "show note", "my notes", "all notes"],
    "save_note": ["save note", "create note", "new note", "write note", "make note"],
    "read_note": ["read note", "open note", "show note", "view note"],
    "append_note": ["append", "add to note", "prepend"],
    "search_notes": ["search", "find note", "look for", "search note"],
    "replace_in_note": ["replace", "find and replace", "change text"],
    "edit_note_line": ["edit note", "change line", "modify note", "update note"],
    "rename_note": ["rename note", "move note"],
    "delete_note": ["delete note", "remove note"],
    "translate_text": ["translate", "translation", "convert to", "how do you say", "in spanish", "in french", "in arabic"],
    "detect_language": ["detect language", "what language", "identify language"],
    "list_languages": ["list language", "available language", "what languages"],
    "list_settings": ["settings", "preferences", "show settings", "my settings"],
    "set_setting": ["set setting", "change setting", "update setting", "set preference"],
    "delete_setting": ["delete setting", "remove setting", "reset setting"],
    "forward_to_ai": ["forward_to_ai", "ask ai", "ask the ai", "conversation", "chat", "talk to", "general question"],
}


def _match_keyword(kw: str, query_words: set) -> bool:
    kw_words = kw.split()
    return all(w in query_words for w in kw_words)


def _select_tools(query: str, tools_spec: list[dict], max_tools: int = _MAX_TOOLS) -> list[dict]:
    query_lower = query.lower()
    query_words = set(query_lower.split())
    scored = []
    for spec in tools_spec:
        fname = spec["function"]["name"]
        keywords = _TOOL_KEYWORDS.get(fname, [])
        score = 0
        for kw in keywords:
            if _match_keyword(kw, query_words) or kw in query_lower:
                score += 1
        scored.append((score, spec))
    scored.sort(key=lambda x: -x[0])
    selected = [spec for score, spec in scored if score > 0]
    if not selected:
        return tools_spec[:max_tools]
    return selected[:max_tools]


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
    prefs = _read_settings()
    return prefs.get("forward_model", "qwen3-0.6b-heretic-abliterated-uncensored")


def _get_forward_base_url() -> str:
    return _get_lm_studio_url()


def _get_forward_api_key() -> str:
    return _get_api_key()


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
                prop = {"type": pdef.get("type", "string").lower()}
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
                        "type": "object",
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


def _parse_fg(text: str, max_calls: int = 5) -> list[dict]:
    calls = []
    seen = set()
    _ARG_RE = re.compile(r'(\w+):(?:<escape>(.*?)<escape>|([^,}]+))')
    # Split on <end_function_call> to isolate each call
    for segment in re.split(r'<end_function_call>', text):
        segment = re.sub(r'<start_function_call>', '', segment).strip()
        if not segment:
            continue
        # Try old format: call:func{args}
        m = re.match(r'call:(\w+)\{(.*)\}', segment)
        if not m:
            # Try new (fine-tuned) format: call{func{args}<escape>}
            m = re.match(r'call\{(\w+)\{(.*?)\}(?:<escape>.*?\}?)?\}', segment)
        if not m:
            continue
        func_name = m.group(1)
        if func_name in seen:
            continue
        seen.add(func_name)
        raw_args = m.group(2).strip()
        args = {}
        if raw_args:
            for am in _ARG_RE.finditer(raw_args):
                k = am.group(1)
                v = (am.group(2) or am.group(3) or "").strip()
                args[k] = v
        calls.append({"function": func_name, "arguments": args})
        if len(calls) >= max_calls:
            break
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
        "temperature": 0.1,
        "max_tokens": 512,
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

        tools_subset = _select_tools(user_input, _TOOLS_SPEC)

        try:
            messages = [
                {"role": "user", "content": user_input},
            ]
            output = _chat_completion(messages, model, url, key, tools=tools_subset)
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

        non_fwd_results = [r for r in tool_results if r["tool"] != "forward_to_ai"]
        fwd_errors = [r for r in tool_results if r["tool"] == "forward_to_ai" and r.get("error")]

        if fwd_errors and not non_fwd_results:
            return {
                "success": False,
                "response": fwd_errors[0]["error"],
                "results": tool_results,
            }

        output = "\n".join(
            r.get("output", "") for r in non_fwd_results if r.get("output")
        )
        return {"success": True, "response": output, "results": tool_results}
