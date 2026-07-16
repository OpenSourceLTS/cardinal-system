from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path
import json
import re


# Reference vocabulary of all known action actions in the system.
CANONICAL_ACTIONS = [
    "append", "approve", "archive", "ask", "block", "bookmark", "branch",
    "calculate", "change", "cancel", "check", "clear", "comment", "commit",
    "complete", "compress", "convert", "copy", "create",
    "decline", "decrypt", "delete", "deny", "deploy", "directions", "disable", "dismiss",
    "enable", "embed", "encrypt", "exec", "extract",
    "fetch", "follow", "forecast", "forward",
    "generate", "get", "grant", "grab",
    "like", "list", "log",
    "mention", "merge", "move", "mute",
    "navigate",
    "pair", "paste", "pause", "pin", "place", "play", "post", "predict", "publish", "pull", "push",
    "query", "queue",
    "react", "read", "release", "remind", "remove", "rename", "reply", "report", "reschedule",
    "reset", "restore", "revoke", "rollback", "run",
    "say", "schedule", "search", "send", "set", "save", "share", "sort", "stop", "stream",
    "subscribe", "sync",
    "toggle", "translate", "train",
    "unblock", "uncheck", "unfollow", "unmute", "unpin", "unsubscribe", "update", "upload",
    "write",
]


class RiskTier(Enum):
    SAFE = 0
    STATEFUL = 1
    NETWORK = 2
    DESTRUCTIVE = 3


@dataclass(frozen=True)
class ToolManifest:
    name: str
    description: str
    actions: List[str]
    target_hint: str
    payload_hint: str
    functions: Dict[str, dict]
    metadata_schema: Optional[Dict[str, str]] = None
    risk_tier: RiskTier = RiskTier.SAFE
    requires_confirmation: bool = False

    @classmethod
    def from_json(cls, data: dict) -> "ToolManifest":
        risk_map = {
            "SAFE": RiskTier.SAFE,
            "STATEFUL": RiskTier.STATEFUL,
            "NETWORK": RiskTier.NETWORK,
            "DESTRUCTIVE": RiskTier.DESTRUCTIVE,
        }
        funcs = data.get("functions", {})
        actions = sorted(set(
            fn.get("action", "") for fn in funcs.values() if fn.get("action")
        ))
        targets = sorted(set(
            expr for fn in funcs.values()
            for key in ("target", "target_expr")
            for expr in [fn.get(key, "")]
            if expr and not expr.startswith("{")
        ))
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            actions=actions,
            target_hint=", ".join(targets) if targets else "",
            payload_hint="value",
            functions=funcs,
            metadata_schema=data.get("metadata_schema", {}),
            risk_tier=risk_map.get(data.get("risk_tier", "SAFE"), RiskTier.SAFE),
        )


_TOOLS_ROOT = Path(__file__).parent.parent / "tools"
_MANIFEST_CACHE: Dict[str, dict] = {}
_TOOL_DIR_MAP: dict[str, str] = {}
_FUNCTION_REGISTRY_CACHE: Dict[str, dict] = {}


def _index_tool_dirs():
    if _TOOL_DIR_MAP:
        return
    if not _TOOLS_ROOT.exists():
        return
    for folder in _TOOLS_ROOT.iterdir():
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", folder.name)
            _TOOL_DIR_MAP[name] = folder.name
        except Exception:
            _TOOL_DIR_MAP[folder.name] = folder.name


def load_manifest(tool_name: str) -> dict:
    if tool_name in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[tool_name]
    _index_tool_dirs()
    dir_name = _TOOL_DIR_MAP.get(tool_name, tool_name)
    path = _TOOLS_ROOT / dir_name / "manifest.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _MANIFEST_CACHE[tool_name] = data
                return data
        except Exception:
            pass
    _MANIFEST_CACHE[tool_name] = {}
    return {}


def discover_tools() -> List[dict]:
    tools = []
    _index_tool_dirs()
    for tool_name, dir_name in _TOOL_DIR_MAP.items():
        data = load_manifest(tool_name)
        if data.get("name") and data.get("description") and data.get("functions"):
            tools.append(data)
    return tools


def get_function_registry() -> Dict[str, dict]:
    global _FUNCTION_REGISTRY_CACHE
    if _FUNCTION_REGISTRY_CACHE:
        return _FUNCTION_REGISTRY_CACHE
    registry = {}
    _index_tool_dirs()
    for tool_name in _TOOL_DIR_MAP:
        data = load_manifest(tool_name)
        functions = data.get("functions", {})
        for func_name, fn_def in functions.items():
            registry[func_name] = {
                "tool": tool_name,
                "action": fn_def.get("action", ""),
                "target_expr": fn_def.get("target_expr") or fn_def.get("target", ""),
                "payload_expr": fn_def.get("payload_expr") or fn_def.get("payload", ""),
                "parameters": fn_def.get("parameters", {}),
                "required": fn_def.get("required", []),
                "description": fn_def.get("description", ""),
            }
    _FUNCTION_REGISTRY_CACHE = registry
    return registry


def resolve_function_call(func_name: str, arguments: dict) -> tuple:
    """Convert a function call with specific params to (tool, action, target, payload)."""
    registry = get_function_registry()
    entry = registry.get(func_name)
    if not entry:
        return None, None, None, None

    tool = entry["tool"]
    action = entry["action"]
    target_expr = entry.get("target_expr", "")
    payload_expr = entry.get("payload_expr", "")

    def resolve_template(template: str) -> str:
        if not template:
            return ""
        result = template
        for key, val in arguments.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, (val or "").strip())
        import re
        result = re.sub(r'\{(\w+)\}', '', result)
        result = re.sub(r'\s*\|\s*$', '', result)
        result = re.sub(r'^\s*\|\s*', '', result)
        result = re.sub(r'  +', ' ', result).strip()
        return result

    target = resolve_template(target_expr)
    payload = resolve_template(payload_expr)

    return tool, action, target, payload


def get_valid_targets(tool_name: str, action: str) -> List[str]:
    data = load_manifest(tool_name)
    functions = data.get("functions", {})
    valid = []
    for fn_name, fn_def in functions.items():
        if fn_def.get("action") == action:
            target_expr = fn_def.get("target_expr", "")
            if not target_expr or target_expr.startswith("{"):
                return []
            valid.append(target_expr)
    return valid


def tool_dir(tool_name: str) -> str:
    _index_tool_dirs()
    return _TOOL_DIR_MAP.get(tool_name, tool_name)


def load_tool_class(tool_name: str):
    import importlib
    from .base_tool import BaseTool
    dir_name = tool_dir(tool_name)
    module = importlib.import_module(f"tools.{dir_name}.{tool_name}_tool")
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if isinstance(obj, type) and issubclass(obj, BaseTool) and obj is not BaseTool:
            return obj
    raise ImportError(f"No BaseTool subclass found in tools.{dir_name}.{tool_name}_tool")


def clear_cache():
    _MANIFEST_CACHE.clear()
    _TOOL_DIR_MAP.clear()
    _FUNCTION_REGISTRY_CACHE.clear()
