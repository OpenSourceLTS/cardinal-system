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
from core.manifest import discover_tools, load_tool_class, resolve_function_call, get_function_registry

_PARALLEL_WORKERS = 4
_EXECUTOR = ThreadPoolExecutor(max_workers=_PARALLEL_WORKERS)

MCP_VERSION = "1.0.0"
SERVER_NAME = "cardinal_system_mcp"
SERVER_VERSION = "0.0.1"


def _build_registry() -> Router:
    router = Router()
    for data in discover_tools():
        cls = load_tool_class(data["name"])
        router.register(cls())
    return router


_ROUTER = _build_registry()


def _build_tool_definitions() -> list[dict]:
    defs = []
    for data in discover_tools():
        functions = data.get("functions", {})
        for func_name, fn_def in functions.items():
            params_schema = fn_def.get("parameters", {})
            properties = {}
            required = fn_def.get("required", [])
            for pname, pdef in params_schema.items():
                properties[pname] = {
                    "type": pdef.get("type", "string").lower(),
                }
                if "description" in pdef:
                    properties[pname]["description"] = pdef["description"]
                if "enum" in pdef:
                    properties[pname]["enum"] = pdef["enum"]
            defs.append({
                "name": func_name,
                "description": fn_def.get("description", data.get("description", "")),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": list(required) if required else [],
                }
            })
    return defs


TOOL_DEFINITIONS = _build_tool_definitions()


def _execute_structured(tool_name: str, action: str, target: str, payload: str) -> dict:
    ctx = ExecutionContext()
    node = CommandNode(action=action, tool=tool_name, target=target, payload=payload, meta={}, deps=[])
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
                "action": getattr(r, "action", ""),
                "target": getattr(r, "target", ""),
            }
            for r in results
            if hasattr(r, "success")
        ],
    }


def _send_message(msg: dict):
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


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


def _execute_single(tool_name: str, action: str, target: str, payload: str) -> dict:
    try:
        result = _execute_structured(tool_name, action, target, payload)
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


def _handle_tools_call(msg: dict) -> dict:
    params = msg.get("params", {})
    arguments = params.get("arguments", {})
    func_name = params.get("name", "")

    if not func_name:
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {"code": -32000, "message": "Missing function name"}
        }

    tool, action, target, payload = resolve_function_call(func_name, arguments)

    if not tool or not action:
        registry = get_function_registry()
        available = ", ".join(sorted(registry.keys()))
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {"code": -32000, "message": f"Unknown function: '{func_name}'. Available: {available}"}
        }

    result = _execute_single(tool, action, target, payload)
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": result,
    }


def _handle_batch(calls: list) -> list:
    if not calls:
        return []

    def work(call):
        call_id = call.get("id")
        if call_id is None:
            return None
        params = call.get("params", {})
        args = params.get("arguments", {})
        func_name = params.get("name", "")
        tool, action, target, payload = resolve_function_call(func_name, args)
        result = _execute_single(tool or func_name, action or "", target or "", payload or "")
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


def run_mcp_server():
    while True:
        raw = _read_message()
        if raw is None:
            break

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
