"""
Controlled Bright Data SERP connectivity smoke test.

This script makes exactly one real request using the format generated
by the Bright Data dashboard. It verifies authentication, zone access,
upstream status, and receipt of a non-empty response body.
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

    try:
        envelope = response.json()
    except ValueError as error:
        raise SystemExit(
            "Bright Data returned an unexpected non-JSON envelope."
        ) from error

    upstream_status = int(
        envelope.get("status_code", response.status_code)
    )
    response_body = envelope.get("body", "")

    if upstream_status >= 400:
        safe_preview = str(response_body)[:300]
        raise SystemExit(
            f"Bright Data upstream request failed with "
            f"status {upstream_status}: {safe_preview}"
        )

    if not response_body:
        raise SystemExit(
            "Bright Data accepted the request but returned an empty body."
        )

    print("Bright Data connectivity smoke test passed.")
    print(f"Outer HTTP status: {response.status_code}")
    print(f"Upstream status: {upstream_status}")
    print(f"Response body received: {len(str(response_body))} characters")
    print(f"Request duration: {elapsed_seconds:.2f} seconds")
    print("Real requests completed: exactly 1")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
