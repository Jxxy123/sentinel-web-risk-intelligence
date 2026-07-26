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
from core.report_contract import (
    validate_calibrated_report_contract,
)


TEST_VENDOR = "Microsoft"
TEST_LANGUAGE = "EN"
RUN_TIMEOUT_SECONDS = 720

OUTPUT_DIRECTORY = Path("artifacts")
OUTPUT_PATH = (
    OUTPUT_DIRECTORY
    / "controlled_live_investigation.json"
)

CORE_REQUIRED_TOOLS = {
    "SERP API",
}

OPTIONAL_TOOLS = {
    "Remote MCP search_engine",
    "Remote MCP scrape_as_markdown",
    "Web Unlocker",
    "Proxy Network",
}

VALID_RISK_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}

MINIMUM_EXECUTIVE_SUMMARY_LENGTH = 80
MINIMUM_RISK_HEADLINE_LENGTH = 20


def _clean_text(value: Any) -> str:
    """Convert an arbitrary value into stripped text."""
    if value is None:
        return ""

    return str(value).strip()


def _require_secret(
    value: str,
    name: str,
) -> None:
    """Fail locally without printing a protected value."""
    if not _clean_text(value):
        raise SystemExit(
            f"{name} is missing. "
            "No full live investigation was attempted."
        )


def _require_setting(
    value: Any,
    name: str,
) -> None:
    """Require a non-secret configuration value."""
    if not _clean_text(value):
        raise SystemExit(
            f"{name} is missing. "
            "No full live investigation was attempted."
        )


def _warn_optional_configuration(
    condition: bool,
    message: str,
) -> None:
    """Print a warning for an unavailable optional provider."""
    if not condition:
        print(
            "[CONFIG WARN] "
            + message
        )


def validate_configuration() -> None:
    """
    Verify required configuration before paid calls begin.

    The LLM and direct SERP path are core requirements for this controlled
    end-to-end run. Remote MCP, Web Unlocker, and proxy services are optional
    evidence providers because each has its own dedicated live smoke test.
    """
    _require_secret(
        settings.openai_api_key,
        "OPENAI_API_KEY",
    )
    _require_secret(
        settings.bright_data_api_key,
        "BRIGHT_DATA_API_KEY",
    )

    _require_setting(
        settings.openai_base_url,
        "OPENAI_BASE_URL",
    )
    _require_setting(
        settings.free_tier_model,
        "FREE_TIER_MODEL",
    )
    _require_setting(
        settings.bright_data_serp_zone,
        "BRIGHT_DATA_SERP_ZONE",
    )
    _require_setting(
        settings.bright_data_serp_api_url,
        "BRIGHT_DATA_SERP_API_URL",
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
            "No full live investigation was attempted."
        )

    mcp_tools = set(
        settings.bright_data_mcp_tool_list
    )

    _warn_optional_configuration(
        bool(
            _clean_text(
                settings.bright_data_web_unlocker_zone
            )
            and _clean_text(
                settings.bright_data_web_unlocker_url
            )
        ),
        (
            "Web Unlocker is not fully configured; "
            "that optional evidence path may be skipped."
        ),
    )

    _warn_optional_configuration(
        bool(
            _clean_text(
                settings.bright_data_mcp_base_url
            )
            and "search_engine" in mcp_tools
        ),
        (
            "Remote MCP search_engine is not fully configured; "
            "that optional evidence path may be skipped."
        ),
    )

    _warn_optional_configuration(
        bool(
            _clean_text(
                settings.bright_data_proxy_host
            )
            and settings.has_proxy_credentials(
                "data_center"
            )
        ),
        (
            "Data Center proxy is not fully configured; "
            "the optional proxy path may be skipped."
        ),
    )

    print(
        "Protected full-investigation "
        "configuration verified."
    )
    print(
        f"AI provider host: {provider_url.netloc}"
    )
    print(
        f"Configured model: "
        f"{settings.free_tier_model}"
    )
    print(
        f"SERP zone: "
        f"{settings.bright_data_serp_zone}"
    )
    print(
        "Web Unlocker zone: "
        + (
            settings.bright_data_web_unlocker_zone
            or "not configured"
        )
    )
    print(
        "MCP tools: "
        + (
            ",".join(
                settings.bright_data_mcp_tool_list
            )
            or "not configured"
        )
    )
    print(
        "Proxy endpoint: "
        + (
            (
                f"{settings.bright_data_proxy_host}:"
                f"{settings.bright_data_proxy_port}"
            )
            if settings.bright_data_proxy_host
            else "not configured"
        )
    )
    print(
        "Vendor investigations planned: exactly 1"
    )
    print(
        "Direct SERP requests planned: exactly 4"
    )
    print(
        "Remote MCP search calls planned: "
        "up to 1"
    )
    print(
        "Web Unlocker calls planned: up to 1"
    )
    print(
        "Data Center proxy calls planned: up to 1"
    )
    print(
        "ISP proxy calls planned: "
        "0 unless Data Center fails"
    )
    print(
        "MCP scraper calls planned: "
        "0 unless Web Unlocker returns no usable content"
    )
    print(
        "CrewAI agents planned: exactly 6"
    )
    print(
        "CrewAI tasks planned: exactly 6"
    )
    print(
        "Database writes planned: 0"
    )


