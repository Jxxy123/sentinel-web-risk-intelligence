"""Unit tests for Sentinel's deterministic risk-scoring engine."""

import pytest

from core.risk_engine import (
    analyze_text_for_signals,
    calculate_disruption_probability,
    calculate_risk_score,
    format_signals_for_report,
    get_risk_color,
)


def make_signal(
    category: str,
    severity: str,
    weight: int,
    keyword: str = "test indicator",
) -> dict:
    """Create a controlled signal for score-calculation tests."""
    return {
        "category": category,
        "severity": severity,
        "keyword": keyword,
        "weight": weight,
    }


# -------------------------------------------------------------------
# Signal extraction tests
# -------------------------------------------------------------------


def test_empty_text_returns_no_signals() -> None:
    assert analyze_text_for_signals("") == []


def test_unrelated_text_returns_no_signals() -> None:
    text = "The company announced a new product and opened another office."
    assert analyze_text_for_signals(text) == []


def test_signal_detection_is_case_insensitive() -> None:
    signals = analyze_text_for_signals(
        "The organisation entered BANKRUPTCY proceedings."
    )

    assert any(
        signal["category"] == "financial"
        and signal["severity"] == "critical"
        and signal["keyword"] == "bankruptcy"
        for signal in signals
    )


def test_detects_signals_across_multiple_categories() -> None:
    text = (
        "The company reported financial distress, major layoffs, "
        "a regulatory investigation, public backlash, and a data breach."
    )

    signals = analyze_text_for_signals(text)
    categories = {signal["category"] for signal in signals}

    assert {
        "financial",
        "operational",
        "legal",
        "reputational",
        "cybersecurity",
    }.issubset(categories)


def test_repeated_keyword_is_not_duplicated() -> None:
    text = "Bankruptcy bankruptcy bankruptcy"

    signals = analyze_text_for_signals(text)
    bankruptcy_signals = [
        signal for signal in signals
        if signal["keyword"] == "bankruptcy"
    ]

    assert len(bankruptcy_signals) == 1


# -------------------------------------------------------------------
# Risk-score tests
# -------------------------------------------------------------------


def test_no_signals_returns_default_low_risk() -> None:
    score, level, confidence = calculate_risk_score([])

    assert score == 5
    assert level == "LOW"
    assert confidence == 0.3


@pytest.mark.parametrize(
    ("weight", "expected_level"),
    [
        (24, "LOW"),
        (25, "MEDIUM"),
        (49, "MEDIUM"),
        (50, "HIGH"),
        (69, "HIGH"),
        (70, "CRITICAL"),
    ],
)
def test_risk_level_boundaries(
    weight: int,
    expected_level: str,
) -> None:
    signals = [
        make_signal(
            category="financial",
            severity="medium",
            weight=weight,
        )
    ]

    score, level, _ = calculate_risk_score(signals)

    assert score == weight
    assert level == expected_level


def test_risk_score_is_capped_at_100() -> None:
    signals = [
        make_signal("financial", "critical", 60, "bankruptcy"),
        make_signal("operational", "critical", 60, "shutdown"),
    ]

    score, level, _ = calculate_risk_score(signals)

    assert score == 100
    assert level == "CRITICAL"


def test_confidence_increases_with_volume_and_category_diversity() -> None:
    categories = [
        "financial",
        "operational",
        "legal",
        "reputational",
        "cybersecurity",
    ]

    signals = [
        make_signal(
            category=categories[index % len(categories)],
            severity="medium",
            weight=1,
            keyword=f"signal-{index}",
        )
        for index in range(15)
    ]

    _, _, confidence = calculate_risk_score(signals)

    assert confidence == 1.0


def test_confidence_remains_between_zero_and_one() -> None:
    signals = [
        make_signal(
            category="financial",
            severity="critical",
            weight=35,
            keyword=f"indicator-{index}",
        )
        for index in range(100)
    ]

    _, _, confidence = calculate_risk_score(signals)

    assert 0.0 <= confidence <= 1.0


# -------------------------------------------------------------------
# Disruption-probability tests
# -------------------------------------------------------------------


def test_disruption_probability_uses_base_score() -> None:
    signals = [
        make_signal("legal", "medium", 10, "lawsuit"),
    ]

    probability = calculate_disruption_probability(50, signals)

    assert probability == 0.5


def test_critical_signal_increases_disruption_probability() -> None:
    signals = [
        make_signal("legal", "critical", 35, "criminal charges"),
    ]

    probability = calculate_disruption_probability(50, signals)

    assert probability == 0.6


def test_financial_and_operational_combination_increases_probability() -> None:
    signals = [
        make_signal("financial", "high", 20, "financial distress"),
        make_signal("operational", "high", 20, "major layoffs"),
    ]

    probability = calculate_disruption_probability(50, signals)

    assert probability == 0.58


def test_disruption_probability_is_capped_at_point_99() -> None:
    signals = [
        make_signal("financial", "critical", 35, "bankruptcy"),
        make_signal("operational", "critical", 35, "shutdown"),
    ]

    probability = calculate_disruption_probability(100, signals)

    assert probability == 0.99


# -------------------------------------------------------------------
# Report-formatting tests
# -------------------------------------------------------------------


def test_format_signals_groups_same_category() -> None:
    signals = [
        make_signal("financial", "medium", 10, "losses"),
        make_signal("financial", "critical", 35, "bankruptcy"),
    ]

    formatted = format_signals_for_report(signals)

    assert len(formatted) == 1
    assert formatted[0]["category"] == "Financial"
    assert formatted[0]["severity"] == "CRITICAL"
    assert formatted[0]["weight"] == 45
    assert set(formatted[0]["indicators"]) == {
        "Losses",
        "Bankruptcy",
    }


def test_formatted_categories_are_sorted_by_weight() -> None:
    signals = [
        make_signal("financial", "low", 3, "restructuring"),
        make_signal("cybersecurity", "critical", 35, "data breach"),
    ]

    formatted = format_signals_for_report(signals)

    assert formatted[0]["category"] == "Cybersecurity"
    assert formatted[1]["category"] == "Financial"


@pytest.mark.parametrize(
    ("level", "expected_color"),
    [
        ("CRITICAL", "#FF2D55"),
        ("HIGH", "#FF9500"),
        ("MEDIUM", "#FFCC00"),
        ("LOW", "#34C759"),
        ("UNKNOWN", "#34C759"),
    ],
)
def test_risk_level_colors(
    level: str,
    expected_color: str,
) -> None:
    assert get_risk_color(level) == expected_color
