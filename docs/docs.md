# Cardinal System v4.0 — Developer Documentation

Welcome to the Cardinal System. This documentation covers the architectural philosophy, execution engine, complete tool reference, and SDK tool creation guide.

---

## Part 1: System Architecture & Philosophy

The Cardinal System is built on a principle called **Cognitive Offloading**. Standard AI agents try to make the LLM do everything (reasoning, formatting, API calling, state management). This fails on small models (<1B parameters).

Cardinal offloads 100% of the logic to a deterministic Python engine. The LLM is stripped of its "thinking" responsibilities and acts solely as a **Natural Language to Tool Call Transducer**.

### 1. The Execution Lifecycle (MCP-based)

Cardinal uses LM Studio's native API with MCP (Model Context Protocol) integration for single-pass tool execution:

1. **User Message** is sent to LM Studio's `/api/v1/chat` endpoint with `integrations: ["mcp/cardinal-system"]`.
2. **LM Studio** loads the model, connects to the MCP server (`core/mcp_server.py`), lists available tools, and injects them into the model's context.
3. **LLM Decides** whether to call one of the registered MCP tools (e.g., `clock_calendar`, `notes`, `libretranslate`, `settings`) or respond directly for conversational queries.
4. **MCP Tool Execution** — LM Studio forwards the tool call to the MCP server, which routes it to the correct tool handler.
5. **Result Injection** — The tool result flows back through LM Studio directly into the LLM's generation context in a single pass.
6. **Final Response** — The LLM continues generating with the real tool result already in its context window.

Each tool call uses three fields:
- **verb** — the action (e.g., `get`, `set`, `translate`, `detect`)
- **target** — the resource (e.g., `current_time`, `bn`, `list_notes`)
- **payload** — the data (e.g., `Asia/Dhaka`, `Hello world | en`)

### 2. The Command Grammar

All tool commands follow this structure:

```text
tool(verb)@{target}|{payload}
```

When expressed as MCP tool call fields:

| Field | Description | Example |
|---|---|---|
| verb | Action to perform | `get`, `translate`, `set` |
| target | Primary subject | `current_time`, `bn` |
| payload | Data or parameters | `Hello world \| en` |

### 3. Safety & Risk Tiers

Every tool must declare a `RiskTier`.
- `SAFE`: Read-only.
- `STATEFUL`: Modifies local user data.
- `NETWORK`: Sends data externally.
- `DESTRUCTIVE`: Deletes data or executes arbitrary code.

---

## Part 2: Project Structure

```
cardinalsystem/
├── main.py                     # Entry point: CLI or web server
├── requirements.txt            # flask, edge-tts, argos-translate-lt, langdetect, tzdata
├── mcp.json                    # LM Studio MCP server configuration
├── core/                       # Engine & framework
│   ├── base_tool.py            # BaseTool, CommandResult, ExecutionContext
│   ├── manifest.py             # ToolManifest, RiskTier, tool discovery
│   ├── engine.py               # CardinalSystemEngine — LM Studio native API client
│   ├── parser.py               # CommandNode dataclass
│   ├── router.py               # Routes parsed commands to tools
│   ├── mcp_server.py           # MCP server over stdio — wraps all tools
│   └── bootstrap.py            # Generates LLM system prompts from manifests
├── ui/                         # SvelteKit frontend + Flask server
│   ├── web_server.py           # Flask server (HTTP API + static UI)
│   ├── package.json            # Node deps: bits-ui, @svelteuidev/core, flowbite-svelte, @skeletonlabs/skeleton, svelte-gantt
│   ├── svelte.config.js        # SvelteKit adapter-static config
│   ├── vite.config.js          # Vite + Tailwind CSS + API proxy
│   ├── src/                    # SvelteKit source
│   │   ├── app.html            # HTML shell
│   │   ├── app.css             # Tailwind import
│   │   ├── routes/
│   │   │   ├── +layout.svelte  # Root layout
│   │   │   ├── +layout.js      # SPA mode config
│   │   │   ├── +page.svelte    # Chat page
│   │   │   └── +page.js        # Page prerender config
│   │   └── lib/components/     # Reusable components
│   ├── static/                 # Static assets
│   └── build/                  # Built output (generated)
├── tools/                      # SDK tools (one subdirectory each)
│   ├── clock_and_calendar/     # Time, date, moon, seasons, calendars, alarms, timers, events
│   ├── notes/                  # Persistent markdown notes with line editing
│   ├── settings/               # User preferences (spoken_lang, timezone, tone, etc.)
│   └── libretranslate/         # Self-hosted translation (argos-translate) + language detection
├── memory/
│   ├── clock_and_calendar.json # Timezone, alarms, timers, stopwatch, events
│   ├── notes/                  # Markdown note files (.md)
│   ├── history/                # Session conversation history
│   └── settings.md             # User preferences
├── docs/
│   └── docs.md                 # This file
└── venv/                       # Python virtual environment
```

