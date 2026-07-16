import re
from datetime import datetime, timezone
from core.base_tool import CommandResult

from . import jdn
from .time_utils import local_now, get_timezone_from_settings


def _format_gregorian(year, month, day):
    era = "BC" if year <= 0 else "CE"
    y = abs(year) + (1 if year <= 0 else 0)
    dow = jdn.day_of_week(jdn.gregorian_to_jdn(year, month, day))
    return f"{dow}, {jdn.GREGORIAN_MONTHS[month - 1]} {day}, {y} {era}"


def handle_calculate(target, payload, metadata):
    t = target.lower()
    p = payload.strip() if payload else ""

    if t == "days-between":
        return _days_between(p)
    elif t == "age":
        return _age(p)
    elif t in ("day-of-week", "day"):
        return _day_of_week(p)
    elif t == "until":
        return _until(p)
    elif t == "week-number":
        return _week_number(p)
    elif t == "day-of-year":
        return _day_of_year(p)
    elif t in ("date-offset", "offset", "add-days"):
        return _date_offset(p)
    elif t in ("leap", "leap-year", "is-leap-year"):
        return _leap_year(p)
    elif t in ("years-offset", "years-ago", "years-before", "add-years"):
        return _years_offset(p)
    elif t == "weeks-between":
        return _weeks_between(p)
    elif t == "months-between":
        return _months_between(p)
    elif t == "years-between":
        return _years_between(p)

    return CommandResult.fail(
        f"Unknown calculation: '{t}'. Try: days-between, age, day-of-week, until, "
        "week-number, day-of-year, leap-year, date-offset, years-offset"
    )


def _days_between(payload):
    dates = re.split(r'\s+(?:to|and|>|->)\s+', payload)
    if len(dates) != 2:
        return CommandResult.fail("Provide two dates separated by ' to ' (e.g. '2024-01-01 to 2024-12-31')")
    d1 = jdn.parse_date(dates[0])
    d2 = jdn.parse_date(dates[1])
    if not d1 or not d2:
        return CommandResult.fail("Invalid date format. Use YYYY-MM-DD.")
    diff = abs(jdn.gregorian_to_jdn(*d2) - jdn.gregorian_to_jdn(*d1))
    return CommandResult.ok(f"{diff} days between {dates[0].strip()} and {dates[1].strip()}")


def _age(payload):
    now = datetime.now(timezone.utc)
    d = jdn.parse_date(payload)
    if not d:
        return CommandResult.fail("Provide birthdate as YYYY-MM-DD")
    total_days = jdn.gregorian_to_jdn(now.year, now.month, now.day) - jdn.gregorian_to_jdn(*d)
    years = total_days // 365
    rem = total_days % 365
    return CommandResult.ok(f"{years} years, {rem // 30} months, {rem % 30} days old")


def _day_of_week(payload):
    if not payload:
        tz = get_timezone_from_settings()
        now = local_now(tz)
        payload = f"{now.year:04d}-{now.month:02d}-{now.day:02d}"
    d = jdn.parse_date(payload)
    if not d:
        return CommandResult.fail("Invalid input. Use a date like YYYY-MM-DD or keyword like 'today', 'yesterday', 'tomorrow'.")
    return CommandResult.ok(jdn.day_of_week(jdn.gregorian_to_jdn(*d)))


def _until(payload):
    d = jdn.parse_date(payload)
    if not d:
        return CommandResult.fail("Provide date as YYYY-MM-DD")
    tz = get_timezone_from_settings()
    now = local_now(tz)
    diff = jdn.gregorian_to_jdn(*d) - jdn.gregorian_to_jdn(now.year, now.month, now.day)
    return CommandResult.ok(f"{abs(diff)} days {'from now' if diff >= 0 else 'ago'}")


def _week_number(payload):
    d = jdn.parse_date(payload)
    if not d:
        return CommandResult.fail("Provide date as YYYY-MM-DD")
    y, m, dn = d
    jdn_val = jdn.gregorian_to_jdn(y, m, dn)
    return CommandResult.ok(f"Week {(jdn_val - jdn.gregorian_to_jdn(y, 1, 1)) // 7 + 1} of {y}")


def _day_of_year(payload):
    d = jdn.parse_date(payload)
    if not d:
        return CommandResult.fail("Provide date as YYYY-MM-DD")
    y, m, dn = d
    jdn_val = jdn.gregorian_to_jdn(y, m, dn)
    return CommandResult.ok(f"Day {jdn_val - jdn.gregorian_to_jdn(y, 1, 1) + 1} of {y}")


