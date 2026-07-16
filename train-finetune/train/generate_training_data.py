"""Training Data Generator for FunctionGemma Fine-Tuning.
Generates training_data.jsonl in google/mobile-actions format
with specific function names and semantically meaningful parameter names.

Usage:
    python generate_training_data.py
    python generate_training_data.py --lang bn,en,hi --templates-per-fn 3
    python generate_training_data.py --output-dir /path/to/output
"""

import argparse
import json
import random
import re
import sys
from datetime import datetime, timedelta
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

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_EPOCH = datetime(2024, 1, 1)
_EPOCH_END = datetime(2027, 1, 1)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def discover_functions(manifests_dir: Path) -> list[dict]:
    functions = []
    for manifest_path in sorted(manifests_dir.glob("*/manifest.json")):
        data = load_json(manifest_path)
        name = data.get("name", manifest_path.parent.stem)
        func_dict = data.get("functions", {})
        for func_name, fn_def in func_dict.items():
            functions.append({
                "tool": name,
                "func_name": func_name,
                "description": fn_def.get("description", ""),
                "parameters": fn_def.get("parameters", {}),
                "required": fn_def.get("required", []),
                "templates": fn_def.get("templates", []),
                "examples": fn_def.get("examples", {}),
            })
    return functions


def load_multi_tool_config(manifests_dir: Path) -> dict:
    llm_manifest = manifests_dir / "llm" / "manifest.json"
    if llm_manifest.exists():
        data = load_json(llm_manifest)
        return data.get("multi_tool", {})
    return {}


def filter_languages(lang_filter: str) -> list:
    if not lang_filter:
        return LANGUAGES
    codes = [c.strip() for c in lang_filter.split(",")]
    lang_map = dict(LANGUAGES)
    return [(c, lang_map.get(c, c)) for c in codes if c]


def random_datetime():
    delta = _EPOCH_END - _EPOCH
    rand_secs = random.randint(0, int(delta.total_seconds()))
    return _EPOCH + timedelta(seconds=rand_secs)


def build_developer_content(dt: datetime) -> str:
    day_name = _DAY_NAMES[dt.weekday()]
    return (
        f"Current date and time given in YYYY-MM-DDTHH:MM:SS format: {dt.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"Day of week is {day_name}\n"
        f"You are a model that can do function calling with the following functions\n"
    )


def build_tools_schema(functions: list[dict]) -> list:
    tools = []
    for fn in functions:
        params_schema = fn["parameters"]
        properties = {}
        required = fn["required"]
        for pname, pdef in params_schema.items():
            prop = {"type": pdef.get("type", "STRING")}
            if "description" in pdef:
                prop["description"] = pdef["description"]
            if "enum" in pdef:
                prop["enum"] = pdef["enum"]
            properties[pname] = prop
        func_def = {
            "function": {
                "name": fn["func_name"],
                "description": fn["description"],
                "parameters": {
                    "type": "OBJECT",
                    "properties": properties,
                },
            }
        }
        if required:
            func_def["function"]["parameters"]["required"] = list(required)
        tools.append(func_def)
    return tools


def build_tool_calls(calls: list) -> list:
    result = []
    for name, args in calls:
        filtered = {k: v for k, v in args.items() if v is not None and v != ""}
        result.append({
            "function": {
                "name": name,
                "arguments": filtered,
            }
        })
    return result


def generate_single_records(
    functions: list[dict],
    languages: list,
    max_templates: int,
) -> list:
    rows = []
    for fn in functions:
        func_name = fn["func_name"]
        templates = fn["templates"]
        examples = fn["examples"]
        params = fn["parameters"]
        required = set(fn["required"])

        for lang_code, _ in languages:
            tmpls = templates if lang_code == "en" else templates

            for template in tmpls[:max_templates]:
                placeholders = [m.group(1) for m in re.finditer(r'\{(\w+)\}', template)]

                param_values = {}
                for pname in placeholders:
                    if pname in examples and examples[pname]:
                        clean_vals = [v for v in examples[pname] if v != ""]
                        if clean_vals:
                            param_values[pname] = random.choice(clean_vals)
                        else:
                            param_values[pname] = ""
                    else:
                        param_values[pname] = ""

                text = template
                for pname, pval in param_values.items():
                    text = text.replace("{" + pname + "}", pval)

                args = dict(param_values)
                for pname in list(args.keys()):
                    if pname not in required and not args[pname]:
                        del args[pname]

                rows.append([text, func_name, args])

    return rows


