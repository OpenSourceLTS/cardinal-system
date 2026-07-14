# Cardinal System v0.0.1 — Developer Documentation

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
| `verb`   | Action to perform                    | `get`, `translate`   |
| `target` | Primary subject / resource           | `current_time`, `bn` |
| `payload`| Data or parameters                   | `Asia/Dhaka`, `Hello world \| en` |

When expressed as a human-readable shorthand:

```
tool(verb)@{target}|{payload}
```

Examples:
```
clock_calendar(get)@time|Asia/Dhaka
notes(save)@groceries|Milk, eggs, bread
libretranslate(translate)@bn|"Hello world | en"
```

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
│   └── libretranslate/         # Self-hosted translation (argos-translate)
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
    def execute(self, verb: str, target: str, payload: Optional[str],
                metadata: dict, ctx: ExecutionContext) -> CommandResult: ...

    def validate(self, verb, target, payload, metadata) -> Optional[str]:
        return None  # Override to block calls with an error string
```

**CommandResult** — standard result wrapper:
```python
CommandResult.ok(value)       # success=True
CommandResult.fail(msg)       # success=False + error message
```

Fields: `success`, `value`, `error`, `tool`, `verb`, `target`

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
    payload_hint="value, date, time, ...",
    risk_tier=RiskTier.SAFE,
    metadata_schema=None,
    requires_confirmation=False,
)
```

**Tool discovery** — automatic from filesystem:
```python
discover_tools()          # Returns all valid manifest dicts from tools/*/manifest.json
load_manifest(name)       # Returns raw JSON dict for a specific tool
load_tool_class(name)     # Dynamically imports the BaseTool subclass
tool_dir(name)            # Maps tool name to directory name (e.g. "clock_calendar" → "clock_and_calendar")
```

Convention: `tools/{dir}/{tool_name}_tool.py` contains a class inheriting `BaseTool`.

### 3.3 Router (`core/router.py`)

Routes tool calls through a 6-step validation pipeline:

1. **Tool exists** — checks `self._tools` registry
2. **Verb valid** — checks against the tool's `manifest.actions`
3. **Target valid** — checks against `v@p` map (when targets are literal strings)
4. **Payload valid** — resolved via `$ref` placeholders
5. **Confirmation** — required for flagged commands
6. **Execute** — calls `tool.execute()`

On failure, returns a manifest format hint so the AI can self-correct.

**User input translation:**
```python
router.route_user_input(text)  # Returns (translated_to_english, original_text)
```

### 3.4 Parser (`core/parser.py`)

**CommandNode** dataclass — a single parsed tool invocation:

