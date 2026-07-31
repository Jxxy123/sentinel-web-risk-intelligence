"""Offline resilience tests for Sentinel's CrewAI execution helpers."""

import json
from typing import Any

import agents.orchestrator as orchestrator_module
from agents.orchestrator import SentinelOrchestrator


class SequenceCrew:
    """Crew test double that returns or raises outcomes in sequence."""

    def __init__(
        self,
        outcomes: list[Any],
    ) -> None:
        self.outcomes = list(outcomes)
        self.call_count = 0

    def kickoff(self) -> Any:
        self.call_count += 1

        if not self.outcomes:
            raise AssertionError(
                "Crew kickoff was called more times than expected."
            )

        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def test_crew_success_returns_output_without_retry(
    monkeypatch,
) -> None:
    """A successful first CrewAI execution must not sleep or retry."""
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        orchestrator_module.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crew = SequenceCrew(
        [
            '{"status": "controlled success"}',
        ]
    )

    result = SentinelOrchestrator._kickoff_crew_with_retry(
        crew
    )

    assert result == '{"status": "controlled success"}'
    assert crew.call_count == 1
    assert sleep_calls == []


def test_rate_limit_retries_then_returns_success(
    monkeypatch,
) -> None:
    """A temporary rate limit must wait and retry successfully."""
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        orchestrator_module.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crew = SequenceCrew(
        [
            RuntimeError(
                "rate_limit: try again in 2.5s"
            ),
            '{"status": "recovered"}',
        ]
    )

    result = SentinelOrchestrator._kickoff_crew_with_retry(
        crew
    )

    assert result == '{"status": "recovered"}'
    assert crew.call_count == 2

    # suggested 2.5 + 5 is below the enforced 10-second minimum
    assert sleep_calls == [10.0]


def test_rate_limit_wait_is_capped(
    monkeypatch,
) -> None:
    """Provider-suggested waits must not exceed Sentinel's safety cap."""
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        orchestrator_module.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crew = SequenceCrew(
        [
            RuntimeError(
                "Rate limit reached; try again in 300s"
            ),
            '{"status": "recovered"}',
        ]
    )

    result = SentinelOrchestrator._kickoff_crew_with_retry(
        crew
    )

    assert result == '{"status": "recovered"}'
    assert sleep_calls == [
        float(
            orchestrator_module
            .CREW_MAX_RATE_LIMIT_WAIT_SECONDS
        )
    ]


def test_rate_limit_without_provider_wait_uses_default(
    monkeypatch,
) -> None:
    """A rate-limit error without a duration must use the default wait."""
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        orchestrator_module.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crew = SequenceCrew(
        [
            RuntimeError(
                "Request failed because of rate limit"
            ),
            '{"status": "recovered"}',
        ]
    )

    result = SentinelOrchestrator._kickoff_crew_with_retry(
        crew
    )

    assert result == '{"status": "recovered"}'
    assert sleep_calls == [65.0]


def test_non_rate_limit_error_fails_closed_without_retry(
    monkeypatch,
) -> None:
    """A non-rate-limit CrewAI error must not be retried."""
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        orchestrator_module.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crew = SequenceCrew(
        [
            RuntimeError(
                "controlled malformed provider response"
            ),
            '{"status": "must not run"}',
        ]
    )

    result = SentinelOrchestrator._kickoff_crew_with_retry(
        crew
    )

    assert result == "{}"
    assert crew.call_count == 1
    assert sleep_calls == []


def test_exhausted_rate_limit_retries_return_empty_json(
    monkeypatch,
) -> None:
    """Repeated rate limits must stop after the configured attempt limit."""
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        orchestrator_module.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crew = SequenceCrew(
        [
            RuntimeError(
                "rate_limit: try again in 1s"
            )
            for _ in range(
                orchestrator_module.CREW_MAX_ATTEMPTS
            )
        ]
    )

    result = SentinelOrchestrator._kickoff_crew_with_retry(
        crew
    )

    assert result == "{}"
    assert crew.call_count == (
        orchestrator_module.CREW_MAX_ATTEMPTS
    )

    # Sentinel sleeps only between attempts, never after the last failure.
    assert sleep_calls == [
        10.0
        for _ in range(
            orchestrator_module.CREW_MAX_ATTEMPTS - 1
        )
    ]


def test_json_parser_accepts_plain_json_object() -> None:
    """A normal CrewAI JSON object must parse directly."""
    result = orchestrator_module._parse_crew_json(
        json.dumps(
            {
                "risk_trajectory": "Stable",
                "key_findings": [
                    "Controlled finding",
                ],
            }
        )
    )

    assert result == {
        "risk_trajectory": "Stable",
        "key_findings": [
            "Controlled finding",
        ],
    }


def test_json_parser_extracts_fenced_json() -> None:
    """Markdown-fenced CrewAI JSON must be recovered safely."""
    result = orchestrator_module._parse_crew_json(
        """```json
        {
          "risk_trajectory": "Improving",
          "recommended_actions": ["Continue monitoring"]
        }
        ```"""
    )

    assert result == {
        "risk_trajectory": "Improving",
        "recommended_actions": [
            "Continue monitoring",
        ],
    }


def test_json_parser_extracts_object_from_surrounding_text() -> None:
    """A JSON object surrounded by model commentary must still parse."""
    result = orchestrator_module._parse_crew_json(
        (
            "Controlled preamble\n"
            '{"risk_headline": "Evidence remains limited."}'
            "\nControlled suffix"
        )
    )

    assert result == {
        "risk_headline": "Evidence remains limited.",
    }


def test_json_parser_rejects_non_object_json() -> None:
    """Arrays and primitive JSON values must not become report dictionaries."""
    assert orchestrator_module._parse_crew_json(
        '["not", "a", "report"]'
    ) == {}

    assert orchestrator_module._parse_crew_json(
        '"not a report"'
    ) == {}


def test_json_parser_returns_empty_for_malformed_output() -> None:
    """Invalid CrewAI output must fail safely to an empty report."""
    assert orchestrator_module._parse_crew_json(
        "This is not JSON."
    ) == {}

    assert orchestrator_module._parse_crew_json(
        '{"broken": true'
    ) == {}

    assert orchestrator_module._parse_crew_json(
        ""
    ) == {}


def test_normalize_string_list_filters_invalid_values() -> None:
    """Report list fields must be normalized into non-empty strings."""
    assert orchestrator_module._normalize_string_list(
        [
            " first ",
            "",
            "   ",
            42,
        ]
    ) == [
        "first",
        "42",
    ]

    assert orchestrator_module._normalize_string_list(
        "not-a-list"
    ) == []
