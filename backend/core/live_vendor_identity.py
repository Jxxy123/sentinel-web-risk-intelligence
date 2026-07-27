"""Live, conservative vendor identity discovery for Sentinel Web-Risk.

Search results are treated only as identity leads. A page is never called an
official company website merely because its title contains words such as
"official", "company", "home", or "about".
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
MAX_REJECTED_RESULTS = 24

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
    "pitchbook.com",
    "ibphub.com",
    "thecompanycheck.com",
    "tracxn.com",
    "owler.com",
    "companieshouse.gov.uk",
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

IDENTITY_REGISTRY_DOMAINS = {
    "companieshouse.gov.uk",
    "find-and-update.company-information.service.gov.uk",
}

IDENTITY_REGISTRY_DOMAIN_MARKERS = (
    "company-register",
    "companies-register",
    "business-register",
    "corporate-register",
    "corporations",
    "companyregistry",
    "businessregistry",
    "registrar",
    "registry",
)

IDENTITY_REGISTRY_PATH_MARKERS = (
    "/company/",
    "/companies/",
    "/entity/",
    "/entities/",
    "/corporation/",
    "/corporations/",
    "/business/",
    "/businesses/",
    "/company-search",
    "/business-search",
    "/archives/edgar/data/",
    "/edgar/browse/",
)

IDENTITY_REGISTRY_TEXT_MARKERS = (
    "company registration",
    "business registration",
    "corporate registry",
    "company registry",
    "registered entity",
    "registration number",
    "company number",
    "corporation number",
    "entity number",
    "legal name",
    "registered office",
    "incorporation date",
    "company status",
    "cik",
)

GOVERNMENT_CONTEXT_PATH_MARKERS = (
    "/recall",
    "/recalls/",
    "/enforcement/",
    "/press-release",
    "/press-releases/",
    "/warning",
    "/warnings/",
    "/advisory",
    "/advisories/",
    "/complaint",
    "/complaints/",
    "/court/",
    "/courts/",
    "/case/",
    "/cases/",
    "/investigation",
    "/investigations/",
    "/consumer-alert",
    "/safety-alert",
)

GOVERNMENT_CONTEXT_TEXT_MARKERS = (
    "product recall",
    "recall notice",
    "safety warning",
    "consumer warning",
    "consumer alert",
    "enforcement action",
    "civil penalty",
    "criminal case",
    "court opinion",
    "public advisory",
    "press release",
    "hazard",
    "investigation",
)

INFORMATIONAL_HOST_MARKERS = (
    "chamber",
    "handelskammer",
    "law",
    "legal",
    "accounting",
    "cpa",
    "consulting",
    "consultancy",
)

REJECT_PATH_PATTERNS = (
    r"\.pdf(?:$|[?#])",
    r"/blog(?:/|$)",
    r"/blogs(?:/|$)",
    r"/category(?:/|$)",
    r"/categories(?:/|$)",
    r"/news(?:/|$)",
    r"/article(?:/|$)",
    r"/articles(?:/|$)",
    r"/guide(?:/|$)",
    r"/guides(?:/|$)",
    r"/resources?(?:/|$)",
    r"/downloads?(?:/|$)",
    r"/page/\d+(?:/|$)",
)

COMPANY_PAGE_PATH_PATTERNS = (
    r"/about(?:[-_/]|$)",
    r"/about-us(?:/|$)",
    r"/company(?:[-_/]|$)",
    r"/corporate(?:[-_/]|$)",
    r"/contact(?:[-_/]|$)",
    r"/who-we-are(?:/|$)",
    r"/profile(?:[-_/]|$)",
)

GENERIC_DOMAIN_TOKENS = {
    "www",
    "com",
    "co",
    "net",
    "org",
    "info",
    "biz",
    "group",
    "company",
    "official",
    "online",
    "store",
}

LEGAL_NAME_TOKENS = {
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
    "pte",
    "gmbh",
    "group",
    "holdings",
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
    accepted_results: tuple[dict[str, str], ...] = ()
    directory_leads: tuple[dict[str, str], ...] = ()
    rejected_results: tuple[dict[str, str], ...] = ()


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


def _domain_tokens(domain: str) -> set[str]:
    labels = domain.lower().split(".")
    meaningful_labels = labels[:-1] if len(labels) > 1 else labels
    tokens: set[str] = set()

    for label in meaningful_labels:
        tokens.update(
            token
            for token in re.split(
                r"[^a-z0-9]+",
                label,
            )
            if (
                len(token) >= 2
                and token not in GENERIC_DOMAIN_TOKENS
            )
        )

    return tokens


def _company_tokens(company_name: str) -> set[str]:
    return {
        token
        for token in _normalize_text(
            company_name
        ).split()
        if (
            len(token) >= 2
            and token not in LEGAL_NAME_TOKENS
        )
    }


def _domain_company_similarity(
    company_name: str,
    domain: str,
) -> float:
    company_tokens = _company_tokens(
        company_name
    )
    domain_tokens = _domain_tokens(
        domain
    )

    if not company_tokens or not domain_tokens:
        return 0.0

    company_compact = "".join(
        sorted(company_tokens)
    )
    domain_compact = "".join(
        sorted(domain_tokens)
    )

    if (
        company_compact
        and company_compact in domain_compact
    ):
        return 1.0

    overlap = len(
        company_tokens & domain_tokens
    )

    return overlap / len(
        company_tokens
    )



DIRECTORY_NON_PROFILE_PATH_MARKERS = (
    "/posts/",
    "/activity/",
    "/pulse/",
    "/feed/update/",
    "/articles/",
    "/article/",
    "/blog/",
    "/news/",
)

DIRECTORY_PROFILE_PATH_PREFIXES = {
    "linkedin.com": ("/company/",),
    "crunchbase.com": ("/organization/",),
    "zoominfo.com": ("/c/",),
    "pitchbook.com": ("/profiles/company/",),
    "opencorporates.com": ("/companies/",),
    "dnb.com": ("/business-directory/company-profiles.",),
    "thecompanycheck.com": ("/company/",),
    "tracxn.com": ("/d/companies/",),
    "owler.com": ("/company/",),
    "ibphub.com": ("/company/",),
}


def _title_supports_requested_name(
    requested_name: str,
    title: str,
) -> bool:
    """Require the title itself to support the requested entity name."""
    requested_tokens = _company_tokens(requested_name)
    title_tokens = set(_normalize_text(title).split())

    if not requested_tokens or not title_tokens:
        return False

    return requested_tokens.issubset(title_tokens)


def _directory_profile_allowed(url: str) -> bool:
    """Allow only actual company-profile paths, never posts or articles."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()

    if any(marker in path for marker in DIRECTORY_NON_PROFILE_PATH_MARKERS):
        return False

    for known_domain, prefixes in DIRECTORY_PROFILE_PATH_PREFIXES.items():
        if domain == known_domain or domain.endswith("." + known_domain):
            return any(path.startswith(prefix) for prefix in prefixes)

    return False


