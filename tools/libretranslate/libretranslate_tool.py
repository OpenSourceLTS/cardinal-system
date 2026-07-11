from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import handlers


class LibreTranslateTool(BaseTool):

    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("libretranslate"))

    def execute(self, verb, target, payload, metadata, ctx):
        if verb == "translate":
            return handlers.handle_translate(target, payload, ctx)
        elif verb == "detect":
            return handlers.handle_detect(target, payload, ctx)
        elif verb == "list":
            return handlers.handle_list(target, payload, ctx)
        return CommandResult.fail(f"Verb '{verb}' not supported by {self.manifest.name}")
