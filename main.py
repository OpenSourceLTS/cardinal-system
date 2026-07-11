import argparse
from core.engine import CardinalSystemEngine
from openai import OpenAI


# CLI mode: interactive prompt loop for direct AI interaction via terminal.
def run_cli(engine):
    print("Cardinal AI v4.0 Initialized. (Type 'quit' to exit)")
    print("Features: structured tool calls via MCP.")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'quit':
            break

        result = engine.process_request(user_input)

        print("\n--- Cardinal ---")

        if result.get("is_chat"):
            print(result["response"])
        elif result.get("success"):
            for r in result.get("results", []):
                if hasattr(r, 'success') and r.success:
                    print(f"-> {r.value}")
                elif hasattr(r, 'error'):
                    print(f"[Error]: {r.error}")
        else:
            print("[System Error]:", result.get("error", "Unknown error"))


# Web mode: starts the Flask web server with the full UI.
def run_web(host: str = "0.0.0.0", port: int = 8080):
    from ui.web_server import run_server
    run_server(host, port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cardinal System")
    parser.add_argument("--web", action="store_true", help="Start web server (default port 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    args = parser.parse_args()

    engine = CardinalSystemEngine()

    if args.web:
        print(f"Starting web server at http://{args.host}:{args.port}")
        run_web(args.host, args.port)
    else:
        run_cli(engine)