### Web Server (`ui/web_server.py`)

Flask-based HTTP server serving:
- Static UI at `/` (SvelteKit built output from `ui/build/`)
- Chat API at `/api/chat` — forwards to LM Studio via `CardinalSystemEngine`
- Translation at `/api/translate` — uses LibreTranslateTool (argos-translate, no Google)
- TTS at `/api/tts` — uses edge-tts (Microsoft Edge neural voices, no Google)
- Session management at `/api/sessions`, `/api/history/<id>`
- Preferences at `/api/preferences` — returns parsed settings.md settings

In development, run SvelteKit separately for HMR:
```bash
cd ui && npm run dev          # SvelteKit on :5173 (proxies /api to :8080)
python -m ui.web_server       # Flask on :8080
```

In production, `npm run build` generates `ui/build/` which Flask serves directly.

### MCP Server (`core/mcp_server.py`)

Runs as a stdio subprocess managed by LM Studio. Implements JSON-RPC 2.0 MCP protocol. Each tool is registered as a separate MCP tool with its own `inputSchema` containing `verb`, `target`, `payload` string fields.

Registered tools:
- `clock_calendar`
- `notes`
- `settings`
- `libretranslate`

### Canonical Verbs

Every tool verb must come from the canonical verbs list. These are the only verbs the system recognizes across all tools:

`append`, `approve`, `archive`, `ask`, `block`, `bookmark`, `branch`, `calculate`, `change`, `cancel`, `check`, `clear`, `comment`, `commit`, `complete`, `compress`, `convert`, `copy`, `create`, `decline`, `decrypt`, `delete`, `deny`, `deploy`, `directions`, `disable`, `dismiss`, `enable`, `embed`, `encrypt`, `exec`, `extract`, `fetch`, `follow`, `forecast`, `forward`, `generate`, `get`, `grant`, `grab`, `like`, `list`, `log`, `mention`, `merge`, `move`, `mute`, `navigate`, `pair`, `paste`, `pause`, `pin`, `place`, `play`, `post`, `predict`, `publish`, `pull`, `push`, `query`, `queue`, `react`, `read`, `release`, `remind`, `remove`, `rename`, `reply`, `report`, `reschedule`, `reset`, `restore`, `revoke`, `rollback`, `run`, `say`, `schedule`, `search`, `send`, `set`, `save`, `share`, `sort`, `stop`, `stream`, `subscribe`, `sync`, `toggle`, `translate`, `train`, `unblock`, `uncheck`, `unfollow`, `unmute`, `unpin`, `unsubscribe`, `update`, `upload`, `write`

These are the recognized verb vocabulary. New tools should choose verbs from this list for consistency. Each tool defines its own subset in `manifest.json` under the `"verbs"` field; the router validates against those per-tool verbs, not this master list.

---

## Part 3: Registered Tools

### ClockCalendarTool (`tools/clock_and_calendar/`)

Time, moon phase, season, timezone, date, day-of-week, calendar conversion, date calculations, alarms, timers, stopwatch, and event scheduling.

| Field | Value |
|---|---|
| Verbs | `get`, `set`, `convert`, `calculate`, `delete` |
| Risk Tier | SAFE / STATEFUL |
| Target hint | `current`, `timezone`, `moon`, `season`, `phases`, `alarm`, `timer`, `stopwatch`, `event`, or calculation type |
| Payload hint | `time`, `moon`, `all`, `datetime`, timezone name, duration, event description |

GET targets: `current_time`, `current_date`, `current_datetime`, `timezone`, `epoch`, `time_in_zone`, `next_weekday`, `quarter`, `week_number`, `sunrise`, `sunset`, `moon`, `season`, `phases`, `alarms`, `timers`, `stopwatch`, `events`

SET targets: `timezone`, `alarm`, `timer`, `stopwatch`, `event`

DELETE targets: `alarm`, `timer`, `event`

CALCULATE targets: `day_of_week`, `days_between`, `date_offset`, `until`, `minutes_until`, `minutes_since`, `weeks_between`, `months_between`, `years_between`, `is_leap_year`

CONVERT targets: `to_hijri`, `timezone`, `time_format`

---

### NotesTool (`tools/notes/`)

Persistent markdown notes saved as `.md` files in `memory/notes/`. Supports read, write, append, list, delete, and line-level editing.

| Field | Value |
|---|---|---|
| Verbs | `list`, `read`, `save`, `append`, `delete`, `change`, `rename`, `search` |
| Risk Tier | STATEFUL |
| Target hint | `filename` |
| Payload hint | content, line/range, or `old -> new` |

