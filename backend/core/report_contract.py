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
) -> None:
    sources = report.get(
        "sources"
    )

    _require(
        isinstance(sources, list)
        and bool(sources),
        "The report must contain cited sources.",
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

    mcp_results_added = raw_intelligence.get(
        "mcp_unique_results_added",
        0,
    )

    if (
        isinstance(mcp_results_added, int)
        and mcp_results_added > 0
        and "Remote MCP search_engine" in tools_used
    ):
        _require(
            any(
                "mcp" in _clean_text(
                    source.get("source")
                ).lower()
                for source in sources
            ),
            (
                "Remote MCP added unique results but no MCP "
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


def validate_calibrated_report_contract(
    report: dict[str, Any],
) -> None:
    """
    Raise ValueError when a final report violates calibration or provenance.

    This function performs no network, LLM, database, or provider calls.
    """
    _require(
        isinstance(report, dict),
        "Report must be an object.",
    )
    _require(
        report.get("status") == "completed",
        "Report status must be completed.",
    )

    level = _clean_text(
        report.get("risk_level")
    ).upper()

    _require(
        level in VALID_RISK_LEVELS,
        "Report contains an invalid risk_level.",
    )

    score = report.get(
        "risk_score"
    )
    _validate_level_score_alignment(
        score,
        level,
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

    raw_intelligence = report.get(
        "raw_intelligence"
    )
    _require(
        isinstance(raw_intelligence, dict),
        "raw_intelligence must be an object.",
    )

    _require(
        raw_intelligence.get(
            "scoring_source"
        )
        == "collected_live_evidence",
        (
            "Final scoring_source must be "
            "collected_live_evidence."
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
