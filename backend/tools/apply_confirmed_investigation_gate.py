"""Apply the confirmed-identity investigation gate to existing backend files.

This one-time patcher is deliberately strict: every replacement must match the
expected branch content exactly once, otherwise it exits without writing a
partial patch.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


TEST_FILES = {
    'tests/test_investigation_authorization.py': '"""Tests for the confirmed-identity investigation authorization boundary."""\n\nimport pytest\n\nfrom core.investigation_authorization import (\n    InvestigationAuthorizationError,\n    clear_investigation_authorizations_for_testing,\n    consume_investigation_authorization,\n    issue_investigation_authorization,\n)\n\n\ndef _confirmed_payload() -> dict:\n    return {\n        "resolution_status": "CONFIRMED",\n        "requested_name": "Microsoft",\n        "selected_candidate": {\n            "legal_name": "Microsoft",\n            "website": "https://www.microsoft.com",\n            "website_domain": "microsoft.com",\n            "country": "United States",\n            "city": None,\n            "industry": "Technology",\n            "identity_confidence": 0.99,\n            "confidence_label": "HIGH",\n            "source_quality_labels": ["OFFICIAL_WEBSITE"],\n            "evidence_urls": ["https://www.microsoft.com"],\n        },\n    }\n\n\ndef setup_function() -> None:\n    clear_investigation_authorizations_for_testing()\n\n\ndef test_confirmed_identity_issues_and_consumes_single_use_authorization() -> None:\n    authorization = issue_investigation_authorization(_confirmed_payload())\n\n    assert authorization["authorization_id"]\n    assert authorization["single_use"] is True\n\n    identity = consume_investigation_authorization(\n        authorization["authorization_id"],\n        requested_vendor_name="Microsoft",\n    )\n\n    assert identity["status"] == "CONFIRMED"\n    assert identity["canonical_name"] == "Microsoft"\n    assert identity["website_domain"] == "microsoft.com"\n    assert "authorization_id" not in identity\n\n    with pytest.raises(InvestigationAuthorizationError) as replay:\n        consume_investigation_authorization(\n            authorization["authorization_id"]\n        )\n\n    assert replay.value.status_code == 401\n\n\ndef test_non_confirmed_identity_cannot_issue_authorization() -> None:\n    payload = _confirmed_payload()\n    payload["resolution_status"] = "MORE_INFORMATION_REQUIRED"\n    payload["selected_candidate"] = None\n\n    with pytest.raises(InvestigationAuthorizationError) as error:\n        issue_investigation_authorization(payload)\n\n    assert error.value.status_code == 409\n\n\ndef test_weak_or_unauthenticated_candidate_cannot_issue_authorization() -> None:\n    payload = _confirmed_payload()\n    payload["selected_candidate"]["identity_confidence"] = 0.79\n    payload["selected_candidate"]["source_quality_labels"] = ["DIRECTORY_LEAD"]\n\n    with pytest.raises(InvestigationAuthorizationError):\n        issue_investigation_authorization(payload)\n\n\ndef test_vendor_name_mismatch_does_not_consume_authorization() -> None:\n    authorization = issue_investigation_authorization(_confirmed_payload())\n\n    with pytest.raises(InvestigationAuthorizationError) as mismatch:\n        consume_investigation_authorization(\n            authorization["authorization_id"],\n            requested_vendor_name="Different Company",\n        )\n\n    assert mismatch.value.status_code == 409\n\n    identity = consume_investigation_authorization(\n        authorization["authorization_id"],\n        requested_vendor_name="Microsoft",\n    )\n    assert identity["canonical_name"] == "Microsoft"\n',
    'tests/test_confirmed_investigation_gate.py': '"""API boundary tests: no investigation job without confirmed identity."""\n\nimport json\n\nimport pytest\nfrom fastapi import BackgroundTasks, HTTPException\n\nimport main\nfrom core.investigation_authorization import (\n    clear_investigation_authorizations_for_testing,\n    issue_investigation_authorization,\n)\n\n\ndef _confirmed_payload() -> dict:\n    return {\n        "resolution_status": "CONFIRMED",\n        "requested_name": "Microsoft",\n        "selected_candidate": {\n            "legal_name": "Microsoft",\n            "website": "https://www.microsoft.com",\n            "website_domain": "microsoft.com",\n            "country": "United States",\n            "city": None,\n            "industry": "Technology",\n            "identity_confidence": 0.99,\n            "confidence_label": "HIGH",\n            "source_quality_labels": ["OFFICIAL_WEBSITE"],\n            "evidence_urls": ["https://www.microsoft.com"],\n        },\n    }\n\n\ndef setup_function() -> None:\n    clear_investigation_authorizations_for_testing()\n    main.active_jobs.clear()\n\n\n@pytest.mark.asyncio\nasync def test_invalid_authorization_cannot_create_job() -> None:\n    request = main.VendorInvestigationRequest(\n        identity_authorization_id="invalid-token",\n        vendor_name="Microsoft",\n        language="EN",\n    )\n\n    with pytest.raises(HTTPException) as error:\n        await main.start_investigation(\n            request,\n            BackgroundTasks(),\n        )\n\n    assert error.value.status_code == 401\n    assert main.active_jobs == {}\n\n\n@pytest.mark.asyncio\nasync def test_confirmed_authorization_queues_canonical_identity_without_token() -> None:\n    authorization = issue_investigation_authorization(_confirmed_payload())\n    background = BackgroundTasks()\n    request = main.VendorInvestigationRequest(\n        identity_authorization_id=authorization["authorization_id"],\n        vendor_name="Microsoft",\n        job_id="confirmed-job",\n        language="EN",\n    )\n\n    response = await main.start_investigation(\n        request,\n        background,\n    )\n\n    assert response == {\n        "job_id": "confirmed-job",\n        "status": "queued",\n        "vendor_name": "Microsoft",\n    }\n    assert main.active_jobs["confirmed-job"]["identity"]["status"] == "CONFIRMED"\n    assert main.active_jobs["confirmed-job"]["identity"]["website_domain"] == "microsoft.com"\n    assert "authorization_id" not in json.dumps(main.active_jobs["confirmed-job"])\n    assert len(background.tasks) == 1\n\n\n@pytest.mark.asyncio\nasync def test_authorization_replay_cannot_create_second_job() -> None:\n    authorization = issue_investigation_authorization(_confirmed_payload())\n\n    first = main.VendorInvestigationRequest(\n        identity_authorization_id=authorization["authorization_id"],\n        job_id="first-job",\n        language="EN",\n    )\n    await main.start_investigation(first, BackgroundTasks())\n\n    second = main.VendorInvestigationRequest(\n        identity_authorization_id=authorization["authorization_id"],\n        job_id="second-job",\n        language="EN",\n    )\n\n    with pytest.raises(HTTPException) as error:\n        await main.start_investigation(second, BackgroundTasks())\n\n    assert error.value.status_code == 401\n    assert "second-job" not in main.active_jobs\n\n\n@pytest.mark.asyncio\nasync def test_vendor_mismatch_is_rejected_before_job_creation() -> None:\n    authorization = issue_investigation_authorization(_confirmed_payload())\n    request = main.VendorInvestigationRequest(\n        identity_authorization_id=authorization["authorization_id"],\n        vendor_name="Different Company",\n        job_id="mismatch-job",\n        language="EN",\n    )\n\n    with pytest.raises(HTTPException) as error:\n        await main.start_investigation(request, BackgroundTasks())\n\n    assert error.value.status_code == 409\n    assert "mismatch-job" not in main.active_jobs\n',
    'tests/test_confirmed_orchestrator_context.py': '"""Tests for passing confirmed identity context into the orchestrator."""\n\nimport pytest\n\nfrom agents.orchestrator import SentinelOrchestrator\n\n\ndef _identity() -> dict:\n    return {\n        "status": "CONFIRMED",\n        "requested_name": "Microsoft",\n        "canonical_name": "Microsoft",\n        "website": "https://www.microsoft.com",\n        "website_domain": "microsoft.com",\n        "country": "United States",\n        "city": None,\n        "industry": "Technology",\n        "identity_confidence": 0.99,\n        "confidence_label": "HIGH",\n        "source_quality_labels": ["OFFICIAL_WEBSITE"],\n        "evidence_urls": ["https://www.microsoft.com"],\n        "issued_at": "2026-07-27T00:00:00+00:00",\n        "expires_at": "2026-07-27T00:15:00+00:00",\n        "consumed_at": "2026-07-27T00:01:00+00:00",\n    }\n\n\n@pytest.mark.asyncio\nasync def test_confirmed_wrapper_delegates_canonical_identity(monkeypatch) -> None:\n    orchestrator = SentinelOrchestrator()\n    captured = {}\n\n    async def fake_investigate_vendor(\n        vendor_name,\n        language="EN",\n        identity_context=None,\n    ):\n        captured.update(\n            {\n                "vendor_name": vendor_name,\n                "language": language,\n                "identity_context": identity_context,\n            }\n        )\n        return {"status": "completed"}\n\n    monkeypatch.setattr(\n        orchestrator,\n        "investigate_vendor",\n        fake_investigate_vendor,\n    )\n\n    result = await orchestrator.investigate_confirmed_vendor(\n        _identity(),\n        language="EN",\n    )\n\n    assert result["status"] == "completed"\n    assert result["identity_context"]["status"] == "CONFIRMED"\n    assert result["identity_context"]["canonical_name"] == "Microsoft"\n    assert result["identity_context"]["website_domain"] == "microsoft.com"\n    assert result["raw_intelligence"]["identity_gate"] == "confirmed"\n    assert captured["vendor_name"] == "Microsoft"\n    assert captured["identity_context"]["status"] == "CONFIRMED"\n    assert captured["identity_context"]["website_domain"] == "microsoft.com"\n\n\n@pytest.mark.asyncio\nasync def test_confirmed_wrapper_rejects_unconfirmed_identity() -> None:\n    identity = _identity()\n    identity["status"] = "MORE_INFORMATION_REQUIRED"\n\n    with pytest.raises(ValueError, match="CONFIRMED"):\n        await SentinelOrchestrator().investigate_confirmed_vendor(identity)\n',
}


def _write_gate_tests() -> None:
    for relative_path, content in TEST_FILES.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _replace_once(
    text: str,
    old: str,
    new: str,
    *,
    label: str,
) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected one exact match, found {count}."
        )
    return text.replace(old, new, 1)


def _patch_vendor_resolution_api() -> None:
    path = ROOT / "core/vendor_resolution_api.py"
    text = path.read_text(encoding="utf-8")

    text = _replace_once(
        text,
        "from core.live_vendor_identity import (\n",
        "from core.investigation_authorization import (\n"
        "    issue_investigation_authorization,\n"
        ")\n"
        "from core.live_vendor_identity import (\n",
        label="vendor authorization import",
    )

    text = _replace_once(
        text,
        "    return payload\n",
        "    payload[\"investigation_authorization\"] = None\n"
        "\n"
        "    if payload.get(\"resolution_status\") == \"CONFIRMED\":\n"
        "        payload[\"investigation_authorization\"] = (\n"
        "            issue_investigation_authorization(payload)\n"
        "        )\n"
        "\n"
        "    return payload\n",
        label="vendor authorization response",
    )

    path.write_text(text, encoding="utf-8")


def _patch_main() -> None:
    path = ROOT / "main.py"
    text = path.read_text(encoding="utf-8")

    text = _replace_once(
        text,
        "from core.database import (\n",
        "from core.investigation_authorization import (\n"
        "    InvestigationAuthorizationError,\n"
        "    consume_investigation_authorization,\n"
        ")\n"
        "from core.database import (\n",
        label="main authorization import",
    )

    text = _replace_once(
        text,
        "    vendor_name: str\n"
        "    job_id: str | None = None\n"
        "    language: str = \"EN\"\n",
        "    identity_authorization_id: str\n"
        "    vendor_name: str | None = None\n"
        "    job_id: str | None = None\n"
        "    language: str = \"EN\"\n",
        label="investigation request model",
    )

    text = _replace_once(
        text,
        "    Vendor identity resolution is available separately through\n"
        "    POST /api/vendors/resolve. This route remains backward compatible.\n",
        "    A short-lived authorization from POST /api/vendors/resolve is\n"
        "    required. Unconfirmed, expired, mismatched, or replayed identity\n"
        "    authorizations cannot create investigation jobs.\n",
        label="investigation endpoint documentation",
    )

    text = _replace_once(
        text,
        "    vendor_name = \" \".join(\n"
        "        request.vendor_name.split()\n"
        "    ).strip()\n"
        "\n"
        "    if not vendor_name:\n"
        "        raise HTTPException(\n"
        "            status_code=400,\n"
        "            detail=\"vendor_name is required\",\n"
        "        )\n"
        "\n",
        "",
        label="legacy vendor-name-only gate",
    )

    duplicate_block = (
        "    if job_id in active_jobs:\n"
        "        raise HTTPException(\n"
        "            status_code=409,\n"
        "            detail=\"job_id already exists\",\n"
        "        )\n"
    )
    authorized_block = duplicate_block + (
        "\n"
        "    try:\n"
        "        confirmed_identity = (\n"
        "            consume_investigation_authorization(\n"
        "                request.identity_authorization_id,\n"
        "                requested_vendor_name=request.vendor_name,\n"
        "            )\n"
        "        )\n"
        "    except InvestigationAuthorizationError as error:\n"
        "        raise HTTPException(\n"
        "            status_code=error.status_code,\n"
        "            detail=error.detail,\n"
        "        ) from error\n"
        "\n"
        "    vendor_name = confirmed_identity[\"canonical_name\"]\n"
    )
    text = _replace_once(
        text,
        duplicate_block,
        authorized_block,
        label="authorization consumption gate",
    )

    text = _replace_once(
        text,
        "        \"language\": language,\n"
        "        \"status\": \"queued\",\n",
        "        \"language\": language,\n"
        "        \"identity\": confirmed_identity,\n"
        "        \"status\": \"queued\",\n",
        label="job identity snapshot",
    )

    text = _replace_once(
        text,
        "        vendor_name,\n"
        "        language,\n"
        "    )\n",
        "        vendor_name,\n"
        "        language,\n"
        "        confirmed_identity,\n"
        "    )\n",
        label="background identity argument",
    )

    text = _replace_once(
        text,
        "async def _run_investigation(\n"
        "    job_id: str,\n"
        "    vendor_name: str,\n"
        "    language: str,\n"
        ") -> None:\n",
        "async def _run_investigation(\n"
        "    job_id: str,\n"
        "    vendor_name: str,\n"
        "    language: str,\n"
        "    identity_context: dict[str, Any],\n"
        ") -> None:\n",
        label="background identity signature",
    )

    text = _replace_once(
        text,
        "        report = await orchestrator.investigate_vendor(\n"
        "            vendor_name,\n"
        "            language=language,\n"
        "        )\n",
        "        report = await orchestrator.investigate_confirmed_vendor(\n"
        "            identity_context,\n"
        "            language=language,\n"
        "        )\n",
        label="confirmed orchestrator call",
    )

    path.write_text(text, encoding="utf-8")


def _patch_orchestrator() -> None:
    path = ROOT / "agents/orchestrator.py"
    text = path.read_text(encoding="utf-8")

    language_helper = (
        "def _normalize_language(language: str) -> str:\n"
        "    \"\"\"Return a normalized language token for reports and SERP requests.\"\"\"\n"
        "    normalized = language.strip().upper()\n"
        "    return normalized or \"EN\"\n"
    )
    identity_helper = language_helper + (
        "\n\n"
        "def _normalize_confirmed_identity_context(\n"
        "    identity_context: dict[str, Any],\n"
        ") -> dict[str, Any]:\n"
        "    \"\"\"Validate and minimize confirmed identity context for a report.\"\"\"\n"
        "    if not isinstance(identity_context, dict):\n"
        "        raise ValueError(\"Confirmed identity context is required.\")\n"
        "\n"
        "    if str(identity_context.get(\"status\", \"\")).upper() != \"CONFIRMED\":\n"
        "        raise ValueError(\"Investigation requires CONFIRMED identity status.\")\n"
        "\n"
        "    canonical_name = _normalize_vendor_name(\n"
        "        str(identity_context.get(\"canonical_name\", \"\"))\n"
        "    )\n"
        "    confidence = identity_context.get(\"identity_confidence\")\n"
        "\n"
        "    if (\n"
        "        not isinstance(confidence, (int, float))\n"
        "        or isinstance(confidence, bool)\n"
        "        or float(confidence) < 0.90\n"
        "    ):\n"
        "        raise ValueError(\"Confirmed identity confidence is below 0.90.\")\n"
        "\n"
        "    return {\n"
        "        \"status\": \"CONFIRMED\",\n"
        "        \"requested_name\": str(identity_context.get(\"requested_name\", \"\")).strip(),\n"
        "        \"canonical_name\": canonical_name,\n"
        "        \"website\": identity_context.get(\"website\"),\n"
        "        \"website_domain\": identity_context.get(\"website_domain\"),\n"
        "        \"country\": identity_context.get(\"country\"),\n"
        "        \"city\": identity_context.get(\"city\"),\n"
        "        \"industry\": identity_context.get(\"industry\"),\n"
        "        \"identity_confidence\": round(float(confidence), 2),\n"
        "        \"confidence_label\": str(identity_context.get(\"confidence_label\", \"HIGH\")),\n"
        "        \"source_quality_labels\": list(identity_context.get(\"source_quality_labels\") or []),\n"
        "        \"evidence_urls\": list(identity_context.get(\"evidence_urls\") or []),\n"
        "    }\n"
    )
    text = _replace_once(
        text,
        language_helper,
        identity_helper,
        label="confirmed identity context helper",
    )

    method_anchor = (
        "    async def investigate_vendor(\n"
        "        self,\n"
        "        vendor_name: str,\n"
        "        language: str = \"EN\",\n"
        "    ) -> dict[str, Any]:\n"
    )
    confirmed_method = (
        "    async def investigate_confirmed_vendor(\n"
        "        self,\n"
        "        identity_context: dict[str, Any],\n"
        "        language: str = \"EN\",\n"
        "    ) -> dict[str, Any]:\n"
        "        \"\"\"Investigate only a strongly confirmed canonical identity.\"\"\"\n"
        "        confirmed = _normalize_confirmed_identity_context(\n"
        "            identity_context\n"
        "        )\n"
        "        report = await self.investigate_vendor(\n"
        "            confirmed[\"canonical_name\"],\n"
        "            language=language,\n"
        "        )\n"
        "        report[\"identity_context\"] = confirmed\n"
        "        raw = report.setdefault(\"raw_intelligence\", {})\n"
        "        raw[\"identity_gate\"] = \"confirmed\"\n"
        "        return report\n"
        "\n"
        + method_anchor
    )
    text = _replace_once(
        text,
        method_anchor,
        confirmed_method,
        label="confirmed orchestrator entrypoint",
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    paths = [
        ROOT / "core/vendor_resolution_api.py",
        ROOT / "main.py",
        ROOT / "agents/orchestrator.py",
    ]
    originals = {
        path: path.read_text(encoding="utf-8")
        for path in paths
    }
    test_paths = [ROOT / relative for relative in TEST_FILES]
    original_tests = {
        path: path.read_text(encoding="utf-8")
        for path in test_paths
        if path.exists()
    }

    try:
        _patch_vendor_resolution_api()
        _patch_main()
        _patch_orchestrator()
        _write_gate_tests()
    except Exception:
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        for path in test_paths:
            if path in original_tests:
                path.write_text(original_tests[path], encoding="utf-8")
            elif path.exists():
                path.unlink()
        raise

    print("Confirmed investigation gate applied successfully.")


if __name__ == "__main__":
    main()
