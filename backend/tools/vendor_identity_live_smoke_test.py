"""Controlled live smoke test for pre-investigation vendor identity resolution.

Expected external activity:
- two Bright Data SERP searches;
- one Bright Data Remote MCP search;
- zero page scrapes;
- zero CrewAI or LLM calls;
- zero risk-scoring operations;
- zero database writes;
- zero investigation jobs.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.vendor_resolution_api import router


ARTIFACT_PATH = Path(
    "artifacts/vendor_identity_live_smoke.json"
)

ALLOWED_STATUSES = {
    "CONFIRMED",
    "SELECTION_REQUIRED",
    "MORE_INFORMATION_REQUIRED",
}

PROTECTED_MARKERS = (
    "bright_data_api_key",
    "authorization: bearer",
    "proxy_password",
    "proxy_pass",
    "api_token",
    '"token"',
    "crewai",
    "openai_api_key",
)

FORBIDDEN_RESPONSE_FIELDS = {
    "job_id",
    "report",
    "risk_score",
    "risk_level",
    "disruption_probability",
    "raw_intelligence",
}


FORBIDDEN_CANDIDATE_SOURCE_LABELS = {
    "GENERAL_WEB",
    "SOCIAL",
    "REPUTABLE_NEWS",
}

FORBIDDEN_CANDIDATE_PATH_MARKERS = (
    ".pdf",
    "/blog/",
    "/blogs/",
    "/category/",
    "/article/",
    "/articles/",
    "/news/",
    "/guide/",
    "/guides/",
    "/download/",
    "/downloads/",
)


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def _valid_http_url(value: Any) -> bool:
    text = _clean(value)
    parsed = urlparse(text)

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SystemExit(message)


def _validate_candidate(
    candidate: dict[str, Any],
) -> None:
    _require(
        isinstance(candidate, dict),
        "Every vendor candidate must be an object.",
    )
    _require(
        bool(_clean(candidate.get("candidate_id"))),
        "Vendor candidate is missing candidate_id.",
    )
    _require(
        bool(_clean(candidate.get("legal_name"))),
        "Vendor candidate is missing legal_name.",
    )

    confidence = candidate.get(
        "identity_confidence"
    )
    _require(
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= confidence <= 1,
        "Candidate identity_confidence must be between 0 and 1.",
    )

    label = _clean(
        candidate.get("confidence_label")
    )
    _require(
        label in {
            "HIGH",
            "MEDIUM",
            "LIMITED",
        },
        "Candidate confidence_label is invalid.",
    )

    evidence_urls = candidate.get(
        "evidence_urls"
    )
    _require(
        isinstance(evidence_urls, list),
        "Candidate evidence_urls must be a list.",
    )

    for url in evidence_urls:
        _require(
            _valid_http_url(url),
            "Candidate contains an invalid evidence URL.",
        )

    source_labels = candidate.get(
        "source_quality_labels"
    )
    _require(
        isinstance(source_labels, list),
        "Candidate source_quality_labels must be a list.",
    )
    _require(
        not (
            set(source_labels)
            & FORBIDDEN_CANDIDATE_SOURCE_LABELS
        ),
        (
            "Candidate contains a source class that cannot "
            "establish company identity."
        ),
    )

    evidence_count = candidate.get(
        "evidence_source_count"
    )
    _require(
        isinstance(evidence_count, int)
        and evidence_count >= 1,
        "Candidate evidence_source_count must be a positive integer.",
    )

    if evidence_count == 1 and "AUTHORITATIVE" not in source_labels:
        _require(
            confidence <= 0.54
            and label == "LIMITED",
            (
                "Single-source non-authoritative candidate is "
                "overconfident."
            ),
        )

    website = _clean(
        candidate.get("website")
    )

    if website:
        _require(
            _valid_http_url(website),
            "Candidate contains an invalid website URL.",
        )
        normalized_website = website.lower()
        _require(
            not any(
                marker in normalized_website
                for marker in FORBIDDEN_CANDIDATE_PATH_MARKERS
            ),
            (
                "Candidate website points to an article, archive, "
                "guide, download, or PDF."
            ),
        )


def validate_identity_response(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate the endpoint contract without asserting a specific company."""
    _require(
        isinstance(payload, dict),
        "Vendor identity response must be an object.",
    )

    status = _clean(
        payload.get("resolution_status")
    )
    _require(
        status in ALLOWED_STATUSES,
        "Vendor identity response contains an invalid resolution status.",
    )

    requested_name = _clean(
        payload.get("requested_name")
    )
    _require(
        bool(requested_name),
        "Vendor identity response is missing requested_name.",
    )

    for field in FORBIDDEN_RESPONSE_FIELDS:
        _require(
            field not in payload,
            (
                "Identity-only endpoint unexpectedly returned "
                f"investigation field: {field}."
            ),
        )

    candidates = payload.get(
        "candidates"
    )
    _require(
        isinstance(candidates, list),
        "Vendor identity candidates must be a list.",
    )
    _require(
        len(candidates) <= 8,
        "Vendor identity response returned more than eight candidates.",
    )

    candidate_ids: set[str] = set()

    for candidate in candidates:
        _validate_candidate(candidate)
        _require(
            "OFFICIAL_WEBSITE"
            not in candidate.get(
                "source_quality_labels",
                [],
            ),
            (
                "Search-discovered candidate was falsely labelled "
                "OFFICIAL_WEBSITE without a user-provided domain."
            ),
        )
        candidate_id = _clean(
            candidate.get("candidate_id")
        )
        _require(
            candidate_id not in candidate_ids,
            "Vendor identity response contains duplicate candidate IDs.",
        )
        candidate_ids.add(candidate_id)

    selected = payload.get(
        "selected_candidate"
    )

    if status == "CONFIRMED":
        _require(
            isinstance(selected, dict),
            "CONFIRMED response must include selected_candidate.",
        )
        _validate_candidate(selected)
        _require(
            selected.get("confidence_label") == "HIGH",
            "Automatically confirmed candidate must have HIGH confidence.",
        )
    else:
        _require(
            selected is None,
            (
                "An unresolved identity response must not silently "
                "select a candidate."
            ),
        )

    if status == "SELECTION_REQUIRED":
        _require(
            len(candidates) >= 2,
            "SELECTION_REQUIRED must provide at least two candidates.",
        )
        _require(
            all(
                candidate.get(
                    "evidence_source_count",
                    0,
                )
                >= 2
                and candidate.get(
                    "identity_confidence",
                    0,
                )
                >= 0.65
                for candidate in candidates
            ),
            (
                "SELECTION_REQUIRED contains a candidate without "
                "independent identity support."
            ),
        )

    if status == "MORE_INFORMATION_REQUIRED":
        requested_fields = payload.get(
            "requested_fields"
        )
        _require(
            isinstance(requested_fields, list)
            and bool(requested_fields),
            (
                "MORE_INFORMATION_REQUIRED must identify useful "
                "context fields."
            ),
        )

    search = payload.get(
        "identity_search"
    )
    _require(
        isinstance(search, dict),
        "Vendor identity response is missing identity_search metadata.",
    )
    _require(
        search.get("search_performed") is True,
        "Live identity smoke test did not perform a live search.",
    )
    _require(
        search.get("llm_used") is False,
        "Identity resolution must not use an LLM.",
    )
    _require(
        search.get("risk_scoring_started") is False,
        "Identity resolution unexpectedly started risk scoring.",
    )
    _require(
        search.get("database_writes") == 0,
        "Identity resolution unexpectedly reported a database write.",
    )
    _require(
        search.get("assessment_type")
        == "pre_investigation_identity_resolution",
        "Identity search assessment_type is invalid.",
    )

    queries = search.get(
        "queries_executed"
    )
    _require(
        isinstance(queries, list)
        and len(queries) == 3,
        "Identity smoke test must execute exactly three planned queries.",
    )

    providers = search.get(
        "providers"
    )
    _require(
        isinstance(providers, list),
        "Identity-search providers must be a list.",
    )
    _require(
        "Bright Data SERP" in providers,
        "Bright Data SERP was not successfully reached.",
    )
    _require(
        "Bright Data Remote MCP" in providers,
        "Bright Data Remote MCP was not successfully reached.",
    )

    record_count = search.get(
        "candidate_evidence_records"
    )
    _require(
        isinstance(record_count, int)
        and record_count >= 0,
        "candidate_evidence_records must be a non-negative integer.",
    )

    rejected_results = search.get(
        "rejected_results"
    )
    rejected_count = search.get(
        "rejected_result_count"
    )
    _require(
        isinstance(rejected_results, list),
        "rejected_results must be a list.",
    )
    _require(
        isinstance(rejected_count, int)
        and rejected_count == len(
            rejected_results
        ),
        "rejected_result_count does not match rejected_results.",
    )

    for rejected in rejected_results:
        _require(
            isinstance(rejected, dict),
            "Every rejected identity result must be an object.",
        )
        _require(
            set(rejected) == {
                "url",
                "title",
                "reason",
            },
            (
                "Rejected identity audit must contain only "
                "url, title, and reason."
            ),
        )
        _require(
            _valid_http_url(
                rejected.get("url")
            ),
            "Rejected identity result contains an invalid URL.",
        )
        _require(
            bool(
                _clean(
                    rejected.get("reason")
                )
            ),
            "Rejected identity result is missing a reason.",
        )

    _require(
        bool(_clean(search.get("started_at"))),
        "Identity search is missing started_at.",
    )
    _require(
        bool(_clean(search.get("completed_at"))),
        "Identity search is missing completed_at.",
    )

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
    ).lower()

    exposed = [
        marker
        for marker in PROTECTED_MARKERS
        if marker in serialized
    ]
    _require(
        not exposed,
        (
            "Identity response contains a protected marker: "
            + ", ".join(exposed)
        ),
    )

    return {
        "resolution_status": status,
        "candidate_count": len(candidates),
        "candidate_evidence_records": record_count,
        "rejected_result_count": rejected_count,
        "providers": providers,
        "warnings": search.get("warnings", []),
        "validated_no_job": True,
        "validated_no_llm": True,
        "validated_no_risk_scoring": True,
        "validated_no_database_write": True,
    }


