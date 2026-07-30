"""Truth-safe evidence preparation for the live Sentinel orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.company_identity import CompanyIdentity, build_company_identity
from core.evidence_scoring import EvidenceAssessment, score_verified_evidence
from core.evidence_validation import (
    EvidenceRecord,
    SourceDocument,
    extract_evidence_candidates,
    validate_evidence_candidates,
)


SearchResult = dict[str, str]


@dataclass(frozen=True)
class OrchestratorEvidenceBundle:
    """Verified evidence and compatibility fields required by the orchestrator."""

    assessment: EvidenceAssessment
    verified_records: tuple[EvidenceRecord, ...]
    rejected_records: tuple[EvidenceRecord, ...]
    legacy_signals: tuple[dict[str, Any], ...]
    crew_search_results: tuple[SearchResult, ...]
    crew_evidence_context: str
    score_available: bool
    score: int
    level: str
    confidence: float


def _build_identity(
    vendor_name: str,
    identity_context: dict[str, Any] | None,
) -> CompanyIdentity:
    """Build the identity used for sentence-level evidence attribution."""
    context = identity_context if isinstance(identity_context, dict) else {}

    return build_company_identity(
        requested_name=(
            str(context.get("requested_name", "")).strip() or vendor_name
        ),
        canonical_name=(
            str(context.get("canonical_name", "")).strip() or vendor_name
        ),
        aliases=[
            alias
            for alias in (
                context.get("requested_name"),
                context.get("canonical_name"),
            )
            if str(alias or "").strip()
        ],
        website=str(context.get("website", "")).strip() or None,
        country=str(context.get("country", "")).strip() or None,
        industry=str(context.get("industry", "")).strip() or None,
    )


def _provider(result: SearchResult) -> str:
    """Return a stable provider label for one result."""
    provider = str(result.get("source") or result.get("provider") or "").strip()

    if provider == "bright_data_remote_mcp":
        return "Remote MCP search_engine"

    return provider or "SERP API"


def _to_documents(search_results: list[SearchResult]) -> list[SourceDocument]:
    """Preserve source boundaries instead of flattening all text."""
    documents: list[SourceDocument] = []

    for result in search_results:
        title = str(result.get("title", "")).strip()
        url = str(result.get("url", "")).strip()

        if not title or not url:
            continue

        published_at = (
            str(
                result.get("published_at")
                or result.get("published")
                or result.get("date")
                or ""
            ).strip()
            or None
        )
        documents.append(
            SourceDocument(
                title=title,
                url=url,
                provider=_provider(result),
                snippet=str(result.get("snippet", "")).strip(),
                published_at=published_at,
            )
        )

    return documents


def _to_legacy_signals(
    records: tuple[EvidenceRecord, ...],
) -> tuple[dict[str, Any], ...]:
    """Convert only accepted evidence into the existing report signal shape."""
    severity_weights = {
        "critical": 35,
        "high": 20,
        "medium": 10,
        "low": 3,
    }
    severity_rank = {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }
    strongest: dict[tuple[str, str], dict[str, Any]] = {}

    for record in records:
        key = (record.category, record.indicator.lower())
        candidate = {
            "category": record.category,
            "severity": record.severity,
            "keyword": record.indicator,
            "weight": severity_weights.get(record.severity, 0),
        }
        existing = strongest.get(key)

        if existing is None or severity_rank.get(
            record.severity, 0
        ) > severity_rank.get(str(existing.get("severity", "")), 0):
            strongest[key] = candidate

    return tuple(strongest.values())


def _verified_results(
    search_results: list[SearchResult],
    records: tuple[EvidenceRecord, ...],
) -> tuple[SearchResult, ...]:
    """Return only results that produced accepted evidence."""
    verified_urls = {record.source_url for record in records if record.source_url}

    return tuple(
        result
        for result in search_results
        if str(result.get("url", "")).strip() in verified_urls
    )


def _verified_context(records: tuple[EvidenceRecord, ...]) -> str:
    """Build source-linked CrewAI context using accepted evidence only."""
    lines: list[str] = []

    for record in records[:12]:
        lines.append(
            "- "
            f"{record.category.title()} / {record.severity.upper()} / "
            f"{record.indicator}: {record.evidence_excerpt} "
            f"[Source: {record.source_title}]({record.source_url})"
        )

    return "\n".join(lines)


def assess_search_results(
    vendor_name: str,
    identity_context: dict[str, Any] | None,
    search_results: list[SearchResult],
) -> OrchestratorEvidenceBundle:
    """Validate and score only source-linked, directly attributed evidence."""
    identity = _build_identity(vendor_name, identity_context)
    candidates = extract_evidence_candidates(identity, _to_documents(search_results))
    records = validate_evidence_candidates(candidates)
    context_confidence = (
        float(identity_context.get("identity_confidence", identity.confidence))
        if isinstance(identity_context, dict)
        else identity.confidence
    )
    assessment = score_verified_evidence(
        records,
        identity_confidence=context_confidence,
    )
    verified = tuple(assessment.verified_signals)
    rejected = tuple(assessment.rejected_signals)
    score_available = assessment.risk_score is not None

    return OrchestratorEvidenceBundle(
        assessment=assessment,
        verified_records=verified,
        rejected_records=rejected,
        legacy_signals=_to_legacy_signals(verified),
        crew_search_results=_verified_results(search_results, verified),
        crew_evidence_context=_verified_context(verified),
        score_available=score_available,
        score=assessment.risk_score if score_available else 0,
        level=assessment.risk_level if score_available else "LOW",
        confidence=assessment.confidence_score,
    )


def serialize_evidence_record(record: EvidenceRecord) -> dict[str, Any]:
    """Return a safe audit representation of one evidence decision."""
    return {
        "category": record.category,
        "severity": record.severity,
        "indicator": record.indicator,
        "source_url": record.source_url,
        "source_title": record.source_title,
        "source_provider": record.source_provider,
        "source_quality": record.source_quality,
        "publication_date": record.publication_date,
        "evidence_excerpt": record.evidence_excerpt,
        "entity_match": record.entity_match,
        "direct_claim": record.direct_claim,
        "negated": record.negated,
        "hypothetical": record.hypothetical,
        "protective_context": record.protective_context,
        "corroboration_count": record.corroboration_count,
        "independent_domains": list(record.independent_domains),
        "verified": record.verified,
        "rejection_reason": record.rejection_reason,
    }


def build_verified_key_findings(
    records: tuple[EvidenceRecord, ...],
) -> list[str]:
    """Build factual findings directly from accepted evidence excerpts."""
    findings: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for record in records:
        key = (record.category, record.indicator.lower(), record.source_url)

        if key in seen:
            continue

        seen.add(key)
        excerpt = " ".join(record.evidence_excerpt.split())
        findings.append(
            f"{record.category.title()} ({record.severity.upper()}): "
            f"{record.indicator}. Evidence: {excerpt[:240]} "
            f"Source: {record.source_title}."
        )

        if len(findings) >= 5:
            break

    return findings


def build_insufficient_evidence_language(
    vendor_name: str,
    assessment: EvidenceAssessment,
) -> dict[str, Any]:
    """Return non-misleading language when no defensible score exists."""
    rejected_count = len(assessment.rejected_signals)

    return {
        "executive_summary": (
            f"Sentinel could not assign a defensible point-in-time vendor-risk "
            f"score to {vendor_name}. The collected public material did not "
            "contain enough verified, directly attributed, and sufficiently "
            "corroborated evidence. Missing public evidence is not treated as "
            "evidence of low risk. Additional authoritative due-diligence "
            "material is required before making a risk decision."
        ),
        "risk_headline": (
            f"Insufficient verified evidence is available to assign "
            f"{vendor_name} a defensible risk level."
        ),
        # Compatibility placeholder until the frontend supports an unavailable
        # category. The explicit assessment status prevents LOW interpretation.
        "primary_risk_category": "Operational",
        "key_findings": [
            assessment.coverage_message,
            (
                f"{rejected_count} candidate evidence records were rejected "
                "because they failed attribution, context, source-quality, "
                "or corroboration requirements."
            ),
            (
                "No verified risk score or disruption estimate should be "
                "interpreted from this assessment."
            ),
        ],
        "risk_trajectory": "Stable",
        "recommended_actions": [
            "Review the rejected-evidence audit trail before relying on any claim.",
            (
                "Collect authoritative regulatory, company, financial, and "
                "operational records for additional verification."
            ),
            (
                "Repeat the point-in-time assessment only after stronger "
                "source-linked evidence becomes available."
            ),
        ],
        "monitoring_signals": [
            "New authoritative regulatory findings",
            "Direct company disclosures or independently corroborated incidents",
        ],
        "time_horizon": "Near-term",
    }