```python
CommandNode(
    verb="get",              # Action to perform
    tool="clock_calendar",   # Target tool name
    target="current_time",   # Primary resource
    payload="Asia/Dhaka",    # Data or parameters
    meta={},                 # Extra metadata key-value pairs
    requires_confirm=False,  # If True, user must approve
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
| `tools/list`              | Returns all registered tool definitions  |
| `tools/call`              | Executes a single tool call              |
| `notifications/initialized` | Ignored (no-op)                        |
| `notifications/cancelled` | Ignored (no-op)                          |

**Batch execution:** JSON-RPC arrays are processed in parallel using a thread pool (4 workers).

**Tool definition format** (sent to LM Studio):
```json
{
  "name": "clock_calendar",
  "description": "Time, date, moon...\nRisk: SAFE\nStructured command fields:\n...",
  "inputSchema": {
    "type": "object",
    "properties": {
      "verb": { "type": "string", "enum": ["get", "set", "delete"] },
      "target": { "type": "string", "description": "..." },
      "payload": { "type": "string", "description": "..." }
    },
    "required": ["verb"]
  }
}
```

### 3.7 Engine (`core/engine.py`)

`CardinalSystemEngine` — LM Studio native API client.

**Configuration:**
```python
LM_STUDIO_URL = "http://localhost:1234"
MODEL = "lfm2.5-230m-fable-5"
```

**System prompt** — auto-generated from tool manifests at startup via `_build_system_prompt()`:
```
You are an autonomous AI assistant connected to the Cardinal system via MCP.
Available Tools: clock_calendar, notes, settings, libretranslate
Directives:
- ACTION REQUIRED: You MUST use tool calls to fetch dynamic information...
- NO ASSUMPTIONS: Never assume a request is already handled...
- EXECUTION: Always call the relevant tool(s)...
```

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

### 4.1 ClockCalendarTool (`tools/clock_and_calendar/`)

Time, moon phase, season, timezone, date, day-of-week, calendar conversion, date calculations, alarms, timers, stopwatch, and event scheduling.

| Field | Value |
|---|---|
| Tool name | `clock_calendar` |
| Verbs | `get`, `set`, `delete` |
| Risk Tier | SAFE / STATEFUL |

**GET targets:**

| Target | Payload | Description |
|--------|---------|-------------|
| `time` | tz (optional) | Current time |
| `date` | — | Current date (YYYY-MM-DD) |
| `datetime` | tz (optional) | Current date and time |
| `timezone` | — | User's configured timezone |
| `timezone` | `src to dst` | Convert timezone |
| `epoch` | — | Unix timestamp |
| `time_in_zone` | timezone name | Time in a specific zone |
| `next_weekday` | day name | Next occurrence of a weekday |
| `quarter` | — | Current quarter of the year |
| `week_number` | — | ISO week number |
| `sun` | `rise/set date tz` | Sunrise or sunset time |
| `moon` | date (optional) | Moon phase name |
| `season` | date (optional) | Current season |
| `phases` | — | Upcoming moon phases |
| `day_of_week` | date | Day of week for a date |
| `date_offset` | `date +/-days` | Date offset by N days |
| `is_leap_year` | year | Whether a year is a leap year |
| `between` | `d1 to d2 (days/weeks/months)` | Duration between two dates |
| `until` | time/date | Time remaining until target |
| `since` | time/date | Time elapsed since target |
| `calendar` | `date to hijri` | Calendar conversion |
| `time_format` | `time to 12h/24h` | Format time string |
| `alarms` | — | List all alarms |
| `timers` | — | List all timers |
| `stopwatch` | — | Get stopwatch state |
| `events` | — | List all events |

**SET targets:**

| Target | Payload | Description |
|--------|---------|-------------|
| `alarm` | `time label` | Set an alarm |
| `timer` | duration | Set a countdown timer |
| `stopwatch` | `start/stop/reset` | Control the stopwatch |
| `event` | `desc date time` | Schedule an event |

**DELETE targets:**

| Target | Payload | Description |
|--------|---------|-------------|
| `alarm` | id | Remove an alarm |
| `timer` | id | Remove a timer |
| `event` | id | Remove an event |

---

### 4.2 NotesTool (`tools/notes/`)

CRUD for `.md` notes saved in `memory/notes/`. Supports line-level editing, timestamps, and find/replace.

| Field | Value |
|---|---|
| Tool name | `notes` |
| Verbs | `list`, `read`, `save`, `append`, `delete`, `change`, `rename`, `search` |
| Risk Tier | STATEFUL |

**Verb reference:**

| Verb | Target | Payload | Description |
|------|--------|---------|-------------|
| `list` | — | — | List all note filenames with dates |
| `read` | filename | line/range (optional) | Read note or specific lines (`3` or `3-5`) |
| `save` | filename | content | Create/overwrite note. Auto-name from first 3 words if no target |
| `append` | filename | content | Append content to end of note |
| `delete` | filename | line/range (optional) | Delete whole file or specific lines |
| `change` | filename | `line \| new_content` | Replace a line |
| `change` | filename | `+line \| content` | Insert before a line |
| `change` | filename | `old -> new` | Find and replace |
| `rename` | filename | new_filename | Rename a note file |
| `search` | filename (optional) | keyword | Search within file or across all notes |

---

### 4.3 SettingsTool (`tools/settings/`)

User preferences that affect system behavior.

| Field | Value |
|---|---|
| Tool name | `settings` |
| Verbs | `get`, `set`, `delete` |
| Risk Tier | STATEFUL |

**Known settings:**

| Key | Example | Description |
|-----|---------|-------------|
| `timezone` | `Asia/Dhaka` | User timezone (IANA, offset, city, or country) |
| `time_format` | `12h` or `24h` | Time display format |
| `spoken_lang` | `bn` | TTS + display translation language code. Default: `bn` |
| `tone` | `casual` | Response tone |
| `name` | `Bob` | User's name |

**Verb reference:**

| Verb | Target | Payload | Description |
|------|--------|---------|-------------|
| `get` | `setting` | setting_name | Get a specific setting |
| `get` | `timezone` | — | Get timezone |
| `get` | `time_format` | — | Get time format |
| `get` | `spoken_lang` | — | Get spoken language |
| `get` | `list` | — | List all settings |
| `set` | `setting` | `name\|value` | Set any key-value pair |
| `set` | `timezone` | city/country/offset | Set timezone |
| `set` | `time_format` | `12h` or `24h` | Set time format |
| `set` | `spoken_lang` | language code | Set spoken language |
| `delete` | `setting` | setting_name | Delete a setting |

---

### 4.4 LibreTranslateTool (`tools/libretranslate/`)

Self-hosted machine translation using argos-translate. Supports 50 languages. Auto-downloads translation models on first use.

| Field | Value |
|---|---|
| Tool name | `libretranslate` |
| Verbs | `translate`, `detect`, `list` |
| Risk Tier | NETWORK |

**Available language codes:**

`ar` (Arabic), `az` (Azerbaijani), `bg` (Bulgarian), `bn` (Bengali), `ca` (Catalan), `cs` (Czech), `da` (Danish), `de` (German), `el` (Greek), `en` (English), `eo` (Esperanto), `es` (Spanish), `et` (Estonian), `eu` (Basque), `fa` (Persian), `fi` (Finnish), `fr` (French), `ga` (Irish), `gl` (Galician), `he` (Hebrew), `hi` (Hindi), `hu` (Hungarian), `id` (Indonesian), `it` (Italian), `ja` (Japanese), `ko` (Korean), `ky` (Kyrgyz), `lt` (Lithuanian), `lv` (Latvian), `ms` (Malay), `nb` (Norwegian Bokmal), `nl` (Dutch), `pb` (Pushto), `pl` (Polish), `pt` (Portuguese), `ro` (Romanian), `ru` (Russian), `sk` (Slovak), `sl` (Slovenian), `sq` (Albanian), `sv` (Swedish), `sw` (Swahili), `th` (Thai), `tl` (Tagalog), `tr` (Turkish), `uk` (Ukrainian), `ur` (Urdu), `vi` (Vietnamese), `zh` (Chinese Simplified), `zt` (Chinese Traditional)

**Verb reference:**

| Verb | Target | Payload | Description |
|------|--------|---------|-------------|
| `translate` | language_code | `text \| source_lang` | Translate text (source defaults to `en`) |
| `detect` | — | text to detect | Detect language of input text |
| `list` | `languages` | — | List all 50 supported languages |
| `list` | `installed` | — | List currently downloaded models |

**Examples:**
```
translate(bn)@"Hello world | en"   → translate English to Bengali
translate(en)@"Bonjour | fr"       → translate French to English
detect()|"Bonjour le monde"         → detect language (returns "fr (French)")
list()@languages|""                 → list all supported languages
```

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
Router.route_user_input() → argos-translate → English
    ↓
English text sent to AI (LM Studio)
    ↓
AI responds in English
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
    "results": [],
    "is_chat": true,
    "error": "",
    "stats": { "input_tokens": 327, "total_output_tokens": 283 },
    "raw_output": "..."
}
```

