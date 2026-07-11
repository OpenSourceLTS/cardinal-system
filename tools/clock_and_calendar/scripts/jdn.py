from datetime import datetime, timezone, timedelta
import re

GREGORIAN_EPOCH = 1721426
JULIAN_EPOCH = 1721424

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]

GREGORIAN_MONTHS = ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"]


def gregorian_to_jdn(year, month, day):
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def jdn_to_gregorian(jdn):
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + (m // 10)
    return year, month, day


def julian_to_jdn(year, month, day):
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083


def jdn_to_julian(jdn):
    a = jdn + 32082
    b = (4 * a + 3) // 1461
    c = a - 1461 * b // 4
    d = (5 * c + 2) // 153
    day = c - (153 * d + 2) // 5 + 1
    month = d + 3 - 12 * (d // 10)
    year = b - 4800 + (d // 10)
    return year, month, day


def day_of_week(jdn):
    return DAY_NAMES[jdn % 7]


def is_gregorian_leap(year):
    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0


def parse_date(s, now=None):
    s = s.strip()
    if now is None:
        now = datetime.now(timezone.utc)
    sl = s.lower()

    if sl in ("today", "now", "current"):
        return now.year, now.month, now.day
    if sl in ("yesterday", "1 day ago"):
        d = now - timedelta(days=1)
        return d.year, d.month, d.day
    if sl == "tomorrow":
        d = now + timedelta(days=1)
        return d.year, d.month, d.day

    m = re.match(r'^(\d+)\s+day[s]?\s+ago$', sl)
    if m:
        d = now - timedelta(days=int(m.group(1)))
        return d.year, d.month, d.day

    m = re.match(r'^(?:(\d+)\s+day[s]?\s+from\s+now|in\s+(\d+)\s+day[s]?)$', sl)
    if m:
        n = int(m.group(1) or m.group(2))
        d = now + timedelta(days=n)
        return d.year, d.month, d.day

    neg = 1
    if s.startswith("-"):
        neg = -1
        s = s[1:]
    parts = s.split("-")
    try:
        if len(parts) == 3:
            return int(parts[0]) * neg, int(parts[1]), int(parts[2])
        return None
    except Exception:
        return None
