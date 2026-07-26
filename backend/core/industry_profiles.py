"""Industry-aware search planning for Sentinel Web-Risk."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from core.company_identity import CompanyIdentity


@dataclass(frozen=True)
class IndustryProfile:
    key: str
    display_name: str
    detection_terms: tuple[str, ...]
    risk_terms: tuple[str, ...]
    regulator_terms: tuple[str, ...]


PROFILES: dict[str, IndustryProfile] = {
    "technology": IndustryProfile(
        key="technology",
        display_name="Technology",
        detection_terms=(
            "software",
            "cloud",
            "saas",
            "technology",
            "cybersecurity",
            "data center",
            "artificial intelligence",
            "it services",
        ),
        risk_terms=(
            "service outage",
            "data breach",
            "security incident",
            "regulatory investigation",
            "layoffs",
            "licensing dispute",
        ),
        regulator_terms=(
            "data protection authority",
            "competition regulator",
            "cybersecurity agency",
        ),
    ),
    "financial_services": IndustryProfile(
        key="financial_services",
        display_name="Financial Services",
        detection_terms=(
            "bank",
            "insurance",
            "fintech",
            "lender",
            "asset management",
            "financial services",
        ),
        risk_terms=(
            "capital adequacy",
            "liquidity",
            "regulatory action",
            "fraud",
            "licence suspension",
            "customer funds",
        ),
        regulator_terms=(
            "central bank",
            "securities regulator",
            "financial conduct authority",
        ),
    ),
    "healthcare": IndustryProfile(
        key="healthcare",
        display_name="Healthcare",
        detection_terms=(
            "hospital",
            "clinic",
            "healthcare",
            "medical",
            "pharmaceutical",
            "diagnostic",
        ),
        risk_terms=(
            "patient safety",
            "medical negligence",
            "licence suspension",
            "drug recall",
            "regulatory action",
            "service disruption",
        ),
        regulator_terms=(
            "health ministry",
            "medical council",
            "drug regulator",
        ),
    ),
    "logistics": IndustryProfile(
        key="logistics",
        display_name="Logistics and Transportation",
        detection_terms=(
            "logistics",
            "freight",
            "shipping",
            "transport",
            "courier",
            "warehouse",
            "customs",
        ),
        risk_terms=(
            "shipment delay",
            "customs violation",
            "port disruption",
            "fleet accident",
            "licence issue",
            "cargo loss",
        ),
        regulator_terms=(
            "customs authority",
            "transport authority",
            "port authority",
        ),
    ),
    "food_hospitality": IndustryProfile(
        key="food_hospitality",
        display_name="Food and Hospitality",
        detection_terms=(
            "restaurant",
            "hotel",
            "food",
            "catering",
            "hospitality",
            "beverage",
        ),
        risk_terms=(
            "food safety",
            "health violation",
            "product recall",
            "licence suspension",
            "customer illness",
            "hygiene inspection",
        ),
        regulator_terms=(
            "food safety authority",
            "health department",
            "consumer protection authority",
        ),
    ),
    "construction": IndustryProfile(
        key="construction",
        display_name="Construction and Engineering",
        detection_terms=(
            "construction",
            "engineering",
            "contractor",
            "infrastructure",
            "property developer",
        ),
        risk_terms=(
            "workplace accident",
            "permit violation",
            "project delay",
            "contract dispute",
            "safety enforcement",
            "cost overrun",
        ),
        regulator_terms=(
            "building authority",
            "labour inspectorate",
            "occupational safety regulator",
        ),
    ),
    "manufacturing": IndustryProfile(
        key="manufacturing",
        display_name="Manufacturing",
        detection_terms=(
            "manufacturing",
            "factory",
            "industrial",
            "producer",
            "plant",
        ),
        risk_terms=(
            "factory closure",
            "product recall",
            "supply shortage",
            "workplace accident",
            "production halt",
            "quality failure",
        ),
        regulator_terms=(
            "product safety regulator",
            "labour inspectorate",
            "environmental regulator",
        ),
    ),
    "retail": IndustryProfile(
        key="retail",
        display_name="Retail and Consumer",
        detection_terms=(
            "retail",
            "store",
            "ecommerce",
            "supermarket",
            "consumer goods",
        ),
        risk_terms=(
            "store closure",
            "product recall",
            "consumer complaint",
            "supply disruption",
            "data breach",
            "licence issue",
        ),
        regulator_terms=(
            "consumer protection authority",
            "competition regulator",
            "product safety regulator",
        ),
    ),
    "energy": IndustryProfile(
        key="energy",
        display_name="Energy and Utilities",
        detection_terms=(
            "energy",
            "utility",
            "oil",
            "gas",
            "electricity",
            "power",
            "renewable",
        ),
        risk_terms=(
            "environmental violation",
            "plant outage",
            "safety incident",
            "licence suspension",
            "supply disruption",
            "regulatory action",
        ),
        regulator_terms=(
            "energy regulator",
            "environmental agency",
            "occupational safety regulator",
        ),
    ),
    "general": IndustryProfile(
        key="general",
        display_name="General Business",
        detection_terms=(),
        risk_terms=(
            "financial distress",
            "operational disruption",
            "regulatory action",
            "lawsuit",
            "licence suspension",
            "restructuring",
            "fraud",
            "workforce reduction",
        ),
        regulator_terms=(
            "company registry",
            "competition regulator",
            "consumer protection authority",
        ),
    ),
}


def infer_industry(
    text: str,
    *,
    declared_industry: str | None = None,
) -> tuple[IndustryProfile, float]:
    """Infer an industry conservatively; fall back to General Business."""
    normalized = " ".join(str(text or "").lower().split())

    if declared_industry:
        declared = declared_industry.strip().lower()

        for key, profile in PROFILES.items():
            if (
                declared == key
                or declared == profile.display_name.lower()
                or declared in profile.detection_terms
            ):
                return profile, 1.0

    scores: dict[str, int] = {}

    for key, profile in PROFILES.items():
        if key == "general":
            continue

        scores[key] = sum(
            term in normalized
            for term in profile.detection_terms
        )

    if not scores or max(scores.values(), default=0) == 0:
        return PROFILES["general"], 0.25

    best_key = max(
        scores,
        key=lambda key: (
            scores[key],
            key,
        ),
    )
    best_score = scores[best_key]
    confidence = min(
        0.95,
        0.45 + (best_score * 0.15),
    )

    return PROFILES[best_key], round(confidence, 2)


def build_live_search_queries(
    identity: CompanyIdentity,
    profile: IndustryProfile,
    *,
    year: int | None = None,
) -> list[str]:
    """
    Build general, industry, regulatory, and identity-verification queries.

    These are live-web search plans, not claims about the company.
    """
    current_year = year or datetime.now(timezone.utc).year
    quoted_name = f'"{identity.canonical_name}"'
    geography = f' "{identity.country}"' if identity.country else ""

    industry_terms = " OR ".join(
        f'"{term}"'
        for term in profile.risk_terms[:6]
    )
    regulator_terms = " OR ".join(
        f'"{term}"'
        for term in profile.regulator_terms[:3]
    )

    queries = [
        (
            f"{quoted_name}{geography} "
            f"(financial OR operational OR legal OR regulatory) "
            f"({current_year - 1} OR {current_year})"
        ),
        (
            f"{quoted_name}{geography} "
            f"({industry_terms}) "
            f"({current_year - 1} OR {current_year})"
        ),
        (
            f"{quoted_name}{geography} "
            f"({regulator_terms}) "
            f"(notice OR action OR warning OR decision)"
        ),
        (
            f"{quoted_name}{geography} "
            "(official website OR company profile OR registry OR headquarters)"
        ),
    ]

    return queries
