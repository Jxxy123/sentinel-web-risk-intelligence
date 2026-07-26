"""Offline API tests for vendor identity resolution."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.vendor_resolution_api as api_module
from core.vendor_resolution import CandidateEvidence
from core.vendor_resolution_api import (
    IdentityEvidenceBatch,
    router,
)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    original_collector = (
        api_module.identity_evidence_collector
    )

    app = FastAPI()
    app.include_router(
        router
    )

    with TestClient(app) as test_client:
        yield test_client

    api_module.identity_evidence_collector = (
        original_collector
    )


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
) -> CandidateEvidence:
    return CandidateEvidence(
        legal_name=legal_name,
        source_url=source_url,
        source_title="Verified identity source",
        source_quality=source_quality,
        website=website,
        country=country,
        city=city,
        industry=industry,
        aliases=aliases,
    )


def test_blank_vendor_name_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "vendor_name is required"
    )


def test_unconfigured_collector_does_not_claim_live_search(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": "ABC Trading",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert (
        payload["resolution_status"]
        == "MORE_INFORMATION_REQUIRED"
    )
    assert (
        payload["identity_search"][
            "search_performed"
        ]
        is False
    )
    assert payload["identity_search"]["providers"] == []
    assert (
        payload["identity_search"][
            "candidate_evidence_records"
        ]
        == 0
    )


def test_multiple_supported_matches_require_selection(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(
        request,
    ) -> IdentityEvidenceBatch:
        assert request.vendor_name == "ABC Trading"

        return IdentityEvidenceBatch(
            records=(
                _record(
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
                _record(
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
            ),
            search_performed=True,
            providers=(
                "Test Identity Provider",
            ),
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": "ABC Trading",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert (
        payload["resolution_status"]
        == "SELECTION_REQUIRED"
    )
    assert len(payload["candidates"]) == 2
    assert (
        payload["identity_search"][
            "search_performed"
        ]
        is True
    )


def test_one_strong_identity_is_confirmed(
    client: TestClient,
    monkeypatch,
) -> None:
    async def collector(
        request,
    ) -> IdentityEvidenceBatch:
        assert request.language == "EN"

        return IdentityEvidenceBatch(
            records=(
                _record(
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
                _record(
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
            ),
            search_performed=True,
            providers=(
                "Official Website",
                "Government Registry",
            ),
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
            "language": "en",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["resolution_status"] == "CONFIRMED"
    assert (
        payload["selected_candidate"][
            "website_domain"
        ]
        == "microsoft.com"
    )
    assert payload["identity_search"]["providers"] == [
        "Official Website",
        "Government Registry",
    ]


def test_optional_context_is_normalized_and_forwarded(
    client: TestClient,
    monkeypatch,
) -> None:
    captured = {}

    async def collector(
        request,
    ) -> IdentityEvidenceBatch:
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
    async def collector(
        request,
    ) -> IdentityEvidenceBatch:
        del request
        raise RuntimeError(
            "secret-provider-detail"
        )

    monkeypatch.setattr(
        api_module,
        "identity_evidence_collector",
        collector,
    )

    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": "Example Vendor",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Vendor identity search is temporarily unavailable."
    )
    assert "secret-provider-detail" not in response.text


def test_resolution_endpoint_never_returns_job_id(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/vendors/resolve",
        json={
            "vendor_name": "Example Vendor",
        },
    )

    assert response.status_code == 200
    assert "job_id" not in response.json()
