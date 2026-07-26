"""Evidence-grounded scoring that never treats missing data as LOW risk."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from core.evidence_validation import EvidenceRecord


BASE_WEIGHTS = {
    "critical": 35.0,
    "high": 20.0,
    "medium": 10.0,
    "low": 3.0,
}

SOURCE_MULTIPLIERS = {
    "AUTHORITATIVE": 1.00,
    "REPUTABLE_NEWS": 0.95,
    "COMPANY_OWNED": 0.85,
    "SPECIALIST": 0.75,
    "GENERAL_WEB": 0.55,
    "SOCIAL": 0.00,
    "UNKNOWN": 0.35,
}


@dataclass(frozen=True)
class EvidenceAssessment:
    status: str
    risk_score: int | None
    risk_level: str | None
    confidence_score: float
    primary_risk_category: str | None
    verified_signals: tuple[EvidenceRecord, ...]
    rejected_signals: tuple[EvidenceRecord, ...]
    unique_source_count: int
    authoritative_source_count: int
    coverage_message: str


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _freshness_multiplier(
    publication_date: str | None,
    *,
    now: datetime,
) -> float:
    parsed = _parse_date(publication_date)

    if parsed is None:
        return 0.75

    age_days = max(
        0,
        (now - parsed).days,
    )

    if age_days <= 90:
        return 1.00
    if age_days <= 365:
        return 0.90
    if age_days <= 730:
        return 0.70

    return 0.45


def _risk_level(score: int) -> str:
    if score >= 70:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"

    return "LOW"


def score_verified_evidence(
    records: Iterable[EvidenceRecord],
    *,
    identity_confidence: float,
    now: datetime | None = None,
) -> EvidenceAssessment:
    """
    Score only verified, sentence-level, source-linked evidence.

    When public evidence is too sparse, return INSUFFICIENT_EVIDENCE rather
    than claiming the company is LOW risk.
    """
    current_time = now or datetime.now(
        timezone.utc
    )
    all_records = list(records)
    verified = [
        record
        for record in all_records
        if record.verified
    ]
    rejected = [
        record
        for record in all_records
        if not record.verified
    ]

    unique_domains = {
        record.source_url.split("/")[2].lower()
        for record in verified
        if "://" in record.source_url
    }
    authoritative_count = sum(
        record.source_quality == "AUTHORITATIVE"
        for record in verified
    )

    sufficient = (
        bool(verified)
        and (
            len(unique_domains) >= 2
            or authoritative_count >= 1
            or any(
                (
                    record.source_quality == "COMPANY_OWNED"
                    and record.corroboration_count >= 2
                )
                for record in verified
            )
        )
    )

    if not sufficient:
        return EvidenceAssessment(
            status="INSUFFICIENT_EVIDENCE",
            risk_score=None,
            risk_level=None,
            confidence_score=round(
                min(
                    0.35,
                    max(0.05, identity_confidence * 0.35),
                ),
                2,
            ),
            primary_risk_category=None,
            verified_signals=tuple(verified),
            rejected_signals=tuple(rejected),
            unique_source_count=len(unique_domains),
            authoritative_source_count=authoritative_count,
            coverage_message=(
                "Insufficient verified public evidence is available to assign "
                "a defensible risk score. Absence of public evidence is not "
                "treated as evidence of low risk."
            ),
        )

    # Prevent duplicate copies of the same indicator from being fully counted.
    best_by_indicator: dict[
        tuple[str, str],
        tuple[float, EvidenceRecord],
    ] = {}

    for record in verified:
        base = BASE_WEIGHTS[
            record.severity
        ]
        source_multiplier = SOURCE_MULTIPLIERS.get(
            record.source_quality,
            0.35,
        )
        freshness = _freshness_multiplier(
            record.publication_date,
            now=current_time,
        )
        corroboration = min(
            1.25,
            1.0 + max(
                0,
                record.corroboration_count - 1,
            ) * 0.10,
        )
        weighted = (
            base
            * source_multiplier
            * freshness
            * corroboration
        )

        key = (
            record.category,
            record.indicator.lower(),
        )
        existing = best_by_indicator.get(
            key
        )

        if existing is None or weighted > existing[0]:
            best_by_indicator[key] = (
                weighted,
                record,
            )

    score = min(
        100,
        int(
            round(
                sum(
                    value
                    for value, _ in best_by_indicator.values()
                )
            )
        ),
    )

    category_weights: Counter[str] = Counter()

    for (
        category,
        _indicator,
    ), (
        weighted,
        _record,
    ) in best_by_indicator.items():
        category_weights[category] += weighted

    primary_category = (
        category_weights.most_common(1)[0][0].title()
        if category_weights
        else None
    )

    high_quality_count = sum(
        record.source_quality
        in {
            "AUTHORITATIVE",
            "REPUTABLE_NEWS",
            "COMPANY_OWNED",
        }
        for record in verified
    )
    corroborated_count = sum(
        record.corroboration_count >= 2
        for record in verified
    )

    source_coverage = min(
        1.0,
        len(unique_domains) / 5,
    )
    evidence_quality = min(
        1.0,
        high_quality_count / max(1, len(verified)),
    )
    corroboration_quality = min(
        1.0,
        corroborated_count / max(1, len(verified)),
    )

    confidence = (
        max(
            0.0,
            min(1.0, identity_confidence),
        )
        * 0.25
        + source_coverage * 0.30
        + evidence_quality * 0.25
        + corroboration_quality * 0.20
    )

    return EvidenceAssessment(
        status="COMPLETED",
        risk_score=score,
        risk_level=_risk_level(score),
        confidence_score=round(
            min(0.99, confidence),
            2,
        ),
        primary_risk_category=primary_category,
        verified_signals=tuple(verified),
        rejected_signals=tuple(rejected),
        unique_source_count=len(unique_domains),
        authoritative_source_count=authoritative_count,
        coverage_message=(
            "The score is based only on verified, source-linked, "
            "contextually attributed public evidence."
        ),
    )
