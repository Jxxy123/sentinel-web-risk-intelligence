"""Offline tests for the genuine Bright Data Remote MCP client."""

import asyncio
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
