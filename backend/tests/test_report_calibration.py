"""
Offline tests for deterministic report calibration.

These tests make no Bright Data, CrewAI, LLM, proxy, database, or network calls.
"""

from __future__ import annotations

import re

from core.report_calibration import (
    build_calibrated_report_language,
    build_evidence_provenance,
    calibrate_trajectory,
    derive_primary_category,
    select_balanced_sources,
)


def _signals() -> list[dict]:
    return [
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
    ]


def test_low_risk_language_cannot_be_inflated_by_llm() -> None:
    result = build_calibrated_report_language(
        vendor_name="Microsoft",
        score=6,
        level="LOW",
        confidence=0.27,
        disruption_probability=0.07,
        formatted_signals=_signals(),
        source_count=29,
        tools_used=[
            "SERP API",
            "Remote MCP search_engine",
            "Remote MCP scrape_as_markdown",
        ],
        llm_report={
            "executive_summary": (
                "Microsoft faces significant financial, operational, "
                "and reputational risks."
            ),
            "risk_headline": (
                "Microsoft faces a critical threat."
            ),
            "risk_trajectory": "Deteriorating",
            "primary_risk_category": "Financial",
            "key_findings": [
                "Recent restructuring creates significant financial risk.",
                "A low-severity restructuring signal was observed.",
            ],
            "recommended_actions": [
                "Continuously monitor Microsoft.",
            ],
        },
    )

    combined = " ".join(
        [
            result["executive_summary"],
            result["risk_headline"],
            *result["key_findings"],
        ]
    ).lower()

    forbidden = (
        "significant risk",
        "significant financial risk",
        "critical threat",
        "severe risk",
        "major financial instability",
        "high likelihood",
    )

    assert result["risk_trajectory"] == "Stable"
    assert result["primary_risk_category"] == "Operational"
    assert "6/100" in result["executive_summary"]
    assert "confidence is low" in result["executive_summary"].lower()
    assert all(
        phrase not in combined
        for phrase in forbidden
    )


def test_low_risk_always_calibrates_trajectory_to_stable() -> None:
    assert calibrate_trajectory(
        "LOW",
        0.27,
        "Deteriorating",
    ) == "Stable"

    assert calibrate_trajectory(
        "LOW",
        0.95,
        "Critical",
    ) == "Stable"


def test_primary_category_comes_from_signal_weights() -> None:
    result = derive_primary_category(
        [
            {
                "category": "Financial",
                "severity": "LOW",
                "indicators": ["Restructuring"],
                "weight": 3,
            },
            {
                "category": "Operational",
                "severity": "MEDIUM",
                "indicators": [
                    "Workforce Reduction",
                    "Operational Challenges",
                ],
                "weight": 20,
            },
        ]
    )

    assert result == "Operational"


def test_primary_category_uses_deterministic_tie_break() -> None:
    assert derive_primary_category(
        _signals()
    ) == "Operational"


def test_balanced_sources_include_serp_and_mcp() -> None:
    search_results = [
        {
            "url": f"https://news.example.com/serp-{index}",
            "title": f"SERP result {index}",
            "source": "bright_data_serp",
        }
        for index in range(10)
    ] + [
        {
            "url": f"https://mcp.example.com/result-{index}",
            "title": f"MCP result {index}",
            "source": "bright_data_remote_mcp",
        }
        for index in range(6)
    ]

    selected = select_balanced_sources(
        search_results,
        max_total=12,
        max_serp=8,
        max_mcp=4,
    )

    serp_count = sum(
        "serp" in item["source"]
        for item in selected
    )
    mcp_count = sum(
        "mcp" in item["source"]
        for item in selected
    )

    assert len(selected) == 12
    assert serp_count == 8
    assert mcp_count == 4
    assert len(
        {
            item["url"]
            for item in selected
        }
    ) == 12


def test_source_selection_prefers_authoritative_domains() -> None:
    search_results = [
        {
            "url": "https://www.facebook.com/example/post",
            "title": "Social post",
            "source": "bright_data_serp",
        },
        {
            "url": "https://www.reuters.com/example/story",
            "title": "Reuters report",
            "source": "bright_data_serp",
        },
        {
            "url": "https://www.microsoft.com/security/blog",
            "title": "Official Microsoft statement",
            "source": "bright_data_serp",
        },
    ]

    selected = select_balanced_sources(
        search_results,
        max_total=3,
        max_serp=3,
        max_mcp=0,
    )

    assert selected[0]["url"].startswith(
        "https://www.microsoft.com/"
    )
    assert selected[1]["url"].startswith(
        "https://www.reuters.com/"
    )
    assert selected[-1]["url"].startswith(
        "https://www.facebook.com/"
    )


def test_continuous_monitoring_claim_is_rewritten() -> None:
    result = build_calibrated_report_language(
        vendor_name="Example Vendor",
        score=6,
        level="LOW",
        confidence=0.27,
        disruption_probability=0.07,
        formatted_signals=_signals(),
        source_count=12,
        tools_used=["SERP API"],
        llm_report={
            "recommended_actions": [
                "Continuously monitor Example Vendor.",
            ]
        },
    )

    joined = " ".join(
        result["recommended_actions"]
    )

    assert "Continuously monitor" not in joined
    assert "Review periodically" in joined


def test_evidence_provenance_stores_hash_not_raw_content() -> None:
    content = "Retrieved public evidence about a vendor."

    provenance = build_evidence_provenance(
        provider="Remote MCP scrape_as_markdown",
        url="https://example.com/evidence",
        content=content,
        status="success",
        retrieved_at="2026-07-26T17:54:20+00:00",
    )

    assert provenance["provider"] == (
        "Remote MCP scrape_as_markdown"
    )
    assert provenance["url"] == (
        "https://example.com/evidence"
    )
    assert provenance["status"] == "success"
    assert provenance["characters"] == len(content)
    assert provenance["retrieved_at"] == (
        "2026-07-26T17:54:20+00:00"
    )
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        provenance["content_sha256"],
    )
    assert "content" not in provenance
    assert content not in str(provenance)
