from datetime import datetime, timezone
from core.base_tool import CommandResult
from .jdn import parse_date, gregorian_to_jdn
from .moon import moon_phase, next_moon_phases


def handle_forecast(target, payload, metadata):
    t = target.lower()
    p = payload.strip() if payload else ""

    d = parse_date(p) if p else None
    if not d:
        now = datetime.now(timezone.utc)
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
        if (month == 3 and day >= 20) or month in (4, 5) or (month == 6 and day < 21):
            season = "Spring"
        elif (month == 6 and day >= 21) or month in (7, 8) or (month == 9 and day < 23):
            season = "Summer"
        elif (month == 9 and day >= 23) or month in (10, 11) or (month == 12 and day < 21):
            season = "Autumn"
        else:
            season = "Winter"
        return CommandResult.ok(f"Season: {season}")

    return CommandResult.fail(f"Unknown forecast: '{t}'. Try: moon, moon-phases, season")
