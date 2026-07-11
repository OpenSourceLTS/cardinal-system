# Cardinal System v4.0

A lightweight AI assistant framework built on **Cognitive Offloading** — all logic lives in a deterministic Python engine while a small local LLM (via [LM Studio](https://lmstudio.ai/)) acts solely as a natural-language-to-tool-call transducer.

---

## Table of Contents

- [Why Cardinal](#why-cardinal)
- [Architecture](#architecture)
  - [Execution Lifecycle](#execution-lifecycle)
  - [Command Grammar](#command-grammar)
  - [Safety & Risk Tiers](#safety--risk-tiers)
- [Project Structure](#project-structure)
- [Built-in Tools](#built-in-tools)
  - [Clock & Calendar](#clock--calendar-tool)
  - [Notes](#notes-tool)
  - [Settings](#settings-tool)
  - [LibreTranslate](#libretranslate-tool)
- [Web UI](#web-ui)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Install](#install)
  - [Build Frontend](#build-frontend)
  - [Run](#run)
- [API Reference](#api-reference)
- [SDK Tool Creation Guide](#sdk-tool-creation-guide)
- [Full SDK Example](#full-sdk-example)

---

## Why Cardinal

Standard AI agents try to make the LLM do everything — reasoning, formatting, API calling, state management. This fails on small models (< 1B parameters).

Cardinal offloads 100% of the logic to a deterministic Python engine. The LLM is stripped of its "thinking" responsibilities and acts solely as a **Natural Language to Tool Call Transducer**. The engine handles all validation, routing, and execution.

**Key benefits:**

- Works with tiny models (e.g. `lfm2.5-230m-fable-5`)
- Deterministic execution — no hallucinated API calls
- Self-hosted translation via argos-translate (no Google dependency)
- Microsoft Edge neural TTS (no Google dependency)
- Modular tool SDK — add new tools without touching the engine

---

## Architecture

### Execution Lifecycle

Cardinal uses LM Studio's native API with MCP (Model Context Protocol) integration:

```
User Message
    ↓
LM Studio (/api/v1/chat + integrations: ["mcp/cardinal-system"])
    ↓
LLM decides: call tool or respond directly
    ↓
MCP Tool Execution (core/mcp_server.py routes to tool handler)
    ↓
Result injected back into LLM context (single pass)
    ↓
Final Response
```

### Command Grammar

Every tool call uses three fields:

| Field    | Description                | Example                |
| -------- | -------------------------- | ---------------------- |
| `verb`   | Action to perform          | `get`, `translate`     |
| `target` | Primary subject            | `current_time`, `bn`   |
| `payload`| Data or parameters         | `Hello world \| en`    |

### Safety & Risk Tiers

Every tool declares a `RiskTier`:

| Tier        | Description                   |
| ----------- | ----------------------------- |
| `SAFE`      | Read-only operations          |
| `STATEFUL`  | Modifies local user data      |
| `NETWORK`   | Sends data externally         |
| `DESTRUCTIVE`| Deletes data or executes code |

---

## Project Structure

```
cardinalsystem/
├── main.py                     # Entry point: CLI or web server
├── requirements.txt            # Python dependencies
├── mcp.json                    # LM Studio MCP server config
├── core/                       # Engine & framework
│   ├── base_tool.py            # BaseTool, CommandResult, ExecutionContext
│   ├── manifest.py             # ToolManifest, RiskTier, tool discovery
│   ├── engine.py               # CardinalSystemEngine — LM Studio API client
│   ├── parser.py               # CommandNode dataclass
│   ├── router.py               # Routes parsed commands to tools
│   ├── mcp_server.py           # MCP server over stdio — wraps all tools
│   └── history.py              # Conversation history management
├── ui/                         # SvelteKit frontend + Flask server
│   ├── web_server.py           # Flask server (HTTP API + static UI)
│   ├── src/                    # SvelteKit source
│   │   └── lib/components/     # Reusable Svelte components
│   └── build/                  # Built output (generated)
├── tools/                      # SDK tools (one subdirectory each)
│   ├── clock_and_calendar/     # Time, date, moon, calendars, alarms, timers
│   ├── notes/                  # Persistent markdown notes
│   ├── settings/               # User preferences
│   └── libretranslate/         # Self-hosted translation (argos-translate)
├── memory/                     # Persistent data storage
│   ├── clock_and_calendar.json # Timezone, alarms, timers, events
│   ├── notes/                  # Markdown note files
│   ├── history/                # Session conversation history
│   └── settings.md             # User preferences
└── docs/
    └── docs.md                 # Full developer documentation
```

---

## Built-in Tools

### Clock & Calendar Tool

**Verbs:** `get`, `set`, `convert`, `calculate`, `delete`
**Risk Tier:** SAFE / STATEFUL

| Action      | Targets                                                                         |
| ----------- | ------------------------------------------------------------------------------- |
| **Get**     | `current_time`, `current_date`, `timezone`, `epoch`, `moon`, `season`, `phases`, `sunrise`, `sunset`, `alarms`, `timers`, `stopwatch`, `events` |
| **Set**     | `timezone`, `alarm`, `timer`, `stopwatch`, `event`                              |
| **Delete**  | `alarm`, `timer`, `event`                                                       |
| **Calculate**| `day_of_week`, `days_between`, `date_offset`, `until`, `minutes_until`, `is_leap_year` |
| **Convert** | `to_hijri`, `timezone`, `time_format`                                           |

### Notes Tool

**Verbs:** `list`, `read`, `save`, `append`, `delete`, `change`, `rename`, `search`
**Risk Tier:** STATEFUL

- Read entire notes or specific line ranges
- Create, overwrite, or append to notes
- Line-level editing: replace, insert, find/replace
- Search across all notes with filename + line numbers

### Settings Tool

**Verbs:** `get`, `set`, `delete`
**Risk Tier:** STATEFUL

Known settings:

| Key           | Example               | Description                          |
| ------------- | --------------------- | ------------------------------------ |
| `timezone`    | `Asia/Dhaka`          | User's timezone (IANA, offset, city) |
| `time_format` | `12h` or `24h`        | Time display format                  |
| `spoken_lang` | `bn`                  | TTS + display translation language   |
| `tone`        | `casual`              | Response tone                        |
| `name`        | `Bob`                 | User's name                          |

### LibreTranslate Tool

**Verbs:** `translate`, `detect`, `list`
**Risk Tier:** NETWORK

Self-hosted machine translation using argos-translate. Supports 50 languages with auto-downloading of translation models on first use.

```
translate(bn)@"Hello world | en"   → translate English to Bengali
detect()|"Bonjour le monde"         → detect language (returns "fr (French)")
list()@languages|""                 → list all 50 supported languages
```

---

## Web UI

SvelteKit frontend with a two-panel layout:

- **Chat panel** (left) — text input with voice support
- **Display canvas** (right) — rendered responses

**Features:**

- Voice input via browser SpeechRecognition (STT)
- Voice output via `/api/tts` using Edge TTS neural voices
- Automatic translation flow: user input → English → AI → translated response
- Dual-language message display (original + translation)
- Session management with conversation history
- Light/dark theme toggle (persisted to localStorage)

**Frontend libraries:**

| Library           | Purpose                          |
| ----------------- | -------------------------------- |
| Skeleton          | CSS design system (cerberus)     |
| bits-ui           | Headless UI primitives           |
| shadcn-svelte     | Copy-paste components            |
| Flowbite Svelte   | Tailwind component library       |
| Svelte Gantt      | Gantt chart component            |

---

## Getting Started

### Prerequisites

1. **Python 3.10+**
2. **Node.js 18+** (for building the UI)
3. **LM Studio** (v0.4.0+) running with a model loaded
4. In LM Studio Developer tab:
   - **Require Authentication**: ON
   - **Allow calling servers from mcp.json**: ON
5. An API token from LM Studio Server Settings → Authentication

### Install

```bash
# Clone
git clone https://github.com/OpenSourceLTS/cardinal-system.git
cd cardinal-system

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install Python dependencies
pip install -r requirements.txt
```

### Build Frontend

```bash
cd ui
npm install
npm run build
cd ..
```

### Run

**Production (Flask serves built UI):**

```bash
python main.py --web
# Opens at http://localhost:8080
```

**Development (SvelteKit HMR + Flask):**

```bash
# Terminal 1
python -m ui.web_server       # Flask on :8080

# Terminal 2
cd ui && npm run dev          # SvelteKit on :5173 (proxies /api to :8080)
# Opens at http://localhost:5173
```

**CLI mode:**

```bash
python main.py
# Interactive terminal prompt
```

### LM Studio MCP Configuration

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

---

## API Reference

### Chat

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
    "results": [],
    "is_chat": true,
    "stats": { "input_tokens": 327, "total_output_tokens": 283 }
}
```

### Translation

```
POST /api/translate
Content-Type: application/json

{
    "text": "Hello world",
    "source": "en",
    "target": "bn"
}
```

### Text-to-Speech

```
POST /api/tts
Content-Type: application/json

{
    "text": "Hello world",
    "lang": "en"
}
```

Returns audio data.

### Sessions & History

```
GET  /api/sessions           # List all sessions
GET  /api/history/<id>       # Get conversation history for a session
```

### Preferences

```
GET  /api/preferences        # Returns parsed settings
```

---

## SDK Tool Creation Guide

### Step 1: Create the tool directory

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

No manual registration needed. `core/mcp_server.py` auto-discovers all tools. Just ensure:

- Directory is `tools/{name}/`
- Python file is `tools/{name}/{name}_tool.py`
- Class name is PascalCase (e.g., `weather` → `WeatherTool`)
- `manifest.json` exists with valid `name`, `description`, `verbs`, `risk_tier`, and `manifest.v@p`

---

## Full SDK Example — WeatherTool

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

No registration needed — tools are auto-discovered from `tools/*/manifest.json`.

---

## Canonical Verbs

Every tool verb must come from this list for consistency:

`append`, `approve`, `archive`, `ask`, `block`, `bookmark`, `branch`, `calculate`, `change`, `cancel`, `check`, `clear`, `comment`, `commit`, `complete`, `compress`, `convert`, `copy`, `create`, `decline`, `decrypt`, `delete`, `deny`, `deploy`, `directions`, `disable`, `dismiss`, `enable`, `embed`, `encrypt`, `exec`, `extract`, `fetch`, `follow`, `forecast`, `forward`, `generate`, `get`, `grant`, `grab`, `like`, `list`, `log`, `mention`, `merge`, `move`, `mute`, `navigate`, `pair`, `paste`, `pause`, `pin`, `place`, `play`, `post`, `predict`, `publish`, `pull`, `push`, `query`, `queue`, `react`, `read`, `release`, `remind`, `remove`, `rename`, `reply`, `report`, `reschedule`, `reset`, `restore`, `revoke`, `rollback`, `run`, `say`, `schedule`, `search`, `send`, `set`, `save`, `share`, `sort`, `stop`, `stream`, `subscribe`, `sync`, `toggle`, `translate`, `train`, `unblock`, `uncheck`, `unfollow`, `unmute`, `unpin`, `unsubscribe`, `update`, `upload`, `write`

---

## License

See [LICENSE](LICENSE) for details.
