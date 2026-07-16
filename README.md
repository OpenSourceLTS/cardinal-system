---
license: cc-by-4.0
tags:
  - gemma
  - functiongemma
  - function-calling
  - cardinal-system
  - system-tools
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

JSONL, one sample per line. Each sample has:

- `metadata`: `"train"` or `"eval"` (90/10 split)
- `tools`: Available function definitions (JSON Schema format) — subset of all 43 functions
- `messages`: Conversation with `developer` (system context), `user` (instruction), and `assistant` (tool call) roles

## Functions (43)

Grouped by source tool:

| Tool | Functions |
|------|-----------|
| **clock_calendar** | `get_time`, `get_date`, `get_datetime`, `get_day_of_week`, `get_timezone_info`, `get_moon_phase`, `get_season`, `list_alarms`, `list_timers`, `get_stopwatch_status`, `list_events`, `calculate_duration`, `calculate_time_until`, `calculate_time_since`, `calculate_date_offset`, `check_leap_year`, `set_alarm`, `set_timer`, `control_stopwatch`, `schedule_event`, `delete_alarm`, `delete_timer`, `delete_event` |
| **notes** | `list_notes`, `read_note`, `save_note`, `append_note`, `delete_note`, `replace_in_note`, `edit_note_line`, `rename_note`, `search_notes` |
| **libretranslate** | `translate_text`, `detect_language`, `list_languages` |
| **settings** | `set_setting`, `delete_setting`, `list_settings` |
| **llm** | `forward_to_ai` |

## Languages (30)

`ar`, `bn`, `zh`, `cs`, `nl`, `en`, `fr`, `de`, `el`, `he`, `hi`, `hu`, `id`, `it`, `ja`, `ko`, `mr`, `fa`, `pl`, `pt`, `ro`, `ru`, `es`, `sw`, `ta`, `te`, `th`, `tr`, `ur`, `vi`

## Statistics

| Statistic | Value |
|-----------|-------|
| Total samples | 8,490 |
| Training | 7,641 |
| Evaluation | 849 |
| Functions | 43 |
| Source tools | 5 |
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
