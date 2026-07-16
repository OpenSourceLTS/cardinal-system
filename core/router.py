from typing import List, Tuple
from .base_tool import BaseTool, ExecutionContext, CommandResult
from .parser import CommandNode
from .manifest import get_valid_targets, load_manifest as load_manifest_json


# Routes tool calls to the correct handler with validation.
# Each step in execute_dag() validates the tool, action, target, payload,
# then dispatches execution. On failure it returns the manifest format
# so the AI can self-correct.
class Router:
    def __init__(self, confirm_callback=None):
        self._tools = {}
        self._confirm = confirm_callback or (lambda *args: True)

    def register(self, tool: BaseTool):
        self._tools[tool.manifest.name] = tool

    # Sends text to libretranslate with auto-detect source.
    # libretranslate passes English through, translates non-English to English.
    def route_user_input(self, text: str) -> Tuple[str, str]:
        if not text or not text.strip():
            return text, text
        from tools.libretranslate.libretranslate_tool import LibreTranslateTool
        tool = LibreTranslateTool()
        ctx = ExecutionContext()
        result = tool.execute("translate", "en", f"{text} | auto", {}, ctx)
        if result.success and result.value:
            return result.value, text
        return text, text

    # Builds a human-readable format hint from the tool's manifest.json
    # so the AI sees valid action/target/payload combinations on error.
    def _manifest_summary(self, tool_name):
        data = load_manifest_json(tool_name)
        if not data:
            return ""
        m = data.get("manifest", {})
        examples = m.get("examples") or ([m["example"]] if m.get("example") else [])
        vp = m.get("a@p", {})
        lines = ["Correct format:"]
        for ex in examples:
            v = ex.get("action", "")
            t = ex.get("target", "")
            p = ex.get("payload", "")
            d = ex.get("desc", "")
            lines.append(f"  {v}({t})@{p or '...'}  — {d}")
        if vp:
            lines.append("\nVerb → target → payload:")
            for action, targets in vp.items():
                for entry in targets:
                    t = entry[0] if entry else ""
                    p = entry[1] if len(entry) > 1 else ""
                    lines.append(f"  {action} → target='{t}' payload='{p}'")
        return "\n".join(lines)

    # Executes a list of CommandNodes sequentially.
    # Validation pipeline per node:
    #   1. Tool exists -> 2. Verb valid -> 3. Target valid -> 4. Payload valid
    #   5. Confirmation -> 6. Execute
    def execute_dag(self, nodes: List[CommandNode], ctx: ExecutionContext) -> List[CommandResult]:
        results = [None] * len(nodes)

        for i, node in enumerate(nodes):
            node_tool = node.tool
            node_action = node.action
            node_target = node.target

            # 1. Check the tool is registered
            tool = self._tools.get(node_tool)
            if not tool:
                available = ", ".join(self._tools.keys())
                results[i] = CommandResult.fail(
                    f"Unknown tool: '{node_tool}'. Available: {available}",
                    tool=node_tool, action=node_action, target=node_target)
                ctx.results.append(results[i]); continue

            # 2. Check the action is in the tool's declared action list
            if node_action not in tool.manifest.actions:
                results[i] = CommandResult.fail(
                    f"Verb '{node_action}' not allowed for '{node_tool}'.\n{self._manifest_summary(node_tool)}",
                    tool=node_tool, action=node_action, target=node_target)
                ctx.results.append(results[i]); continue

            # 3. Check the target is valid for this action (if manifest defines literal targets)
            valid_targets = get_valid_targets(node_tool, node_action)
            if valid_targets and node_target not in valid_targets:
                results[i] = CommandResult.fail(
                    f"Target '{node_target}' not valid for '{node_tool}' action '{node_action}'.\n{self._manifest_summary(node_tool)}",
                    tool=node_tool, action=node_action, target=node_target)
                ctx.results.append(results[i]); continue

            # Resolve $ref placeholders to actual values from prior steps
            target = ctx.resolve_ref(node.target, results)
            payload = ctx.resolve_ref(node.payload, results) if node.payload else None

            # 4. Run tool-level validation hook
            err = tool.validate(node_action, target, payload, node.meta)
            if err:
                results[i] = CommandResult.fail(
                    f"{err}\n{self._manifest_summary(node_tool)}",
                    tool=node_tool, action=node_action, target=node_target)
                ctx.results.append(results[i]); continue

            # 5. Require user confirmation for flagged commands
            if node.requires_confirm and not self._confirm(tool.manifest.name, node_action, target):
                results[i] = CommandResult.fail("User declined confirmation.", tool=node_tool, action=node_action, target=node_target)
                ctx.results.append(results[i]); continue

            # 6. Execute the tool call
            try:
                res = tool.execute(node_action, target, payload, node.meta, ctx)
                res.tool = node_tool
                res.action = node_action
                res.target = node_target
                results[i] = res
                ctx.results.append(res)
            except Exception as e:
                results[i] = CommandResult.fail(f"{type(e).__name__}: {str(e)}", tool=node_tool, action=node_action, target=node_target)
                ctx.results.append(results[i])

        return results
