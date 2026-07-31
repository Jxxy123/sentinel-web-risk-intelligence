"""
Controlled Bright Data ISP Proxy live smoke test.

This script performs exactly one small request through the configured
ISP proxy and verifies that a non-empty response is returned.
"""

import asyncio
import time

from core.brightdata import BrightDataProxyClient
from core.config import settings


TEST_URL = (
    "https://geo.brdtest.com/welcome.txt"
    "?product=isp&method=native"
)


async def run_smoke_test() -> None:
    """Perform exactly one request through the ISP proxy."""

    if not settings.bright_data_isp_proxy_user:
        raise SystemExit(
            "BRIGHT_DATA_ISP_PROXY_USER is missing. "
            "No request was made."
        )

    if not settings.bright_data_isp_proxy_pass:
        raise SystemExit(
            "BRIGHT_DATA_ISP_PROXY_PASS is missing. "
            "No request was made."
        )

    if not settings.bright_data_proxy_host:
        raise SystemExit(
            "BRIGHT_DATA_PROXY_HOST is missing. "
            "No request was made."
        )

    if not settings.bright_data_proxy_port:
        raise SystemExit(
            "BRIGHT_DATA_PROXY_PORT is missing. "
            "No request was made."
        )

    print("Starting controlled Bright Data ISP Proxy test...")
    print(f"Proxy host: {settings.bright_data_proxy_host}")
    print(f"Proxy port: {settings.bright_data_proxy_port}")
    print("ISP credentials: protected and present")
    print("Planned ISP requests: exactly 1")

    client = BrightDataProxyClient(
        default_proxy_type="isp",
    )

    started_at = time.perf_counter()

    response_body = await client.fetch_with_proxy(
        TEST_URL,
        proxy_type="isp",
    )

    elapsed_seconds = time.perf_counter() - started_at

    if not response_body or not response_body.strip():
        raise SystemExit(
            "Bright Data ISP Proxy returned no usable response."
        )

    print("Bright Data ISP Proxy smoke test passed.")
    print(
        "Response body received: "
        f"{len(response_body)} characters"
    )
    print(
        f"Request duration: {elapsed_seconds:.2f} seconds"
    )
    print("ISP requests completed: exactly 1")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
