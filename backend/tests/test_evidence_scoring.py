from dataclasses import replace
from datetime import datetime, timezone

from core.company_identity import build_company_identity
from core.evidence_scoring import score_verified_evidence
from core.evidence_validation import EvidenceRecord


def _record(
    *,
    source_url: str,
    source_quality: str,
    category: str = "operational",
    severity: str = "medium",
    indicator: str = "workforce reduction",
    verified: bool = True,
    corroboration_count: int = 2,
) -> EvidenceRecord:
    return EvidenceRecord(
        company="Example Vendor",
        category=category,
        severity=severity,
        indicator=indicator,
        source_url=source_url,
        source_title="Verified report",
        source_provider="test",
        source_quality=source_quality,
        publication_date="2026-07-01T00:00:00+00:00",
        evidence_excerpt=(
            "Example Vendor confirmed a workforce reduction."
        ),
        entity_match=True,
        direct_claim=True,
        negated=False,
        hypothetical=False,
        protective_context=False,
        corroboration_count=corroboration_count,
        independent_domains=(
            "reuters.com",
            "apnews.com",
        ),
        verified=verified,
        rejection_reason=None if verified else "Rejected",
    )


def test_no_evidence_is_not_low_risk() -> None:
    result = score_verified_evidence(
        [],
        identity_confidence=0.8,
        now=datetime(
            2026,
            7,
            26,
            tzinfo=timezone.utc,
        ),
    )

    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.risk_score is None
    assert result.risk_level is None
    assert "not treated as evidence of low risk" in (
        result.coverage_message
    )


def test_one_general_web_signal_is_insufficient() -> None:
    result = score_verified_evidence(
        [
            _record(
                source_url="https://example.com/report",
                source_quality="GENERAL_WEB",
                corroboration_count=1,
            )
        ],
        identity_confidence=0.8,
        now=datetime(
            2026,
            7,
            26,
            tzinfo=timezone.utc,
        ),
    )

    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_two_independent_reputable_sources_produce_score() -> None:
    records = [
        _record(
            source_url="https://www.reuters.com/report",
            source_quality="REPUTABLE_NEWS",
        ),
        _record(
            source_url="https://apnews.com/report",
            source_quality="REPUTABLE_NEWS",
        ),
    ]

    result = score_verified_evidence(
        records,
        identity_confidence=0.9,
        now=datetime(
            2026,
            7,
            26,
            tzinfo=timezone.utc,
        ),
    )

    assert result.status == "COMPLETED"
    assert result.risk_score is not None
    assert result.risk_level is not None
    assert result.primary_risk_category == "Operational"
    assert result.unique_source_count == 2


def test_rejected_signal_never_affects_score() -> None:
    verified = _record(
        source_url="https://www.reuters.com/report",
        source_quality="REPUTABLE_NEWS",
    )
    second = _record(
        source_url="https://apnews.com/report",
        source_quality="REPUTABLE_NEWS",
    )
    rejected = replace(
        _record(
            source_url="https://example.com/bad",
            source_quality="GENERAL_WEB",
            category="cybersecurity",
            severity="critical",
            indicator="ransomware attack",
        ),
        verified=False,
        rejection_reason="Unrelated company.",
    )

    result = score_verified_evidence(
        [
            verified,
            second,
            rejected,
        ],
        identity_confidence=0.9,
        now=datetime(
            2026,
            7,
            26,
            tzinfo=timezone.utc,
        ),
    )

    assert result.primary_risk_category == "Operational"
    assert rejected in result.rejected_signals
