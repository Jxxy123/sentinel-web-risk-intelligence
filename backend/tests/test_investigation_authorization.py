"""Tests for the confirmed-identity investigation authorization boundary."""

import pytest

from core.investigation_authorization import (
    InvestigationAuthorizationError,
    clear_investigation_authorizations_for_testing,
    consume_investigation_authorization,
    issue_investigation_authorization,
)


def _confirmed_payload() -> dict:
    return {
        "resolution_status": "CONFIRMED",
        "requested_name": "Microsoft",
        "selected_candidate": {
            "legal_name": "Microsoft",
            "website": "https://www.microsoft.com",
            "website_domain": "microsoft.com",
            "country": "United States",
            "city": None,
            "industry": "Technology",
            "identity_confidence": 0.99,
            "confidence_label": "HIGH",
            "source_quality_labels": ["OFFICIAL_WEBSITE"],
            "evidence_urls": ["https://www.microsoft.com"],
        },
    }


def setup_function() -> None:
    clear_investigation_authorizations_for_testing()


def test_confirmed_identity_issues_and_consumes_single_use_authorization() -> None:
    authorization = issue_investigation_authorization(_confirmed_payload())

    assert authorization["authorization_id"]
    assert authorization["single_use"] is True

    identity = consume_investigation_authorization(
        authorization["authorization_id"],
        requested_vendor_name="Microsoft",
    )

    assert identity["status"] == "CONFIRMED"
    assert identity["canonical_name"] == "Microsoft"
    assert identity["website_domain"] == "microsoft.com"
    assert "authorization_id" not in identity

    with pytest.raises(InvestigationAuthorizationError) as replay:
        consume_investigation_authorization(
            authorization["authorization_id"]
        )

    assert replay.value.status_code == 401


def test_non_confirmed_identity_cannot_issue_authorization() -> None:
    payload = _confirmed_payload()
    payload["resolution_status"] = "MORE_INFORMATION_REQUIRED"
    payload["selected_candidate"] = None

    with pytest.raises(InvestigationAuthorizationError) as error:
        issue_investigation_authorization(payload)

    assert error.value.status_code == 409


def test_weak_or_unauthenticated_candidate_cannot_issue_authorization() -> None:
    payload = _confirmed_payload()
    payload["selected_candidate"]["identity_confidence"] = 0.79
    payload["selected_candidate"]["source_quality_labels"] = ["DIRECTORY_LEAD"]

    with pytest.raises(InvestigationAuthorizationError):
        issue_investigation_authorization(payload)


def test_vendor_name_mismatch_does_not_consume_authorization() -> None:
    authorization = issue_investigation_authorization(_confirmed_payload())

    with pytest.raises(InvestigationAuthorizationError) as mismatch:
        consume_investigation_authorization(
            authorization["authorization_id"],
            requested_vendor_name="Different Company",
        )

    assert mismatch.value.status_code == 409

    identity = consume_investigation_authorization(
        authorization["authorization_id"],
        requested_vendor_name="Microsoft",
    )
    assert identity["canonical_name"] == "Microsoft"
