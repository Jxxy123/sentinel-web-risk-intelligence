import asyncio

import httpx

import core.brightdata as brightdata
from core.brightdata import BrightDataSERPClient


SAMPLE_SERP_HTML = """
<html>
  <body>
    <div class="g">
      <a href="https://example.com/risk-report">
        <h3>Example Vendor Risk Report</h3>
      </a>
      <div class="VwiC3b">
        Example Vendor announced an operational-risk review.
      </div>
    </div>
  </body>
</html>
"""


def _configured_client() -> BrightDataSERPClient:
    """Create a client with safe test-only credentials."""
    client = BrightDataSERPClient()
    client.api_key = "test-only-key"
    client.headers["Authorization"] = "Bearer test-only-key"
    return client


def test_search_sends_raw_html_request_and_parses_results(
    monkeypatch,
) -> None:
    captured_request = {}

    class FakeResponse:
        status_code = 200
        text = SAMPLE_SERP_HTML

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            captured_request["timeout"] = timeout

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
            captured_request["url"] = url
            captured_request["headers"] = headers
            captured_request["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_serp_zone",
        "sentinel_serp",
    )
    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    client = _configured_client()

    results = asyncio.run(
        client.search(
            "Example Vendor risk",
            num_results=3,
            lang="en",
        )
    )

    assert len(results) == 1
    assert results[0] == {
        "title": "Example Vendor Risk Report",
        "url": "https://example.com/risk-report",
        "snippet": (
            "Example Vendor announced an operational-risk review."
        ),
        "source": "bright_data_serp",
    }

    assert captured_request["url"] == (
        "https://api.brightdata.com/request"
    )
    assert captured_request["payload"]["zone"] == "sentinel_serp"
    assert captured_request["payload"]["format"] == "raw"
    assert captured_request["payload"]["data_format"] == "html"
    assert "num=3" in captured_request["payload"]["url"]
    assert captured_request["timeout"] == 45


def test_search_returns_empty_for_blank_query(
    monkeypatch,
) -> None:
    class ForbiddenAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError(
                "A network client must not be created for blank input."
            )

    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        ForbiddenAsyncClient,
    )

    client = _configured_client()

    assert asyncio.run(client.search("   ")) == []


def test_search_returns_empty_for_non_positive_limit(
    monkeypatch,
) -> None:
    class ForbiddenAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError(
                "A network client must not be created for limit zero."
            )

    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        ForbiddenAsyncClient,
    )

    client = _configured_client()

    assert asyncio.run(
        client.search(
            "Example Vendor",
            num_results=0,
        )
    ) == []


def test_search_handles_http_error(
    monkeypatch,
) -> None:
    request = httpx.Request(
        "POST",
        "https://api.brightdata.com/request",
    )
    error_response = httpx.Response(
        status_code=403,
        request=request,
    )

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

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
            return error_response

    monkeypatch.setattr(
        brightdata.settings,
        "bright_data_serp_zone",
        "sentinel_serp",
    )
    monkeypatch.setattr(
        brightdata.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    client = _configured_client()

    assert asyncio.run(
        client.search("Example Vendor")
    ) == []
