"""
Sentinel Web-Risk — Bright Data Remote MCP Client.

Provides a genuine Model Context Protocol connection to Bright Data's
managed Streamable HTTP MCP server.
"""

from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from core.config import settings


class BrightDataRemoteMCPClient:
    """
    Genuine Bright Data Remote MCP client.

    The client manages the MCP transport and session lifecycle without
    exposing or logging the authenticated endpoint.
    """

    def __init__(self) -> None:
        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None

    @property
    def is_connected(self) -> bool:
        """Return True when an initialized MCP session is available."""
        return self._session is not None

    async def __aenter__(
        self,
    ) -> "BrightDataRemoteMCPClient":
        """Connect when entering an async context."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        """Close all MCP resources when leaving the context."""
        await self.close()

    async def connect(self) -> None:
        """
        Open and initialize the Bright Data Remote MCP session.

        Repeated calls are safe and do not create duplicate sessions.
        """
        if self.is_connected:
            return

        endpoint = settings.build_bright_data_mcp_url()
        exit_stack = AsyncExitStack()

        try:
            transport = await exit_stack.enter_async_context(
                streamable_http_client(endpoint)
            )

            read_stream, write_stream, _ = transport

            session = await exit_stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                )
            )

            await session.initialize()

        except Exception:
            await exit_stack.aclose()
            raise

        self._exit_stack = exit_stack
        self._session = session

    async def close(self) -> None:
        """Close the MCP session and its transport resources."""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()

        self._exit_stack = None
        self._session = None

    def _require_session(self) -> ClientSession:
        """Return the active session or raise a clear lifecycle error."""
        if self._session is None:
            raise RuntimeError(
                "Bright Data Remote MCP is not connected. "
                "Call connect() or use 'async with' first."
            )

        return self._session

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the MCP tools exposed to Sentinel."""
        session = self._require_session()
        response = await session.list_tools()

        tools: list[dict[str, Any]] = []

        for tool in response.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                }
            )

        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Call one Bright Data MCP tool and return a serializable result.

        No tool is called when the supplied name is blank.
        """
        normalized_tool_name = tool_name.strip()

        if not normalized_tool_name:
            raise ValueError("MCP tool name cannot be empty.")

        session = self._require_session()

        result = await session.call_tool(
            normalized_tool_name,
            arguments=arguments or {},
        )

        serialized_content: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for content_block in result.content:
            if hasattr(content_block, "model_dump"):
                serialized_block = content_block.model_dump(
                    mode="json",
                    by_alias=True,
                )
            else:
                serialized_block = {
                    "type": getattr(
                        content_block,
                        "type",
                        "unknown",
                    ),
                    "text": getattr(
                        content_block,
                        "text",
                        None,
                    ),
                }

            serialized_content.append(serialized_block)

            if (
                getattr(content_block, "type", None) == "text"
                and getattr(content_block, "text", None)
            ):
                text_parts.append(content_block.text)

        return {
            "tool": normalized_tool_name,
            "is_error": bool(
                getattr(result, "isError", False)
            ),
            "text": "\n".join(text_parts),
            "content": serialized_content,
            "structured_content": getattr(
                result,
                "structuredContent",
                None,
            ),
        }


remote_mcp_client = BrightDataRemoteMCPClient()
