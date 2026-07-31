"""Offline tests for the genuine Bright Data Remote MCP client."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import core.brightdata_remote_mcp as remote_mcp_module
from core.brightdata_remote_mcp import BrightDataRemoteMCPClient


TEST_MCP_ENDPOINT = "https://example.invalid/mcp?token=hidden"


def _mock_mcp_settings(monkeypatch) -> None:
    """
    Replace the module-level Pydantic settings object with a safe test double.

    Pydantic settings methods cannot be monkeypatched directly on the model
    instance because they are not model fields.
    """
    monkeypatch.setattr(
        remote_mcp_module,
        "settings",
        SimpleNamespace(
            build_bright_data_mcp_url=lambda: TEST_MCP_ENDPOINT,
        ),
    )


def test_connect_initializes_and_closes_mcp_session(
    monkeypatch,
) -> None:
    """The client must initialize and cleanly close MCP resources."""
    events: list[str] = []

    @asynccontextmanager
    async def fake_streamable_http_client(endpoint):
        events.append("transport_opened")
        assert endpoint == TEST_MCP_ENDPOINT

        yield (
            "fake-read-stream",
            "fake-write-stream",
            None,
        )

        events.append("transport_closed")

    class FakeClientSession:
        def __init__(
            self,
            read_stream,
            write_stream,
        ) -> None:
            assert read_stream == "fake-read-stream"
            assert write_stream == "fake-write-stream"
            events.append("session_created")

        async def __aenter__(self):
            events.append("session_opened")
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            traceback,
        ) -> None:
            events.append("session_closed")

        async def initialize(self) -> None:
            events.append("session_initialized")

    _mock_mcp_settings(monkeypatch)

    monkeypatch.setattr(
        remote_mcp_module,
        "streamable_http_client",
        fake_streamable_http_client,
    )
    monkeypatch.setattr(
        remote_mcp_module,
        "ClientSession",
        FakeClientSession,
    )

    client = BrightDataRemoteMCPClient()

    async def exercise_client() -> None:
        assert client.is_connected is False

        await client.connect()
        assert client.is_connected is True

        await client.close()
        assert client.is_connected is False

    asyncio.run(exercise_client())

    assert events == [
        "transport_opened",
        "session_created",
        "session_opened",
        "session_initialized",
        "session_closed",
        "transport_closed",
    ]


def test_connect_is_idempotent(
    monkeypatch,
) -> None:
    """Repeated connect calls must not create duplicate MCP sessions."""
    connection_count = 0
    initialization_count = 0

    @asynccontextmanager
    async def fake_streamable_http_client(endpoint):
        nonlocal connection_count

        assert endpoint == TEST_MCP_ENDPOINT
        connection_count += 1

        yield (
            "read-stream",
            "write-stream",
            None,
        )

    class FakeClientSession:
        def __init__(
            self,
            read_stream,
            write_stream,
        ) -> None:
            assert read_stream == "read-stream"
            assert write_stream == "write-stream"

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            traceback,
        ) -> None:
            return None

        async def initialize(self) -> None:
            nonlocal initialization_count
            initialization_count += 1

    _mock_mcp_settings(monkeypatch)

    monkeypatch.setattr(
        remote_mcp_module,
        "streamable_http_client",
        fake_streamable_http_client,
    )
    monkeypatch.setattr(
        remote_mcp_module,
        "ClientSession",
        FakeClientSession,
    )

    client = BrightDataRemoteMCPClient()

    async def exercise_client() -> None:
        await client.connect()
        await client.connect()
        await client.close()

    asyncio.run(exercise_client())

    assert connection_count == 1
    assert initialization_count == 1
    assert client.is_connected is False


def test_close_is_safe_when_not_connected() -> None:
    """Closing an unused client must not raise an exception."""
    client = BrightDataRemoteMCPClient()

    asyncio.run(client.close())

    assert client.is_connected is False


def test_list_tools_returns_serializable_metadata() -> None:
    """MCP tool definitions must be converted into plain dictionaries."""

    class FakeSession:
        async def list_tools(self):
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="search_engine",
                        description="Search the live web",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                }
                            },
                        },
                    ),
                    SimpleNamespace(
                        name="scrape_as_markdown",
                        description=None,
                        inputSchema={
                            "type": "object",
                        },
                    ),
                ]
            )

    client = BrightDataRemoteMCPClient()
    client._session = FakeSession()  # type: ignore[assignment]

    tools = asyncio.run(client.list_tools())

    assert tools == [
        {
            "name": "search_engine",
            "description": "Search the live web",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                    }
                },
            },
        },
        {
            "name": "scrape_as_markdown",
            "description": "",
            "input_schema": {
                "type": "object",
            },
        },
    ]


def test_call_tool_serializes_text_and_structured_content() -> None:
    """MCP tool output must be safely converted into API-ready data."""

    class FakeTextContent:
        type = "text"
        text = "Controlled MCP result"

        def model_dump(
            self,
            mode,
            by_alias,
        ):
            assert mode == "json"
            assert by_alias is True

            return {
                "type": "text",
                "text": self.text,
            }

    class FakeSession:
        async def call_tool(
            self,
            tool_name,
            arguments,
        ):
            assert tool_name == "search_engine"
            assert arguments == {
                "query": "Example Vendor risk"
            }

            return SimpleNamespace(
                content=[
                    FakeTextContent(),
                ],
                isError=False,
                structuredContent={
                    "results": 1,
                },
            )

    client = BrightDataRemoteMCPClient()
    client._session = FakeSession()  # type: ignore[assignment]

    result = asyncio.run(
        client.call_tool(
            " search_engine ",
            {
                "query": "Example Vendor risk",
            },
        )
    )

    assert result == {
        "tool": "search_engine",
        "is_error": False,
        "text": "Controlled MCP result",
        "content": [
            {
                "type": "text",
                "text": "Controlled MCP result",
            }
        ],
        "structured_content": {
            "results": 1,
        },
    }


def test_call_tool_supports_snake_case_response_fields() -> None:
    """The client must support SDK responses using snake_case fields."""

    class FakeSession:
        async def call_tool(
            self,
            tool_name,
            arguments,
        ):
            return SimpleNamespace(
                content=[],
                is_error=True,
                structured_content={
                    "error": "controlled",
                },
            )

    client = BrightDataRemoteMCPClient()
    client._session = FakeSession()  # type: ignore[assignment]

    result = asyncio.run(
        client.call_tool(
            "search_engine",
            {},
        )
    )

    assert result["is_error"] is True
    assert result["structured_content"] == {
        "error": "controlled",
    }


def test_call_tool_rejects_blank_name() -> None:
    """Blank tool names must fail before an MCP request is attempted."""
    client = BrightDataRemoteMCPClient()

    with pytest.raises(
        ValueError,
        match="tool name cannot be empty",
    ):
        asyncio.run(
            client.call_tool("   ")
        )


def test_operations_require_active_connection() -> None:
    """Tool operations must not run before the MCP session connects."""
    client = BrightDataRemoteMCPClient()

    with pytest.raises(
        RuntimeError,
        match="Remote MCP is not connected",
    ):
        asyncio.run(client.list_tools())


def test_call_tool_once_opens_and_closes_temporary_session(
    monkeypatch,
) -> None:
    """One-shot tool calls must manage a temporary MCP session."""
    events: list[str] = []
    client = BrightDataRemoteMCPClient()

    async def fake_connect() -> None:
        events.append("connect")
        client._session = SimpleNamespace()  # type: ignore[assignment]

    async def fake_call_tool(
        tool_name,
        arguments,
    ):
        events.append("call")
        assert tool_name == "search_engine"
        assert arguments == {
            "query": "Example"
        }

        return {
            "is_error": False,
            "text": "result",
            "structured_content": None,
        }

    async def fake_close() -> None:
        events.append("close")
        client._session = None

    monkeypatch.setattr(
        client,
        "connect",
        fake_connect,
    )
    monkeypatch.setattr(
        client,
        "call_tool",
        fake_call_tool,
    )
    monkeypatch.setattr(
        client,
        "close",
        fake_close,
    )

    result = asyncio.run(
        client._call_tool_once(
            "search_engine",
            {
                "query": "Example",
            },
        )
    )

    assert result["text"] == "result"
    assert events == [
        "connect",
        "call",
        "close",
    ]


def test_call_tool_once_reuses_existing_session(
    monkeypatch,
) -> None:
    """An existing MCP session must not be opened or closed again."""
    events: list[str] = []
    client = BrightDataRemoteMCPClient()
    client._session = SimpleNamespace()  # type: ignore[assignment]

    async def forbidden_connect() -> None:
        raise AssertionError(
            "connect() must not run for an active session."
        )

    async def fake_call_tool(
        tool_name,
        arguments,
    ):
        events.append("call")
        return {
            "is_error": False,
            "text": "reused",
            "structured_content": None,
        }

    async def forbidden_close() -> None:
        raise AssertionError(
            "close() must not run for a reused session."
        )

    monkeypatch.setattr(
        client,
        "connect",
        forbidden_connect,
    )
    monkeypatch.setattr(
        client,
        "call_tool",
        fake_call_tool,
    )
    monkeypatch.setattr(
        client,
        "close",
        forbidden_close,
    )

    result = asyncio.run(
        client._call_tool_once(
            "search_engine",
            {
                "query": "Example",
            },
        )
    )

    assert result["text"] == "reused"
    assert events == ["call"]


def test_search_normalizes_json_text_results(
    monkeypatch,
) -> None:
    """JSON MCP search output must match Sentinel's result format."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        assert tool_name == "search_engine"
        assert arguments == {
            "query": "Example Vendor risk"
        }

        return {
            "is_error": False,
            "text": json.dumps(
                {
                    "results": [
                        {
                            "title": "Example Report",
                            "url": "https://example.com/report",
                            "description": (
                                "Verified vendor intelligence"
                            ),
                        }
                    ]
                }
            ),
            "structured_content": None,
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    results = asyncio.run(
        client.search(
            "Example Vendor risk",
        )
    )

    assert results == [
        {
            "title": "Example Report",
            "url": "https://example.com/report",
            "snippet": "Verified vendor intelligence",
            "source": "bright_data_remote_mcp",
        }
    ]


def test_search_normalizes_structured_results_and_removes_duplicates(
    monkeypatch,
) -> None:
    """Structured MCP results must be normalized and de-duplicated."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        return {
            "is_error": False,
            "text": "",
            "structured_content": {
                "organic_results": [
                    {
                        "name": "First result",
                        "link": "https://example.com/one",
                        "summary": "First summary",
                    },
                    {
                        "title": "Duplicate result",
                        "url": "https://example.com/one",
                        "snippet": "Duplicate summary",
                    },
                    {
                        "title": "Second result",
                        "url": "https://example.com/two",
                        "snippet": "Second summary",
                    },
                    {
                        "title": "Invalid result",
                        "url": "ftp://example.com/invalid",
                    },
                ]
            },
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    results = asyncio.run(
        client.search(
            "Example",
            limit=10,
        )
    )

    assert results == [
        {
            "title": "First result",
            "url": "https://example.com/one",
            "snippet": "First summary",
            "source": "bright_data_remote_mcp",
        },
        {
            "title": "Second result",
            "url": "https://example.com/two",
            "snippet": "Second summary",
            "source": "bright_data_remote_mcp",
        },
    ]


def test_search_parses_markdown_links(
    monkeypatch,
) -> None:
    """Markdown MCP search output must be converted into results."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        return {
            "is_error": False,
            "text": (
                "[Example One](https://example.com/one)\n"
                "[Example Two](https://example.com/two)"
            ),
            "structured_content": None,
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    results = asyncio.run(
        client.search(
            "Example",
        )
    )

    assert [result["url"] for result in results] == [
        "https://example.com/one",
        "https://example.com/two",
    ]


def test_search_stops_for_blank_query_or_non_positive_limit(
    monkeypatch,
) -> None:
    """Invalid local search input must stop before an MCP tool call."""
    client = BrightDataRemoteMCPClient()

    async def forbidden_call(*args, **kwargs):
        raise AssertionError(
            "MCP must not be called for invalid search input."
        )

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        forbidden_call,
    )

    assert asyncio.run(
        client.search("   ")
    ) == []

    assert asyncio.run(
        client.search(
            "Example",
            limit=0,
        )
    ) == []