def _supported_legal_name(
    requested_name: str,
    title: str,
) -> str | None:
    """Extract a name only when the source title explicitly supports it."""
    cleaned_title = _clean(title)

    if not cleaned_title:
        return None

    requested_tokens = _company_tokens(requested_name)
    candidates = [cleaned_title]

    for separator in TITLE_SEPARATORS:
        if separator in cleaned_title:
            candidates.extend(
                part.strip()
                for part in cleaned_title.split(separator)
                if part.strip()
            )

    for candidate in candidates:
        candidate_tokens = set(_normalize_text(candidate).split())

        if (
            requested_tokens
            and requested_tokens.issubset(candidate_tokens)
            and 2 <= len(candidate) <= 120
        ):
            return candidate

    return None


def _canonical_official_name(
    requested_name: str,
    title: str,
) -> str | None:
    """Use the user-requested company name, never a page/document title.

    A matching user-supplied domain authenticates ownership of the page, while
    the title only needs to support that the page is about the requested
    company. It does not prove that the whole page title is a legal name.
    """
    cleaned_requested = _clean(
        requested_name
    )

    if (
        not cleaned_requested
        or not _title_supports_requested_name(
            cleaned_requested,
            title,
        )
    ):
        return None

    return cleaned_requested


def _is_rejected_page_type(
    url: str,
) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.lower()

    for pattern in REJECT_PATH_PATTERNS:
        if re.search(pattern, path):
            if ".pdf" in pattern:
                return "informational PDF or downloadable document"
            if "category" in pattern or "page" in pattern:
                return "archive or category page"
            if "blog" in pattern or "article" in pattern or "news" in pattern:
                return "article, blog, or news page"

            return "informational guide or resource page"

    return None


