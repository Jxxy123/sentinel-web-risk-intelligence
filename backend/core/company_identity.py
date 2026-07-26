"""Company identity normalization and ambiguity controls for Sentinel Web-Risk."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "company",
    "co",
    "ltd",
    "limited",
    "llc",
    "plc",
    "gmbh",
    "sa",
    "ag",
    "pte",
    "sdn",
    "bhd",
    "group",
    "holdings",
}

GENERIC_NAME_TOKENS = {
    "abc",
    "global",
    "international",
    "enterprise",
    "enterprises",
    "trading",
    "services",
    "solutions",
    "business",
    "company",
    "group",
    "store",
    "shop",
    "industries",
}


@dataclass(frozen=True)
class CompanyIdentity:
    """Resolved or partially resolved identity for one requested business."""

    requested_name: str
    canonical_name: str
    aliases: tuple[str, ...]
    website: str | None
    website_domain: str | None
    country: str | None
    industry: str | None
    confidence: float
    status: str
    ambiguity_reason: str | None


def normalize_company_name(value: str) -> str:
    """Normalize human-entered company names without changing their meaning."""
    normalized = " ".join(str(value or "").split()).strip()

    if not normalized:
        raise ValueError("Company name cannot be empty.")

    if len(normalized) > 200:
        raise ValueError("Company name exceeds 200 characters.")

    return normalized


def _normalize_alias(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _core_tokens(value: str) -> list[str]:
    return [
        token
        for token in _normalize_alias(value).split()
        if token not in LEGAL_SUFFIXES
    ]


def normalize_website(value: str | None) -> tuple[str | None, str | None]:
    """Return a normalized website URL and bare domain."""
    if not value:
        return None, None

    candidate = value.strip()

    if not candidate:
        return None, None

    if "://" not in candidate:
        candidate = "https://" + candidate

    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Company website must be a valid HTTP or HTTPS URL.")

    domain = parsed.netloc.lower().removeprefix("www.")
    return f"{parsed.scheme}://{parsed.netloc}", domain


def build_company_identity(
    requested_name: str,
    *,
    canonical_name: str | None = None,
    aliases: Iterable[str] | None = None,
    website: str | None = None,
    country: str | None = None,
    industry: str | None = None,
) -> CompanyIdentity:
    """
    Build a conservative identity object.

    Generic or extremely short names are marked ambiguous unless additional
    context such as a website, country, or explicit canonical name is supplied.
    """
    requested = normalize_company_name(requested_name)
    canonical = normalize_company_name(canonical_name or requested)
    normalized_website, domain = normalize_website(website)

    alias_values = {
        canonical,
        requested,
        *(alias for alias in (aliases or []) if str(alias).strip()),
    }
    alias_tuple = tuple(
        sorted(
            {
                " ".join(str(alias).split()).strip()
                for alias in alias_values
                if str(alias).strip()
            },
            key=lambda item: (
                item.lower() != canonical.lower(),
                item.lower(),
            ),
        )
    )

    tokens = _core_tokens(canonical)
    generic_token_count = sum(
        token in GENERIC_NAME_TOKENS
        for token in tokens
    )

    context_count = sum(
        bool(value)
        for value in (
            domain,
            country and country.strip(),
            industry and industry.strip(),
            canonical_name and canonical_name.strip(),
        )
    )

    ambiguous = (
        not tokens
        or (
            len(tokens) == 1
            and (
                len(tokens[0]) <= 3
                or tokens[0] in GENERIC_NAME_TOKENS
            )
            and context_count == 0
        )
        or (
            tokens
            and generic_token_count == len(tokens)
            and context_count == 0
        )
    )

    if ambiguous:
        return CompanyIdentity(
            requested_name=requested,
            canonical_name=canonical,
            aliases=alias_tuple,
            website=normalized_website,
            website_domain=domain,
            country=country.strip() if country else None,
            industry=industry.strip() if industry else None,
            confidence=0.25,
            status="AMBIGUOUS",
            ambiguity_reason=(
                "The company name is too generic to identify reliably. "
                "A country, city, website, or more specific legal name is required."
            ),
        )

    confidence = 0.55
    confidence += 0.20 if domain else 0.0
    confidence += 0.10 if country else 0.0
    confidence += 0.10 if industry else 0.0
    confidence += 0.05 if canonical_name else 0.0

    return CompanyIdentity(
        requested_name=requested,
        canonical_name=canonical,
        aliases=alias_tuple,
        website=normalized_website,
        website_domain=domain,
        country=country.strip() if country else None,
        industry=industry.strip() if industry else None,
        confidence=round(min(confidence, 1.0), 2),
        status="RESOLVED",
        ambiguity_reason=None,
    )


def company_mentioned(
    identity: CompanyIdentity,
    text: str,
    *,
    source_url: str | None = None,
) -> bool:
    """Return True when text or an official domain supports an entity match."""
    normalized_text = _normalize_alias(text)

    for alias in identity.aliases:
        normalized_alias = _normalize_alias(alias)

        if not normalized_alias:
            continue

        if re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
            normalized_text,
        ):
            return True

    if identity.website_domain and source_url:
        parsed = urlparse(source_url)
        source_domain = parsed.netloc.lower().removeprefix("www.")

        if (
            source_domain == identity.website_domain
            or source_domain.endswith("." + identity.website_domain)
        ):
            return True

    return False
