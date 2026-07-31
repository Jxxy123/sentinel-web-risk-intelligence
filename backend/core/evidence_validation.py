"""Sentence-level evidence extraction and false-attribution controls."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

from core.company_identity import CompanyIdentity, company_mentioned


RISK_TERMS: dict[str, dict[str, tuple[str, ...]]] = {
    "financial": {
        "critical": (
            "bankruptcy",
            "insolvency",
            "liquidation",
            "bond default",
            "financial collapse",
        ),
        "high": (
            "credit downgrade",
            "financial distress",
            "debt crisis",
            "cash flow crisis",
        ),
        "medium": (
            "revenue decline",
            "budget cuts",
            "losses",
            "write-down",
        ),
        "low": (
            "cost optimization",
            "strategic review",
            "restructuring",
        ),
    },
    "operational": {
        "critical": (
            "operations halted",
            "production stopped",
            "factory closure",
            "critical failure",
        ),
        "high": (
            "mass layoffs",
            "major layoffs",
            "facility closure",
            "operational disruption",
        ),
        "medium": (
            "workforce reduction",
            "hiring freeze",
            "production delay",
            "capacity reduction",
        ),
        "low": (
            "reorganization",
            "headcount adjustment",
            "restructuring",
        ),
    },
    "legal": {
        "critical": (
            "criminal charges",
            "fraud conviction",
            "licence revoked",
            "regulatory shutdown",
        ),
        "high": (
            "class action",
            "regulatory investigation",
            "antitrust violation",
            "fraud allegations",
        ),
        "medium": (
            "lawsuit",
            "fine",
            "penalty",
            "regulatory warning",
        ),
        "low": (
            "regulatory inquiry",
            "compliance review",
            "legal review",
        ),
    },
    "reputational": {
        "critical": (
            "executive arrested",
            "corruption exposed",
            "massive fraud",
        ),
        "high": (
            "boycott",
            "major controversy",
            "brand crisis",
            "customer exodus",
        ),
        "medium": (
            "negative press",
            "customer complaints",
            "public relations crisis",
        ),
        "low": (
            "criticism",
            "concerns raised",
            "negative sentiment",
        ),
    },
    "cybersecurity": {
        "critical": (
            "ransomware attack",
            "data breach",
            "systems compromised",
            "cyber attack",
        ),
        "high": (
            "security breach",
            "data leak",
            "hacked",
        ),
        "medium": (
            "security incident",
            "data exposure",
            "security concerns",
        ),
        "low": (
            "security review",
            "vulnerability patched",
        ),
    },
}

REPUTABLE_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "cnbc.com",
    "ft.com",
    "wsj.com",
    "bloomberg.com",
    "theguardian.com",
}

SOCIAL_DOMAINS = {
    "facebook.com",
    "reddit.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
}

SPECIALIST_DOMAINS = {
    "law.com",
    "researchgate.net",
    "techcrunch.com",
    "theregister.com",
    "bleepingcomputer.com",
}

NEGATION_PATTERNS = (
    r"\bno\b",
    r"\bnot\b",
    r"\bnever\b",
    r"\bwithout\b",
    r"\bdenied\b",
    r"\bfalse\b",
    r"\bunfounded\b",
)

HYPOTHETICAL_PATTERNS = (
    r"\bmay\b",
    r"\bmight\b",
    r"\bcould\b",
    r"\bpotential\b",
    r"\bpossible\b",
    r"\bhypothetical\b",
    r"\bscenario\b",
    r"\brisk of\b",
)

PROTECTIVE_CONTEXT_PATTERNS = (
    r"\bprevent(?:ed|ing|s)?\b",
    r"\bprotect(?:ed|ing|s)? against\b",
    r"\bdefend(?:ed|ing|s)? against\b",
    r"\bguidance\b",
    r"\bhow to\b",
    r"\bpreparedness\b",
    r"\bresilience\b",
    r"\bmonitoring\b",
    r"\bawareness\b",
)

DIRECT_INCIDENT_VERBS = (
    "suffered",
    "experienced",
    "reported",
    "confirmed",
    "disclosed",
    "was hit",
    "were hit",
    "fined",
    "penalized",
    "charged",
    "sued",
    "filed for",
    "closed",
    "halted",
    "cut",
    "laid off",
    "reduced",
    "suspended",
    "revoked",
)


@dataclass(frozen=True)
class SourceDocument:
    title: str
    url: str
    provider: str
    snippet: str = ""
    content: str = ""
    published_at: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    company: str
    category: str
    severity: str
    indicator: str
    source_url: str
    source_title: str
    source_provider: str
    source_quality: str
    publication_date: str | None
    evidence_excerpt: str
    entity_match: bool
    direct_claim: bool
    negated: bool
    hypothetical: bool
    protective_context: bool
    corroboration_count: int
    independent_domains: tuple[str, ...]
    verified: bool
    rejection_reason: str | None


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def classify_source_quality(
    url: str,
    identity: CompanyIdentity,
) -> str:
    domain = _domain(url)

    if not domain:
        return "UNKNOWN"

    if identity.website_domain and (
        domain == identity.website_domain
        or domain.endswith("." + identity.website_domain)
    ):
        return "COMPANY_OWNED"

    if (
        domain.endswith(".gov")
        or ".gov." in domain
        or domain.endswith(".europa.eu")
        or any(
            token in domain
            for token in (
                "regulator",
                "authority",
                "commission",
                "ministry",
                "centralbank",
                "central-bank",
                "sec.gov",
                "ftc.gov",
                "justice.gov",
            )
        )
    ):
        return "AUTHORITATIVE"

    if any(
        domain == item or domain.endswith("." + item)
        for item in REPUTABLE_NEWS_DOMAINS
    ):
        return "REPUTABLE_NEWS"

    if any(
        domain == item or domain.endswith("." + item)
        for item in SOCIAL_DOMAINS
    ):
        return "SOCIAL"

    if any(
        domain == item or domain.endswith("." + item)
        for item in SPECIALIST_DOMAINS
    ):
        return "SPECIALIST"

    return "GENERAL_WEB"


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()

    if not cleaned:
        return []

    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+(?=[A-Z0-9])",
            cleaned,
        )
        if sentence.strip()
    ]


def _window_has_pattern(
    sentence: str,
    indicator: str,
    patterns: Iterable[str],
    *,
    token_window: int = 8,
) -> bool:
    normalized = sentence.lower()
    indicator_index = normalized.find(indicator.lower())

    if indicator_index < 0:
        return False

    prefix = normalized[:indicator_index]
    tokens = prefix.split()
    local_prefix = " ".join(tokens[-token_window:])

    return any(
        re.search(pattern, local_prefix)
        for pattern in patterns
    )


def _has_protective_context(sentence: str) -> bool:
    normalized = sentence.lower()

    return any(
        re.search(pattern, normalized)
        for pattern in PROTECTIVE_CONTEXT_PATTERNS
    )


def _direct_claim(
    sentence: str,
    identity: CompanyIdentity,
    indicator: str,
) -> bool:
    normalized = sentence.lower()

    if not company_mentioned(identity, sentence):
        return False

    company_positions = [
        normalized.find(alias.lower())
        for alias in identity.aliases
        if alias.lower() in normalized
    ]
    indicator_position = normalized.find(indicator.lower())

    if not company_positions or indicator_position < 0:
        return False

    distance = min(
        abs(position - indicator_position)
        for position in company_positions
    )

    return (
        distance <= 160
        and any(
            verb in normalized
            for verb in DIRECT_INCIDENT_VERBS
        )
    )


def extract_evidence_candidates(
    identity: CompanyIdentity,
    documents: Iterable[SourceDocument],
) -> list[EvidenceRecord]:
    """
    Extract sentence-level candidates.

    A phrase found anywhere on a page is not enough. The exact excerpt, target
    entity match, context flags, source URL, and source quality are retained.
    """
    candidates: list[EvidenceRecord] = []

    for document in documents:
        combined = " ".join(
            part
            for part in (
                document.title,
                document.snippet,
                document.content,
            )
            if part
        )
        sentences = _sentences(combined)
        quality = classify_source_quality(
            document.url,
            identity,
        )

        for index, sentence in enumerate(sentences):
            context = " ".join(
                sentences[
                    max(0, index - 1):
                    min(len(sentences), index + 2)
                ]
            )

            for category, severity_map in RISK_TERMS.items():
                for severity, indicators in severity_map.items():
                    for indicator in indicators:
                        if indicator.lower() not in sentence.lower():
                            continue

                        entity_match = company_mentioned(
                            identity,
                            context,
                            source_url=document.url,
                        )
                        negated = _window_has_pattern(
                            sentence,
                            indicator,
                            NEGATION_PATTERNS,
                        )
                        hypothetical = _window_has_pattern(
                            sentence,
                            indicator,
                            HYPOTHETICAL_PATTERNS,
                        )
                        protective_context = _has_protective_context(
                            sentence
                        )
                        direct_claim = _direct_claim(
                            sentence,
                            identity,
                            indicator,
                        )

                        candidates.append(
                            EvidenceRecord(
                                company=identity.canonical_name,
                                category=category,
                                severity=severity,
                                indicator=indicator,
                                source_url=document.url,
                                source_title=document.title,
                                source_provider=document.provider,
                                source_quality=quality,
                                publication_date=document.published_at,
                                evidence_excerpt=sentence[:500],
                                entity_match=entity_match,
                                direct_claim=direct_claim,
                                negated=negated,
                                hypothetical=hypothetical,
                                protective_context=protective_context,
                                corroboration_count=0,
                                independent_domains=(),
                                verified=False,
                                rejection_reason=None,
                            )
                        )

    return candidates


def validate_evidence_candidates(
    candidates: Iterable[EvidenceRecord],
) -> list[EvidenceRecord]:
    """Apply attribution, context, source-quality, and corroboration rules."""
    candidate_list = list(candidates)
    groups: dict[tuple[str, str], list[EvidenceRecord]] = defaultdict(list)

    for record in candidate_list:
        groups[
            (
                record.category,
                record.indicator.lower(),
            )
        ].append(record)

    validated: list[EvidenceRecord] = []

    for record in candidate_list:
        peers = groups[
            (
                record.category,
                record.indicator.lower(),
            )
        ]
        credible_domains = {
            _domain(peer.source_url)
            for peer in peers
            if (
                peer.entity_match
                and not peer.negated
                and not peer.hypothetical
                and not peer.protective_context
                and peer.source_quality
                in {
                    "AUTHORITATIVE",
                    "COMPANY_OWNED",
                    "REPUTABLE_NEWS",
                    "SPECIALIST",
                }
            )
        }
        corroboration_count = len(
            credible_domains
        )

        rejection_reason: str | None = None

        if not record.entity_match:
            rejection_reason = (
                "The target company is not reliably linked to the indicator."
            )
        elif record.negated:
            rejection_reason = (
                "The excerpt negates or denies the alleged event."
            )
        elif record.hypothetical:
            rejection_reason = (
                "The excerpt is hypothetical or speculative."
            )
        elif record.protective_context:
            rejection_reason = (
                "The phrase appears in prevention, guidance, monitoring, or "
                "resilience context rather than as a confirmed incident."
            )
        elif record.source_quality == "SOCIAL":
            rejection_reason = (
                "Social/community content may be a lead but cannot independently "
                "create a verified risk signal."
            )
        elif record.severity in {"high", "critical"} and not record.direct_claim:
            rejection_reason = (
                "High-severity evidence must directly attribute the event to "
                "the target company."
            )
        elif record.severity == "critical":
            critical_supported = (
                record.source_quality == "AUTHORITATIVE"
                or (
                    record.source_quality == "COMPANY_OWNED"
                    and corroboration_count >= 2
                )
                or (
                    record.source_quality == "REPUTABLE_NEWS"
                    and corroboration_count >= 2
                )
            )

            if not critical_supported:
                rejection_reason = (
                    "Critical evidence requires an authoritative source or "
                    "independent corroboration from credible sources."
                )
        elif record.severity == "high":
            high_supported = (
                record.source_quality == "AUTHORITATIVE"
                or (
                    record.source_quality
                    in {
                        "COMPANY_OWNED",
                        "REPUTABLE_NEWS",
                        "SPECIALIST",
                    }
                    and corroboration_count >= 2
                )
            )

            if not high_supported:
                rejection_reason = (
                    "High-severity evidence requires authoritative support or "
                    "independent corroboration."
                )

        validated.append(
            replace(
                record,
                corroboration_count=corroboration_count,
                independent_domains=tuple(
                    sorted(
                        domain
                        for domain in credible_domains
                        if domain
                    )
                ),
                verified=rejection_reason is None,
                rejection_reason=rejection_reason,
            )
        )

    return validated
