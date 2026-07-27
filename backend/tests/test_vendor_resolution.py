"""Offline tests for strict vendor candidate confidence and resolution."""

from core.vendor_resolution import (
    CandidateEvidence,
    resolve_vendor_candidates,
)


def _record(
    *,
    source_url: str,
    source_quality: str,
    website: str | None = None,
    country: str | None = None,
    registration_number: str | None = None,
) -> CandidateEvidence:
    return CandidateEvidence(
        legal_name="ABC Trading",
        source_url=source_url,
        source_title="ABC Trading identity source",
        source_quality=source_quality,
        website=website,
        country=country,
        aliases=("ABC Trading",),
        registration_number=registration_number,
    )


def test_single_possible_website_is_limited_and_requests_context() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url=(
                    "https://abctrading.example/about"
                ),
                source_quality=(
                    "POSSIBLE_COMPANY_WEBSITE"
                ),
                website=(
                    "https://abctrading.example/about"
                ),
            )
        ],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )
    assert len(result.candidates) <= 1

    if result.candidates:
        assert (
            result.candidates[0].identity_confidence
            <= 0.54
        )
        assert (
            result.candidates[0].confidence_label
            == "LIMITED"
        )


def test_single_directory_source_is_not_selectable() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url=(
                    "https://pitchbook.com/company/123"
                ),
                source_quality=(
                    "REPUTABLE_BUSINESS_DIRECTORY"
                ),
            )
        ],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )
    assert result.selected_candidate is None


def test_two_single_source_leads_do_not_force_selection() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url=(
                    "https://abctrading-one.example/about"
                ),
                source_quality=(
                    "POSSIBLE_COMPANY_WEBSITE"
                ),
                website=(
                    "https://abctrading-one.example/about"
                ),
                country="Bangladesh",
            ),
            _record(
                source_url=(
                    "https://abctrading-two.example/about"
                ),
                source_quality=(
                    "POSSIBLE_COMPANY_WEBSITE"
                ),
                website=(
                    "https://abctrading-two.example/about"
                ),
                country="Singapore",
            ),
        ],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )


def test_user_provided_matching_website_can_confirm() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url=(
                    "https://abctrading.example/about"
                ),
                source_quality="OFFICIAL_WEBSITE",
                website=(
                    "https://abctrading.example/about"
                ),
                country="Bangladesh",
            ),
            _record(
                source_url=(
                    "https://registry.example.gov/company/123"
                ),
                source_quality="AUTHORITATIVE_IDENTITY",
                website=(
                    "https://abctrading.example"
                ),
                country="Bangladesh",
                registration_number="BD-123",
            ),
        ],
        website="https://abctrading.example",
        country="Bangladesh",
    )

    assert result.resolution_status == "CONFIRMED"
    assert result.selected_candidate is not None
    assert (
        result.selected_candidate.confidence_label
        == "HIGH"
    )


def test_two_independently_supported_companies_require_selection() -> None:
    records = [
        _record(
            source_url=(
                "https://abc-bd.example/about"
            ),
            source_quality=(
                "POSSIBLE_COMPANY_WEBSITE"
            ),
            website=(
                "https://abc-bd.example/about"
            ),
            country="Bangladesh",
        ),
        _record(
            source_url=(
                "https://registry.bd.gov/company/abc"
            ),
            source_quality="AUTHORITATIVE_IDENTITY",
            website=(
                "https://abc-bd.example"
            ),
            country="Bangladesh",
            registration_number="BD-ABC",
        ),
        _record(
            source_url=(
                "https://abc-sg.example/about"
            ),
            source_quality=(
                "POSSIBLE_COMPANY_WEBSITE"
            ),
            website=(
                "https://abc-sg.example/about"
            ),
            country="Singapore",
        ),
        _record(
            source_url=(
                "https://registry.sg.gov/company/abc"
            ),
            source_quality="AUTHORITATIVE_IDENTITY",
            website=(
                "https://abc-sg.example"
            ),
            country="Singapore",
            registration_number="SG-ABC",
        ),
    ]

    result = resolve_vendor_candidates(
        "ABC Trading",
        records,
    )

    assert (
        result.resolution_status
        == "SELECTION_REQUIRED"
    )
    assert len(result.candidates) == 2
    assert all(
        candidate.evidence_source_count == 2
        for candidate in result.candidates
    )



