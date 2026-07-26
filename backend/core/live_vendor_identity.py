"""Live, conservative vendor identity discovery for Sentinel Web-Risk.

The collector uses existing Bright Data SERP and genuine Remote MCP search
clients. It performs no scraping, LLM inference, risk scoring, or database
writes. Search-result text is treated as candidate identity evidence, not as a
verified risk claim.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

from core.brightdata import serp_client
from core.brightdata_remote_mcp import remote_mcp_client
from core.industry_profiles import infer_industry
from core.vendor_resolution import CandidateEvidence


SERP_TIMEOUT_SECONDS = 50
MCP_TIMEOUT_SECONDS = 50
MAX_RESULTS_PER_QUERY = 8
MAX_IDENTITY_RECORDS = 24

REPUTABLE_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "cnbc.com",
    "ft.com",
    "wsj.com",
    "bloomberg.com",
}

BUSINESS_DIRECTORY_DOMAINS = {
    "linkedin.com",
    "crunchbase.com",
    "dnb.com",
    "opencorporates.com",
    "zoominfo.com",
    "bloomberg.com",
}

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
}

SEARCH_PLATFORM_DOMAINS = {
    "google.com",
    "bing.com",
    "yahoo.com",
}

COUNTRY_TLD_MAP = {
    "bd": "Bangladesh",
    "sg": "Singapore",
    "my": "Malaysia",
    "in": "India",
    "pk": "Pakistan",
    "lk": "Sri Lanka",
    "np": "Nepal",
    "ae": "United Arab Emirates",
    "qa": "Qatar",
    "sa": "Saudi Arabia",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "us": "United States",
    "ca": "Canada",
    "au": "Australia",
    "nz": "New Zealand",
    "de": "Germany",
    "fr": "France",
    "it": "Italy",
    "es": "Spain",
    "nl": "Netherlands",
    "se": "Sweden",
    "no": "Norway",
    "fi": "Finland",
    "dk": "Denmark",
    "ch": "Switzerland",
    "at": "Austria",
    "be": "Belgium",
    "ie": "Ireland",
    "jp": "Japan",
    "kr": "South Korea",
    "cn": "China",
    "hk": "Hong Kong",
    "id": "Indonesia",
    "ph": "Philippines",
    "th": "Thailand",
    "vn": "Vietnam",
    "br": "Brazil",
    "mx": "Mexico",
    "za": "South Africa",
}

COUNTRY_NAMES = tuple(
    sorted(
        set(COUNTRY_TLD_MAP.values()),
        key=len,
        reverse=True,
    )
)

TITLE_SEPARATORS = (
    " | ",
    " — ",
    " – ",
    " - ",
    ": ",
)

OFFICIAL_HINTS = (
    "official",
    "home",
    "homepage",
    "about us",
    "company",
    "corporate",
    "welcome",
)

REGISTRY_DOMAIN_MARKERS = (
    "companieshouse.gov.uk",
    "sec.gov",
    "business.gov",
    "registry",
    "registrar",
    "commission",
    "authority",
    "ministry",
)


class VendorResolutionRequestLike(Protocol):
    vendor_name: str
    country: str | None
    city: str | None
    website: str | None
    industry: str | None
    language: str


@dataclass(frozen=True)
class IdentityEvidenceBatch:
    """Auditable result of one live identity-discovery operation."""

    records: tuple[CandidateEvidence, ...]
    search_performed: bool
    providers: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    queries_executed: tuple[str, ...] = ()
    started_at: str | None = None
    completed_at: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _normalize_text(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


def _valid_http_url(url: str) -> bool:
    parsed = urlparse(url)

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


def _registered_domain_matches(
    domain: str,
    expected_domain: str,
) -> bool:
    return (
        domain == expected_domain
        or domain.endswith("." + expected_domain)
    )


def _request_website_domain(
    website: str | None,
) -> str | None:
    cleaned = _clean(website)

    if not cleaned:
        return None

    if "://" not in cleaned:
        cleaned = "https://" + cleaned

    parsed = urlparse(cleaned)

    if not parsed.netloc:
        return None

    return parsed.netloc.lower().removeprefix("www.")


def build_identity_queries(
    request: VendorResolutionRequestLike,
) -> tuple[str, str, str]:
    """Build two SERP queries and one MCP query for identity discovery."""
    name = _clean(request.vendor_name)
    quoted_name = f'"{name}"'

    context_parts = [
        _clean(request.country),
        _clean(request.city),
        _clean(request.industry),
    ]
    context = " ".join(
        f'"{part}"'
        for part in context_parts
        if part
    )

    website_domain = _request_website_domain(
        request.website
    )
    website_context = (
        f' site:{website_domain}'
        if website_domain
        else ""
    )

    official_query = " ".join(
        part
        for part in (
            quoted_name,
            context,
            "official website company headquarters",
            website_context,
        )
        if part
    )
    registry_query = " ".join(
        part
        for part in (
            quoted_name,
            context,
            "company registry registration legal name industry",
        )
        if part
    )
    mcp_query = " ".join(
        part
        for part in (
            quoted_name,
            context,
            "official website company profile country industry",
        )
        if part
    )

    return (
        official_query,
        registry_query,
        mcp_query,
    )


def classify_identity_source(
    url: str,
    *,
    requested_website_domain: str | None,
    combined_text: str,
) -> str:
    """Classify a candidate source without claiming unsupported authority."""
    domain = _domain(url)
    normalized_text = combined_text.lower()

    if requested_website_domain and _registered_domain_matches(
        domain,
        requested_website_domain,
    ):
        return "OFFICIAL_WEBSITE"

    if (
        domain.endswith(".gov")
        or ".gov." in domain
        or domain.endswith(".europa.eu")
        or any(
            marker in domain
            for marker in REGISTRY_DOMAIN_MARKERS
        )
    ):
        return "AUTHORITATIVE"

    if any(
        domain == item
        or domain.endswith("." + item)
        for item in SOCIAL_DOMAINS
    ):
        return "SOCIAL"

    if any(
        domain == item
        or domain.endswith("." + item)
        for item in BUSINESS_DIRECTORY_DOMAINS
    ):
        return "REPUTABLE_BUSINESS_DIRECTORY"

    if any(
        domain == item
        or domain.endswith("." + item)
        for item in REPUTABLE_NEWS_DOMAINS
    ):
        return "REPUTABLE_NEWS"

    official_hint = any(
        hint in normalized_text
        for hint in OFFICIAL_HINTS
    )
    blocked_domain = any(
        domain == item
        or domain.endswith("." + item)
        for item in (
            *BUSINESS_DIRECTORY_DOMAINS,
            *SOCIAL_DOMAINS,
            *REPUTABLE_NEWS_DOMAINS,
            *SEARCH_PLATFORM_DOMAINS,
        )
    )

    if official_hint and not blocked_domain:
        return "OFFICIAL_WEBSITE"

    return "GENERAL_WEB"


def _result_is_relevant(
    requested_name: str,
    title: str,
    snippet: str,
    url: str,
    requested_website_domain: str | None,
) -> bool:
    combined = _normalize_text(
        f"{title} {snippet}"
    )
    requested = _normalize_text(
        requested_name
    )

    if requested_website_domain and _registered_domain_matches(
        _domain(url),
        requested_website_domain,
    ):
        return True

    if not requested:
        return False

    if requested in combined:
        return True

    requested_tokens = [
        token
        for token in requested.split()
        if len(token) >= 3
    ]

    return (
        bool(requested_tokens)
        and all(
            token in combined
            for token in requested_tokens
        )
    )


def _extract_legal_name(
    requested_name: str,
    title: str,
) -> str:
    """Extract only a conservative title segment; otherwise keep user input."""
    cleaned_title = _clean(title)

    if not cleaned_title:
        return requested_name

    requested_normalized = _normalize_text(
        requested_name
    )

    candidates = [
        cleaned_title
    ]

    for separator in TITLE_SEPARATORS:
        if separator in cleaned_title:
            candidates.extend(
                segment.strip()
                for segment in cleaned_title.split(
                    separator
                )
                if segment.strip()
            )

    for candidate in candidates:
        normalized_candidate = _normalize_text(
            candidate
        )

        if (
            requested_normalized
            and requested_normalized in normalized_candidate
            and 2 <= len(candidate) <= 120
        ):
            return candidate

    return requested_name


def _country_from_result(
    url: str,
    combined_text: str,
    requested_country: str | None,
) -> str | None:
    normalized_text = combined_text.lower()
    requested = _clean(
        requested_country
    )

    if requested and requested.lower() in normalized_text:
        return requested

    domain = _domain(url)
    final_label = domain.rsplit(".", 1)[-1]

    if final_label in COUNTRY_TLD_MAP:
        return COUNTRY_TLD_MAP[
            final_label
        ]

    for country_name in COUNTRY_NAMES:
        if country_name.lower() in normalized_text:
            return country_name

    return None


def _city_from_result(
    combined_text: str,
    requested_city: str | None,
) -> str | None:
    city = _clean(
        requested_city
    )

    if city and city.lower() in combined_text.lower():
        return city

    return None


def _industry_from_result(
    combined_text: str,
    requested_industry: str | None,
) -> str | None:
    declared = _clean(
        requested_industry
    )

    if declared and declared.lower() in combined_text.lower():
        return declared

    profile, confidence = infer_industry(
        combined_text
    )

    if (
        profile.key != "general"
        and confidence >= 0.55
    ):
        return profile.display_name

    return None


def result_to_candidate_evidence(
    request: VendorResolutionRequestLike,
    result: dict[str, str],
) -> CandidateEvidence | None:
    """Convert one relevant search result into conservative identity evidence."""
    title = _clean(
        result.get("title")
    )
    snippet = _clean(
        result.get("snippet")
    )
    url = _clean(
        result.get("url")
    )

    if not _valid_http_url(url):
        return None

    requested_website_domain = _request_website_domain(
        request.website
    )

    if not _result_is_relevant(
        request.vendor_name,
        title,
        snippet,
        url,
        requested_website_domain,
    ):
        return None

    combined_text = f"{title} {snippet}".strip()
    source_quality = classify_identity_source(
        url,
        requested_website_domain=(
            requested_website_domain
        ),
        combined_text=combined_text,
    )

    legal_name = _extract_legal_name(
        request.vendor_name,
        title,
    )

    candidate_website = (
        url
        if source_quality == "OFFICIAL_WEBSITE"
        else None
    )

    return CandidateEvidence(
        legal_name=legal_name,
        source_url=url,
        source_title=title or url,
        source_quality=source_quality,
        website=candidate_website,
        country=_country_from_result(
            url,
            combined_text,
            request.country,
        ),
        city=_city_from_result(
            combined_text,
            request.city,
        ),
        industry=_industry_from_result(
            combined_text,
            request.industry,
        ),
        aliases=(
            request.vendor_name,
        ),
        registration_number=None,
        parent_company=None,
        public_private_status=None,
    )


class LiveVendorIdentityCollector:
    """Collect identity candidates through existing live search clients."""

    def __init__(
        self,
        *,
        serp: Any = None,
        mcp: Any = None,
    ) -> None:
        self.serp = serp or serp_client
        self.mcp = mcp or remote_mcp_client

    async def collect(
        self,
        request: VendorResolutionRequestLike,
    ) -> IdentityEvidenceBatch:
        started_at = _utc_now_iso()
        queries = build_identity_queries(
            request
        )
        language = (
            _clean(request.language).lower()
            or "en"
        )

        calls = (
            asyncio.wait_for(
                self.serp.search(
                    queries[0],
                    num_results=MAX_RESULTS_PER_QUERY,
                    lang=language,
                ),
                timeout=SERP_TIMEOUT_SECONDS,
            ),
            asyncio.wait_for(
                self.serp.search(
                    queries[1],
                    num_results=MAX_RESULTS_PER_QUERY,
                    lang=language,
                ),
                timeout=SERP_TIMEOUT_SECONDS,
            ),
            asyncio.wait_for(
                self.mcp.search(
                    queries[2],
                    limit=MAX_RESULTS_PER_QUERY,
                ),
                timeout=MCP_TIMEOUT_SECONDS,
            ),
        )

        outcomes = await asyncio.gather(
            *calls,
            return_exceptions=True,
        )

        provider_labels = (
            "Bright Data SERP",
            "Bright Data SERP",
            "Bright Data Remote MCP",
        )
        warnings: list[str] = []
        providers_used: list[str] = []
        combined_results: list[dict[str, str]] = []

        for provider, outcome in zip(
            provider_labels,
            outcomes,
        ):
            if isinstance(
                outcome,
                BaseException,
            ):
                warnings.append(
                    f"{provider} identity search was unavailable: "
                    f"{type(outcome).__name__}."
                )
                continue

            providers_used.append(
                provider
            )

            if not outcome:
                warnings.append(
                    f"{provider} returned no usable identity results."
                )
                continue

            combined_results.extend(
                outcome
            )

        unique_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for result in combined_results:
            url = _clean(
                result.get("url")
            )

            if not url or url in seen_urls:
                continue

            seen_urls.add(
                url
            )
            unique_results.append(
                result
            )

        records: list[CandidateEvidence] = []

        for result in unique_results:
            record = result_to_candidate_evidence(
                request,
                result,
            )

            if record is not None:
                records.append(
                    record
                )

            if len(records) >= MAX_IDENTITY_RECORDS:
                break

        return IdentityEvidenceBatch(
            records=tuple(
                records
            ),
            search_performed=True,
            providers=tuple(
                dict.fromkeys(
                    providers_used
                )
            ),
            warnings=tuple(
                warnings
            ),
            queries_executed=queries,
            started_at=started_at,
            completed_at=_utc_now_iso(),
        )


_default_collector = LiveVendorIdentityCollector()


async def collect_live_vendor_identity_evidence(
    request: VendorResolutionRequestLike,
) -> IdentityEvidenceBatch:
    """Collect live identity evidence using the configured default clients."""
    return await _default_collector.collect(
        request
    )
