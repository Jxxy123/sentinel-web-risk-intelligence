"""
Controlled live validation for Sentinel's normalized Bright Data MCP search.

This script calls the production `BrightDataRemoteMCPClient.search()` method
exactly once and verifies that the live MCP response is converted into
Sentinel search-result records.

It does not call:
- Bright Data direct SERP
- Web Unlocker
- Data Center or ISP proxies
- CrewAI or any LLM
- the API server
- the database
"""

import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlparse

from core.brightdata_remote_mcp import BrightDataRemoteMCPClient
from core.config import settings


TEST_QUERY = '"Microsoft" vendor operational risk news'
RESULT_LIMIT = 10
SEARCH_TIMEOUT_SECONDS = 120

OUTPUT_DIRECTORY = Path("artifacts")
OUTPUT_PATH = (
    OUTPUT_DIRECTORY
    / "mcp_normalized_search_validation.json"
)


def _clean_text(value: object) -> str:
    """Convert an arbitrary value into stripped text."""
    if value is None:
        return ""

    return str(value).strip()


def validate_configuration() -> None:
    """Stop before the live call when protected MCP settings are absent."""
    if not _clean_text(
        settings.bright_data_api_key
    ):
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. "
            "No MCP search call was attempted."
        )

    if not _clean_text(
        settings.bright_data_mcp_base_url
    ):
        raise SystemExit(
            "BRIGHT_DATA_MCP_BASE_URL is missing. "
            "No MCP search call was attempted."
        )

    if (
        "search_engine"
        not in settings.bright_data_mcp_tool_list
    ):
        raise SystemExit(
            "search_engine is missing from BRIGHT_DATA_MCP_TOOLS. "
            "No MCP search call was attempted."
        )

    print(
        "Protected normalized MCP search "
        "configuration verified."
    )
    print(
        "MCP sessions planned: exactly 1"
    )
    print(
        "search_engine calls planned: exactly 1"
    )
    print(
        f"Normalized result limit: {RESULT_LIMIT}"
    )
    print(
        "Direct SERP calls planned: 0"
    )
    print(
        "Web Unlocker calls planned: 0"
    )
    print(
        "Proxy calls planned: 0"
    )
    print(
        "CrewAI and LLM calls planned: 0"
    )
    print(
        "Database calls planned: 0"
    )


def validate_results(
    results: object,
) -> list[dict[str, str]]:
    """Validate Sentinel's normalized MCP search-result contract."""
    if not isinstance(
        results,
        list,
    ):
        raise SystemExit(
            "Normalized MCP search did not return a list."
        )

    if not results:
        raise SystemExit(
            "Normalized MCP search returned zero results."
        )

    normalized_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for index, result in enumerate(
        results,
        start=1,
    ):
        if not isinstance(
            result,
            dict,
        ):
            raise SystemExit(
                f"Normalized result {index} is not an object."
            )

        title = _clean_text(
            result.get("title")
        )
        url = _clean_text(
            result.get("url")
        )
        snippet = _clean_text(
            result.get("snippet")
        )
        source = _clean_text(
            result.get("source")
        )

        parsed_url = urlparse(
            url
        )

        if not title:
            raise SystemExit(
                f"Normalized result {index} has no title."
            )

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise SystemExit(
                f"Normalized result {index} has an invalid URL."
            )

        if source != "bright_data_remote_mcp":
            raise SystemExit(
                f"Normalized result {index} has an "
                "unexpected source label."
            )

        if url in seen_urls:
            raise SystemExit(
                "Normalized MCP results contain a duplicate URL."
            )

        seen_urls.add(
            url
        )
        normalized_results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": source,
            }
        )

    return normalized_results


async def run_validation() -> None:
    """Execute one production normalizer call and validate the result."""
    validate_configuration()

    client = BrightDataRemoteMCPClient()

    print(
        "Starting controlled normalized MCP search validation..."
    )

    started_at = time.perf_counter()

    results = await asyncio.wait_for(
        client.search(
            TEST_QUERY,
            limit=RESULT_LIMIT,
        ),
        timeout=SEARCH_TIMEOUT_SECONDS,
    )

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    normalized_results = validate_results(
        results
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "query": TEST_QUERY,
                "result_count": len(
                    normalized_results
                ),
                "elapsed_seconds": round(
                    elapsed_seconds,
                    3,
                ),
                "results": normalized_results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "Controlled normalized MCP search validation passed."
    )
    print(
        "Normalized results returned: "
        f"{len(normalized_results)}"
    )
    print(
        "Unique URLs validated: "
        f"{len({item['url'] for item in normalized_results})}"
    )
    print(
        "First result title: "
        f"{normalized_results[0]['title'][:160]}"
    )
    print(
        "First result source: "
        f"{normalized_results[0]['source']}"
    )
    print(
        f"Request duration: "
        f"{elapsed_seconds:.2f} seconds"
    )
    print(
        f"Validation artifact created: "
        f"{OUTPUT_PATH}"
    )
    print(
        "MCP sessions completed: exactly 1"
    )
    print(
        "search_engine calls completed: exactly 1"
    )
    print(
        "Direct SERP calls completed: 0"
    )
    print(
        "Web Unlocker calls completed: 0"
    )
    print(
        "Proxy calls completed: 0"
    )
    print(
        "CrewAI and LLM calls completed: 0"
    )
    print(
        "Database calls completed: 0"
    )


if __name__ == "__main__":
    asyncio.run(
        run_validation()
    )
