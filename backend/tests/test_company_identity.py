from core.company_identity import (
    build_company_identity,
    company_mentioned,
)


def test_generic_name_requires_context() -> None:
    identity = build_company_identity(
        "ABC Trading"
    )

    assert identity.status == "AMBIGUOUS"
    assert identity.confidence == 0.25


def test_generic_name_with_country_and_website_resolves() -> None:
    identity = build_company_identity(
        "ABC Trading",
        country="Bangladesh",
        website="abctrading.example",
    )

    assert identity.status == "RESOLVED"
    assert identity.website_domain == "abctrading.example"


def test_entity_match_uses_alias_or_official_domain() -> None:
    identity = build_company_identity(
        "Microsoft Corporation",
        aliases=["Microsoft"],
        website="https://www.microsoft.com",
    )

    assert company_mentioned(
        identity,
        "Microsoft confirmed a service update.",
    )
    assert company_mentioned(
        identity,
        "We published a service update.",
        source_url="https://learn.microsoft.com/report",
    )
    assert not company_mentioned(
        identity,
        "Google confirmed a service update.",
    )
