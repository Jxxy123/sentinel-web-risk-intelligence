"""Generic live smoke runner for runtime vendor identity inputs.

No vendor, website, country, city, or industry is embedded in this module.
Every test input is supplied dynamically through a runtime JSON configuration file or environment variables.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ARTIFACT_PATH = Path(
    "artifacts/vendor_identity_runtime_smoke.json"
)

ALLOWED_STATUSES = {
    "CONFIRMED",
    "SELECTION_REQUIRED",
    "MORE_INFORMATION_REQUIRED",
}

FORBIDDEN_RESPONSE_FIELDS = {
    "job_id",
    "report",
    "risk_score",
    "risk_level",
    "disruption_probability",
    "raw_intelligence",
}

FORBIDDEN_ACCEPTED_QUALITIES = {
    "AUTHORITATIVE_CONTEXT",
    "DIRECTORY_LEAD",
    "REPUTABLE_BUSINESS_DIRECTORY",
    "GENERAL_WEB",
    "SOCIAL",
    "REPUTABLE_NEWS",
}

PROTECTED_MARKERS = (
    "bright_data_api_key",
    "authorization: bearer",
    "proxy_password",
    "proxy_pass",
    "openai_api_key",
    "github_token",
    '"access_token"',
)


@dataclass(frozen=True)
class RuntimeExpectation:
    expected_status: str
    minimum_confidence: float
    require_official_website: bool
    require_zero_authenticated_evidence: bool


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _env(name: str, default: str = "") -> str:
    return _clean(os.getenv(name, default))


def _coerce_bool(
    value: Any,
    *,
    field_name: str,
    default: bool = False,
) -> bool:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return value

    normalized = _clean(value).lower()

    if normalized in {"true", "1", "yes", "on"}:
        return True

    if normalized in {"false", "0", "no", "off"}:
        return False

    raise ValueError(
        f"{field_name} must be true or false."
    )


def _env_bool(name: str, default: bool = False) -> bool:
    return _coerce_bool(
        os.getenv(name),
        field_name=name,
        default=default,
    )


RUNTIME_CONFIG_FIELDS = {
    "vendor_name",
    "website",
    "country",
    "city",
    "industry",
    "language",
    "expected_status",
    "minimum_confidence",
    "require_official_website",
    "require_zero_authenticated_evidence",
}


def load_runtime_config(
    config_path: str | Path,
) -> dict[str, Any]:
    path = Path(config_path)

    if not path.is_file():
        raise ValueError(
            f"Runtime configuration file not found: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            "Runtime configuration must contain valid JSON."
        ) from error

    if not isinstance(payload, dict):
        raise ValueError(
            "Runtime configuration must be a JSON object."
        )

    unknown_fields = sorted(
        set(payload) - RUNTIME_CONFIG_FIELDS
    )

    if unknown_fields:
        raise ValueError(
            "Runtime configuration contains unsupported fields: "
            + ", ".join(unknown_fields)
        )

    return payload


def _config_or_env(
    config: dict[str, Any],
    config_key: str,
    env_name: str,
    default: Any = "",
) -> Any:
    if config_key in config:
        return config[config_key]

    return os.getenv(env_name, default)


def _domain(value: Any) -> str:
    text = _clean(value)

    if not text:
        return ""

    if "://" not in text:
        text = "https://" + text

    parsed = urlparse(text)

    return (
        parsed.netloc.lower()
        .removeprefix("www.")
    )


LEGAL_COMPANY_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "company",
    "co",
    "limited",
    "ltd",
    "llc",
    "plc",
    "holdings",
    "group",
    "llp",
    "pte",
    "sdn",
    "bhd",
    "gmbh",
    "ag",
    "sa",
    "spa",
    "srl",
    "bv",
    "nv",
    "oy",
    "ab",
}


def _domain_matches_expected(
    observed_domain: str,
    expected_domain: str,
) -> bool:
    return bool(
        observed_domain
        and expected_domain
        and (
            observed_domain == expected_domain
            or observed_domain.endswith(
                "." + expected_domain
            )
        )
    )


def _company_name_is_canonical(
    requested_name: Any,
    candidate_name: Any,
) -> bool:
    requested_tokens = [
        token
        for token in re.sub(
            r"[^a-z0-9]+",
            " ",
            _clean(requested_name).lower(),
        ).split()
        if token
    ]
    candidate_tokens = [
        token
        for token in re.sub(
            r"[^a-z0-9]+",
            " ",
            _clean(candidate_name).lower(),
        ).split()
        if token
    ]

    if not requested_tokens or not candidate_tokens:
        return False

    requested_core = [
        token
        for token in requested_tokens
        if token not in LEGAL_COMPANY_SUFFIXES
    ]
    candidate_core = [
        token
        for token in candidate_tokens
        if token not in LEGAL_COMPANY_SUFFIXES
    ]

    return candidate_core == requested_core


def _valid_http_url(value: Any) -> bool:
    parsed = urlparse(
        _clean(value)
    )

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


def build_runtime_request() -> tuple[
    dict[str, str],
    RuntimeExpectation,
]:
    config_file = _env(
        "IDENTITY_RUNTIME_CONFIG_FILE"
    )
    config = (
        load_runtime_config(config_file)
        if config_file
        else {}
    )

    vendor_name = _clean(
        _config_or_env(
            config,
            "vendor_name",
            "IDENTITY_RUNTIME_VENDOR_NAME",
        )
    )

    if not vendor_name:
        raise ValueError(
            "vendor_name is required."
        )

    language = _clean(
        _config_or_env(
            config,
            "language",
            "IDENTITY_RUNTIME_LANGUAGE",
            "EN",
        )
    ).upper() or "EN"

    request_body = {
        "vendor_name": vendor_name,
        "language": language,
    }

    optional_fields = {
        "website": _clean(
            _config_or_env(
                config,
                "website",
                "IDENTITY_RUNTIME_WEBSITE",
            )
        ),
        "country": _clean(
            _config_or_env(
                config,
                "country",
                "IDENTITY_RUNTIME_COUNTRY",
            )
        ),
        "city": _clean(
            _config_or_env(
                config,
                "city",
                "IDENTITY_RUNTIME_CITY",
            )
        ),
        "industry": _clean(
            _config_or_env(
                config,
                "industry",
                "IDENTITY_RUNTIME_INDUSTRY",
            )
        ),
    }

    request_body.update(
        {
            key: value
            for key, value in optional_fields.items()
            if value
        }
    )

    expected_status = _clean(
        _config_or_env(
            config,
            "expected_status",
            "IDENTITY_RUNTIME_EXPECTED_STATUS",
            "ANY_SAFE",
        )
    ).upper() or "ANY_SAFE"

    if expected_status not in (
        ALLOWED_STATUSES
        | {"ANY_SAFE"}
    ):
        raise ValueError(
            "expected_status must be ANY_SAFE, "
            "CONFIRMED, SELECTION_REQUIRED, or "
            "MORE_INFORMATION_REQUIRED."
        )

    minimum_confidence = float(
        _config_or_env(
            config,
            "minimum_confidence",
            "IDENTITY_RUNTIME_MINIMUM_CONFIDENCE",
            "0.90",
        )
    )

    if not 0 <= minimum_confidence <= 1:
        raise ValueError(
            "minimum_confidence must be between 0 and 1."
        )

    expectation = RuntimeExpectation(
        expected_status=expected_status,
        minimum_confidence=minimum_confidence,
        require_official_website=_coerce_bool(
            _config_or_env(
                config,
                "require_official_website",
                "IDENTITY_RUNTIME_REQUIRE_OFFICIAL_WEBSITE",
                False,
            ),
            field_name="require_official_website",
        ),
        require_zero_authenticated_evidence=_coerce_bool(
            _config_or_env(
                config,
                "require_zero_authenticated_evidence",
                "IDENTITY_RUNTIME_REQUIRE_ZERO_EVIDENCE",
                False,
            ),
            field_name=(
                "require_zero_authenticated_evidence"
            ),
        ),
    )

    if (
        expectation.require_official_website
        and not request_body.get("website")
    ):
        raise ValueError(
            "A website is required when "
            "require_official_website is true."
        )

    return request_body, expectation


def validate_runtime_response(
    payload: dict[str, Any],
    request_body: dict[str, str],
    expectation: RuntimeExpectation,
) -> list[str]:
    errors: list[str] = []

    def require(
        condition: bool,
        message: str,
    ) -> None:
        if not condition:
            errors.append(message)

    require(
        isinstance(payload, dict),
        "Endpoint response must be a JSON object.",
    )

    if not isinstance(payload, dict):
        return errors

    forbidden = sorted(
        FORBIDDEN_RESPONSE_FIELDS
        & set(payload)
    )
    require(
        not forbidden,
        (
            "Identity response contains investigation "
            "fields: "
            + ", ".join(forbidden)
        ),
    )

    status = _clean(
        payload.get("resolution_status")
    ).upper()
    require(
        status in ALLOWED_STATUSES,
        "Resolution status is invalid.",
    )

    if (
        expectation.expected_status
        != "ANY_SAFE"
    ):
        require(
            status
            == expectation.expected_status,
            (
                "Expected resolution status "
                f"{expectation.expected_status}, "
                f"received {status or 'missing'}."
            ),
        )

    selected = payload.get(
        "selected_candidate"
    )
    candidates = payload.get(
        "candidates"
    )

    require(
        isinstance(candidates, list),
        "candidates must be a list.",
    )

    if status == "CONFIRMED":
        require(
            isinstance(selected, dict),
            (
                "CONFIRMED must include a selected "
                "candidate."
            ),
        )
    else:
        require(
            selected is None,
            (
                "A non-CONFIRMED result must not "
                "silently select a company."
            ),
        )

    expected_domain = _domain(
        request_body.get("website")
    )

    if isinstance(selected, dict):
        selected_domain = _clean(
            selected.get("website_domain")
        ).lower().removeprefix("www.")

        if expected_domain:
            require(
                _domain_matches_expected(
                    selected_domain,
                    expected_domain,
                ),
                (
                    "Selected candidate domain does not "
                    "match the user-supplied website."
                ),
            )

        if status == "CONFIRMED":
            require(
                _company_name_is_canonical(
                    request_body.get(
                        "vendor_name"
                    ),
                    selected.get(
                        "legal_name"
                    ),
                ),
                (
                    "Confirmed legal_name looks like a "
                    "page or document title instead of "
                    "the requested company identity."
                ),
            )

        confidence = selected.get(
            "identity_confidence"
        )
        require(
            isinstance(
                confidence,
                (int, float),
            )
            and not isinstance(
                confidence,
                bool,
            )
            and 0 <= confidence <= 1,
            (
                "Selected candidate confidence must "
                "be between 0 and 1."
            ),
        )

        if status == "CONFIRMED":
            require(
                isinstance(
                    confidence,
                    (int, float),
                )
                and confidence
                >= expectation.minimum_confidence,
                (
                    "Confirmed candidate confidence is "
                    "below the requested minimum."
                ),
            )
            require(
                selected.get(
                    "confidence_label"
                )
                == "HIGH",
                (
                    "Confirmed candidate must have "
                    "HIGH confidence."
                ),
            )

        labels = selected.get(
            "source_quality_labels"
        )
        require(
            isinstance(labels, list),
            (
                "source_quality_labels must be a "
                "list."
            ),
        )

        if isinstance(labels, list):
            require(
                not (
                    FORBIDDEN_ACCEPTED_QUALITIES
                    & set(labels)
                ),
                (
                    "Selected candidate contains a "
                    "forbidden context or directory "
                    "source class."
                ),
            )

            if (
                expectation
                .require_official_website
            ):
                require(
                    "OFFICIAL_WEBSITE"
                    in labels,
                    (
                        "The confirmed candidate is "
                        "missing OFFICIAL_WEBSITE."
                    ),
                )

        evidence_urls = selected.get(
            "evidence_urls"
        )
        require(
            isinstance(
                evidence_urls,
                list,
            ),
            (
                "Candidate evidence_urls must be "
                "a list."
            ),
        )

        if isinstance(
            evidence_urls,
            list,
        ):
            require(
                all(
                    _valid_http_url(url)
                    for url
                    in evidence_urls
                ),
                (
                    "Candidate contains an invalid "
                    "evidence URL."
                ),
            )

    if status == "SELECTION_REQUIRED":
        require(
            isinstance(candidates, list)
            and len(candidates) >= 2,
            (
                "SELECTION_REQUIRED needs at least "
                "two candidates."
            ),
        )

        if isinstance(candidates, list):
            for candidate in candidates:
                require(
                    isinstance(candidate, dict),
                    (
                        "Every selectable candidate "
                        "must be an object."
                    ),
                )

                if not isinstance(
                    candidate,
                    dict,
                ):
                    continue

                require(
                    candidate.get(
                        "evidence_source_count"
                    )
                    >= 2,
                    (
                        "Selectable candidates require "
                        "at least two evidence sources."
                    ),
                )
                require(
                    candidate.get(
                        "identity_confidence"
                    )
                    >= 0.65,
                    (
                        "Selectable candidates require "
                        "confidence of at least 0.65."
                    ),
                )

    search = payload.get(
        "identity_search"
    )
    require(
        isinstance(search, dict),
        (
            "identity_search audit object is "
            "required."
        ),
    )

    if isinstance(search, dict):
        require(
            search.get(
                "search_performed"
            )
            is True,
            "Live identity search was not performed.",
        )

        providers = search.get(
            "providers"
        )
        require(
            isinstance(providers, list)
            and len(providers) >= 1,
            "Live provider audit is missing.",
        )

        queries = search.get(
            "queries_executed"
        )
        require(
            isinstance(queries, list)
            and len(queries) == 3,
            (
                "Expected exactly three identity "
                "queries."
            ),
        )

        record_count = search.get(
            "candidate_evidence_records"
        )
        require(
            isinstance(record_count, int)
            and record_count >= 0,
            (
                "candidate_evidence_records must be "
                "a non-negative integer."
            ),
        )

        accepted = search.get(
            "accepted_results"
        )
        accepted_count = search.get(
            "accepted_result_count"
        )
        require(
            isinstance(accepted, list),
            "accepted_results must be a list.",
        )

        if isinstance(accepted, list):
            require(
                isinstance(
                    accepted_count,
                    int,
                )
                and accepted_count
                == len(accepted),
                (
                    "accepted_result_count does not "
                    "match accepted_results."
                ),
            )

            for result in accepted:
                require(
                    isinstance(result, dict)
                    and set(result) == {
                        "url",
                        "title",
                        "source_quality",
                        "proposed_legal_name",
                        "acceptance_reason",
                    },
                    (
                        "Accepted identity audit has "
                        "unsupported or raw-content "
                        "fields."
                    ),
                )

                if not isinstance(
                    result,
                    dict,
                ):
                    continue

                quality = _clean(
                    result.get(
                        "source_quality"
                    )
                )
                require(
                    quality
                    not in
                    FORBIDDEN_ACCEPTED_QUALITIES,
                    (
                        "A context or directory result "
                        "was accepted as authenticated "
                        "identity evidence."
                    ),
                )
                require(
                    _valid_http_url(
                        result.get("url")
                    ),
                    (
                        "Accepted identity result has "
                        "an invalid URL."
                    ),
                )
                require(
                    bool(
                        _clean(
                            result.get(
                                "proposed_legal_name"
                            )
                        )
                    ),
                    (
                        "Accepted identity result lacks "
                        "a source-supported name."
                    ),
                )

                if (
                    quality
                    == "OFFICIAL_WEBSITE"
                ):
                    require(
                        bool(expected_domain),
                        (
                            "OFFICIAL_WEBSITE was used "
                            "without a user-supplied "
                            "website."
                        ),
                    )
                    require(
                        _domain_matches_expected(
                            _domain(
                                result.get("url")
                            ),
                            expected_domain,
                        ),
                        (
                            "OFFICIAL_WEBSITE was "
                            "assigned to a different "
                            "domain."
                        ),
                    )
                    require(
                        _company_name_is_canonical(
                            request_body.get(
                                "vendor_name"
                            ),
                            result.get(
                                "proposed_legal_name"
                            ),
                        ),
                        (
                            "OFFICIAL_WEBSITE proposed "
                            "legal name looks like a page "
                            "or document title."
                        ),
                    )

        leads = search.get(
            "directory_leads"
        )
        lead_count = search.get(
            "directory_lead_count"
        )
        require(
            isinstance(leads, list),
            "directory_leads must be a list.",
        )

        if isinstance(leads, list):
            require(
                isinstance(
                    lead_count,
                    int,
                )
                and lead_count
                == len(leads),
                (
                    "directory_lead_count does not "
                    "match directory_leads."
                ),
            )

            for lead in leads:
                require(
                    isinstance(lead, dict)
                    and lead.get(
                        "source_quality"
                    )
                    == "DIRECTORY_LEAD",
                    (
                        "Directory audit contains a "
                        "scoring source."
                    ),
                )

        rejected = search.get(
            "rejected_results"
        )
        rejected_count = search.get(
            "rejected_result_count"
        )
        require(
            isinstance(rejected, list),
            "rejected_results must be a list.",
        )

        if isinstance(rejected, list):
            require(
                isinstance(
                    rejected_count,
                    int,
                )
                and rejected_count
                == len(rejected),
                (
                    "rejected_result_count does not "
                    "match rejected_results."
                ),
            )

        require(
            search.get("llm_used")
            is False,
            (
                "Identity resolution unexpectedly "
                "used an LLM."
            ),
        )
        require(
            search.get(
                "risk_scoring_started"
            )
            is False,
            (
                "Identity resolution unexpectedly "
                "started risk scoring."
            ),
        )
        require(
            search.get(
                "database_writes"
            )
            == 0,
            (
                "Identity resolution unexpectedly "
                "wrote to the database."
            ),
        )
        require(
            bool(
                _clean(
                    search.get("started_at")
                )
            ),
            (
                "Identity search is missing "
                "started_at."
            ),
        )
        require(
            bool(
                _clean(
                    search.get(
                        "completed_at"
                    )
                )
            ),
            (
                "Identity search is missing "
                "completed_at."
            ),
        )

        if (
            expectation
            .require_zero_authenticated_evidence
        ):
            require(
                record_count == 0,
                (
                    "Expected zero authenticated "
                    "identity records."
                ),
            )
            require(
                accepted_count == 0,
                (
                    "Expected zero accepted identity "
                    "results."
                ),
            )

        if (
            expectation
            .require_official_website
        ):
            require(
                isinstance(
                    accepted,
                    list,
                )
                and any(
                    result.get(
                        "source_quality"
                    )
                    == "OFFICIAL_WEBSITE"
                    for result
                    in accepted
                    if isinstance(
                        result,
                        dict,
                    )
                ),
                (
                    "No accepted result from the "
                    "supplied domain was typed "
                    "OFFICIAL_WEBSITE."
                ),
            )

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
    ).lower()

    exposed = [
        marker
        for marker
        in PROTECTED_MARKERS
        if marker in serialized
    ]
    require(
        not exposed,
        (
            "Identity response contains a protected "
            "marker: "
            + ", ".join(exposed)
        ),
    )

    return errors


def main() -> None:
    request_body: dict[str, str] = {}
    expectation: RuntimeExpectation | None = None
    response_status: int | None = None
    response_payload: dict[str, Any] | None = None
    errors: list[str] = []

    try:
        request_body, expectation = (
            build_runtime_request()
        )

        # Imports remain inside main so the pure validator
        # can be tested without starting the application.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.vendor_resolution_api import (
            router,
        )

        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            response = client.post(
                "/api/vendors/resolve",
                json=request_body,
            )

        response_status = response.status_code

        if response.status_code != 200:
            errors.append(
                "Vendor identity endpoint returned "
                f"HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        else:
            response_payload = response.json()
            errors.extend(
                validate_runtime_response(
                    response_payload,
                    request_body,
                    expectation,
                )
            )
    except Exception as error:
        errors.append(
            "Runtime identity smoke raised "
            f"{type(error).__name__}: {error}"
        )

    artifact = {
        "test_name": (
            "parameterized_vendor_identity_runtime_smoke"
        ),
        "passed": not errors,
        "request": request_body,
        "expectation": (
            {
                "expected_status": (
                    expectation.expected_status
                ),
                "minimum_confidence": (
                    expectation.minimum_confidence
                ),
                "require_official_website": (
                    expectation
                    .require_official_website
                ),
                "require_zero_authenticated_evidence": (
                    expectation
                    .require_zero_authenticated_evidence
                ),
            }
            if expectation
            else None
        ),
        "http_status": response_status,
        "response": response_payload,
        "validation_errors": errors,
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

    if errors:
        print(
            "Runtime vendor identity smoke "
            "test failed."
        )

        for error in errors:
            print(f"- {error}")

        print(f"Artifact: {ARTIFACT_PATH}")
        raise SystemExit(1)

    print(
        "Runtime vendor identity smoke "
        "test passed."
    )
    print(
        "Vendor input: "
        f"{request_body['vendor_name']}"
    )
    print(
        "Resolution status: "
        f"{response_payload['resolution_status']}"
    )
    print("CrewAI/LLM calls: 0")
    print("Risk-scoring calls: 0")
    print("Database writes: 0")
    print("Investigation jobs: 0")
    print(f"Artifact: {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