def generate_jsonl(
    functions: list[dict],
    single_rows: list,
    languages: list,
    multi_config: dict,
) -> list:
    tools_schema = build_tools_schema(functions)
    records = []
    lang_codes = [lc for lc, _ in languages]

    def shuffled_tools():
        return random.sample(tools_schema, len(tools_schema))

    def add_record(phrase: str, calls: list):
        dt = random_datetime()
        dev_content = build_developer_content(dt)
        tool_calls = build_tool_calls(calls)
        records.append({
            "metadata": "train",
            "tools": shuffled_tools(),
            "messages": [
                {"role": "developer", "content": dev_content},
                {"role": "user", "content": phrase},
                {"role": "assistant", "tool_calls": tool_calls},
            ],
        })

    for text, func_name, args in single_rows:
        add_record(text, [(func_name, args)])

    def process_multi_entry(tools_array):
        phrases = tools_array[-1] if tools_array else {}
        phrase = phrases.get("en", "") if isinstance(phrases, dict) else ""
        items = tools_array[:-1]
        calls = [(items[i], items[i + 1]) for i in range(0, len(items), 2)]
        return phrase, calls

    for entry in multi_config.get("parallel", []):
        phrase, calls = process_multi_entry(entry["tools"])
        for code in lang_codes:
            add_record(phrase, calls)

    for entry in multi_config.get("sequential", []):
        phrase, calls = process_multi_entry(entry["tools"])
        for code in lang_codes:
            add_record(phrase, calls)

    for entry in multi_config.get("triple", []):
        phrase, calls = process_multi_entry(entry["tools"])
        for code in lang_codes:
            add_record(phrase, calls)

    for entry in multi_config.get("no_tool", []):
        queries = entry.get("query", {})
        responses = entry.get("response", {})
        for code in lang_codes:
            query = queries.get(code, queries.get("en", ""))
            response = responses.get(code, responses.get("en", ""))
            if not query or not response:
                continue
            dt = random_datetime()
            dev_content = build_developer_content(dt)
            records.append({
                "metadata": "train",
                "tools": shuffled_tools(),
                "messages": [
                    {"role": "developer", "content": dev_content},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
            })

    for entry in multi_config.get("irrelevant", []):
        queries = entry.get("query", {})
        responses = entry.get("response", {})
        for code in lang_codes:
            query = queries.get(code, queries.get("en", ""))
            response = responses.get(code, responses.get("en", ""))
            if not query or not response:
                continue
            dt = random_datetime()
            dev_content = build_developer_content(dt)
            records.append({
                "metadata": "train",
                "tools": shuffled_tools(),
                "messages": [
                    {"role": "developer", "content": dev_content},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
            })

    random.shuffle(records)
    return records


def parse_args():
    parser = argparse.ArgumentParser(description="Generate FunctionGemma training data")
    parser.add_argument("--lang", help="Comma-separated language codes (default: all 30)")
    parser.add_argument("--templates-per-fn", type=int, default=12, help="Max templates per function (default: 12)")
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
    functions = discover_functions(manifests_dir)
    if not functions:
        print("ERROR: No functions found in manifests"); sys.exit(1)
    print(f"Functions: {len(functions)}")
    for fn in functions:
        print(f"  {fn['tool']}.{fn['func_name']}")

    print(f"Languages: {len(languages)} ({', '.join(lc for lc, _ in languages)})")

    single_rows = generate_single_records(functions, languages, args.templates_per_fn)
    print(f"Single-call records: {len(single_rows)}")

    multi_config = load_multi_tool_config(manifests_dir)
    multi_counts = {k: len(v) for k, v in multi_config.items()}
    print(f"Multi-tool config: {multi_counts}")

    jsonl_records = generate_jsonl(functions, single_rows, languages, multi_config)
    jsonl_path = out_dir / "training_data.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in jsonl_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"JSONL: {len(jsonl_records)} records -> {jsonl_path}")
    print(f"\nDone! {len(jsonl_records)} JSONL records")


if __name__ == "__main__":
    main()
