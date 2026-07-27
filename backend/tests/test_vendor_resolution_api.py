"""Offline API tests for authenticated vendor identity resolution."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.vendor_resolution_api as api_module
from core.live_vendor_identity import IdentityEvidenceBatch
from core.vendor_resolution import CandidateEvidence
from core.vendor_resolution_api import router


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    original_collector = api_module.identity_evidence_collector

    async def no_search_collector(request) -> IdentityEvidenceBatch:
        del request
        return IdentityEvidenceBatch(
            records=(),
            search_performed=False,
            providers=(),
            warnings=("Controlled offline test collector.",),
        )

    api_module.identity_evidence_collector = no_search_collector

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as test_client:
        yield test_client

    api_module.identity_evidence_collector = original_collector


def _record(
    *,
    legal_name: str,
    source_url: str,
    source_quality: str,
    website: str | None = None,
    country: str | None = None,
    city: str | None = None,
    industry: str | None = None,
    aliases: tuple[str, ...] = (),
    registration_number: str | None = None,
) -> CandidateEvidence:
    return CandidateEvidence(
        legal_name=legal_name,
        source_url=source_url,
        source_title="Authenticated identity source",
        source_quality=source_quality,
        website=website,
        country=country,
        city=city,
        industry=industry,
        aliases=aliases,
        registration_number=registration_number,
    )


def test_blank_vendor_name_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "vendor_name is required"


def test_controlled_collector_does_not_claim_live_search(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "ABC Trading"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["resolution_status"] == "MORE_INFORMATION_REQUIRED"
    assert payload["identity_search"]["search_performed"] is False
    assert payload["identity_search"]["providers"] == []
    assert payload["identity_search"]["accepted_result_count"] == 0
    assert payload["identity_search"]["accepted_results"] == []
    assert payload["identity_search"]["rejected_result_count"] == 0
    assert payload["identity_search"]["rejected_results"] == []
    assert payload["identity_search"]["risk_scoring_started"] is False
    assert payload["identity_search"]["llm_used"] is False


def test_independently_supported_matches_require_selection(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(request) -> IdentityEvidenceBatch:
        assert request.vendor_name == "ABC Trading"

        return IdentityEvidenceBatch(
            records=(
                _record(
                    legal_name="ABC Trading Ltd.",
                    aliases=("ABC Trading",),
                    source_url="https://abc-bd.example/about",
                    source_quality="POSSIBLE_COMPANY_WEBSITE",
                    website="https://abc-bd.example",
                    country="Bangladesh",
                    city="Chattogram",
                    industry="Logistics",
                ),
                _record(
                    legal_name="ABC Trading Ltd.",
                    aliases=("ABC Trading",),
                    source_url="https://registry.bd.gov/company/abc",
                    source_quality="AUTHORITATIVE_IDENTITY",
                    website="https://abc-bd.example",
                    country="Bangladesh",
                    city="Chattogram",
                    industry="Logistics",
                    registration_number="BD-ABC",
                ),
                _record(
                    legal_name="ABC Trading Pte. Ltd.",
                    aliases=("ABC Trading",),
                    source_url="https://abc-sg.example/about",
                    source_quality="POSSIBLE_COMPANY_WEBSITE",
                    website="https://abc-sg.example",
                    country="Singapore",
                    city="Singapore",
                    industry="Wholesale",
                ),
                _record(
                    legal_name="ABC Trading Pte. Ltd.",
                    aliases=("ABC Trading",),
                    source_url="https://registry.sg.gov/company/abc",
                    source_quality="AUTHORITATIVE_IDENTITY",
                    website="https://abc-sg.example",
                    country="Singapore",
                    city="Singapore",
                    industry="Wholesale",
                    registration_number="SG-ABC",
                ),
            ),
            search_performed=True,
            providers=("Test Identity Provider",),
            queries_executed=("query one",),
            started_at="2026-07-27T00:00:00+00:00",
            completed_at="2026-07-27T00:00:01+00:00",
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "ABC Trading"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["resolution_status"] == "SELECTION_REQUIRED"
    assert len(payload["candidates"]) == 2
    assert all(
        candidate["evidence_source_count"] == 2
        for candidate in payload["candidates"]
    )
    assert {
        candidate["country"]
        for candidate in payload["candidates"]
    } == {"Bangladesh", "Singapore"}
    assert payload["identity_search"]["queries_executed"] == ["query one"]


def test_user_domain_and_registry_confirm_identity(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(request) -> IdentityEvidenceBatch:
        assert request.language == "EN"
        assert request.website == "https://www.microsoft.com"
        assert request.country == "United States"

        return IdentityEvidenceBatch(
            records=(
                _record(
                    legal_name="Microsoft Corporation",
                    aliases=("Microsoft",),
                    source_url="https://www.microsoft.com/",
                    source_quality="OFFICIAL_WEBSITE",
                    website="https://www.microsoft.com",
                    country="United States",
                    industry="Technology",
                ),
                _record(
                    legal_name="Microsoft Corporation",
                    aliases=("Microsoft",),
                    source_url="https://www.sec.gov/example",
                    source_quality="AUTHORITATIVE_IDENTITY",
                    website="https://www.microsoft.com",
                    country="United States",
                    industry="Technology",
                    registration_number="US-MSFT",
                ),
            ),
            search_performed=True,
            providers=("Official Website", "Government Registry"),
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": " Microsoft ",
            "website": "https://www.microsoft.com",
            "country": "United States",
            "language": "en",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["resolution_status"] == "CONFIRMED"
    assert payload["selected_candidate"]["website_domain"] == "microsoft.com"
    assert payload["selected_candidate"]["confidence_label"] == "HIGH"


def test_single_unconfirmed_website_lead_requests_context(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(request) -> IdentityEvidenceBatch:
        del request
        return IdentityEvidenceBatch(
            records=(
                _record(
                    legal_name="ABC Trading",
                    aliases=("ABC Trading",),
                    source_url="https://abctrading.example/about",
                    source_quality="POSSIBLE_COMPANY_WEBSITE",
                    website="https://abctrading.example",
                ),
            ),
            search_performed=True,
            providers=("Test Identity Provider",),
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "ABC Trading"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["resolution_status"] == "MORE_INFORMATION_REQUIRED"
    assert payload["selected_candidate"] is None

    if payload["candidates"]:
        assert payload["candidates"][0]["confidence_label"] == "LIMITED"


def test_optional_context_is_normalized_and_forwarded(
    client: TestClient,
    monkeypatch,
) -> None:
    captured = {}

    async def collector(request) -> IdentityEvidenceBatch:
        captured["request"] = request
        return IdentityEvidenceBatch(
            records=(),
            search_performed=True,
            providers=("Test Provider",),
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": "  ABC   Trading  ",
            "country": " Bangladesh ",
            "city": " Chattogram ",
            "website": " abctrading.example ",
            "industry": " Logistics ",
            "language": " en ",
        },
    )

    assert response.status_code == 200
    request = captured["request"]

    assert request.vendor_name == "ABC Trading"
    assert request.country == "Bangladesh"
    assert request.city == "Chattogram"
    assert request.website == "abctrading.example"
    assert request.industry == "Logistics"
    assert request.language == "EN"


def test_provider_failure_returns_generic_503(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(request) -> IdentityEvidenceBatch:
        del request
        raise RuntimeError("secret-provider-detail")

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "Example Vendor"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Vendor identity search is temporarily unavailable."
    )
    assert "secret-provider-detail" not in response.text


def test_resolution_endpoint_never_returns_job_or_risk_fields(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "Example Vendor"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert "job_id" not in payload
    assert "risk_score" not in payload
    assert "risk_level" not in payload
    assert "report" not in payload



def test_rejected_identity_results_are_exposed_without_raw_content(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(request) -> IdentityEvidenceBatch:
        del request

        return IdentityEvidenceBatch(
            records=(),
            search_performed=True,
            providers=("Test Identity Provider",),
            rejected_results=(
                {
                    "url": (
                        "https://example.com/download/"
                        "company-guide.pdf"
                    ),
                    "title": "ABC Trading company guide",
                    "reason": (
                        "informational PDF or downloadable document"
                    ),
                },
                {
                    "url": (
                        "https://example.com/blog/"
                        "trading-names"
                    ),
                    "title": "Trading names article",
                    "reason": "article, blog, or news page",
                },
            ),
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "ABC Trading"},
    )

    assert response.status_code == 200
    payload = response.json()
    search = payload["identity_search"]

    assert search["rejected_result_count"] == 2
    assert len(search["rejected_results"]) == 2

    for record in search["rejected_results"]:
        assert set(record) == {
            "url",
            "title",
            "reason",
        }
        assert record["url"].startswith(
            "https://"
        )
        assert record["reason"]
        assert "content" not in record
        assert "snippet" not in record
        assert "body" not in record



def test_accepted_identity_audit_is_safe_and_typed(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(request) -> IdentityEvidenceBatch:
        del request

        return IdentityEvidenceBatch(
            records=(
                _record(
                    legal_name="ABC Trading Ltd.",
                    aliases=("ABC Trading",),
                    source_url=(
                        "https://registry.example.gov/"
                        "company/ABC-123"
                    ),
                    source_quality="AUTHORITATIVE_IDENTITY",
                    country="Bangladesh",
                    registration_number="ABC-123",
                ),
            ),
            search_performed=True,
            providers=("Test Identity Provider",),
            accepted_results=(
                {
                    "url": (
                        "https://registry.example.gov/"
                        "company/ABC-123"
                    ),
                    "title": "ABC Trading company record",
                    "source_quality": "AUTHORITATIVE_IDENTITY",
                    "proposed_legal_name": "ABC Trading Ltd.",
                    "acceptance_reason": (
                        "government or corporate registry identity record"
                    ),
                },
            ),
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={"vendor_name": "ABC Trading"},
    )

    assert response.status_code == 200
    search = response.json()["identity_search"]
    assert search["accepted_result_count"] == 1
    assert len(search["accepted_results"]) == 1
    record = search["accepted_results"][0]
    assert set(record) == {
        "url",
        "title",
        "source_quality",
        "proposed_legal_name",
        "acceptance_reason",
    }
    assert record["source_quality"] == "AUTHORITATIVE_IDENTITY"
    assert "snippet" not in record
    assert "content" not in record
    assert "body" not in record
