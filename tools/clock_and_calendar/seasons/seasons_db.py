from datetime import datetime
from .timezone_country import timezone_to_country

# Season system definitions
# Each system has a list of seasons with (start_month, start_day, end_month, end_day)
_SYSTEMS = {
    "northern": {
        "label": "Northern Hemisphere",
        "seasons": [
            ("Spring",  3, 20,  6, 20),
            ("Summer",  6, 21,  9, 22),
            ("Autumn",  9, 23, 12, 20),
            ("Winter", 12, 21,  3, 19),
        ],
    },
    "southern": {
        "label": "Southern Hemisphere",
        "seasons": [
            ("Spring",  9, 23, 12, 20),
            ("Summer", 12, 21,  3, 19),
            ("Autumn",  3, 20,  6, 20),
            ("Winter",  6, 21,  9, 22),
        ],
    },
    "bangladesh": {
        "label": "Bangladesh (Bengali 6-season)",
        "seasons": [
            ("Grishsho (Summer)",      4, 14,  6, 14),
            ("Borsha (Monsoon)",       6, 15,  8, 15),
            ("Shorot (Autumn)",        8, 16, 10, 16),
            ("Hemonto (Late Autumn)", 10, 17, 12, 15),
            ("Sheet (Winter)",        12, 16,  2, 14),
            ("Boshonto (Spring)",      2, 15,  4, 13),
        ],
    },
    "india": {
        "label": "India (Hindu 6-season)",
        "seasons": [
            ("Vasanta (Spring)",       2, 19,  4, 19),
            ("Grishma (Summer)",       4, 20,  6, 21),
            ("Varsha (Monsoon)",       6, 22,  8, 22),
            ("Sharad (Autumn)",        8, 23, 10, 22),
            ("Hemanta (Pre-winter)",  10, 23, 12, 21),
            ("Shishira (Winter)",     12, 22,  2, 18),
        ],
    },
    "japan": {
        "label": "Japan",
        "seasons": [
            ("Haru (Spring)",          3, 21,  6,  5),
            ("Tsuyu (Rainy)",          6,  6,  7, 16),
            ("Natsu (Summer)",         7, 17,  9,  6),
            ("Aki (Autumn)",           9,  7, 11,  6),
            ("Fuyu (Winter)",         11,  7,  3, 20),
        ],
    },
    "korea": {
        "label": "Korea",
        "seasons": [
            ("Spring",  3, 21,  6,  5),
            ("Summer",  6,  6,  9,  6),
            ("Autumn",  9,  7, 11, 20),
            ("Winter", 11, 21,  3, 20),
        ],
    },
    "tropical_wet_dry": {
        "label": "Tropical (Wet/Dry)",
        "seasons": [
            ("Dry",    11, 15,  4, 14),
            ("Wet",     4, 15, 11, 14),
        ],
    },
    "tropical_wet_dry_south": {
        "label": "Tropical Southern (Wet/Dry)",
        "seasons": [
            ("Wet",    11, 15,  4, 14),
            ("Dry",     4, 15, 11, 14),
        ],
    },
    "mediterranean": {
        "label": "Mediterranean",
        "seasons": [
            ("Spring",  3, 21,  5, 20),
            ("Summer",  5, 21,  9,  6),
            ("Autumn",  9,  7, 11, 20),
            ("Winter", 11, 21,  3, 20),
        ],
    },
    "australian_indigenous": {
        "label": "Australian Indigenous (Noongar 6-season)",
        "seasons": [
            ("Bunuru (Summer)",       12, 21,  3, 20),
            ("Djeran (Autumn)",        3, 21,  5, 20),
            ("Makuru (Wet/Cold)",      5, 21,  7, 20),
            ("Djilba (Spring)",        7, 21,  9,  6),
            ("Kambarang (Bloom)",      9,  7, 10, 31),
            ("Birak (Dry/Warm)",      11,  1, 12, 20),
        ],
    },
    "nordic": {
        "label": "Nordic (Midnight Sun/Polar Night)",
        "seasons": [
            ("Spring",  3, 21,  5, 20),
            ("Summer",  5, 21,  8, 20),
            ("Autumn",  8, 21, 10, 31),
            ("Winter", 11,  1,  3, 20),
        ],
    },
    "arctic": {
        "label": "Arctic",
        "seasons": [
            ("Midnight Sun",   4, 21,  8, 20),
            ("Autumn",         8, 21, 10, 15),
            ("Polar Night",   10, 16,  2, 20),
            ("Spring",         2, 21,  4, 20),
        ],
    },
}

# Hemisphere fallback by timezone region
_HEMISPHERE_PREFIX = {
    "Africa": "northern",
    "America/Argentina": "southern",
    "America/Brazil": "southern",
    "America/Buenos_Aires": "southern",
    "America/Cordoba": "southern",
    "America/Montevideo": "southern",
    "America/Asuncion": "southern",
    "America/Santiago": "southern",
    "America/Lima": "southern",
    "America/La_Paz": "southern",
    "America/Bogota": "northern", # near equator, treat as northern
    "America/Caracas": "northern",
    "America/Mexico_City": "northern",
    "America/Chicago": "northern",
    "America/New_York": "northern",
    "America/Denver": "northern",
    "America/Los_Angeles": "northern",
    "America/Toronto": "northern",
    "America/Vancouver": "northern",
    "America/Anchorage": "northern",
    "Pacific/Auckland": "southern",
    "Pacific/Fiji": "southern",
    "Pacific/Port_Moresby": "southern",
    "Australia": "southern",
    "Antarctica": "southern",
    "Asia": "northern",
    "Europe": "northern",
    "Indian": "southern",
}