def test_search_returns_empty_for_remote_error(
    monkeypatch,
) -> None:
    """Remote MCP search errors must return an empty result list."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        return {
            "is_error": True,
            "text": "controlled error",
            "structured_content": None,
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    assert asyncio.run(
        client.search("Example")
    ) == []


def test_scrape_returns_remote_mcp_markdown(
    monkeypatch,
) -> None:
    """The MCP scraper wrapper must return Markdown text."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        assert tool_name == "scrape_as_markdown"
        assert arguments == {
            "url": "https://example.com"
        }

        return {
            "is_error": False,
            "text": "# Example Domain",
            "structured_content": None,
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    result = asyncio.run(
        client.scrape(
            "https://example.com"
        )
    )

    assert result == "# Example Domain"


def test_scrape_serializes_structured_content_when_text_is_empty(
    monkeypatch,
) -> None:
    """Structured scraper output must be retained as JSON fallback."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        return {
            "is_error": False,
            "text": "",
            "structured_content": {
                "title": "Example Domain",
            },
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    result = asyncio.run(
        client.scrape(
            "https://example.com"
        )
    )

    assert json.loads(result) == {
        "title": "Example Domain",
    }


def test_scrape_validates_input_before_remote_call(
    monkeypatch,
) -> None:
    """Blank and unsupported scraper URLs must stop locally."""
    client = BrightDataRemoteMCPClient()

    async def forbidden_call(*args, **kwargs):
        raise AssertionError(
            "MCP must not run for invalid scraper input."
        )

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        forbidden_call,
    )

    assert asyncio.run(
        client.scrape("   ")
    ) is None

    with pytest.raises(
        ValueError,
        match="must start with http:// or https://",
    ):
        asyncio.run(
            client.scrape(
                "ftp://example.com"
            )
        )


def test_scrape_returns_none_for_remote_error(
    monkeypatch,
) -> None:
    """Remote MCP scraper errors must return None."""
    client = BrightDataRemoteMCPClient()

    async def fake_call_tool_once(
        tool_name,
        arguments,
    ):
        return {
            "is_error": True,
            "text": "",
            "structured_content": None,
        }

    monkeypatch.setattr(
        client,
        "_call_tool_once",
        fake_call_tool_once,
    )

    assert asyncio.run(
        client.scrape(
            "https://example.com"
        )
    ) is None