def _looks_like_company_page(
    url: str,
) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")

    if not path:
        return True

    return any(
        re.search(pattern, path + "/")
        for pattern in COMPANY_PAGE_PATH_PATTERNS
    )


def _is_government_or_registry_domain(domain: str) -> bool:
    return (
        domain.endswith(".gov")
        or ".gov." in domain
        or domain.endswith(".europa.eu")
        or domain in IDENTITY_REGISTRY_DOMAINS
        or any(
            marker in domain
            for marker in IDENTITY_REGISTRY_DOMAIN_MARKERS
        )
    )


def _classify_government_source(
    url: str,
    combined_text: str,
) -> str | None:
    """Separate corporate identity records from government context pages."""
    domain = _domain(url)

    if not _is_government_or_registry_domain(domain):
        return None

    path = urlparse(url).path.lower()
    normalized_text = combined_text.lower()

    if (
        any(marker in path for marker in GOVERNMENT_CONTEXT_PATH_MARKERS)
        or any(
            marker in normalized_text
            for marker in GOVERNMENT_CONTEXT_TEXT_MARKERS
        )
    ):
        return "AUTHORITATIVE_CONTEXT"

    identity_domain = (
        domain in IDENTITY_REGISTRY_DOMAINS
        or any(
            marker in domain
            for marker in IDENTITY_REGISTRY_DOMAIN_MARKERS
        )
    )
    identity_path = any(
        marker in path
        for marker in IDENTITY_REGISTRY_PATH_MARKERS
    )
    identity_text = any(
        marker in normalized_text
        for marker in IDENTITY_REGISTRY_TEXT_MARKERS
    )

    if identity_domain and (identity_path or identity_text):
        return "AUTHORITATIVE_IDENTITY"

    if domain == "sec.gov" or domain.endswith(".sec.gov"):
        if identity_path or identity_text:
            return "AUTHORITATIVE_IDENTITY"

    return "AUTHORITATIVE_CONTEXT"


def _acceptance_reason(source_quality: str) -> str:
    reasons = {
        "OFFICIAL_WEBSITE": "user-provided domain matches the result",
        "POSSIBLE_COMPANY_WEBSITE": (
            "company name aligns with a plausible company-owned domain"
        ),
        "AUTHORITATIVE_IDENTITY": (
            "government or corporate registry identity record"
        ),
        "REPUTABLE_BUSINESS_DIRECTORY": (
            "reputable business-directory identity lead"
        ),
    }

    return reasons.get(
        source_quality,
        "accepted by conservative identity-source controls",
    )


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
        f" site:{website_domain}"
        if website_domain
        else ""
    )

    return (
        " ".join(
            part
            for part in (
                quoted_name,
                context,
                '"official website" headquarters contact',
                website_context,
            )
            if part
        ),
        " ".join(
            part
            for part in (
                quoted_name,
                context,
                "company registry registration legal name industry",
            )
            if part
        ),
        " ".join(
            part
            for part in (
                quoted_name,
                context,
                '"official website" company profile country industry',
            )
            if part
        ),
    )


