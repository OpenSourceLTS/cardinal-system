import json
from pathlib import Path

# Conversation history is stored as JSON files in memory/history/{session_id}.json
HISTORY_DIR = Path(__file__).parent.parent / "memory" / "history"
MAX_TURNS = 20  # Keep only the most recent N turns


def _session_path(session_id: str) -> Path:
    return HISTORY_DIR / f"{session_id}.json"


# Returns a list of {id, message_count, preview} for the session selector UI.
def list_sessions() -> list[dict]:
    if not HISTORY_DIR.exists():
        return []
    sessions = []
    for f in sorted(HISTORY_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix == ".json" and f.stem:
            hist = load(f.stem)
            first_msg = hist[0]["content"][:60] if hist else ""
            sessions.append({
                "id": f.stem,
                "message_count": len(hist),
                "preview": first_msg,
            })
    return sessions


def create(session_id: str):
    path = _session_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        save(session_id, [])


def delete(session_id: str):
    path = _session_path(session_id)
    if path.exists():
        path.unlink()


def load(session_id: str) -> list[dict]:
    path = _session_path(session_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save(session_id: str, history: list[dict]):
    path = _session_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# `content` is always English (AI context). `user_original` holds the user's original input.
# `translated_response` holds the assistant's reply translated to the user's language.
# `tool_name` and `tool_args` capture tool call metadata for model context.
def append(session_id: str, role: str, content: str, translated_response: str = "", user_original: str = "", tool_name: str = "", tool_args: str = ""):
    history = load(session_id)
    entry = {"role": role, "content": content}
    if translated_response:
        entry["translated_response"] = translated_response
    if user_original:
        entry["user_original"] = user_original
    if tool_name:
        entry["tool_name"] = tool_name
    if tool_args:
        entry["tool_args"] = tool_args
    history.append(entry)
    if len(history) > MAX_TURNS:
        history = history[-MAX_TURNS:]
    save(session_id, history)


def format_context(history: list[dict]) -> str:
    if not history:
        return ""
    lines = ["Conversation log:"]
    for entry in history:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role == "tool":
            tn = entry.get("tool_name", "tool")
            ta = entry.get("tool_args", "")
            lines.append(f"Tool result ({tn} {ta}): {content}")
        else:
            lines.append(f"User: {content}" if role == "user" else f"Assistant: {content}")
        lines.append("")
    return "\n".join(lines)
