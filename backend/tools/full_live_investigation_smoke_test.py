"""
Controlled full live investigation smoke test for Sentinel Web-Risk.

This script executes one production-style point-in-time investigation through:
- Bright Data SERP API
- Bright Data Remote MCP search_engine
- Bright Data Web Unlocker
- Bright Data Data Center proxy with optional ISP fallback
- Six sequential CrewAI agents/tasks
- Deterministic risk scoring

It does not start the API server, modify the frontend, or write to the database.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agents.orchestrator import SentinelOrchestrator
from core.config import settings


TEST_VENDOR = "Microsoft"
TEST_LANGUAGE = "EN"
RUN_TIMEOUT_SECONDS = 720

OUTPUT_DIRECTORY = Path("artifacts")
OUTPUT_PATH = OUTPUT_DIRECTORY / "controlled_live_investigation.json"

REQUIRED_TOOLS = {
    "SERP API",
    "Remote MCP search_engine",
    "Web Unlocker",
    "Proxy Network",
}

VALID_RISK_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}


def _require_secret(
    value: str,
    name: str,
) -> None:
    """Fail locally without printing a protected value."""
    if not value.strip():
        raise SystemExit(
            f"{name} is missing. "
            "No full live investigation was attempted."
        )


def validate_configuration() -> None:
    """Verify all required live-provider settings before paid calls begin."""
    _require_secret(
        settings.openai_api_key,
        "OPENAI_API_KEY",
    )
    _require_secret(
        settings.bright_data_api_key,
        "BRIGHT_DATA_API_KEY",
    )
    _require_secret(
        settings.bright_data_proxy_user,
        "BRIGHT_DATA_PROXY_USER",
    )
    _require_secret(
        settings.bright_data_proxy_pass,
        "BRIGHT_DATA_PROXY_PASS",
    )

    required_text_settings = {
        "OPENAI_BASE_URL": settings.openai_base_url,
        "FREE_TIER_MODEL": settings.free_tier_model,
        "BRIGHT_DATA_SERP_ZONE": (
            settings.bright_data_serp_zone
        ),
        "BRIGHT_DATA_WEB_UNLOCKER_ZONE": (
            settings.bright_data_web_unlocker_zone
        ),
        "BRIGHT_DATA_MCP_BASE_URL": (
            settings.bright_data_mcp_base_url
        ),
        "BRIGHT_DATA_MCP_TOOLS": (
            settings.bright_data_mcp_tools
        ),
        "BRIGHT_DATA_PROXY_HOST": (
            settings.bright_data_proxy_host
        ),
    }

    missing = [
        name
        for name, value in required_text_settings.items()
        if not str(value).strip()
    ]

    if missing:
        raise SystemExit(
            "Missing live investigation configuration: "
            + ", ".join(missing)
            + ". No live investigation was attempted."
        )

    if (
        "search_engine"
        not in settings.bright_data_mcp_tool_list
    ):
        raise SystemExit(
            "search_engine is missing from BRIGHT_DATA_MCP_TOOLS. "
            "No live investigation was attempted."
        )

    provider_url = urlparse(
        settings.openai_base_url
    )

    if (
        provider_url.scheme not in {"http", "https"}
        or not provider_url.netloc
    ):
        raise SystemExit(
            "OPENAI_BASE_URL is invalid. "
            "No live investigation was attempted."
        )

    print("Protected full-investigation configuration verified.")
    print(f"AI provider host: {provider_url.netloc}")
    print(f"Configured model: {settings.free_tier_model}")
    print(f"SERP zone: {settings.bright_data_serp_zone}")
    print(
        "Web Unlocker zone: "
        f"{settings.bright_data_web_unlocker_zone}"
    )
    print(
        "MCP tools: "
        + ",".join(
            settings.bright_data_mcp_tool_list
        )
    )
    print(
        "Proxy endpoint: "
        f"{settings.bright_data_proxy_host}:"
        f"{settings.bright_data_proxy_port}"
    )
    print("Vendor investigations planned: exactly 1")
    print("Direct SERP requests planned: exactly 4")
    print("Remote MCP search calls planned: exactly 1")
    print("Web Unlocker calls planned: exactly 1")
    print("Data Center proxy calls planned: exactly 1")
    print("ISP proxy calls planned: 0 unless Data Center fails")
    print(
        "MCP scraper calls planned: 0 unless "
        "Web Unlocker returns no content"
    )
    print("CrewAI agents planned: exactly 6")
    print("CrewAI tasks planned: exactly 6")
    print("Database writes planned: 0")


async def progress_callback(
    payload: dict[str, Any],
) -> None:
    """Print controlled progress without exposing provider credentials."""
    stage = str(
        payload.get("stage", "unknown")
    )
    progress = int(
        payload.get("progress", 0)
    )
    message = str(
        payload.get("message", "")
    )

    print(
        f"[PROGRESS] {progress:>3}% "
        f"stage={stage}: {message}"
    )


def validate_report(
    report: dict[str, Any],
) -> None:
    """Validate the complete production-style report contract."""
    if report.get("status") != "completed":
        raise SystemExit(
            "The investigation did not return status='completed'."
        )

    if report.get("vendor_name") != TEST_VENDOR:
        raise SystemExit(
            "The report vendor name does not match the controlled input."
        )

    risk_score = report.get("risk_score")

    if (
        not isinstance(risk_score, (int, float))
        or isinstance(risk_score, bool)
        or not 0 <= risk_score <= 100
    ):
        raise SystemExit(
            "The report returned an invalid risk_score."
        )

    risk_level = str(
        report.get("risk_level", "")
    ).upper()

    if risk_level not in VALID_RISK_LEVELS:
        raise SystemExit(
            "The report returned an invalid risk_level."
        )

    confidence = report.get(
        "confidence_score"
    )

    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise SystemExit(
            "The report returned an invalid confidence_score."
        )

    disruption_probability = report.get(
        "disruption_probability"
    )

    if (
        not isinstance(
            disruption_probability,
            (int, float),
        )
        or isinstance(
            disruption_probability,
            bool,
        )
        or not 0 <= disruption_probability <= 1
    ):
        raise SystemExit(
            "The report returned an invalid "
            "disruption_probability."
        )

    executive_summary = str(
        report.get("executive_summary", "")
    ).strip()

    if len(executive_summary) < 80:
        raise SystemExit(
            "The executive summary is unexpectedly short."
        )

    risk_headline = str(
        report.get("risk_headline", "")
    ).strip()

    if len(risk_headline) < 20:
        raise SystemExit(
            "The risk headline is unexpectedly short."
        )

    key_findings = report.get(
        "key_findings"
    )

    if (
        not isinstance(key_findings, list)
        or not key_findings
    ):
        raise SystemExit(
            "The report contains no key findings."
        )

    sources = report.get("sources")

    if (
        not isinstance(sources, list)
        or not sources
    ):
        raise SystemExit(
            "The full investigation returned no cited sources."
        )

    for source in sources:
        if not isinstance(source, dict):
            raise SystemExit(
                "A source record is not an object."
            )

        source_url = str(
            source.get("url", "")
        ).strip()

        parsed_url = urlparse(source_url)

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise SystemExit(
                "The report contains an invalid source URL."
            )

    raw_intelligence = report.get(
        "raw_intelligence"
    )

    if not isinstance(
        raw_intelligence,
        dict,
    ):
        raise SystemExit(
            "raw_intelligence is missing from the report."
        )

    tools_used = set(
        raw_intelligence.get(
            "bright_data_tools_used",
            [],
        )
    )

    missing_tools = REQUIRED_TOOLS - tools_used

    if missing_tools:
        raise SystemExit(
            "The full live path did not return usable data from: "
            + ", ".join(
                sorted(missing_tools)
            )
        )

    search_count = raw_intelligence.get(
        "search_results_count"
    )

    if (
        not isinstance(search_count, int)
        or search_count < 1
    ):
        raise SystemExit(
            "No unique live intelligence results were recorded."
        )

    generated_at = str(
        report.get("generated_at", "")
    ).strip()

    if not generated_at:
        raise SystemExit(
            "The report is missing generated_at."
        )


async def run_investigation() -> None:
    """Run exactly one complete production-style investigation."""
    validate_configuration()

    orchestrator = SentinelOrchestrator(
        progress_callback=progress_callback,
    )

    print(
        "Starting controlled full live Sentinel investigation..."
    )
    print(f"Controlled vendor: {TEST_VENDOR}")

    started_at = time.perf_counter()

    report = await asyncio.wait_for(
        orchestrator.investigate_vendor(
            TEST_VENDOR,
            language=TEST_LANGUAGE,
        ),
        timeout=RUN_TIMEOUT_SECONDS,
    )

    elapsed_seconds = (
        time.perf_counter() - started_at
    )

    validate_report(report)

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tools_used = report[
        "raw_intelligence"
    ]["bright_data_tools_used"]

    print(
        "Controlled full live Sentinel investigation passed."
    )
    print(
        "Report status: "
        f"{report['status']}"
    )
    print(
        "Risk result: "
        f"{report['risk_score']}/100 "
        f"({report['risk_level']})"
    )
    print(
        "Confidence score: "
        f"{report['confidence_score']}"
    )
    print(
        "Disruption probability: "
        f"{report['disruption_probability']}"
    )
    print(
        "Unique search results: "
        f"{report['raw_intelligence']['search_results_count']}"
    )
    print(
        "Cited sources: "
        f"{len(report['sources'])}"
    )
    print(
        "Bright Data services with usable output: "
        + ", ".join(tools_used)
    )
    print(
        f"Total request duration: "
        f"{elapsed_seconds:.2f} seconds"
    )
    print(
        f"Report artifact created: {OUTPUT_PATH}"
    )
    print("Database writes completed: 0")


if __name__ == "__main__":
    asyncio.run(
        run_investigation()
    )
