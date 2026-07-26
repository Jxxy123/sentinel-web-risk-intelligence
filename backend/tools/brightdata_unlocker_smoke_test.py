"""
Controlled live Bright Data Web Unlocker smoke test.

This script performs exactly one real Web Unlocker request and verifies
that Sentinel receives a non-empty response.
"""

import asyncio
import time

from core.brightdata import BrightDataWebUnlocker
from core.config import settings


TEST_URL = (
    "https://geo.brdtest.com/welcome.txt"
    "?product=unlocker&method=api"
)


async def run_smoke_test() -> None:
    """Perform exactly one real Web Unlocker request."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. No request was made."
        )

    if not settings.bright_data_web_unlocker_zone:
        raise SystemExit(
            "BRIGHT_DATA_WEB_UNLOCKER_ZONE is missing. "
            "No request was made."
        )

    print("Starting controlled Web Unlocker smoke test...")
    print(
        "Unlocker zone: "
        f"{settings.bright_data_web_unlocker_zone}"
    )
    print("Planned real requests: exactly 1")

    client = BrightDataWebUnlocker()
    started_at = time.perf_counter()

    response_body = await client.fetch_url(
        TEST_URL,
        render_js=False,
    )

    elapsed_seconds = time.perf_counter() - started_at

    if not response_body or not response_body.strip():
        raise SystemExit(
            "Web Unlocker returned no usable response."
        )

    print("Bright Data Web Unlocker smoke test passed.")
    print(
        "Response body received: "
        f"{len(response_body)} characters"
    )
    print(
        f"Request duration: {elapsed_seconds:.2f} seconds"
    )
    print("Real requests completed: exactly 1")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