def test_single_authoritative_result_is_not_auto_confirmed() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url=(
                    "https://registry.example.gov/company/abc"
                ),
                source_quality="AUTHORITATIVE_IDENTITY",
                country="Bangladesh",
                registration_number="BD-ABC",
            )
        ],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )
    assert result.selected_candidate is None


def test_weak_candidates_are_not_shown_as_selection_choices() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url="https://pitchbook.com/company/one",
                source_quality=(
                    "REPUTABLE_BUSINESS_DIRECTORY"
                ),
                country="Bangladesh",
            ),
            _record(
                source_url="https://ibphub.com/company/two",
                source_quality=(
                    "REPUTABLE_BUSINESS_DIRECTORY"
                ),
                country="India",
            ),
        ],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )
    assert result.selected_candidate is None



def test_authoritative_context_never_creates_candidate() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url=(
                    "https://www.cpsc.gov/Recalls/1973/"
                    "abc-trading-recall"
                ),
                source_quality="AUTHORITATIVE_CONTEXT",
                country="United States",
            )
        ],
    )

    assert result.resolution_status == "MORE_INFORMATION_REQUIRED"
    assert result.selected_candidate is None
    assert result.candidates == ()



def test_directory_lead_is_ignored_even_if_passed_to_resolver() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _record(
                source_url="https://www.linkedin.com/company/abc-trading",
                source_quality="DIRECTORY_LEAD",
                country="Bangladesh",
            )
        ],
    )

    assert result.resolution_status == "MORE_INFORMATION_REQUIRED"
    assert result.selected_candidate is None
    assert result.candidates == ()



def test_official_subdomains_group_under_supplied_domain_and_name() -> None:
    records = [
        CandidateEvidence(
            legal_name="Facts About Microsoft - Stories",
            source_url=(
                "https://news.microsoft.com/"
                "facts-about-microsoft/"
            ),
            source_title=(
                "Facts About Microsoft - Stories"
            ),
            source_quality="OFFICIAL_WEBSITE",
            website=(
                "https://news.microsoft.com/"
                "facts-about-microsoft/"
            ),
            country=None,
            industry=None,
            aliases=("Microsoft",),
        ),
        CandidateEvidence(
            legal_name=(
                "Microsoft Trademark and Brand Guidelines"
            ),
            source_url=(
                "https://www.microsoft.com/en-us/legal/"
                "intellectualproperty/trademarks"
            ),
            source_title=(
                "Microsoft Trademark and Brand Guidelines"
            ),
            source_quality="OFFICIAL_WEBSITE",
            website=(
                "https://www.microsoft.com/en-us/legal/"
                "intellectualproperty/trademarks"
            ),
            country=None,
            industry=None,
            aliases=("Microsoft",),
        ),
    ]

    result = resolve_vendor_candidates(
        "Microsoft",
        records,
        website="https://www.microsoft.com",
        country="United States",
        industry="Technology",
    )

    assert result.resolution_status == "CONFIRMED"
    assert result.selected_candidate is not None
    assert (
        result.selected_candidate.legal_name
        == "Microsoft"
    )
    assert (
        result.selected_candidate.website_domain
        == "microsoft.com"
    )
    assert (
        result.selected_candidate.evidence_source_count
        == 2
    )
    assert (
        "Supported by independent public sources"
        not in result.selected_candidate.match_reasons
    )
    assert (
        result.selected_candidate.identity_confidence
        == 0.90
    )
    assert len(result.candidates) == 1
