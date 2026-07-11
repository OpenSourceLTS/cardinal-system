import re
from pathlib import Path
from zoneinfo import available_timezones, ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, timezone, timedelta

TZDB_DIR = Path(__file__).parent.parent / "tzdb"
ISO3166_FILE = TZDB_DIR / "iso3166.tab"
ZONE_TAB = TZDB_DIR / "zone.tab"
ZONE1970_TAB = TZDB_DIR / "zone1970.tab"


def _parse_iso3166():
    name_to_iso = {}
    if not ISO3166_FILE.exists():
        return name_to_iso
    for line in ISO3166_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" not in line:
            continue
        code, name = line.split("\t", 1)
        lower = name.strip().lower()
        name_to_iso[lower] = code.strip().lower()
        short = lower.split("(")[0].strip()
        if short != lower:
            name_to_iso[short] = code.strip().lower()
    return name_to_iso


def _parse_zone_tab():
    cc_to_tz = {}
    city_to_tz = {}
    coord_to_tz = {}
    tz_names = set()
    all_zones = []  # (country_code, tz_name, coords)
    if not ZONE_TAB.exists():
        return cc_to_tz, city_to_tz, coord_to_tz, tz_names, all_zones
    for line in ZONE_TAB.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        country_code = parts[0].strip().lower()
        coords = parts[1].strip()
        tz_name = parts[2].strip()
        comment = parts[3].strip() if len(parts) > 3 else ""
        tz_names.add(tz_name)
        all_zones.append((country_code, tz_name, coords))
        if country_code not in cc_to_tz:
            cc_to_tz[country_code] = tz_name
        city_part = tz_name.split("/")[-1].replace("_", " ").lower()
        if city_part not in city_to_tz:
            city_to_tz[city_part] = tz_name
        if comment:
            comment_city = comment.split("(")[0].strip().replace("_", " ").lower()
            if comment_city and comment_city not in city_to_tz:
                city_to_tz[comment_city] = tz_name
        coord_to_tz[coords] = tz_name
    return cc_to_tz, city_to_tz, coord_to_tz, tz_names, all_zones


_ALT_NAMES = {
    "uk": "gb",
    "usa": "us",
    "united states": "us",
    "united states of america": "us",
    "uae": "ae",
    "united arab emirates": "ae",
    "england": "gb",
    "america": "us",
    "czech republic": "cz",
    "czechia": "cz",
    "turkiye": "tr",
    "north korea": "kp",
    "south korea": "kr",
    "britain": "gb",
    "palestine": "ps",
    "russia": "ru",
    "viet nam": "vn",
}

# Preferred (most populous) timezone for countries with multiple zones
_MAIN_TZ = {
    "au": "Australia/Sydney",
    "br": "America/Sao_Paulo",
    "ca": "America/Toronto",
    "jp": "Asia/Tokyo",
    "us": "America/New_York",
    "mx": "America/Mexico_City",
    "ru": "Europe/Moscow",
    "id": "Asia/Jakarta",
    "cn": "Asia/Shanghai",
    "de": "Europe/Berlin",
    "es": "Europe/Madrid",
    "pt": "Europe/Lisbon",
    "nz": "Pacific/Auckland",
    "cl": "America/Santiago",
    "ar": "America/Argentina/Buenos_Aires",
    "cd": "Africa/Kinshasa",
    "ua": "Europe/Kyiv",
    "my": "Asia/Kuala_Lumpur",
    "kz": "Asia/Almaty",
    "ec": "America/Guayaquil",
    "pe": "America/Lima",
    "co": "America/Bogota",
    "gl": "America/Nuuk",
    "fm": "Pacific/Chuuk",
    "pg": "Pacific/Port_Moresby",
    "ki": "Pacific/Tarawa",
    "mn": "Asia/Ulaanbaatar",
    "mh": "Pacific/Majuro",
    "pf": "Pacific/Tahiti",
    "um": "Pacific/Midway",
}

_ALIAS_TO_TZ = {
    "nyc": "America/New_York",
    "ny": "America/New_York",
    "new york city": "America/New_York",
    "hongkong": "Asia/Hong_Kong",
    "macau": "Asia/Macau",
    "ho chi minh": "Asia/Ho_Chi_Minh",
    "saigon": "Asia/Ho_Chi_Minh",
    "burma": "Asia/Yangon",
    "bombay": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "calcuta": "Asia/Kolkata",
    "peking": "Asia/Shanghai",
    "korea": "Asia/Seoul",
}

