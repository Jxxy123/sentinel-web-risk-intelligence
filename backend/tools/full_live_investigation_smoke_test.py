"""
Controlled full live investigation smoke test for Sentinel Web-Risk.

This script executes one production-style point-in-time investigation through
the configured live providers. It accepts two valid completed outcomes:

1. COMPLETED
   Verified evidence is sufficient, a risk score is available, and at least
   one verified source is cited.

2. INSUFFICIENT_EVIDENCE
   Live retrieval completed, but no defensible score is assigned. Rejected or
   unverified candidates are not promoted into the final citation set, and AI
   synthesis is skipped.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agents.orchestrator import SentinelOrchestrator
from core.config import settings
from core.report_contract import validate_calibrated_report_contract


TEST_VENDOR = "Microsoft"
TEST_LANGUAGE = "EN"
RUN_TIMEOUT_SECONDS = 720

OUTPUT_DIRECTORY = Path("artifacts")
OUTPUT_PATH = OUTPUT_DIRECTORY / "controlled_live_investigation.json"

CORE_REQUIRED_TOOLS = {"SERP API"}
OPTIONAL_TOOLS = {
    "Remote MCP search_engine",
    "Remote MCP scrape_as_markdown",
    "Web Unlocker",
    "Proxy Network",
}

VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_EVIDENCE_STATUSES = {"COMPLETED", "INSUFFICIENT_EVIDENCE"}

MINIMUM_EXECUTIVE_SUMMARY_LENGTH = 80
MINIMUM_RISK_HEADLINE_LENGTH = 20


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _require_secret(value: str, name: str) -> None:
    if not _clean_text(value):
        raise SystemExit(
            f"{name} is missing. No full live investigation was attempted."
        )


def _require_setting(value: Any, name: str) -> None:
    if not _clean_text(value):
        raise SystemExit(
            f"{name} is missing. No full live investigation was attempted."
        )


def _warn_optional_configuration(condition: bool, message: str) -> None:
    if not condition:
        print("[CONFIG WARN] " + message)


def validate_configuration() -> None:
    """Verify required configuration before any paid calls begin."""
    _require_secret(settings.openai_api_key, "OPENAI_API_KEY")
    _require_secret(settings.bright_data_api_key, "BRIGHT_DATA_API_KEY")

    _require_setting(settings.openai_base_url, "OPENAI_BASE_URL")
    _require_setting(settings.free_tier_model, "FREE_TIER_MODEL")
    _require_setting(settings.bright_data_serp_zone, "BRIGHT_DATA_SERP_ZONE")
    _require_setting(
        settings.bright_data_serp_api_url,
        "BRIGHT_DATA_SERP_API_URL",
    )

    provider_url = urlparse(settings.openai_base_url)
    if (
        provider_url.scheme not in {"http", "https"}
        or not provider_url.netloc
    ):
        raise SystemExit(
            "OPENAI_BASE_URL is invalid. "
            "No full live investigation was attempted."
        )

    mcp_tools = set(settings.bright_data_mcp_tool_list)

    _warn_optional_configuration(
        bool(
            _clean_text(settings.bright_data_web_unlocker_zone)
            and _clean_text(settings.bright_data_web_unlocker_url)
        ),
        "Web Unlocker is not fully configured; that optional path may be skipped.",
    )
    _warn_optional_configuration(
        bool(
            _clean_text(settings.bright_data_mcp_base_url)
            and "search_engine" in mcp_tools
        ),
        "Remote MCP search_engine is not fully configured; "
        "that optional path may be skipped.",
    )
    _warn_optional_configuration(
        bool(
            _clean_text(settings.bright_data_proxy_host)
            and settings.has_proxy_credentials("data_center")
        ),
        "Data Center proxy is not fully configured; "
        "the optional proxy path may be skipped.",
    )

    print("Protected full-investigation configuration verified.")
    print(f"AI provider host: {provider_url.netloc}")
    print(f"Configured model: {settings.free_tier_model}")
    print(f"SERP zone: {settings.bright_data_serp_zone}")
    print("Vendor investigations planned: exactly 1")
    print("Direct SERP requests planned: exactly 4")
    print("Remote MCP search calls planned: up to 1")
    print("Web Unlocker calls planned: up to 1")
    print("Data Center proxy calls planned: up to 1")
    print("ISP proxy calls planned: 0 unless Data Center fails")
    print("MCP scraper calls planned: 0 unless Web Unlocker returns no usable content")
    print("CrewAI agents planned: up to 6 when verified evidence is sufficient")
    print("Database writes planned: 0")


async def progress_callback(payload: dict[str, Any]) -> None:
    stage = _clean_text(payload.get("stage")) or "unknown"
    try:
        progress = int(payload.get("progress", 0))
    except (TypeError, ValueError):
        progress = 0
    progress = max(0, min(progress, 100))
    message = _clean_text(payload.get("message"))
    print(f"[PROGRESS] {progress:>3}% stage={stage}: {message}")


def _validate_probability(value: Any, field_name: str) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= value <= 1
    ):
        raise SystemExit(f"The report returned an invalid {field_name}.")


def _resolve_outcome(
    report: dict[str, Any],
    raw_intelligence: dict[str, Any],
) -> tuple[str, bool]:
    top_status = _clean_text(
        report.get("evidence_assessment_status")
    ).upper()
    raw_status = _clean_text(
        raw_intelligence.get("evidence_assessment_status")
    ).upper()
    evidence_status = top_status or raw_status or "COMPLETED"

    if evidence_status not in VALID_EVIDENCE_STATUSES:
        raise SystemExit(
            "The report returned an invalid evidence_assessment_status."
        )

    if top_status and raw_status and top_status != raw_status:
        raise SystemExit(
            "Top-level and raw_intelligence evidence statuses do not match."
        )

    top_available = report.get("risk_score_available")
    raw_available = raw_intelligence.get("risk_score_available")
    values = [
        value
        for value in (top_available, raw_available)
        if value is not None
    ]

    for value in values:
        if not isinstance(value, bool):
            raise SystemExit("risk_score_available must be a boolean.")

    if len(values) == 2 and values[0] != values[1]:
        raise SystemExit(
            "Top-level and raw_intelligence risk_score_available values "
            "do not match."
        )

    score_available = (
        values[0] if values else evidence_status == "COMPLETED"
    )

    if score_available != (evidence_status == "COMPLETED"):
        raise SystemExit(
            "risk_score_available contradicts evidence_assessment_status."
        )

    return evidence_status, score_available


def _validate_source_records(
    sources: Any,
    *,
    require_sources: bool,
) -> None:
    if not isinstance(sources, list):
        raise SystemExit("sources must be a list.")

    if require_sources and not sources:
        raise SystemExit(
            "A scored investigation returned no verified cited sources."
        )

    if not require_sources and sources:
        raise SystemExit(
            "An INSUFFICIENT_EVIDENCE report promoted unverified sources "
            "into the final citation set."
        )

    seen_urls: set[str] = set()

    for source in sources:
        if not isinstance(source, dict):
            raise SystemExit("A source record is not an object.")

        source_url = _clean_text(source.get("url"))
        source_title = _clean_text(source.get("title"))
        source_provider = _clean_text(source.get("source"))
        parsed_url = urlparse(source_url)

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise SystemExit("The report contains an invalid source URL.")
        if not source_title:
            raise SystemExit("The report contains a source without a title.")
        if not source_provider:
            raise SystemExit(
                "The report contains a source without a provider label."
            )
        if source_url in seen_urls:
            raise SystemExit(
                "The report contains a duplicate source URL."
            )

        seen_urls.add(source_url)


def _validate_tools_used(
    raw_intelligence: dict[str, Any],
) -> list[str]:
    tools_value = raw_intelligence.get(
        "bright_data_tools_used",
        [],
    )
    if not isinstance(tools_value, list):
        raise SystemExit("bright_data_tools_used must be a list.")

    tools_used = [
        _clean_text(tool)
        for tool in tools_value
        if _clean_text(tool)
    ]
    tools_set = set(tools_used)

    missing_core_tools = CORE_REQUIRED_TOOLS - tools_set
    if missing_core_tools:
        raise SystemExit(
            "The investigation did not return usable data from the "
            "required core provider: "
            + ", ".join(sorted(missing_core_tools))
        )

    unavailable_optional_tools = OPTIONAL_TOOLS - tools_set
    if unavailable_optional_tools:
        print(
            "[VALIDATION WARN] Optional providers without usable output: "
            + ", ".join(sorted(unavailable_optional_tools))
        )

    unknown_tools = (
        tools_set - CORE_REQUIRED_TOOLS - OPTIONAL_TOOLS
    )
    if unknown_tools:
        print(
            "[VALIDATION WARN] Unrecognized provider labels: "
            + ", ".join(sorted(unknown_tools))
        )

    return tools_used


def _validate_no_score_outcome(
    report: dict[str, Any],
    raw_intelligence: dict[str, Any],
) -> None:
    """Validate a truthful insufficient-evidence result."""
    if report.get("risk_score") != 0:
        raise SystemExit(
            "INSUFFICIENT_EVIDENCE must use risk_score=0 only as an "
            "unavailable compatibility placeholder."
        )
    if _clean_text(report.get("risk_level")).upper() != "LOW":
        raise SystemExit(
            "INSUFFICIENT_EVIDENCE must use risk_level=LOW only as an "
            "unavailable compatibility placeholder."
        )
    if report.get("disruption_probability") != 0:
        raise SystemExit(
            "INSUFFICIENT_EVIDENCE must not expose a disruption probability."
        )
    if report.get("signals") != []:
        raise SystemExit(
            "INSUFFICIENT_EVIDENCE must not contain scored signals."
        )

    for field in (
        "verified_evidence_count",
        "verified_source_count",
        "authoritative_source_count",
        "verified_mcp_result_count",
    ):
        value = raw_intelligence.get(field, 0)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value != 0
        ):
            raise SystemExit(
                f"{field} must be zero for INSUFFICIENT_EVIDENCE."
            )

    if raw_intelligence.get("verified_evidence", []) != []:
        raise SystemExit(
            "INSUFFICIENT_EVIDENCE must not contain verified evidence."
        )

    if (
        raw_intelligence.get("llm_execution_status")
        != "skipped_insufficient_verified_evidence"
    ):
        raise SystemExit(
            "AI synthesis was not skipped for insufficient verified evidence."
        )


def validate_report(report: dict[str, Any]) -> list[str]:
    """Validate either a scored report or a truthful no-score outcome."""
    if not isinstance(report, dict):
        raise SystemExit(
            "The investigation did not return a report object."
        )
    if report.get("status") != "completed":
        raise SystemExit(
            "The investigation did not return status='completed'."
        )
    if _clean_text(report.get("vendor_name")) != TEST_VENDOR:
        raise SystemExit(
            "The report vendor name does not match the controlled input."
        )

    raw_intelligence = report.get("raw_intelligence")
    if not isinstance(raw_intelligence, dict):
        raise SystemExit(
            "raw_intelligence is missing from the report."
        )

    evidence_status, score_available = _resolve_outcome(
        report,
        raw_intelligence,
    )

    _validate_probability(
        report.get("confidence_score"),
        "confidence_score",
    )
    _validate_probability(
        report.get("disruption_probability"),
        "disruption_probability",
    )

    executive_summary = _clean_text(
        report.get("executive_summary")
    )
    if len(executive_summary) < MINIMUM_EXECUTIVE_SUMMARY_LENGTH:
        raise SystemExit(
            "The executive summary is unexpectedly short."
        )

    risk_headline = _clean_text(
        report.get("risk_headline")
    )
    if len(risk_headline) < MINIMUM_RISK_HEADLINE_LENGTH:
        raise SystemExit(
            "The risk headline is unexpectedly short."
        )

    key_findings = report.get("key_findings")
    if (
        not isinstance(key_findings, list)
        or not any(_clean_text(item) for item in key_findings)
    ):
        raise SystemExit("The report contains no key findings.")

    if score_available:
        risk_score = report.get("risk_score")
        if (
            not isinstance(risk_score, (int, float))
            or isinstance(risk_score, bool)
            or not 0 <= risk_score <= 100
        ):
            raise SystemExit(
                "The report returned an invalid risk_score."
            )

        risk_level = _clean_text(
            report.get("risk_level")
        ).upper()
        if risk_level not in VALID_RISK_LEVELS:
            raise SystemExit(
                "The report returned an invalid risk_level."
            )
    else:
        _validate_no_score_outcome(
            report,
            raw_intelligence,
        )

    _validate_source_records(
        report.get("sources"),
        require_sources=score_available,
    )

    try:
        validate_calibrated_report_contract(report)
    except ValueError as error:
        raise SystemExit(
            "Calibrated report contract failed: " + str(error)
        ) from error

    tools_used = _validate_tools_used(raw_intelligence)

    search_count = raw_intelligence.get(
        "search_results_count"
    )
    if (
        not isinstance(search_count, int)
        or isinstance(search_count, bool)
        or search_count < 1
    ):
        raise SystemExit(
            "No unique live intelligence results were recorded."
        )

    if not _clean_text(report.get("generated_at")):
        raise SystemExit("The report is missing generated_at.")

    print(
        "Evidence outcome: "
        f"{evidence_status}; "
        f"risk_score_available={score_available}"
    )
    return tools_used


def save_report_artifact(report: dict[str, Any]) -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Report artifact created: {OUTPUT_PATH}")


async def run_investigation() -> None:
    validate_configuration()

    orchestrator = SentinelOrchestrator(
        progress_callback=progress_callback,
    )

    print("Starting controlled full live Sentinel investigation...")
    print(f"Controlled vendor: {TEST_VENDOR}")

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

    elapsed_seconds = time.perf_counter() - started_at

    if not isinstance(report, dict):
        raise SystemExit(
            "The orchestrator returned a non-object result."
        )

    save_report_artifact(report)
    tools_used = validate_report(report)

    score_available = bool(
        report.get("risk_score_available")
    )
    evidence_status = _clean_text(
        report.get("evidence_assessment_status")
    )

    print("Controlled full live Sentinel investigation passed.")
    print(f"Report status: {report['status']}")
    print(f"Evidence assessment: {evidence_status}")

    if score_available:
        print(
            "Risk result: "
            f"{report['risk_score']}/100 "
            f"({report['risk_level']})"
        )
        print(
            "Disruption probability: "
            f"{report['disruption_probability']}"
        )
    else:
        print(
            "Risk result: unavailable "
            "(INSUFFICIENT_EVIDENCE)"
        )
        print("Disruption probability: unavailable")

    print(f"Confidence score: {report['confidence_score']}")
    print(
        "Unique search results: "
        f"{report['raw_intelligence']['search_results_count']}"
    )
    print(f"Cited verified sources: {len(report['sources'])}")
    print(
        "Bright Data services with usable output: "
        + ", ".join(tools_used)
    )
    print(f"Total request duration: {elapsed_seconds:.2f} seconds")
    print("Database writes completed: 0")


if __name__ == "__main__":
    asyncio.run(run_investigation())