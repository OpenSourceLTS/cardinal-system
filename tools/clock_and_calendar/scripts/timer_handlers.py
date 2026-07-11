import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from core.base_tool import CommandResult
from .time_utils import format_time

_DATA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "memory" / "clock_and_calendar.json"


def _load():
    if _DATA_FILE.exists():
        try:
            with open(_DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"alarms": [], "timers": [], "stopwatch": {"running": False, "start": None, "elapsed": 0}, "events": []}


def _save(data):
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def handle_get(target, payload, metadata, ctx):
    t = (target or "").lower().strip()
    data = _load()

    if t in ("alarms", "alarm"):
        alarms = data.get("alarms", [])
        if not alarms:
            return CommandResult.ok("No alarms set.")
        lines = []
        for a in alarms:
            a_dt = datetime(1, 1, 1, a["hour"], a["minute"])
            label = a.get("label", "")
            lines.append(f"  [{a['id']}] {format_time(a_dt)}{' - ' + label if label else ''}")
        return CommandResult.ok("Alarms:\n" + "\n".join(lines))

    if t in ("timer", "timers"):
        timers = data.get("timers", [])
        now = time.time()
        lines = []
        for timer in timers:
            remaining = max(0, timer["target"] - now)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            label = timer.get("label", "")
            lines.append(f"  [{timer['id']}] {mins}:{secs:02d} remaining{' (' + label + ')' if label else ''}")
        return CommandResult.ok("Timers:\n" + "\n".join(lines) if lines else "No active timers.")

    if t in ("stopwatch",):
        sw = data.get("stopwatch", {"running": False, "start": None, "elapsed": 0})
        elapsed = sw.get("elapsed", 0)
        if sw.get("running") and sw.get("start"):
            elapsed += time.time() - sw["start"]
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        status = "Running" if sw.get("running") else "Stopped"
        return CommandResult.ok(f"Stopwatch: {status} at {mins}:{secs:02d}")

    if t in ("events", "event"):
        events = data.get("events", [])
        if not events:
            return CommandResult.ok("No events scheduled.")
        lines = []
        for ev in events:
            lines.append(f"  [{ev['id']}] {ev.get('datetime', '?')} - {ev.get('title', ev.get('label', '?'))}")
        return CommandResult.ok("Events:\n" + "\n".join(lines))

    return CommandResult.fail(f"Unknown get target: '{t}'. Try: alarms, timers, stopwatch, events")


