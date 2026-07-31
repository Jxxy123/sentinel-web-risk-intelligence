"""
Controlled Bright Data MCP search_engine smoke test.

This script creates one MCP session and performs exactly one genuine
search_engine tool call. It does not invoke scraping, CrewAI, proxies,
Web Unlocker, or the direct SERP API.
"""

import asyncio
import json
import time
from typing import Any

from core.brightdata_remote_mcp import BrightDataRemoteMCPClient
from core.config import settings


TEST_QUERY = "Example Domain IANA official website"
SEARCH_TIMEOUT_SECONDS = 90


async def execute_single_search() -> dict[str, Any]:
    """Connect and perform exactly one search_engine call."""
    async with BrightDataRemoteMCPClient() as client:
        tools = await client.list_tools()

        search_tool = next(
            (
                tool
                for tool in tools
                if tool.get("name") == "search_engine"
            ),
            None,
        )

        if search_tool is None:
            raise RuntimeError(
                "The Remote MCP server did not expose search_engine."
            )

        input_schema = search_tool.get("input_schema") or {}
        properties = input_schema.get("properties") or {}

        if "query" not in properties:
            raise RuntimeError(
                "search_engine does not expose the expected "
                "'query' argument."
            )

        return await client.call_tool(
            "search_engine",
            {
                "query": TEST_QUERY,
            },
        )


async def run_smoke_test() -> None:
    """Verify one genuine Remote MCP search operation."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. "
            "No MCP session or search call was attempted."
        )

    if not settings.bright_data_mcp_base_url:
        raise SystemExit(
            "BRIGHT_DATA_MCP_BASE_URL is missing. "
            "No MCP session or search call was attempted."
        )

    if "search_engine" not in settings.bright_data_mcp_tool_list:
        raise SystemExit(
            "search_engine is not included in "
            "BRIGHT_DATA_MCP_TOOLS. No search was attempted."
        )

    print("Starting controlled MCP search_engine smoke test...")
    print("MCP authentication: protected API token present")
    print("MCP sessions planned: exactly 1")
    print("search_engine calls planned: exactly 1")
    print("scrape_as_markdown calls planned: 0")
    print("Direct SERP API calls planned: 0")
    print("CrewAI and LLM calls planned: 0")

    started_at = time.perf_counter()

    result = await asyncio.wait_for(
        execute_single_search(),
        timeout=SEARCH_TIMEOUT_SECONDS,
    )

    elapsed_seconds = time.perf_counter() - started_at

    if result.get("is_error"):
        raise SystemExit(
            "Bright Data MCP reported an error from search_engine."
        )

    text_content = str(result.get("text", "")).strip()
    structured_content = result.get("structured_content")

    serialized_structured = ""

    if structured_content is not None:
        serialized_structured = json.dumps(
            structured_content,
            ensure_ascii=False,
            default=str,
        )

    combined_output = (
        text_content + "\n" + serialized_structured
    ).strip()

    if not combined_output:
        raise SystemExit(
            "search_engine returned no usable result content."
        )

    if len(combined_output) < 20:
        raise SystemExit(
            "search_engine returned an unexpectedly small response."
        )

    print("Bright Data MCP search_engine smoke test passed.")
    print(
        "Search-result characters received: "
        f"{len(combined_output)}"
    )
    print(f"Request duration: {elapsed_seconds:.2f} seconds")
    print("search_engine calls completed: exactly 1")
    print("scrape_as_markdown calls completed: 0")
    print("Direct SERP API calls completed: 0")
    print("CrewAI and LLM calls completed: 0")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
