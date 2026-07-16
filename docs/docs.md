# Cardinal System v0.0.2-alpha — Developer Documentation

Welcome to the Cardinal System. This documentation covers the architectural philosophy, execution engine, complete tool reference, API reference, and SDK tool creation guide.

---

## Table of Contents

- [Part 1: System Architecture & Philosophy](#part-1-system-architecture--philosophy)
- [Part 2: Project Structure](#part-2-project-structure)
- [Part 3: Core Framework](#part-3-core-framework)
- [Part 4: Registered Tools](#part-4-registered-tools)
- [Part 5: Web UI](#part-5-web-ui)
- [Part 6: API Reference](#part-6-api-reference)
- [Part 7: Running](#part-7-running)
- [Part 8: SDK Tool Creation Guide](#part-8-sdk-tool-creation-guide)
- [Part 9: Full SDK Example](#part-9-full-sdk-example)
- [Part 10: Training Data Pipeline](#part-10-training-data-pipeline)
  - [10.1 Data Ownership](#101-data-ownership)
  - [10.2 Pipeline](#102-pipeline)
  - [10.3 Record Generation](#103-record-generation)
  - [10.4 Adding a New Language](#104-adding-a-new-language)
  - [10.5 Fine-Tuning](#105-fine-tuning)

---

## Part 1: System Architecture & Philosophy

The Cardinal System is built on a principle called **Cognitive Offloading**. Standard AI agents try to make the LLM do everything — reasoning, formatting, API calling, state management. This fails on small models (<1B parameters).

Cardinal offloads 100% of the logic to a deterministic Python engine. The LLM is stripped of its "thinking" responsibilities and acts solely as a **Natural Language to Tool Call Transducer**.

### 1.1 The Execution Lifecycle (MCP-based)

Cardinal uses LM Studio's native API with MCP (Model Context Protocol) integration for single-pass tool execution:

```
User Message
    │
    ▼
LM Studio (/api/v1/chat + integrations: ["mcp/cardinal-system"])
    │
    ▼
LLM decides: call tool or respond directly
    │
    ▼
MCP Tool Execution (core/mcp_server.py → Router → BaseTool.execute())
    │
    ▼
Result injected back into LLM context (single pass)
    │
    ▼
Final Response
```

1. **User Message** is sent to LM Studio's `/api/v1/chat` endpoint with `integrations: ["mcp/cardinal-system"]`.
2. **LM Studio** loads the model, connects to the MCP server (`core/mcp_server.py`), lists available tools, and injects them into the model's context.
3. **LLM Decides** whether to call one of the registered MCP tools (`clock_calendar`, `notes`, `libretranslate`, `settings`) or respond directly for conversational queries.
4. **MCP Tool Execution** — LM Studio forwards the tool call to the MCP server, which routes it to the correct tool handler via the Router.
5. **Result Injection** — The tool result flows back through LM Studio directly into the LLM's generation context in a single pass.
6. **Final Response** — The LLM continues generating with the real tool result already in its context window.

### 1.2 The Command Grammar

All tool calls use three structured fields:

| Field    | Description                          | Example              |
|----------|--------------------------------------|----------------------|
| `action` | Action to perform                    | `get`, `translate`   |
| `target` | Primary subject / resource           | `time`, `bn`         |
| `payload`| Data or parameters                   | `Asia/Dhaka`, `Hello world \| en` |

These map onto named MCP functions (e.g., `get_time`, `translate_text`) which the MCP server resolves back to `(tool, action, target, payload)` via `resolve_function_call()`.

When expressed as a human-readable shorthand:

```
tool(action)@{target}|{payload}
```

Examples:
```
clock_calendar(get)@time|Asia/Dhaka
notes(save)@groceries|Milk, eggs, bread
libretranslate(translate)@bn|"Hello world | en"
```

In the current MCP implementation, these are exposed as individual named functions (e.g., `get_time`, `save_note`, `translate_text`) rather than a single tool with verb/target/payload fields. The Router internally translates function calls back to the `(tool, action, target, payload)` tuple for execution.

### 1.3 Safety & Risk Tiers

Every tool must declare a `RiskTier` in its `manifest.json`:

| Tier          | Description                              | Examples              |
|---------------|------------------------------------------|-----------------------|
| `SAFE`        | Read-only operations, no side effects    | Clock, calendar       |
| `STATEFUL`    | Modifies local user data                 | Notes, settings       |
| `NETWORK`     | Sends data externally                    | Translation           |
| `DESTRUCTIVE` | Deletes data or executes arbitrary code  | (none currently)      |

---

## Part 2: Project Structure

```
cardinalsystem/
├── main.py                     # Entry point: CLI or web server
├── requirements.txt            # Python dependencies
├── mcp.json                    # LM Studio MCP server configuration
├── core/                       # Engine & framework
│   ├── base_tool.py            # BaseTool, CommandResult, ExecutionContext
│   ├── manifest.py             # ToolManifest, RiskTier, tool discovery
│   ├── engine.py               # CardinalSystemEngine — LM Studio native API client
│   ├── parser.py               # CommandNode dataclass
│   ├── router.py               # Routes parsed commands to tools
│   ├── mcp_server.py           # MCP server over stdio — wraps all tools
│   └── history.py              # Conversation history management
├── ui/                         # SvelteKit frontend + Flask server
│   ├── web_server.py           # Flask server (HTTP API + static UI)
│   ├── package.json            # Node dependencies
│   ├── svelte.config.js        # SvelteKit adapter-static config
│   ├── vite.config.js          # Vite + Tailwind CSS + API proxy
│   ├── src/                    # SvelteKit source
│   │   ├── app.html            # HTML shell
│   │   ├── app.css             # Tailwind import
│   │   ├── routes/             # Page routes
│   │   └── lib/components/     # Reusable Svelte components
│   ├── build/                  # Built output (generated, gitignored)
│   └── node_modules/           # (gitignored)
├── tools/                      # SDK tools (one subdirectory each)
│   ├── clock_and_calendar/     # Time, date, moon, calendars, alarms, timers
│   ├── notes/                  # Persistent markdown notes with line editing
│   ├── settings/               # User preferences
│   ├── libretranslate/         # Self-hosted translation (argos-translate)
│   └── llm/                    # Forwards user input to the main AI model
├── train-finetune/             # Training data & fine-tuning pipeline
│   ├── train/
│   │   ├── generate_training_data.py  # Generates FunctionGemma training JSONL
│   │   ├── combine.py                 # (legacy) Extracts training data from manifests
│   │   ├── templates.json             # (legacy, generated by combine.py)
│   │   ├── payload_examples.json      # (legacy, generated by combine.py)
│   │   ├── multi_tool_config.json     # (legacy, generated by combine.py)
│   │   ├── dataset.jsonl              # Training data in Gemini multi-turn format
│   │   └── training_data.jsonl        # Final FunctionGemma-format conversation records
│   └── finetune/
│       ├── colab_finetune.ipynb       # Colab notebook for FunctionGemma fine-tuning
│       └── functiongemma-270m-it.zip  # Base model download (gitignored)
├── memory/                     # Persistent data storage
│   ├── clock_and_calendar.json # Timezone, alarms, timers, stopwatch, events
│   ├── notes/                  # Markdown note files (.md)
│   ├── history/                # Session conversation history (JSON)
│   └── settings.md             # User preferences (key: value format)
├── cli/                        # CLI interface helpers
│   ├── handler.py              # Terminal rendering, colors, history display
│   └── main.py                 # CLI entry point
├── docs/
│   └── docs.md                 # This file
└── venv/                       # Python virtual environment (gitignored)
```

---

## Part 3: Core Framework

### 3.1 BaseTool (`core/base_tool.py`)

The abstract base class every tool must subclass.

```python
class BaseTool(ABC):
    @property
    @abstractmethod
    def manifest(self) -> ToolManifest: ...

    @abstractmethod
    def execute(self, action: str, target: str, payload: Optional[str],
                metadata: dict, ctx: ExecutionContext) -> CommandResult: ...

    def validate(self, action, target, payload, metadata) -> Optional[str]:
        return None  # Override to block calls with an error string
```

**CommandResult** — standard result wrapper:
```python
CommandResult.ok(value)       # success=True
CommandResult.fail(msg)       # success=False + error message
```

Fields: `success`, `value`, `error`, `tool`, `action`, `target`

**ExecutionContext** — shared state across a pipeline of tool calls:
```python
ctx.memo       # dict — shared working memory across commands
ctx.results    # list[CommandResult] — results from previous steps
ctx.timezone   # str — user timezone (default "UTC")
ctx.resolve_ref(value, results)  # Resolves $prev, $1..$N, memo:// references
```

### 3.2 Manifest (`core/manifest.py`)

**ToolManifest** dataclass:
```python
ToolManifest(
    name="clock_calendar",
    description="Time, date, moon, ...",
    actions=["get", "set", "delete"],
    target_hint="time, date, moon, ...",
    payload_hint="value",
    functions={"get_time": {...}, ...},  # Named functions with schemas
    risk_tier=RiskTier.SAFE,
    requires_confirmation=False,
)
```

Each function in the `functions` dict has: `description`, `parameters` (JSON Schema), `required`, `action`, `target`, `payload_expr`, `templates`, and `examples`.

**Tool discovery** — automatic from filesystem:
```python
discover_tools()                # Returns list of {name, description, functions} from tools/*/manifest.json
load_manifest(name)             # Returns raw JSON dict for a specific tool
load_tool_class(name)           # Dynamically imports the BaseTool subclass
tool_dir(name)                  # Maps tool name to directory name (e.g. "clock_calendar" → "clock_and_calendar")
get_function_registry()         # Returns flat dict of all functions across all tools
resolve_function_call(name, arguments)  # Maps function name + args → (tool, action, target, payload)
get_valid_targets(tool, action) # Returns literal target values for a tool+action
```

Convention: `tools/{dir}/{tool_name}_tool.py` contains a class inheriting `BaseTool`.

Functions are auto-discovered via `get_function_registry()` → each function from each tool's manifest is available for MCP registration. The Router uses `resolve_function_call()` to map an incoming function name + arguments back to the `(tool, action, target, payload)` tuple needed for internal execution.

### 3.3 Router (`core/router.py`)

Routes tool calls through a 6-step validation pipeline:

1. **Function resolved** — `resolve_function_call()` maps function name + args to a `(tool, action, target, payload)` tuple
2. **Tool exists** — checks `self._tools` registry
3. **Action valid** — checks against the tool's `manifest.actions`
4. **Target valid** — checks against `get_valid_targets()` when targets are literal strings
5. **Confirmation** — required for flagged commands
6. **Execute** — calls `tool.execute(action, target, payload, meta, ctx)`

On failure, returns a manifest format hint so the AI can self-correct.

**User input translation:**
```python
router.route_user_input(text)  # Returns (translated_to_english, original_text)
```

### 3.4 Parser (`core/parser.py`)

**CommandNode** dataclass — a single parsed tool invocation:

```python
CommandNode(
    action="get",            # Action to perform (e.g., "get", "translate", "save")
    tool="clock_calendar",   # Target tool name (e.g., "clock_calendar", "notes")
    target="time",           # Primary resource (e.g., "time", "groceries")
    payload="Asia/Dhaka",    # Data or parameters (e.g., "Asia/Dhaka", "milk -> oat milk")
    meta={},                 # Extra metadata key-value pairs
    requires_confirm=False,  # If True, user must approve before execution
    deps=[],                 # Indices of prerequisite nodes (for DAG execution)
)
```

### 3.5 History (`core/history.py`)

Conversation history stored as JSON in `memory/history/{session_id}.json`.

| Function           | Description                                    |
|--------------------|------------------------------------------------|
| `list_sessions()`  | Returns `[{id, message_count, preview}]`       |
| `create(id)`       | Creates a new session file                     |
| `delete(id)`       | Deletes a session file                         |
| `load(id)`         | Returns full history list                      |
| `save(id, history)`| Overwrites session history                     |
| `append(id, ...)`  | Appends one turn (caps at `MAX_TURNS = 20`)    |
| `format_context()` | Formats history as a string for LLM context    |

History entry fields:
- `role` — `"user"`, `"assistant"`, or `"tool"`
- `content` — always in English (for AI context)
- `user_original` — the user's original input (pre-translation)
- `translated_response` — assistant reply translated to `spoken_lang`
- `tool_name` / `tool_args` — tool call metadata

### 3.6 MCP Server (`core/mcp_server.py`)

Runs as a stdio subprocess managed by LM Studio. Implements JSON-RPC 2.0 MCP protocol.

**Protocol version:** MCP 1.0.0
**Server name:** `cardinal_system_mcp`
**Server version:** `0.0.1`

**Handled methods:**
| Method                    | Description                              |
|---------------------------|------------------------------------------|
| `initialize`              | Handshake, returns capabilities          |
| `tools/list`              | Returns all 43 registered function definitions |
| `tools/call`              | Executes a single tool call (resolved via `resolve_function_call()`) |
| `notifications/initialized` | Ignored (no-op)                        |
| `notifications/cancelled` | Ignored (no-op)                          |

**Batch execution:** JSON-RPC arrays are processed in parallel using a thread pool (4 workers).

**Function resolution:** When a `tools/call` request arrives with `name: "set_alarm"` and `arguments: {time: "07:00", label: "Wake up"}`, the server calls `resolve_function_call("set_alarm", arguments)` which looks up the function in the registry and returns the `(tool="clock_calendar", action="set", target="alarm", payload="07:00 Wake up")` tuple for internal execution.

**Tool definition format** (each function is a named tool sent to LM Studio):
```json
{
  "name": "get_time",
  "description": "Get the current time",
  "inputSchema": {
    "type": "object",
    "properties": {
      "timezone": { "type": "string", "description": "Optional timezone override (e.g., Asia/Dhaka, America/New_York)" }
    },
    "required": []
  }
}
```

The MCP server registers **43 individual named functions** (not 4 tool groups). Function names are snake_case and include the tool name (e.g., `set_alarm`, `save_note`, `translate_text`). LM Studio lists these as separate callable tools the model can invoke.

### 3.7 Engine (`core/engine.py`)

`CardinalSystemEngine` — LM Studio native API client.

**Configuration (read from `memory/settings.md`):**

| Setting | Default | Purpose |
|---------|---------|---------|
| `fc_base_url` | `http://localhost:1234` | LM Studio URL for function-calling model |
| `fc_api_key` | `(auto-generated)` | LM Studio API key |
| `fc_model` | `functiongemma-finetuned@f16` | Function-calling model name |
| `forward_base_url` | `http://localhost:1235` | Forward LLM URL (for `forward_to_ai`) |
| `forward_api_key` | `(auto-generated)` | Forward LLM API key |
| `forward_model` | `qwen3-0.6b-heretic-abliterated-uncensored` | Forward LLM model name |

**System prompt** — auto-generated from all registered functions at startup:
```
Current date and time given in YYYY-MM-DDTHH:MM:SS format: {now}
Day of week is {dow}
You are a model that can do function calling with the following functions
```

The system prompt includes the current datetime, then lists all 43 available functions by name and schema. LM Studio injects these as OpenAI-compatible `tools` in the API request, and the model responds with function calls in Gemma's native function-calling format (`<start_function_call>call:funcName{...}<end_function_call>`).

**Request flow:**
1. Prepends conversation history (if session exists)
2. Sends to LM Studio with `integrations: ["mcp/cardinal-system"]`
3. Parses output items into `texts` and `tool_results`
4. Returns structured response dict

### 3.8 Canonical Verbs

Every tool action must come from this canonical list. New tools should prefer existing actions for consistency.

`append`, `approve`, `archive`, `ask`, `block`, `bookmark`, `branch`, `calculate`, `change`, `cancel`, `check`, `clear`, `comment`, `commit`, `complete`, `compress`, `convert`, `copy`, `create`, `decline`, `decrypt`, `delete`, `deny`, `deploy`, `directions`, `disable`, `dismiss`, `enable`, `embed`, `encrypt`, `exec`, `extract`, `fetch`, `follow`, `forecast`, `forward`, `generate`, `get`, `grant`, `grab`, `like`, `list`, `log`, `mention`, `merge`, `move`, `mute`, `navigate`, `pair`, `paste`, `pause`, `pin`, `place`, `play`, `post`, `predict`, `publish`, `pull`, `push`, `query`, `queue`, `react`, `read`, `release`, `remind`, `remove`, `rename`, `reply`, `report`, `reschedule`, `reset`, `restore`, `revoke`, `rollback`, `run`, `say`, `schedule`, `search`, `send`, `set`, `save`, `share`, `sort`, `stop`, `stream`, `subscribe`, `sync`, `toggle`, `translate`, `train`, `unblock`, `uncheck`, `unfollow`, `unmute`, `unpin`, `unsubscribe`, `update`, `upload`, `write`

Each tool defines its own subset in `manifest.json` under `"actions"`. The Router validates against per-tool actions, not this master list.

---

## Part 4: Registered Tools

The MCP server exposes **43 named functions** grouped into 5 tool classes. Each function has its own JSON Schema and is registered as an independent callable tool with LM Studio.

### 4.1 ClockCalendarTool (`tools/clock_and_calendar/`)

Time, moon phase, season, timezone, date, day-of-week, date calculations, alarms, timers, stopwatch, and event scheduling.

| Field | Value |
|---|---|
| Tool name | `clock_calendar` |
| Actions | `get`, `set`, `delete` |
| Risk Tier | SAFE |
| Registered functions | 23 |

**GET functions (17):**

| Function | Parameters | Description |
|----------|------------|-------------|
| `get_time` | `timezone` (opt) | Current time |
| `get_date` | `timezone` (opt) | Current date |
| `get_datetime` | `timezone` (opt) | Current date and time |
| `get_day_of_week` | `date` (opt) | Day of week for a date |
| `get_timezone_info` | — | User's configured timezone |
| `get_moon_phase` | `date` (opt) | Current moon phase |
| `get_season` | `location` (opt) | Current season |
| `list_alarms` | — | List all alarms |
| `list_timers` | — | List all timers |
| `get_stopwatch_status` | — | Stopwatch state |
| `list_events` | — | List scheduled events |
| `calculate_duration` | `start_date`, `end_date`, `unit` (opt) | Duration between two dates |
| `calculate_time_until` | `target_time` | Time until target |
| `calculate_time_since` | `past_time` | Time since past |
| `calculate_date_offset` | `date`, `offset` (opt) | Date +/- days |
| `check_leap_year` | `year` (opt) | Leap year check |

**SET functions (4):**

| Function | Parameters | Description |
|----------|------------|-------------|
| `set_alarm` | `time`, `label` (opt) | Set an alarm |
| `set_timer` | `duration`, `label` (opt) | Set countdown timer |
| `control_stopwatch` | `action` (start/stop/reset) | Control stopwatch |
| `schedule_event` | `datetime`, `title` | Schedule event |

**DELETE functions (3):**

| Function | Parameters | Description |
|----------|------------|-------------|
| `delete_alarm` | `id` | Remove alarm by ID |
| `delete_timer` | `id` | Remove timer by ID |
| `delete_event` | `id` | Remove event by ID |

---

### 4.2 NotesTool (`tools/notes/`)

CRUD for `.md` notes saved in `memory/notes/`. Supports line-level editing, timestamps, and find/replace.

| Field | Value |
|---|---|
| Tool name | `notes` |
| Actions | `list`, `read`, `save`, `append`, `delete`, `change`, `rename`, `search` |
| Risk Tier | STATEFUL |
| Registered functions | 9 |

| Function | Parameters | Description |
|----------|------------|-------------|
| `list_notes` | — | List all note filenames |
| `read_note` | `filename`, `lines` (opt) | Read note or specific lines |
| `save_note` | `filename`, `content` | Create/overwrite note |
| `append_note` | `filename`, `content` | Append to end of note |
| `delete_note` | `filename` | Delete whole file |
| `replace_in_note` | `filename`, `pattern`, `replacement` | Find and replace |
| `edit_note_line` | `filename`, `line_number`, `content` | Replace or insert a line |
| `rename_note` | `filename`, `new_filename` | Rename note |
| `search_notes` | `keyword`, `filename` (opt) | Search within file or all notes |

---

### 4.3 SettingsTool (`tools/settings/`)

User preferences stored in `memory/settings.md`.

| Field | Value |
|---|---|
| Tool name | `settings` |
| Actions | `set`, `delete`, `get` |
| Risk Tier | STATEFUL |
| Registered functions | 3 |

**Known settings:**

| Key | Example | Description |
|-----|---------|-------------|
| `timezone` | `Asia/Dhaka` | User timezone (IANA, offset, city, or country) |
| `time_format` | `12h` or `24h` | Time display format |
| `spoken_lang` | `bn` | TTS + display translation language |
| `tone` | `casual` | Response tone |
| `name` | `Bob` | User's name |

| Function | Parameters | Description |
|----------|------------|-------------|
| `set_setting` | `name`, `value` | Set any key-value pair |
| `delete_setting` | `name` | Delete a setting |
| `list_settings` | — | List all settings |

---

### 4.4 LibreTranslateTool (`tools/libretranslate/`)

Self-hosted machine translation using argos-translate. Supports 50 languages.

| Field | Value |
|---|---|
| Tool name | `libretranslate` |
| Actions | `translate`, `detect`, `list` |
| Risk Tier | NETWORK |
| Registered functions | 3 |

**Available language codes (50):**

`ar`, `az`, `bg`, `bn`, `ca`, `cs`, `da`, `de`, `el`, `en`, `eo`, `es`, `et`, `eu`, `fa`, `fi`, `fr`, `ga`, `gl`, `he`, `hi`, `hu`, `id`, `it`, `ja`, `ko`, `ky`, `lt`, `lv`, `ms`, `nb`, `nl`, `pb`, `pl`, `pt`, `ro`, `ru`, `sk`, `sl`, `sq`, `sv`, `sw`, `th`, `tl`, `tr`, `uk`, `ur`, `vi`, `zh`, `zt`

| Function | Parameters | Description |
|----------|------------|-------------|
| `translate_text` | `text`, `target_lang`, `source_lang` (opt) | Translate text |
| `detect_language` | `text` | Detect language |
| `list_languages` | `scope` (languages/installed) | List supported or installed languages |

---

### 4.5 LLMTool (`tools/llm/`)

Routes user input to the main conversational AI model. Used for open-ended questions, instructions, and complex queries.

| Field | Value |
|---|---|
| Tool name | `llm` |
| Actions | `forward` |
| Risk Tier | NETWORK |
| Registered functions | 1 |

| Function | Parameters | Description |
|----------|------------|-------------|
| `forward_to_ai` | `message` | Forwards text to the forward LLM with full conversation history |

**How it works:** The function-calling LLM (FunctionGemma) decides when a query needs the forward LLM's broader capabilities. `handle_forward()` in `tools/llm/scripts/handlers.py` reads the current `session_id` from `memory/current_session`, loads conversation history via `core/history.load()`, and injects it as context to the forward LLM API call (configured via `forward_base_url`, `forward_model` in `memory/settings.md`).

---

## Part 5: Web UI

The SvelteKit frontend with a Flask backend.

### 5.1 Frontend Libraries

| Library | Purpose |
|---------|---------|
| **Skeleton** | CSS design system (cerberus theme), light/dark mode |
| **bits-ui** | Headless UI primitives (Select, Dialog, Tooltip) |
| **shadcn-svelte** | Copy-paste components built on bits-ui |
| **Flowbite Svelte** | Tailwind-based component library |

### 5.2 UI Components

| Component | File | Description |
|-----------|------|-------------|
| ChatPanel | `src/lib/components/ChatPanel.svelte` | Main chat interface with voice input/output |
| DisplayPanel | `src/lib/components/DisplayPanel.svelte` | Right-side display canvas |
| Message | `src/lib/components/Message.svelte` | Individual message bubble |

### 5.3 Features

- **Two-panel layout:** Chat (left) + display canvas (right)
- **Voice input:** Browser SpeechRecognition (STT)
- **Voice output:** Edge TTS neural voices via `/api/tts`
- **Automatic translation:** User input → English → AI → translated response
- **Dual-language display:** Original text above, translation below
- **Session management:** Create, switch, delete sessions with history
- **Theme toggle:** Light/dark mode, persisted to localStorage

### 5.4 Translation Flow

```
User types in spoken_lang (e.g., Bengali)
    ↓
POST /api/chat → web_server.py translates input to English via LibreTranslateTool
    ↓
CardinalSystemEngine.process_request() sends to LM Studio with MCP tools
    ↓
LM Studio model calls functions → results injected back into context
    ↓
Final response in English
    ↓
web_server.py translates response back to spoken_lang
    ↓
Display: original (English) + translated response (spoken_lang)
    ↓
TTS speaks the translated response
```

### 5.5 TTS Voice Map

The web server maps language codes to Edge TTS neural voices:

| Lang | Voice | Lang | Voice |
|------|-------|------|-------|
| `en` | en-US-JennyNeural | `bn` | bn-BD-NabanitaNeural |
| `ar` | ar-SA-ZariyahNeural | `fr` | fr-FR-DeniseNeural |
| `de` | de-DE-KatjaNeural | `es` | es-ES-ElviraNeural |
| `ja` | ja-JP-NanamiNeural | `ko` | ko-KR-SunHiNeural |
| `pt` | pt-BR-FranciscaNeural | `ru` | ru-RU-SvetlanaNeural |
| `zh` | zh-CN-XiaoxiaoNeural | `hi` | hi-IN-SwaraNeural |

Full voice map supports 40 languages. Falls back to `en-US-JennyNeural`.

---

## Part 6: API Reference

### 6.1 Health Check

```
GET /api/health
```

Response:
```json
{ "status": "ok" }
```

### 6.2 Chat

```
POST /api/chat
Content-Type: application/json

{
    "message": "what time is it?",
    "session_id": "optional-session-id"
}
```

Response:
```json
{
    "success": true,
    "response": "The current time is 06:26:13 PM in Asia/Dhaka.",
    "translated_response": "সময় হলো বিকাল ০৬:২৬:১৩...",
    "user_translated": "",
    "translation_time": 0.45,
    "results": [{"success": true, "value": "06:26 PM", "tool": "clock_calendar"}],
    "is_chat": true,
    "error": "",
    "stats": { "input_tokens": 327, "output_tokens": 283, "total_duration_ms": 1250 },
    "raw_output": "..."
}
```

The `/api/chat` endpoint also:
- Auto-detects and translates non-English input to English via `LibreTranslateTool`
- Processes through `CardinalSystemEngine` (function-calling model + tool execution)
- Translates the AI response back to `spoken_lang` (if configured)
- Saves conversation history to `memory/history/{session_id}.json`

### 6.3 Sessions

```
GET  /api/sessions                        → List all sessions
POST /api/sessions                        → Create new session
POST /api/sessions {"id": "custom-id"}    → Create session with custom ID
DELETE /api/sessions/<session_id>         → Delete a session
```

List response:
```json
{
    "sessions": [
        { "id": "abc123", "message_count": 12, "preview": "hello" }
    ]
}
```

### 6.4 History

```
GET /api/history/<session_id>
```

Response:
```json
{
    "history": [
        { "role": "user", "content": "what time is it", "user_original": "what time is it" },
        { "role": "assistant", "content": "06:26 PM", "translated_response": "..." }
    ]
}
```

### 6.5 Translation

```
POST /api/translate
Content-Type: application/json

{
    "text": "Hello world",
    "source": "en",
    "target": "bn"
}
```

### 6.6 Text-to-Speech

```
GET /api/tts?text=Hello+world&lang=en
```

Returns MP3 audio. Uses cached results for repeated requests. Falls back to `spoken_lang` from settings if `lang` is not provided.

### 6.7 Preferences

```
GET /api/preferences
```

Returns parsed `memory/settings.md` as JSON:
```json
{
    "spoken_lang": "bn",
    "timezone": "Asia/Dhaka",
    "time_format": "12h",
    "tone": "casual",
    "name": "Bob"
}
```

---

## Part 7: Running

### 7.1 Prerequisites

1. **Python 3.10+**
2. **Node.js 18+** (for building the UI)
3. **LM Studio** (v0.4.0+) running with models loaded:
   - Function-calling model (e.g., `functiongemma-finetuned@f16`) on port 1234
   - Forward model (e.g., `qwen3-0.6b-heretic-abliterated-uncensored`) on port 1235 (optional, for `/api/chat`)
4. In LM Studio Developer tab:
   - **Require Authentication**: ON
   - **Allow calling servers from mcp.json**: ON
5. An API token from LM Studio Server Settings → Authentication

### 7.2 Install

```bash
git clone https://github.com/OpenSourceLTS/cardinal-system.git
cd cardinal-system

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

Dependencies: `flask`, `requests`, `tzdata`, `argos-translate-lt`, `edge-tts`, `langdetect`, `openai`

### 7.3 Build Frontend

```bash
cd ui
npm install
npm run build
cd ..
```

### 7.4 Run

**Production (Flask serves built UI):**
```bash
python main.py --web
# Opens at http://localhost:8080
```

**With custom host/port:**
```bash
python main.py --web --host 127.0.0.1 --port 3000
```

**Development mode (SvelteKit HMR + Flask):**
```bash
# Terminal 1
python -m ui.web_server       # Flask on :8080

# Terminal 2
cd ui && npm run dev           # SvelteKit on :5173 (proxies /api to :8080)
# Opens at http://localhost:5173
```

**CLI mode:**
```bash
python main.py
# Interactive terminal prompt
```

### 7.5 LM Studio MCP Configuration

Register the MCP server in LM Studio's `~/.lmstudio/mcp.json`:

```json
{
  "mcpServers": {
    "cardinal-system": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\cardinalsystem\\core\\mcp_server.py"],
      "env": {}
    }
  }
}
```

On macOS/Linux:
```json
{
  "mcpServers": {
    "cardinal-system": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/cardinalsystem/core/mcp_server.py"],
      "env": {}
    }
  }
}
```

---

## Part 8: SDK Tool Creation Guide

### Step 1: Create the tool directory structure

```
tools/{name}/
├── {name}_tool.py           # Tool class
├── manifest.json            # JSON manifest
├── scripts/
│   ├── __init__.py          # Empty
│   └── handlers.py          # Business logic
```

### Step 2: Write the tool class

```python
from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import handlers

class MyTool(BaseTool):
    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("mytool"))

    def execute(self, action, target, payload, metadata, ctx):
        if action == "get":
            return handlers.handle_get(target, payload, metadata, ctx)
        if action == "set":
            return handlers.handle_set(target, payload, metadata, ctx)
        return CommandResult.fail(f"Action '{action}' not supported by {self.manifest.name}")
```

### Step 3: Write your scripts

Place business logic in `scripts/` modules. Each handler receives parsed command components and returns `CommandResult.ok(value)` or `CommandResult.fail(error)`.

```python
# scripts/handlers.py
from core.base_tool import CommandResult

def handle_get(target, payload, metadata, ctx):
    if target == "greeting":
        return CommandResult.ok("Hello from MyTool!")
    return CommandResult.fail(f"Unknown target: {target}")

def handle_set(target, payload, metadata, ctx):
    # Do something with the data
    return CommandResult.ok(f"Set {target} to {payload}")
```

### Step 4: Write `manifest.json`

```json
{
    "name": "mytool",
    "description": "Does something useful.",
    "risk_tier": "SAFE",
    "functions": {
        "get_greeting": {
            "description": "Get a greeting message",
            "parameters": {},
            "required": [],
            "action": "get",
            "target": "greeting",
            "payload_expr": "",
            "templates": ["Say hello", "Greet me", "Give me a greeting"],
            "examples": {}
        },
        "set_setting": {
            "description": "Set a configuration value",
            "parameters": {
                "name": { "type": "STRING", "description": "Setting name" },
                "value": { "type": "STRING", "description": "Setting value" }
            },
            "required": ["name", "value"],
            "action": "set",
            "target": "setting",
            "payload_expr": "{name} | {value}",
            "templates": ["Set {name} to {value}"],
            "examples": { "name": ["theme", "language"], "value": ["dark", "bn"] }
        }
    }
}
```

**Manifest fields:**
- `name` — tool name (must match directory and class naming convention)
- `description` — shown to the AI in tool definitions
- `risk_tier` — `SAFE`, `STATEFUL`, `NETWORK`, or `DESTRUCTIVE`
- `functions` — dict of named functions, each with:
  - `description` — function description
  - `parameters` — JSON Schema object with typed properties
  - `required` — list of required parameter names
  - `action` — tool action verb (from canonical verbs list)
  - `target` — tool target resource for routing
  - `payload_expr` — template string with `{param}` placeholders for the payload
  - `templates` — user prompt templates, keyed by language or flat array for `en`
  - `examples` — dict of parameter → example values for training data generation
- `multi_tool` — (llm only) multi-call scenarios: `parallel`, `sequential`, `triple`, `irrelevant`

### Step 5: Registration

No manual registration needed. `core/mcp_server.py` auto-discovers all tools. Just ensure:

1. Directory is `tools/{name}/`
2. Python file is `tools/{name}/{name}_tool.py`
3. Class name is PascalCase of the tool name (e.g., `weather` → `WeatherTool`)
4. `manifest.json` exists with valid `name`, `description`, `actions`, `risk_tier`, and `manifest.a@p`
5. The class inherits from `BaseTool`

Discovery flow:
```
mcp_server.py → discover_tools() → scans tools/*/manifest.json
             → load_tool_class() → imports tools.{dir}.{name}_tool
             → finds BaseTool subclass → registers with Router
```

---

## Part 9: Full SDK Example — WeatherTool

### `tools/weather/weather_tool.py`

```python
from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import fetch

class WeatherTool(BaseTool):
    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("weather"))

    def execute(self, action, target, payload, metadata, ctx):
        if action == "get":
            return fetch.handle_get(target, payload, metadata, ctx)
        return CommandResult.fail(f"Action {action} not supported by {self.manifest.name}")
```

### `tools/weather/scripts/fetch.py`

```python
import requests
from core.base_tool import CommandResult

def handle_get(city, unit, metadata, ctx):
    try:
        response = requests.get(
            f"https://api.weather.com/v1/{city}",
            params={"unit": unit},
            timeout=10,
        )
        data = response.json()
        return CommandResult.ok(f"{data['temp']}°{unit[0].upper()} in {city}")
    except Exception as e:
        return CommandResult.fail(f"API Error: {str(e)}")
```

### `tools/weather/manifest.json`

```json
{
    "name": "weather",
    "description": "Current weather conditions for any city.",
    "risk_tier": "NETWORK",
    "functions": {
        "get_weather": {
            "description": "Get current weather for a city",
            "parameters": {
                "city": { "type": "STRING", "description": "City name" },
                "unit": { "type": "STRING", "description": "celsius or fahrenheit" }
            },
            "required": ["city"],
            "action": "get",
            "target": "weather",
            "payload_expr": "{city} | {unit}",
            "templates": [
                "What's the weather in {city}?",
                "Weather for {city}",
                "How's the weather in {city}?"
            ],
            "examples": {
                "city": ["London", "Tokyo", "New York", "Dhaka"],
                "unit": ["celsius", "fahrenheit"]
            }
        }
    }
}
```

No registration needed — tools are auto-discovered from `tools/*/manifest.json` by `core/mcp_server.py` using `load_tool_class()`.

---

## Part 10: Training Data Pipeline

Cardinal generates FunctionGemma-format training data for fine-tuning the function-calling model (`google/functiongemma-270m-it`). Training data lives in each tool's **own manifest** under the `functions` dict.

### 10.1 Data Ownership

Each function entry in `manifest.json` contains training-specific fields:

| Field | Description |
|---|---|
| `templates` | User prompt templates with `{param}` placeholders |
| `examples` | Dict of parameter → example values for substitution |
| `multi_tool` | (llm only) Multi-call scenarios |

**Example** (from `tools/clock_and_calendar/manifest.json`):
```json
{
  "get_time": {
    "description": "Get the current time",
    "parameters": {
      "timezone": { "type": "STRING", "description": "..." }
    },
    "action": "get",
    "target": "time",
    "payload_expr": "{timezone}",
    "templates": ["What time is it?", "Tell me the time", "Time in {timezone}"],
    "examples": { "timezone": ["Asia/Dhaka", "America/New_York"] }
  }
}
```

Multi-tool scenarios live only in `tools/llm/manifest.json`:
```json
{
  "multi_tool": {
    "parallel": [
      {
        "tools": [
          {"function": "get_time", "args": {}},
          {"function": "get_timezone_info", "args": {}},
          {"en": "What time is it and what's my timezone?"}
        ]
      }
    ],
    "sequential": [...],
    "triple": [...],
    "irrelevant": [...]
  }
}
```

Languages are embedded directly in templates as arrays (flat for English), with translations across 30 languages stored in a `_translations` key.

### 10.2 Pipeline

```
tools/*/manifest.json      ← Each tool owns its training data (functions dict)
        │
        ▼
python generate_training_data.py  ← Reads manifests directly, no intermediate step
        │
        ▼
train-finetune/train/
  └── training_data.jsonl   (final: FunctionGemma-format conversation records)
```

`generate_training_data.py` reads manifests directly (it no longer depends on `combine.py`'s output).

```bash
python generate_training_data.py --lang en              # English only
python generate_training_data.py --lang en,fr,de,bn     # Multi-language
python generate_training_data.py --templates-per-fn 5   # Limit templates per function
```

### 10.3 Record Generation

`generate_training_data.py`:

1. Discovers all functions via `tools/*/manifest.json` (reads each `functions` dict)
2. Filters to requested languages
3. For each function + template + language:
   - Substitutes `{param}` placeholders with example values from the function's `examples` dict
   - Builds a developer message with current date/time context and available tools
   - Builds a user message with the rendered template
   - Builds an assistant `tool_calls` entry with the function name and arguments
4. Loads `multi_tool` config from `tools/llm/manifest.json`
5. Generates multi-call records (parallel, sequential, triple) and irrelevant/no-tool records
6. Randomly shuffles and writes `training_data.jsonl`

### 10.4 Adding a New Language

1. Add translations for each function's `templates` array in its tool's `manifest.json`
2. Add language-keyed phrases to `multi_tool` entries in `llm/manifest.json`
3. Regenerate:

```bash
python generate_training_data.py --lang en,fr,de,ja,bn
```

### 10.5 Fine-Tuning

The generated `training_data.jsonl` feeds into `train-finetune/finetune/colab_finetune.ipynb`:

1. Notebook downloads `training_data.jsonl` from GitHub and `functiongemma-270m-it.zip` from Hugging Face
2. Loads `google/functiongemma-270m-it`, applies SFT with `SFTTrainer` from `trl`
3. Training config: `num_train_epochs=2`, batch size 4, lr 5e-5, BF16
4. Splits data 90/10 for train/validation
5. Fine-tuned model saves to `functiongemma-finetuned/` and uploads to Hugging Face
6. Convert to GGUF via `llama.cpp` (`convert_hf_to_gguf.py --outtype f16`)
7. Load the fine-tuned GGUF in LM Studio for inference

**Eval split (10%):** The dataset is shuffled and split 90/10 by `metadata` field (`"train"` / `"eval"`). Current stats: 7,641 train, 849 eval.

**Hugging Face dataset:** Published as `SkGufranAhmed/functiongemma-finetune-dataset`. Includes `training_data.jsonl` and a `README.md` card. Upload via:
```bash
python -c "
from huggingface_hub import HfApi
api = HfApi()
api.upload_file(path_or_fileobj='training_data.jsonl', path_in_repo='training_data.jsonl',
                repo_id='SkGufranAhmed/functiongemma-finetune-dataset', repo_type='dataset')
"
```
