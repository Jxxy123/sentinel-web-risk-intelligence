"""Offline tests for Bright Data Remote MCP configuration."""

from urllib.parse import parse_qs, urlparse

import pytest

from core.config import settings


def test_mcp_url_contains_expected_configuration(
    monkeypatch,
) -> None:
    """The generated MCP URL must contain the expected safe parameters."""
    monkeypatch.setattr(
        settings,
        "bright_data_api_key",
        "test-only-api-token",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_base_url",
        "https://mcp.brightdata.com/mcp",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_tools",
        (
            "search_engine,"
            "scrape_as_markdown,"
            "session_stats"
        ),
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_groups",
        "",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_unlocker_zone",
        "sentinel_unlocker",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_pro",
        False,
    )

    generated_url = settings.build_bright_data_mcp_url()
    assert (
        "tools=search_engine,scrape_as_markdown,session_stats"
        in generated_url
    )
    parsed_url = urlparse(generated_url)
    parameters = parse_qs(parsed_url.query)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "mcp.brightdata.com"
    assert parsed_url.path == "/mcp"

    assert parameters["token"] == [
        "test-only-api-token"
    ]
    assert parameters["tools"] == [
        "search_engine,scrape_as_markdown,session_stats"
    ]
    assert parameters["unlocker"] == [
        "sentinel_unlocker"
    ]
    assert "groups" not in parameters
    assert "pro" not in parameters


def test_mcp_tool_names_are_normalized(
    monkeypatch,
) -> None:
    """Duplicate and empty MCP tool values must be removed."""
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_tools",
        (
            " search_engine, "
            "scrape_as_markdown, "
            "search_engine, ,"
            "session_stats "
        ),
    )

    assert settings.bright_data_mcp_tool_list == [
        "search_engine",
        "scrape_as_markdown",
        "session_stats",
    ]


def test_mcp_group_names_are_normalized(
    monkeypatch,
) -> None:
    """Duplicate and empty MCP groups must be removed."""
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_groups",
        " research, business, research, ",
    )

    assert settings.bright_data_mcp_group_list == [
        "research",
        "business",
    ]


def test_mcp_url_requires_api_key(
    monkeypatch,
) -> None:
    """Missing API authentication must stop URL generation."""
    monkeypatch.setattr(
        settings,
        "bright_data_api_key",
        "",
    )

    with pytest.raises(
        ValueError,
        match="BRIGHT_DATA_API_KEY",
    ):
        settings.build_bright_data_mcp_url()


def test_mcp_url_requires_base_url(
    monkeypatch,
) -> None:
    """Missing MCP endpoint must stop URL generation."""
    monkeypatch.setattr(
        settings,
        "bright_data_api_key",
        "test-only-api-token",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_base_url",
        "",
    )

    with pytest.raises(
        ValueError,
        match="BRIGHT_DATA_MCP_BASE_URL",
    ):
        settings.build_bright_data_mcp_url()


def test_mcp_pro_parameter_is_added_when_enabled(
    monkeypatch,
) -> None:
    """Pro mode must be represented only when explicitly enabled."""
    monkeypatch.setattr(
        settings,
        "bright_data_api_key",
        "test-only-api-token",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_base_url",
        "https://mcp.brightdata.com/mcp",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_tools",
        "",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_groups",
        "",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_unlocker_zone",
        "",
    )
    monkeypatch.setattr(
        settings,
        "bright_data_mcp_pro",
        True,
    )

    parameters = parse_qs(
        urlparse(
            settings.build_bright_data_mcp_url()
        ).query
    )

    assert parameters["pro"] == ["1"]