def _date_offset(payload):
    parts = payload.rsplit(None, 1)
    if len(parts) != 2:
        return CommandResult.fail("Provide 'YYYY-MM-DD offset_days' (e.g. '2026-06-30 -15')")
    d = jdn.parse_date(parts[0])
    if not d:
        return CommandResult.fail("Invalid date. Use YYYY-MM-DD.")
    try:
        offset = int(parts[1])
    except ValueError:
        return CommandResult.fail(f"Invalid offset '{parts[1]}'. Must be an integer.")
    jdn_val = jdn.gregorian_to_jdn(*d) + offset
    gy, gm, gd = jdn.jdn_to_gregorian(jdn_val)
    label = "before" if offset < 0 else "after"
    return CommandResult.ok(f"{abs(offset)} days {label} {parts[0]}: {_format_gregorian(gy, gm, gd)}")


def _leap_year(payload):
    d = jdn.parse_date(payload) if payload else None
    y = None
    if d:
        y = d[0]
    elif payload and payload.strip().isdigit():
        y = int(payload.strip())
    else:
        tz = get_timezone_from_settings()
        y = local_now(tz).year
    leap = jdn.is_gregorian_leap(y)
    return CommandResult.ok(f"{y} is{' a leap year' if leap else ' not a leap year'}")


def _years_offset(payload):
    parts = payload.rsplit(None, 1)
    if len(parts) != 2:
        return CommandResult.fail("Provide 'YYYY-MM-DD offset_years' (e.g. '2026-06-30 -10')")
    d = jdn.parse_date(parts[0])
    if not d:
        return CommandResult.fail("Invalid date. Use YYYY-MM-DD.")
    try:
        offset = int(parts[1])
    except ValueError:
        return CommandResult.fail(f"Invalid offset '{parts[1]}'. Must be an integer.")

    y, m, day = d
    y += offset
    if m == 2 and day == 29 and not jdn.is_gregorian_leap(y):
        day = 28
    jdn_val = jdn.gregorian_to_jdn(y, m, day)
    gy, gm, gd = jdn.jdn_to_gregorian(jdn_val)
    label = "before" if offset < 0 else "after"
    return CommandResult.ok(f"{abs(offset)} years {label} {parts[0]}: {_format_gregorian(gy, gm, gd)}")


def _weeks_between(payload):
    dates = re.split(r'\s+(?:to|and|>|->)\s+', payload)
    if len(dates) != 2:
        return CommandResult.fail("Provide two dates separated by ' to ' (e.g. '2024-01-01 to 2024-12-31')")
    d1 = jdn.parse_date(dates[0])
    d2 = jdn.parse_date(dates[1])
    if not d1 or not d2:
        return CommandResult.fail("Invalid date format. Use YYYY-MM-DD.")
    diff = abs(jdn.gregorian_to_jdn(*d2) - jdn.gregorian_to_jdn(*d1))
    weeks = diff // 7
    days = diff % 7
    return CommandResult.ok(f"{weeks} week{'s' if weeks != 1 else ''} and {days} day{'s' if days != 1 else ''} between {dates[0].strip()} and {dates[1].strip()}")


def _months_between(payload):
    dates = re.split(r'\s+(?:to|and|>|->)\s+', payload)
    if len(dates) != 2:
        return CommandResult.fail("Provide two dates separated by ' to '")
    d1 = jdn.parse_date(dates[0])
    d2 = jdn.parse_date(dates[1])
    if not d1 or not d2:
        return CommandResult.fail("Invalid date format. Use YYYY-MM-DD.")
    y1, m1, _ = d1
    y2, m2, _ = d2
    months = abs((y2 - y1) * 12 + (m2 - m1))
    return CommandResult.ok(f"{months} month{'s' if months != 1 else ''} between {dates[0].strip()} and {dates[1].strip()}")


def _years_between(payload):
    dates = re.split(r'\s+(?:to|and|>|->)\s+', payload)
    if len(dates) != 2:
        return CommandResult.fail("Provide two dates separated by ' to '")
    d1 = jdn.parse_date(dates[0])
    d2 = jdn.parse_date(dates[1])
    if not d1 or not d2:
        return CommandResult.fail("Invalid date format. Use YYYY-MM-DD.")
    years = abs(d2[0] - d1[0])
    return CommandResult.ok(f"{years} year{'s' if years != 1 else ''} between {dates[0].strip()} and {dates[1].strip()}")
