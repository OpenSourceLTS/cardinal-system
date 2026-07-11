import re
from datetime import datetime, timezone, timedelta
from core.base_tool import CommandResult
from . import jdn
from . import hijri as hij
from . import ethiopian as eth
from . import persian as per
from .time_utils import get_timezone_from_settings, format_time
from .timezone_resolver import resolve_timezone as fuzzy_resolve, _is_valid_timezone


def _day_of_week(jdn_val):
    return jdn.DAY_NAMES[(jdn_val - 1) % 7]


def _format_gregorian(year, month, day):
    era = "BC" if year <= 0 else "CE"
    y = abs(year) + (1 if year <= 0 else 0)
    dow = _day_of_week(jdn.gregorian_to_jdn(year, month, day))
    return f"{dow}, {jdn.GREGORIAN_MONTHS[month - 1]} {day}, {y} {era}"


def handle_convert(target, payload, metadata):
    if not target:
        return CommandResult.fail("Provide a conversion target")

    t = target.lower().strip()
    p = (payload or "").strip()

    # Timezone conversion: "14:00 Tokyo to Dhaka" or "Tokyo to Dhaka" (current)
    if t == "timezone":
        p = (payload or "").strip()
        if not p:
            return CommandResult.fail("Use: 'src to dst' (current time) or 'HH:MM src to dst' e.g. 'Tokyo to Dhaka' or '14:00 Tokyo to Dhaka'")

        # Try with explicit time first
        m = re.match(r'^(\d{1,2}:\d{2})\s+(.+?)\s+to\s+(.+)$', p, re.IGNORECASE)
        explicit_time = False
        if m:
            time_str = m.group(1)
            src_input = m.group(2).strip()
            dst_input = m.group(3).strip()
            explicit_time = True
        else:
            # Try "src to dst" (current time)
            m = re.match(r'^(.+?)\s+to\s+(.+)$', p, re.IGNORECASE)
            if not m:
                return CommandResult.fail("Use: 'src to dst' or 'HH:MM src to dst' e.g. 'Tokyo to Dhaka' or '14:00 Tokyo to Dhaka'")
            src_input = m.group(1).strip()
            dst_input = m.group(2).strip()

        try:
            # Resolve both inputs via fuzzy timezone resolver
            src_tz_str = fuzzy_resolve(src_input)
            dst_tz_str = fuzzy_resolve(dst_input)

            if src_tz_str is None:
                return CommandResult.fail(f"Could not resolve source timezone: '{src_input}'")
            if dst_tz_str is None:
                return CommandResult.fail(f"Could not resolve destination timezone: '{dst_input}'")

            from .time_utils import resolve_timezone as get_tz
            src_tz_obj = get_tz(src_tz_str)
            dst_tz_obj = get_tz(dst_tz_str)

            if explicit_time:
                hour, minute = map(int, time_str.split(":"))
                src_dt = datetime.now(src_tz_obj).replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                src_dt = datetime.now(src_tz_obj)

            dst_dt = src_dt.astimezone(dst_tz_obj)

            src_fmt = format_time(src_dt)
            dst_fmt = format_time(dst_dt)
            src_date = src_dt.strftime("%b %d")
            dst_date = dst_dt.strftime("%b %d")

            if src_date == dst_date:
                return CommandResult.ok(f"{src_fmt} {src_tz_str} = {dst_fmt} {dst_tz_str}")
            else:
                return CommandResult.ok(f"{src_fmt} {src_tz_str} ({src_date}) = {dst_fmt} {dst_tz_str} ({dst_date})")

        except Exception as e:
            return CommandResult.fail(f"Timezone conversion error: {e}")

    # Time format conversion: "14:00 to 12h" or "2:00 PM to 24h"
    if t == "time-format":
        m = re.match(r'^(.+?)\s+to\s+(12h|24h)$', p)
        if not m:
            return CommandResult.fail("Use: 'HH:MM to 12h' or 'HH:MM to 24h' e.g. '14:00 to 12h'")
        time_str, fmt = m.groups()
        time_str = time_str.strip()
        if fmt == "12h":
            # 24h to 12h
            parts = time_str.split(":")
            if len(parts) == 2:
                try:
                    h = int(parts[0])
                    m = int(parts[1])
                    ampm = "AM" if h < 12 else "PM"
                    dh = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
                    if h == 0:
                        dh = 12
                    return CommandResult.ok(f"{dh}:{m:02d} {ampm}")
                except ValueError:
                    pass
            return CommandResult.fail(f"Cannot parse '{time_str}' as 24-hour time")
        else:
            # 12h to 24h
            m2 = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', time_str, re.IGNORECASE)
            if m2:
                h = int(m2.group(1))
                m = int(m2.group(2))
                ampm = m2.group(3).upper()
                if ampm == "PM" and h != 12:
                    h += 12
                if ampm == "AM" and h == 12:
                    h = 0
                return CommandResult.ok(f"{h:02d}:{m:02d}")
            return CommandResult.fail(f"Cannot parse '{time_str}' as 12-hour time")

    # Calendar conversion: {from}-to-{to} format
    if "-" not in target:
        return CommandResult.fail("Use format: {from}-to-{to} (e.g. 'gregorian-to-hijri')")
    parts = target.lower().split("-to-")
    if len(parts) != 2:
        return CommandResult.fail("Use format: {from}-to-{to}")
    src, dst = parts[0], parts[1]
    date_str = payload or target
    src_parsed = jdn.parse_date(date_str)
    if not src_parsed:
        return CommandResult.fail(f"Cannot parse date: '{date_str}'")

    sy, sm, sd = src_parsed
    src_jdn = None
    if src in ("gregorian", "greg", "ce", "bc"):
        src_jdn = jdn.gregorian_to_jdn(sy, sm, sd)
    elif src in ("julian",):
        src_jdn = jdn.julian_to_jdn(sy, sm, sd)
    elif src in ("hijri", "islamic"):
        src_jdn = hij.hijri_to_jdn(sy, sm, sd)
    elif src in ("ethiopian", "ethio"):
        src_jdn = eth.ethiopian_to_jdn(sy, sm, sd)
    elif src in ("persian", "solar"):
        src_jdn = per.persian_to_jdn(sy, sm, sd)
    else:
        return CommandResult.fail(f"Unknown source calendar: '{src}'")

    if src_jdn is None:
        return CommandResult.fail(f"Cannot compute JDN from '{src}' date {date_str}")

    if dst in ("all",):
        lines = []
        gy, gm, gd = jdn.jdn_to_gregorian(src_jdn)
        lines.append(f"Gregorian: {_format_gregorian(gy, gm, gd)}")
        h = hij.jdn_to_hijri(src_jdn)
        lines.append(f"Hijri: {hij.format_hijri(*h) if h else 'N/A (before 622 CE)'}")
        e = eth.jdn_to_ethiopian(src_jdn)
        lines.append(f"Ethiopian: {eth.format_ethiopian(*e)}")
        p = per.jdn_to_persian(src_jdn)
        lines.append(f"Persian: {per.format_persian(*p) if p else 'N/A (before 622 CE)'}")
        jy, jm, jd = jdn.jdn_to_julian(src_jdn)
        era2 = "BC" if jy <= 0 else "CE"
        y2 = abs(jy) + (1 if jy <= 0 else 0)
        lines.append(f"Julian: {jdn.GREGORIAN_MONTHS[jm - 1]} {jd}, {y2} {era2}")
        lines.append(f"Day: {_day_of_week(src_jdn)}")
        return CommandResult.ok("\n".join(lines))

    if dst in ("day", "dow", "weekday", "day-of-week"):
        return CommandResult.ok(_day_of_week(src_jdn))
    elif dst in ("day-of-year",):
        gy, gm, gd = jdn.jdn_to_gregorian(src_jdn)
        jan1 = jdn.gregorian_to_jdn(gy, 1, 1)
        return CommandResult.ok(f"Day {src_jdn - jan1 + 1} of {gy}")
    elif dst in ("gregorian", "greg", "ce", "bc", "date"):
        gy, gm, gd = jdn.jdn_to_gregorian(src_jdn)
        return CommandResult.ok(_format_gregorian(gy, gm, gd))
    elif dst in ("julian",):
        jy, jm, jd = jdn.jdn_to_julian(src_jdn)
        era = "BC" if jy <= 0 else "CE"
        y = abs(jy) + (1 if jy <= 0 else 0)
        return CommandResult.ok(f"{jdn.GREGORIAN_MONTHS[jm - 1]} {jd}, {y} {era}")
    elif dst in ("hijri", "islamic"):
        h = hij.jdn_to_hijri(src_jdn)
        return CommandResult.ok(hij.format_hijri(*h) if h else "N/A (before 622 CE)")
    elif dst in ("ethiopian", "ethio"):
        return CommandResult.ok(eth.format_ethiopian(*eth.jdn_to_ethiopian(src_jdn)))
    elif dst in ("persian", "solar"):
        p_result = per.jdn_to_persian(src_jdn)
        return CommandResult.ok(per.format_persian(*p_result) if p_result else "N/A (before 622 CE)")
    else:
        return CommandResult.fail(f"Unknown destination calendar: '{dst}'")
