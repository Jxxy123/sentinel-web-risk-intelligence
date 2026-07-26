"""Offline tests for safe vendor-candidate resolution."""

from core.vendor_resolution import (
    CandidateEvidence,
    resolve_vendor_candidates,
)


def _evidence(
    *,
    legal_name: str,
    source_url: str,
    source_quality: str,
    website: str | None = None,
    country: str | None = None,
    city: str | None = None,
    industry: str | None = None,
    registration_number: str | None = None,
    aliases: tuple[str, ...] = (),
) -> CandidateEvidence:
    return CandidateEvidence(
        legal_name=legal_name,
        source_url=source_url,
        source_title="Public identity source",
        source_quality=source_quality,
        website=website,
        country=country,
        city=city,
        industry=industry,
        registration_number=registration_number,
        aliases=aliases,
    )


def test_no_candidates_requests_more_information() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )
    assert result.selected_candidate is None
    assert result.candidates == ()
    assert result.requested_fields == (
        "country",
        "city",
        "website",
        "industry",
    )


def test_one_strong_official_candidate_is_confirmed() -> None:
    result = resolve_vendor_candidates(
        "Microsoft",
        [
            _evidence(
                legal_name=(
                    "Microsoft Corporation"
                ),
                aliases=("Microsoft",),
                source_url=(
                    "https://www.microsoft.com/"
                ),
                source_quality=(
                    "OFFICIAL_WEBSITE"
                ),
                website=(
                    "https://www.microsoft.com"
                ),
                country="United States",
                industry="Technology",
            ),
            _evidence(
                legal_name=(
                    "Microsoft Corporation"
                ),
                aliases=("Microsoft",),
                source_url=(
                    "https://www.sec.gov/example"
                ),
                source_quality="AUTHORITATIVE",
                website=(
                    "https://www.microsoft.com"
                ),
                country="United States",
                industry="Technology",
            ),
        ],
    )

    assert result.resolution_status == "CONFIRMED"
    assert result.selected_candidate is not None
    assert (
        result.selected_candidate.website_domain
        == "microsoft.com"
    )
    assert (
        result.selected_candidate.confidence_label
        == "HIGH"
    )


def test_same_name_in_two_countries_requires_selection() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _evidence(
                legal_name="ABC Trading Ltd.",
                source_url=(
                    "https://abctradingbd.example"
                ),
                source_quality=(
                    "OFFICIAL_WEBSITE"
                ),
                website=(
                    "https://abctradingbd.example"
                ),
                country="Bangladesh",
                city="Chattogram",
                industry="Logistics",
            ),
            _evidence(
                legal_name=(
                    "ABC Trading Pte. Ltd."
                ),
                source_url=(
                    "https://abctrading.example.sg"
                ),
                source_quality=(
                    "OFFICIAL_WEBSITE"
                ),
                website=(
                    "https://abctrading.example.sg"
                ),
                country="Singapore",
                city="Singapore",
                industry="Wholesale",
            ),
        ],
    )

    assert (
        result.resolution_status
        == "SELECTION_REQUIRED"
    )
    assert len(result.candidates) == 2
    assert {
        candidate.country
        for candidate in result.candidates
    } == {
        "Bangladesh",
        "Singapore",
    }


def test_user_country_context_selects_matching_candidate() -> None:
    result = resolve_vendor_candidates(
        "ABC Trading",
        [
            _evidence(
                legal_name="ABC Trading Ltd.",
                source_url=(
                    "https://abctradingbd.example"
                ),
                source_quality=(
                    "OFFICIAL_WEBSITE"
                ),
                website=(
                    "https://abctradingbd.example"
                ),
                country="Bangladesh",
                city="Chattogram",
                industry="Logistics",
            ),
            _evidence(
                legal_name=(
                    "ABC Trading Pte. Ltd."
                ),
                source_url=(
                    "https://abctrading.example.sg"
                ),
                source_quality=(
                    "GENERAL_WEB"
                ),
                website=(
                    "https://abctrading.example.sg"
                ),
                country="Singapore",
                city="Singapore",
                industry="Wholesale",
            ),
        ],
        country="Bangladesh",
        city="Chattogram",
    )

    assert result.resolution_status == "CONFIRMED"
    assert result.selected_candidate is not None
    assert (
        result.selected_candidate.country
        == "Bangladesh"
    )


def test_duplicate_sources_for_same_domain_are_merged() -> None:
    result = resolve_vendor_candidates(
        "Example Vendor",
        [
            _evidence(
                legal_name="Example Vendor Ltd.",
                source_url=(
                    "https://examplevendor.com/about"
                ),
                source_quality=(
                    "OFFICIAL_WEBSITE"
                ),
                website=(
                    "https://examplevendor.com"
                ),
                country="Malaysia",
            ),
            _evidence(
                legal_name="Example Vendor Ltd.",
                source_url=(
                    "https://registry.example.gov/company"
                ),
                source_quality="AUTHORITATIVE",
                website=(
                    "https://examplevendor.com"
                ),
                country="Malaysia",
                registration_number="MY-12345",
            ),
        ],
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.evidence_source_count == 2
    assert candidate.registration_number == "MY-12345"


def test_one_weak_directory_candidate_is_not_auto_confirmed() -> None:
    result = resolve_vendor_candidates(
        "Small Local Store",
        [
            _evidence(
                legal_name=(
                    "Small Local Store"
                ),
                source_url=(
                    "https://directory.example/store"
                ),
                source_quality=(
                    "GENERAL_WEB"
                ),
                country="Bangladesh",
                industry="Retail",
            )
        ],
    )

    assert (
        result.resolution_status
        == "MORE_INFORMATION_REQUIRED"
    )
    assert result.selected_candidate is None
    assert len(result.candidates) == 1


def test_response_does_not_claim_complete_internet_coverage() -> None:
    result = resolve_vendor_candidates(
        "Unknown Vendor",
        [],
    )

    notice = result.coverage_notice.lower()

    assert "accessible public sources" in notice
    assert "every business" in notice
    assert "all companies" not in notice


def test_result_is_json_serializable() -> None:
    result = resolve_vendor_candidates(
        "Microsoft",
        [
            _evidence(
                legal_name=(
                    "Microsoft Corporation"
                ),
                aliases=("Microsoft",),
                source_url=(
                    "https://www.microsoft.com/"
                ),
                source_quality=(
                    "OFFICIAL_WEBSITE"
                ),
                website=(
                    "https://www.microsoft.com"
                ),
                country="United States",
                industry="Technology",
            ),
            _evidence(
                legal_name=(
                    "Microsoft Corporation"
                ),
                aliases=("Microsoft",),
                source_url=(
                    "https://www.sec.gov/example"
                ),
                source_quality="AUTHORITATIVE",
                website=(
                    "https://www.microsoft.com"
                ),
                country="United States",
                industry="Technology",
            ),
        ],
    )

    payload = result.to_dict()

    assert payload["resolution_status"] == "CONFIRMED"
    assert (
        payload["selected_candidate"][
            "website_domain"
        ]
        == "microsoft.com"
    )
