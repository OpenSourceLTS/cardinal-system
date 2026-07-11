import os
import json
import shutil
import textwrap
from datetime import datetime


class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


# ── Terminal Setup ──

def init_terminal():
    if os.name == "nt":
        os.system("color")


# ── History (in-memory) ──

_history = []
_HISTORY_MAX = 50


def add_to_history(role, text):
    _history.append({"role": role, "text": text, "time": datetime.now().strftime("%H:%M:%S")})
    if len(_history) > _HISTORY_MAX:
        _history.pop(0)


def get_history(n=20):
    return _history[-n:]


# ── Session Log ──

_LOG_FILE = "cardinal_session.log"


def log_session(entry):
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# ── Display Helpers ──

def mode_tag(mode):
    tag = "SIM" if mode == "simplex" else "DUP"
    return f"{Colors.YELLOW}{tag}{Colors.RESET}"


def prompt_str(engine):
    return f"  {mode_tag(engine.mode)} {Colors.YELLOW}You{Colors.RESET}: "


def wrap_text(text, width=78):
    return "\n".join(textwrap.fill(line, width=width) for line in text.split("\n"))


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    w = min(shutil.get_terminal_size().columns, 60)
    line = "=" * w
    print(f"{Colors.CYAN}{Colors.BOLD}{line}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  CARDINAL SYSTEM v0.0.1{Colors.RESET}")
    print(f"{Colors.DIM}  collection of Verbs | DAG Pipelining | Pattern Caching | Simplex/Duplex{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{line}{Colors.RESET}")


def status_bar(engine):
    m = f"{Colors.YELLOW}{engine.mode.upper()}{Colors.RESET}"
    l = f"{Colors.GREEN}ONLINE{Colors.RESET}" if engine.llm_online else f"{Colors.RED}OFFLINE{Colors.RESET}"
    return f"{Colors.DIM}[{m} | LLM: {l}]{Colors.RESET}"


def separator():
    w = min(shutil.get_terminal_size().columns, 40)
    print(f"{Colors.DIM}{'-' * w}{Colors.RESET}")


# ── Help ──

def print_help():
    print(f"\n{Colors.BOLD}{'='*40}{Colors.RESET}")
    print(f"{Colors.BOLD}  COMMANDS{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*40}{Colors.RESET}")
    print(f"  {Colors.CYAN}/help{Colors.RESET}         Show this help")
    print(f"  {Colors.CYAN}/status{Colors.RESET}       Mode, LLM state, pattern count")
    print(f"  {Colors.CYAN}/simplex{Colors.RESET}      Switch to Simplex mode")
    print(f"  {Colors.CYAN}/duplex{Colors.RESET}       Switch to Duplex mode")
    print(f"  {Colors.CYAN}/online{Colors.RESET}       Enable LLM")
    print(f"  {Colors.CYAN}/offline{Colors.RESET}      Disable LLM (pattern cache only)")
    print(f"  {Colors.CYAN}/patterns{Colors.RESET}     Show cached patterns")
    print(f"  {Colors.CYAN}/clear{Colors.RESET}        Clear terminal screen")
    print(f"  {Colors.CYAN}/purge{Colors.RESET}        Clear cached patterns")
    print(f"  {Colors.CYAN}/history{Colors.RESET}      Show last 20 exchanges")
    print(f"  {Colors.CYAN}/retry{Colors.RESET}        Re-run your last input")
    print(f"  {Colors.CYAN}/export{Colors.RESET}       Save conversation to file")
    print(f"  {Colors.CYAN}/tools{Colors.RESET}        List registered tools and verbs")
    print(f"  {Colors.CYAN}/log{Colors.RESET}          Show session log path")
    print(f"  {Colors.CYAN}/url{Colors.RESET}          Show or change LM Studio URL")
    print(f"  {Colors.CYAN}/quit{Colors.RESET}         Exit")
    print(f"{Colors.DIM}  Arrow keys browse input history. Any other text is sent to AI.{Colors.RESET}")


