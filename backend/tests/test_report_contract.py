"""Offline tests for the final calibrated report contract."""

from __future__ import annotations

import copy

import pytest

from core.report_contract import (
    validate_calibrated_report_contract,
)


def _valid_report() -> dict:
    return {
        "vendor_name": "Microsoft",
        "risk_score": 6,
        "risk_level": "LOW",
        "confidence_score": 0.27,
        "disruption_probability": 0.07,
        "executive_summary": (
            "Microsoft has a low point-in-time vendor-risk score of "
            "6/100 based on live evidence. The strongest observed "
            "category is operational. Confidence is low because the "
            "available evidence is limited."
        ),
        "risk_headline": (
            "Microsoft currently has a low point-in-time risk profile, "
            "led by operational indicators."
        ),
        "primary_risk_category": "Operational",
        "key_findings": [
            "A low-severity restructuring indicator was observed.",
        ],
        "risk_trajectory": "Stable",
        "recommended_actions": [
            "Review the cited evidence periodically.",
        ],
        "monitoring_signals": [],
        "time_horizon": "Near-term",
        "signals": [
            {
                "category": "Financial",
                "severity": "LOW",
                "indicators": ["Restructuring"],
                "weight": 3,
            },
            {
                "category": "Operational",
                "severity": "LOW",
                "indicators": ["Restructuring"],
                "weight": 3,
            },
        ],
        "sources": [
            {
                "url": "https://www.reuters.com/example",
                "title": "Reuters report",
                "source": "bright_data_serp",
            },
            {
                "url": "https://www.microsoft.com/example",
                "title": "Official report",
                "source": "bright_data_remote_mcp",
            },
        ],
        "evidence_provenance": [
            {
                "provider": "Remote MCP scrape_as_markdown",
                "url": "https://www.microsoft.com/example",
                "status": "success",
                "characters": 100,
                "retrieved_at": "2026-07-26T17:54:20+00:00",
                "content_sha256": "a" * 64,
            },
        ],
        "raw_intelligence": {
            "search_results_count": 29,
            "mcp_unique_results_added": 9,
            "bright_data_tools_used": [
                "SERP API",
                "Remote MCP search_engine",
                "Remote MCP scrape_as_markdown",
            ],
            "scoring_source": "collected_live_evidence",
            "language_authority": (
                "deterministic_report_calibration"
            ),
            "assessment_type": "point_in_time",
        },
        "status": "completed",
        "generated_at": "2026-07-26T17:54:20+00:00",
    }


def test_valid_calibrated_report_passes() -> None:
    validate_calibrated_report_contract(
        _valid_report()
    )


def test_low_report_rejects_inflated_wording() -> None:
    report = _valid_report()
    report["risk_headline"] = (
        "Microsoft faces significant financial risk."
    )

    with pytest.raises(
        ValueError,
        match="inflated wording",
    ):
        validate_calibrated_report_contract(
            report
        )


def test_low_report_rejects_deteriorating_trajectory() -> None:
    report = _valid_report()
    report["risk_trajectory"] = "Deteriorating"

    with pytest.raises(
        ValueError,
        match="risk_trajectory contradicts",
    ):
        validate_calibrated_report_contract(
            report
        )


def test_mcp_results_require_mcp_citation() -> None:
    report = _valid_report()
    report["sources"] = [
        source
        for source in report["sources"]
        if "mcp" not in source["source"]
    ]

    with pytest.raises(
        ValueError,
        match="no MCP citation",
    ):
        validate_calibrated_report_contract(
            report
        )


def test_mcp_scraper_requires_successful_provenance() -> None:
    report = _valid_report()
    report["evidence_provenance"] = []

    with pytest.raises(
        ValueError,
        match="MCP scrape provenance is missing",
    ):
        validate_calibrated_report_contract(
            report
        )


def test_llm_scoring_source_is_rejected() -> None:
    report = copy.deepcopy(
        _valid_report()
    )
    report["raw_intelligence"][
        "scoring_source"
    ] = "llm_generated_text"

    with pytest.raises(
        ValueError,
        match="Final scoring_source",
    ):
        validate_calibrated_report_contract(
            report
        )
