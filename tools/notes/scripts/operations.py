from pathlib import Path
from datetime import datetime
import re
from core.base_tool import CommandResult

_NOTES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "memory" / "notes"


def _ensure_dir():
    _NOTES_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize(name: str) -> str:
    """Safely extract filename and prevent directory traversal."""
    name = Path(name).stem
    if not name:
        return ""
    return name + ".md"


def _parse_line_spec(spec: str):
    """Parse '3' or '3-5' into start and end integers."""
    spec = spec.strip()
    if not spec:
        return None, None
    range_m = re.match(r"^(\d+)(?:\s*-\s*(\d+))?$", spec)
    if range_m:
        line_start = int(range_m.group(1))
        line_end = int(range_m.group(2)) if range_m.group(2) else line_start
        return line_start, line_end
    return None, None


def handle_list(ctx):
    _ensure_dir()
    files = sorted(_NOTES_DIR.iterdir()) if _NOTES_DIR.exists() else []
    md_files = [f for f in files if f.suffix == ".md"]
    if not md_files:
        return CommandResult.ok("No notes saved.")
    
    lines = []
    for f in md_files:
        stat = f.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        lines.append(f"  {f.name}  ({size} bytes, modified: {mtime})")
    return CommandResult.ok("Notes:\n" + "\n".join(lines))


def handle_read(target, payload, ctx):
    name = _sanitize(target)
    if not name:
        return CommandResult.fail("Provide a note filename to read")
    
    path = _NOTES_DIR / name
    if not path.exists():
        notes = sorted(_NOTES_DIR.glob("*.md")) if _NOTES_DIR.exists() else []
        similar = [f.stem for f in notes if target.lower() in f.stem.lower()]
        hint = f" Did you mean: {', '.join(similar[:5])}?" if similar else ""
        return CommandResult.fail(f"Note '{target}' not found.{hint}")
    
    content = path.read_text(encoding="utf-8")
    all_lines = content.splitlines()
    
    line_start, line_end = _parse_line_spec(payload)
    if line_start is not None:
        if line_start < 1 or line_start > len(all_lines):
            return CommandResult.fail(f"Line {line_start} out of range (file has {len(all_lines)} lines)")
        end = min(line_end, len(all_lines))
        selected = all_lines[line_start - 1:end]
        return CommandResult.ok("\n".join(selected))
    
    return CommandResult.ok(content)


def handle_write(target, payload, ctx):
    name = _sanitize(target)
    if not name:
        return CommandResult.fail("Provide a filename")
    content = (payload or "").strip()
    if not content:
        return CommandResult.fail("Provide content to save")
    
    _ensure_dir()
    path = _NOTES_DIR / name
    path.write_text(content + "\n", encoding="utf-8")
    return CommandResult.ok(f"Saved {name} ({len(content)} chars)")


def handle_append(target, payload, ctx):
    name = _sanitize(target)
    if not name:
        return CommandResult.fail("Provide a filename")
    content = (payload or "").strip()
    if not content:
        return CommandResult.fail("Provide content to append")
    
    _ensure_dir()
    path = _NOTES_DIR / name
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(existing + content + "\n", encoding="utf-8")
    return CommandResult.ok(f"Appended to {name} ({len(content)} chars)")


def handle_change(target, payload, ctx):
    name = _sanitize(target)
    if not name:
        return CommandResult.fail("Provide a filename")
    
    path = _NOTES_DIR / name
    if not path.exists():
        return CommandResult.fail(f"Note '{name}' not found")
    
    # 1. Find and Replace: old_text -> new_text
    if "->" in payload:
        parts = payload.split("->", 1)
        old_text = parts[0].strip()
        new_text = parts[1].strip()
        if not old_text:
            return CommandResult.fail("Provide text to replace before '->'")
        
        content = path.read_text(encoding="utf-8")
        if old_text not in content:
            return CommandResult.fail(f"Text '{old_text}' not found in {name}")
        
        new_content = content.replace(old_text, new_text)
        path.write_text(new_content, encoding="utf-8")
        return CommandResult.ok(f"Replaced '{old_text}' with '{new_text}' in {name}")

    # 2. Line Edit: line | new_content OR +line | content
    parts = payload.split("|", 1)
    spec = parts[0].strip()
    content = parts[1].strip() if len(parts) > 1 else ""
    
    lines = path.read_text(encoding="utf-8").splitlines()
    
    if spec.startswith("+"):
        line_n_str = spec[1:].strip()
        if not line_n_str:
            # Append at end
            lines.append(content)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return CommandResult.ok(f"Appended line to {name}: '{content}'")
        
        if not line_n_str.isdigit():
            return CommandResult.fail("Provide a valid line number after '+'")
        
        line_n = int(line_n_str)
        if line_n < 1 or line_n > len(lines) + 1:
            return CommandResult.fail(f"Line {line_n} out of range (file has {len(lines)} lines, insert 1-{len(lines)+1})")
        
        lines.insert(line_n - 1, content)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return CommandResult.ok(f"Inserted line {line_n} in {name}: '{content}'")
    
    elif spec.isdigit():
        line_n = int(spec)
        if line_n < 1 or line_n > len(lines):
            return CommandResult.fail(f"Line {line_n} out of range (file has {len(lines)} lines)")
        
        old_text = lines[line_n - 1]
        lines[line_n - 1] = content
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return CommandResult.ok(f"Replaced line {line_n} in {name}: '{old_text}' -> '{content}'")
    
    return CommandResult.fail("Invalid change format. Use 'line | content', '+line | content', or 'old -> new'")


