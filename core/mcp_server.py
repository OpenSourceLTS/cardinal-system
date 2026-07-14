import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from core.router import Router
from core.base_tool import ExecutionContext
from core.parser import CommandNode
from core.manifest import discover_tools, load_tool_class

# Thread pool for executing batch tool calls in parallel
_PARALLEL_WORKERS = 4
_EXECUTOR = ThreadPoolExecutor(max_workers=_PARALLEL_WORKERS)

MCP_VERSION = "1.0.0"
SERVER_NAME = "cardinal_system_mcp"
SERVER_VERSION = "0.0.1"


# Builds the Router by auto-discovering all tool classes from the filesystem.
# No hardcoded imports — every tool in tools/*/manifest.json gets registered.
def _build_registry() -> Router:
    router = Router()
    for data in discover_tools():
        cls = load_tool_class(data["name"])
        router.register(cls())
    return router


_ROUTER = _build_registry()


# Builds a human-readable description string embedding the tool's manifest
# so the AI can see valid verb/target/payload combinations.
def _build_tool_description(manifest_data: dict) -> str:
    manifest = manifest_data.get("manifest", {})
    example = manifest.get("example", {})
    vp = manifest.get("v@p", {})

    desc = manifest_data.get("description", "")
    risk = manifest_data.get("risk_tier", "SAFE")

    lines = [
        desc,
        f"Risk: {risk}",
        "Structured command fields:",
        f"Example: {json.dumps(example, separators=(',', ':'))}",
        "Valid combinations (verb -> [[target, payload_format], ...]):",
        json.dumps(vp, separators=(',', ':')),
    ]
    return "\n".join(lines)


# Builds one MCP tool definition per discovered tool for the tools/list response.
def _build_tool_definitions() -> list[dict]:
    tools = discover_tools()
    definitions = []
    for data in tools:
        name = data["name"]
        actions = data["actions"]
        description = _build_tool_description(data)

        definitions.append({
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "verb": {
                        "type": "string",
                        "enum": actions,
                        "description": f"Action verb. One of: {', '.join(actions)}"
                    },
                    "target": {
                        "type": "string",
                        "description": (
                            "Resource target. Refer to the manifest above for valid targets "
                            "per verb (e.g., current_time, alarm, days_between, list, read)."
                        )
                    },
                    "payload": {
                        "type": "string",
                        "description": (
                            "Payload data. Refer to the manifest for expected format. "
                            "Use empty string or omit if no payload is needed."
                        )
                    }
                },
                "required": ["verb"]
            }
        })
    return definitions


TOOL_DEFINITIONS = _build_tool_definitions()


# Routes a structured command through the Router's validation pipeline.
def _execute_structured(tool_name: str, verb: str, target: str, payload: str) -> dict:
    ctx = ExecutionContext()
    node = CommandNode(verb=verb, tool=tool_name, target=target, payload=payload, meta={}, deps=[])
    results = _ROUTER.execute_dag([node], ctx)

    output_parts = []
    first_error = None
    for r in results:
        if hasattr(r, "success") and r.success and r.value:
            output_parts.append(str(r.value))
        elif hasattr(r, "success") and not r.success and r.error:
            output_parts.append(f"Error: {r.error}")
            if first_error is None:
                first_error = r.error

    success = any(hasattr(r, "success") and r.success for r in results)

    return {
        "success": success,
        "error": None if success else (first_error or "Unknown error"),
        "output": "\n".join(output_parts),
        "results": [
            {
                "success": r.success,
                "value": str(r.value) if hasattr(r, "value") and r.value is not None else None,
                "error": r.error,
                "tool": getattr(r, "tool", ""),
                "verb": getattr(r, "verb", ""),
                "target": getattr(r, "target", ""),
            }
            for r in results
            if hasattr(r, "success")
        ],
    }


# Sends a JSON-RPC message to stdout for the MCP client to read.
def _send_message(msg: dict):
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


# Reads one JSON-RPC message from stdin (sent by the MCP client).
def _read_message() -> Optional[dict]:
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except (json.JSONDecodeError, EOFError):
        return None


