"""Regression tests for evidence attribution and truth-safe scoring."""

from core.company_identity import build_company_identity
from core.evidence_scoring import score_verified_evidence
from core.evidence_validation import (
    SourceDocument,
    extract_evidence_candidates,
    validate_evidence_candidates,
)


def _microsoft_identity():
    """Return a strongly resolved Microsoft identity for focused tests."""
    return build_company_identity(
        requested_name="Microsoft",
        canonical_name="Microsoft",
        website="https://www.microsoft.com",
        country="United States",
        industry="Technology",
    )


def test_protective_ransomware_context_is_not_vendor_incident() -> None:
    """
    Microsoft preventing ransomware must not become a Microsoft incident.
    """
    identity = _microsoft_identity()

    documents = [
        SourceDocument(
            title=(
                "Microsoft Defender prevented a ransomware attack "
                "before it started"
            ),
            url=(
                "https://www.microsoft.com/en-us/security/blog/"
                "defender-ransomware-case-study"
            ),
            provider="SERP API",
            snippet=(
                "Microsoft Defender prevented a ransomware attack "
                "against an educational institution."
            ),
        )
    ]

    candidates = extract_evidence_candidates(
        identity,
        documents,
    )
    validated = validate_evidence_candidates(
        candidates,
    )

    ransomware_records = [
        record
        for record in validated
        if record.indicator == "ransomware attack"
    ]

    assert ransomware_records
    assert any(
        record.protective_context
        for record in ransomware_records
    )
    assert all(
        not record.verified
        for record in ransomware_records
    )
    assert all(
        record.rejection_reason
        for record in ransomware_records
    )


def test_rejected_evidence_does_not_create_risk_score() -> None:
    """
    Rejected mentions must produce insufficient evidence, not a LOW/HIGH score.
    """
    identity = _microsoft_identity()

    documents = [
        SourceDocument(
            title="Microsoft security guidance on ransomware protection",
            url=(
                "https://www.microsoft.com/en-us/security/"
                "business/security-101/ransomware"
            ),
            provider="SERP API",
            snippet=(
                "Microsoft provides guidance on how organisations "
                "can prevent a ransomware attack."
            ),
        )
    ]

    candidates = extract_evidence_candidates(
        identity,
        documents,
    )
    validated = validate_evidence_candidates(
        candidates,
    )

    assessment = score_verified_evidence(
        validated,
        identity_confidence=identity.confidence,
    )

    assert assessment.status == "INSUFFICIENT_EVIDENCE"
    assert assessment.risk_score is None
    assert assessment.risk_level is None
    assert assessment.verified_signals == ()
    assert assessment.rejected_signals