async def progress_callback(
    payload: dict[str, Any],
) -> None:
    """Print controlled progress without exposing provider credentials."""
    stage = _clean_text(
        payload.get("stage")
    ) or "unknown"

    try:
        progress = int(
            payload.get("progress", 0)
        )
    except (TypeError, ValueError):
        progress = 0

    progress = max(
        0,
        min(progress, 100),
    )

    message = _clean_text(
        payload.get("message")
    )

    print(
        f"[PROGRESS] {progress:>3}% "
        f"stage={stage}: {message}"
    )


def _validate_probability(
    value: Any,
    field_name: str,
) -> None:
    """Validate a numeric probability in the inclusive 0–1 range."""
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= value <= 1
    ):
        raise SystemExit(
            f"The report returned an invalid "
            f"{field_name}."
        )


def _validate_source_records(
    sources: Any,
) -> None:
    """Validate source records and their absolute HTTP URLs."""
    if (
        not isinstance(sources, list)
        or not sources
    ):
        raise SystemExit(
            "The full investigation returned "
            "no cited sources."
        )

    for source in sources:
        if not isinstance(source, dict):
            raise SystemExit(
                "A source record is not an object."
            )

        source_url = _clean_text(
            source.get("url")
        )
        source_title = _clean_text(
            source.get("title")
        )

        parsed_url = urlparse(
            source_url
        )

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise SystemExit(
                "The report contains an invalid "
                "source URL."
            )

        if not source_title:
            raise SystemExit(
                "The report contains a source "
                "without a title."
            )


def _validate_tools_used(
    raw_intelligence: dict[str, Any],
) -> list[str]:
    """
    Validate provider traceability.

    Direct SERP is required for this controlled end-to-end test. Other
    providers are optional because provider availability may vary by target,
    robots policy, account product access, routing, and regional restrictions.
    """
    tools_value = raw_intelligence.get(
        "bright_data_tools_used",
        [],
    )

    if not isinstance(
        tools_value,
        list,
    ):
        raise SystemExit(
            "bright_data_tools_used must be a list."
        )

    tools_used = [
        _clean_text(tool)
        for tool in tools_value
        if _clean_text(tool)
    ]

    tools_set = set(
        tools_used
    )

    missing_core_tools = (
        CORE_REQUIRED_TOOLS - tools_set
    )

    if missing_core_tools:
        raise SystemExit(
            "The investigation did not return usable "
            "data from the required core provider: "
            + ", ".join(
                sorted(missing_core_tools)
            )
        )

    unavailable_optional_tools = (
        OPTIONAL_TOOLS - tools_set
    )

    if unavailable_optional_tools:
        print(
            "[VALIDATION WARN] Optional providers "
            "without usable evidence in this run: "
            + ", ".join(
                sorted(
                    unavailable_optional_tools
                )
            )
        )

    unknown_tools = (
        tools_set
        - CORE_REQUIRED_TOOLS
        - OPTIONAL_TOOLS
    )

    if unknown_tools:
        print(
            "[VALIDATION WARN] Unrecognized provider "
            "labels were recorded: "
            + ", ".join(
                sorted(unknown_tools)
            )
        )

    return tools_used


