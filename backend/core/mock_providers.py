"""
Deterministic external-provider replacements for automated testing.

These providers never make network requests and never consume
Bright Data or LLM credits.
"""

from typing import Dict, List, Optional
from urllib.parse import quote_plus


def _scenario_for(vendor_name: str) -> str:
    """
    Choose a deterministic synthetic scenario from the test vendor name.

    Recommended test names:
    - Stable Demo Vendor
    - Mixed Demo Vendor
    - Critical Demo Vendor
    """
    normalized = vendor_name.lower()

    if "critical" in normalized:
        return "critical"

    if "mixed" in normalized:
        return "mixed"

    return "stable"


def _build_result(
    vendor_name: str,
    index: int,
    title: str,
    snippet: str,
    source: str,
    language: str = "en",
) -> Dict:
    """Create one clearly labelled synthetic search result."""
    vendor_slug = quote_plus(vendor_name.lower())

    return {
        "title": f"[MOCK] {vendor_name}: {title}",
        "url": (
            f"https://example.com/mock-intelligence/"
            f"{vendor_slug}/{index}"
        ),
        "snippet": (
            f"Synthetic test evidence for {vendor_name}. "
            f"{snippet}"
        ),
        "source": source,
        "language": language,
        "is_mock": True,
    }


class MockBrightDataSERPClient:
    """Deterministic replacement for the Bright Data SERP client."""

    async def search(
        self,
        query: str,
        num_results: int = 10,
        lang: str = "en",
    ) -> List[Dict]:
        result_count = max(1, min(num_results, 5))

        return [
            {
                "title": f"[MOCK] Synthetic search result {index + 1}",
                "url": (
                    "https://example.com/mock-search/"
                    f"{quote_plus(query)}/{index + 1}"
                ),
                "snippet": (
                    "Synthetic result generated for automated testing. "
                    f"Query: {query}"
                ),
                "source": "mock_serp",
                "language": lang,
                "is_mock": True,
            }
            for index in range(result_count)
        ]

    async def search_vendor_news(
        self,
        vendor_name: str,
        lang: str = "en",
    ) -> List[Dict]:
        scenario = _scenario_for(vendor_name)

        scenarios = {
            "stable": [
                (
                    "Audited results published",
                    "The synthetic company reports stable operations.",
                ),
                (
                    "New product investment announced",
                    "The synthetic company continues normal expansion.",
                ),
                (
                    "Governance review completed",
                    "No material concerns were identified in this mock scenario.",
                ),
            ],
            "mixed": [
                (
                    "Operational challenges reported",
                    "The mock scenario contains operational challenges.",
                ),
                (
                    "Legal dispute disclosed",
                    "The mock scenario contains a legal dispute.",
                ),
                (
                    "Negative press increases",
                    "The mock scenario contains negative press.",
                ),
            ],
            "critical": [
                (
                    "Bankruptcy proceedings reported",
                    "The mock scenario contains bankruptcy indicators.",
                ),
                (
                    "Operations halted after shutdown",
                    "The mock scenario contains shutdown indicators.",
                ),
                (
                    "Regulatory investigation opened",
                    "The mock scenario contains a regulatory investigation.",
                ),
                (
                    "Data breach confirmed",
                    "The mock scenario contains a data breach.",
                ),
                (
                    "Public backlash escalates",
                    "The mock scenario contains public backlash.",
                ),
            ],
        }

        return [
            _build_result(
                vendor_name=vendor_name,
                index=index + 1,
                title=title,
                snippet=snippet,
                source="mock_serp",
                language=lang,
            )
            for index, (title, snippet) in enumerate(
                scenarios[scenario]
            )
        ]


class MockBrightDataWebUnlocker:
    """Deterministic replacement for Bright Data Web Unlocker."""

    async def fetch_url(
        self,
        url: str,
        render_js: bool = True,
    ) -> Optional[str]:
        return (
            "[MOCK WEB UNLOCKER CONTENT]\n"
            f"Synthetic content for URL: {url}\n"
            f"JavaScript rendering requested: {render_js}\n"
            "No external webpage was accessed."
        )

    async def fetch_legal_filing(
        self,
        company_name: str,
    ) -> Optional[str]:
        scenario = _scenario_for(company_name)

        return (
            "[MOCK LEGAL FILING]\n"
            f"Company: {company_name}\n"
            f"Synthetic scenario: {scenario}\n"
            "This content is generated only for automated testing."
        )

    async def fetch_news_portal(
        self,
        url: str,
    ) -> Optional[str]:
        return await self.fetch_url(url, render_js=True)


class MockBrightDataProxyClient:
    """Deterministic replacement for the Bright Data proxy client."""

    async def fetch_with_proxy(
        self,
        url: str,
        country: str = "us",
    ) -> Optional[str]:
        return (
            "[MOCK PROXY CONTENT]\n"
            f"Synthetic URL: {url}\n"
            f"Synthetic country route: {country}\n"
            "No proxy network was contacted."
        )


class MockBrightDataMCPClient:
    """Deterministic replacement for the current MCP-style client."""

    def get_tools_config(self) -> Dict:
        return {
            "mcp_url": "mock://bright-data-mcp",
            "api_key": "",
            "tools": [
                "search_engine",
                "scrape_as_markdown",
                "web_data_feed",
            ],
            "is_mock": True,
        }

    async def search(self, query: str) -> List[Dict]:
        return [
            {
                "title": "[MOCK MCP] Supplementary intelligence",
                "url": "https://example.com/mock-mcp/result-1",
                "snippet": (
                    "Synthetic MCP-style result generated for testing. "
                    f"Query: {query}"
                ),
                "source": "mock_mcp",
                "is_mock": True,
            }
        ]

    async def scrape(self, url: str) -> Optional[str]:
        return (
            "[MOCK MCP SCRAPE]\n"
            f"Synthetic content for URL: {url}\n"
            "No external resource was accessed."
        )


mock_serp_client = MockBrightDataSERPClient()
mock_web_unlocker = MockBrightDataWebUnlocker()
mock_proxy_client = MockBrightDataProxyClient()
mock_mcp_client = MockBrightDataMCPClient()
