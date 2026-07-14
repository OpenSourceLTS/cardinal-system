"""Training Data Generator for FunctionGemma Fine-Tuning.

Generates training_data.jsonl in native FunctionGemma format.

Usage:
    python generate_training_data.py
    python generate_training_data.py --lang bn,en,hi --templates 3
    python generate_training_data.py --output-dir /path/to/output
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

LANGUAGES = [
    ("ar", "Arabic"), ("bn", "Bangla"), ("zh", "Chinese (Mandarin)"),
    ("cs", "Czech"), ("nl", "Dutch"), ("en", "English"),
    ("fr", "French"), ("de", "German"), ("el", "Greek"),
    ("he", "Hebrew"), ("hi", "Hindi"), ("hu", "Hungarian"),
    ("id", "Indonesian"), ("it", "Italian"), ("ja", "Japanese"),
    ("ko", "Korean"), ("mr", "Marathi"), ("fa", "Persian (Farsi)"),
    ("pl", "Polish"), ("pt", "Portuguese"), ("ro", "Romanian"),
    ("ru", "Russian"), ("es", "Spanish"), ("sw", "Swahili"),
    ("ta", "Tamil"), ("te", "Telugu"), ("th", "Thai"),
    ("tr", "Turkish"), ("ur", "Urdu"), ("vi", "Vietnamese"),
]


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manifests(manifests_dir: Path) -> list:
    manifests = []
    for manifest_path in sorted(manifests_dir.glob("*/manifest.json")):
        data = load_json(manifest_path)
        vp = data.get("manifest", {}).get("a@p", {})
        manifests.append({
            "name": data.get("name", manifest_path.parent.stem),
            "description": data.get("description", ""),
            "actions": data.get("actions", []),
            "a@p": vp,
        })
    return manifests


def filter_languages(lang_filter: str) -> list:
    if not lang_filter:
        return LANGUAGES
    codes = [c.strip() for c in lang_filter.split(",")]
    lang_map = dict(LANGUAGES)
    return [(c, lang_map.get(c, c)) for c in codes if c]


def resolve_payload(examples: dict, tool_name: str, target: str, default: str = "value") -> str:
    val = examples.get(tool_name, {}).get(target, default)
    if isinstance(val, list):
        return random.choice(val)
    return val


# ── FunctionGemma format builders ──────────────────────────────────────────

def escape(val: str) -> str:
    return f"<escape>{val}<escape>"


def build_tools_schema(manifests: list) -> list:
    tools = []
    for m in manifests:
        actions = m["actions"]
        tools.append({
            "type": "function",
            "function": {
                "name": m["name"],
                "description": m.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": actions,
                            "description": f"Action verb. One of: {', '.join(actions)}"
                        },
                        "target": {"type": "string", "description": "Target resource"},
                        "payload": {"type": "string", "description": "Payload data"}
                    },
                    "required": ["action"]
                }
            }
        })
    return tools


def build_call_str(tool_name: str, args: dict) -> str:
    param_parts = []
    for key, value in args.items():
        if value is not None and value != "":
            param_parts.append(f"{key}:{escape(value)}")
    return f"<start_function_call>call:{tool_name}{{{','.join(param_parts)}}}<end_function_call>"


# ── Parameter mapping ──────────────────────────────────────────────────────
# All tools use the same 3-param schema: action, target, payload.
# The a@p entry provides target and payload_format; payload_val comes from examples.

def map_params(tool_name: str, action: str, target: str, payload_val: str, payload_format: str) -> dict:
    params = {"action": action, "target": target}
    if payload_val and payload_val.strip() and payload_val != "value":
        params["payload"] = payload_val
    return params


# ── CSV generator ──────────────────────────────────────────────────────────

def generate_single_records(
    manifests: list,
    templates: dict,
    payload_examples: dict,
    languages: list,
    max_templates: int,
) -> list:
    """Generate single-tool-call records: list of [user_text, tool_name, args_dict]."""
    rows = []
    warnings = 0

    for manifest in manifests:
        tool_name = manifest["name"]
        vp = manifest["a@p"]

        for action, targets in vp.items():
            action_templates = templates.get(action, templates.get("get", {}))

            for target_entry in targets:
                target = target_entry[0] if target_entry else ""
                payload_format = target_entry[1] if len(target_entry) > 1 else ""

                for lang_code, _ in languages:
                    tmpls = action_templates.get(lang_code, action_templates.get("en", []))
                    if not tmpls:
                        tmpls = action_templates.get("en", [f"{action} {target}"])
                        warnings += 1

                    for template in tmpls[:max_templates]:
                        text = template
                        if "{target}" in text:
                            text = text.replace("{target}", target if target else tool_name)
                        if "{payload}" in text:
                            pl = resolve_payload(payload_examples, tool_name, target, "value")
                            text = text.replace("{payload}", pl)

                        pl = resolve_payload(payload_examples, tool_name, target)
                        args = map_params(tool_name, action, target, pl, payload_format)
                        rows.append([text, tool_name, args])

    if warnings:
        print(f"  Warnings: {warnings} missing language templates (fell back to en)")
    return rows


# ── JSONL generator ────────────────────────────────────────────────────────

DEVELOPER_CONTENT = (
    "You are Cardinal, an AI assistant with tools.\n"
    "Directives:\n"
    "- Use tool calls to fetch dynamic information or perform state changes.\n"
    "- Never answer from internal knowledge. Base responses on tool outputs.\n"
    "- For conversation or complex reasoning, forward to the 'llm' tool."
)


def generate_jsonl(
    manifests: list,
    single_rows: list,
    languages: list,
    multi_config: dict,
) -> list:
    tools_schema = build_tools_schema(manifests)
    records = []
    lang_codes = [lc for lc, _ in languages]

    def add_record(phrase: str, calls: list):
        call_contents = "\n".join(build_call_str(name, args) for name, args in calls)
        records.append({
            "messages": [
                {"role": "developer", "content": DEVELOPER_CONTENT},
                {"role": "user", "content": phrase},
                {"role": "assistant", "content": call_contents},
            ],
            "tools": tools_schema,
        })

    for text, tool_name, args in single_rows:
        add_record(text, [(tool_name, args)])

    for entry in multi_config.get("parallel", []):
        a, b, c, d, phrases = entry["tools"]
        for code in lang_codes:
            add_record(phrases.get(code, phrases.get("en", "")), [(a, b), (c, d)])

    for entry in multi_config.get("sequential", []):
        a, b, c, d, phrases = entry["tools"]
        for code in lang_codes:
            add_record(phrases.get(code, phrases.get("en", "")), [(a, b), (c, d)])

    for entry in multi_config.get("triple", []):
        a, b, c, d, e, f, phrases = entry["tools"]
        for code in lang_codes:
            add_record(phrases.get(code, phrases.get("en", "")), [(a, b), (c, d), (e, f)])

    for entry in multi_config.get("no_tool", []):
        queries = entry["query"]
        responses = entry["response"]
        for code in lang_codes:
            query = queries.get(code, queries.get("en", ""))
            response = responses.get(code, responses.get("en", ""))
            if not query or not response:
                continue
            records.append({
                "messages": [
                    {"role": "developer", "content": DEVELOPER_CONTENT},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
                "tools": tools_schema,
            })

    # Legacy alias for "irrelevant"
    for entry in multi_config.get("irrelevant", []):
        queries = entry["query"]
        responses = entry["response"]
        for code in lang_codes:
            query = queries.get(code, queries.get("en", ""))
            response = responses.get(code, responses.get("en", ""))
            if not query or not response:
                continue
            records.append({
                "messages": [
                    {"role": "developer", "content": DEVELOPER_CONTENT},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
                "tools": tools_schema,
            })

    for entry in multi_config.get("llm_sequential", []):
        a, b, c, d, phrases = entry["tools"]
        for code in lang_codes:
            add_record(phrases.get(code, phrases.get("en", "")), [(a, b), (c, d)])

    for entry in multi_config.get("llm_parallel", []):
        a, b, c, d, phrases = entry["tools"]
        for code in lang_codes:
            add_record(phrases.get(code, phrases.get("en", "")), [(a, b), (c, d)])

    random.shuffle(records)
    return records


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Generate FunctionGemma training data")
    parser.add_argument("--lang", help="Comma-separated language codes (default: all 30)")
    parser.add_argument("--templates", type=int, default=10, help="Max templates per combo (default: 10)")
    parser.add_argument("--output-dir", help="Output directory (default: script dir)")
    parser.add_argument("--manifests-dir", help="Manifests directory (default: ../../tools)")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(42)
    base = Path(__file__).parent
    out_dir = Path(args.output_dir) if args.output_dir else base
    manifests_dir = Path(args.manifests_dir) if args.manifests_dir else base.parent.parent / "tools"
    languages = filter_languages(args.lang)

    # Step 0: Combine manifests into config files
    from combine import combine as combine_tool
    combine_tool(manifests_dir, out_dir)

    print(f"Loading manifests from {manifests_dir}...")
    manifests = load_manifests(manifests_dir)
    if not manifests:
        print("ERROR: No manifests found"); sys.exit(1)
    print(f"Tools: {[m['name'] for m in manifests]}")
    print(f"Languages: {len(languages)} ({', '.join(lc for lc, _ in languages)})")

    templates = load_json(out_dir / "templates.json")
    print(f"Templates: {len(templates)} actions")

    payload_examples = load_json(out_dir / "payload_examples.json")

    single_rows = generate_single_records(manifests, templates, payload_examples, languages, args.templates)
    print(f"Single-call records: {len(single_rows)}")

    multi_config = load_json(out_dir / "multi_tool_config.json")
    jsonl_records = generate_jsonl(manifests, single_rows, languages, multi_config)
    jsonl_path = out_dir / "training_data.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in jsonl_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"JSONL: {len(jsonl_records)} records -> {jsonl_path}")

    print(f"\nDone! {len(jsonl_records)} JSONL records")


if __name__ == "__main__":
    main()
