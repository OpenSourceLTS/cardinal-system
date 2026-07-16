from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import handlers


class LlmTool(BaseTool):

    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("llm"))

    def execute(self, action, target, payload, metadata, ctx):
        if action == "forward":
            return handlers.handle_forward(target, payload, metadata, ctx)
        return CommandResult.fail(f"Verb '{action}' not supported by {self.manifest.name}")
