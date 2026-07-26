"""
Sentinel Web-Risk — Deterministic Report Calibration.

This module keeps the final report language aligned with Sentinel's
deterministic risk score, confidence, disruption probability, and
evidence provenance.

The LLM may provide supporting analysis, but it is never the final
authority for:
- risk level wording
- primary risk category
- trajectory
- executive summary
- risk headline
- provider traceability
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse


VALID_RISK_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}

CATEGORY_TIE_BREAK_ORDER = (
    "Operational",
    "Financial",
    "Legal",
    "Cybersecurity",
    "Reputational",
)

LEVEL_LANGUAGE = {
    "LOW": {
        "descriptor": "low",
        "summary": (
            "limited, low-severity risk signals"
        ),
        "headline": (
            "a low point-in-time risk profile"
        ),
    },
    "MEDIUM": {
        "descriptor": "moderate",
        "summary": (
            "moderate risk signals that warrant review"
        ),
        "headline": (
            "a moderate point-in-time risk profile"
        ),
    },
    "HIGH": {
        "descriptor": "high",
        "summary": (
            "substantial risk signals requiring prompt review"
        ),
        "headline": (
            "an elevated point-in-time risk profile"
        ),
    },
    "CRITICAL": {
        "descriptor": "critical",
        "summary": (
            "severe and immediate risk signals"
        ),
        "headline": (
            "a critical point-in-time risk profile"
        ),
    },
}

UNSAFE_LOW_RISK_PHRASES = (
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

SOURCE_PRIORITY_DOMAINS = {
    "official": (
        ".gov",
        ".europa.eu",
        "sec.gov",
        "justice.gov",
        "ftc.gov",
        "microsoft.com",
    ),
    "major_news": (
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "cnbc.com",
        "ft.com",
        "wsj.com",
        "bloomberg.com",
    ),
    "specialist": (
        "law.com",
        "lobbyfacts.eu",
        "researchgate.net",
    ),
}

SOCIAL_OR_LOW_CONFIDENCE_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "studocu.com",
)


def _clean_text(value: Any) -> str:
    """Return a normalized string value."""
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def _normalize_level(level: str) -> str:
    """Return a supported uppercase risk level."""
    normalized = _clean_text(level).upper()

    if normalized not in VALID_RISK_LEVELS:
        return "LOW"

    return normalized


def _normalize_category(value: Any) -> str:
    """Normalize a category into Sentinel's public display names."""
    normalized = _clean_text(value).lower()

    mapping = {
        "operational": "Operational",
        "financial": "Financial",
        "legal": "Legal",
        "cybersecurity": "Cybersecurity",
        "cyber": "Cybersecurity",
        "reputational": "Reputational",
        "reputation": "Reputational",
    }

    return mapping.get(
        normalized,
        "",
    )


