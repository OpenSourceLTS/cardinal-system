from core.base_tool import CommandResult
from .time_utils import save_timezone_to_settings


def handle_set(target, payload, metadata):
    """Handle set(clock)@timezone|<timezone_name>"""
    t = target.lower().strip() if target else ""
    p = (payload or "").strip()

    if t == "timezone":
        tz_name = p
        if not tz_name:
            return CommandResult.fail("Provide timezone name, e.g., set(clock)@timezone|America/New_York")

        if save_timezone_to_settings(tz_name):
            return CommandResult.ok(f"Timezone set to {tz_name}")
        else:
            return CommandResult.fail("Failed to save timezone")

    return CommandResult.fail(f"Unknown set target: '{target}'. Try: timezone")