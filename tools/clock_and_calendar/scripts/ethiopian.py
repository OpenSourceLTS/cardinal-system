ETHIOPIAN_EPOCH = 1724222

ETHIOPIAN_MONTHS = ["Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir",
                    "Yekatit", "Megabit", "Miazia", "Ginbot", "Sene",
                    "Hamle", "Nehase", "Pagume"]

ETHIOPIAN_MONTH_LENS = [30] * 12 + [5]


def ethiopian_leap(year):
    return year % 4 == 0


def ethiopian_year_days(year):
    return 366 if ethiopian_leap(year) else 365


def ethiopian_to_jdn(year, month, day):
    years = year - 1
    d = years * 365 + years // 4
    d += (month - 1) * 30
    d += day - 1
    if month == 13 and ethiopian_leap(year):
        d += 1
    return ETHIOPIAN_EPOCH + d


def jdn_to_ethiopian(jdn):
    days = jdn - ETHIOPIAN_EPOCH
    year = max(1, days // 366)
    days -= (year - 1) * 365 + (year - 1) // 4
    while days <= 0:
        year -= 1
        days += ethiopian_year_days(year)
    while days > ethiopian_year_days(year):
        days -= ethiopian_year_days(year)
        year += 1
    month = days // 30 + 1
    day = days % 30 + 1
    if month == 13 and day > (6 if ethiopian_leap(year) else 5):
        day = 6 if ethiopian_leap(year) else 5
    return year, month, day


def format_ethiopian(year, month, day):
    m = ETHIOPIAN_MONTHS[month - 1] if month <= 13 else f"Month {month}"
    return f"{m} {day}, {year} EC"
