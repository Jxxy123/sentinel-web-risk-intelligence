"""Offline tests for the generic runtime identity smoke validator."""

from tools.vendor_identity_runtime_smoke_test import (
    RuntimeExpectation,
    build_runtime_request,
    load_runtime_config,
    validate_runtime_response,
)


def _search(
    *,
    accepted=None,
    leads=None,
    rejected=None,
):
    accepted = accepted or []
    leads = leads or []
    rejected = rejected or []

    return {
        "search_performed": True,
        "providers": [
            "Bright Data SERP",
            "Bright Data Remote MCP",
        ],
        "warnings": [],
        "candidate_evidence_records": len(
            accepted
        ),
        "accepted_result_count": len(
            accepted
        ),
        "accepted_results": accepted,
        "directory_lead_count": len(leads),
        "directory_leads": leads,
        "rejected_result_count": len(
            rejected
        ),
        "rejected_results": rejected,
        "queries_executed": [
            "query one",
            "query two",
            "query three",
        ],
        "started_at": (
            "2026-07-27T00:00:00+00:00"
        ),
        "completed_at": (
            "2026-07-27T00:00:01+00:00"
        ),
        "assessment_type": (
            "pre_investigation_identity_resolution"
        ),
        "llm_used": False,
        "risk_scoring_started": False,
        "database_writes": 0,
    }


def _official_result(
    domain="example.com",
):
    return {
        "url": f"https://{domain}/about",
        "title": "Example Corporation",
        "source_quality": (
            "OFFICIAL_WEBSITE"
        ),
        "proposed_legal_name": (
            "Example Corporation"
        ),
        "acceptance_reason": (
            "user-provided domain matches "
            "the result"
        ),
    }


def _candidate(
    *,
    domain="example.com",
    confidence=0.96,
):
    return {
        "candidate_id": (
            "example-corporation"
        ),
        "legal_name": (
            "Example Corporation"
        ),
        "aliases": ["Example"],
        "website": (
            f"https://{domain}"
        ),
        "website_domain": domain,
        "country": "Test Country",
        "city": None,
        "industry": "Technology",
        "registration_number": None,
        "parent_company": None,
        "public_private_status": None,
        "identity_confidence": confidence,
        "confidence_label": "HIGH",
        "evidence_source_count": 1,
        "source_quality_labels": [
            "OFFICIAL_WEBSITE"
        ],
        "evidence_urls": [
            f"https://{domain}/about"
        ],
        "match_reasons": [
            (
                "Website matches "
                "user-provided domain"
            )
        ],
    }


def test_dynamic_confirmed_official_domain_passes():
    accepted = [
        _official_result()
    ]
    candidate = _candidate()

    payload = {
        "resolution_status": "CONFIRMED",
        "requested_name": "Example",
        "selected_candidate": candidate,
        "candidates": [candidate],
        "requested_fields": [],
        "message": "Confirmed.",
        "coverage_notice": "Public sources.",
        "identity_search": _search(
            accepted=accepted
        ),
    }
    expectation = RuntimeExpectation(
        expected_status="CONFIRMED",
        minimum_confidence=0.90,
        require_official_website=True,
        require_zero_authenticated_evidence=False,
    )

    assert validate_runtime_response(
        payload,
        {
            "vendor_name": "Example",
            "website": (
                "https://example.com"
            ),
        },
        expectation,
    ) == []


def test_wrong_official_domain_fails():
    accepted = [
        _official_result(
            "different.example"
        )
    ]
    candidate = _candidate(
        domain="different.example"
    )

    payload = {
        "resolution_status": "CONFIRMED",
        "selected_candidate": candidate,
        "candidates": [candidate],
        "identity_search": _search(
            accepted=accepted
        ),
    }
    expectation = RuntimeExpectation(
        expected_status="CONFIRMED",
        minimum_confidence=0.90,
        require_official_website=True,
        require_zero_authenticated_evidence=False,
    )

    errors = validate_runtime_response(
        payload,
        {
            "vendor_name": "Example",
            "website": (
                "https://example.com"
            ),
        },
        expectation,
    )

    assert any(
        "does not match" in error
        or "different domain" in error
        for error in errors
    )


def test_ambiguous_zero_evidence_passes():
    payload = {
        "resolution_status": (
            "MORE_INFORMATION_REQUIRED"
        ),
        "selected_candidate": None,
        "candidates": [],
        "identity_search": _search(),
    }
    expectation = RuntimeExpectation(
        expected_status=(
            "MORE_INFORMATION_REQUIRED"
        ),
        minimum_confidence=0.90,
        require_official_website=False,
        require_zero_authenticated_evidence=True,
    )

    assert validate_runtime_response(
        payload,
        {
            "vendor_name": (
                "Ambiguous Trading"
            )
        },
        expectation,
    ) == []


def test_directory_result_cannot_be_accepted():
    directory_result = {
        "url": (
            "https://directory.example/"
            "company/example"
        ),
        "title": "Example",
        "source_quality": (
            "REPUTABLE_BUSINESS_DIRECTORY"
        ),
        "proposed_legal_name": "Example",
        "acceptance_reason": (
            "directory result"
        ),
    }
    payload = {
        "resolution_status": (
            "MORE_INFORMATION_REQUIRED"
        ),
        "selected_candidate": None,
        "candidates": [],
        "identity_search": _search(
            accepted=[
                directory_result
            ]
        ),
    }
    expectation = RuntimeExpectation(
        expected_status="ANY_SAFE",
        minimum_confidence=0.90,
        require_official_website=False,
        require_zero_authenticated_evidence=False,
    )

    errors = validate_runtime_response(
        payload,
        {"vendor_name": "Example"},
        expectation,
    )

    assert any(
        "context or directory" in error
        for error in errors
    )