def classify_identity_source(
    url: str,
    *,
    requested_name: str,
    requested_website_domain: str | None,
    combined_text: str,
) -> str:
    """
    Classify a source conservatively.

    OFFICIAL_WEBSITE is reserved for a user-provided matching domain. Search
    results can only establish POSSIBLE_COMPANY_WEBSITE until corroborated.
    """
    domain = _domain(url)

    if requested_website_domain and _registered_domain_matches(
        domain,
        requested_website_domain,
    ):
        return "OFFICIAL_WEBSITE"

    government_quality = _classify_government_source(
        url,
        combined_text,
    )

    if government_quality:
        return government_quality

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
        if not _directory_profile_allowed(url):
            return "SOCIAL"
        return "REPUTABLE_BUSINESS_DIRECTORY"

    if any(
        domain == item
        or domain.endswith("." + item)
        for item in REPUTABLE_NEWS_DOMAINS
    ):
        return "REPUTABLE_NEWS"

    if any(
        marker in domain
        for marker in INFORMATIONAL_HOST_MARKERS
    ):
        return "GENERAL_WEB"

    page_rejection = _is_rejected_page_type(
        url
    )

    if page_rejection:
        return "GENERAL_WEB"

    similarity = _domain_company_similarity(
        requested_name,
        domain,
    )

    if (
        similarity >= 0.50
        and _looks_like_company_page(
            url
        )
    ):
        return "POSSIBLE_COMPANY_WEBSITE"

    return "GENERAL_WEB"


def _result_is_relevant(
    requested_name: str,
    title: str,
    snippet: str,
    url: str,
    requested_website_domain: str | None,
) -> bool:
    del snippet

    if requested_website_domain and _registered_domain_matches(
        _domain(url),
        requested_website_domain,
    ):
        return True

    return _title_supports_requested_name(
        requested_name,
        title,
    )


def _extract_legal_name(
    requested_name: str,
    title: str,
) -> str | None:
    return _supported_legal_name(
        requested_name,
        title,
    )


def _country_from_result(
    url: str,
    combined_text: str,
    requested_country: str | None,
) -> str | None:
    normalized_text = combined_text.lower()
    requested = _clean(
        requested_country
    )

    if requested:
        if requested.lower() in normalized_text:
            return requested

        # Do not replace user-provided context with a country merely mentioned
        # by an article, report, regional page, or downloadable document.
        return None

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

    if declared:
        if declared.lower() in combined_text.lower():
            return declared

        # Do not overwrite supplied context with an industry inferred from
        # incidental page content.
        return None

    profile, confidence = infer_industry(
        combined_text
    )

    if (
        profile.key != "general"
        and confidence >= 0.70
    ):
        return profile.display_name

    return None


def _rejection_reason(
    request: VendorResolutionRequestLike,
    result: dict[str, str],
) -> str | None:
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
        return "invalid or missing HTTP URL"

    requested_domain = _request_website_domain(
        request.website
    )

    if not _result_is_relevant(
        request.vendor_name,
        title,
        snippet,
        url,
        requested_domain,
    ):
        return "target company name is not directly present in the result"

    page_reason = _is_rejected_page_type(
        url
    )

    if page_reason and not (
        requested_domain
        and _registered_domain_matches(
            _domain(url),
            requested_domain,
        )
    ):
        return page_reason

    quality = classify_identity_source(
        url,
        requested_name=request.vendor_name,
        requested_website_domain=requested_domain,
        combined_text=f"{title} {snippet}",
    )

    if (
        quality != "OFFICIAL_WEBSITE"
        and not _title_supports_requested_name(
            request.vendor_name,
            title,
        )
    ):
        return (
            "source title does not establish the requested company identity"
        )

    if quality == "REPUTABLE_BUSINESS_DIRECTORY":
        if not _directory_profile_allowed(url):
            return (
                "directory or social page is not an actual company profile"
            )

        if _supported_legal_name(
            request.vendor_name,
            title,
        ) is None:
            return (
                "directory profile title does not match the requested company"
            )

    if quality == "AUTHORITATIVE_CONTEXT":
        return (
            "authoritative government or regulator context, "
            "not a corporate identity record"
        )

    if quality in {
        "SOCIAL",
        "REPUTABLE_NEWS",
    }:
        return (
            "source may provide context but does not establish "
            "the company's official identity"
        )

    if quality == "GENERAL_WEB":
        return (
            "company ownership of the domain or page is not established"
        )

    return None