Read targets:
- `read` — read entire note, or `filename` with payload `3` (single line) or `3-5` (line range)

Save/append:
- `save` — create/overwrite note. Auto-generates filename from first 3 words if no target.
- `append` — append content to existing note.

Delete:
- `delete` — delete entire file. With line range payload, delete specific lines.

Change:
- `change` — replace line (`line | new_content`), insert (`+line | content`), or find/replace (`old -> new`)

Rename:
- `rename` — rename a note file.

Search:
- `search` — search within a file or across all notes. Returns filename + line number matches.

---

### SettingsTool (`tools/settings/`)

User preferences that affect system behavior: timezone, time format, tone, spoken language for TTS/translation, and arbitrary key-value settings.

| Field | Value |
|---|---|
| Verbs | `get`, `set`, `delete` |
| Risk Tier | STATEFUL |
| Target hint | preference name or `list` |
| Payload hint | `setting_name\|value` or just `value` for known settings |

Known settings:
- `timezone` — IANA name, offset, city, or country (resolved via timezone resolver)
- `time_format` — `12h` or `24h`
- `spoken_lang` — language code for TTS speech and input translation source (e.g. `bn`, `fr`, `ja`, `de`). Default: `bn`
- Any custom key-value pair via `setting|key|value`

---

### LibreTranslateTool (`tools/libretranslate/`)

Self-hosted machine translation using argos-translate. Supports 50 languages. Auto-downloads translation models on first use.

| Field | Value |
|---|---|
| Verbs | `translate`, `detect`, `list` |
| Risk Tier | NETWORK |
| Target hint | language code for translate; empty for detect; `languages` or `installed` for list |
| Payload hint | `text \| source_lang` (translate); text to detect (detect) |

Available language codes: `ar`, `az`, `bg`, `bn`, `ca`, `cs`, `da`, `de`, `el`, `en`, `eo`, `es`, `et`, `eu`, `fa`, `fi`, `fr`, `ga`, `gl`, `he`, `hi`, `hu`, `id`, `it`, `ja`, `ko`, `ky`, `lt`, `lv`, `ms`, `nb`, `nl`, `pb`, `pl`, `pt`, `ro`, `ru`, `sk`, `sl`, `sq`, `sv`, `sw`, `th`, `tl`, `tr`, `uk`, `ur`, `vi`, `zh`, `zt`

translate verb:
- `translate(bn)@"Hello world | en"` — translate "Hello world" from English to Bengali
- `translate(en)@"হ্যালো | bn"` — translate from Bengali to English
- `translate(fr)@"Good morning"` — translate from default source (en) to French

detect verb:
- `detect(libretranslate)@""|"Bonjour le monde"` — detect language as French
- Returns language code and name (e.g., `fr (French)`)

list verb:
- `list(libretranslate)@languages|""` — list all 50 supported languages
- `list(libretranslate)@installed|""` — list currently downloaded models

---

## Part 4: Web UI

The SvelteKit frontend is built with a combination of design systems and component libraries:

| Library | Purpose | Link |
|---|---|---|
| **Skeleton** | CSS design system (cerberus theme), light/dark mode, CSS variables | https://www.skeleton.dev/ |
| **bits-ui** | Headless UI primitives (Select, Dialog, Tooltip, DropdownMenu) | https://bits-ui.com/ |
| **shadcn-svelte** | Copy-paste components built on bits-ui | https://www.shadcn-svelte.com/ |
| **Flowbite Svelte** | Tailwind-based component library | https://flowbite-svelte.com/ |
| **Svar Design System** | Full design system (AppShell, Button, Card, Text, TextInput, Notification, Modal) | https://svar.dev/svelte/ |
| **Svar Core** | Core foundation of Svar design system | https://svar.dev/svelte/core/ |
| **Svelte Gantt** | Gantt chart component | https://anovokmet.github.io/svelte-gantt/ |

Features:
- Two-panel layout: chat (left) + display canvas (right)
- Voice input via browser SpeechRecognition (STT)
- Voice output via `/api/tts` (edge-tts neural voices)
- Translation always active — user input translated to English for AI processing; AI responses translated to `spoken_lang` for display and TTS
- Dual-language message display: original above, translation below
- Session management with history
- Theme toggle (light/dark) persisted to localStorage

### Preferences

Set via `set(settings)@key|value`:
```
spoken_lang: bn      # TTS + display translation target, and input source language
timezone: Asia/Dhaka
time_format: 12h
tone: casual
name: Bob
```

### Translation Flow

