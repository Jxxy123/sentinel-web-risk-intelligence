"""
Controlled Bright Data MCP search response-shape diagnostic.

This diagnostic performs exactly one genuine Remote MCP `search_engine` call,
records the serializable response shape, and applies Sentinel's existing
normalizer to the same response.

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
import re
import time
from pathlib import Path
from typing import Any

from core.brightdata_remote_mcp import BrightDataRemoteMCPClient
from core.config import settings


TEST_QUERY = '"Microsoft" vendor operational risk news'
DIAGNOSTIC_TIMEOUT_SECONDS = 120

OUTPUT_DIRECTORY = Path("artifacts")
OUTPUT_PATH = (
    OUTPUT_DIRECTORY
    / "mcp_search_shape_diagnostic.json"
)

MAX_LOG_PREVIEW_CHARACTERS = 800
MAX_SHAPE_DEPTH = 4


def _clean_text(value: Any) -> str:
    """Convert an arbitrary value into stripped text."""
    if value is None:
        return ""

    return str(value).strip()


def _safe_text_preview(
    text: str,
    limit: int = MAX_LOG_PREVIEW_CHARACTERS,
) -> str:
    """Return a compact public-data preview without control characters."""
    normalized = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return normalized[:limit]


def _strip_code_fences(text: str) -> str:
    """Remove common Markdown code fences before JSON parsing."""
    normalized = text.strip()

    if normalized.startswith("```"):
        normalized = re.sub(
            r"^```(?:json|JSON)?\s*",
            "",
            normalized,
        )
        normalized = re.sub(
            r"\s*```$",
            "",
            normalized,
        )

    return normalized.strip()


def _try_parse_json(
    text: str,
) -> Any:
    """Parse text as JSON and return None when it is not JSON."""
    normalized = _strip_code_fences(
        text
    )

    if not normalized:
        return None

    try:
        return json.loads(
            normalized
        )
    except json.JSONDecodeError:
        return None


def _describe_shape(
    value: Any,
    depth: int = 0,
) -> dict[str, Any]:
    """
    Build a bounded structural description without duplicating full content.
    """
    description: dict[str, Any] = {
        "type": type(value).__name__,
    }

    if depth >= MAX_SHAPE_DEPTH:
        description["truncated_at_depth"] = depth
        return description

    if isinstance(value, dict):
        keys = [
            str(key)
            for key in value.keys()
        ]
        description["keys"] = keys

        description["children"] = {
            str(key): _describe_shape(
                child,
                depth + 1,
            )
            for key, child in list(
                value.items()
            )[:12]
        }

    elif isinstance(value, list):
        description["length"] = len(value)

        if value:
            description["first_item"] = (
                _describe_shape(
                    value[0],
                    depth + 1,
                )
            )

    elif isinstance(value, str):
        description["characters"] = len(value)
        description["preview"] = (
            _safe_text_preview(
                value,
                limit=200,
            )
        )

    elif value is None:
        description["value"] = None

    else:
        description["value"] = value

    return description


def _extract_public_urls(
    value: Any,
) -> list[str]:
    """Recursively collect public HTTP URLs from a serializable value."""
    found: list[str] = []
    seen: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
            return

        if isinstance(item, list):
            for child in item:
                visit(child)
            return

        if not isinstance(item, str):
            return

        for url in re.findall(
            r"https?://[^\s\"'<>)}\]]+",
            item,
        ):
            cleaned_url = url.rstrip(
                ".,;:"
            )

            if cleaned_url not in seen:
                seen.add(cleaned_url)
                found.append(cleaned_url)

    visit(value)

    return found


def validate_configuration() -> None:
    """Fail before the remote call when protected MCP settings are absent."""
    if not _clean_text(
        settings.bright_data_api_key
    ):
        raise SystemExit(
            "BRIGHT_DATA_API_KEY is missing. "
            "No MCP call was attempted."
        )

    if not _clean_text(
        settings.bright_data_mcp_base_url
    ):
        raise SystemExit(
            "BRIGHT_DATA_MCP_BASE_URL is missing. "
            "No MCP call was attempted."
        )

    if (
        "search_engine"
        not in settings.bright_data_mcp_tool_list
    ):
        raise SystemExit(
            "search_engine is missing from BRIGHT_DATA_MCP_TOOLS. "
            "No MCP call was attempted."
        )

    print(
        "Protected MCP diagnostic configuration verified."
    )
    print(
        "MCP sessions planned: exactly 1"
    )
    print(
        "search_engine calls planned: exactly 1"
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


async def execute_diagnostic() -> None:
    """Perform one MCP search call and inspect its serializable shape."""
    validate_configuration()

    started_at = time.perf_counter()

    async with BrightDataRemoteMCPClient() as client:
        tools = await client.list_tools()

        exposed_tool_names = {
            _clean_text(
                tool.get("name")
            )
            for tool in tools
        }

        if "search_engine" not in exposed_tool_names:
            raise SystemExit(
                "The connected MCP server did not expose search_engine."
            )

        result = await asyncio.wait_for(
            client.call_tool(
                "search_engine",
                {
                    "query": TEST_QUERY,
                },
            ),
            timeout=DIAGNOSTIC_TIMEOUT_SECONDS,
        )

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    if result.get("is_error"):
        raise SystemExit(
            "Bright Data MCP returned is_error=true "
            "for search_engine."
        )

    text = _clean_text(
        result.get("text")
    )
    structured_content = result.get(
        "structured_content"
    )
    content_blocks = result.get(
        "content",
        [],
    )

    parsed_text = _try_parse_json(
        text
    )

    normalized_results = (
        BrightDataRemoteMCPClient
        ._normalize_search_results(
            result
        )
    )

    public_urls = _extract_public_urls(
        result
    )

    diagnostic = {
        "query": TEST_QUERY,
        "elapsed_seconds": round(
            elapsed_seconds,
            3,
        ),
        "result_top_level_keys": list(
            result.keys()
        ),
        "is_error": bool(
            result.get("is_error")
        ),
        "text_characters": len(text),
        "text_preview": _safe_text_preview(
            text
        ),
        "text_is_json": (
            parsed_text is not None
        ),
        "text_json_shape": (
            _describe_shape(
                parsed_text
            )
            if parsed_text is not None
            else None
        ),
        "structured_content_shape": (
            _describe_shape(
                structured_content
            )
        ),
        "content_blocks_shape": (
            _describe_shape(
                content_blocks
            )
        ),
        "raw_result_shape": (
            _describe_shape(
                result
            )
        ),
        "public_url_count": len(
            public_urls
        ),
        "public_url_samples": (
            public_urls[:5]
        ),
        "normalized_result_count": len(
            normalized_results
        ),
        "normalized_result_samples": (
            normalized_results[:3]
        ),
        "raw_serializable_result": result,
    }

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            diagnostic,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        "Bright Data MCP search response-shape "
        "diagnostic completed."
    )
    print(
        "Top-level result keys: "
        + ", ".join(
            diagnostic[
                "result_top_level_keys"
            ]
        )
    )
    print(
        f"Text characters: "
        f"{diagnostic['text_characters']}"
    )
    print(
        f"Text parses as JSON: "
        f"{diagnostic['text_is_json']}"
    )
    print(
        "Structured content type: "
        f"{type(structured_content).__name__}"
    )
    print(
        "Serialized content blocks: "
        f"{len(content_blocks)}"
    )
    print(
        "Public URLs detected recursively: "
        f"{diagnostic['public_url_count']}"
    )
    print(
        "Existing normalizer results: "
        f"{diagnostic['normalized_result_count']}"
    )

    if text:
        print(
            "Safe text preview: "
            + diagnostic["text_preview"]
        )

    if normalized_results:
        print(
            "Existing MCP normalizer recognized "
            "at least one result."
        )
    else:
        print(
            "[DIAGNOSTIC WARN] MCP returned usable "
            "content, but the existing normalizer "
            "recognized zero search results."
        )

    print(
        f"Request duration: "
        f"{elapsed_seconds:.2f} seconds"
    )
    print(
        f"Diagnostic artifact created: "
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
        execute_diagnostic()
    )