def handle_delete_lines(target, payload, ctx):
    name = _sanitize(target)
    if not name:
        return CommandResult.fail("Provide a filename")
    
    path = _NOTES_DIR / name
    if not path.exists():
        return CommandResult.fail(f"Note '{name}' not found")
    
    line_start, line_end = _parse_line_spec(payload)
    if line_start is None:
        return CommandResult.fail("Provide a valid line number or range (e.g., 3 or 3-5)")
    
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_start < 1 or line_start > len(lines):
        return CommandResult.fail(f"Line {line_start} out of range (file has {len(lines)} lines)")
    
    end = min(line_end, len(lines))
    removed = lines[line_start - 1:end]
    del lines[line_start - 1:end]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return CommandResult.ok(f"Deleted {len(removed)} line(s) {line_start}-{end} from {name}")


def handle_delete_file(target, ctx):
    name = _sanitize(target)
    if not name:
        return CommandResult.fail("Provide a note filename to delete")
    
    path = _NOTES_DIR / name
    if not path.exists():
        return CommandResult.fail(f"Note '{target}' not found")
    
    path.unlink()
    return CommandResult.ok(f"Deleted {name}")


def handle_rename(target, payload, ctx):
    old_name = _sanitize(target)
    new_name = _sanitize(payload)
    if not old_name or not new_name:
        return CommandResult.fail("Provide current filename and new filename")
    
    old_path = _NOTES_DIR / old_name
    if not old_path.exists():
        return CommandResult.fail(f"Note '{old_name}' not found")
    
    new_path = _NOTES_DIR / new_name
    if new_path.exists():
        return CommandResult.fail(f"Note '{new_name}' already exists")
    old_path.rename(new_path)
    return CommandResult.ok(f"Renamed {old_name} to {new_name}")


def handle_search(target, payload, ctx):
    """Search notes. target=filename (optional). payload=keyword."""
    keyword = (payload or "").strip().lower()
    if not keyword and target:
        keyword = target.strip().lower()
        target = ""
    if not keyword:
        return CommandResult.fail("Provide a search term")
    
    _ensure_dir()
    files = sorted(_NOTES_DIR.iterdir()) if _NOTES_DIR.exists() else []
    md_files = [f for f in files if f.suffix == ".md"]

    if target:
        name = _sanitize(target)
        path = _NOTES_DIR / name
        if not path.exists():
            return CommandResult.fail(f"Note '{target}' not found")
        md_files = [f for f in md_files if f.name == name]

    name_matches = [f for f in md_files if keyword in f.stem.lower()]
    all_matches = []
    for f in md_files:
        content = f.read_text(encoding="utf-8")
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if keyword in line.lower():
                all_matches.append((f.stem, i + 1, line))

    parts = []
    if name_matches:
        names = ", ".join(f"{f.stem}.md" for f in name_matches)
        parts.append(f"Matching notes: {names}")

    if all_matches:
        match_lines = [f"{name}:{lineno}: {line}" for name, lineno, line in all_matches]
        parts.append(f"Found {len(all_matches)} content match(es):\n" + "\n".join(match_lines))

    if not parts:
        scope = f" in {target}" if target else ""
        return CommandResult.ok(f"No matches for '{keyword}'{scope}")

    return CommandResult.ok("\n".join(parts))