from datetime import datetime, timezone
from core.base_tool import CommandResult
from .jdn import parse_date, gregorian_to_jdn
from .moon import moon_phase, next_moon_phases
from ..seasons.seasons_db import get_season, get_system
from .time_utils import get_timezone_from_settings, local_now


def handle_forecast(target, payload, metadata, tz_name=None):
    t = target.lower()
    p = payload.strip() if payload else ""

    if not tz_name or tz_name == "UTC":
        tz_name = get_timezone_from_settings()

    d = parse_date(p) if p else None
    if not d:
        now = local_now(tz_name)
        d = (now.year, now.month, now.day)
    jdn = gregorian_to_jdn(*d)

    if t in ("moon", "moon-phase", "phase"):
        name, illum = moon_phase(jdn)
        return CommandResult.ok(f"Moon phase: {name} ({illum}% illuminated)")

    elif t in ("moon-phases", "phases"):
        phases = next_moon_phases(jdn, 4)
        lines = ["Next moon phases:"]
        for ds, pn in phases:
            lines.append(f"  {ds}: {pn}")
        return CommandResult.ok("\n".join(lines))

    elif t in ("season",):
        _, month, day = d
        season = get_season(tz_name, month, day)
        system = get_system(tz_name)
        system_label = system["label"] if system else ""
        if system_label:
            return CommandResult.ok(f"Season: {season} ({system_label})")
        return CommandResult.ok(f"Season: {season}")

    return CommandResult.fail(f"Unknown forecast: '{t}'. Try: moon, moon-phases, season")
