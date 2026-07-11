import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from core.base_tool import CommandResult
from tools.clock_and_calendar.scripts.timezone_resolver import resolve_timezone

SETTINGS_FILE = Path(__file__).parent.parent.parent.parent / "memory" / "settings.md"


def _is_valid_timezone(tz_name: str) -> bool:
    """Check if a timezone string is valid (IANA name or UTC offset)."""
    if not tz_name:
        return False
    tz = tz_name.strip()
    # UTC offset format: +6, -5, UTC+6, GMT+6, +5:30, UTC+05:30
    if re.match(r'^(?:UTC|GMT)?[+-]\d{1,2}(:\d{2})?$', tz, re.IGNORECASE):
        return True
    # Check IANA timezone name
    try:
        ZoneInfo(tz)
        return True
    except (KeyError, TypeError, ZoneInfoNotFoundError):
        return False


def _ensure_file():
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text("# User Preferences\n", encoding="utf-8")


def _read_all():
    _ensure_file()
    lines = SETTINGS_FILE.read_text(encoding="utf-8").splitlines()
    prefs = {}
    for line in lines:
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            prefs[key.strip()] = val.strip()
    return prefs


def _write_all(prefs):
    _ensure_file()
    lines = ["# User Preferences"]
    for k, v in sorted(prefs.items()):
        lines.append(f"{k}: {v}")
    SETTINGS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def handle_get(target, payload, metadata, ctx):
    if not target:
        return CommandResult.fail("Provide a preference name, e.g., get(settings)@name")
    prefs = _read_all()
    val = prefs.get(target)
    if val is None:
        return CommandResult.fail(f"Preference '{target}' not found. Use list(settings)@ to see all preferences.")
    return CommandResult.ok(f"{target}: {val}")


def handle_set(target, payload, metadata, ctx):
    if not target:
        return CommandResult.fail("Provide a preference name, e.g., set(settings)@name|Alice")
    val = (payload or "").strip()
    if not val:
        return CommandResult.fail(f"Provide a value for '{target}', e.g., set(settings)@{target}|value")
    if target == "timezone":
        resolved = resolve_timezone(val)
        if not _is_valid_timezone(resolved):
            return CommandResult.fail(
                f"Could not resolve timezone: '{val}'. "
                "Use a city name (Tokyo, London), country name (Japan, UK), "
                "IANA name (Asia/Tokyo), or UTC offset (UTC+6, +6, -5)."
            )
        current = _read_all().get("timezone", "")
        if resolved.upper() == "UTC" and current and current.upper() != "UTC":
            return CommandResult.fail(
                f"Timezone change rejected: '{resolved}' is ambiguous. "
                "Specify an offset like UTC+6 or a region like Asia/Dhaka instead."
            )
        val = resolved
    elif target == "time_format":
        val = val.strip().lower()
        if val not in ("12h", "24h"):
            return CommandResult.fail("time_format must be '12h' or '24h'")
    elif target == "spoken_lang":
        code = val.strip().lower()
        # validate against available libretranslate codes
        from tools.libretranslate.scripts.handlers import _LANG_NAMES
        if code not in _LANG_NAMES:
            return CommandResult.fail(
                f"Unsupported language code: '{code}'. "
                f"Valid codes: {', '.join(sorted(_LANG_NAMES.keys()))}"
            )
        val = code
    prefs = _read_all()
    prefs[target] = val
    _write_all(prefs)
    return CommandResult.ok(f"Saved: {target}: {val}")


def handle_list(target, payload, metadata, ctx):
    prefs = _read_all()
    if not prefs:
        return CommandResult.ok("No preferences saved yet.")
    lines = [f"{k}: {v}" for k, v in sorted(prefs.items())]
    return CommandResult.ok("\n".join(lines))


def handle_delete(target, payload, metadata, ctx):
    if not target:
        return CommandResult.fail("Provide a preference name to delete, e.g., delete(settings)@name")
    prefs = _read_all()
    if target not in prefs:
        return CommandResult.fail(f"Preference '{target}' not found.")
    del prefs[target]
    _write_all(prefs)
    return CommandResult.ok(f"Deleted: {target}")
