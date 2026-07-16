from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import handlers


class LibreTranslateTool(BaseTool):

    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("libretranslate"))

    def execute(self, action, target, payload, metadata, ctx):
        if action == "translate":
            return handlers.handle_translate(target, payload, ctx)
        elif action == "detect":
            return handlers.handle_detect(target, payload, ctx)
        elif action == "list":
            return handlers.handle_list(target, payload, ctx)
        return CommandResult.fail(f"Verb '{action}' not supported by {self.manifest.name}")
