"""
Controlled live CrewAI smoke test for Sentinel Web-Risk.

This test validates the configured LLM provider through one minimal CrewAI
agent and one minimal task. It does not call Bright Data, MCP, proxies,
databases, the API server, or the full vendor-investigation orchestrator.
"""

import time
from urllib.parse import urlparse

from crewai import Agent, Crew, Process, Task

from agents.orchestrator import get_llm
from core.config import settings


EXPECTED_TOKEN = "SENTINEL_CREWAI_SMOKE_OK"


def validate_configuration() -> None:
    """Fail before CrewAI starts when required AI settings are absent."""
    if not settings.openai_api_key.strip():
        raise SystemExit(
            "OPENAI_API_KEY is missing. No CrewAI or LLM call was attempted."
        )

    if not settings.openai_base_url.strip():
        raise SystemExit(
            "OPENAI_BASE_URL is missing. No CrewAI or LLM call was attempted."
        )

    if not settings.free_tier_model.strip():
        raise SystemExit(
            "FREE_TIER_MODEL is missing. No CrewAI or LLM call was attempted."
        )

    parsed_url = urlparse(settings.openai_base_url)

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise SystemExit(
            "OPENAI_BASE_URL is invalid. No CrewAI or LLM call was attempted."
        )

    print("Protected AI configuration verified.")
    print(f"Provider host: {parsed_url.netloc}")
    print(f"Configured model: {settings.free_tier_model}")
    print("CrewAI agents planned: exactly 1")
    print("CrewAI tasks planned: exactly 1")
    print("Bright Data calls planned: 0")
    print("MCP calls planned: 0")
    print("Proxy calls planned: 0")
    print("Database calls planned: 0")


def run_smoke_test() -> None:
    """Execute one minimal live CrewAI task and verify its response."""
    validate_configuration()

    llm = get_llm()

    agent = Agent(
        role="Sentinel Connection Validation Agent",
        goal=(
            "Return the exact validation token requested by the task, "
            "without adding analysis or unrelated text."
        ),
        backstory=(
            "You are a deterministic connection-test agent used only to "
            "confirm that Sentinel can reach its configured LLM through CrewAI."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    task = Task(
        description=(
            "Return exactly this token and nothing else: "
            f"{EXPECTED_TOKEN}"
        ),
        expected_output=EXPECTED_TOKEN,
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        max_rpm=1,
        verbose=False,
    )

    print("Starting controlled live CrewAI smoke test...")
    started_at = time.perf_counter()

    result = str(crew.kickoff()).strip()

    elapsed_seconds = time.perf_counter() - started_at

    if EXPECTED_TOKEN not in result:
        safe_preview = result[:200].replace("\n", " ")

        raise SystemExit(
            "CrewAI returned an unexpected response. "
            f"Safe response preview: {safe_preview!r}"
        )

    print("Controlled live CrewAI smoke test passed.")
    print(f"Validated token: {EXPECTED_TOKEN}")
    print(f"Request duration: {elapsed_seconds:.2f} seconds")
    print("CrewAI agents completed: exactly 1")
    print("CrewAI tasks completed: exactly 1")
    print("Bright Data calls completed: 0")
    print("MCP calls completed: 0")
    print("Proxy calls completed: 0")
    print("Database calls completed: 0")


if __name__ == "__main__":
    run_smoke_test()