def result_to_candidate_evidence(
    request: VendorResolutionRequestLike,
    result: dict[str, str],
) -> CandidateEvidence | None:
    """Convert one identity result only when it passes authenticity controls."""
    rejection = _rejection_reason(
        request,
        result,
    )

    if rejection:
        return None

    title = _clean(
        result.get("title")
    )
    snippet = _clean(
        result.get("snippet")
    )
    url = _clean(
        result.get("url")
    )
    requested_domain = _request_website_domain(
        request.website
    )
    combined_text = f"{title} {snippet}".strip()
    source_quality = classify_identity_source(
        url,
        requested_name=request.vendor_name,
        requested_website_domain=requested_domain,
        combined_text=combined_text,
    )
    legal_name = (
        _canonical_official_name(
            request.vendor_name,
            title,
        )
        if source_quality == "OFFICIAL_WEBSITE"
        else _extract_legal_name(
            request.vendor_name,
            title,
        )
    )

    if (
        legal_name is None
        or source_quality == "REPUTABLE_BUSINESS_DIRECTORY"
    ):
        return None

    if source_quality == "OFFICIAL_WEBSITE":
        candidate_website = (
            _clean(request.website)
            or url
        )
    elif source_quality == "POSSIBLE_COMPANY_WEBSITE":
        candidate_website = url
    else:
        candidate_website = None

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
        accepted: list[dict[str, str]] = []
        directory_leads: list[dict[str, str]] = []
        rejected: list[dict[str, str]] = []

        for result in unique_results:
            rejection = _rejection_reason(
                request,
                result,
            )

            if rejection:
                if len(rejected) < MAX_REJECTED_RESULTS:
                    rejected.append(
                        {
                            "url": _clean(
                                result.get("url")
                            ),
                            "title": _clean(
                                result.get("title")
                            ),
                            "reason": rejection,
                        }
                    )
                continue

            title = _clean(
                result.get("title")
            )
            url = _clean(
                result.get("url")
            )
            snippet = _clean(
                result.get("snippet")
            )
            requested_domain = _request_website_domain(
                request.website
            )
            source_quality = classify_identity_source(
                url,
                requested_name=request.vendor_name,
                requested_website_domain=requested_domain,
                combined_text=f"{title} {snippet}",
            )

            if source_quality == "REPUTABLE_BUSINESS_DIRECTORY":
                legal_name = (
                    _clean(request.vendor_name)
                    if _title_supports_requested_name(
                        request.vendor_name,
                        title,
                    )
                    else None
                )

                if legal_name is not None:
                    directory_leads.append(
                        {
                            "url": url,
                            "title": title,
                            "source_quality": "DIRECTORY_LEAD",
                            "proposed_legal_name": legal_name,
                            "lead_reason": (
                                "matching company-directory profile; "
                                "not used for identity scoring"
                            ),
                        }
                    )
                continue

            record = result_to_candidate_evidence(
                request,
                result,
            )

            if record is not None:
                records.append(
                    record
                )
                accepted.append(
                    {
                        "url": record.source_url,
                        "title": record.source_title,
                        "source_quality": record.source_quality,
                        "proposed_legal_name": record.legal_name,
                        "acceptance_reason": _acceptance_reason(
                            record.source_quality
                        ),
                    }
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
            accepted_results=tuple(
                accepted
            ),
            directory_leads=tuple(
                directory_leads
            ),
            rejected_results=tuple(
                rejected
            ),
        )


_default_collector = LiveVendorIdentityCollector()


async def collect_live_vendor_identity_evidence(
    request: VendorResolutionRequestLike,
) -> IdentityEvidenceBatch:
    """Collect live identity evidence using configured default clients."""
    return await _default_collector.collect(
        request
    )
