"""API boundary tests: no investigation job without confirmed identity."""

import json

import pytest
from fastapi import BackgroundTasks, HTTPException

import main
from core.investigation_authorization import (
    clear_investigation_authorizations_for_testing,
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
    main.active_jobs.clear()


@pytest.mark.asyncio
async def test_invalid_authorization_cannot_create_job() -> None:
    request = main.VendorInvestigationRequest(
        identity_authorization_id="invalid-token",
        vendor_name="Microsoft",
        language="EN",
    )

    with pytest.raises(HTTPException) as error:
        await main.start_investigation(
            request,
            BackgroundTasks(),
        )

    assert error.value.status_code == 401
    assert main.active_jobs == {}


@pytest.mark.asyncio
async def test_blank_vendor_name_is_rejected_before_authorization() -> None:
    request = main.VendorInvestigationRequest(
        vendor_name="   ",
        language="EN",
    )

    with pytest.raises(HTTPException) as error:
        await main.start_investigation(
            request,
            BackgroundTasks(),
        )

    assert error.value.status_code == 400
    assert error.value.detail == "vendor_name is required"
    assert main.active_jobs == {}


@pytest.mark.asyncio
async def test_missing_authorization_cannot_create_job() -> None:
    request = main.VendorInvestigationRequest(
        vendor_name="Microsoft",
        language="EN",
    )

    with pytest.raises(HTTPException) as error:
        await main.start_investigation(
            request,
            BackgroundTasks(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == "identity_authorization_id is required."
    assert main.active_jobs == {}

@pytest.mark.asyncio
async def test_confirmed_authorization_queues_canonical_identity_without_token() -> None:
    authorization = issue_investigation_authorization(_confirmed_payload())
    background = BackgroundTasks()
    request = main.VendorInvestigationRequest(
        identity_authorization_id=authorization["authorization_id"],
        vendor_name="Microsoft",
        job_id="confirmed-job",
        language="EN",
    )

    response = await main.start_investigation(
        request,
        background,
    )

    assert response == {
        "job_id": "confirmed-job",
        "status": "queued",
        "vendor_name": "Microsoft",
    }
    assert main.active_jobs["confirmed-job"]["identity"]["status"] == "CONFIRMED"
    assert main.active_jobs["confirmed-job"]["identity"]["website_domain"] == "microsoft.com"
    assert "authorization_id" not in json.dumps(main.active_jobs["confirmed-job"])
    assert len(background.tasks) == 1


@pytest.mark.asyncio
async def test_authorization_replay_cannot_create_second_job() -> None:
    authorization = issue_investigation_authorization(_confirmed_payload())

    first = main.VendorInvestigationRequest(
        identity_authorization_id=authorization["authorization_id"],
        vendor_name="Microsoft",
        job_id="first-job",
        language="EN",
    )
    await main.start_investigation(first, BackgroundTasks())

    second = main.VendorInvestigationRequest(
        identity_authorization_id=authorization["authorization_id"],
        vendor_name="Microsoft",
        job_id="second-job",
        language="EN",
    )

    with pytest.raises(HTTPException) as error:
        await main.start_investigation(second, BackgroundTasks())

    assert error.value.status_code == 401
    assert "second-job" not in main.active_jobs


@pytest.mark.asyncio
async def test_vendor_mismatch_is_rejected_before_job_creation() -> None:
    authorization = issue_investigation_authorization(_confirmed_payload())
    request = main.VendorInvestigationRequest(
        identity_authorization_id=authorization["authorization_id"],
        vendor_name="Different Company",
        job_id="mismatch-job",
        language="EN",
    )

    with pytest.raises(HTTPException) as error:
        await main.start_investigation(request, BackgroundTasks())

    assert error.value.status_code == 409
    assert "mismatch-job" not in main.active_jobs
