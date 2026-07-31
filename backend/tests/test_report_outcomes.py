"""Regression tests for scored and insufficient-evidence reports."""

from __future__ import annotations

import copy

import pytest

from core.report_contract import validate_calibrated_report_contract


def _scored_report() -> dict:
    return {
        "vendor_name": "Microsoft",
        "evidence_assessment_status": "COMPLETED",
        "risk_score_available": True,
        "risk_score": 6,
        "risk_level": "LOW",
        "confidence_score": 0.27,
        "disruption_probability": 0.07,
        "executive_summary": (
            "Microsoft has a low point-in-time vendor-risk score of 6/100 "
            "based on verified evidence. Confidence is low because the "
            "available evidence is limited."
        ),
        "risk_headline": (
            "Microsoft currently has a low point-in-time risk profile, "
            "led by operational indicators."
        ),
        "primary_risk_category": "Operational",
        "key_findings": [
            "A low-severity restructuring indicator was verified."
        ],
        "risk_trajectory": "Stable",
        "recommended_actions": [
            "Review the cited evidence periodically."
        ],
        "monitoring_signals": [],
        "time_horizon": "Near-term",
        "signals": [
            {
                "category": "Operational",
                "severity": "LOW",
                "indicators": ["Restructuring"],
                "weight": 3,
            }
        ],
        "sources": [
            {
                "url": "https://www.reuters.com/example",
                "title": "Reuters report",
                "source": "bright_data_serp",
            }
        ],
        "evidence_provenance": [],
        "raw_intelligence": {
            "evidence_assessment_status": "COMPLETED",
            "risk_score_available": True,
            "verified_evidence_count": 1,
            "verified_source_count": 1,
            "authoritative_source_count": 0,
            "verified_mcp_result_count": 0,
            "verified_evidence": [{"verified": True}],
            "bright_data_tools_used": ["SERP API"],
            "llm_execution_status": "completed",
            "scoring_source": "verified_source_linked_evidence",
            "language_authority": "deterministic_report_calibration",
            "assessment_type": "point_in_time",
        },
        "status": "completed",
        "generated_at": "2026-07-31T00:00:00+00:00",
    }


def _insufficient_report() -> dict:
    return {
        "vendor_name": "Microsoft",
        "evidence_assessment_status": "INSUFFICIENT_EVIDENCE",
        "risk_score_available": False,
        "risk_score": 0,
        "risk_level": "LOW",
        "confidence_score": 0.21,
        "disruption_probability": 0.0,
        "executive_summary": (
            "Sentinel could not assign a defensible point-in-time vendor-risk "
            "score to Microsoft because the collected public material did not "
            "contain enough verified and directly attributed evidence."
        ),
        "risk_headline": (
            "Insufficient verified evidence is available to assign Microsoft "
            "a defensible risk level."
        ),
        "primary_risk_category": "Operational",
        "key_findings": [
            "Insufficient verified public evidence is available.",
            "Rejected candidates were not used for scoring.",
        ],
        "risk_trajectory": "Stable",
        "recommended_actions": [
            "Collect stronger authoritative evidence."
        ],
        "monitoring_signals": [],
        "time_horizon": "Near-term",
        "signals": [],
        "sources": [],
        "evidence_provenance": [],
        "raw_intelligence": {
            "evidence_assessment_status": "INSUFFICIENT_EVIDENCE",
            "risk_score_available": False,
            "verified_evidence_count": 0,
            "rejected_evidence_count": 2,
            "verified_source_count": 0,
            "authoritative_source_count": 0,
            "verified_mcp_result_count": 0,
            "verified_evidence": [],
            "bright_data_tools_used": ["SERP API"],
            "llm_execution_status": (
                "skipped_insufficient_verified_evidence"
            ),
            "scoring_source": "verified_source_linked_evidence",
            "language_authority": "deterministic_report_calibration",
            "assessment_type": "point_in_time",
        },
        "status": "completed",
        "generated_at": "2026-07-31T00:00:00+00:00",
    }


def test_scored_report_requires_verified_sources() -> None:
    validate_calibrated_report_contract(_scored_report())

    report = _scored_report()
    report["sources"] = []

    with pytest.raises(
        ValueError,
        match="scored report must contain cited sources",
    ):
        validate_calibrated_report_contract(report)


def test_insufficient_evidence_allows_empty_sources() -> None:
    validate_calibrated_report_contract(_insufficient_report())


def test_insufficient_evidence_rejects_promoted_sources() -> None:
    report = _insufficient_report()
    report["sources"] = [
        {
            "url": "https://example.com/rejected",
            "title": "Rejected candidate",
            "source": "bright_data_serp",
        }
    ]

    with pytest.raises(
        ValueError,
        match="must not cite rejected or unverified sources",
    ):
        validate_calibrated_report_contract(report)


def test_insufficient_evidence_rejects_fake_score_availability() -> None:
    report = _insufficient_report()
    report["risk_score_available"] = True

    with pytest.raises(
        ValueError,
        match="risk_score_available",
    ):
        validate_calibrated_report_contract(report)


def test_insufficient_evidence_requires_llm_skip() -> None:
    report = copy.deepcopy(_insufficient_report())
    report["raw_intelligence"]["llm_execution_status"] = "completed"

    with pytest.raises(
        ValueError,
        match="AI synthesis must be skipped",
    ):
        validate_calibrated_report_contract(report)