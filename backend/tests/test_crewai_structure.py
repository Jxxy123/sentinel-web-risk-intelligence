"""Offline structure tests for Sentinel's CrewAI agents and tasks."""

from types import SimpleNamespace
from typing import Any

import agents.orchestrator as orchestrator_module


AGENT_BUILDERS = (
    (
        "recon",
        orchestrator_module.build_recon_agent,
        "Intelligence Recon Specialist",
    ),
    (
        "scraping",
        orchestrator_module.build_scraping_agent,
        "Deep Web Extraction Specialist",
    ),
    (
        "verification",
        orchestrator_module.build_verification_agent,
        "Source Credibility Analyst",
    ),
    (
        "intelligence",
        orchestrator_module.build_intelligence_agent,
        "Risk Intelligence Synthesizer",
    ),
    (
        "prediction",
        orchestrator_module.build_prediction_agent,
        "Predictive Risk Modeler",
    ),
    (
        "reporting",
        orchestrator_module.build_reporting_agent,
        "Executive Intelligence Reporter",
    ),
)


class FakeAgent:
    """Small constructor-compatible replacement for CrewAI Agent."""

    created: list["FakeAgent"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.role = kwargs["role"]
        self.goal = kwargs["goal"]
        self.backstory = kwargs["backstory"]
        self.llm = kwargs["llm"]
        self.verbose = kwargs["verbose"]
        self.allow_delegation = kwargs["allow_delegation"]
        self.__class__.created.append(self)


class FakeTask:
    """Small constructor-compatible replacement for CrewAI Task."""

    created: list["FakeTask"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.description = kwargs["description"]
        self.agent = kwargs["agent"]
        self.expected_output = kwargs["expected_output"]
        self.context = kwargs.get("context", [])
        self.__class__.created.append(self)


def _build_fake_agents() -> dict[str, SimpleNamespace]:
    """Return deterministic agent placeholders for task-construction tests."""
    return {
        name: SimpleNamespace(role=name)
        for name, _, _ in AGENT_BUILDERS
    }


def test_all_six_agent_builders_use_safe_configuration(
    monkeypatch,
) -> None:
    """Every builder must produce a distinct, non-delegating agent."""
    FakeAgent.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Agent",
        FakeAgent,
    )

    fake_llm = object()
    built_agents: dict[str, FakeAgent] = {}

    for name, builder, expected_role in AGENT_BUILDERS:
        agent = builder(fake_llm)
        built_agents[name] = agent

        assert agent.role == expected_role
        assert agent.llm is fake_llm
        assert agent.verbose is True
        assert agent.allow_delegation is False
        assert agent.goal.strip()
        assert agent.backstory.strip()

    assert len(built_agents) == 6
    assert len(FakeAgent.created) == 6
    assert len(
        {
            agent.role
            for agent in built_agents.values()
        }
    ) == 6


def test_agent_prompts_are_evidence_grounded(
    monkeypatch,
) -> None:
    """Agent goals and backstories must discourage unsupported claims."""
    FakeAgent.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Agent",
        FakeAgent,
    )

    fake_llm = object()

    for _, builder, _ in AGENT_BUILDERS:
        builder(fake_llm)

    combined_prompt = " ".join(
        (
            agent.goal
            + " "
            + agent.backstory
        ).lower()
        for agent in FakeAgent.created
    )

    assert "evidence" in combined_prompt
    assert (
        "never invent"
        in combined_prompt
        or "without unsupported claims"
        in combined_prompt
    )
    assert "verified" in combined_prompt


def test_build_tasks_creates_six_tasks_in_required_order(
    monkeypatch,
) -> None:
    """Task order and dependency chain must remain deterministic."""
    FakeTask.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Task",
        FakeTask,
    )

    agents = _build_fake_agents()

    tasks = orchestrator_module.build_tasks(
        vendor_name="Example Vendor",
        search_results=[
            {
                "title": "Verified filing",
                "url": "https://example.com/filing",
                "snippet": "A controlled legal filing update.",
                "source": "bright_data_serp",
            },
            {
                "title": "Verified operations report",
                "url": "https://example.com/operations",
                "snippet": "A controlled operational update.",
                "source": "bright_data_remote_mcp",
            },
        ],
        scraped_content=(
            "Controlled protected-source evidence."
        ),
        agents=agents,
        language="EN",
        pre_score=25,
        pre_level="MEDIUM",
        tools_used=[
            "SERP API",
            "Remote MCP search_engine",
            "Web Unlocker",
        ],
    )

    assert len(tasks) == 6
    assert tasks == FakeTask.created

    assert [
        task.agent
        for task in tasks
    ] == [
        agents["recon"],
        agents["scraping"],
        agents["verification"],
        agents["intelligence"],
        agents["prediction"],
        agents["reporting"],
    ]

    assert tasks[0].context == []
    assert tasks[1].context == [
        tasks[0],
    ]
    assert tasks[2].context == [
        tasks[0],
        tasks[1],
    ]
    assert tasks[3].context == [
        tasks[2],
    ]
    assert tasks[4].context == [
        tasks[3],
    ]
    assert tasks[5].context == [
        tasks[3],
        tasks[4],
    ]