def main() -> None:
    vendor_name = (
        os.getenv(
            "IDENTITY_SMOKE_VENDOR",
            "ABC Trading",
        ).strip()
        or "ABC Trading"
    )

    app = FastAPI()
    app.include_router(router)

    request_body = {
        "vendor_name": vendor_name,
        "language": "EN",
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/vendors/resolve",
            json=request_body,
        )

    _require(
        response.status_code == 200,
        (
            "Vendor identity endpoint returned HTTP "
            f"{response.status_code}: {response.text[:500]}"
        ),
    )

    payload = response.json()
    validation = validate_identity_response(
        payload
    )

    artifact = {
        "test_name": (
            "controlled_vendor_identity_live_smoke"
        ),
        "vendor_input": vendor_name,
        "request": request_body,
        "response": payload,
        "validation": validation,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "external_call_budget": {
            "bright_data_serp_searches": 2,
            "bright_data_remote_mcp_searches": 1,
            "page_scrapes": 0,
            "llm_calls": 0,
            "risk_scoring_calls": 0,
            "database_writes": 0,
            "investigation_jobs": 0,
        },
    }

    ARTIFACT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    ARTIFACT_PATH.write_text(
        json.dumps(
            artifact,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print("Vendor identity live smoke test passed.")
    print(f"Vendor input: {vendor_name}")
    print(
        "Resolution status: "
        f"{validation['resolution_status']}"
    )
    print(
        "Candidate count: "
        f"{validation['candidate_count']}"
    )
    print(
        "Identity evidence records: "
        f"{validation['candidate_evidence_records']}"
    )
    print(
        "Rejected identity results: "
        f"{validation['rejected_result_count']}"
    )
    print(
        "Providers: "
        + ", ".join(
            validation["providers"]
        )
    )
    print("CrewAI/LLM calls: 0")
    print("Risk-scoring calls: 0")
    print("Database writes: 0")
    print("Investigation jobs: 0")
    print(f"Artifact: {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
