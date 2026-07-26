"""
Sentinel Web-Risk — Bright Data Remote MCP Client.

Provides a genuine Model Context Protocol connection to Bright Data's
managed Streamable HTTP MCP server.
"""

import ast
import json
import re
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from core.config import settings


SearchResult = dict[str, str]

MAX_MCP_SEARCH_RESULTS = 20
MAX_MCP_TEXT_PARSE_CHARACTERS = 100_000


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
        """Close the MCP session and all transport resources."""
        exit_stack = self._exit_stack

        self._exit_stack = None
        self._session = None

        if exit_stack is not None:
            await exit_stack.aclose()

    def _require_session(self) -> ClientSession:
        """Return the active session or raise a clear lifecycle error."""
        if self._session is None:
            raise RuntimeError(
                "Bright Data Remote MCP is not connected. "
                "Call connect() or use 'async with' first."
            )

        return self._session

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return serializable metadata for tools exposed to Sentinel."""
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

        content_blocks = getattr(result, "content", None) or []

        for content_block in content_blocks:
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

            content_type = str(
                getattr(content_block, "type", "")
            ).strip()

            content_text = getattr(
                content_block,
                "text",
                None,
            )

            if content_type == "text" and content_text:
                text_parts.append(str(content_text))

        structured_content = getattr(
            result,
            "structuredContent",
            None,
        )

        if structured_content is None:
            structured_content = getattr(
                result,
                "structured_content",
                None,
            )

        is_error = getattr(
            result,
            "isError",
            None,
        )

        if is_error is None:
            is_error = getattr(
                result,
                "is_error",
                False,
            )

        return {
            "tool": normalized_tool_name,
            "is_error": bool(is_error),
            "text": "\n".join(text_parts),
            "content": serialized_content,
            "structured_content": structured_content,
        }

    async def _call_tool_once(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute one MCP tool with automatic session management.

        An existing session is reused. Otherwise, one temporary session
        is opened and closed automatically.
        """
        opened_here = not self.is_connected

        if opened_here:
            await self.connect()

        try:
            return await self.call_tool(
                tool_name,
                arguments,
            )
        finally:
            if opened_here:
                await self.close()

    @staticmethod
    def _extract_search_items(
        payload: Any,
    ) -> list[dict[str, Any]]:
        """Extract result dictionaries from common MCP response shapes."""
        if isinstance(payload, list):
            return [
                item
                for item in payload
                if isinstance(item, dict)
            ]

        if not isinstance(payload, dict):
            return []

        common_result_keys = (
            "results",
            "organic",
            "organic_results",
            "items",
            "data",
            "entries",
        )

        for key in common_result_keys:
            nested_items = (
                BrightDataRemoteMCPClient
                ._extract_search_items(
                    payload.get(key)
                )
            )

            if nested_items:
                return nested_items

        if any(
            key in payload
            for key in (
                "url",
                "link",
                "title",
                "name",
            )
        ):
            return [payload]

        return []

    @staticmethod
    def _strip_code_fences(
        text: str,
    ) -> str:
        """Remove common Markdown code fences from serialized output."""
        normalized_text = text.strip()

        if normalized_text.startswith("```"):
            normalized_text = re.sub(
                r"^```(?:json|JSON|python|Python)?\\s*",
                "",
                normalized_text,
            )
            normalized_text = re.sub(
                r"\\s*```$",
                "",
                normalized_text,
            )

        return normalized_text.strip()

    @staticmethod
    def _extract_balanced_mapping(
        text: str,
    ) -> Optional[str]:
        """
        Extract the first balanced dictionary literal from wrapped MCP text.

        The scanner respects quoted strings and escape sequences, preventing
        braces inside titles, descriptions, or URLs from ending the mapping
        prematurely.
        """
        start = text.find("{")

        if start < 0:
            return None

        depth = 0
        quote_character: Optional[str] = None
        escaped = False

        for index in range(start, len(text)):
            character = text[index]

            if quote_character is not None:
                if escaped:
                    escaped = False
                    continue

                if character == "\\":
                    escaped = True
                    continue

                if character == quote_character:
                    quote_character = None

                continue

            if character in {"'", '"'}:
                quote_character = character
                continue

            if character == "{":
                depth += 1
                continue

            if character == "}":
                depth -= 1

                if depth == 0:
                    return text[start:index + 1]

                if depth < 0:
                    return None

        return None

    @classmethod
    def _parse_json_text(
        cls,
        text: str,
    ) -> Any:
        """
        Parse JSON or a safe Python literal from wrapped MCP search output.

        Bright Data may wrap search data in an untrusted-content notice and
        serialize the payload with single quotes. ``ast.literal_eval`` accepts
        only Python literals and never executes functions or instructions.
        """
        normalized_text = cls._strip_code_fences(
            text
        )

        if not normalized_text:
            return None

        if (
            len(normalized_text)
            > MAX_MCP_TEXT_PARSE_CHARACTERS
        ):
            return None

        candidates = [
            normalized_text,
        ]

        extracted_mapping = cls._extract_balanced_mapping(
            normalized_text
        )

        if (
            extracted_mapping
            and extracted_mapping != normalized_text
        ):
            candidates.append(
                extracted_mapping
            )

        for candidate in candidates:
            try:
                parsed_json = json.loads(
                    candidate
                )
            except json.JSONDecodeError:
                parsed_json = None

            if isinstance(
                parsed_json,
                (dict, list),
            ):
                return parsed_json

            try:
                parsed_literal = ast.literal_eval(
                    candidate
                )
            except (
                SyntaxError,
                ValueError,
                TypeError,
                MemoryError,
                RecursionError,
            ):
                parsed_literal = None

            if isinstance(
                parsed_literal,
                (dict, list),
            ):
                return parsed_literal

        return None

    @staticmethod
    def _clean_text(value: Any) -> str:
        """Convert an arbitrary value into normalized text."""
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        return str(value).strip()

    @classmethod
    def _normalize_search_results(
        cls,
        result: dict[str, Any],
    ) -> list[SearchResult]:
        """Convert MCP search output into Sentinel search-result records."""
        payload = result.get("structured_content")
        items = cls._extract_search_items(payload)

        text = cls._clean_text(
            result.get("text")
        )

        if not items and text:
            parsed_text = cls._parse_json_text(text)
            items = cls._extract_search_items(parsed_text)

        normalized: list[SearchResult] = []
        seen_urls: set[str] = set()

        for item in items:
            title = cls._clean_text(
                item.get("title")
                or item.get("name")
                or item.get("headline")
            )

            url = cls._clean_text(
                item.get("url")
                or item.get("link")
                or item.get("href")
            )

            snippet = cls._clean_text(
                item.get("snippet")
                or item.get("description")
                or item.get("summary")
                or item.get("text")
            )

            if not url.startswith(
                ("http://", "https://")
            ):
                continue

            if url in seen_urls:
                continue

            normalized.append(
                {
                    "title": title or url,
                    "url": url,
                    "snippet": snippet,
                    "source": "bright_data_remote_mcp",
                }
            )

            seen_urls.add(url)

        if not normalized and text:
            markdown_links = re.findall(
                r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                text,
            )

            for title, url in markdown_links:
                normalized_url = url.strip()

                if normalized_url in seen_urls:
                    continue

                normalized.append(
                    {
                        "title": title.strip() or normalized_url,
                        "url": normalized_url,
                        "snippet": "",
                        "source": "bright_data_remote_mcp",
                    }
                )

                seen_urls.add(normalized_url)

        return normalized

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Perform a genuine Bright Data MCP search.

        Results are normalized into Sentinel's title, URL, snippet,
        and source structure.
        """
        normalized_query = query.strip()

        if not normalized_query or limit <= 0:
            return []

        result = await self._call_tool_once(
            "search_engine",
            {
                "query": normalized_query,
            },
        )

        if result.get("is_error"):
            return []

        results = self._normalize_search_results(
            result
        )

        result_limit = min(
            limit,
            MAX_MCP_SEARCH_RESULTS,
        )

        return results[:result_limit]

    async def scrape(
        self,
        url: str,
    ) -> Optional[str]:
        """
        Scrape one public page through genuine MCP scrape_as_markdown.

        Returns clean Markdown text when successful.
        """
        normalized_url = url.strip()

        if not normalized_url:
            return None

        if not normalized_url.startswith(
            ("http://", "https://")
        ):
            raise ValueError(
                "MCP scraper URL must start with http:// or https://."
            )

        result = await self._call_tool_once(
            "scrape_as_markdown",
            {
                "url": normalized_url,
            },
        )

        if result.get("is_error"):
            return None

        markdown = self._clean_text(
            result.get("text")
        )

        if markdown:
            return markdown

        structured_content = result.get(
            "structured_content"
        )

        if structured_content is not None:
            return json.dumps(
                structured_content,
                ensure_ascii=False,
                default=str,
            )

        return None


remote_mcp_client = BrightDataRemoteMCPClient()
