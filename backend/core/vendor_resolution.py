"""Conservative vendor-candidate resolution for Sentinel Web-Risk.

This module performs no network, LLM, database, or provider calls. It converts
already-collected public identity evidence into safe candidate-selection states.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable
from urllib.parse import urlparse

from core.company_identity import (
    build_company_identity,
    normalize_company_name,
    normalize_website,
)


MAX_CANDIDATES = 8
AUTO_CONFIRM_THRESHOLD = 0.85
AUTO_CONFIRM_MARGIN = 0.15
PLAUSIBLE_CANDIDATE_THRESHOLD = 0.45

SOURCE_QUALITY_WEIGHTS = {
    "AUTHORITATIVE": 0.28,
    "OFFICIAL_WEBSITE": 0.26,
    "COMPANY_OWNED": 0.24,
    "REPUTABLE_BUSINESS_DIRECTORY": 0.12,
    "REPUTABLE_NEWS": 0.10,
    "SPECIALIST": 0.08,
    "GENERAL_WEB": 0.04,
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
        """Return a JSON-safe response payload."""
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

    normalized_name = _normalize_match_text(
        evidence.legal_name
    )
    normalized_country = _normalize_match_text(
        evidence.country or ""
    )
    registration = _normalize_match_text(
        evidence.registration_number or ""
    )

    if registration:
        return (
            "registration:"
            + normalized_country
            + ":"
            + registration
        )

    return (
        "name:"
        + normalized_name
        + ":"
        + normalized_country
    )


def _candidate_id(
    legal_name: str,
    website_domain: str | None,
    country: str | None,
) -> str:
    raw = "|".join(
        [
            _normalize_match_text(legal_name),
            website_domain or "",
            _normalize_match_text(country or ""),
        ]
    )

    # Stable readable identifier; not a secret or database identifier.
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
        _normalize_match_text(legal_name),
        *(
            _normalize_match_text(alias)
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

        intersection = len(
            requested_tokens & option_tokens
        )
        union = len(
            requested_tokens | option_tokens
        )
        score = (
            intersection / union
            if union
            else 0.0
        )
        best = max(
            best,
            score,
        )

    return best


def _confidence_label(
    value: float,
) -> str:
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
            bool(item.website),
            bool(item.registration_number),
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

    countries = [
        _clean_optional(
            record.country
        )
        for record in records
        if _clean_optional(record.country)
    ]
    cities = [
        _clean_optional(
            record.city
        )
        for record in records
        if _clean_optional(record.city)
    ]
    industries = [
        _clean_optional(
            record.industry
        )
        for record in records
        if _clean_optional(record.industry)
    ]
    registrations = [
        _clean_optional(
            record.registration_number
        )
        for record in records
        if _clean_optional(
            record.registration_number
        )
    ]
    parents = [
        _clean_optional(
            record.parent_company
        )
        for record in records
        if _clean_optional(
            record.parent_company
        )
    ]
    public_private_values = [
        _clean_optional(
            record.public_private_status
        )
        for record in records
        if _clean_optional(
            record.public_private_status
        )
    ]

    candidate_country = (
        countries[0]
        if countries
        else None
    )
    candidate_city = (
        cities[0]
        if cities
        else None
    )
    candidate_industry = (
        industries[0]
        if industries
        else None
    )

    name_score = _name_similarity(
        requested_name,
        primary.legal_name,
        aliases,
    )

    quality_values = {
        record.source_quality.upper()
        for record in records
    }
    strongest_quality = max(
        (
            SOURCE_QUALITY_WEIGHTS.get(
                value,
                0.0,
            )
            for value in quality_values
        ),
        default=0.0,
    )

    confidence = 0.18
    match_reasons: list[str] = []

    confidence += name_score * 0.28

    if name_score >= 0.99:
        match_reasons.append(
            "Exact company-name or alias match"
        )
    elif name_score >= 0.60:
        match_reasons.append(
            "Strong company-name similarity"
        )

    confidence += strongest_quality

    if (
        "OFFICIAL_WEBSITE" in quality_values
        or "COMPANY_OWNED" in quality_values
    ):
        match_reasons.append(
            "Official company website evidence"
        )

    if "AUTHORITATIVE" in quality_values:
        match_reasons.append(
            "Government or regulator evidence"
        )

    if website_domain:
        confidence += 0.12
        match_reasons.append(
            "Company domain identified"
        )

    if registrations:
        confidence += 0.10
        match_reasons.append(
            "Registration identifier found"
        )

    normalized_requested_website = _domain(
        website
    )

    if (
        normalized_requested_website
        and website_domain
        and normalized_requested_website
        == website_domain
    ):
        confidence += 0.20
        match_reasons.append(
            "Website matches user-provided domain"
        )

    if (
        country
        and candidate_country
        and _normalize_match_text(country)
        == _normalize_match_text(
            candidate_country
        )
    ):
        confidence += 0.12
        match_reasons.append(
            "Country matches user-provided context"
        )

    if (
        city
        and candidate_city
        and _normalize_match_text(city)
        == _normalize_match_text(
            candidate_city
        )
    ):
        confidence += 0.08
        match_reasons.append(
            "City matches user-provided context"
        )

    if (
        industry
        and candidate_industry
        and _normalize_match_text(industry)
        == _normalize_match_text(
            candidate_industry
        )
    ):
        confidence += 0.08
        match_reasons.append(
            "Industry matches user-provided context"
        )

    unique_evidence_urls = tuple(
        sorted(
            {
                record.source_url
                for record in records
                if record.source_url
            }
        )
    )

    if len(unique_evidence_urls) >= 2:
        confidence += min(
            0.12,
            (
                len(unique_evidence_urls) - 1
            )
            * 0.04,
        )
        match_reasons.append(
            "Supported by multiple public sources"
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
        registration_number=(
            registrations[0]
            if registrations
            else None
        ),
        parent_company=(
            parents[0]
            if parents
            else None
        ),
        public_private_status=(
            public_private_values[0]
            if public_private_values
            else None
        ),
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
    """
    Resolve public candidate evidence into a safe pre-investigation state.

    The function never claims complete internet coverage and never starts an
    investigation. A candidate is auto-confirmed only when evidence is strong,
    unique, and materially better than every alternative.
    """
    requested = normalize_company_name(
        requested_name
    )
    supplied_identity = build_company_identity(
        requested,
        website=website,
        country=country,
        industry=industry,
    )

    grouped: dict[
        str,
        list[CandidateEvidence],
    ] = {}

    for record in evidence:
        legal_name = normalize_company_name(
            record.legal_name
        )

        normalized_record = replace(
            record,
            legal_name=legal_name,
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
            registration_number=(
                _clean_optional(
                    record.registration_number
                )
            ),
            parent_company=_clean_optional(
                record.parent_company
            ),
            public_private_status=(
                _clean_optional(
                    record.public_private_status
                )
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
                "No sufficiently supported company identity could be "
                "confirmed. Provide a country, city, website, or industry."
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

    auto_confirm = (
        top.identity_confidence
        >= AUTO_CONFIRM_THRESHOLD
        and (
            runner_up is None
            or margin >= AUTO_CONFIRM_MARGIN
        )
        and (
            top.website_domain is not None
            or top.registration_number is not None
            or "AUTHORITATIVE"
            in top.source_quality_labels
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
                "A single strongly supported company identity was found."
            ),
            coverage_notice=coverage_notice,
        )

    if len(plausible) >= 2:
        return VendorResolutionResult(
            resolution_status=(
                "SELECTION_REQUIRED"
            ),
            requested_name=requested,
            selected_candidate=None,
            candidates=plausible,
            requested_fields=(),
            message=(
                "Several plausible businesses match this name. "
                "Select the correct vendor before investigation."
            ),
            coverage_notice=coverage_notice,
        )

    # One weak or incomplete candidate is not silently accepted.
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
        if not _clean_optional(value)
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
            "One possible business was found, but its identity evidence "
            "is not strong enough for automatic confirmation."
        ),
        coverage_notice=coverage_notice,
    )
