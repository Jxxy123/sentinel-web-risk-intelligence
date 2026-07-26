from core.company_identity import build_company_identity
from core.industry_profiles import (
    build_live_search_queries,
    infer_industry,
)


def test_infers_logistics_profile() -> None:
    profile, confidence = infer_industry(
        "International freight, customs, warehouse and logistics services."
    )

    assert profile.key == "logistics"
    assert confidence > 0.5


def test_unknown_industry_falls_back_to_general() -> None:
    profile, confidence = infer_industry(
        "A privately owned business."
    )

    assert profile.key == "general"
    assert confidence == 0.25


def test_queries_are_company_country_and_industry_aware() -> None:
    identity = build_company_identity(
        "B.H. International",
        country="Bangladesh",
        industry="Logistics and Transportation",
    )
    profile, _ = infer_industry(
        "",
        declared_industry="Logistics and Transportation",
    )

    queries = build_live_search_queries(
        identity,
        profile,
        year=2026,
    )

    assert len(queries) == 4
    assert all(
        '"B.H. International"' in query
        for query in queries
    )
    assert any(
        "customs violation" in query
        for query in queries
    )
    assert any(
        '"Bangladesh"' in query
        for query in queries
    )
