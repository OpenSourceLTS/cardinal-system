import re
from datetime import datetime, timezone
from core.base_tool import CommandResult
from .jdn import gregorian_to_jdn, jdn_to_gregorian, parse_date, is_gregorian_leap
from .time_utils import local_now, parse_time, disambiguate_hour, get_timezone_from_settings, format_time


def _build_duration_string(hours, mins, target_hour, target_min, tz_name, now):
    from datetime import datetime
    now_str = format_time(now, include_seconds=True)
    result_parts = []
    if hours > 0:
        result_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if mins > 0:
        result_parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
    target_dt = datetime(1, 1, 1, target_hour, target_min)
    time_desc = format_time(target_dt)
    in_tz = f" in {tz_name}" if tz_name != "UTC" else ""
    return now_str, result_parts, time_desc, in_tz


def handle_calculate(target, payload, metadata, ctx):
    t = target.lower().strip() if target else ""
    p = (payload or "").strip()

    if t in ("minutes-until", "time-until", "until"):
        if not p:
            return CommandResult.fail("Provide target time (e.g. '10:00', '10 PM', '10 o'clock')")
        parsed = parse_time(p)
        if not parsed:
            return CommandResult.fail(f"Cannot parse time '{p}'. Use format like '10:00', '10 PM', or '10 o'clock'")
        target_hour, target_min, unqualified = parsed
        tz_name = ctx.timezone if ctx and ctx.timezone != "UTC" else get_timezone_from_settings()
        now = local_now(tz_name)
        target_hour = disambiguate_hour(target_hour, unqualified, now.hour, now.minute, now.second)
        target_seconds = target_hour * 3600 + target_min * 60
        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
        diff_seconds = target_seconds - now_seconds
        if diff_seconds <= 0:
            diff_seconds += 86400
        minutes = diff_seconds // 60
        hours_part = minutes // 60
        mins_part = minutes % 60
        now_str, result_parts, time_desc, in_tz = _build_duration_string(
            hours_part, mins_part, target_hour, target_min, tz_name, now
        )
        return CommandResult.ok(
            f"It is {now_str}{in_tz}. "
            f"{', '.join(result_parts) if result_parts else 'Less than a minute'} until {time_desc}."
        )

    elif t in ("minutes-since", "time-since", "since"):
        if not p:
            return CommandResult.fail("Provide target time (e.g. '10:00', '10 PM')")
        parsed = parse_time(p)
        if not parsed:
            return CommandResult.fail(f"Cannot parse time '{p}'.")
        target_hour, target_min, unqualified = parsed
        tz_name = ctx.timezone if ctx and ctx.timezone != "UTC" else get_timezone_from_settings()
        now = local_now(tz_name)
        target_hour = disambiguate_hour(target_hour, unqualified, now.hour, now.minute, now.second)
        target_seconds = target_hour * 3600 + target_min * 60
        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
        diff_seconds = now_seconds - target_seconds
        if diff_seconds < 0:
            diff_seconds += 86400
        minutes = diff_seconds // 60
        hours_part = minutes // 60
        mins_part = minutes % 60
        now_str, result_parts, time_desc, in_tz = _build_duration_string(
            hours_part, mins_part, target_hour, target_min, tz_name, now
        )
        return CommandResult.ok(
            f"{', '.join(result_parts) if result_parts else 'Less than a minute'} since {time_desc}{in_tz}."
        )

    return CommandResult.fail(f"Unknown calculate target: '{t}'. Try: minutes-until, minutes-since")
