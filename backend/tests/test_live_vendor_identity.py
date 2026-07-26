"""Offline tests for live vendor identity discovery."""

from types import SimpleNamespace

from core.live_vendor_identity import (
    LiveVendorIdentityCollector,
    build_identity_queries,
    classify_identity_source,
    result_to_candidate_evidence,
)


def _request(**overrides):
    values = {
        "vendor_name": "ABC Trading",
        "country": None,
        "city": None,
        "website": None,
        "industry": None,
        "language": "EN",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeSERP:
    def __init__(
        self,
        responses=None,
        error=None,
    ):
        self.responses = list(
            responses or []
        )
        self.error = error
        self.calls = []

    async def search(
        self,
        query,
        num_results=10,
        lang="en",
    ):
        self.calls.append(
            {
                "query": query,
                "num_results": num_results,
                "lang": lang,
            }
        )

        if self.error:
            raise self.error

        if self.responses:
            return self.responses.pop(0)

        return []


class FakeMCP:
    def __init__(
        self,
        results=None,
        error=None,
    ):
        self.results = list(
            results or []
        )
        self.error = error
        self.calls = []

    async def search(
        self,
        query,
        limit=10,
    ):
        self.calls.append(
            {
                "query": query,
                "limit": limit,
            }
        )

        if self.error:
            raise self.error

        return list(
            self.results
        )


def test_queries_include_identity_context() -> None:
    queries = build_identity_queries(
        _request(
            country="Bangladesh",
            city="Chattogram",
            industry="Logistics",
        )
    )

    assert len(queries) == 3
    assert all(
        '"ABC Trading"' in query
        for query in queries
    )
    assert any(
        '"Bangladesh"' in query
        for query in queries
    )
    assert any(
        "company registry" in query
        for query in queries
    )


def test_requested_website_is_classified_official() -> None:
    quality = classify_identity_source(
        "https://www.abctrading.example/about",
        requested_website_domain=(
            "abctrading.example"
        ),
        combined_text="ABC Trading About Us",
    )

    assert quality == "OFFICIAL_WEBSITE"


def test_government_registry_is_authoritative() -> None:
    quality = classify_identity_source(
        "https://registry.example.gov/company/123",
        requested_website_domain=None,
        combined_text="ABC Trading registration",
    )

    assert quality == "AUTHORITATIVE"


def test_unrelated_search_result_is_rejected() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "Completely Different Company",
            "url": "https://different.example",
            "snippet": "Unrelated business profile",
            "source": "bright_data_serp",
        },
    )

    assert record is None


def test_country_is_inferred_from_country_tld() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading Official Company",
            "url": "https://abctrading.com.bd",
            "snippet": "Import and logistics company",
            "source": "bright_data_serp",
        },
    )

    assert record is not None
    assert record.country == "Bangladesh"
    assert record.source_quality == "OFFICIAL_WEBSITE"


def test_collector_combines_serp_and_mcp_without_scraping() -> None:
    serp = FakeSERP(
        responses=[
            [
                {
                    "title": "ABC Trading Official Company",
                    "url": "https://abctrading.com.bd",
                    "snippet": "Logistics company in Bangladesh",
                    "source": "bright_data_serp",
                }
            ],
            [
                {
                    "title": "ABC Trading Pte. Ltd.",
                    "url": "https://abctrading.sg",
                    "snippet": "Wholesale company in Singapore",
                    "source": "bright_data_serp",
                }
            ],
        ]
    )
    mcp = FakeMCP(
        results=[
            {
                "title": "ABC Trading company profile",
                "url": "https://www.linkedin.com/company/abc-trading",
                "snippet": "Company profile",
                "source": "bright_data_remote_mcp",
            }
        ]
    )

    collector = LiveVendorIdentityCollector(
        serp=serp,
        mcp=mcp,
    )

    import asyncio

    batch = asyncio.run(
        collector.collect(
            _request()
        )
    )

    assert batch.search_performed is True
    assert len(serp.calls) == 2
    assert len(mcp.calls) == 1
    assert len(batch.queries_executed) == 3
    assert {
        record.country
        for record in batch.records
        if record.country
    } == {
        "Bangladesh",
        "Singapore",
    }
    assert "Bright Data SERP" in batch.providers
    assert "Bright Data Remote MCP" in batch.providers


def test_provider_failure_is_isolated() -> None:
    serp = FakeSERP(
        error=RuntimeError(
            "controlled failure"
        )
    )
    mcp = FakeMCP(
        results=[
            {
                "title": "ABC Trading Official Company",
                "url": "https://abctrading.example",
                "snippet": "Official company website",
                "source": "bright_data_remote_mcp",
            }
        ]
    )

    collector = LiveVendorIdentityCollector(
        serp=serp,
        mcp=mcp,
    )

    import asyncio

    batch = asyncio.run(
        collector.collect(
            _request()
        )
    )

    assert batch.records
    assert any(
        "Bright Data SERP" in warning
        for warning in batch.warnings
    )
    assert "Bright Data Remote MCP" in batch.providers


def test_duplicate_urls_are_removed() -> None:
    duplicate = {
        "title": "ABC Trading Official Company",
        "url": "https://abctrading.example",
        "snippet": "Official company website",
        "source": "bright_data_serp",
    }

    collector = LiveVendorIdentityCollector(
        serp=FakeSERP(
            responses=[
                [duplicate],
                [duplicate],
            ]
        ),
        mcp=FakeMCP(
            results=[duplicate]
        ),
    )

    import asyncio

    batch = asyncio.run(
        collector.collect(
            _request()
        )
    )

    assert len(batch.records) == 1