def validate_report(
    report: dict[str, Any],
) -> list[str]:
    """
    Validate the production-style report contract.

    Returns the normalized list of Bright Data services that produced usable
    evidence. Optional provider gaps are reported as warnings rather than
    causing a false end-to-end failure.
    """
    if not isinstance(
        report,
        dict,
    ):
        raise SystemExit(
            "The investigation did not return "
            "a report object."
        )

    if report.get("status") != "completed":
        raise SystemExit(
            "The investigation did not return "
            "status='completed'."
        )

    if (
        _clean_text(
            report.get("vendor_name")
        )
        != TEST_VENDOR
    ):
        raise SystemExit(
            "The report vendor name does not "
            "match the controlled input."
        )

    risk_score = report.get(
        "risk_score"
    )

    if (
        not isinstance(risk_score, (int, float))
        or isinstance(risk_score, bool)
        or not 0 <= risk_score <= 100
    ):
        raise SystemExit(
            "The report returned an invalid "
            "risk_score."
        )

    risk_level = _clean_text(
        report.get("risk_level")
    ).upper()

    if risk_level not in VALID_RISK_LEVELS:
        raise SystemExit(
            "The report returned an invalid "
            "risk_level."
        )

    _validate_probability(
        report.get("confidence_score"),
        "confidence_score",
    )
    _validate_probability(
        report.get(
            "disruption_probability"
        ),
        "disruption_probability",
    )

    executive_summary = _clean_text(
        report.get("executive_summary")
    )

    if (
        len(executive_summary)
        < MINIMUM_EXECUTIVE_SUMMARY_LENGTH
    ):
        raise SystemExit(
            "The executive summary is "
            "unexpectedly short."
        )

    risk_headline = _clean_text(
        report.get("risk_headline")
    )

    if (
        len(risk_headline)
        < MINIMUM_RISK_HEADLINE_LENGTH
    ):
        raise SystemExit(
            "The risk headline is "
            "unexpectedly short."
        )

    key_findings = report.get(
        "key_findings"
    )

    if (
        not isinstance(key_findings, list)
        or not any(
            _clean_text(item)
            for item in key_findings
        )
    ):
        raise SystemExit(
            "The report contains no key findings."
        )

    _validate_source_records(
        report.get("sources")
    )

    try:
        validate_calibrated_report_contract(
            report
        )
    except ValueError as error:
        raise SystemExit(
            "Calibrated report contract failed: "
            + str(error)
        ) from error

    raw_intelligence = report.get(
        "raw_intelligence"
    )

    if not isinstance(
        raw_intelligence,
        dict,
    ):
        raise SystemExit(
            "raw_intelligence is missing "
            "from the report."
        )

    tools_used = _validate_tools_used(
        raw_intelligence
    )

    search_count = raw_intelligence.get(
        "search_results_count"
    )

    if (
        not isinstance(search_count, int)
        or isinstance(search_count, bool)
        or search_count < 1
    ):
        raise SystemExit(
            "No unique live intelligence "
            "results were recorded."
        )

    generated_at = _clean_text(
        report.get("generated_at")
    )

    if not generated_at:
        raise SystemExit(
            "The report is missing generated_at."
        )

    return tools_used


def save_report_artifact(
    report: dict[str, Any],
) -> None:
    """
    Save the report before strict validation.

    Preserving the artifact allows provider and contract failures to be
    diagnosed without spending another complete six-agent live run.
    """
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        f"Report artifact created: {OUTPUT_PATH}"
    )


async def run_investigation() -> None:
    """Run exactly one complete production-style investigation."""
    validate_configuration()

    orchestrator = SentinelOrchestrator(
        progress_callback=progress_callback,
    )

    print(
        "Starting controlled full live "
        "Sentinel investigation..."
    )
    print(
        f"Controlled vendor: {TEST_VENDOR}"
    )

    started_at = time.perf_counter()

    try:
        report = await asyncio.wait_for(
            orchestrator.investigate_vendor(
                TEST_VENDOR,
                language=TEST_LANGUAGE,
            ),
            timeout=RUN_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as error:
        raise SystemExit(
            "The full investigation exceeded "
            f"{RUN_TIMEOUT_SECONDS} seconds."
        ) from error

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    if not isinstance(
        report,
        dict,
    ):
        raise SystemExit(
            "The orchestrator returned a "
            "non-object result."
        )

    # Save first so failed validation still leaves a diagnostic artifact.
    save_report_artifact(
        report
    )

    tools_used = validate_report(
        report
    )

    print(
        "Controlled full live Sentinel "
        "investigation passed."
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
        "Total request duration: "
        f"{elapsed_seconds:.2f} seconds"
    )
    print(
        "Database writes completed: 0"
    )


if __name__ == "__main__":
    asyncio.run(
        run_investigation()
    )
