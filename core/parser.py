from dataclasses import dataclass
from typing import List, Optional, Dict


# A single parsed tool invocation.
# The MCP server creates these directly, then passes the list to the Router.
@dataclass
class CommandNode:
    verb: str                # Action to perform (e.g., "get", "translate", "save")
    tool: str                # Target tool name (e.g., "clock_calendar", "notes")
    target: str              # Primary resource (e.g., "current_time", "groceries")
    payload: Optional[str]   # Data or parameters (e.g., "Asia/Dhaka", "milk -> oat milk")
    meta: Dict[str, str]     # Extra metadata key-value pairs
    requires_confirm: bool = False  # If True, user must approve before execution
    deps: List[int] = None   # Indices of prerequisite nodes (for DAG execution)
