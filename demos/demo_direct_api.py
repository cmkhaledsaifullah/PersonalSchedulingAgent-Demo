"""
Demo: Personal Scheduling Agent using Direct Google API Integration.

This demo shows how the agent uses LangChain tools that call the
Google Gmail and Calendar APIs directly via google-api-python-client.

Architecture:
    User Prompt
        │
        ▼
    LangGraph ReAct Agent (Claude / GPT-4o / Gemini)
        │ uses
        ▼
    Direct API Tools:
        ├── ReadEmailsTool       → Gmail API
        ├── CreateCalendarEventTool → Calendar API (+ Meet)
        └── CreateMeetLinkTool   → Calendar API (Meet only)

Run:
    python demos/demo_direct_api.py
    python demos/demo_direct_api.py --llm openai
    python demos/demo_direct_api.py --llm google --query "is:unread subject:meeting"
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from auth.google_auth import get_google_credentials
from tools.direct_api import CreateCalendarEventTool, CreateMeetLinkTool, ReadEmailsTool
from agent.agent import create_scheduling_agent, run_agent


def build_tools():
    """Authenticate with Google and create direct API tool instances."""
    print("🔐 Authenticating with Google...")
    creds = get_google_credentials()
    print("✅ Authenticated.\n")

    return [
        ReadEmailsTool(credentials=creds),
        CreateCalendarEventTool(credentials=creds),
        CreateMeetLinkTool(credentials=creds),
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Personal Scheduling Agent — Direct API Demo"
    )
    parser.add_argument(
        "--llm",
        choices=["anthropic", "openai", "google"],
        default="anthropic",
        dest="llm_provider",
        help="LLM provider: 'anthropic' (Claude), 'openai' (GPT-4o), 'google' (Gemini). Default: anthropic",
    )
    parser.add_argument(
        "--query",
        default="is:unread",
        help="Gmail search query to filter emails (default: 'is:unread')",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Custom agent prompt. If omitted, uses the default scheduling prompt.",
    )
    args = parser.parse_args()

    llm_labels = {"anthropic": "Claude (Anthropic)", "openai": "GPT-4o (OpenAI)", "google": "Gemini (Google)"}

    print("=" * 60)
    print("  Personal Scheduling Agent — Direct API Approach")
    print("=" * 60)
    print(f"  Tool approach : Direct Google API calls")
    print(f"  LLM           : {llm_labels[args.llm_provider]}")
    print(f"  Email filter  : {args.query}")
    print("=" * 60)
    print()

    tools = build_tools()

    print("🛠️  Tools loaded (Direct API):")
    for t in tools:
        print(f"   • {t.name}: {t.description[:70]}...")
    print()

    agent = create_scheduling_agent(tools, llm_provider=args.llm_provider)

    user_prompt = args.prompt or (
        f"Please check my emails (query: '{args.query}') and schedule any "
        "meetings you find. For online meetings create a Google Meet link. "
        "For in-person meetings add the address to the calendar event. "
        "Send invites to all relevant participants."
    )

    print(f"💬 User prompt:\n   {user_prompt}\n")
    print("🤖 Agent is working...\n")
    print("-" * 60)

    response = run_agent(agent, user_prompt)

    print("\n" + "=" * 60)
    print("  Agent Response")
    print("=" * 60)
    print(response)
    print("=" * 60)


if __name__ == "__main__":
    main()
