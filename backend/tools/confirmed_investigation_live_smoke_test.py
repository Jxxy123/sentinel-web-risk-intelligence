"""One controlled live identity-to-investigation-to-database smoke test."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.orchestrator import SentinelOrchestrator
from core.database import (
    DB_PATH,
    delete_report_by_id,
    get_report_by_id,
    init_db,
    save_report,
)
from core.investigation_authorization import (
    consume_investigation_authorization,
)
from core.vendor_resolution_api import (
    VendorResolutionRequest,
    resolve_vendor_identity,
)


CONFIG_PATH = Path(
    os.getenv(
        "CONFIRMED_INVESTIGATION_CONFIG_FILE",
        "tools/run_confirmed_investigation_live_smoke.json",
    )
)
ARTIFACT_PATH = Path(
    "artifacts/confirmed_investigation_live_smoke.json"
)
PROTECTED_MARKERS = (
    "authorization: bearer",
    "bright_data_api_key",
    "openai_api_key",
    "proxy_password",
    "proxy_pass",
    "github_token",
    '"access_token"',
    '"authorization_id"',
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _domain(value: Any) -> str:
    text = _clean(value).lower()
    text = text.removeprefix("https://").removeprefix("http://")
    return text.split("/", 1)[0].removeprefix("www.")


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Live smoke configuration must be a JSON object.")

    vendor_name = _clean(payload.get("vendor_name"))
    website = _clean(payload.get("website"))
    if not vendor_name or not website:
        raise ValueError("vendor_name and website are required.")

    return {
        "vendor_name": vendor_name,
        "website": website,
        "country": _clean(payload.get("country")) or None,
        "city": _clean(payload.get("city")) or None,
        "industry": _clean(payload.get("industry")) or None,
        "language": (_clean(payload.get("language")) or "EN").upper(),
        "expected_domain": (
            _clean(payload.get("expected_domain"))
            or _domain(website)
        ).lower().removeprefix("www."),
        "minimum_identity_confidence": float(
            payload.get("minimum_identity_confidence", 0.90)
        ),
    }


def _validate_report(
    report: dict[str, Any],
    identity: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(report.get("status") == "completed", "Report status is not completed.")
    require(
        report.get("vendor_name") == identity.get("canonical_name"),
        "Report vendor does not match confirmed canonical identity.",
    )

    report_identity = report.get("identity_context")
    require(isinstance(report_identity, dict), "Report is missing identity_context.")
    if isinstance(report_identity, dict):
        require(
            report_identity.get("status") == "CONFIRMED",
            "Report identity status is not CONFIRMED.",
        )
        require(
            report_identity.get("canonical_name") == identity.get("canonical_name"),
            "Report identity canonical name changed.",
        )
        require(
            report_identity.get("website_domain") == config["expected_domain"],
            "Report identity domain does not match the supplied official domain.",
        )

    score = report.get("risk_score")
    require(
        isinstance(score, (int, float))
        and not isinstance(score, bool)
        and 0 <= score <= 100,
        "risk_score must be numeric between 0 and 100.",
    )
    require(
        report.get("risk_level") in {"LOW", "MEDIUM", "HIGH", "CRITICAL"},
        "risk_level is invalid.",
    )
    confidence = report.get("confidence_score")
    require(
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= confidence <= 1,
        "confidence_score must be numeric between 0 and 1.",
    )
    require(isinstance(report.get("sources"), list), "sources must be a list.")
    require(
        isinstance(report.get("evidence_provenance"), list),
        "evidence_provenance must be a list.",
    )
    raw = report.get("raw_intelligence")
    require(isinstance(raw, dict), "raw_intelligence must be an object.")
    if isinstance(raw, dict):
        require(
            raw.get("identity_gate") == "confirmed",
            "Orchestrator did not record the confirmed identity gate.",
        )
        require(
            raw.get("scoring_source") == "collected_live_evidence",
            "Risk score was not grounded in collected live evidence.",
        )

    serialized = json.dumps(report, ensure_ascii=False, default=str).lower()
    exposed = [marker for marker in PROTECTED_MARKERS if marker in serialized]
    require(not exposed, "Report exposed protected markers: " + ", ".join(exposed))

    return errors


async def _run() -> dict[str, Any]:
    config = _load_config()
    resolution_request = VendorResolutionRequest(
        vendor_name=config["vendor_name"],
        website=config["website"],
        country=config["country"],
        city=config["city"],
        industry=config["industry"],
        language=config["language"],
    )

    resolution = await resolve_vendor_identity(resolution_request)
    authorization = resolution.pop("investigation_authorization", None)

    if resolution.get("resolution_status") != "CONFIRMED":
        raise RuntimeError(
            "Identity resolution did not return CONFIRMED: "
            + str(resolution.get("resolution_status"))
        )

    selected = resolution.get("selected_candidate") or {}
    if selected.get("website_domain") != config["expected_domain"]:
        raise RuntimeError("Confirmed identity domain did not match the supplied website.")
    if float(selected.get("identity_confidence", 0)) < config["minimum_identity_confidence"]:
        raise RuntimeError("Confirmed identity confidence was below the configured minimum.")
    if not isinstance(authorization, dict) or not authorization.get("authorization_id"):
        raise RuntimeError("Confirmed identity did not issue investigation authorization.")

    identity = consume_investigation_authorization(
        authorization["authorization_id"],
        requested_vendor_name=config["vendor_name"],
    )

    orchestrator = SentinelOrchestrator()
    report = await orchestrator.investigate_confirmed_vendor(
        identity,
        language=config["language"],
    )

    errors = _validate_report(report, identity, config)

    init_db()
    report_id = save_report(report)
    stored = get_report_by_id(report_id)
    if not stored:
        errors.append("Database round-trip could not retrieve the saved report.")
    else:
        if stored.get("vendor_name") != report.get("vendor_name"):
            errors.append("Database vendor name changed during persistence.")
        if stored.get("risk_score") != report.get("risk_score"):
            errors.append("Database risk score changed during persistence.")

    deleted = delete_report_by_id(report_id)
    if not deleted:
        errors.append("Ephemeral smoke-test report could not be deleted.")

    return {
        "passed": not errors,
        "config": config,
        "identity_resolution": resolution,
        "confirmed_identity": identity,
        "report": report,
        "database_round_trip": {
            "database_path": str(DB_PATH),
            "report_id": report_id,
            "retrieved": bool(stored),
            "deleted": deleted,
        },
        "validation_errors": errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        artifact = asyncio.run(_run())
    except Exception as error:
        artifact = {
            "passed": False,
            "error_type": type(error).__name__,
            "error": str(error),
            "validation_errors": [str(error)],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    if not artifact.get("passed"):
        print("Confirmed investigation live smoke test failed.")
        for error in artifact.get("validation_errors", []):
            print(f"- {error}")
        print(f"Artifact: {ARTIFACT_PATH}")
        raise SystemExit(1)

    report = artifact["report"]
    print("Confirmed investigation live smoke test passed.")
    print(f"Vendor: {report['vendor_name']}")
    print(f"Risk: {report['risk_level']} ({report['risk_score']})")
    print(f"Sources: {len(report.get('sources', []))}")
    print("Identity gate: confirmed")
    print("Database round-trip: passed and cleaned")
    print(f"Artifact: {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