def _parse_backward():
    links = {}
    bw_file = TZDB_DIR / "backward"
    if not bw_file.exists():
        return links
    for line in bw_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("Link"):
            parts = line.split()
            if len(parts) >= 3:
                links[parts[2]] = parts[1]
    return links


_CC_TO_TZ, _CITY_TO_TZ, _COORD_TO_TZ, _VALID_TZ_NAMES, _ALL_ZONES = _parse_zone_tab()
_NAME_TO_ISO = _parse_iso3166()
_BACKWARD_LINKS = _parse_backward()

# Also add all available timezone names from zoneinfo
for tz in available_timezones():
    _VALID_TZ_NAMES.add(tz)

# Build UTC offset -> preferred IANA timezone mapping (using standard offsets, not DST)
_OFFSET_TO_TZ: dict[str, str] = {}
_REF_DATES = [
    datetime(2024, 1, 15, 12, tzinfo=timezone.utc),  # northern winter
    datetime(2024, 7, 15, 12, tzinfo=timezone.utc),  # southern winter
]
def _compute_std_offset(tz_name: str):
    try:
        zi = ZoneInfo(tz_name)
        for dt in _REF_DATES:
            dst_val = zi.dst(dt)
            if dst_val is None or dst_val.total_seconds() == 0:
                return zi.utcoffset(dt)
        return zi.utcoffset(_REF_DATES[0])
    except Exception:
        return None

def _offset_key(std_offset):
    if std_offset is None:
        return None
    total_hours = int(std_offset.total_seconds() / 3600)
    total_minutes = abs(int((std_offset.total_seconds() % 3600) / 60))
    if total_minutes == 0:
        return f"UTC{total_hours:+d}"
    return f"UTC{total_hours:+d}:{total_minutes:02d}"

# Pass 1: only _MAIN_TZ preferred zones (most populous city per country)
for tz_name in _MAIN_TZ.values():
    ok = _offset_key(_compute_std_offset(tz_name))
    if ok:
        _OFFSET_TO_TZ.setdefault(ok, tz_name)

# Override with best-known timezone per offset
_OFFSET_TO_TZ.update({
    "UTC-12": "Pacific/Midway",
    "UTC-11": "Pacific/Midway",
    "UTC-10": "Pacific/Honolulu",
    "UTC-9": "America/Anchorage",
    "UTC-8": "America/Los_Angeles",
    "UTC-7": "America/Denver",
    "UTC-6": "America/Chicago",
    "UTC-5": "America/New_York",
    "UTC-4": "America/Santiago",
    "UTC-3": "America/Sao_Paulo",
    "UTC-2": "America/Nuuk",
    "UTC-1": "Atlantic/Cape_Verde",
    "UTC+0": "Europe/London",
    "UTC+1": "Europe/Berlin",
    "UTC+2": "Europe/Helsinki",
    "UTC+3": "Europe/Moscow",
    "UTC+3:30": "Asia/Tehran",
    "UTC+4": "Asia/Dubai",
    "UTC+4:30": "Asia/Kabul",
    "UTC+5": "Asia/Karachi",
    "UTC+5:30": "Asia/Kolkata",
    "UTC+5:45": "Asia/Kathmandu",
    "UTC+6": "Asia/Dhaka",
    "UTC+6:30": "Asia/Yangon",
    "UTC+7": "Asia/Bangkok",
    "UTC+8": "Asia/Shanghai",
    "UTC+8:45": "Australia/Eucla",
    "UTC+9": "Asia/Tokyo",
    "UTC+9:30": "Australia/Darwin",
    "UTC+10": "Australia/Sydney",
    "UTC+10:30": "Australia/Lord_Howe",
    "UTC+11": "Pacific/Noumea",
    "UTC+12": "Pacific/Auckland",
    "UTC+12:45": "Pacific/Chatham",
    "UTC+13": "Pacific/Apia",
    "UTC+14": "Pacific/Kiritimati",
})

# Pass 2: fill remaining gaps from all zone.tab entries
for cc, tz_name, _ in _ALL_ZONES:
    ok = _offset_key(_compute_std_offset(tz_name))
    if ok and ok not in _OFFSET_TO_TZ:
        _OFFSET_TO_TZ[ok] = tz_name


