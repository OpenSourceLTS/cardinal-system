import requests
from core.base_tool import CommandResult
from core.engine import _get_forward_model, _get_forward_base_url, _get_forward_api_key


def handle_forward(target, payload, metadata, ctx):
    if not payload:
        return CommandResult.fail(
            "Provide a message to forward to the AI, e.g., forward(llm)@Tell me a story"
        )

    model = _get_forward_model()
    base_url = _get_forward_base_url()
    api_key = _get_forward_api_key()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    body = {
        "model": model,
        "input": payload,
        "system_prompt": "You are a helpful AI assistant.",
        "integrations": ["mcp/cardinal-system"],
        "context_length": 8192,
        "temperature": 0.7,
        "max_output_tokens": 1000,
    }

    try:
        resp = requests.post(
            f"{base_url}/api/v1/chat",
            json=body,
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        output_items = data.get("output", [])
        texts = [
            item.get("content", "")
            for item in output_items
            if item.get("type") == "message"
        ]
        response_text = " ".join(texts).strip()

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