def test_valid_selection_required_passes():
    first = _candidate(
        domain="one.example",
        confidence=0.72,
    )
    first[
        "evidence_source_count"
    ] = 2
    first[
        "confidence_label"
    ] = "MEDIUM"

    second = _candidate(
        domain="two.example",
        confidence=0.70,
    )
    second[
        "evidence_source_count"
    ] = 2
    second[
        "confidence_label"
    ] = "MEDIUM"

    payload = {
        "resolution_status": (
            "SELECTION_REQUIRED"
        ),
        "selected_candidate": None,
        "candidates": [first, second],
        "identity_search": _search(),
    }
    expectation = RuntimeExpectation(
        expected_status=(
            "SELECTION_REQUIRED"
        ),
        minimum_confidence=0.90,
        require_official_website=False,
        require_zero_authenticated_evidence=False,
    )

    assert validate_runtime_response(
        payload,
        {"vendor_name": "Example"},
        expectation,
    ) == []


def test_protected_marker_and_risk_field_fail():
    payload = {
        "resolution_status": (
            "MORE_INFORMATION_REQUIRED"
        ),
        "selected_candidate": None,
        "candidates": [],
        "risk_score": 20,
        "identity_search": {
            **_search(),
            "warnings": [
                (
                    "authorization: bearer "
                    "must never appear"
                )
            ],
        },
    }
    expectation = RuntimeExpectation(
        expected_status="ANY_SAFE",
        minimum_confidence=0.90,
        require_official_website=False,
        require_zero_authenticated_evidence=False,
    )

    errors = validate_runtime_response(
        payload,
        {"vendor_name": "Example"},
        expectation,
    )

    assert any(
        "investigation fields" in error
        for error in errors
    )
    assert any(
        "protected marker" in error
        for error in errors
    )



def test_runtime_request_loads_dynamic_json(
    monkeypatch,
    tmp_path,
):
    config_path = (
        tmp_path
        / "runtime_identity.json"
    )
    config_path.write_text(
        """{
  "vendor_name": "Dynamic Example Ltd",
  "website": "https://dynamic.example",
  "country": "Example Country",
  "city": "Example City",
  "industry": "Technology",
  "language": "EN",
  "expected_status": "CONFIRMED",
  "minimum_confidence": 0.91,
  "require_official_website": true,
  "require_zero_authenticated_evidence": false
}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "IDENTITY_RUNTIME_CONFIG_FILE",
        str(config_path),
    )

    request_body, expectation = (
        build_runtime_request()
    )

    assert request_body == {
        "vendor_name": "Dynamic Example Ltd",
        "website": "https://dynamic.example",
        "country": "Example Country",
        "city": "Example City",
        "industry": "Technology",
        "language": "EN",
    }
    assert expectation == RuntimeExpectation(
        expected_status="CONFIRMED",
        minimum_confidence=0.91,
        require_official_website=True,
        require_zero_authenticated_evidence=False,
    )


def test_runtime_config_rejects_unknown_fields(
    tmp_path,
):
    config_path = (
        tmp_path
        / "unsafe_runtime_identity.json"
    )
    config_path.write_text(
        """{
  "vendor_name": "Example",
  "api_key": "must-not-be-accepted"
}
""",
        encoding="utf-8",
    )

    try:
        load_runtime_config(config_path)
    except ValueError as error:
        assert (
            "unsupported fields"
            in str(error)
        )
        assert "api_key" in str(error)
    else:
        raise AssertionError(
            "Unknown runtime fields were accepted."
        )



def test_official_subdomain_is_accepted_for_supplied_root() -> None:
    accepted = [
        _official_result(
            "news.example.com"
        )
    ]
    candidate = _candidate(
        domain="example.com"
    )

    payload = {
        "resolution_status": "CONFIRMED",
        "selected_candidate": candidate,
        "candidates": [candidate],
        "identity_search": _search(
            accepted=accepted
        ),
    }
    expectation = RuntimeExpectation(
        expected_status="CONFIRMED",
        minimum_confidence=0.90,
        require_official_website=True,
        require_zero_authenticated_evidence=False,
    )

    assert validate_runtime_response(
        payload,
        {
            "vendor_name": "Example",
            "website": (
                "https://example.com"
            ),
        },
        expectation,
    ) == []


def test_page_title_cannot_be_confirmed_as_legal_name() -> None:
    accepted = [
        {
            **_official_result(),
            "proposed_legal_name": (
                "Example Trademark and Brand Guidelines"
            ),
        }
    ]
    candidate = {
        **_candidate(),
        "legal_name": (
            "Example Trademark and Brand Guidelines"
        ),
    }

    payload = {
        "resolution_status": "CONFIRMED",
        "selected_candidate": candidate,
        "candidates": [candidate],
        "identity_search": _search(
            accepted=accepted
        ),
    }
    expectation = RuntimeExpectation(
        expected_status="CONFIRMED",
        minimum_confidence=0.90,
        require_official_website=True,
        require_zero_authenticated_evidence=False,
    )

    errors = validate_runtime_response(
        payload,
        {
            "vendor_name": "Example",
            "website": (
                "https://example.com"
            ),
        },
        expectation,
    )

    assert any(
        "page or document title"
        in error
        for error in errors
    )