def handle_set(target, payload, metadata, ctx):
    t = (target or "").lower().strip()
    p = (payload or "").strip()
    data = _load()

    if t == "alarm":
        parts = p.replace(":", " ").split()
        if len(parts) < 2:
            return CommandResult.fail("Provide time like '14:30' or '2:30 PM'")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return CommandResult.fail(f"Cannot parse time: '{p}'")
        label = " ".join(parts[2:]) if len(parts) > 2 else ""
        if len(parts) > 2 and parts[2].upper() in ("AM", "PM"):
            ampm = parts[2].upper()
            label = " ".join(parts[3:]) if len(parts) > 3 else ""
            if ampm == "PM" and hour != 12:
                hour += 12
            if ampm == "AM" and hour == 12:
                hour = 0
        alarm = {"id": str(uuid.uuid4())[:8], "hour": hour, "minute": minute, "label": label}
        data.setdefault("alarms", []).append(alarm)
        _save(data)
        return CommandResult.ok(f"Alarm set for {hour:02d}:{minute:02d}" + (f" ({label})" if label else ""))

    if t == "timer":
        total_secs = 0
        if p.endswith("s") and not p.endswith("ds") and not p.endswith("ins"):
            try:
                val = p.rstrip("s").strip()
                total_secs = int(val)
            except ValueError:
                return CommandResult.fail(f"Cannot parse duration: '{p}'")
        elif "minute" in p.lower():
            m = __import__('re').search(r'(\d+)', p)
            if m:
                total_secs = int(m.group(1)) * 60
            else:
                return CommandResult.fail(f"Cannot parse duration: '{p}'")
        elif "hour" in p.lower():
            m = __import__('re').search(r'(\d+)', p)
            if m:
                total_secs = int(m.group(1)) * 3600
            else:
                return CommandResult.fail(f"Cannot parse duration: '{p}'")
        elif p.endswith("m"):
            try:
                total_secs = int(p.rstrip("m")) * 60
            except ValueError:
                return CommandResult.fail(f"Cannot parse duration: '{p}'")
        elif p.endswith("h"):
            try:
                total_secs = int(p.rstrip("h")) * 3600
            except ValueError:
                return CommandResult.fail(f"Cannot parse duration: '{p}'")
        else:
            return CommandResult.fail("Specify duration like '10 minutes', '30s', '5m', '2h'")
        timer = {"id": str(uuid.uuid4())[:8], "duration": total_secs, "target": time.time() + total_secs, "label": p}
        data.setdefault("timers", []).append(timer)
        _save(data)
        return CommandResult.ok(f"Timer set for {total_secs} seconds.")

    if t == "stopwatch":
        sw = data.setdefault("stopwatch", {"running": False, "start": None, "elapsed": 0})
        if p.lower() in ("start", "resume"):
            if sw.get("running"):
                return CommandResult.ok("Stopwatch already running.")
            sw["running"] = True
            sw["start"] = time.time()
        elif p.lower() == "stop":
            if not sw.get("running"):
                return CommandResult.ok("Stopwatch already stopped.")
            sw["elapsed"] = sw.get("elapsed", 0) + time.time() - sw["start"]
            sw["running"] = False
            sw["start"] = None
        elif p.lower() == "reset":
            sw["running"] = False
            sw["start"] = None
            sw["elapsed"] = 0
        else:
            return CommandResult.fail("Use: stopwatch start/resume, stop, or reset")
        _save(data)
        elapsed = sw.get("elapsed", 0)
        if sw.get("running") and sw.get("start"):
            elapsed += time.time() - sw["start"]
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        return CommandResult.ok(f"Stopwatch: {p.lower()}d at {mins}:{secs:02d}")

    if t == "event":
        if not p:
            return CommandResult.fail("Provide event description and time/date")
        import re
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', p)
        time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', p, re.IGNORECASE)
        dt_str = date_match.group(1) if date_match else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if time_match:
            h, m, ampm = int(time_match.group(1)), int(time_match.group(2)), (time_match.group(3) or "").upper()
            if ampm == "PM" and h != 12:
                h += 12
            if ampm == "AM" and h == 12:
                h = 0
            dt_str += f" {h:02d}:{m:02d}"
        title = p
        if date_match:
            title = p.replace(date_match.group(1), "").strip()
        if time_match:
            title = title.replace(time_match.group(0), "").strip()
        ev = {"id": str(uuid.uuid4())[:8], "datetime": dt_str, "title": title}
        data.setdefault("events", []).append(ev)
        _save(data)
        return CommandResult.ok(f"Event created: '{title}' at {dt_str}")

    return CommandResult.fail(f"Unknown set target: '{t}'. Try: alarm, timer, stopwatch, event")


def handle_delete(target, payload, metadata, ctx):
    t = (target or "").lower().strip()
    p = (payload or "").strip()
    data = _load()

    if not p:
        return CommandResult.fail("Provide item ID to delete")

    if t in ("alarm", "alarms"):
        alarms = data.get("alarms", [])
        for i, a in enumerate(alarms):
            if a["id"] == p:
                data["alarms"].pop(i)
                _save(data)
                return CommandResult.ok(f"Alarm {p} deleted.")
        return CommandResult.fail(f"Alarm '{p}' not found.")

    if t in ("timer", "timers"):
        timers = data.get("timers", [])
        for i, timer in enumerate(timers):
            if timer["id"] == p:
                data["timers"].pop(i)
                _save(data)
                return CommandResult.ok(f"Timer {p} deleted.")
        return CommandResult.fail(f"Timer '{p}' not found.")

    if t in ("event", "events"):
        events = data.get("events", [])
        for i, ev in enumerate(events):
            if ev["id"] == p:
                data["events"].pop(i)
                _save(data)
                return CommandResult.ok(f"Event {p} deleted.")
        return CommandResult.fail(f"Event '{p}' not found.")

    return CommandResult.fail(f"Unknown delete target: '{t}'. Try: alarm, timer, event")
