"""Isolated tests for Sentinel's SQLite persistence layer."""

import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from core import database


@pytest.fixture()
def isolated_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """
    Redirect all database operations to a temporary test database.

    The real sentinel.db file is never opened or modified.
    """
    test_db_path = tmp_path / "sentinel-test.db"

    monkeypatch.setattr(
        database,
        "DB_PATH",
        test_db_path,
    )

    database.init_db()

    yield test_db_path


def make_report(
    vendor_name: str = "Example Test Vendor",
    risk_score: int = 72,
) -> dict:
    """Create deterministic report data for persistence tests."""
    return {
        "vendor_name": vendor_name,
        "risk_score": risk_score,
        "risk_level": "CRITICAL",
        "confidence_score": 0.91,
        "disruption_probability": 0.78,
        "executive_summary": (
            "Synthetic report created exclusively for database testing."
        ),
        "signals": [
            {
                "category": "Financial",
                "severity": "CRITICAL",
                "weight": 35,
                "indicators": ["Bankruptcy"],
            }
        ],
        "sources": [
            {
                "title": "Synthetic test source",
                "url": "https://example.com/test-source",
            }
        ],
        "raw_intelligence": {
            "primary_risk_category": "Financial",
            "risk_headline": "Synthetic critical-risk test",
            "risk_trajectory": "Deteriorating",
            "time_horizon": "Near-term",
            "key_findings": ["Synthetic finding"],
            "recommended_actions": ["Synthetic action"],
        },
        "status": "completed",
    }


def test_database_initialization_creates_required_tables(
    isolated_database: Path,
) -> None:
    connection = sqlite3.connect(isolated_database)

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()

    connection.close()

    tables = {row[0] for row in rows}

    assert {
        "vendors",
        "risk_reports",
        "intelligence_cache",
        "alerts",
    }.issubset(tables)


def test_save_and_get_report_round_trip(
    isolated_database: Path,
) -> None:
    original = make_report()

    report_id = database.save_report(original)
    saved = database.get_report_by_id(report_id)

    assert saved is not None
    assert saved["id"] == report_id
    assert saved["vendor_name"] == original["vendor_name"]
    assert saved["risk_score"] == 72
    assert saved["risk_level"] == "CRITICAL"
    assert saved["signals"] == original["signals"]
    assert saved["sources"] == original["sources"]
    assert saved["raw_intelligence"] == original["raw_intelligence"]


def test_same_vendor_is_reused_for_multiple_reports(
    isolated_database: Path,
) -> None:
    database.save_report(
        make_report("Reusable Test Vendor", risk_score=40)
    )
    database.save_report(
        make_report("Reusable Test Vendor", risk_score=70)
    )

    connection = sqlite3.connect(isolated_database)

    vendor_count = connection.execute(
        "SELECT COUNT(*) FROM vendors"
    ).fetchone()[0]

    report_count = connection.execute(
        "SELECT COUNT(*) FROM risk_reports"
    ).fetchone()[0]

    connection.close()

    assert vendor_count == 1
    assert report_count == 2


def test_recent_reports_hydrate_ui_metadata(
    isolated_database: Path,
) -> None:
    database.save_report(make_report())

    reports = database.get_recent_reports(limit=1)

    assert len(reports) == 1

    report = reports[0]

    assert report["generated_at"] == report["created_at"]
    assert report["primary_risk_category"] == "Financial"
    assert report["risk_headline"] == (
        "Synthetic critical-risk test"
    )
    assert report["risk_trajectory"] == "Deteriorating"
    assert report["time_horizon"] == "Near-term"
    assert report["key_findings"] == ["Synthetic finding"]
    assert report["recommended_actions"] == ["Synthetic action"]


def test_recent_reports_respect_limit(
    isolated_database: Path,
) -> None:
    database.save_report(make_report("Vendor One", 20))
    database.save_report(make_report("Vendor Two", 40))
    database.save_report(make_report("Vendor Three", 60))

    reports = database.get_recent_reports(limit=2)

    assert len(reports) == 2


def test_unknown_report_returns_none(
    isolated_database: Path,
) -> None:
    assert database.get_report_by_id(999999) is None


def test_delete_report_returns_correct_status(
    isolated_database: Path,
) -> None:
    report_id = database.save_report(make_report())

    assert database.delete_report_by_id(report_id) is True
    assert database.get_report_by_id(report_id) is None
    assert database.delete_report_by_id(report_id) is False