# Country → season system overrides
_COUNTRY_OVERRIDES = {
    "Bangladesh": "bangladesh",
    "India": "india",
    "Japan": "japan",
    "South_Korea": "korea",
    "North_Korea": "korea",
    "Indonesia": "tropical_wet_dry",
    "Malaysia": "tropical_wet_dry",
    "Singapore": "tropical_wet_dry",
    "Thailand": "tropical_wet_dry",
    "Vietnam": "tropical_wet_dry",
    "Philippines": "tropical_wet_dry",
    "Myanmar": "tropical_wet_dry",
    "Cambodia": "tropical_wet_dry",
    "Laos": "tropical_wet_dry",
    "Brunei": "tropical_wet_dry",
    "East_Timor": "tropical_wet_dry_south",
    "Papua_New_Guinea": "tropical_wet_dry_south",
    "Fiji": "tropical_wet_dry_south",
    "Kenya": "tropical_wet_dry",
    "Uganda": "tropical_wet_dry",
    "Tanzania": "tropical_wet_dry",
    "Nigeria": "tropical_wet_dry",
    "Ghana": "tropical_wet_dry",
    "Ivory_Coast": "tropical_wet_dry",
    "Cameroon": "tropical_wet_dry",
    "DRC": "tropical_wet_dry",
    "Ethiopia": "tropical_wet_dry",
    "Somalia": "tropical_wet_dry",
    "Sudan": "tropical_wet_dry",
    "South_Sudan": "tropical_wet_dry",
    "Greece": "mediterranean",
    "Italy": "mediterranean",
    "Spain": "mediterranean",
    "Portugal": "mediterranean",
    "Turkey": "mediterranean",
    "Cyprus": "mediterranean",
    "Malta": "mediterranean",
    "Croatia": "mediterranean",
    "Albania": "mediterranean",
    "Morocco": "mediterranean",
    "Algeria": "mediterranean",
    "Tunisia": "mediterranean",
    "Libya": "mediterranean",
    "Egypt": "mediterranean",
    "Lebanon": "mediterranean",
    "Syria": "mediterranean",
    "Israel": "mediterranean",
    "Jordan": "mediterranean",
    "Palestine": "mediterranean",
    "Sweden": "nordic",
    "Norway": "nordic",
    "Finland": "nordic",
    "Iceland": "nordic",
    "Greenland": "arctic",
    "New_Zealand": "southern",
    "South_Africa": "southern",
    "Brazil": "southern",
    "Argentina": "southern",
    "Chile": "southern",
    "Peru": "southern",
    "Bolivia": "southern",
    "Paraguay": "southern",
    "Uruguay": "southern",
    "Ecuador": "tropical_wet_dry",
    "Colombia": "tropical_wet_dry",
    "Venezuela": "tropical_wet_dry",
    "Panama": "tropical_wet_dry",
    "Costa_Rica": "tropical_wet_dry",
    "Nicaragua": "tropical_wet_dry",
    "Honduras": "tropical_wet_dry",
    "Guatemala": "tropical_wet_dry",
    "El_Salvador": "tropical_wet_dry",
    "Belize": "tropical_wet_dry",
    "Cuba": "tropical_wet_dry",
    "Jamaica": "tropical_wet_dry",
    "Dominican_Republic": "tropical_wet_dry",
    "Haiti": "tropical_wet_dry",
    "Bahamas": "tropical_wet_dry",
    "Trinidad_and_Tobago": "tropical_wet_dry",
    "Barbados": "tropical_wet_dry",
    "Sri_Lanka": "tropical_wet_dry",
    "Nepal": "india",
    "Bhutan": "india",
    "Pakistan": "india",
    "Afghanistan": "northern",
    "Iran": "northern",
    "Iraq": "mediterranean",
    "Saudi_Arabia": "tropical_wet_dry",
    "Yemen": "tropical_wet_dry",
    "Oman": "tropical_wet_dry",
    "UAE": "tropical_wet_dry",
    "Qatar": "tropical_wet_dry",
    "Bahrain": "tropical_wet_dry",
    "Kuwait": "tropical_wet_dry",
    "Maldives": "tropical_wet_dry",
}


def _is_between(m, d, sm, sd, em, ed):
    """Check if (m, d) falls within the range [sm, sd] to [em, ed] inclusive."""
    start = (sm, sd)
    end = (em, ed)
    point = (m, d)
    if start <= end:
        return start <= point <= end
    return point >= start or point <= end


def get_system(tz_name: str) -> dict:
    """Get the season system for a timezone name."""
    country = timezone_to_country(tz_name)
    if not country:
        # Try hemisphere fallback by region prefix
        parts = tz_name.split("/")
        if parts:
            region = parts[0]
            hemi = _HEMISPHERE_PREFIX.get(region, "northern")
            return _SYSTEMS[hemi]
        return _SYSTEMS["northern"]

    sys_name = _COUNTRY_OVERRIDES.get(country)

    if sys_name:
        return _SYSTEMS[sys_name]

    # Hemisphere fallback by country zone
    region = _HEMISPHERE_PREFIX.get(country)
    if region and region in _SYSTEMS:
        return _SYSTEMS[region]
    return _SYSTEMS["northern"]


def get_season(tz_name: str, month: int = None, day: int = None) -> str:
    """Get the current season name for a given timezone."""
    if month is None or day is None:
        now = datetime.now()
        month = now.month
        day = now.day

    system = get_system(tz_name)
    if not system:
        return "Unknown"

    for name, sm, sd, em, ed in system["seasons"]:
        if _is_between(month, day, sm, sd, em, ed):
            return name
    return system["seasons"][-1][0] if system["seasons"] else "Unknown"


def list_systems() -> dict:
    return {k: v["label"] for k, v in _SYSTEMS.items()}
