"""
LangChain MCP Adapter — loads tools from the Google Services MCP Server.

This module connects to the local MCP server via stdio transport and
exposes its tools as LangChain-compatible tools using langchain-mcp-adapters.

Usage:
    async with load_mcp_tools() as tools:
        # tools is a list of LangChain BaseTool instances
        agent = create_scheduling_agent(tools)
        ...

The MCP server (mcp_server/google_services_server.py) must be reachable
as a Python module from the project root.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools as _load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Path to the MCP server entry point
PROJECT_ROOT = Path(__file__).parent.parent
MCP_SERVER_PATH = PROJECT_ROOT / "mcp_server" / "google_services_server.py"


@asynccontextmanager
async def load_mcp_tools() -> AsyncGenerator[List[BaseTool], None]:
    """
    Context manager that starts the Google Services MCP server as a subprocess,
    establishes an MCP session over stdio, and yields the server's tools as
    LangChain BaseTool instances.

    Example:
        async with load_mcp_tools() as tools:
            print([t.name for t in tools])
            # ['read_emails', 'create_meeting', 'list_calendar_events']

    Raises:
        FileNotFoundError: If the MCP server script cannot be found.
    """
    if not MCP_SERVER_PATH.exists():
        raise FileNotFoundError(
            f"MCP server script not found: {MCP_SERVER_PATH}\n"
            "Make sure you are running from the project root."
        )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SERVER_PATH)],
        env=None,  # Inherit environment (needed for GOOGLE_APPLICATION_CREDENTIALS etc.)
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await _load_mcp_tools(session)
            yield tools
