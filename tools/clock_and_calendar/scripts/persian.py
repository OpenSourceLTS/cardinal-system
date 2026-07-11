PERSIAN_EPOCH = 1952063

PERSIAN_MONTHS = ["Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad",
                  "Shahrivar", "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand"]


def persian_leap(year):
    return (year % 33) in [4, 8, 12, 16, 20, 24, 28, 32]


def persian_year_days(year):
    return 366 if persian_leap(year) else 365


def persian_to_jdn(year, month, day):
    years = year - 1
    cycles = years // 33
    remainder = years % 33
    d = cycles * (33 * 365 + 8)
    for y in range(1, remainder + 1):
        d += 366 if persian_leap(y) else 365
    if month <= 6:
        d += (month - 1) * 31
    else:
        d += 6 * 31 + (month - 7) * 30
    d += day - 1
    return PERSIAN_EPOCH + d


def jdn_to_persian(jdn):
    days = jdn - PERSIAN_EPOCH
    if days < 0:
        return None
    year = max(1, days // 366)
    base = (year - 1) // 33
    rem = (year - 1) % 33
    cumul = base * (33 * 365 + 8)
    for y in range(1, rem + 1):
        cumul += 366 if persian_leap(y) else 365
    days -= cumul
    while days <= 0:
        year -= 1
        days += persian_year_days(year)
    while days > persian_year_days(year):
        days -= persian_year_days(year)
        year += 1
    if days < 6 * 31:
        month = days // 31 + 1
        day = days % 31 + 1
    else:
        days -= 6 * 31
        month = days // 30 + 7
        day = days % 30 + 1
    return year, month, day


def format_persian(year, month, day):
    return f"{PERSIAN_MONTHS[month - 1]} {day}, {year} SH"
