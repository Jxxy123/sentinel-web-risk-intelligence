"""
Controlled Bright Data Remote MCP connection smoke test.

This test opens one MCP session, discovers available tools, and closes
the session. It does not invoke any web-search or scraping tool.
"""

import asyncio
import time

from core.brightdata_remote_mcp import BrightDataRemoteMCPClient
from core.config import settings


REQUIRED_TOOLS = {
    "search_engine",
    "scrape_as_markdown",
}

CONNECTION_TIMEOUT_SECONDS = 60


async def inspect_remote_tools() -> list[dict[str, object]]:
    """Connect, list MCP tools, and close the session."""
    async with BrightDataRemoteMCPClient() as client:
        return await client.list_tools()


async def run_smoke_test() -> None:
    """Verify genuine Remote MCP connectivity without calling a tool."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. "
            "No MCP connection was attempted."
        )

    if not settings.bright_data_mcp_base_url:
        raise SystemExit(
            "BRIGHT_DATA_MCP_BASE_URL is missing. "
            "No MCP connection was attempted."
        )

    print("Starting controlled Bright Data Remote MCP test...")
    print("MCP authentication: protected API token present")
    print("MCP web-data tool calls planned: 0")
    print("Connection sessions planned: exactly 1")

    started_at = time.perf_counter()

    tools = await asyncio.wait_for(
        inspect_remote_tools(),
        timeout=CONNECTION_TIMEOUT_SECONDS,
    )

    elapsed_seconds = time.perf_counter() - started_at

    tool_names = sorted(
        {
            str(tool.get("name", "")).strip()
            for tool in tools
            if str(tool.get("name", "")).strip()
        }
    )

    print("Discovered MCP tools:")

    for tool_name in tool_names:
      
        print(f"- {tool_name}")
    
    missing_tools = sorted(
        REQUIRED_TOOLS.difference(tool_names)
    )

    if missing_tools:
        raise SystemExit(
            "Remote MCP connected, but required tools are missing: "
            + ", ".join(missing_tools)
        )

    print("Bright Data Remote MCP connection passed.")
    print(f"Available tools discovered: {len(tool_names)}")
    print("Required tools verified:")
    print("- search_engine")
    print("- scrape_as_markdown")

    if "session_stats" in tool_names:
        print("- session_stats")

    print(f"Session duration: {elapsed_seconds:.2f} seconds")
    print("MCP web-data tool calls completed: 0")
    print("Connection sessions completed: exactly 1")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