# ── Response Rendering ──

def render_result(result, engine, elapsed=None):
    if result.get("mode_switched"):
        line = f"{Colors.DIM}[System]{Colors.RESET} {result['response']}"
        print(f"  {line}")
        add_to_history("system", result["response"])
        log_session(f"[{datetime.now().isoformat()}] [System] {result['response']}")
        return

    if result.get("is_chat"):
        text = result["response"]
        print(f"  {Colors.CYAN}{wrap_text(text)}{Colors.RESET}")
        add_to_history("cardinal", text)
        log_session(f"[{datetime.now().isoformat()}] [Chat] {text}")
        return

    if result.get("success"):
        src = result.get("source", "llm")
        timing = f" ({elapsed:.1f}s)" if elapsed else ""
        if src == "local_pattern":
            src_tag = f"{Colors.DIM}[Cache]{Colors.RESET}"
        else:
            src_tag = f"{Colors.DIM}[LLM{timing}]{Colors.RESET}" if elapsed else f"{Colors.DIM}[LLM]{Colors.RESET}"

        chat_texts = []
        tool_lines = []

        for r in result.get("results", []):
            if not hasattr(r, "success"):
                continue
            if r.success:
                if r.value:
                    chat_texts.append(str(r.value))
                else:
                    tool_lines.append(f"  {src_tag} {Colors.GREEN}OK{Colors.RESET}")
            else:
                err = r.error or "?"
                if "Unknown tool" in err:
                    tool_lines.append(f"  {Colors.RED}{err}. Type /tools to see available tools.{Colors.RESET}")
                else:
                    tool_lines.append(f"  {Colors.RED}{err}{Colors.RESET}")

        for line in tool_lines:
            print(line)
        for t in chat_texts:
            print(f"  {src_tag} {Colors.CYAN}{wrap_text(t)}{Colors.RESET}")
            add_to_history("cardinal", t)
            log_session(f"[{datetime.now().isoformat()}] [Chat] {t}")
    else:
        err = result.get("error", "Unknown error")
        print(f"  {Colors.RED}[Error] {err}{Colors.RESET}")
        add_to_history("system", f"Error: {err}")
        log_session(f"[{datetime.now().isoformat()}] [Error] {err}")





# ── History Display & Export ──

def print_history():
    entries = get_history(20)
    if not entries:
        print(f"  {Colors.DIM}No conversation yet.{Colors.RESET}")
        return
    print(f"  {Colors.DIM}Last {len(entries)} exchanges:{Colors.RESET}")
    for e in entries:
        tag = f"{Colors.YELLOW}You{Colors.RESET}" if e["role"] == "user" else f"{Colors.CYAN}Cardinal{Colors.RESET}"
        text = e["text"][:120] + "..." if len(e["text"]) > 120 else e["text"]
        print(f"  {tag} ({e['time']}): {Colors.DIM}{text}{Colors.RESET}")


def export_history(filepath="cardinal_export.txt"):
    entries = get_history(50)
    if not entries:
        print(f"  {Colors.DIM}[System] No conversation to export.{Colors.RESET}")
        return
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=== Cardinal Session Export ===\n")
        f.write(f"Exported: {datetime.now().isoformat()}\n\n")
        for e in entries:
            role = "You" if e["role"] == "user" else "Cardinal"
            f.write(f"[{e['time']}] {role}: {e['text']}\n")
    print(f"  {Colors.DIM}[System] Exported {len(entries)} exchanges to {filepath}{Colors.RESET}")


# ── Tool List ──

def print_tools(router):
    print(f"  {Colors.DIM}Registered tools:{Colors.RESET}")
    for name, tool in router._tools.items():
        verbs = ", ".join(tool.manifest.verbs)
        desc = tool.manifest.description
        print(f"    {Colors.GREEN}{name}{Colors.RESET} [{verbs}] {Colors.DIM}{desc}{Colors.RESET}")
