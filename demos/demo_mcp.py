"""
Demo: Personal Scheduling Agent using MCP Server Integration.

This demo shows how the agent uses the same Google Gmail and Calendar
functionality but accessed through a custom MCP (Model Context Protocol)
server running as a subprocess.

Architecture:
    User Prompt
        │
        ▼
    LangGraph ReAct Agent (Claude / GPT-4o / Gemini)
        │ uses
        ▼
    MCP Tools (via langchain-mcp-adapters):
        └── Google Services MCP Server (subprocess, stdio)
                ├── read_emails       → Gmail API
                ├── create_meeting    → Calendar API (+ Meet)
                └── list_calendar_events → Calendar API

The agent code is identical to the direct API demo — only the tool
set changes. This demonstrates the MCP abstraction layer.

Run:
    python demos/demo_mcp.py
    python demos/demo_mcp.py --llm openai
    python demos/demo_mcp.py --llm google --query "is:unread subject:meeting"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from tools.mcp_tools.mcp_wrapper import load_mcp_tools
from agent.agent import create_scheduling_agent, run_agent


async def run_demo(query: str, llm_provider: str, custom_prompt: str | None = None):
    """Run the scheduling agent using MCP tools."""
    llm_labels = {"anthropic": "Claude (Anthropic)", "openai": "GPT-4o (OpenAI)", "google": "Gemini (Google)"}

    print("=" * 60)
    print("  Personal Scheduling Agent — MCP Server Approach")
    print("=" * 60)
    print(f"  Tool approach : MCP Server (stdio transport)")
    print(f"  MCP server    : mcp_server/google_services_server.py")
    print(f"  LLM           : {llm_labels.get(llm_provider, llm_provider)}")
    print(f"  Email filter  : {query}")
    print("=" * 60)
    print()

    print("🚀 Starting MCP server and connecting...")
    async with load_mcp_tools() as tools:
        print("✅ MCP server connected.\n")

        print("🛠️  Tools loaded (via MCP):")
        for t in tools:
            description = getattr(t, "description", "")
            print(f"   • {t.name}: {str(description)[:70]}...")
        print()

        agent = create_scheduling_agent(tools, llm_provider=llm_provider)

        user_prompt = custom_prompt or (
            f"Please check my emails (query: '{query}') and schedule any "
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


def main():
    parser = argparse.ArgumentParser(
        description="Personal Scheduling Agent — MCP Server Demo"
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

    asyncio.run(run_demo(query=args.query, llm_provider=args.llm_provider, custom_prompt=args.prompt))


if __name__ == "__main__":
    main()
