"""Conservative vendor-candidate resolution for Sentinel Web-Risk.

This module performs no network, LLM, database, or provider calls. It converts
already-collected identity evidence into safe candidate-selection states.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable
from urllib.parse import urlparse

from core.company_identity import (
    normalize_company_name,
    normalize_website,
)


MAX_CANDIDATES = 8
AUTO_CONFIRM_THRESHOLD = 0.90
AUTO_CONFIRM_MARGIN = 0.18
PLAUSIBLE_CANDIDATE_THRESHOLD = 0.55

SOURCE_QUALITY_WEIGHTS = {
    "AUTHORITATIVE_IDENTITY": 0.24,
    "AUTHORITATIVE_CONTEXT": 0.00,
    "OFFICIAL_WEBSITE": 0.26,
    "POSSIBLE_COMPANY_WEBSITE": 0.10,
    "COMPANY_OWNED": 0.20,
    "REPUTABLE_BUSINESS_DIRECTORY": 0.08,
    "REPUTABLE_NEWS": 0.04,
    "SPECIALIST": 0.05,
    "GENERAL_WEB": 0.00,
    "SOCIAL": 0.00,
    "UNKNOWN": 0.00,
}

REQUESTED_DETAIL_FIELDS = (
    "country",
    "city",
    "website",
    "industry",
)


@dataclass(frozen=True)
class CandidateEvidence:
    """One public identity observation about a possible company."""

    legal_name: str
    source_url: str
    source_title: str
    source_quality: str
    website: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    aliases: tuple[str, ...] = ()
    registration_number: str | None = None
    parent_company: str | None = None
    public_private_status: str | None = None


@dataclass(frozen=True)
class VendorCandidate:
    """A deduplicated company identity candidate suitable for UI display."""

    candidate_id: str
    legal_name: str
    aliases: tuple[str, ...]
    website: str | None
    website_domain: str | None
    country: str | None
    city: str | None
    industry: str | None
    registration_number: str | None
    parent_company: str | None
    public_private_status: str | None
    identity_confidence: float
    confidence_label: str
    evidence_source_count: int
    source_quality_labels: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    match_reasons: tuple[str, ...]


@dataclass(frozen=True)
class VendorResolutionResult:
    """Safe result returned before any vendor-risk investigation begins."""

    resolution_status: str
    requested_name: str
    selected_candidate: VendorCandidate | None
    candidates: tuple[VendorCandidate, ...]
    requested_fields: tuple[str, ...]
    message: str
    coverage_notice: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None

    cleaned = " ".join(str(value).split()).strip()
    return cleaned or None


def _normalize_match_text(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _domain(url: str | None) -> str | None:
    if not url:
        return None

    candidate = url.strip()

    if "://" not in candidate:
        candidate = "https://" + candidate

    parsed = urlparse(candidate)

    if not parsed.netloc:
        return None

    return parsed.netloc.lower().removeprefix("www.")


def _candidate_key(evidence: CandidateEvidence) -> str:
    website_domain = _domain(
        evidence.website
    )

    if website_domain:
        return "domain:" + website_domain

    registration = _normalize_match_text(
        evidence.registration_number or ""
    )
    country = _normalize_match_text(
        evidence.country or ""
    )

    if registration:
        return (
            "registration:"
            + country
            + ":"
            + registration
        )

    return (
        "name:"
        + _normalize_match_text(
            evidence.legal_name
        )
        + ":"
        + country
    )


def _candidate_id(
    legal_name: str,
    website_domain: str | None,
    country: str | None,
) -> str:
    raw = "|".join(
        [
            _normalize_match_text(
                legal_name
            ),
            website_domain or "",
            _normalize_match_text(
                country or ""
            ),
        ]
    )
    compact = re.sub(
        r"[^a-z0-9]+",
        "-",
        raw,
    ).strip("-")

    return compact[:120] or "vendor-candidate"


def _name_similarity(
    requested_name: str,
    legal_name: str,
    aliases: Iterable[str],
) -> float:
    requested = _normalize_match_text(
        requested_name
    )
    options = {
        _normalize_match_text(
            legal_name
        ),
        *(
            _normalize_match_text(
                alias
            )
            for alias in aliases
            if str(alias).strip()
        ),
    }

    if requested in options:
        return 1.0

    requested_tokens = set(
        requested.split()
    )

    if not requested_tokens:
        return 0.0

    best = 0.0

    for option in options:
        option_tokens = set(
            option.split()
        )

        if not option_tokens:
            continue

        union = len(
            requested_tokens | option_tokens
        )

        if union:
            best = max(
                best,
                len(
                    requested_tokens
                    & option_tokens
                )
                / union,
            )

    return best


def _confidence_label(value: float) -> str:
    if value >= 0.85:
        return "HIGH"
    if value >= 0.65:
        return "MEDIUM"

    return "LIMITED"


def _merge_group(
    requested_name: str,
    records: list[CandidateEvidence],
    *,
    country: str | None,
    city: str | None,
    website: str | None,
    industry: str | None,
) -> VendorCandidate:
    primary = max(
        records,
        key=lambda item: (
            SOURCE_QUALITY_WEIGHTS.get(
                item.source_quality.upper(),
                0.0,
            ),
            bool(
                item.registration_number
            ),
            bool(
                item.website
            ),
        ),
    )

    aliases = tuple(
        sorted(
            {
                alias
                for record in records
                for alias in (
                    record.legal_name,
                    *record.aliases,
                )
                if str(alias).strip()
            },
            key=str.lower,
        )
    )

    website_values = [
        record.website
        for record in records
        if record.website
    ]
    candidate_website = (
        website_values[0]
        if website_values
        else None
    )
    normalized_website, website_domain = (
        normalize_website(
            candidate_website
        )
        if candidate_website
        else (
            None,
            None,
        )
    )

    def first_value(
        attribute: str,
    ) -> str | None:
        for record in records:
            value = _clean_optional(
                getattr(
                    record,
                    attribute,
                )
            )

            if value:
                return value

        return None

    candidate_country = first_value(
        "country"
    )
    candidate_city = first_value(
        "city"
    )
    candidate_industry = first_value(
        "industry"
    )
    registration_number = first_value(
        "registration_number"
    )
    parent_company = first_value(
        "parent_company"
    )
    public_private_status = first_value(
        "public_private_status"
    )

    quality_values = {
        record.source_quality.upper()
        for record in records
    }
    identity_quality_values = quality_values - {
        "AUTHORITATIVE_CONTEXT",
    }
    unique_evidence_urls = tuple(
        sorted(
            {
                record.source_url
                for record in records
                if record.source_url
            }
        )
    )
    unique_domains = {
        domain
        for domain in (
            _domain(
                record.source_url
            )
            for record in records
        )
        if domain
    }

    name_score = _name_similarity(
        requested_name,
        primary.legal_name,
        aliases,
    )
    strongest_quality = max(
        (
            SOURCE_QUALITY_WEIGHTS.get(
                quality,
                0.0,
            )
            for quality in identity_quality_values
        ),
        default=0.0,
    )

    confidence = 0.10
    confidence += name_score * 0.20
    confidence += strongest_quality
    match_reasons: list[str] = []

    if name_score >= 0.99:
        match_reasons.append(
            "Exact company-name or alias match"
        )
    elif name_score >= 0.60:
        match_reasons.append(
            "Strong company-name similarity"
        )

    normalized_requested_website = _domain(
        website
    )
    website_matches_user = bool(
        normalized_requested_website
        and website_domain
        and normalized_requested_website
        == website_domain
    )

    if website_matches_user:
        confidence += 0.34
        match_reasons.append(
            "Website matches user-provided domain"
        )

    if "AUTHORITATIVE_IDENTITY" in quality_values:
        confidence += 0.12
        match_reasons.append(
            "Government or corporate registry identity evidence"
        )

    if registration_number:
        confidence += 0.12
        match_reasons.append(
            "Registration identifier found"
        )

    if (
        "OFFICIAL_WEBSITE"
        in quality_values
    ):
        match_reasons.append(
            "User-confirmed website evidence"
        )
    elif (
        "POSSIBLE_COMPANY_WEBSITE"
        in quality_values
    ):
        match_reasons.append(
            "Possible company-domain lead"
        )

    if (
        country
        and candidate_country
        and _normalize_match_text(
            country
        )
        == _normalize_match_text(
            candidate_country
        )
    ):
        confidence += 0.10
        match_reasons.append(
            "Country matches user-provided context"
        )

    if (
        city
        and candidate_city
        and _normalize_match_text(
            city
        )
        == _normalize_match_text(
            candidate_city
        )
    ):
        confidence += 0.06
        match_reasons.append(
            "City matches user-provided context"
        )

    if (
        industry
        and candidate_industry
        and _normalize_match_text(
            industry
        )
        == _normalize_match_text(
            candidate_industry
        )
    ):
        confidence += 0.06
        match_reasons.append(
            "Industry matches user-provided context"
        )

    if len(unique_domains) >= 2:
        confidence += min(
            0.14,
            (
                len(
                    unique_domains
                )
                - 1
            )
            * 0.07,
        )
        match_reasons.append(
            "Supported by independent public sources"
        )

    has_authoritative_corroboration = (
        "AUTHORITATIVE_IDENTITY" in quality_values
        and (
            len(unique_domains) >= 2
            or website_matches_user
        )
    )
    has_multi_source_website_support = (
        (
            "OFFICIAL_WEBSITE"
            in quality_values
            or "POSSIBLE_COMPANY_WEBSITE"
            in quality_values
        )
        and len(unique_domains) >= 2
    )

    # Single-source, non-authoritative search leads can never look verified.
    if (
        len(unique_domains) <= 1
        and not website_matches_user
        and "AUTHORITATIVE_IDENTITY"
        not in quality_values
    ):
        confidence = min(
            confidence,
            0.54,
        )

    # A directory by itself is only a lead.
    if (
        quality_values
        <= {
            "REPUTABLE_BUSINESS_DIRECTORY",
            "GENERAL_WEB",
            "POSSIBLE_COMPANY_WEBSITE",
        }
        and len(unique_domains) <= 1
        and not website_matches_user
    ):
        confidence = min(
            confidence,
            0.54,
        )

    # HIGH confidence requires explicit or corroborated identity evidence.
    if not (
        website_matches_user
        or has_authoritative_corroboration
        or has_multi_source_website_support
    ):
        confidence = min(
            confidence,
            0.79,
        )

    confidence = round(
        min(
            0.99,
            max(
                0.0,
                confidence,
            ),
        ),
        2,
    )

    return VendorCandidate(
        candidate_id=_candidate_id(
            primary.legal_name,
            website_domain,
            candidate_country,
        ),
        legal_name=primary.legal_name,
        aliases=aliases,
        website=normalized_website,
        website_domain=website_domain,
        country=candidate_country,
        city=candidate_city,
        industry=candidate_industry,
        registration_number=registration_number,
        parent_company=parent_company,
        public_private_status=public_private_status,
        identity_confidence=confidence,
        confidence_label=_confidence_label(
            confidence
        ),
        evidence_source_count=len(
            unique_evidence_urls
        ),
        source_quality_labels=tuple(
            sorted(
                quality_values
            )
        ),
        evidence_urls=unique_evidence_urls,
        match_reasons=tuple(
            dict.fromkeys(
                match_reasons
            )
        ),
    )


def resolve_vendor_candidates(
    requested_name: str,
    evidence: Iterable[CandidateEvidence],
    *,
    country: str | None = None,
    city: str | None = None,
    website: str | None = None,
    industry: str | None = None,
) -> VendorResolutionResult:
    """Resolve candidate evidence without guessing or claiming full coverage."""
    requested = normalize_company_name(
        requested_name
    )
    grouped: dict[
        str,
        list[CandidateEvidence],
    ] = {}

    for record in evidence:
        normalized_record = replace(
            record,
            legal_name=normalize_company_name(
                record.legal_name
            ),
            source_url=_clean_optional(
                record.source_url
            )
            or "",
            source_title=_clean_optional(
                record.source_title
            )
            or "Untitled public source",
            source_quality=(
                _clean_optional(
                    record.source_quality
                )
                or "UNKNOWN"
            ).upper(),
            website=_clean_optional(
                record.website
            ),
            country=_clean_optional(
                record.country
            ),
            city=_clean_optional(
                record.city
            ),
            industry=_clean_optional(
                record.industry
            ),
            registration_number=_clean_optional(
                record.registration_number
            ),
            parent_company=_clean_optional(
                record.parent_company
            ),
            public_private_status=_clean_optional(
                record.public_private_status
            ),
        )
        grouped.setdefault(
            _candidate_key(
                normalized_record
            ),
            [],
        ).append(
            normalized_record
        )

    candidates = [
        _merge_group(
            requested,
            records,
            country=country,
            city=city,
            website=website,
            industry=industry,
        )
        for records in grouped.values()
    ]
    candidates.sort(
        key=lambda candidate: (
            -candidate.identity_confidence,
            candidate.legal_name.lower(),
            (
                candidate.country
                or ""
            ).lower(),
        )
    )

    plausible = tuple(
        candidate
        for candidate in candidates[
            :MAX_CANDIDATES
        ]
        if (
            candidate.identity_confidence
            >= PLAUSIBLE_CANDIDATE_THRESHOLD
        )
    )

    coverage_notice = (
        "Candidate matches are based on accessible public sources and "
        "may not represent every business using this name."
    )

    if not plausible:
        return VendorResolutionResult(
            resolution_status=(
                "MORE_INFORMATION_REQUIRED"
            ),
            requested_name=requested,
            selected_candidate=None,
            candidates=(),
            requested_fields=(
                REQUESTED_DETAIL_FIELDS
            ),
            message=(
                "No sufficiently authenticated company identity was found. "
                "Provide a country, city, website, or industry."
            ),
            coverage_notice=coverage_notice,
        )

    top = plausible[0]
    runner_up = (
        plausible[1]
        if len(plausible) > 1
        else None
    )
    margin = (
        top.identity_confidence
        - runner_up.identity_confidence
        if runner_up
        else top.identity_confidence
    )

    strong_identity_basis = (
        "Website matches user-provided domain"
        in top.match_reasons
        or (
            "AUTHORITATIVE_IDENTITY"
            in top.source_quality_labels
            and top.evidence_source_count >= 2
        )
        or (
            top.evidence_source_count >= 2
            and (
                "OFFICIAL_WEBSITE"
                in top.source_quality_labels
                or "POSSIBLE_COMPANY_WEBSITE"
                in top.source_quality_labels
            )
        )
    )

    auto_confirm = (
        top.identity_confidence
        >= AUTO_CONFIRM_THRESHOLD
        and strong_identity_basis
        and (
            runner_up is None
            or margin >= AUTO_CONFIRM_MARGIN
        )
    )

    if auto_confirm:
        return VendorResolutionResult(
            resolution_status="CONFIRMED",
            requested_name=requested,
            selected_candidate=top,
            candidates=plausible,
            requested_fields=(),
            message=(
                "A single strongly authenticated company identity was found."
            ),
            coverage_notice=coverage_notice,
        )

    selectable = tuple(
        candidate
        for candidate in plausible
        if (
            candidate.identity_confidence
            >= 0.65
            and candidate.evidence_source_count >= 2
        )
    )

    if len(selectable) >= 2:
        return VendorResolutionResult(
            resolution_status=(
                "SELECTION_REQUIRED"
            ),
            requested_name=requested,
            selected_candidate=None,
            candidates=selectable,
            requested_fields=(),
            message=(
                "Several independently supported businesses match this name. "
                "Select the correct vendor before investigation."
            ),
            coverage_notice=coverage_notice,
        )

    requested_fields = tuple(
        field
        for field, value in (
            (
                "country",
                country,
            ),
            (
                "city",
                city,
            ),
            (
                "website",
                website,
            ),
            (
                "industry",
                industry,
            ),
        )
        if not _clean_optional(
            value
        )
    )

    return VendorResolutionResult(
        resolution_status=(
            "MORE_INFORMATION_REQUIRED"
        ),
        requested_name=requested,
        selected_candidate=None,
        candidates=plausible,
        requested_fields=(
            requested_fields
            or REQUESTED_DETAIL_FIELDS
        ),
        message=(
            "Possible company leads were found, but the identity evidence "
            "is not sufficiently authenticated. Provide more context."
        ),
        coverage_notice=coverage_notice,
    )