def _signal_weight(signal: dict[str, Any]) -> int:
    """Return a safe non-negative integer weight for one signal."""
    value = signal.get("weight", 0)

    try:
        return max(
            0,
            int(value),
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def derive_primary_category(
    formatted_signals: Iterable[dict[str, Any]],
) -> str:
    """
    Derive the strongest risk category from deterministic signal weights.

    Ties are resolved through a fixed enterprise-risk priority order rather
    than accepting an arbitrary LLM category.
    """
    category_weights: Counter[str] = Counter()
    category_signal_counts: Counter[str] = Counter()

    for signal in formatted_signals:
        category = _normalize_category(
            signal.get("category")
        )

        if not category:
            continue

        category_weights[category] += _signal_weight(
            signal
        )

        indicators = signal.get(
            "indicators",
            [],
        )

        if isinstance(
            indicators,
            list,
        ):
            category_signal_counts[category] += len(
                {
                    _clean_text(indicator).lower()
                    for indicator in indicators
                    if _clean_text(indicator)
                }
            )
        else:
            category_signal_counts[category] += 1

    if not category_weights:
        return "Operational"

    highest_weight = max(
        category_weights.values()
    )

    candidates = [
        category
        for category, weight in category_weights.items()
        if weight == highest_weight
    ]

    if len(candidates) == 1:
        return candidates[0]

    highest_signal_count = max(
        category_signal_counts.get(
            category,
            0,
        )
        for category in candidates
    )

    count_candidates = [
        category
        for category in candidates
        if category_signal_counts.get(
            category,
            0,
        ) == highest_signal_count
    ]

    for category in CATEGORY_TIE_BREAK_ORDER:
        if category in count_candidates:
            return category

    return sorted(
        count_candidates
    )[0]


def calibrate_trajectory(
    level: str,
    confidence: float,
    llm_trajectory: Any = None,
) -> str:
    """
    Calibrate trajectory against deterministic severity and confidence.

    LOW-risk reports cannot be labelled Deteriorating or Critical merely
    because an LLM used alarming wording.
    """
    normalized_level = _normalize_level(
        level
    )

    try:
        normalized_confidence = max(
            0.0,
            min(
                1.0,
                float(confidence),
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        normalized_confidence = 0.0

    requested_trajectory = (
        _clean_text(
            llm_trajectory
        ).title()
    )

    if normalized_level == "LOW":
        return "Stable"

    if normalized_level == "MEDIUM":
        if (
            requested_trajectory
            in {
                "Improving",
                "Stable",
                "Deteriorating",
            }
        ):
            return requested_trajectory

        return (
            "Stable"
            if normalized_confidence < 0.5
            else "Deteriorating"
        )

    if normalized_level == "HIGH":
        return "Deteriorating"

    return "Critical"


def _confidence_sentence(
    confidence: float,
) -> str:
    """Return calibrated confidence wording."""
    try:
        normalized_confidence = max(
            0.0,
            min(
                1.0,
                float(confidence),
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        normalized_confidence = 0.0

    if normalized_confidence < 0.4:
        return (
            "Confidence is low because the available evidence is "
            "limited, mixed, or unevenly distributed across risk categories."
        )

    if normalized_confidence < 0.7:
        return (
            "Confidence is moderate and should be reviewed as additional "
            "evidence becomes available."
        )

    return (
        "Confidence is relatively strong for this point-in-time assessment, "
        "but the result should still be re-evaluated as new evidence emerges."
    )


def _build_default_findings(
    level: str,
    primary_category: str,
    signal_count: int,
    source_count: int,
) -> list[str]:
    """Build deterministic key findings when LLM findings are unsuitable."""
    normalized_level = _normalize_level(
        level
    )

    if normalized_level == "LOW":
        return [
            (
                f"The deterministic engine identified {signal_count} "
                "low-severity risk indicators."
            ),
            (
                f"The strongest observed category is "
                f"{primary_category.lower()}."
            ),
            (
                f"The assessment is based on {source_count} unique live "
                "intelligence results and should not be treated as a "
                "definitive forecast."
            ),
        ]

    return [
        (
            f"The deterministic engine classified the current profile as "
            f"{normalized_level} risk."
        ),
        (
            f"The strongest observed category is "
            f"{primary_category.lower()}."
        ),
        (
            f"The assessment is based on {source_count} unique live "
            "intelligence results."
        ),
    ]


def _contains_unsafe_low_risk_language(
    text: str,
) -> bool:
    """Return True when LOW-risk wording is materially overstated."""
    normalized = _clean_text(
        text
    ).lower()

    return any(
        phrase in normalized
        for phrase in UNSAFE_LOW_RISK_PHRASES
    )


def _calibrate_findings(
    level: str,
    llm_findings: Any,
    fallback_findings: list[str],
) -> list[str]:
    """Keep suitable LLM findings without allowing severity inflation."""
    if not isinstance(
        llm_findings,
        list,
    ):
        return fallback_findings

    cleaned_findings = [
        _clean_text(item)
        for item in llm_findings
        if _clean_text(item)
    ]

    if not cleaned_findings:
        return fallback_findings

    if _normalize_level(level) == "LOW":
        cleaned_findings = [
            finding
            for finding in cleaned_findings
            if not _contains_unsafe_low_risk_language(
                finding
            )
        ]

    return (
        cleaned_findings[:5]
        or fallback_findings
    )


def _calibrate_actions(
    level: str,
    llm_actions: Any,
) -> list[str]:
    """Return truthful point-in-time recommendations."""
    normalized_level = _normalize_level(
        level
    )

    default_actions = [
        "Review the cited evidence before making a vendor decision.",
        (
            "Request current operational, financial, legal, and compliance "
            "documents where due diligence requires stronger assurance."
        ),
        (
            "Review relevant indicators periodically, or configure alerts "
            "only where ongoing monitoring is explicitly enabled."
        ),
    ]

    if not isinstance(
        llm_actions,
        list,
    ):
        return default_actions

    calibrated: list[str] = []

    for item in llm_actions:
        action = _clean_text(
            item
        )

        if not action:
            continue

        action = action.replace(
            "Continuously monitor",
            "Review periodically",
        )
        action = action.replace(
            "continuously monitor",
            "review periodically",
        )

        if (
            normalized_level == "LOW"
            and _contains_unsafe_low_risk_language(
                action
            )
        ):
            continue

        calibrated.append(
            action
        )

    return (
        calibrated[:5]
        or default_actions
    )


def build_calibrated_report_language(
    *,
    vendor_name: str,
    score: int,
    level: str,
    confidence: float,
    disruption_probability: float,
    formatted_signals: list[dict[str, Any]],
    source_count: int,
    tools_used: list[str],
    llm_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build final report language from deterministic metrics and evidence.

    The LLM report may supply supporting findings and recommendations, but
    deterministic metrics always control severity, category, trajectory,
    headline, and executive-summary framing.
    """
    normalized_vendor = (
        _clean_text(
            vendor_name
        )
        or "The vendor"
    )
    normalized_level = _normalize_level(
        level
    )
    llm_report = (
        llm_report
        if isinstance(
            llm_report,
            dict,
        )
        else {}
    )

    primary_category = derive_primary_category(
        formatted_signals
    )
    trajectory = calibrate_trajectory(
        normalized_level,
        confidence,
        llm_report.get(
            "risk_trajectory"
        ),
    )

    signal_count = len(
        formatted_signals
    )
    category_count = len(
        {
            _normalize_category(
                signal.get("category")
            )
            for signal in formatted_signals
            if _normalize_category(
                signal.get("category")
            )
        }
    )

    tool_summary = (
        ", ".join(
            tools_used
        )
        if tools_used
        else "the available live-evidence providers"
    )

    level_language = LEVEL_LANGUAGE[
        normalized_level
    ]

    executive_summary = (
        f"{normalized_vendor} has a {normalized_level.lower()} "
        f"point-in-time vendor-risk score of {score}/100, based on "
        f"{source_count} unique live intelligence results collected through "
        f"{tool_summary}. The deterministic engine identified "
        f"{signal_count} indicators across {category_count} categories, with "
        f"{primary_category.lower()} as the strongest observed category. "
        f"The estimated 90-day disruption probability is "
        f"{int(round(disruption_probability * 100))}%. "
        f"{_confidence_sentence(confidence)}"
    )

    risk_headline = (
        f"{normalized_vendor} currently has "
        f"{level_language['headline']}, led by "
        f"{primary_category.lower()} indicators."
    )

    fallback_findings = _build_default_findings(
        normalized_level,
        primary_category,
        signal_count,
        source_count,
    )

    key_findings = _calibrate_findings(
        normalized_level,
        llm_report.get(
            "key_findings"
        ),
        fallback_findings,
    )

    recommended_actions = _calibrate_actions(
        normalized_level,
        llm_report.get(
            "recommended_actions"
        ),
    )

    monitoring_signals = [
        _clean_text(item)
        for item in llm_report.get(
            "monitoring_signals",
            [],
        )
        if _clean_text(item)
    ][:5]

    return {
        "executive_summary": executive_summary,
        "risk_headline": risk_headline,
        "primary_risk_category": primary_category,
        "risk_trajectory": trajectory,
        "key_findings": key_findings,
        "recommended_actions": recommended_actions,
        "monitoring_signals": monitoring_signals,
        "time_horizon": (
            _clean_text(
                llm_report.get(
                    "time_horizon"
                )
            )
            or "Near-term"
        ),
    }


def _source_priority(
    source: dict[str, Any],
) -> tuple[int, int, str]:
    """Return a deterministic source-quality sorting key."""
    url = _clean_text(
        source.get("url")
    )
    parsed = urlparse(
        url
    )
    domain = (
        parsed.netloc.lower()
        .removeprefix("www.")
    )

    source_label = _clean_text(
        source.get("source")
    ).lower()

    if any(
        token in domain
        for token in SOURCE_PRIORITY_DOMAINS[
            "official"
        ]
    ):
        quality = 0
    elif any(
        token in domain
        for token in SOURCE_PRIORITY_DOMAINS[
            "major_news"
        ]
    ):
        quality = 1
    elif any(
        token in domain
        for token in SOURCE_PRIORITY_DOMAINS[
            "specialist"
        ]
    ):
        quality = 2
    elif any(
        token in domain
        for token in SOCIAL_OR_LOW_CONFIDENCE_DOMAINS
    ):
        quality = 4
    else:
        quality = 3

    provider_priority = (
        0
        if "serp" in source_label
        else 1
    )

    return (
        quality,
        provider_priority,
        domain,
    )


def select_balanced_sources(
    search_results: list[dict[str, Any]],
    *,
    max_total: int = 12,
    max_serp: int = 8,
    max_mcp: int = 4,
) -> list[dict[str, str]]:
    """
    Select a quality-aware mix of SERP and Remote MCP sources.

    The function prevents the first provider from occupying every citation
    slot while still preferring official and reputable domains.
    """
    if max_total <= 0:
        return []

    seen_urls: set[str] = set()
    normalized: list[dict[str, str]] = []

    for result in search_results:
        url = _clean_text(
            result.get("url")
        )
        title = _clean_text(
            result.get("title")
        )
        source = (
            _clean_text(
                result.get("source")
            )
            or "bright_data"
        )

        parsed = urlparse(
            url
        )

        if (
            not title
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or url in seen_urls
        ):
            continue

        normalized.append(
            {
                "url": url,
                "title": title,
                "source": source,
            }
        )
        seen_urls.add(
            url
        )

    serp_sources = sorted(
        [
            item
            for item in normalized
            if "serp" in item["source"].lower()
        ],
        key=_source_priority,
    )

    mcp_sources = sorted(
        [
            item
            for item in normalized
            if "mcp" in item["source"].lower()
        ],
        key=_source_priority,
    )

    other_sources = sorted(
        [
            item
            for item in normalized
            if (
                "serp" not in item["source"].lower()
                and "mcp" not in item["source"].lower()
            )
        ],
        key=_source_priority,
    )

    selected = (
        serp_sources[:max_serp]
        + mcp_sources[:max_mcp]
    )

    selected_urls = {
        item["url"]
        for item in selected
    }

    remaining = [
        item
        for item in (
            serp_sources[max_serp:]
            + mcp_sources[max_mcp:]
            + other_sources
        )
        if item["url"] not in selected_urls
    ]

    selected.extend(
        sorted(
            remaining,
            key=_source_priority,
        )[
            :max(
                0,
                max_total - len(selected),
            )
        ]
    )

    return selected[:max_total]


def build_evidence_provenance(
    *,
    provider: str,
    url: str,
    content: str | None,
    status: str,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """
    Build metadata for scraped evidence without storing the full page body.
    """
    normalized_content = (
        content
        if isinstance(
            content,
            str,
        )
        else ""
    )
    normalized_url = _clean_text(
        url
    )

    digest = (
        hashlib.sha256(
            normalized_content.encode(
                "utf-8",
                errors="replace",
            )
        ).hexdigest()
        if normalized_content
        else None
    )

    return {
        "provider": (
            _clean_text(
                provider
            )
            or "unknown"
        ),
        "url": normalized_url,
        "status": (
            _clean_text(
                status
            )
            or "unknown"
        ),
        "characters": len(
            normalized_content
        ),
        "retrieved_at": (
            _clean_text(
                retrieved_at
            )
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "content_sha256": digest,
    }
