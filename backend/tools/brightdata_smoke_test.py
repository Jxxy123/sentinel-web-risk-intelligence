"""
Controlled Bright Data SERP connectivity smoke test.

This script makes exactly one real request using the format generated
by the Bright Data dashboard. It verifies authentication, zone access,
HTTP status, and receipt of a non-empty response body.
"""

import asyncio
import time
from urllib.parse import quote_plus

import httpx

from core.config import settings


BRIGHT_DATA_REQUEST_URL = "https://api.brightdata.com/request"


async def run_smoke_test() -> None:
    """Perform exactly one real Bright Data SERP request."""

    if not settings.bright_data_api_key:
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. No request was made."
        )

    if not settings.bright_data_serp_zone:
        raise SystemExit(
            "BRIGHT_DATA_SERP_ZONE is missing. No request was made."
        )

    query = '"Bright Data" official documentation'
    encoded_query = quote_plus(query)

    payload = {
        "zone": settings.bright_data_serp_zone,
        "url": (
            "https://www.google.com/search"
            f"?q={encoded_query}&hl=en"
        ),
        "format": "raw",
        "data_format": "html",
    }

    headers = {
        "Authorization": f"Bearer {settings.bright_data_api_key}",
        "Content-Type": "application/json",
    }

    print("Starting controlled Bright Data connectivity test...")
    print(f"SERP zone: {settings.bright_data_serp_zone}")
    print("Planned real API requests: 1")

    started_at = time.perf_counter()

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            BRIGHT_DATA_REQUEST_URL,
            headers=headers,
            json=payload,
        )

    elapsed_seconds = time.perf_counter() - started_at

    response.raise_for_status()

    response_body = response.text

    if not response_body.strip():
        raise SystemExit(
            "Bright Data accepted the request but returned an empty body."
        )

    content_type = response.headers.get(
        "content-type",
        "not provided",
    )

    print("Bright Data connectivity smoke test passed.")
    print(f"HTTP status: {response.status_code}")
    print(f"Content type: {content_type}")
    print(f"Response body received: {len(response_body)} characters")
    print(f"Request duration: {elapsed_seconds:.2f} seconds")
    print("Real requests completed: exactly 1")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
