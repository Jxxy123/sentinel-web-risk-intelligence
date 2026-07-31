"""
Sentinel Web-Risk — Final Report Contract Validation.

This module validates that a completed report remains consistent with the
deterministic score, includes balanced provider traceability, and records
scraped-evidence provenance without raw page content.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from core.report_calibration import (
    calibrate_trajectory,
    derive_primary_category,
)


VALID_RISK_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}

LOW_RISK_FORBIDDEN_PHRASES = (
    "significant risk",
    "significant financial risk",
    "significant operational risk",
    "significant reputational risk",
    "severe risk",
    "critical threat",
    "major financial instability",
    "high likelihood",
    "substantial threat",
    "immediate threat",
)

SECRET_MARKERS = (
    "openai_api_key",
    "bright_data_api_key",
    "bright_data_proxy_pass",
    "authorization: bearer",
    '"bearer_token"',
)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValueError(message)


def _valid_http_url(value: Any) -> bool:
    parsed = urlparse(
        _clean_text(value)
    )

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


def _validate_level_score_alignment(
    score: Any,
    level: str,
) -> None:
    _require(
        isinstance(score, (int, float))
        and not isinstance(score, bool)
        and 0 <= score <= 100,
        "risk_score must be a number between 0 and 100.",
    )

    if score >= 70:
        expected = "CRITICAL"
    elif score >= 50:
        expected = "HIGH"
    elif score >= 25:
        expected = "MEDIUM"
    else:
        expected = "LOW"

    _require(
        level == expected,
        (
            "risk_level contradicts risk_score: "
            f"expected {expected}, received {level}."
        ),
    )


def _validate_low_risk_language(
    report: dict[str, Any],
) -> None:
    combined = " ".join(
        [
            _clean_text(
                report.get("executive_summary")
            ),
            _clean_text(
                report.get("risk_headline")
            ),
            *[
                _clean_text(item)
                for item in report.get(
                    "key_findings",
                    [],
                )
                if _clean_text(item)
            ],
        ]
    ).lower()

    detected = [
        phrase
        for phrase in LOW_RISK_FORBIDDEN_PHRASES
        if phrase in combined
    ]

    _require(
        not detected,
        (
            "LOW-risk report contains inflated wording: "
            + ", ".join(detected)
        ),
    )

    actions = " ".join(
        _clean_text(item)
        for item in report.get(
            "recommended_actions",
            [],
        )
    ).lower()

    _require(
        "continuously monitor" not in actions,
        (
            "Point-in-time report must not claim continuous "
            "monitoring."
        ),
    )


def _validate_sources(
    report: dict[str, Any],
    raw_intelligence: dict[str, Any],
    tools_used: set[str],
    *,
    require_citations: bool,
) -> None:
    """Validate the final verified citation set.

    Scored reports must cite at least one verified source. An
    INSUFFICIENT_EVIDENCE report must not promote rejected candidates into
    the final citation set merely to satisfy a non-empty-list requirement.
    """
    sources = report.get(
        "sources"
    )

    _require(
        isinstance(sources, list),
        "sources must be a list.",
    )

    if require_citations:
        _require(
            bool(sources),
            "A scored report must contain cited sources.",
        )
    else:
        _require(
            not sources,
            (
                "INSUFFICIENT_EVIDENCE reports must not cite "
                "rejected or unverified sources."
            ),
        )

    seen_urls: set[str] = set()

    for source in sources:
        _require(
            isinstance(source, dict),
            "Every source must be an object.",
        )

        url = _clean_text(
            source.get("url")
        )
        title = _clean_text(
            source.get("title")
        )
        provider = _clean_text(
            source.get("source")
        )

        _require(
            _valid_http_url(url),
            "Every cited source must have a valid HTTP URL.",
        )
        _require(
            bool(title),
            "Every cited source must have a title.",
        )
        _require(
            bool(provider),
            "Every cited source must have a provider label.",
        )
        _require(
            url not in seen_urls,
            "The final citation set contains a duplicate URL.",
        )

        seen_urls.add(url)

    verified_mcp_results = raw_intelligence.get(
        "verified_mcp_result_count",
        0,
    )

    _require(
        isinstance(verified_mcp_results, int)
        and not isinstance(
            verified_mcp_results,
            bool,
        )
        and verified_mcp_results >= 0,
        (
            "verified_mcp_result_count must be "
            "a non-negative integer."
        ),
    )

    if verified_mcp_results > 0:
        _require(
            require_citations,
            (
                "Verified MCP evidence cannot exist when the "
                "assessment status is INSUFFICIENT_EVIDENCE."
            ),
        )
        _require(
            "Remote MCP search_engine"
            in tools_used,
            (
                "Verified MCP evidence exists but the "
                "Remote MCP search tool was not recorded."
            ),
        )
        _require(
            any(
                "mcp" in _clean_text(
                    source.get("source")
                ).lower()
                for source in sources
            ),
            (
                "Verified MCP evidence exists but no MCP "
                "citation appears in the final source set."
            ),
        )


def _validate_provenance(
    report: dict[str, Any],
    tools_used: set[str],
) -> None:
    provenance = report.get(
        "evidence_provenance"
    )

    _require(
        isinstance(provenance, list),
        "evidence_provenance must be a list.",
    )

    for record in provenance:
        _require(
            isinstance(record, dict),
            "Every provenance record must be an object.",
        )

        provider = _clean_text(
            record.get("provider")
        )
        status = _clean_text(
            record.get("status")
        )
        characters = record.get(
            "characters"
        )
        retrieved_at = _clean_text(
            record.get("retrieved_at")
        )
        digest = record.get(
            "content_sha256"
        )
        url = _clean_text(
            record.get("url")
        )

        _require(
            bool(provider),
            "Provenance record is missing provider.",
        )
        _require(
            bool(status),
            "Provenance record is missing status.",
        )
        _require(
            isinstance(characters, int)
            and characters >= 0,
            "Provenance characters must be a non-negative integer.",
        )
        _require(
            bool(retrieved_at),
            "Provenance record is missing retrieved_at.",
        )

        if url:
            _require(
                _valid_http_url(url),
                "Provenance record contains an invalid URL.",
            )

        if status == "success":
            _require(
                characters > 0,
                "Successful provenance must record content characters.",
            )
            _require(
                isinstance(digest, str)
                and re.fullmatch(
                    r"[0-9a-f]{64}",
                    digest,
                )
                is not None,
                (
                    "Successful provenance must include a "
                    "SHA-256 content hash."
                ),
            )

        _require(
            "content" not in record,
            (
                "Provenance must not store the raw scraped "
                "content body."
            ),
        )

    if "Remote MCP scrape_as_markdown" in tools_used:
        _require(
            any(
                (
                    _clean_text(
                        record.get("provider")
                    )
                    == "Remote MCP scrape_as_markdown"
                    and _clean_text(
                        record.get("status")
                    )
                    == "success"
                )
                for record in provenance
            ),
            (
                "MCP scraper was reported as used but successful "
                "MCP scrape provenance is missing."
            ),
        )


VALID_EVIDENCE_ASSESSMENT_STATUSES = {
    "COMPLETED",
    "INSUFFICIENT_EVIDENCE",
}


def _non_negative_integer(
    value: Any,
) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _resolve_report_outcome(
    report: dict[str, Any],
    raw_intelligence: dict[str, Any],
) -> tuple[str, bool]:
    """Return and validate the evidence outcome and score availability."""
    report_status = _clean_text(
        report.get("evidence_assessment_status")
    ).upper()
    raw_status = _clean_text(
        raw_intelligence.get(
            "evidence_assessment_status"
        )
    ).upper()

    assessment_status = (
        report_status
        or raw_status
        or "COMPLETED"
    )

    _require(
        assessment_status
        in VALID_EVIDENCE_ASSESSMENT_STATUSES,
        "Report contains an invalid evidence_assessment_status.",
    )

    if report_status and raw_status:
        _require(
            report_status == raw_status,
            (
                "Top-level and raw_intelligence evidence statuses "
                "must match."
            ),
        )

    report_available = report.get(
        "risk_score_available"
    )
    raw_available = raw_intelligence.get(
        "risk_score_available"
    )

    available_values = [
        value
        for value in (
            report_available,
            raw_available,
        )
        if value is not None
    ]

    for value in available_values:
        _require(
            isinstance(value, bool),
            "risk_score_available must be a boolean.",
        )

    if len(available_values) == 2:
        _require(
            available_values[0] == available_values[1],
            (
                "Top-level and raw_intelligence "
                "risk_score_available values must match."
            ),
        )

    score_available = (
        available_values[0]
        if available_values
        else assessment_status == "COMPLETED"
    )

    _require(
        score_available
        == (assessment_status == "COMPLETED"),
        (
            "risk_score_available contradicts "
            "evidence_assessment_status."
        ),
    )

    return assessment_status, score_available


def _validate_insufficient_evidence_outcome(
    report: dict[str, Any],
    raw_intelligence: dict[str, Any],
) -> None:
    """Validate a truthful no-score outcome without treating it as LOW risk."""
    _require(
        report.get("risk_score") == 0,
        (
            "INSUFFICIENT_EVIDENCE must use risk_score=0 only as "
            "an explicitly unavailable compatibility placeholder."
        ),
    )
    _require(
        _clean_text(
            report.get("risk_level")
        ).upper() == "LOW",
        (
            "INSUFFICIENT_EVIDENCE must use risk_level=LOW only as "
            "an explicitly unavailable compatibility placeholder."
        ),
    )
    _require(
        report.get("disruption_probability") == 0,
        (
            "INSUFFICIENT_EVIDENCE must not expose a disruption "
            "probability."
        ),
    )
    _require(
        report.get("signals") == [],
        "INSUFFICIENT_EVIDENCE reports must not contain scored signals.",
    )
    _require(
        _clean_text(
            report.get("primary_risk_category")
        ) == "Operational",
        (
            "INSUFFICIENT_EVIDENCE must retain the neutral "
            "Operational compatibility category."
        ),
    )
    _require(
        _clean_text(
            report.get("risk_trajectory")
        ) == "Stable",
        (
            "INSUFFICIENT_EVIDENCE must retain the neutral Stable "
            "compatibility trajectory."
        ),
    )

    summary = _clean_text(
        report.get("executive_summary")
    ).lower()
    headline = _clean_text(
        report.get("risk_headline")
    ).lower()

    _require(
        (
            "insufficient" in summary
            or "could not assign" in summary
        )
        and "insufficient" in headline,
        (
            "INSUFFICIENT_EVIDENCE language must clearly state that "
            "no defensible score was assigned."
        ),
    )

    for field in (
        "verified_evidence_count",
        "verified_source_count",
        "authoritative_source_count",
        "verified_mcp_result_count",
    ):
        value = raw_intelligence.get(field, 0)
        _require(
            _non_negative_integer(value)
            and value == 0,
            f"{field} must be zero for INSUFFICIENT_EVIDENCE.",
        )

    verified_evidence = raw_intelligence.get(
        "verified_evidence",
        [],
    )
    _require(
        isinstance(verified_evidence, list)
        and not verified_evidence,
        (
            "INSUFFICIENT_EVIDENCE must not contain verified "
            "evidence records."
        ),
    )

    _require(
        raw_intelligence.get(
            "llm_execution_status"
        )
        == "skipped_insufficient_verified_evidence",
        (
            "AI synthesis must be skipped when verified evidence is "
            "insufficient."
        ),
    )


def validate_calibrated_report_contract(
    report: dict[str, Any],
) -> None:
    """
    Raise ValueError when a final report violates calibration or provenance.

    This function accepts two valid completed outcomes:
    - COMPLETED: a verified evidence score with mandatory citations.
    - INSUFFICIENT_EVIDENCE: no score and no promoted citations.
    """
    _require(
        isinstance(report, dict),
        "Report must be an object.",
    )
    _require(
        report.get("status") == "completed",
        "Report status must be completed.",
    )

    raw_intelligence = report.get(
        "raw_intelligence"
    )
    _require(
        isinstance(raw_intelligence, dict),
        "raw_intelligence must be an object.",
    )

    assessment_status, score_available = (
        _resolve_report_outcome(
            report,
            raw_intelligence,
        )
    )

    confidence = report.get(
        "confidence_score"
    )
    _require(
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= confidence <= 1,
        "confidence_score must be between 0 and 1.",
    )

    signals = report.get(
        "signals"
    )
    _require(
        isinstance(signals, list),
        "signals must be a list.",
    )

    if score_available:
        level = _clean_text(
            report.get("risk_level")
        ).upper()
        _require(
            level in VALID_RISK_LEVELS,
            "Report contains an invalid risk_level.",
        )

        _validate_level_score_alignment(
            report.get("risk_score"),
            level,
        )

        expected_category = derive_primary_category(
            signals
        )
        actual_category = _clean_text(
            report.get("primary_risk_category")
        )
        _require(
            actual_category == expected_category,
            (
                "primary_risk_category contradicts deterministic "
                f"signals: expected {expected_category}, "
                f"received {actual_category or 'empty'}."
            ),
        )

        trajectory = _clean_text(
            report.get("risk_trajectory")
        )
        expected_trajectory = calibrate_trajectory(
            level,
            float(confidence),
            trajectory,
        )
        _require(
            trajectory == expected_trajectory,
            (
                "risk_trajectory contradicts deterministic "
                f"calibration: expected {expected_trajectory}, "
                f"received {trajectory or 'empty'}."
            ),
        )

        if level == "LOW":
            _validate_low_risk_language(
                report
            )
    else:
        _validate_insufficient_evidence_outcome(
            report,
            raw_intelligence,
        )

    _require(
        raw_intelligence.get(
            "scoring_source"
        )
        == "verified_source_linked_evidence",
        (
            "Final scoring_source must be "
            "verified_source_linked_evidence."
        ),
    )
    _require(
        raw_intelligence.get(
            "language_authority"
        )
        == "deterministic_report_calibration",
        (
            "Final language_authority must be "
            "deterministic_report_calibration."
        ),
    )
    _require(
        raw_intelligence.get(
            "assessment_type"
        )
        == "point_in_time",
        "assessment_type must be point_in_time.",
    )

    tools_value = raw_intelligence.get(
        "bright_data_tools_used",
        [],
    )
    _require(
        isinstance(tools_value, list),
        "bright_data_tools_used must be a list.",
    )
    tools_used = {
        _clean_text(tool)
        for tool in tools_value
        if _clean_text(tool)
    }

    _validate_sources(
        report,
        raw_intelligence,
        tools_used,
        require_citations=score_available,
    )
    _validate_provenance(
        report,
        tools_used,
    )

    serialized = json.dumps(
        report,
        ensure_ascii=False,
        default=str,
    ).lower()
    exposed_markers = [
        marker
        for marker in SECRET_MARKERS
        if marker in serialized
    ]
    _require(
        not exposed_markers,
        (
            "Report contains a protected credential marker: "
            + ", ".join(exposed_markers)
        ),
    )