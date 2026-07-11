import json
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path


USER_PREFS_FILE = Path(__file__).parent.parent.parent.parent / "memory" / "settings.md"
SETTINGS_FILE = Path(__file__).parent.parent.parent.parent / "memory" / "clock_and_calendar.json"


def _read_prefs():
    if not USER_PREFS_FILE.exists():
        return {}
    prefs = {}
    for line in USER_PREFS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            prefs[key.strip()] = val.strip()
    return prefs


def _parse_utc_offset(tz_name: str):
    """Parse UTC+6, UTC+06:00, UTC-5, UTC+5:30 into timedelta."""
    m = re.match(r'^UTC([+-])(\d+)(?::(\d+))?$', tz_name.strip(), re.IGNORECASE)
    if not m:
        return None
    sign = 1 if m.group(1) == '+' else -1
    hours = int(m.group(2))
    minutes = int(m.group(3)) if m.group(3) else 0
    return timedelta(hours=sign * hours, minutes=sign * minutes)


def resolve_timezone(tz_name: str):
    """Resolve a timezone string to a tzinfo object.
    Accepts IANA names (Asia/Dhaka) and UTC offset strings (UTC+6, UTC+06:00, UTC-5)."""
    if not tz_name or tz_name.upper() == "UTC":
        return timezone.utc

    offset = _parse_utc_offset(tz_name)
    if offset is not None:
        return timezone(offset)

    try:
        return ZoneInfo(tz_name)
    except (KeyError, TypeError, ZoneInfoNotFoundError):
        return timezone.utc


def get_timezone_from_settings():
    """Read timezone from memory/settings.md first, then fallback to clock_and_calendar.json."""
    prefs = _read_prefs()
    tz = prefs.get("timezone")
    if tz:
        return tz
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return data.get("timezone", "UTC") or "UTC"
        except (json.JSONDecodeError, IOError):
            pass
    return "UTC"


def get_time_format():
    """Read time format preference (12h or 24h) from settings.md. Defaults to 12h."""
    prefs = _read_prefs()
    fmt = prefs.get("time_format", "12h").strip().lower()
    return fmt if fmt in ("12h", "24h") else "12h"


def local_now(tz_name):
    return datetime.now(resolve_timezone(tz_name))


def format_time(dt, include_seconds=False):
    """Format a datetime according to user's 12h/24h preference."""
    if get_time_format() == "24h":
        fmt = "%H:%M" + (":%S" if include_seconds else "")
    else:
        fmt = "%I:%M" + (":%S" if include_seconds else "") + " %p"
    return dt.strftime(fmt)


def parse_time(s):
    s = s.strip().lower().replace("o'clock", "").replace("oclock", "").strip()
    hour = None
    minute = 0
    is_pm = None
    if "am" in s or "pm" in s:
        is_pm = "pm" in s
        s = s.replace("am", "").replace("pm", "").strip()
    if ":" in s:
        parts = s.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            return None
    else:
        try:
            hour = int(s)
        except ValueError:
            return None
    if hour is None:
        return None
    if is_pm is True and hour != 12:
        hour += 12
    elif is_pm is False and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    unqualified = is_pm is None
    return hour, minute, unqualified


def disambiguate_hour(hour, unqualified, now_hour, now_min, now_sec):
    if not unqualified:
        return hour
    now_total = now_hour * 3600 + now_min * 60 + now_sec
    am_total = hour * 3600
    if hour < 12 and am_total < now_total:
        pm_total = (hour + 12) * 3600
        if pm_total > now_total:
            return hour + 12
    return hour


def save_timezone_to_settings(tz_name):
    """Save timezone to clock_and_calendar.json (backward compat, also updates settings.md)."""
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    data["timezone"] = tz_name
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Also sync to settings.md
    prefs = _read_prefs()
    prefs["timezone"] = tz_name
    lines = ["# User Preferences"]
    for k, v in sorted(prefs.items()):
        lines.append(f"{k}: {v}")
    USER_PREFS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True