def _handle_initialize(msg: dict) -> dict:
    params = msg.get("params", {})
    client_version = params.get("protocolVersion", MCP_VERSION)
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "protocolVersion": client_version,
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {"tools": {}}
        }
    }


# Returns the full list of tool definitions to the MCP client (e.g., LM Studio).
def _handle_tools_list(msg: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {"tools": TOOL_DEFINITIONS}
    }


def _manifest_for(tool_name: str) -> str:
    for d in TOOL_DEFINITIONS:
        if d["name"] == tool_name:
            return d.get("description", "")
    return ""


# Executes a single tool call and wraps the result in MCP response format.
# On failure, appends the manifest format hint so the AI sees valid options.
def _execute_single(tool_name: str, verb: str, target: str, payload: str) -> dict:
    try:
        result = _execute_structured(tool_name, verb, target, payload)
        text = result["output"] if result["output"] else (
            "Success" if result["success"] else result["error"] or "No output"
        )
        if not result["success"] and result["error"]:
            manifest_hint = _manifest_for(tool_name)
            if manifest_hint:
                text += "\n\nExpected format:\n" + manifest_hint
        return {
            "content": [{"type": "text", "text": text}],
            "isError": not result["success"],
        }
    except Exception as e:
        manifest_hint = _manifest_for(tool_name)
        hint = ("\n\nExpected format:\n" + manifest_hint) if manifest_hint else ""
        return {
            "content": [{"type": "text", "text": f"Execution error: {e}" + hint}],
            "isError": True,
        }


# Handles a tools/call request from the MCP client.
# Validates required arguments and dispatches execution.
def _handle_tools_call(msg: dict) -> dict:
    params = msg.get("params", {})
    arguments = params.get("arguments", {})
    tool_name = params.get("name", "")
    verb = arguments.get("verb", "")
    target = arguments.get("target", "")
    payload = arguments.get("payload", "")

    if not tool_name:
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {"code": -32000, "message": "Missing tool name"}
        }
    if not verb:
        available = ", ".join(d["name"] for d in TOOL_DEFINITIONS)
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {
                "code": -32000,
                "message": f"Missing required argument: verb={verb!r}. "
                           f"Available tools: {available}"
            }
        }
    if target is None:
        target = ""

    result = _execute_single(tool_name, verb, target, payload)
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": result,
    }


# Executes a batch of tool calls in parallel and returns ordered results.
# Notifications (messages with no id) are skipped per JSON-RPC spec.
def _handle_batch(calls: list) -> list:
    if not calls:
        return []

    def work(call):
        call_id = call.get("id")
        if call_id is None:
            return None
        params = call.get("params", {})
        args = params.get("arguments", {})
        tool_name = params.get("name", "")
        verb = args.get("verb", "")
        target = args.get("target", "")
        payload = args.get("payload", "")
        result = _execute_single(tool_name, verb, target, payload)
        return {"jsonrpc": "2.0", "id": call_id, "result": result}

    futures = {_EXECUTOR.submit(work, call): i for i, call in enumerate(calls)}
    ordered = [None] * len(calls)
    for future in as_completed(futures):
        idx = futures[future]
        ordered[idx] = future.result()
    return ordered


_HANDLERS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}


# Dispatches a single JSON-RPC message to its handler based on method name.
def _process_single(msg: dict):
    method = msg.get("method", "")
    handler = _HANDLERS.get(method)

    if method == "notifications/initialized":
        return
    if method == "notifications/cancelled":
        return

    if handler:
        try:
            response = handler(msg)
            _send_message(response)
        except Exception as e:
            _send_message({
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {"code": -32603, "message": f"Internal error: {e}"}
            })
    else:
        _send_message({
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })


# Main loop: reads JSON-RPC messages from stdin, handles single or batch requests.
def run_mcp_server():
    while True:
        raw = _read_message()
        if raw is None:
            break

        # JSON-RPC batch request — an array of calls
        if isinstance(raw, list):
            responses = _handle_batch(raw)
            filtered = [r for r in responses if r is not None]
            if filtered:
                line = json.dumps(filtered, ensure_ascii=False)
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
        else:
            _process_single(raw)


if __name__ == "__main__":
    run_mcp_server()
