"""Offline tests for Bright Data Web Unlocker response validation."""

import asyncio
from types import SimpleNamespace

import core.brightdata as brightdata_module
from core.brightdata import BrightDataWebUnlocker


def _configure_test_client(
    monkeypatch,
    response_body: str,
) -> BrightDataWebUnlocker:
    """Create a Web Unlocker client with a fully mocked HTTP response."""

    class FakeResponse:
        status_code = 200
        text = response_body

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(
            self,
            timeout,
        ) -> None:
            assert timeout == (
                brightdata_module
                .WEB_UNLOCKER_TIMEOUT_SECONDS
            )

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
            assert url == "https://example.invalid/request"
            assert headers["Authorization"] == "Bearer controlled-key"
            assert json["zone"] == "controlled-zone"
            assert json["url"] == "https://example.com"
            return FakeResponse()

    monkeypatch.setattr(
        brightdata_module,
        "settings",
        SimpleNamespace(
            bright_data_api_key="controlled-key",
            bright_data_web_unlocker_url=(
                "https://example.invalid/request"
            ),
            bright_data_web_unlocker_zone="controlled-zone",
        ),
    )
    monkeypatch.setattr(
        brightdata_module.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    return BrightDataWebUnlocker()


def test_web_unlocker_rejects_bright_data_error_body(
    monkeypatch,
) -> None:
    """A 200 response containing a Bright Data error is not evidence."""
    client = _configure_test_client(
        monkeypatch,
        (
            "Request Failed (bad_endpoint): Requested site is not "
            "available for immediate access mode in accordance with "
            "robots.txt."
        ),
    )

    result = asyncio.run(
        client.fetch_url(
            "https://example.com",
            render_js=False,
        )
    )

    assert result is None


def test_web_unlocker_returns_valid_page_content(
    monkeypatch,
) -> None:
    """A normal successful page body must remain available."""
    client = _configure_test_client(
        monkeypatch,
        "<html><body>Controlled public evidence</body></html>",
    )

    result = asyncio.run(
        client.fetch_url(
            "https://example.com",
            render_js=False,
        )
    )

    assert result == (
        "<html><body>Controlled public evidence</body></html>"
    )
