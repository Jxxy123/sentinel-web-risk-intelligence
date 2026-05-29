"""
Sentinel Web-Risk — Database Models (SQLite)
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path("./sentinel.db")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the SQLite database with all required tables."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            industry TEXT,
            country TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS risk_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            vendor_name TEXT NOT NULL,
            risk_score INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'LOW',
            confidence_score REAL DEFAULT 0.0,
            disruption_probability REAL DEFAULT 0.0,
            executive_summary TEXT,
            signals TEXT DEFAULT '[]',
            sources TEXT DEFAULT '[]',
            raw_intelligence TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS intelligence_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            content TEXT,
            url TEXT,
            language TEXT DEFAULT 'en',
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER,
            vendor_name TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            message TEXT,
            triggered_signals TEXT DEFAULT '[]',
            acknowledged INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully.")


def save_report(report_data: Dict[str, Any]) -> int:
    conn = get_db()
    cursor = conn.cursor()

    # Upsert vendor
    cursor.execute(
        "INSERT OR IGNORE INTO vendors (name) VALUES (?)",
        (report_data["vendor_name"],)
    )
    cursor.execute("SELECT id FROM vendors WHERE name = ?", (report_data["vendor_name"],))
    vendor = cursor.fetchone()
    vendor_id = vendor["id"]

    # Insert report
    cursor.execute("""
        INSERT INTO risk_reports
        (vendor_id, vendor_name, risk_score, risk_level, confidence_score,
         disruption_probability, executive_summary, signals, sources, raw_intelligence, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        vendor_id,
        report_data["vendor_name"],
        report_data.get("risk_score", 0),
        report_data.get("risk_level", "LOW"),
        report_data.get("confidence_score", 0.0),
        report_data.get("disruption_probability", 0.0),
        report_data.get("executive_summary", ""),
        json.dumps(report_data.get("signals", [])),
        json.dumps(report_data.get("sources", [])),
        json.dumps(report_data.get("raw_intelligence", {})),
        report_data.get("status", "completed"),
    ))

    report_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return report_id


def get_recent_reports(limit: int = 10) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM risk_reports ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    reports = []
    for row in rows:
        r = dict(row)
        r["signals"] = json.loads(r["signals"])
        r["sources"] = json.loads(r["sources"])
        r["raw_intelligence"] = json.loads(r["raw_intelligence"])
        
        # 🌐 FIX: Map database column 'created_at' to key 'generated_at' required by Next.js table UI
        r["generated_at"] = r.get("created_at")
        
        # 🌐 FIX: Extract primary risk category out of JSON storage fields to populate the column mapping layer
        raw_intel = r["raw_intelligence"]
        if isinstance(raw_intel, dict) and "primary_risk_category" in raw_intel:
            r["primary_risk_category"] = raw_intel["primary_risk_category"]
        elif r["signals"] and isinstance(r["signals"], list) and len(r["signals"]) > 0:
            r["primary_risk_category"] = r["signals"][0].get("category", "Cybersecurity").title()
        else:
            r["primary_risk_category"] = "Cybersecurity"
            
        # 🌐 FIX: Hydrate extra collapsible layout parameters for historical card data reconstructions
        if isinstance(raw_intel, dict):
            r["risk_headline"] = raw_intel.get("risk_headline", f"Threat matrix summary for {r['vendor_name']}")
            r["time_horizon"] = raw_intel.get("time_horizon", "Near-term")
            r["risk_trajectory"] = raw_intel.get("risk_trajectory", "Stable")
            r["key_findings"] = raw_intel.get("key_findings", [])
            r["recommended_actions"] = raw_intel.get("recommended_actions", [])
            
        reports.append(r)
    return reports


def get_report_by_id(report_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM risk_reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    r = dict(row)
    r["signals"] = json.loads(r["signals"])
    r["sources"] = json.loads(r["sources"])
    r["raw_intelligence"] = json.loads(r["raw_intelligence"])
    return r


def delete_report_by_id(report_id: int) -> bool:
    """🌐 NEW: Purges a specific threat profile from SQLite risk_reports storage."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM risk_reports WHERE id = ?", (report_id,))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return affected_rows > 0