import asyncio

import core.brightdata as brightdata
from core.brightdata import (
    BrightDataProxyClient,
    BrightDataWebUnlocker,
)


def test_web_unlocker_uses_configured_zone(
    monkeypatch,
) -> None:
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "<html><body>Unlocked page</body></html>"

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            traceback,
        ) -> None:
            return None

        async def post(
            self,
            url,
            headers,
            json,
        ):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_web_unlocker_zone",
        "sentinel_unlocker",
    )
    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_web_unlocker_url",
        "https://api.brightdata.com/request",
    )
    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    client = BrightDataWebUnlocker()
    client.api_key = "test-only-api-key"

    result = asyncio.run(
        client.fetch_url(
            "https://example.com/risk-report",
            render_js=False,
        )
    )

    assert result == "<html><body>Unlocked page</body></html>"
    assert captured["url"] == (
        "https://api.brightdata.com/request"
    )
    assert captured["payload"] == {
        "zone": "sentinel_unlocker",
        "url": "https://example.com/risk-report",
        "format": "raw",
    }
    assert captured["headers"]["Authorization"] == (
        "Bearer test-only-api-key"
    )
    assert captured["timeout"] == 45


def test_web_unlocker_does_not_call_network_without_key(
    monkeypatch,
) -> None:
    class ForbiddenAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError(
                "Network client must not be created without an API key."
            )

    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        ForbiddenAsyncClient,
    )

    client = BrightDataWebUnlocker()
    client.api_key = ""

    result = asyncio.run(
        client.fetch_url("https://example.com")
    )

    assert result is None


def test_proxy_builds_expected_connection(
    monkeypatch,
) -> None:
    captured = {}

    class FakeResponse:
        status_code = 200
        text = '{"ip": "203.0.113.10"}'

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(
            self,
            proxies,
            timeout: int,
        ) -> None:
            captured["proxies"] = proxies
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            traceback,
        ) -> None:
            return None

        async def get(self, url):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_proxy_user",
        "test-proxy-user",
    )
    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_proxy_pass",
        "test-proxy-password",
    )
    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_proxy_host",
        "brd.superproxy.io",
    )
    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_proxy_port",
        33335,
    )
    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    client = BrightDataProxyClient()

    result = asyncio.run(
        client.fetch_with_proxy(
            "https://geo.brdtest.com/welcome.txt"
        )
    )

    expected_proxy = (
        "http://test-proxy-user:test-proxy-password"
        "@brd.superproxy.io:33335"
    )

    assert result == '{"ip": "203.0.113.10"}'
    assert captured["proxies"] == {
        "http://": expected_proxy,
        "https://": expected_proxy,
    }
    assert captured["url"] == (
        "https://geo.brdtest.com/welcome.txt"
    )
    assert captured["timeout"] == 30


def test_proxy_does_not_call_network_without_credentials(
    monkeypatch,
) -> None:
    class ForbiddenAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError(
                "Network client must not be created "
                "without proxy credentials."
            )

    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_proxy_user",
        "",
    )
    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_proxy_pass",
        "",
    )
    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        ForbiddenAsyncClient,
    )

    client = BrightDataProxyClient()

    result = asyncio.run(
        client.fetch_with_proxy("https://example.com")
    )

    assert result is None
