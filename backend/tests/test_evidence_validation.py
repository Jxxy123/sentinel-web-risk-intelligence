from core.company_identity import build_company_identity
from core.evidence_validation import (
    SourceDocument,
    extract_evidence_candidates,
    validate_evidence_candidates,
)


def _identity():
    return build_company_identity(
        "Microsoft Corporation",
        aliases=["Microsoft"],
        website="https://www.microsoft.com",
        country="United States",
        industry="Technology",
    )


def test_general_ransomware_guidance_is_rejected() -> None:
    documents = [
        SourceDocument(
            title="Ransomware preparedness guide",
            url="https://www.microsoft.com/security/guide",
            provider="bright_data_remote_mcp",
            content=(
                "Microsoft published guidance on how to prevent a "
                "ransomware attack and improve resilience."
            ),
        )
    ]

    validated = validate_evidence_candidates(
        extract_evidence_candidates(
            _identity(),
            documents,
        )
    )

    ransomware = [
        record
        for record in validated
        if record.indicator == "ransomware attack"
    ]

    assert ransomware
    assert ransomware[0].verified is False
    assert "prevention" in ransomware[0].rejection_reason.lower()


def test_unrelated_company_incident_is_rejected() -> None:
    documents = [
        SourceDocument(
            title="Industry report",
            url="https://www.researchgate.net/example",
            provider="bright_data_serp",
            content=(
                "Contoso suffered a ransomware attack last year. "
                "Microsoft was discussed elsewhere in the market overview."
            ),
        )
    ]

    validated = validate_evidence_candidates(
        extract_evidence_candidates(
            _identity(),
            documents,
        )
    )

    ransomware = [
        record
        for record in validated
        if record.indicator == "ransomware attack"
    ]

    assert ransomware
    assert ransomware[0].verified is False
    assert "directly attribute" in ransomware[0].rejection_reason.lower()


def test_negated_incident_is_rejected() -> None:
    documents = [
        SourceDocument(
            title="Microsoft statement",
            url="https://www.reuters.com/example",
            provider="bright_data_serp",
            content=(
                "Microsoft confirmed that no data breach occurred."
            ),
        )
    ]

    validated = validate_evidence_candidates(
        extract_evidence_candidates(
            _identity(),
            documents,
        )
    )

    assert validated[0].verified is False
    assert "negates" in validated[0].rejection_reason.lower()


def test_critical_claim_needs_corroboration() -> None:
    documents = [
        SourceDocument(
            title="Microsoft incident",
            url="https://www.reuters.com/microsoft-incident",
            provider="bright_data_serp",
            content=(
                "Microsoft confirmed it suffered a ransomware attack."
            ),
            published_at="2026-07-01T00:00:00+00:00",
        ),
        SourceDocument(
            title="Microsoft incident follow-up",
            url="https://apnews.com/microsoft-incident",
            provider="bright_data_remote_mcp",
            content=(
                "Microsoft reported it was hit by a ransomware attack."
            ),
            published_at="2026-07-02T00:00:00+00:00",
        ),
    ]

    validated = validate_evidence_candidates(
        extract_evidence_candidates(
            _identity(),
            documents,
        )
    )

    records = [
        record
        for record in validated
        if record.indicator == "ransomware attack"
    ]

    assert len(records) == 2
    assert all(record.verified for record in records)
    assert all(record.corroboration_count == 2 for record in records)
    assert all(record.evidence_excerpt for record in records)
