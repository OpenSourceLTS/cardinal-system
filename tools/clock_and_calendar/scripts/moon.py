import math
from .jdn import jdn_to_gregorian

LUNAR_CYCLE = 29.53058867
KNOWN_NEW_MOON = 2451550.1


def moon_phase(jdn):
    days_since = jdn - KNOWN_NEW_MOON
    phase = (days_since % LUNAR_CYCLE) / LUNAR_CYCLE
    illum = int(math.sin(phase * 2 * math.pi) ** 2 * 100)
    if phase < 0.03 or phase > 0.97:
        return "New Moon", 0
    elif phase < 0.22:
        return "Waxing Crescent", illum
    elif phase < 0.28:
        return "First Quarter", 50
    elif phase < 0.47:
        return "Waxing Gibbous", illum
    elif phase < 0.53:
        return "Full Moon", 100
    elif phase < 0.72:
        return "Waning Gibbous", illum
    elif phase < 0.78:
        return "Last Quarter", 50
    else:
        return "Waning Crescent", illum


def next_moon_phases(jdn, count=4):
    phases = []
    j = float(jdn)
    while len(phases) < count:
        days_since = j - KNOWN_NEW_MOON
        raw = (days_since % LUNAR_CYCLE) / LUNAR_CYCLE
        closest = None
        closest_dist = 0.1
        for target, label in [(0, "New Moon"), (0.25, "First Quarter"),
                              (0.5, "Full Moon"), (0.75, "Last Quarter")]:
            dist = abs(raw - target)
            if dist < closest_dist:
                closest_dist = dist
                closest = label
        if closest and closest_dist < 0.01:
            y, m, d = jdn_to_gregorian(int(round(j)))
            phases.append((f"{y:04d}-{m:02d}-{d:02d}", closest))
        j += 1
    return phases
