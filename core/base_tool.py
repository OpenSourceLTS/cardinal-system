from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, List
from .manifest import ToolManifest


# Standard result wrapper returned by every tool execution.
# success=True + value=output  OR  success=False + error=message
@dataclass
class CommandResult:
    success: bool
    value: Any = None
    error: Optional[str] = None
    tool: str = ""
    verb: str = ""
    target: str = ""

    @staticmethod
    def ok(value, tool="", verb="", target=""):
        return CommandResult(True, value=value, tool=tool, verb=verb, target=target)

    @staticmethod
    def fail(msg, tool="", verb="", target=""):
        return CommandResult(False, error=msg, tool=tool, verb=verb, target=target)


# Shared state passed through a pipeline of tool calls.
# Holds previous results, a memo dict for cross-command data, and the user's timezone.
class ExecutionContext:
    def __init__(self, timezone: str = "UTC"):
        self.results: List[CommandResult] = []
        self.memo: dict = {}
        self.timezone: str = timezone

    # Resolves $prev, $1..$N, and memo:// references to actual values from prior steps.
    def resolve_ref(self, value: str, results: List[CommandResult]) -> str:
        if not value: return value
        if value == "$prev" and self.results:
            return str(self.results[-1].value)
        if value.startswith("$") and value[1:].isdigit():
            idx = int(value[1:]) - 1
            if 0 <= idx < len(results) and results[idx] and results[idx].value:
                return str(results[idx].value)
        if value.startswith("memo://"):
            return str(self.memo.get(value[len("memo://"):]))
        return value


# Abstract base for every Cardinal tool.
# Subclasses must provide a manifest (metadata from manifest.json)
# and an execute() method that routes verb/target/payload to the right handler.
class BaseTool(ABC):
    @property
    @abstractmethod
    def manifest(self) -> ToolManifest: ...

    @abstractmethod
    def execute(self, verb: str, target: str, payload: Optional[str],
                metadata: dict, ctx: ExecutionContext) -> CommandResult: ...

    # Optional pre-execution hook; return an error string to block the call.
    def validate(self, verb, target, payload, metadata) -> Optional[str]:
        return None
