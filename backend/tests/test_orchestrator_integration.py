"""Offline integration tests for the Sentinel orchestration pipeline."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

import agents.orchestrator as orchestrator_module
from agents.orchestrator import SentinelOrchestrator


class FakeSERPClient:
    """Deterministic offline replacement for Bright Data SERP."""

    def __init__(
        self,
        results: list[dict[str, str]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[dict[str, str]] = []

    async def search_vendor_news(
        self,
        vendor_name: str,
        lang: str = "en",
    ) -> list[dict[str, str]]:
        self.calls.append(
            {
                "vendor_name": vendor_name,
                "lang": lang,
            }
        )

        if self.error is not None:
            raise self.error

        return list(self.results)


class FakeWebUnlocker:
    """Deterministic offline replacement for Web Unlocker."""

    def __init__(
        self,
        content: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.calls: list[str] = []

    async def fetch_legal_filing(
        self,
        vendor_name: str,
    ) -> str | None:
        self.calls.append(vendor_name)

        if self.error is not None:
            raise self.error

        return self.content


class FakeRemoteMCPClient:
    """Deterministic offline replacement for genuine Remote MCP."""

    def __init__(
        self,
        search_results: list[dict[str, str]] | None = None,
        scrape_content: str | None = None,
        search_error: Exception | None = None,
        scrape_error: Exception | None = None,
    ) -> None:
        self.search_results = search_results or []
        self.scrape_content = scrape_content
        self.search_error = search_error
        self.scrape_error = scrape_error
        self.search_calls: list[dict[str, Any]] = []
        self.scrape_calls: list[str] = []

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        self.search_calls.append(
            {
                "query": query,
                "limit": limit,
            }
        )

        if self.search_error is not None:
            raise self.search_error

        return list(self.search_results)

    async def scrape(
        self,
        url: str,
    ) -> str | None:
        self.scrape_calls.append(url)

        if self.scrape_error is not None:
            raise self.scrape_error

        return self.scrape_content


class FakeProxyClient:
    """Deterministic offline replacement for the proxy network."""

    def __init__(
        self,
        content: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.calls: list[dict[str, str]] = []

    async def fetch_with_fallback(
        self,
        url: str,
        country: str = "us",
    ) -> str | None:
        self.calls.append(
            {
                "url": url,
                "country": country,
            }
        )

        if self.error is not None:
            raise self.error

        return self.content


def _patch_offline_ai_pipeline(
    monkeypatch,
    crew_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Replace CrewAI construction and deterministic scoring with test doubles.

    The returned dictionary captures the data passed into build_tasks and Crew.
    """
    captured: dict[str, Any] = {}

    for builder_name in (
        "build_recon_agent",
        "build_scraping_agent",
        "build_verification_agent",
        "build_intelligence_agent",
        "build_prediction_agent",
        "build_reporting_agent",
    ):
        monkeypatch.setattr(
            orchestrator_module,
            builder_name,
            lambda llm, name=builder_name: SimpleNamespace(
                role=name,
            ),
        )

    def fake_build_tasks(
        vendor_name,
        search_results,
        scraped_content,
        agents,
        language="EN",
        pre_score=5,
        pre_level="LOW",
        tools_used=None,
    ):
        captured["task_input"] = {
            "vendor_name": vendor_name,
            "search_results": list(search_results),
            "scraped_content": scraped_content,
            "agents": dict(agents),
            "language": language,
            "pre_score": pre_score,
            "pre_level": pre_level,
            "tools_used": list(tools_used or []),
        }

        return [
            SimpleNamespace(name=f"task-{index}")
            for index in range(6)
        ]

    monkeypatch.setattr(
        orchestrator_module,
        "build_tasks",
        fake_build_tasks,
    )

    output = crew_report or {
        "executive_summary": (
            "Example Vendor provides enterprise software services. "
            "Verified evidence indicates a stable point-in-time profile "
            "with limited operational concerns and no confirmed severe event."
        ),
        "risk_headline": (
            "Example Vendor currently presents a moderate, evidence-limited "
            "operational risk profile."
        ),
        "primary_risk_category": "Operational",
        "key_findings": [
            "A verified operational update was identified.",
            "No corroborated critical disruption was found.",
        ],
        "risk_trajectory": "Stable",
        "recommended_actions": [
            "Review the cited evidence.",
            "Request current compliance documentation.",
        ],
        "monitoring_signals": [
            "Regulatory changes",
            "Service disruption notices",
        ],
        "time_horizon": "Near-term",
    }

    class FakeCrew:
        def __init__(
            self,
            agents,
            tasks,
            process,
            max_rpm,
            verbose,
        ) -> None:
            captured["crew"] = {
                "agents": list(agents),
                "tasks": list(tasks),
                "process": process,
                "max_rpm": max_rpm,
                "verbose": verbose,
            }

        def kickoff(self) -> str:
            captured["kickoff_count"] = (
                captured.get("kickoff_count", 0) + 1
            )
            return json.dumps(output)

    monkeypatch.setattr(
        orchestrator_module,
        "Crew",
        FakeCrew,
    )

    deterministic_signals = [
        {
            "category": "Operational",
            "severity": "MEDIUM",
            "signal": "Controlled test signal",
        }
    ]

    monkeypatch.setattr(
        orchestrator_module,
        "analyze_text_for_signals",
        lambda text: list(deterministic_signals),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "calculate_risk_score",
        lambda signals: (
            25,
            "MEDIUM",
            0.82,
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "calculate_disruption_probability",
        lambda score, signals: 0.20,
    )
    monkeypatch.setattr(
        orchestrator_module,
        "format_signals_for_report",
        lambda signals: list(signals),
    )

    return captured


def test_complete_offline_pipeline_merges_sources_and_reports_tools(
    monkeypatch,
) -> None:
    """
    The full orchestrator must merge live-source shapes without real requests.
    """
    captured = _patch_offline_ai_pipeline(
        monkeypatch
    )
    progress_events: list[dict[str, Any]] = []

    async def progress_callback(
        payload: dict[str, Any],
    ) -> None:
        progress_events.append(payload)

    serp = FakeSERPClient(
        results=[
            {
                "title": "SERP risk report",
                "url": "https://example.com/risk",
                "snippet": "Operational update",
                "source": "bright_data_serp",
            }
        ]
    )
    mcp = FakeRemoteMCPClient(
        search_results=[
            {
                "title": "Duplicate MCP report",
                "url": "https://example.com/risk",
                "snippet": "Duplicate evidence",
                "source": "bright_data_remote_mcp",
            },
            {
                "title": "MCP legal report",
                "url": "https://example.com/legal",
                "snippet": "Legal filing update",
                "source": "bright_data_remote_mcp",
            },
        ]
    )
    unlocker = FakeWebUnlocker(
        content="<html>Public filing context</html>"
    )
    proxy = FakeProxyClient(
        content="Regional company context"
    )

    orchestrator = SentinelOrchestrator(
        progress_callback=progress_callback,
        llm=object(),  # type: ignore[arg-type]
        serp=serp,
        unlocker=unlocker,
        mcp=mcp,
        proxy=proxy,
    )

    report = asyncio.run(
        orchestrator.investigate_vendor(
            "  Example   Vendor  ",
            language=" en ",
        )
    )

    assert report["status"] == "completed"
    assert report["vendor_name"] == "Example Vendor"
    assert report["risk_score"] == 25
    assert report["risk_level"] == "MEDIUM"
    assert report["confidence_score"] == 0.82
    assert report["disruption_probability"] == 0.20

    assert report["raw_intelligence"][
        "search_results_count"
    ] == 2
    assert report["raw_intelligence"][
        "mcp_unique_results_added"
    ] == 1
    assert report["raw_intelligence"][
        "bright_data_tools_used"
    ] == [
        "SERP API",
        "Remote MCP search_engine",
        "Web Unlocker",
        "Proxy Network",
    ]

    assert [
        source["url"]
        for source in report["sources"]
    ] == [
        "https://example.com/risk",
        "https://example.com/legal",
    ]

    assert serp.calls == [
        {
            "vendor_name": "Example Vendor",
            "lang": "en",
        }
    ]
    assert len(mcp.search_calls) == 1
    assert mcp.search_calls[0]["limit"] == 10
    assert '"Example Vendor"' in mcp.search_calls[0][
        "query"
    ]
    assert mcp.scrape_calls == []
    assert unlocker.calls == [
        "Example Vendor"
    ]
    assert proxy.calls == [
        {
            "url": (
                "https://en.wikipedia.org/wiki/"
                "Example_Vendor"
            ),
            "country": "us",
        }
    ]

    assert captured["task_input"]["vendor_name"] == (
        "Example Vendor"
    )
    assert captured["task_input"]["language"] == "EN"
    assert captured["task_input"]["tools_used"] == [
        "SERP API",
        "Remote MCP search_engine",
        "Web Unlocker",
        "Proxy Network",
    ]
    assert captured["kickoff_count"] == 1

    assert [
        event["stage"]
        for event in progress_events
    ] == [
        "recon",
        "recon",
        "scraping",
        "analysis",
        "agents",
        "scoring",
        "reporting",
        "complete",
    ]
    assert progress_events[-1]["progress"] == 100


def test_mcp_scraper_is_used_only_when_unlocker_returns_no_content(
    monkeypatch,
) -> None:
    """MCP scraping must act as a fallback, not a duplicate scraper call."""
    captured = _patch_offline_ai_pipeline(
        monkeypatch
    )

    serp = FakeSERPClient(
        results=[
            {
                "title": "Primary evidence",
                "url": "https://example.com/evidence",
                "snippet": "Controlled evidence",
            }
        ]
    )
    mcp = FakeRemoteMCPClient(
        search_results=[],
        scrape_content="# Controlled MCP evidence",
    )
    unlocker = FakeWebUnlocker(
        content=None
    )
    proxy = FakeProxyClient(
        content=None
    )

    orchestrator = SentinelOrchestrator(
        llm=object(),  # type: ignore[arg-type]
        serp=serp,
        unlocker=unlocker,
        mcp=mcp,
        proxy=proxy,
    )

    report = asyncio.run(
        orchestrator.investigate_vendor(
            "Example Vendor"
        )
    )

    expected_scraped_context = (
        "[Remote MCP Markdown Context]\n"
        "# Controlled MCP evidence"
    )

    assert mcp.scrape_calls == [
        "https://example.com/evidence"
    ]
    assert report["raw_intelligence"][
        "bright_data_tools_used"
    ] == [
        "SERP API",
        "Remote MCP scrape_as_markdown",
    ]
    assert (
        "Remote MCP search_engine"
        not in report["raw_intelligence"][
            "bright_data_tools_used"
        ]
    )
    assert captured["task_input"][
        "scraped_content"
    ] == expected_scraped_context
    assert report["raw_intelligence"][
        "scraped_content_chars"
    ] == len(expected_scraped_context)


def test_empty_mcp_results_are_not_claimed_as_used(
    monkeypatch,
) -> None:
    """An empty MCP search response must not appear in provider usage."""
    captured = _patch_offline_ai_pipeline(
        monkeypatch
    )

    orchestrator = SentinelOrchestrator(
        llm=object(),  # type: ignore[arg-type]
        serp=FakeSERPClient(
            results=[]
        ),
        unlocker=FakeWebUnlocker(
            content=None
        ),
        mcp=FakeRemoteMCPClient(
            search_results=[],
            scrape_content=None,
        ),
        proxy=FakeProxyClient(
            content=None
        ),
    )

    report = asyncio.run(
        orchestrator.investigate_vendor(
            "Example Vendor"
        )
    )

    assert report["raw_intelligence"][
        "bright_data_tools_used"
    ] == []
    assert captured["task_input"][
        "tools_used"
    ] == []
    assert report["raw_intelligence"][
        "search_results_count"
    ] == 0


def test_provider_failures_are_isolated_and_report_still_completes(
    monkeypatch,
) -> None:
    """Provider errors must not crash the complete investigation."""
    _patch_offline_ai_pipeline(
        monkeypatch,
        crew_report={},
    )

    orchestrator = SentinelOrchestrator(
        llm=object(),  # type: ignore[arg-type]
        serp=FakeSERPClient(
            error=RuntimeError("controlled SERP failure")
        ),
        unlocker=FakeWebUnlocker(
            error=RuntimeError(
                "controlled Unlocker failure"
            )
        ),
        mcp=FakeRemoteMCPClient(
            search_error=RuntimeError(
                "controlled MCP failure"
            ),
        ),
        proxy=FakeProxyClient(
            error=RuntimeError(
                "controlled proxy failure"
            )
        ),
    )

    report = asyncio.run(
        orchestrator.investigate_vendor(
            "Example Vendor"
        )
    )

    assert report["status"] == "completed"
    assert report["raw_intelligence"][
        "search_results_count"
    ] == 0
    assert report["raw_intelligence"][
        "bright_data_tools_used"
    ] == []
    assert report["sources"] == []


def test_invalid_vendor_name_stops_before_provider_calls() -> None:
    """Blank vendor input must fail before any external layer is invoked."""
    serp = FakeSERPClient()
    unlocker = FakeWebUnlocker()
    mcp = FakeRemoteMCPClient()
    proxy = FakeProxyClient()

    orchestrator = SentinelOrchestrator(
        llm=object(),  # type: ignore[arg-type]
        serp=serp,
        unlocker=unlocker,
        mcp=mcp,
        proxy=proxy,
    )

    with pytest.raises(
        ValueError,
        match="Vendor name cannot be empty",
    ):
        asyncio.run(
            orchestrator.investigate_vendor(
                "   "
            )
        )

    assert serp.calls == []
    assert unlocker.calls == []
    assert mcp.search_calls == []
    assert mcp.scrape_calls == []
    assert proxy.calls == []


def test_sync_progress_callback_is_supported() -> None:
    """A normal synchronous progress callback must also work."""
    events: list[dict[str, Any]] = []

    def progress_callback(
        payload: dict[str, Any],
    ) -> None:
        events.append(payload)

    orchestrator = SentinelOrchestrator(
        progress_callback=progress_callback,
        llm=object(),  # type: ignore[arg-type]
        serp=FakeSERPClient(),
        unlocker=FakeWebUnlocker(),
        mcp=FakeRemoteMCPClient(),
        proxy=FakeProxyClient(),
    )

    asyncio.run(
        orchestrator._emit_progress(
            "testing",
            "Controlled progress event",
            50,
        )
    )

    assert events == [
        {
            "stage": "testing",
            "message": "Controlled progress event",
            "progress": 50,
        }
    ]


def test_json_parser_supports_fenced_output() -> None:
    """CrewAI fenced JSON must be parsed without executing an LLM."""
    result = orchestrator_module._parse_crew_json(
        """```json
        {
          "risk_trajectory": "Stable",
          "key_findings": ["Controlled finding"]
        }
        ```"""
    )

    assert result == {
        "risk_trajectory": "Stable",
        "key_findings": [
            "Controlled finding"
        ],
    }


def test_merge_search_results_removes_duplicate_urls() -> None:
    """Supplementary MCP evidence must not duplicate SERP URLs."""
    primary = [
        {
            "title": "Primary",
            "url": "https://example.com/one",
            "snippet": "Primary result",
        }
    ]
    supplementary = [
        {
            "title": "Duplicate",
            "url": "https://example.com/one",
            "snippet": "Duplicate result",
        },
        {
            "title": "Unique",
            "url": "https://example.com/two",
            "snippet": "Unique result",
        },
    ]

    added = orchestrator_module._merge_search_results(
        primary,
        supplementary,
    )

    assert added == 1
    assert [
        result["url"]
        for result in primary
    ] == [
        "https://example.com/one",
        "https://example.com/two",
    ]
