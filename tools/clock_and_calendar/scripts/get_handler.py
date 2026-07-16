import math
from datetime import datetime, timezone, timedelta
from core.base_tool import CommandResult
from .jdn import gregorian_to_jdn, day_of_week, GREGORIAN_MONTHS, parse_date
from .moon import moon_phase
from .time_utils import local_now, get_timezone_from_settings, format_time
from .timezone_resolver import resolve_timezone as fuzzy_resolve


def _sunrise_sunset(lat, lon, year, month, day, tz_offset_hours):
    """Approximate sunrise/sunset using NOAA solar calculations."""
    n = gregorian_to_jdn(year, month, day) - 2451545 + 0.0008
    j_century = n / 36525
    mean_anom = math.radians(357.5291 + 0.98560028 * n)
    ctr = (1.9148 * math.sin(mean_anom) + 0.02 * math.sin(2 * mean_anom) + 0.0003 * math.sin(3 * mean_anom))
    eclip_long = math.radians(280.46646 + 0.98564736 * n + ctr)
    sin_sun_dec = 0.39782 * math.sin(eclip_long)
    cos_sun_dec = math.sqrt(1 - sin_sun_dec * sin_sun_dec)
    sun_dec = math.atan2(sin_sun_dec, cos_sun_dec)
    cos_hr_angle = (math.cos(math.radians(90.833)) - sin_sun_dec * math.sin(math.radians(lat))) / (cos_sun_dec * math.cos(math.radians(lat)))
    cos_hr_angle = max(-1, min(1, cos_hr_angle))
    hr_angle = math.degrees(math.acos(cos_hr_angle))
    eq_of_time = 4 * (0.0053 * math.sin(mean_anom) - 0.0069 * math.sin(2 * eclip_long))
    sunrise = 720 - 4 * (hr_angle + lon) - eq_of_time
    sunset = 720 + 4 * (hr_angle + lon) - eq_of_time
    sunrise_h = int(sunrise // 60)
    sunrise_m = int(sunrise % 60)
    sunset_h = int(sunset // 60)
    sunset_m = int(sunset % 60)
    sunrise_h = (sunrise_h + tz_offset_hours) % 24
    sunset_h = (sunset_h + tz_offset_hours) % 24
    return sunrise_h, sunrise_m, sunset_h, sunset_m


def _next_weekday(day_name: str, tz_name: str) -> str:
    now = local_now(tz_name)
    target_names = [d.lower() for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]]
    dn = day_name.lower().strip()
    if dn not in target_names:
        # Try short forms
        short_map = {"mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday",
                     "fri": "friday", "sat": "saturday", "sun": "sunday"}
        dn = short_map.get(dn, dn)
    if dn not in target_names:
        return None
    target_idx = target_names.index(dn)
    current_idx = now.weekday()
    days_ahead = target_idx - current_idx
    if days_ahead <= 0:
        days_ahead += 7
    result = now + timedelta(days=days_ahead)
    return f"{day_name}, {GREGORIAN_MONTHS[result.month - 1]} {result.day}, {result.year}"


def handle_get(target, payload, metadata, ctx):
    tz_name = ctx.timezone if ctx and ctx.timezone != "UTC" else get_timezone_from_settings()
    tgt = target.lower().strip() if target else "current"
    p = (payload or "").strip()

    # Timezone info
    if tgt == "timezone":
        return CommandResult.ok(f"Current timezone: {tz_name}")

    # Epoch / Unix timestamp
    if tgt == "epoch":
        utc_now = datetime.now(timezone.utc)
        return CommandResult.ok(str(int(utc_now.timestamp())))

    # Time in a specific timezone
    if tgt == "time_in_zone":
        if not p:
            return CommandResult.fail("Provide a timezone like 'Asia/Tokyo'")
        try:
            tz_name_resolved = fuzzy_resolve(p) or p
            tz_local = local_now(tz_name_resolved)
            return CommandResult.ok(f"{format_time(tz_local, include_seconds=True)} in {p}")
        except Exception:
            return CommandResult.fail(f"Unknown timezone: '{p}'")

    # Next weekday
    if tgt == "next_weekday":
        result = _next_weekday(p, tz_name)
        if result is None:
            return CommandResult.fail(f"Unknown weekday: '{p}'. Try Monday, Tuesday, etc.")
        return CommandResult.ok(result)

    # Quarter of year for a date
    if tgt == "quarter":
        d = parse_date(p) if p else None
        if not d:
            now = local_now(tz_name)
            d = (now.year, now.month, now.day)
        y, m, _ = d
        q = (m - 1) // 3 + 1
        return CommandResult.ok(f"Q{q} {y}")

    # Week number of year for a date
    if tgt == "week_number":
        d = parse_date(p) if p else None
        if not d:
            now = local_now(tz_name)
            d = (now.year, now.month, now.day)
        jdn = gregorian_to_jdn(*d)
        y, m, dn = d
        week = (jdn - gregorian_to_jdn(y, 1, 1)) // 7 + 1
        return CommandResult.ok(f"Week {week} of {y}")

    # Sunrise / sunset
    if tgt in ("sunrise", "sunset"):
        parts = p.rsplit(None, 1) if p else []
        date_str = parts[0] if parts else ""
        tz_for_sun = parts[1] if len(parts) > 1 else tz_name
        d = parse_date(date_str) if date_str else None
        if not d:
            now = local_now(tz_for_sun)
            d = (now.year, now.month, now.day)
        try:
            tz_dt = local_now(tz_for_sun)
            tz_offset = tz_dt.utcoffset().total_seconds() / 3600 if tz_dt.tzinfo and tz_dt.utcoffset() else 0
        except Exception:
            tz_offset = 0
        lat, lon = 23.685, 90.356  # Default to Dhaka coordinates
        sr_h, sr_m, ss_h, ss_m = _sunrise_sunset(lat, lon, d[0], d[1], d[2], int(tz_offset))
        sr_dt = datetime(1, 1, 1, sr_h, sr_m)
        ss_dt = datetime(1, 1, 1, ss_h, ss_m)
        sr_str = format_time(sr_dt)
        ss_str = format_time(ss_dt)
        if tgt == "sunrise":
            return CommandResult.ok(f"Sunrise: {sr_str} in {tz_for_sun}")
        else:
            return CommandResult.ok(f"Sunset: {ss_str} in {tz_for_sun}")

    # Standard current time/date payloads (payload optionally overrides timezone)
    if p:
        tz_lookup = fuzzy_resolve(p) or p
    else:
        tz_lookup = tz_name
    now = local_now(tz_lookup)
    if tgt in ("current_time", "time"):
        return CommandResult.ok(f"{format_time(now, include_seconds=True)} in {p}" if p else format_time(now, include_seconds=True))
    if tgt in ("current_date", "date", "today"):
        return CommandResult.ok(f"{now.year:04d}-{now.month:02d}-{now.day:02d}")
    if tgt == "yesterday":
        from datetime import timedelta
        y = now - timedelta(days=1)
        return CommandResult.ok(f"{y.year:04d}-{y.month:02d}-{y.day:02d}")
    if tgt == "tomorrow":
        from datetime import timedelta
        t = now + timedelta(days=1)
        return CommandResult.ok(f"{t.year:04d}-{t.month:02d}-{t.day:02d}")
    if tgt in ("current_datetime", "datetime"):
        result = f"{now.strftime('%Y-%m-%d')} {format_time(now, include_seconds=True)}"
        return CommandResult.ok(f"{result} in {p}" if p else result)

    # Fuzzy fallback: treat unknown target as a place/timezone name
    resolved = fuzzy_resolve(tgt)
    if resolved and resolved != tgt:
        try:
            tz_local = local_now(resolved)
            return CommandResult.ok(f"{format_time(tz_local, include_seconds=True)} in {target}")
        except Exception:
            pass
    return CommandResult.fail(f"Unknown target: '{target}'")
