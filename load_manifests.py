import sys, json
from pathlib import Path

sys.path.insert(0, '.')
TOOLS_ROOT = Path(__file__).parent / 'tools'

# Quick diagnostic: loads manifest.json for a few tool names
# and prints their example count and first two examples.
# Useful for verifying manifest structure after edits.
for tool_name in ['memo', 'clock', 'chat', 'calendar']:
    path = TOOLS_ROOT / tool_name / 'manifest.json'
    if path.exists():
        print(f'{tool_name}:')
        with open(path, 'r') as f:
            data = json.load(f)
            print(f'  examples: {len(data.get("examples", []))}')
            for ex in data.get('examples', [])[:2]:
                print(f'    user: {ex.get("user", "")}')
                print(f'    assistant: {ex.get("assistant", "")}')
        print()
