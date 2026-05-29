"""
Sentinel Web-Risk — Dynamic Risk Scoring Engine
"""
from typing import List, Dict, Any, Tuple
import re


RISK_KEYWORDS = {
    "financial": {
        "critical": ["bankruptcy", "insolvency", "chapter 11", "chapter 7", "liquidation",
                     "default", "debt restructuring", "financial collapse", "insolvent"],
        "high": ["financial distress", "cash flow problems", "massive losses", "debt crisis",
                 "credit downgrade", "junk rating", "bond default", "revenue decline"],
        "medium": ["cost cutting", "budget cuts", "financial pressure", "losses", "debt increase",
                   "declining revenue", "profitability concerns", "write-down"],
        "low": ["restructuring", "strategic review", "cost optimization", "efficiency measures"],
    },
    "operational": {
        "critical": ["shutdown", "factory closure", "operations halted", "production stopped",
                     "supply chain collapse", "critical failure"],
        "high": ["major layoffs", "mass redundancies", "facility closure", "production delays",
                 "supply shortage", "operational disruption"],
        "medium": ["hiring freeze", "workforce reduction", "operational challenges",
                   "capacity reduction", "delays"],
        "low": ["restructuring", "reorganization", "headcount adjustment"],
    },
    "legal": {
        "critical": ["criminal charges", "fraud conviction", "sanctions", "regulatory shutdown",
                     "license revoked", "SEC enforcement"],
        "high": ["major lawsuit", "class action", "regulatory investigation", "DOJ probe",
                 "SEC investigation", "fraud allegations", "antitrust violation"],
        "medium": ["legal dispute", "lawsuit", "regulatory warning", "compliance issues",
                   "fine", "penalty"],
        "low": ["legal review", "regulatory inquiry", "compliance review"],
    },
    "reputational": {
        "critical": ["scandal", "corruption exposed", "massive fraud", "executive arrested"],
        "high": ["public backlash", "brand crisis", "customer exodus", "viral negative",
                 "boycott", "major controversy"],
        "medium": ["negative press", "customer complaints", "PR crisis", "negative reviews"],
        "low": ["criticism", "concerns raised", "negative sentiment"],
    },
    "cybersecurity": {
        "critical": ["data breach", "ransomware attack", "critical vulnerability exploited",
                     "systems compromised", "cyber attack"],
        "high": ["security breach", "hacked", "data leak", "vulnerability exposed"],
        "medium": ["security incident", "data exposure", "security concerns"],
        "low": ["security review", "vulnerability patched"],
    },
}

SEVERITY_WEIGHTS = {
    "critical": 35,
    "high": 20,
    "medium": 10,
    "low": 3,
}


def analyze_text_for_signals(text: str) -> List[Dict]:
    """Extract risk signals from raw text."""
    text_lower = text.lower()
    signals = []

    for category, severity_map in RISK_KEYWORDS.items():
        for severity, keywords in severity_map.items():
            for keyword in keywords:
                if keyword in text_lower:
                    signals.append({
                        "category": category,
                        "severity": severity,
                        "keyword": keyword,
                        "weight": SEVERITY_WEIGHTS[severity],
                    })

    # Deduplicate by category+severity
    seen = set()
    unique_signals = []
    for s in signals:
        key = f"{s['category']}-{s['severity']}-{s['keyword']}"
        if key not in seen:
            seen.add(key)
            unique_signals.append(s)

    return unique_signals


def calculate_risk_score(signals: List[Dict]) -> Tuple[int, str, float]:
    """
    Calculate risk score (0-100), level, and confidence from signals.
    Returns: (score, level, confidence)
    """
    if not signals:
        return 5, "LOW", 0.3

    total_weight = sum(s["weight"] for s in signals)
    score = min(100, total_weight)

    # Determine level
    if score >= 70:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    # Confidence based on signal count and diversity
    categories = set(s["category"] for s in signals)
    signal_diversity = len(categories) / len(RISK_KEYWORDS)
    signal_volume = min(1.0, len(signals) / 15)
    confidence = round((signal_diversity * 0.5 + signal_volume * 0.5), 2)

    return score, level, confidence


def calculate_disruption_probability(score: int, signals: List[Dict]) -> float:
    """Estimate probability of operational disruption (0-1)."""
    base = score / 100

    # Amplify if critical signals present
    has_critical = any(s["severity"] == "critical" for s in signals)
    has_financial = any(s["category"] == "financial" for s in signals)
    has_operational = any(s["category"] == "operational" for s in signals)

    modifier = 1.0
    if has_critical:
        modifier += 0.2
    if has_financial and has_operational:
        modifier += 0.15

    return round(min(0.99, base * modifier), 2)


def get_risk_color(level: str) -> str:
    """Return color code for risk level."""
    colors = {
        "CRITICAL": "#FF2D55",
        "HIGH": "#FF9500",
        "MEDIUM": "#FFCC00",
        "LOW": "#34C759",
    }
    return colors.get(level, "#34C759")


def format_signals_for_report(signals: List[Dict]) -> List[Dict]:
    """Format signals for the executive report."""
    formatted = []
    category_map = {}

    for s in signals:
        cat = s["category"]
        if cat not in category_map:
            category_map[cat] = {
                "category": cat.title(),
                "severity": s["severity"].upper(),
                "indicators": [],
                "weight": 0,
            }
        category_map[cat]["indicators"].append(s["keyword"].title())
        category_map[cat]["weight"] += s["weight"]
        # Keep highest severity
        if SEVERITY_WEIGHTS.get(s["severity"], 0) > SEVERITY_WEIGHTS.get(
            category_map[cat]["severity"].lower(), 0
        ):
            category_map[cat]["severity"] = s["severity"].upper()

    for cat_data in category_map.values():
        cat_data["indicators"] = list(set(cat_data["indicators"]))[:5]
        formatted.append(cat_data)

    return sorted(formatted, key=lambda x: x["weight"], reverse=True)