def test_task_prompts_include_live_evidence_and_guidance(
    monkeypatch,
) -> None:
    """CrewAI tasks must receive source evidence and deterministic guidance."""
    FakeTask.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Task",
        FakeTask,
    )

    tasks = orchestrator_module.build_tasks(
        vendor_name="Example Vendor",
        search_results=[
            {
                "title": "Verified report",
                "url": "https://example.com/report",
                "snippet": "A controlled risk update.",
            }
        ],
        scraped_content="Controlled scraped evidence.",
        agents=_build_fake_agents(),
        language="FR",
        pre_score=42,
        pre_level="HIGH",
        tools_used=[
            "SERP API",
            "Remote MCP scrape_as_markdown",
        ],
    )

    recon_description = tasks[0].description
    scraping_description = tasks[1].description
    prediction_description = tasks[4].description
    reporting_description = tasks[5].description

    assert "Example Vendor" in recon_description
    assert "https://example.com/report" in recon_description
    assert "controlled risk update." in recon_description.lower()

    assert (
        "Controlled scraped evidence."
        in scraping_description
    )

    assert "42/100" in prediction_description
    assert "HIGH" in prediction_description

    assert "language code FR" in reporting_description
    assert '"SERP API"' in reporting_description
    assert (
        '"Remote MCP scrape_as_markdown"'
        in reporting_description
    )


def test_reporting_prompt_forbids_false_provider_and_monitoring_claims(
    monkeypatch,
) -> None:
    """The report task must only claim tools that were actually supplied."""
    FakeTask.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Task",
        FakeTask,
    )

    tasks = orchestrator_module.build_tasks(
        vendor_name="Example Vendor",
        search_results=[],
        scraped_content="",
        agents=_build_fake_agents(),
        tools_used=[
            "SERP API",
        ],
    )

    reporting_description = tasks[5].description.lower()

    assert (
        "do not claim continuous monitoring"
        in reporting_description
    )
    assert (
        "do not list a bright data service"
        in reporting_description
    )
    assert '"serp api"' in reporting_description
    assert (
        "remote mcp search_engine"
        not in reporting_description
    )
    assert "web unlocker" not in reporting_description


def test_missing_evidence_prompt_prevents_hallucinated_facts(
    monkeypatch,
) -> None:
    """No-evidence tasks must instruct agents to lower confidence."""
    FakeTask.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Task",
        FakeTask,
    )

    tasks = orchestrator_module.build_tasks(
        vendor_name="Unknown Vendor",
        search_results=[],
        scraped_content="",
        agents=_build_fake_agents(),
    )

    recon_description = tasks[0].description.lower()
    scraping_description = tasks[1].description.lower()

    assert (
        "do not invent company facts"
        in recon_description
    )
    assert (
        "evidence is insufficient"
        in recon_description
    )
    assert (
        "keep confidence low"
        in recon_description
        or "reduce confidence"
        in recon_description
    )

    assert (
        "no protected-source content"
        in scraping_description
    )
    assert (
        "do not infer facts from missing data"
        in scraping_description
    )


def test_search_summary_enforces_result_and_snippet_limits() -> None:
    """Prompt evidence must be bounded to prevent oversized LLM contexts."""
    search_results = [
        {
            "title": f"Result {index}",
            "url": f"https://example.com/{index}",
            "snippet": "x" * 400,
        }
        for index in range(
            orchestrator_module.MAX_SEARCH_RESULTS_FOR_TASK + 3
        )
    ]

    summary = orchestrator_module._build_search_summary(
        search_results,
        "Example Vendor",
    )

    lines = summary.splitlines()

    assert len(lines) == (
        orchestrator_module.MAX_SEARCH_RESULTS_FOR_TASK
    )
    assert (
        "https://example.com/"
        + str(
            orchestrator_module
            .MAX_SEARCH_RESULTS_FOR_TASK
        )
        not in summary
    )

    first_snippet = lines[0].split(": ", 1)[1]
    assert len(first_snippet) == 250


def test_scraped_content_is_truncated_before_task_creation(
    monkeypatch,
) -> None:
    """Large scraped pages must not be injected fully into CrewAI prompts."""
    FakeTask.created = []

    monkeypatch.setattr(
        orchestrator_module,
        "Task",
        FakeTask,
    )

    oversized_content = (
        "z"
        * (
            orchestrator_module
            .MAX_SCRAPED_CONTENT_FOR_TASK
            + 500
        )
    )

    tasks = orchestrator_module.build_tasks(
        vendor_name="Example Vendor",
        search_results=[],
        scraped_content=oversized_content,
        agents=_build_fake_agents(),
    )

    scraping_description = tasks[1].description
    injected_content = oversized_content[
        :orchestrator_module
        .MAX_SCRAPED_CONTENT_FOR_TASK
    ]

    assert injected_content in scraping_description
    assert oversized_content not in scraping_description


def test_get_llm_uses_environment_backed_settings(
    monkeypatch,
) -> None:
    """LLM construction must use central settings without making a request."""
    captured: dict[str, Any] = {}

    class FakeLLM:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        orchestrator_module,
        "LLM",
        FakeLLM,
    )
    monkeypatch.setattr(
        orchestrator_module,
        "settings",
        SimpleNamespace(
            free_tier_model="controlled-model",
            openai_api_key="controlled-key",
            openai_base_url="https://example.invalid/v1",
        ),
    )

    result = orchestrator_module.get_llm()

    assert isinstance(result, FakeLLM)
    assert captured == {
        "model": "openai/controlled-model",
        "api_key": "controlled-key",
        "base_url": "https://example.invalid/v1",
        "temperature": 0.1,
        "max_retries": 3,
        "request_timeout": 90,
    }