The `/api/chat` endpoint also:
- Auto-detects and translates non-English input to English
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
3. **LM Studio** (v0.4.0+) running with a model loaded
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

    def execute(self, verb, target, payload, metadata, ctx):
        if verb == "get":
            return handlers.handle_get(target, payload, metadata, ctx)
        if verb == "set":
            return handlers.handle_set(target, payload, metadata, ctx)
        return CommandResult.fail(f"Verb '{verb}' not supported by {self.manifest.name}")
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
    "actions": ["get", "set"],
    "target_hint": "greeting or setting_name",
    "payload_hint": "value to set",
    "manifest": {
        "example": { "action": "get", "target": "greeting", "payload": "" },
        "v@p": {
            "get": [["greeting", ""]],
            "set": [["setting_name", "value"]]
        }
    }
}
```

**Manifest fields:**
- `name` — tool name (must match directory and class naming convention)
- `description` — shown to the AI in tool definitions
- `risk_tier` — `SAFE`, `STATEFUL`, `NETWORK`, or `DESTRUCTIVE`
- `actions` — list of supported action verbs
- `target_hint` / `payload_hint` — human-readable hints
- `manifest.example` — example action/target/payload for the AI
- `manifest.v@p` — action → [[target, payload_format]] mapping for validation
- `manifest.examples` — array of examples (alternative to single `example`)

### Step 5: Registration

No manual registration needed. `core/mcp_server.py` auto-discovers all tools. Just ensure:

1. Directory is `tools/{name}/`
2. Python file is `tools/{name}/{name}_tool.py`
3. Class name is PascalCase of the tool name (e.g., `weather` → `WeatherTool`)
4. `manifest.json` exists with valid `name`, `description`, `actions`, `risk_tier`, and `manifest.v@p`
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

    def execute(self, verb, target, payload, metadata, ctx):
        if verb == "get":
            return fetch.handle_get(target, payload, metadata, ctx)
        return CommandResult.fail(f"Verb {verb} not supported by {self.manifest.name}")
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
    "actions": ["get"],
    "target_hint": "city_name",
    "payload_hint": "unit (celsius or fahrenheit)",
    "manifest": {
        "example": { "action": "get", "target": "London", "payload": "celsius" },
        "v@p": {
            "get": [["city_name", "celsius|fahrenheit"]]
        }
    }
}
```

No registration needed — tools are auto-discovered from `tools/*/manifest.json` by `core/mcp_server.py` using `load_tool_class()`.
