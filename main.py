"""
Personal Scheduling Agent — Interactive CLI Entry Point.

Lets you choose between two integration approaches and three LLM providers:

  Approaches:
    1. Direct API  — tools call Google APIs directly via google-api-python-client
    2. MCP Server  — tools are served by a local FastMCP server over stdio

  LLM providers (--llm):
    anthropic  → Claude  (default)
    openai     → GPT-4o
    google     → Gemini

Usage:
    python main.py
    python main.py --approach direct --llm anthropic
    python main.py --approach direct --llm openai
    python main.py --approach mcp    --llm google
    python main.py --approach direct --llm openai --query "subject:meeting is:unread"
    python main.py --approach mcp    --llm google --prompt "Schedule a team sync tomorrow at 2pm"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()


def run_direct(query: str, prompt: str | None, llm_provider: str):
    """Run the agent using direct Google API tools."""
    from auth.google_auth import get_google_credentials
    from tools.direct_api import CreateCalendarEventTool, CreateMeetLinkTool, ReadEmailsTool, CreateReminderTool
    from agent.agent import create_scheduling_agent, run_agent

    print("\n🔐 Authenticating with Google...")
    creds = get_google_credentials()
    print("✅ Authenticated.\n")

    tools = [
        ReadEmailsTool(credentials=creds),
        CreateCalendarEventTool(credentials=creds),
        CreateMeetLinkTool(credentials=creds),
        CreateReminderTool(credentials=creds),
    ]

    agent = create_scheduling_agent(tools, llm_provider=llm_provider)

    user_prompt = prompt or (
        f"Please check my emails (query: '{query}') and handle each one appropriately: "
        "schedule a meeting with the sender if they're requesting to meet, "
        "create a personal reminder if the email asks me to do something (like call an office), "
        "or block the date on my calendar if the email announces an event or date I should attend. "
        "Process all emails and confirm each action taken."
    )

    print(f"💬 Prompt: {user_prompt}\n")
    print("🤖 Agent is working...\n" + "-" * 60)

    response = run_agent(agent, user_prompt)
    print("\n" + "=" * 60)
    print(response)
    print("=" * 60)


async def run_mcp(query: str, prompt: str | None, llm_provider: str):
    """Run the agent using MCP server tools."""
    from tools.mcp_tools.mcp_wrapper import load_mcp_tools
    from agent.agent import create_scheduling_agent, run_agent

    print("\n🚀 Starting MCP server...")
    async with load_mcp_tools() as tools:
        print("✅ MCP server ready.\n")

        agent = create_scheduling_agent(tools, llm_provider=llm_provider)

    user_prompt = prompt or (
        f"Please check my emails (query: '{query}') and handle each one appropriately: "
        "schedule a meeting with the sender if they're requesting to meet, "
        "create a personal reminder if the email asks me to do something (like call an office), "
        "or block the date on my calendar if the email announces an event or date I should attend. "
        "Process all emails and confirm each action taken."
    )

    print(f"💬 Prompt: {user_prompt}\n")
    print("🤖 Agent is working...\n" + "-" * 60)

    response = run_agent(agent, user_prompt)
    print("\n" + "=" * 60)
    print(response)
    print("=" * 60)


def interactive_menu() -> tuple[str, str, str, str | None]:
    """Interactive menu when no CLI flags are provided."""
    print("\n" + "=" * 60)
    print("  🤖  Personal Scheduling Agent Demo")
    print("=" * 60)
    print("  Powered by LangGraph + Google APIs")
    print("=" * 60 + "\n")

    print("Choose integration approach:")
    print("  [1] Direct API  — calls Google APIs directly")
    print("  [2] MCP Server  — routes through a local MCP server\n")

    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in ("1", "2"):
            break
        print("Please enter 1 or 2.")

    approach = "direct" if choice == "1" else "mcp"

    print("\nChoose LLM provider:")
    print("  [1] Anthropic — Claude (default)")
    print("  [2] OpenAI    — GPT-4o")
    print("  [3] Google    — Gemini\n")

    llm_map = {"1": "anthropic", "2": "openai", "3": "google"}
    while True:
        llm_choice = input("Enter choice (1/2/3) [default: 1]: ").strip() or "1"
        if llm_choice in llm_map:
            break
        print("Please enter 1, 2, or 3.")
    llm_provider = llm_map[llm_choice]

    query = input("\nGmail search query [default: is:unread]: ").strip() or "is:unread"

    print("\nCustom prompt? Press Enter to use the default scheduling prompt.")
    prompt = input("Prompt: ").strip() or None

    return approach, llm_provider, query, prompt


def main():
    parser = argparse.ArgumentParser(
        description="Personal Scheduling Agent — Interactive Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                             # interactive menu
  python main.py --approach direct --llm anthropic          # Claude + direct API
  python main.py --approach direct --llm openai             # GPT-4o + direct API
  python main.py --approach mcp    --llm google             # Gemini + MCP server
  python main.py --approach direct --llm openai --query "subject:standup is:unread"
  python main.py --approach mcp    --llm google --prompt "Schedule a 1:1 with john@example.com tomorrow at 3pm"
        """,
    )
    parser.add_argument(
        "--approach",
        choices=["direct", "mcp"],
        default=None,
        help="Integration approach: 'direct' (Google API) or 'mcp' (MCP server)",
    )
    parser.add_argument(
        "--llm",
        choices=["anthropic", "openai", "google"],
        default=None,
        dest="llm_provider",
        help="LLM provider: 'anthropic' (Claude), 'openai' (GPT-4o), 'google' (Gemini). Default: anthropic",
    )
    parser.add_argument(
        "--query",
        default="is:unread",
        help="Gmail search query (default: 'is:unread')",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Custom agent prompt",
    )
    args = parser.parse_args()

    if args.approach is None:
        # Interactive mode
        approach, llm_provider, query, prompt = interactive_menu()
    else:
        approach = args.approach
        llm_provider = args.llm_provider or os.getenv("LLM_PROVIDER", "anthropic")
        query = args.query
        prompt = args.prompt

    llm_labels = {"anthropic": "Claude (Anthropic)", "openai": "GPT-4o (OpenAI)", "google": "Gemini (Google)"}
    approach_label = "Direct API" if approach == "direct" else "MCP Server"

    print(f"\n{'=' * 60}")
    print(f"  🚀 Approach : {approach_label}")
    print(f"  🧠 LLM      : {llm_labels.get(llm_provider, llm_provider)}")
    print(f"{'=' * 60}")

    if approach == "direct":
        run_direct(query=query, prompt=prompt, llm_provider=llm_provider)
    else:
        asyncio.run(run_mcp(query=query, prompt=prompt, llm_provider=llm_provider))


if __name__ == "__main__":
    main()
