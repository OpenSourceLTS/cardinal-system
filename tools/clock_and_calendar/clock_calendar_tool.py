import re
from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import get_handler
from .scripts import forecast_handler
from .scripts import calculate_handler as clock_calculate

from .scripts import convert as calendar_convert
from .scripts import calculate as calendar_calculate
from .scripts import timer_handlers
from .scripts.time_utils import get_timezone_from_settings


class ClockCalendarTool(BaseTool):

    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("clock_calendar"))

    def execute(self, verb, target, payload, metadata, ctx):
        t = target.lower().strip() if target else ""
        p = (payload or "").strip()

        if verb == "get":
            if t in ("alarms", "alarm", "timer", "timers", "stopwatch", "events", "event"):
                return timer_handlers.handle_get(target, payload, metadata, ctx)
            if t in ("moon", "season", "phases", "moon-phase", "moon-phases"):
                return forecast_handler.handle_forecast(t, p, metadata)
            if t == "sun":
                return _handle_sun(p, metadata, ctx)
            if t in ("date", "today"):
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                return CommandResult.ok(f"{now.year:04d}-{now.month:02d}-{now.day:02d}")
            if t in ("day_of_week", "date_offset", "is_leap_year"):
                mapped = t.replace("_", "-")
                return calendar_calculate.handle_calculate(mapped, p, metadata)
            if t == "between":
                return _handle_between(p, metadata)
            if t in ("until", "since"):
                return _handle_until_since(t, p, metadata, ctx)
            if t == "calendar":
                m = re.match(r'^(.+?)\s+to\s+(.+)$', p)
                if m:
                    date_str = m.group(1).strip()
                    cal = m.group(2).strip()
                    return calendar_convert.handle_convert(f"gregorian-to-{cal}", date_str, metadata)
                return calendar_convert.handle_convert("gregorian-to-hijri", p, metadata)
            if t == "timezone":
                if " to " in p:
                    return calendar_convert.handle_convert("timezone", payload, metadata)
                return get_handler.handle_get(target, payload, metadata, ctx)
            if t == "time_format":
                return calendar_convert.handle_convert("time-format", payload, metadata)
            return get_handler.handle_get(target, payload, metadata, ctx)

        elif verb == "set":
            if t in ("alarm", "timer", "stopwatch", "event"):
                if t == "alarm" and "|" in payload:
                    time_part, label_part = payload.split("|", 1)
                    payload = f"{time_part} {label_part}"
                return timer_handlers.handle_set(target, payload, metadata, ctx)
            return CommandResult.fail(f"Target '{t}' cannot be set with clock_calendar. Use settings tool.")

        elif verb == "delete":
            return timer_handlers.handle_delete(target, payload, metadata, ctx)

        return CommandResult.fail(f"Verb '{verb}' not supported by {self.manifest.name}")


def _handle_sun(payload, metadata, ctx):
    p = (payload or "").strip().lower()
    kind = "sunrise"
    rest = p
    if p.startswith("set"):
        kind = "sunset"
        rest = p[3:].strip()
    elif p.startswith("rise"):
        rest = p[4:].strip()
    return get_handler.handle_get(kind, rest, metadata, ctx)


def _handle_between(payload, metadata):
    p = (payload or "").strip()
    if not p:
        return CommandResult.fail("Provide two dates: 'd1 to d2 (days/weeks/months)'")
    p_lower = p.lower()
    if "week" in p_lower:
        return calendar_calculate.handle_calculate("weeks-between", p, metadata)
    if "month" in p_lower:
        return calendar_calculate.handle_calculate("months-between", p, metadata)
    if "year" in p_lower:
        return calendar_calculate.handle_calculate("years-between", p, metadata)
    return calendar_calculate.handle_calculate("days-between", p, metadata)


def _handle_until_since(target, payload, metadata, ctx):
    p = (payload or "").strip()
    if not p:
        return CommandResult.fail(f"Provide a time or date for '{target}'")
    from .scripts import jdn
    d = jdn.parse_date(p)
    if d:
        r = calendar_calculate.handle_calculate("until", p, metadata)
        if r.success:
            return r
    mapped = "minutes-until" if target == "until" else "minutes-since"
    return clock_calculate.handle_calculate(mapped, p, metadata, ctx)
