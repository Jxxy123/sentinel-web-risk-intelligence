"""Tests for safe real/mock web-provider selection."""

import asyncio

from core.brightdata import (
    BrightDataMCPClient,
    BrightDataProxyClient,
    BrightDataSERPClient,
    BrightDataWebUnlocker,
)
from core.config import settings
from core.mock_providers import (
    MockBrightDataMCPClient,
    MockBrightDataProxyClient,
    MockBrightDataSERPClient,
    MockBrightDataWebUnlocker,
)
from core.provider_factory import get_web_providers


def test_factory_returns_mock_providers_in_mock_mode(
    monkeypatch,
) -> None:
    """Mock mode must return only local, non-network providers."""
    monkeypatch.setattr(settings, "execution_mode", "mock")

    providers = get_web_providers()

    assert providers.execution_mode == "mock"
    assert providers.is_mock is True
    assert isinstance(providers.serp, MockBrightDataSERPClient)
    assert isinstance(
        providers.web_unlocker,
        MockBrightDataWebUnlocker,
    )
    assert isinstance(providers.proxy, MockBrightDataProxyClient)
    assert isinstance(providers.mcp, MockBrightDataMCPClient)


def test_factory_returns_real_providers_in_real_mode(
    monkeypatch,
) -> None:
    """Real mode must preserve the existing Bright Data clients."""
    monkeypatch.setattr(settings, "execution_mode", "real")

    providers = get_web_providers()

    assert providers.execution_mode == "real"
    assert providers.is_mock is False
    assert isinstance(providers.serp, BrightDataSERPClient)
    assert isinstance(
        providers.web_unlocker,
        BrightDataWebUnlocker,
    )
    assert isinstance(providers.proxy, BrightDataProxyClient)
    assert isinstance(providers.mcp, BrightDataMCPClient)


def test_mock_serp_results_are_deterministic(
    monkeypatch,
) -> None:
    """The same mock investigation must return the same evidence."""
    monkeypatch.setattr(settings, "execution_mode", "mock")
    providers = get_web_providers()

    first_results = asyncio.run(
        providers.serp.search_vendor_news(
            "Critical Demo Vendor",
            lang="en",
        )
    )
    second_results = asyncio.run(
        providers.serp.search_vendor_news(
            "Critical Demo Vendor",
            lang="en",
        )
    )

    assert first_results == second_results
    assert len(first_results) == 5
    assert all(result["is_mock"] is True for result in first_results)
    assert all(
        result["source"] == "mock_serp"
        for result in first_results
    )


def test_mock_providers_make_clearly_labelled_outputs(
    monkeypatch,
) -> None:
    """Synthetic responses must never be confused with real evidence."""
    monkeypatch.setattr(settings, "execution_mode", "mock")
    providers = get_web_providers()

    serp_results = asyncio.run(
        providers.serp.search_vendor_news("Stable Demo Vendor")
    )
    unlocked_content = asyncio.run(
        providers.web_unlocker.fetch_url(
            "https://example.com/test"
        )
    )
    proxy_content = asyncio.run(
        providers.proxy.fetch_with_proxy(
            "https://example.com/test",
            country="us",
        )
    )
    mcp_results = asyncio.run(
        providers.mcp.search("Stable Demo Vendor risk")
    )

    assert all(result["is_mock"] for result in serp_results)
    assert "[MOCK WEB UNLOCKER CONTENT]" in unlocked_content
    assert "[MOCK PROXY CONTENT]" in proxy_content
    assert mcp_results[0]["is_mock"] is True
