"""
Controlled Bright Data MCP scrape_as_markdown smoke test.

This script makes exactly one real MCP scraper tool call against a
small public test page. It does not run search, browser automation,
CrewAI, or any other external provider.
"""

import asyncio
import time
from typing import Any

from core.brightdata_remote_mcp import BrightDataRemoteMCPClient
from core.config import settings


TEST_URL = "https://example.com"
SCRAPE_TIMEOUT_SECONDS = 90


async def execute_single_scrape() -> dict[str, Any]:
    """Connect and execute exactly one scrape_as_markdown call."""
    async with BrightDataRemoteMCPClient() as client:
        return await client.call_tool(
            "scrape_as_markdown",
            {
                "url": TEST_URL,
            },
        )


async def run_smoke_test() -> None:
    """Verify one genuine MCP scraping operation."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. "
            "No MCP connection or scraper call was attempted."
        )

    if not settings.bright_data_mcp_base_url:
        raise SystemExit(
            "BRIGHT_DATA_MCP_BASE_URL is missing. "
            "No MCP connection or scraper call was attempted."
        )

    configured_tools = settings.bright_data_mcp_tool_list

    if "scrape_as_markdown" not in configured_tools:
        raise SystemExit(
            "scrape_as_markdown is not included in "
            "BRIGHT_DATA_MCP_TOOLS. No tool call was attempted."
        )

    print("Starting controlled MCP scraper smoke test...")
    print("Target: public example test page")
    print("MCP connections planned: exactly 1")
    print("scrape_as_markdown calls planned: exactly 1")
    print("Other MCP tool calls planned: 0")

    started_at = time.perf_counter()

    result = await asyncio.wait_for(
        execute_single_scrape(),
        timeout=SCRAPE_TIMEOUT_SECONDS,
    )

    elapsed_seconds = time.perf_counter() - started_at

    if result.get("is_error"):
        raise SystemExit(
            "Bright Data MCP reported an error while scraping."
        )

    markdown = str(result.get("text", "")).strip()

    if not markdown:
        raise SystemExit(
            "scrape_as_markdown returned no usable text."
        )

    if "example domain" not in markdown.lower():
        raise SystemExit(
            "The scraper returned content, but the expected "
            "test-page text was not found."
        )

    print("Bright Data MCP scraper smoke test passed.")
    print(f"Markdown characters received: {len(markdown)}")
    print(f"Request duration: {elapsed_seconds:.2f} seconds")
    print("scrape_as_markdown calls completed: exactly 1")
    print("Other MCP tool calls completed: 0")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
