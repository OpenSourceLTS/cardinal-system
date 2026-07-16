"""Combine training data from tool manifests into centralized config files.

Usage:
    python combine.py
    python combine.py --manifests-dir <path>
    python combine.py --output-dir <path>
"""
import argparse, json, sys
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def combine(manifests_dir, output_dir):
    """Read all manifests and write combined config files for the new format."""
    templates = {}
    payload_examples = {}
    all_functions = {}
    multi_tool = None

    for mp in sorted(manifests_dir.glob("*/manifest.json")):
        data = load_json(mp)
        name = data.get("name", mp.parent.stem)
        functions = data.get("functions", {})

        fn_list = []
        for func_name, fn_def in functions.items():
            fn_list.append(func_name)
            # Collect templates per function
            fn_templates = fn_def.get("templates", [])
            if fn_templates:
                templates[func_name] = fn_templates
            # Collect examples per function
            fn_examples = fn_def.get("examples", {})
            if fn_examples:
                payload_examples[func_name] = fn_examples

        all_functions[name] = fn_list

        if name == "llm" and "multi_tool" in data:
            multi_tool = data["multi_tool"]

    if not templates:
        print("ERROR: No templates found in any manifest"); sys.exit(1)
    if multi_tool is None:
        print("ERROR: No multi_tool found in llm manifest"); sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    json.dump(templates, open(output_dir / "templates.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(payload_examples, open(output_dir / "payload_examples.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(multi_tool, open(output_dir / "multi_tool_config.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    total = sum(len(v) for v in multi_tool.values())
    return len(templates), len(payload_examples), total


def main():
    parser = argparse.ArgumentParser(description="Combine training data from manifests")
    parser.add_argument("--manifests-dir", help="Manifests directory (default: ../../tools)")
    parser.add_argument("--output-dir", help="Output directory (default: script dir)")
    args = parser.parse_args()

    base = Path(__file__).parent
    out_dir = Path(args.output_dir) if args.output_dir else base
    manifests_dir = Path(args.manifests_dir) if args.manifests_dir else base.parent.parent / "tools"

    t_count, p_count, m_total = combine(manifests_dir, out_dir)
    print(f"templates.json: {t_count} functions")
    print(f"payload_examples.json: {p_count} functions")
    print(f"multi_tool_config.json: {m_total} entries")
    print(f"\nDone! Files written to {out_dir}")


if __name__ == "__main__":
    main()
