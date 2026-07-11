from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import operations


class NotesTool(BaseTool):

    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("notes"))

    def execute(self, verb, target, payload, metadata, ctx):
        t = (target or "").strip()
        p = (payload or "").strip()

        if verb == "list":
            return operations.handle_list(ctx)

        if verb == "read":
            if not t or t == "all":
                return operations.handle_list(ctx)
            return operations.handle_read(t, p, ctx)

        if verb == "save":
            name = t
            content = p
            if not content and name:
                # Auto-name from first 3 words if only payload is given
                content = name
                words = content.split()
                name = "-".join(w.lower().strip(",.!?;:") for w in words[:3])
            if not name:
                return CommandResult.fail("Provide a filename or content to save")
            return operations.handle_write(name, content, ctx)

        if verb == "append":
            if not t:
                return CommandResult.fail("Provide a filename to append to")
            if not p:
                return CommandResult.fail("Provide content to append")
            return operations.handle_append(t, p, ctx)

        if verb == "delete":
            if not t:
                return CommandResult.fail("Provide a filename")
            # If payload is a line number or range, delete lines. Otherwise, delete file.
            if p and (p.isdigit() or (p.count("-") == 1 and all(x.strip().isdigit() for x in p.split("-")))):
                return operations.handle_delete_lines(t, p, ctx)
            return operations.handle_delete_file(t, ctx)

        if verb == "change":
            if not t:
                return CommandResult.fail("Provide a filename")
            if not p:
                return CommandResult.fail("Provide 'line | new_content', '+line | content', or 'old -> new'")
            return operations.handle_change(t, p, ctx)

        if verb == "rename":
            if not t or not p:
                return CommandResult.fail("Provide current filename as target and new filename as payload")
            return operations.handle_rename(t, p, ctx)

        if verb == "search":
            keyword = p or t
            if not keyword:
                return CommandResult.fail("Provide a search term")
            # If keyword is in target, search all files. If target is provided, search only that file.
            search_target = t if p else ""
            return operations.handle_search(search_target, keyword, ctx)

        return CommandResult.fail(f"Verb '{verb}' not supported by {self.manifest.name}")