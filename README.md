# Personal Scheduling Agent Demo

A personal AI agent that reads Gmail emails and automatically schedules
Google Calendar meetings — with Google Meet links for online meetings and
physical addresses for in-person meetings.

This project **demos two tool integration approaches** side by side:

| Approach | Description |
|---|---|
| **Direct API** | LangChain tools call Google APIs directly via `google-api-python-client` |
| **MCP Server** | A local [FastMCP](https://github.com/jlowin/fastmcp) server wraps the same APIs; the agent connects via stdio |

---

## Architecture

```
User Prompt
    │
    ▼
LangGraph ReAct Agent (Claude / GPT / Google)
    │
    ├── Direct API Approach ──────────────────────────────────┐
    │       ├── ReadEmailsTool          → Gmail API           │
    │       ├── CreateCalendarEventTool → Calendar API + Meet │
    │       └── CreateMeetLinkTool      → Calendar API        │
    │                                                         │
    └── MCP Server Approach ──────────────────────────────────┘
            └── Google Services MCP Server (subprocess/stdio)
                    ├── read_emails
                    ├── create_meeting
                    └── list_calendar_events
```

---

## Prerequisites

- Python 3.11+
- A Google Cloud project with **Gmail API** and **Google Calendar API** enabled
- An Anthropic API key

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/cmkhaledsaifullah/PersonalSchedulingAgent-Demo.git
cd PersonalSchedulingAgent-Demo
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 4. Set up Google OAuth2 credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable:
   - **Gmail API**
   - **Google Calendar API**
4. Go to **APIs & Services → Credentials**
5. Click **Create Credentials → OAuth 2.0 Client IDs** → Desktop app
6. Download the JSON file and save it as **`credentials.json`** in the project root
7. Also configure the **OAuth consent screen** (add your email as a test user)

On first run, a browser window will open for Google sign-in. After that,
the token is cached in `token.pickle`.

---

## Running the Demo

### Interactive menu (recommended for demos)

```bash
python main.py
```

You'll be prompted to choose an approach, LLM provider, Gmail query, and optionally a custom prompt.

### Direct API approach

```bash
python main.py --approach direct --llm anthropic   # Claude (default)
python main.py --approach direct --llm openai      # GPT-4o
python main.py --approach direct --llm google      # Gemini

# With a custom Gmail search query
python main.py --approach direct --llm openai --query "subject:meeting is:unread"

# With a custom prompt
python main.py --approach direct --llm anthropic --prompt "Schedule a 1:1 with john@example.com tomorrow at 3pm"
```

### MCP Server approach

```bash
python main.py --approach mcp --llm anthropic
python main.py --approach mcp --llm openai
python main.py --approach mcp --llm google

# Or run the demo script directly
python demos/demo_mcp.py --llm openai --query "is:unread subject:standup"
```

### Individual demo scripts

```bash
# Direct API demo
python demos/demo_direct_api.py --llm anthropic
python demos/demo_direct_api.py --llm openai

# MCP server demo
python demos/demo_mcp.py --llm google
```

## Evaluation Setup

This repo now includes two local evaluation harnesses in `evals/`.
Both use mocked tools so you can evaluate agent behavior without calling
real Gmail/Calendar APIs.

### Files

- `evals/run_eval.py` — tool-use evaluator (required/forbidden tool calls)
- `evals/run_response_eval.py` — response-quality evaluator
- `evals/scenarios/*.jsonl` — bucketed scenario datasets
- `evals/cases.jsonl` — single-file compatibility dataset

### Scenario buckets

- `meeting_requests`
- `reminder_tasks`
- `event_announcements`
- `ambiguous_intent`
- `multi_email_batch`

### Run tool-use evaluator (`run_eval.py`)

```bash
python evals/run_eval.py --llm google
python evals/run_eval.py --llm google --bucket all
python evals/run_eval.py --llm google --bucket meeting_requests
python evals/run_eval.py --llm google --cases evals/cases.jsonl
```

### Run response evaluator (`run_response_eval.py`)

```bash
python evals/run_response_eval.py --llm google --bucket all
python evals/run_response_eval.py --llm google --bucket ambiguous_intent
python evals/run_response_eval.py --llm openai --bucket reminder_tasks
```

### Case format

Each line in a `.jsonl` case file is a JSON object:

```json
{
  "id": "meeting_request",
  "prompt": "Check unread emails and schedule any meeting requests.",
  "must_call": ["read_emails", "create_calendar_event"],
  "must_not_call": ["create_reminder"],
  "response_min_chars": 30,
  "response_contains_any": ["scheduled", "calendar", "meeting"],
  "response_contains_all": []
}
```

Scoring in `run_eval.py` is pass/fail per case:

- A case fails if any tool in `must_call` was not used
- A case fails if any tool in `must_not_call` was used
- Overall score is `passed/total`

Scoring in `run_response_eval.py` is pass/fail per case:

- Response length must satisfy `response_min_chars` (default: 30)
- All tokens in `response_contains_all` must appear
- At least one token in `response_contains_any` must appear (if provided)

### `--llm` options

| Flag | Provider | Default model |
|---|---|---|
| `--llm anthropic` | Claude (Anthropic) | `claude-3-5-sonnet-20241022` |
| `--llm openai` | GPT-4o (OpenAI) | `gpt-4o` |
| `--llm google` | Gemini (Google) | `gemini-2.5-flash` |

Override the model per-provider in `.env`:
```
ANTHROPIC_MODEL=claude-3-opus-20240229
OPENAI_MODEL=gpt-4o-mini
GOOGLE_MODEL=gemini-1.5-flash
```

---

## Project Structure

```
PersonalSchedulingAgent-Demo/
├── credentials.json          ← Your Google OAuth2 secrets (not committed)
├── token.pickle              ← Cached OAuth token (auto-created, not committed)
├── .env                      ← Your API keys (not committed)
├── .env.example              ← Template for .env
├── requirements.txt
├── main.py                   ← Interactive CLI entry point
│
├── auth/
│   └── google_auth.py        ← OAuth2 flow + token caching
│
├── tools/
│   ├── direct_api/
│   │   ├── gmail_tool.py     ← LangChain tool: read Gmail emails
│   │   ├── calendar_tool.py  ← LangChain tool: create Calendar events
│   │   └── meet_tool.py      ← LangChain tool: create Meet links
│   └── mcp_tools/
│       └── mcp_wrapper.py    ← Connects to MCP server, loads tools
│
├── mcp_server/
│   └── google_services_server.py  ← FastMCP server (Gmail + Calendar tools)
│
├── agent/
│   ├── agent.py              ← LangGraph ReAct agent factory
│   └── prompts.py            ← Scheduling system prompt for Claude
│
└── demos/
    ├── demo_direct_api.py    ← Standalone direct API demo
    └── demo_mcp.py           ← Standalone MCP server demo
```

---

## How the Agent Decides Meeting Type

The agent reads email content and automatically detects:

- **Online meeting** → keywords like "video call", "Google Meet", "Zoom", "virtual", "remote"
  → creates a Google Calendar event with an auto-generated **Google Meet link**

- **In-person meeting** → keywords like a street address, "office", "coffee", "in-person"
  → creates a Google Calendar event with the **physical location/address**

---

## What the Agent Does (Step by Step)

1. **Reads emails** from Gmail using the specified query
2. **Identifies** which emails contain meeting requests
3. **Extracts** title, attendees, date/time, timezone, and meeting type
4. **Creates** a Google Calendar event with:
   - Attendee invitations (emails sent automatically)
   - Google Meet link (online) or location address (in-person)
5. **Confirms** the scheduled meeting with a summary

---

## MCP Server Details

The MCP server (`mcp_server/google_services_server.py`) exposes three tools:

| Tool | Description |
|---|---|
| `read_emails` | List and read Gmail messages |
| `create_meeting` | Create a Calendar event (online or in-person) |
| `list_calendar_events` | List upcoming Calendar events |

The server uses **stdio transport** (standard for local MCP servers) and is
launched as a subprocess by the MCP client in `tools/mcp_tools/mcp_wrapper.py`.

You can also inspect/test the MCP server independently:

```bash
# Run MCP development inspector
mcp dev mcp_server/google_services_server.py
```

---

## Files to NOT Commit

Add these to `.gitignore`:

```
.env
credentials.json
token.pickle
__pycache__/
*.pyc
```