1. User types in `spoken_lang` (e.g., Bengali)
2. Text is translated to English via `/api/translate` (using argos-translate)
3. English text sent to AI (LM Studio)
4. AI responds in English
5. Response translated back to `spoken_lang` for display and TTS

---

## Part 5: Running

### Prerequisites

1. **LM Studio** (v0.4.0+) running with a model loaded
2. **Server Settings** in LM Studio Developer tab:
   - **Require Authentication**: ON
   - **Allow calling servers from mcp.json**: ON
3. **MCP Server configured** — register the `cardinal-system` MCP server in LM Studio
4. **API Token** from LM Studio Server Settings → Authentication

### Install dependencies

```bash
pip install -r requirements.txt
```

Dependencies: `flask`, `edge-tts`, `argos-translate-lt`, `langdetect`, `requests`, `tzdata`

### Build frontend (first time or after UI changes)

Installs all UI libraries (bits-ui, @svelteuidev/core, flowbite-svelte, @skeletonlabs/skeleton, svelte-gantt) and builds:

```bash
cd ui && npm install && npm run build
```

### Web server

```bash
python -m ui.web_server
```

Opens HTTP server at `http://localhost:8080`. Open in browser for the chat UI.

### Development mode (with HMR, single command)

```bash
cd ui && npm run dev
```

Starts both SvelteKit on `:5173` (with hot reload) and Flask on `:8080`. The Vite proxy forwards `/api/*` to Flask. Open `http://localhost:5173` in the browser.

### API Endpoint

```
POST http://localhost:8080/api/chat
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
    "results": [],
    "is_chat": true,
    "stats": { "input_tokens": 327, "total_output_tokens": 283 }
}
```

### LM Studio MCP Configuration

Configured in `~/.lmstudio/mcp.json`:

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

---

## Part 6: SDK Tool Creation Guide

### Step 1: Create the tool directory structure
```
tools/{name}/
├── {name}_tool.py           # Tool class
├── manifest.json            # JSON manifest
├── scripts/
│   ├── __init__.py          # Empty
│   └── handlers.py
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

    def execute(self, verb, target, payload, metadata, ctx):
        if verb == "get":
            return handlers.handle_get(target, payload, metadata, ctx)
        return CommandResult.fail(f"Verb '{verb}' not supported by {self.manifest.name}")
```

### Step 3: Write your scripts
Place business logic in `scripts/` modules. Each handler receives parsed command components and returns `CommandResult.ok(value)` or `CommandResult.fail(error)`.

### Step 4: Write `manifest.json`
```json
{
    "name": "mytool",
    "description": "Does something useful.",
    "risk_tier": "SAFE",
    "verbs": ["get", "set"],
    "manifest": {
        "example": { "verb": "get", "target": "info", "payload": "" },
        "v@p": {
            "get": [["target", "payload"]],
            "set": [["target", "payload"]]
        }
    }
}
```

### Step 5: Registration

No manual registration needed. `core/mcp_server.py` uses `load_tool_class()` to auto-discover all tools. Just ensure:
- Directory is `tools/{name}/`
- Python file is `tools/{name}/{name}_tool.py`
- Class name is the PascalCase version of the tool name (e.g., `weather` → `WeatherTool`)
- `manifest.json` exists with valid `name`, `description`, `verbs`, `risk_tier`, and `manifest.v@p`

### ExecutionContext reference

```python
ctx.memo       # dict — shared working memory across commands in a pipeline
ctx.results    # list[CommandResult] — results from previous commands
ctx.timezone   # str — timezone name (default "UTC")
```

---

## Part 7: Full SDK Example — `WeatherTool`

**File: `tools/weather/weather_tool.py`**
```python
from core.base_tool import BaseTool, CommandResult, ExecutionContext
from core.manifest import ToolManifest, load_manifest
from .scripts import fetch

class WeatherTool(BaseTool):
    @property
    def manifest(self):
        return ToolManifest.from_json(load_manifest("weather"))

    def execute(self, verb, target, payload, metadata, ctx):
        if verb == "get":
            return fetch.handle_get(target, metadata.get("unit", "celsius"))
        return CommandResult.fail(f"Verb {verb} not supported by {self.manifest.name}")
```

**File: `tools/weather/scripts/fetch.py`**
```python
import requests
from core.base_tool import CommandResult

def handle_get(city, unit):
    try:
        response = requests.get(f"https://api.weather.com/v1/{city}?unit={unit}")
        data = response.json()
        return CommandResult.ok(f"{data['temp']}°{unit[0].upper()} in {city}")
    except Exception as e:
        return CommandResult.fail(f"API Error: {str(e)}")
```

No registration needed — tools are auto-discovered from `tools/*/manifest.json` by `core/mcp_server.py` using `load_tool_class()`.
