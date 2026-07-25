"""
Controlled live test of Sentinel's structured Bright Data SERP client.

This script performs exactly one real SERP request and verifies that
Sentinel converts the returned HTML into structured search results.
"""

import asyncio
import time

from core.brightdata import BrightDataSERPClient
from core.config import settings


async def run_smoke_test() -> None:
    """Perform one real request through Sentinel's SERP client."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. No request was made."
        )

    if not settings.bright_data_serp_zone:
        raise SystemExit(
            "BRIGHT_DATA_SERP_ZONE is missing. No request was made."
        )

    print("Starting structured Bright Data SERP smoke test...")
    print(f"SERP zone: {settings.bright_data_serp_zone}")
    print("Planned real API requests: exactly 1")

    client = BrightDataSERPClient()
    started_at = time.perf_counter()

    results = await client.search(
        query='"Bright Data" official documentation',
        num_results=5,
        lang="en",
    )

    elapsed_seconds = time.perf_counter() - started_at

    if not results:
        raise SystemExit(
            "Bright Data returned HTML, but Sentinel extracted "
            "no structured results."
        )

    for result in results:
        if not result.get("title"):
            raise SystemExit(
                "A structured result is missing its title."
            )

        if not result.get("url"):
            raise SystemExit(
                "A structured result is missing its URL."
            )

        if result.get("source") != "bright_data_serp":
            raise SystemExit(
                "A structured result has an unexpected source tag."
            )

    print("Structured Bright Data SERP test passed.")
    print(f"Structured results returned: {len(results)}")
    print(f"Request duration: {elapsed_seconds:.2f} seconds")
    print("Real requests completed: exactly 1")

    for index, result in enumerate(results[:3], start=1):
        print(f"{index}. {result['title']}")
        print(f"   {result['url']}")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
