import os
import sys
import time
import argparse

try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        readline = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core.engine import CardinalSystemEngine
from cli.handler import (
    Colors, init_terminal, banner, status_bar, prompt_str, separator,
    print_help, render_result, print_history,
    clear_screen, export_history
)
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Cardinal System CLI")
    parser.add_argument("--url", default="http://localhost:1234/v1",
                        help="LM Studio API URL (default: http://localhost:1234/v1)")
    args = parser.parse_args()

    init_terminal()

    engine = CardinalSystemEngine()

    banner()
    print(f"  {Colors.DIM}API: {args.url}{Colors.RESET}")
    print(f"  Type /help for commands")
    separator()

    last_input = ""

    while True:
        try:
            raw = input(f"\n{prompt_str(engine)}")
            user_input = raw.strip()
            if not user_input:
                continue

            # Slash Commands
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/quit", "/exit"):
                    print(f"  {Colors.DIM}[System] Shutting down.{Colors.RESET}")
                    break

                elif cmd == "/help":
                    print_help()

                elif cmd == "/clear":
                    clear_screen()
                    banner()

                elif cmd == "/history":
                    print_history()

                elif cmd == "/retry":
                    if last_input:
                        print(f"  {Colors.DIM}[System] Retrying: {last_input}{Colors.RESET}")
                        user_input = last_input
                    else:
                        print(f"  {Colors.DIM}[System] Nothing to retry.{Colors.RESET}")
                        continue

                elif cmd == "/export":
                    export_history()

                elif cmd == "/url":
                    print(f"  {Colors.DIM}Current API URL: {args.url}{Colors.RESET}")

                else:
                    print(f"  {Colors.RED}Unknown command. Type /help{Colors.RESET}")
                    continue

                if cmd != "/retry":
                    continue

            # Natural Language Input
            last_input = user_input

            t0 = time.time()
            result = engine.process_request(user_input)
            elapsed = time.time() - t0

            render_result(result, engine, elapsed)

        except KeyboardInterrupt:
            print(f"\n  {Colors.DIM}[System] Shutting down.{Colors.RESET}")
            break
        except Exception as e:
            print(f"  {Colors.RED}[Error] {e}{Colors.RESET}")
            break


if __name__ == "__main__":
    main()
