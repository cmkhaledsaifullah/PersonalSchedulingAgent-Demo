"""
Scheduling agent factory.

Creates a LangGraph ReAct agent backed by a chosen LLM provider and
the provided set of tools. Works with both direct API tools and
MCP-loaded tools, since both produce LangChain BaseTool instances.

Supported LLM providers (set via --llm flag or LLM_PROVIDER env var):
  - anthropic  (default) → Claude via langchain-anthropic
  - openai               → GPT via langchain-openai
  - google               → Gemini via langchain-google-genai

Usage:
    # With direct API tools
    from tools.direct_api import ReadEmailsTool, CreateCalendarEventTool, CreateMeetLinkTool
    from auth import get_google_credentials

    creds = get_google_credentials()
    tools = [
        ReadEmailsTool(credentials=creds),
        CreateCalendarEventTool(credentials=creds),
        CreateMeetLinkTool(credentials=creds),
    ]
    agent = create_scheduling_agent(tools, llm_provider="openai")
    result = agent.invoke({"messages": [("user", "Check my emails and schedule any meetings.")]})

    # With MCP tools (async context required)
    from tools.mcp_tools import load_mcp_tools
    import asyncio

    async def run():
        async with load_mcp_tools() as tools:
            agent = create_scheduling_agent(tools, llm_provider="google")
            result = agent.invoke(...)
"""

import os
from typing import List, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from agent.prompts import SCHEDULING_AGENT_SYSTEM_PROMPT

LLMProvider = Literal["anthropic", "openai", "google"]

# Default models per provider (overridable via .env)
DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-3-5-sonnet-20241022",
    "openai": "gpt-4o",
    "google": "gemini-1.5-pro",
}


def build_llm(llm_provider: LLMProvider = "anthropic") -> BaseChatModel:
    """
    Instantiate and return the appropriate LangChain chat model.

    Model selection (in priority order):
      1. Provider-specific env var  (ANTHROPIC_MODEL / OPENAI_MODEL / GOOGLE_MODEL)
      2. Generic LLM_MODEL env var
      3. Hardcoded default for the provider

    Args:
        llm_provider: One of 'anthropic', 'openai', or 'google'.

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ValueError: If an unknown provider is specified.
    """
    provider = llm_provider.lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = (
            os.getenv("ANTHROPIC_MODEL")
            or os.getenv("LLM_MODEL")
            or DEFAULT_MODELS["anthropic"]
        )
        return ChatAnthropic(model=model, temperature=0, max_tokens=4096)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        model = (
            os.getenv("OPENAI_MODEL")
            or os.getenv("LLM_MODEL")
            or DEFAULT_MODELS["openai"]
        )
        return ChatOpenAI(model=model, temperature=0, max_tokens=4096)

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = (
            os.getenv("GOOGLE_MODEL")
            or os.getenv("LLM_MODEL")
            or DEFAULT_MODELS["google"]
        )
        return ChatGoogleGenerativeAI(model=model, temperature=0, max_output_tokens=4096)

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            "Choose from: 'anthropic', 'openai', 'google'."
        )


def create_scheduling_agent(
    tools: List[BaseTool],
    llm_provider: LLMProvider = "anthropic",
):
    """
    Build and return a LangGraph ReAct agent for scheduling.

    Args:
        tools:        List of LangChain BaseTool instances (direct API or MCP).
        llm_provider: LLM backend — 'anthropic' (default), 'openai', or 'google'.
                      Can also be set via the LLM_PROVIDER environment variable.

    Returns:
        A compiled LangGraph CompiledGraph (callable like a function).
        Call with: agent.invoke({"messages": [("human", "<your request>")]})
    """
    # Allow env var override of provider
    provider = os.getenv("LLM_PROVIDER", llm_provider)
    llm = build_llm(provider)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SCHEDULING_AGENT_SYSTEM_PROMPT,
    )

    return agent


def run_agent(agent, user_message: str) -> str:
    """
    Invoke the agent with a user message and return the final text response.

    Args:
        agent:        Compiled LangGraph agent from create_scheduling_agent().
        user_message: Natural language instruction for the agent.

    Returns:
        The agent's final response as a plain string.
    """
    result = agent.invoke({"messages": [("human", user_message)]})

    # Extract the last AI message content
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
            content = msg.content
            if isinstance(content, list):
                # Handle structured content (text blocks)
                return "\n".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                    if not (isinstance(block, dict) and block.get("type") == "tool_use")
                )
            return str(content)

    return "No response from agent."
