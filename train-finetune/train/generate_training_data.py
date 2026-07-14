"""Training Data Generator for FunctionGemma Fine-Tuning.

Reads manifests and config files to generate:
1. training_data.csv -- Single tool calls for Tuning Lab (3 cols, no header)
2. training_data.jsonl -- Single + multi tool calls (standard FunctionGemma format)

Usage:
    python generate_training_data.py
    python generate_training_data.py --lang bn,en,hi --templates 3
    python generate_training_data.py --output-dir /path/to/output
"""

import argparse
import csv
import json
import random
import sys
from datetime import datetime
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
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manifests(manifests_dir: Path) -> list:
    manifests = []
    for manifest_path in sorted(manifests_dir.glob("*/manifest.json")):
        data = load_json(manifest_path)
        vp = data.get("manifest", {}).get("v@p", {})
        manifests.append({
            "name": data.get("name", manifest_path.parent.stem),
            "description": data.get("description", ""),
            "actions": data.get("actions", []),
            "v@p": vp,
            "schema": data.get("schema"),
        })
    return manifests


def filter_languages(lang_filter: str) -> list:
    if not lang_filter:
        return LANGUAGES
    codes = [c.strip() for c in lang_filter.split(",")]
    lang_map = dict(LANGUAGES)
    return [(c, lang_map.get(c, c)) for c in codes if c]


def random_datestr() -> tuple:
    year = random.randint(2024, 2026)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    dt = datetime(year, month, day, hour, minute, second)
    return dt.strftime("%Y-%m-%dT%H:%M:%S"), DAYS[dt.weekday()]


def resolve_payload(examples: dict, tool_name: str, target: str, default: str = "value") -> str:
    val = examples.get(tool_name, {}).get(target, default)
    if isinstance(val, list):
        return random.choice(val)
    return val


def generate_csv(
    manifests: list,
    templates: dict,
    payload_examples: dict,
    languages: list,
    max_templates: int,
) -> tuple:
    rows = []
    warnings = 0

    for manifest in manifests:
        tool_name = manifest["name"]
        vp = manifest["v@p"]

        for action, targets in vp.items():
            action_templates = templates.get(action, templates.get("get", {}))

            for target_entry in targets:
                target = target_entry[0] if target_entry else ""

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

                        tool_args = {"action": action}
                        if target:
                            tool_args["target"] = target
                        pl = resolve_payload(payload_examples, tool_name, target)
                        if pl:
                            tool_args["payload"] = pl

                        rows.append([text, tool_name, json.dumps(tool_args, ensure_ascii=False)])

    if warnings:
        print(f"  Warnings: {warnings} missing language templates (fell back to en)")

    return len(rows), rows


def generate_jsonl(
    manifests: list,
    csv_rows: list,
    languages: list,
    multi_config: dict,
) -> list:
    tool_schemas = [m["schema"] for m in manifests]
    records = []
    lang_codes = [lc for lc, _ in languages]

    def add_record(phrase: str, calls: list):
        dt_str, day_str = random_datestr()
        dev_msg = (
            f"Current date and time given in YYYY-MM-DDTHH:MM:SS format: {dt_str}\n"
            f"Day of week is {day_str}\n"
            "You are a model that can do function calling with the following functions\n"
        )
        records.append({
            "metadata": "train",
            "messages": [
                {"role": "developer", "content": dev_msg, "tool_calls": None},
                {"role": "user", "content": phrase},
                {"role": "assistant", "content": None, "tool_calls": [
                    {
                        "id": f"call_{i+1}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                    }
                    for i, (name, args) in enumerate(calls)
                ]},
            ],
            "tools": tool_schemas,
        })

    for text, tool_name, args_json in csv_rows:
        add_record(text, [(tool_name, json.loads(args_json))])

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

    for entry in multi_config.get("irrelevant", []):
        queries = entry["query"]
        responses = entry["response"]
        for code in lang_codes:
            query = queries.get(code, queries.get("en", ""))
            response = responses.get(code, responses.get("en", ""))
            if not query or not response:
                continue
            dt_str, day_str = random_datestr()
            dev_msg = (
                f"Current date and time given in YYYY-MM-DDTHH:MM:SS format: {dt_str}\n"
                f"Day of week is {day_str}\n"
                "You are a model that can do function calling with the following functions\n"
            )
            records.append({
                "metadata": "train",
                "messages": [
                    {"role": "developer", "content": dev_msg, "tool_calls": None},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
                "tools": tool_schemas,
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


def parse_args():
    parser = argparse.ArgumentParser(description="Generate FunctionGemma training data")
    parser.add_argument("--lang", help="Comma-separated language codes (default: all 30)")
    parser.add_argument("--templates", type=int, default=5, help="Max templates per combo (default: 5)")
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

    print(f"Loading manifests from {manifests_dir}...")
    manifests = load_manifests(manifests_dir)
    if not manifests:
        print("ERROR: No manifests found"); sys.exit(1)
    print(f"Tools: {[m['name'] for m in manifests]}")
    print(f"Languages: {len(languages)} ({', '.join(lc for lc, _ in languages)})")

    templates = load_json(base / "templates.json")
    print(f"Templates: {len(templates)} actions")

    payload_examples = load_json(base / "payload_examples.json")

    csv_path = out_dir / "training_data.csv"
    csv_count, csv_rows = generate_csv(manifests, templates, payload_examples, languages, args.templates)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(csv_rows)
    print(f"CSV: {csv_count} rows -> {csv_path}")

    multi_config = load_json(base / "multi_tool_config.json")
    jsonl_records = generate_jsonl(manifests, csv_rows, languages, multi_config)
    jsonl_path = out_dir / "training_data.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in jsonl_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"JSONL: {len(jsonl_records)} records -> {jsonl_path}")

    print(f"\nDone! {csv_count} CSV rows, {len(jsonl_records)} JSONL records")


if __name__ == "__main__":
    main()
