---
license: cc-by-4.0
tags:
  - gemma
  - functiongemma
  - function-calling
  - android
  - system-tools
language:
- en
size_categories:
- 1K<n<10K
---

# Cardinal System: A Dataset for On-Device Function Calling

The dataset contains conversational traces designed to train lightweight models (such as FunctionGemma 270M) to translate natural language instructions into executable function calls for system tools.

## Dataset Format

The dataset is provided in JSONL format. Each line represents a data sample. The
dataset is pre-split into training and evaluation sets. This distinction is
denoted by the `metadata` field within each sample.

Each JSON object in the file contains the following fields:

- `metadata`: Contains metadata about the data sample for splitting. The value is either "train" or "eval".
- `tools`: A list of available tools (functions) that the model can call. Each tool has:
    - `function`: An object describing the function:
        - `name`: The name of the function.
        - `description`: A description of what the function does.
        - `parameters`: An object describing the parameters the function accepts, following a JSON Schema like structure.
- `messages`: A list of messages, usually containing system context, user input, and the expected function call.
    - `role`: Typically "developer" for system context, "user" for the input command, and "assistant" for the function call.
    - `content`: The natural language input or system context.
    - `tool_calls`: (For assistant role) A list of tool calls the model should predict. Each tool call has:
        - `function`: An object specifying the function to call:
            - `name`: The name of the function.
            - `arguments`: A JSON object containing the arguments for the function.

## Tools

The dataset covers 39 system-level tools across multiple domains:

| Category | Tools |
|----------|-------|
| **Clock & Time** | `get_time`, `get_date`, `get_datetime`, `set_timer`, `delete_timer`, `list_timers`, `set_alarm`, `delete_alarm`, `list_alarms`, `get_timezone_info`, `get_moon_phase`, `get_season`, `calculate_time_until`, `calculate_time_since`, `calculate_duration`, `calculate_date_offset`, `check_leap_year`, `get_day_of_week`, `control_stopwatch`, `get_stopwatch_status` |
| **Notes** | `save_note`, `read_note`, `append_note`, `edit_note_line`, `replace_in_note`, `rename_note`, `delete_note`, `search_notes`, `list_notes` |
| **Translation** | `translate_text`, `detect_language`, `list_languages` |
| **Settings** | `set_setting`, `delete_setting`, `list_settings` |
| **Events** | `schedule_event`, `delete_event`, `list_events` |
| **AI** | `forward_to_ai` |

## Dataset Statistics

| Statistic | Value |
|-----------|-------|
| Total samples | 8,490 |
| Training samples | 7,641 |
| Evaluation samples | 849 |
| Unique tools | 39 |
| Format | JSONL |

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("SkGufranAhmed/functiongemma-finetune-dataset")
```

## License

This dataset is licensed under CC-BY-4.0.

## Uploading

Uploaded to [Hugging Face Datasets](https://huggingface.co/datasets/SkGufranAhmed/functiongemma-finetune-dataset). Upload via:
```python
from huggingface_hub import HfApi
api = HfApi()
api.upload_file(path_or_fileobj="training_data.jsonl", path_in_repo="training_data.jsonl",
                repo_id="SkGufranAhmed/functiongemma-finetune-dataset", repo_type="dataset")
```
