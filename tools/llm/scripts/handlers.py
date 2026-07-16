from pathlib import Path

import requests
from core import history
from core.base_tool import CommandResult
from core.engine import _get_forward_model, _get_forward_base_url, _get_forward_api_key

_CURRENT_SESSION_FILE = Path(__file__).parent.parent.parent.parent / "memory" / "current_session"


def handle_forward(target, payload, metadata, ctx):
    if not payload:
        return CommandResult.fail(
            "Provide a message to forward to the AI, e.g., forward(llm)@Tell me a story"
        )

    model = _get_forward_model()
    base_url = _get_forward_base_url()
    api_key = _get_forward_api_key()

    session_id = ""
    if _CURRENT_SESSION_FILE.exists():
        session_id = _CURRENT_SESSION_FILE.read_text(encoding="utf-8").strip()

    context = ""
    if session_id:
        hist = history.load(session_id)
        context = history.format_context(hist)

    input_text = payload
    if context:
        input_text = f"{context}\n{payload}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    messages = [{"role": "user", "content": input_text}]
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000,
    }

    try:
        resp = requests.post(
            f"{base_url}/v1/chat/completions",
            json=body,
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        response_text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")

        if response_text:
            return CommandResult.ok(response_text)
        return CommandResult.ok("(AI returned no text output)")

    except requests.exceptions.ConnectionError:
        return CommandResult.fail(
            "Cannot connect to the configured LLM for AI response. Check llm_base_url setting."
        )
    except requests.exceptions.Timeout:
        return CommandResult.fail("LLM request timed out")
    except Exception as e:
        return CommandResult.fail(f"AI forward error: {e}")