def _parse_utc_offset(tz_name: str):
    m = re.match(r'^UTC([+-])(\d{1,2})(?::(\d{2}))?$', tz_name.strip(), re.IGNORECASE)
    if not m:
        return None
    sign = 1 if m.group(1) == '+' else -1
    hours = int(m.group(2))
    minutes = int(m.group(3)) if m.group(3) else 0
    return timedelta(hours=sign * hours, minutes=sign * minutes)


def resolve_timezone(user_input: str) -> str:
    if not user_input:
        return ""
    input_lower = user_input.strip().lower()
    has_slash = "/" in input_lower

    # UTC offset: UTC+6, UTC+06:00, UTC-5, GMT+6, or bare +6, -5, +5:30
    m_offset = re.match(r'^(?:UTC|GMT)?([+-]\d{1,2}(?::\d{2})?)$', input_lower, re.IGNORECASE)
    if m_offset:
        bare = m_offset.group(1)
        sign = bare[0]
        parts = bare[1:].split(":")
        hours = str(int(parts[0]))
        key = f"UTC{sign}{hours}"
        if len(parts) > 1 and parts[1] != "00":
            key += f":{parts[1]}"
        if key in _OFFSET_TO_TZ:
            return _OFFSET_TO_TZ[key]

    # Normalize underscores to spaces for city/country lookups
    normalized = input_lower.replace("_", " ")
    parts_slash = [p.replace("_", " ").strip() for p in input_lower.split("/", 1)]

    # Format: country/city (Japan/Tokyo), continent/city (Asia/Tokyo)
    if has_slash:
        first, last = parts_slash[0], parts_slash[-1]
        if last in _CITY_TO_TZ:
            return _CITY_TO_TZ[last]
        iso = _resolve_country_to_iso(first)
        if iso:
            if iso in _MAIN_TZ:
                return _MAIN_TZ[iso]
            if iso in _CC_TO_TZ:
                return _CC_TO_TZ[iso]

    # Country name -> preferred timezone (for bare names without /)
    if not has_slash:
        iso = _resolve_country_to_iso(normalized)
        if iso:
            if iso in _MAIN_TZ:
                return _MAIN_TZ[iso]
            if iso in _CC_TO_TZ:
                return _CC_TO_TZ[iso]

    # City name / alias (use normalized input)
    if normalized in _ALIAS_TO_TZ:
        return _ALIAS_TO_TZ[normalized]
    if normalized in _CITY_TO_TZ:
        return _CITY_TO_TZ[normalized]

    # Exact IANA match (names with / like America/New_York)
    if has_slash and user_input.strip() in _VALID_TZ_NAMES:
        return user_input.strip()

    # Backward link fallback (bare name like "Singapore" as valid IANA)
    if not has_slash and user_input.strip() in _VALID_TZ_NAMES:
        return user_input.strip()

    # Partial city name match (only for longer inputs)
    if len(normalized) >= 4:
        for key, tz_name in _CITY_TO_TZ.items():
            if normalized in key or key in normalized:
                return tz_name

    # Word-by-word
    words = normalized.split()
    for word in words:
        if word in _CITY_TO_TZ:
            return _CITY_TO_TZ[word]

    # Backward link resolution: "New_York" -> "America/New_York"
    if user_input.strip() in _BACKWARD_LINKS:
        return _BACKWARD_LINKS[user_input.strip()]

    return user_input.strip()


def _resolve_country_to_iso(name: str) -> str | None:
    name = name.strip().lower()
    # Direct ISO code
    if name in _CC_TO_TZ or name in _MAIN_TZ:
        return name
    # Alternative common names
    if name in _ALT_NAMES:
        return _ALT_NAMES[name]
    # Full country name from iso3166.tab
    if name in _NAME_TO_ISO:
        return _NAME_TO_ISO[name]
    # Partial name match (only for longer inputs to avoid false positives)
    if len(name) >= 4:
        for key, iso in _NAME_TO_ISO.items():
            if name in key or key in name:
                return iso
    return None


def _is_valid_timezone(tz_name: str) -> bool:
    if not tz_name:
        return False
    tz = tz_name.strip()
    if re.match(r'^(?:UTC|GMT)?[+-]\d{1,2}(:\d{2})?$', tz, re.IGNORECASE):
        return True
    # Resolve backward links
    if tz in _BACKWARD_LINKS:
        return True
    try:
        ZoneInfo(tz)
        return True
    except (KeyError, TypeError, ZoneInfoNotFoundError):
        return False
