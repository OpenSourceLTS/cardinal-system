from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import handlers


class SettingsTool(BaseTool):

    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("settings"))

    def execute(self, action, target, payload, metadata, ctx):
        if action == "get":
            if target == "list":
                return handlers.handle_list(target, payload, metadata, ctx)
            if target == "setting":
                return handlers.handle_get(payload, payload, metadata, ctx)
            return handlers.handle_get(target, payload, metadata, ctx)
        elif action == "set":
            if target == "setting":
                parts = (payload or "").split("|", 1)
                name = parts[0].strip()
                val = parts[1].strip() if len(parts) > 1 else ""
                return handlers.handle_set(name, val, metadata, ctx)
            return handlers.handle_set(target, payload, metadata, ctx)
        elif action == "delete":
            if target == "setting":
                return handlers.handle_delete(payload, payload, metadata, ctx)
            return handlers.handle_delete(target, payload, metadata, ctx)
        return CommandResult.fail(f"Verb '{action}' not supported")
