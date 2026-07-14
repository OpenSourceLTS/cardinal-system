from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path
import json


# Reference vocabulary of all known action verbs in the system.
# When creating a new tool, prefer using an existing verb from this list.
# If none fits, add a new one — this list tracks every top-level action name.
# Each tool declares its own subset under "actions" in manifest.json;
# the router validates against the tool's own list, not this master list.
CANONICAL_VERBS = [
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


# Safety classification for every tool.
class RiskTier(Enum):
    SAFE = 0
    STATEFUL = 1
    NETWORK = 2
    DESTRUCTIVE = 3


# Structured metadata for a tool. Used by the Router for validation
# and by MCP server for building AI-facing descriptions.
@dataclass(frozen=True)
class ToolManifest:
    name: str
    description: str
    actions: List[str]
    target_hint: str
    payload_hint: str
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
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            actions=data.get("actions", []),
            target_hint=data.get("target_hint", ""),
            payload_hint=data.get("payload_hint", ""),
            metadata_schema=data.get("metadata_schema", {}),
            risk_tier=risk_map.get(data.get("risk_tier", "SAFE"), RiskTier.SAFE),
        )


# Internal state for tool discovery
_TOOLS_ROOT = Path(__file__).parent.parent / "tools"
_MANIFEST_CACHE: Dict[str, dict] = {}

_TOOL_DIR_MAP: dict[str, str] = {}


# Builds a tool-name-to-directory-name mapping by scanning tools/*/manifest.json
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


# Returns the raw JSON dict from a tool's manifest.json (cached).
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


# Returns all tool manifest dicts that have the required fields.
# Used by MCP server (to register tools) and engine (to build system prompt).
def discover_tools() -> List[dict]:
    tools = []
    _index_tool_dirs()
    for tool_name, dir_name in _TOOL_DIR_MAP.items():
        data = load_manifest(tool_name)
        required = ["name", "description", "actions", "manifest"]
        if all(k in data for k in required):
            tools.append(data)
    return tools


# Extracts literal target values for a tool+verb from the v@p map.
# Returns empty list when the manifest uses descriptive placeholders
# (like "filename", "keyword") — in that case skip validation.
def get_valid_targets(tool_name: str, verb: str) -> List[str]:
    import re
    data = load_manifest(tool_name)
    manifest = data.get("manifest", {})
    verb_map = manifest.get("v@p", {})
    entries = verb_map.get(verb, [])
    valid = []
    for entry in entries:
        t = entry[0] if entry else ""
        if not t:
            valid.append(t)
        elif re.match(r'^[a-z_][a-z0-9_]*$', t):
            return []
        else:
            valid.append(t)
    return valid


# Converts a tool name to its filesystem directory name
# (e.g. "clock_calendar" -> "clock_and_calendar").
def tool_dir(tool_name: str) -> str:
    _index_tool_dirs()
    return _TOOL_DIR_MAP.get(tool_name, tool_name)


# Dynamically imports the BaseTool subclass from a tool's directory.
# Convention: tools/{dir}/{tool_name}_tool.py contains a class inheriting BaseTool.
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
