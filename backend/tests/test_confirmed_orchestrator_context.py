"""Tests for passing confirmed identity context into the orchestrator."""

import pytest

from agents.orchestrator import SentinelOrchestrator


def _identity() -> dict:
    return {
        "status": "CONFIRMED",
        "requested_name": "Microsoft",
        "canonical_name": "Microsoft",
        "website": "https://www.microsoft.com",
        "website_domain": "microsoft.com",
        "country": "United States",
        "city": None,
        "industry": "Technology",
        "identity_confidence": 0.99,
        "confidence_label": "HIGH",
        "source_quality_labels": ["OFFICIAL_WEBSITE"],
        "evidence_urls": ["https://www.microsoft.com"],
        "issued_at": "2026-07-27T00:00:00+00:00",
        "expires_at": "2026-07-27T00:15:00+00:00",
        "consumed_at": "2026-07-27T00:01:00+00:00",
    }


@pytest.mark.asyncio
async def test_confirmed_wrapper_delegates_canonical_identity(monkeypatch) -> None:
    orchestrator = SentinelOrchestrator()
    captured = {}

    async def fake_investigate_vendor(
        vendor_name,
        language="EN",
        identity_context=None,
    ):
        captured.update(
            {
                "vendor_name": vendor_name,
                "language": language,
                "identity_context": identity_context,
            }
        )
        return {"status": "completed"}

    monkeypatch.setattr(
        orchestrator,
        "investigate_vendor",
        fake_investigate_vendor,
    )

    result = await orchestrator.investigate_confirmed_vendor(
        _identity(),
        language="EN",
    )

    assert result["status"] == "completed"
    assert result["identity_context"]["status"] == "CONFIRMED"
    assert result["identity_context"]["canonical_name"] == "Microsoft"
    assert result["identity_context"]["website_domain"] == "microsoft.com"
    assert result["raw_intelligence"]["identity_gate"] == "confirmed"
    assert captured["vendor_name"] == "Microsoft"
    assert captured["identity_context"]["status"] == "CONFIRMED"
    assert captured["identity_context"]["website_domain"] == "microsoft.com"


@pytest.mark.asyncio
async def test_confirmed_wrapper_rejects_unconfirmed_identity() -> None:
    identity = _identity()
    identity["status"] = "MORE_INFORMATION_REQUIRED"

    with pytest.raises(ValueError, match="CONFIRMED"):
        await SentinelOrchestrator().investigate_confirmed_vendor(identity)
