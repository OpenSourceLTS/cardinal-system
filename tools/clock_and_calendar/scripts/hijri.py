from .jdn import DAY_NAMES, GREGORIAN_MONTHS

HIJRI_EPOCH = 1948440

HIJRI_MONTHS = ["Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani",
                "Jumada al-Ula", "Jumada al-Thaniya", "Rajab", "Sha'ban",
                "Ramadan", "Shawwal", "Dhu al-Qi'dah", "Dhu al-Hijjah"]

HIJRI_MONTH_LENS = [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29]


def hijri_leap(year):
    return ((year * 11) + 14) % 30 < 11


def hijri_year_days(year):
    return 355 if hijri_leap(year) else 354


def hijri_to_jdn(year, month, day):
    d = (year - 1) * 354 + ((year - 1) * 11 + 14) // 30
    for m in range(1, month):
        d += HIJRI_MONTH_LENS[m - 1]
    d += day - 1
    return HIJRI_EPOCH + d


def jdn_to_hijri(jdn):
    if jdn < HIJRI_EPOCH:
        return None
    days = jdn - HIJRI_EPOCH
    year = max(1, days // 355)
    days -= (year - 1) * 354 + ((year - 1) * 11 + 14) // 30
    while days <= 0:
        year -= 1
        days += hijri_year_days(year)
    while days > hijri_year_days(year):
        days -= hijri_year_days(year)
        year += 1
    for m, ml in enumerate(HIJRI_MONTH_LENS):
        if m == 11 and hijri_leap(year):
            ml = 30
        if days < ml:
            return year, m + 1, days + 1
        days -= ml
    return year, 12, 30


def format_hijri(year, month, day):
    return f"{HIJRI_MONTHS[month - 1]} {day}, {year} AH"
