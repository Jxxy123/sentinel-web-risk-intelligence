"""Safe API-contract tests that never start a real investigation."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import active_jobs, app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Provide an isolated API client for each test."""
    active_jobs.clear()

    with TestClient(app) as test_client:
        yield test_client

    active_jobs.clear()


def test_health_endpoint_is_operational(
    client: TestClient,
) -> None:
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "operational"
    assert body["service"] == "Sentinel Web-Risk"
    assert body["version"] == "1.0.0"
    assert "timestamp" in body


def test_blank_vendor_name_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/investigate",
        json={
            "vendor_name": "   ",
            "language": "EN",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "vendor_name is required"
    assert active_jobs == {}


def test_missing_vendor_name_is_validation_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/investigate",
        json={
            "language": "EN",
        },
    )

    assert response.status_code == 422
    assert active_jobs == {}


def test_unknown_job_returns_not_found(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/jobs/nonexistent-test-job"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_health_check_does_not_create_jobs(
    client: TestClient,
) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert active_jobs == {}
