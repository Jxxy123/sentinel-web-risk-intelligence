"""
Controlled Bright Data SERP smoke test.

This script performs exactly one real SERP API request.
It does not run the complete Sentinel investigation pipeline.
"""

import asyncio
import time

from core.brightdata import BrightDataSERPClient
from core.config import settings


async def run_smoke_test() -> None:
    """Perform one real Bright Data SERP request."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. No request was made."
        )

    if not settings.bright_data_serp_zone:
        raise SystemExit(
            "BRIGHT_DATA_SERP_ZONE is missing. No request was made."
        )

    print("Starting controlled Bright Data smoke test...")
    print(f"SERP zone: {settings.bright_data_serp_zone}")
    print("Planned real API requests: 1")

    client = BrightDataSERPClient()
    started_at = time.perf_counter()

    results = await client.search(
        query='"Bright Data" official documentation',
        num_results=3,
        lang="en",
    )

    elapsed_seconds = time.perf_counter() - started_at

    if not results:
        raise SystemExit(
            "Smoke test failed: Bright Data returned no usable results. "
            "The API key, zone permission, or zone configuration may need checking."
        )

    print("Bright Data smoke test passed.")
    print(f"Usable results returned: {len(results)}")
    print(f"Request duration: {elapsed_seconds:.2f} seconds")

    for index, result in enumerate(results[:3], start=1):
        print(f"{index}. {result.get('title', 'Untitled result')}")
        print(f"   {result.get('url', 'No URL returned')}")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
