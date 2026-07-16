---
license: cc-by-4.0
tags:
  - gemma
  - functiongemma
  - function-calling
  - cardinal-system
language:
- en
- ar
- bn
- zh
- cs
- nl
- fr
- de
- el
- he
- hi
- hu
- id
- it
- ja
- ko
- mr
- fa
- pl
- pt
- ro
- ru
- es
- sw
- ta
- te
- th
- tr
- ur
- vi
size_categories:
- 1K<n<10K
---

# FunctionGemma Finetune Dataset — Cardinal System Tools

Conversational traces for training lightweight models (FunctionGemma 270M) to translate natural language into executable function calls for system tools: clock, calendar, notes, translation, settings, and AI routing.

## Dataset Format

JSONL, one sample per line. Format matches `google/mobile-actions` exactly.

Each sample has:

- `metadata`: `"train"` or `"eval"` (90/10 split)
- `tools`: A list of 7 available functions (random subset) with JSON Schema definitions
- `messages`: Conversation with `user` (instruction) and `assistant` (tool call) roles

### Example

```json
{
  "metadata": "train",
  "tools": [
    {"function": {"name": "set_timer", "description": "...", "parameters": {...}}},
    ...
  ],
  "messages": [
    {"role": "user", "content": "Set a timer for 10 minutes called pasta"},
    {"role": "assistant", "tool_calls": [
      {
        "id": "call_a1b2c3d4",
        "type": "function",
        "function": {
          "name": "set_timer",
          "arguments": "{\"duration\": \"10 minutes\", \"label\": \"pasta\"}"
        }
      }
    ]}
  ]
}
```

## Functions (39)

| Tool | Functions |
|------|-----------|
| **clock_calendar** (23) | `get_time`, `get_date`, `get_datetime`, `get_day_of_week`, `get_timezone_info`, `get_moon_phase`, `get_season`, `list_alarms`, `list_timers`, `get_stopwatch_status`, `list_events`, `calculate_duration`, `calculate_time_until`, `calculate_time_since`, `calculate_date_offset`, `check_leap_year`, `set_alarm`, `set_timer`, `control_stopwatch`, `schedule_event`, `delete_alarm`, `delete_timer`, `delete_event` |
| **notes** (9) | `list_notes`, `read_note`, `save_note`, `append_note`, `delete_note`, `replace_in_note`, `edit_note_line`, `rename_note`, `search_notes` |
| **libretranslate** (3) | `translate_text`, `detect_language`, `list_languages` |
| **settings** (3) | `set_setting`, `delete_setting`, `list_settings` |
| **llm** (1) | `forward_to_ai` |

## Record Types

| Type | Count | Description |
|------|-------|-------------|
| Single-call | 7,170 (66.7%) | One function call per assistant message |
| Multi-call | 3,576 (33.3%) | Multiple function calls in one assistant message |

Ratio matches `google/mobile-actions` exactly (33.3% multi-call, 66.7% single-call).

## Languages (30)

`ar`, `bn`, `zh`, `cs`, `nl`, `en`, `fr`, `de`, `el`, `he`, `hi`, `hu`, `id`, `it`, `ja`, `ko`, `mr`, `fa`, `pl`, `pt`, `ro`, `ru`, `es`, `sw`, `ta`, `te`, `th`, `tr`, `ur`, `vi`

## Statistics

| Statistic | Value |
|-----------|-------|
| Total samples | 10,746 |
| Training | 9,671 |
| Evaluation | 1,075 |
| Functions | 39 |
| Tools per sample | 7 |
| Languages | 30 |

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("SkGufranAhmed/functiongemma-finetune-dataset")
train = dataset["train"]
eval_split = dataset["eval"]
```

## License

CC-BY-4.0
