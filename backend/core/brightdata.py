"""
Sentinel Web-Risk — Bright Data Integration Layer.

All live web-intelligence access flows through this module.
"""

import asyncio
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from core.config import settings
from core.serp_parser import parse_google_serp_html


SearchResult = Dict[str, str]
MAX_SERP_RESULTS = 20


class BrightDataSERPClient:
    """
    Bright Data SERP API client for real-time search intelligence.

    The client requests raw HTML from the configured Bright Data SERP zone
    and converts it into structured Sentinel search results using the tested
    local parser.
    """

    BASE_URL = "https://api.brightdata.com/request"

    def __init__(self) -> None:
        self.api_key = settings.bright_data_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def search(
        self,
        query: str,
        num_results: int = 10,
        lang: str = "en",
    ) -> List[SearchResult]:
        """Search the live web and return structured organic results."""
        normalized_query = query.strip()

        if not normalized_query or num_results <= 0:
            return []

        if not self.api_key:
            print("[SERP CONFIG ERROR] BRIGHT_DATA_API_KEY is missing.")
            return []

        if not settings.bright_data_serp_zone:
            print("[SERP CONFIG ERROR] BRIGHT_DATA_SERP_ZONE is missing.")
            return []

        result_limit = min(num_results, MAX_SERP_RESULTS)
        encoded_query = quote_plus(normalized_query)

        payload = {
            "zone": settings.bright_data_serp_zone,
            "url": (
                "https://www.google.com/search"
                f"?q={encoded_query}&hl={lang}&num={result_limit}"
            ),
            "format": "raw",
            "data_format": "html",
        }

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers=self.headers,
                    json=payload,
                )

            response.raise_for_status()

            results = parse_google_serp_html(
                response.text,
                limit=result_limit,
            )

            if results:
                print(
                    f"[SERP] query='{normalized_query[:50]}' "
                    f"→ {len(results)} structured results"
                )
            else:
                print(
                    f"[SERP PARSER WARN] query='{normalized_query[:50]}' "
                    "→ Bright Data returned HTML, but no structured "
                    "organic results were extracted"
                )

            return results

        except httpx.HTTPStatusError as error:
            print(
                "[SERP HTTP ERROR] "
                f"status={error.response.status_code}"
            )
            return []

        except httpx.RequestError as error:
            print(
                "[SERP NETWORK ERROR] "
                f"{type(error).__name__}"
            )
            return []

        except Exception as error:
            print(
                "[SERP PARSER ERROR] "
                f"{type(error).__name__}: {error}"
            )
            return []

    async def search_vendor_news(
        self,
        vendor_name: str,
        lang: str = "en",
    ) -> List[SearchResult]:
        """
        Gather vendor-risk signals through multiple objective search queries.

        Results are accepted only when the vendor name appears in the title
        or snippet, and duplicate URLs are removed.
        """
        normalized_vendor = vendor_name.strip()

        if not normalized_vendor:
            return []

        compact_vendor = (
            normalized_vendor
            .lower()
            .replace(" ", "")
        )

        if "." in compact_vendor:
            target_domain = compact_vendor
        else:
            target_domain = f"{compact_vendor}.com"

        exclusion_syntax = f" -site:{target_domain}"

        queries = [
            (
                f'"{normalized_vendor}" corporate financial stability'
                f"{exclusion_syntax}"
            ),
            (
                f'"{normalized_vendor}" corporate layoffs '
                f'OR "restructuring" operations{exclusion_syntax}'
            ),
            (
                f'"{normalized_vendor}" regulatory lawsuit '
                f"OR investigation violation{exclusion_syntax}"
            ),
            (
                f'"{normalized_vendor}" risk advisory '
                f"OR operational performance telemetry{exclusion_syntax}"
            ),
        ]

        vendor_lower = normalized_vendor.lower()
        all_results: List[SearchResult] = []
        seen_urls: set[str] = set()

        for index, search_query in enumerate(queries):
            results = await self.search(
                search_query,
                num_results=5,
                lang=lang,
            )

            for result in results:
                combined_text = (
                    f"{result.get('title', '')} "
                    f"{result.get('snippet', '')}"
                ).lower()
                result_url = result.get("url", "")

                if (
                    vendor_lower in combined_text
                    and result_url
                    and result_url not in seen_urls
                ):
                    all_results.append(result)
                    seen_urls.add(result_url)

            if index < len(queries) - 1:
                await asyncio.sleep(0.5)

        return all_results


class BrightDataWebUnlocker:
    """
    Bright Data Web Unlocker client for protected or dynamic web pages.
    """

    def __init__(self) -> None:
        self.api_key = settings.bright_data_api_key
        self.base_url = settings.bright_data_web_unlocker_url

    async def fetch_url(
        self,
        url: str,
        render_js: bool = True,
    ) -> Optional[str]:
        """Fetch a URL through Bright Data Web Unlocker."""
        if not self.api_key:
            print(
                "[WEB UNLOCKER CONFIG ERROR] "
                "BRIGHT_DATA_API_KEY is missing."
            )
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "zone": settings.bright_data_web_unlocker_zone,
            "url": url,
            "format": "raw",
        }

        if render_js:
            payload["render"] = "html"

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )

            response.raise_for_status()
            return response.text

        except httpx.HTTPStatusError as error:
            print(
                "[WEB UNLOCKER HTTP ERROR] "
                f"status={error.response.status_code}; url={url}"
            )
            return None

        except httpx.RequestError as error:
            print(
                "[WEB UNLOCKER NETWORK ERROR] "
                f"{type(error).__name__}; url={url}"
            )
            return None

        except Exception as error:
            print(
                "[WEB UNLOCKER ERROR] "
                f"{type(error).__name__}: {error}; url={url}"
            )
            return None

    async def fetch_legal_filing(
        self,
        company_name: str,
    ) -> Optional[str]:
        """Attempt to fetch public SEC company filings."""
        encoded_company = quote_plus(company_name.strip())
        url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?company={encoded_company}&action=getcompany"
        )
        return await self.fetch_url(url, render_js=False)

    async def fetch_news_portal(
        self,
        url: str,
    ) -> Optional[str]:
        """Fetch a potentially restricted or dynamic news page."""
        return await self.fetch_url(url, render_js=True)


class BrightDataProxyClient:
    """
    Bright Data Proxy Network client for regionally restricted resources.
    """

    def __init__(self) -> None:
        self.proxy_url = (
            f"http://{settings.bright_data_proxy_user}:"
            f"{settings.bright_data_proxy_pass}@"
            f"{settings.bright_data_proxy_host}:"
            f"{settings.bright_data_proxy_port}"
        )

    async def fetch_with_proxy(
        self,
        url: str,
        country: str = "us",
    ) -> Optional[str]:
        """
        Fetch a URL through the configured Bright Data proxy.

        The country argument is retained for API compatibility. Country-level
        routing must be configured in the proxy credentials or zone settings.
        """
        _ = country

        if (
            not settings.bright_data_proxy_user
            or not settings.bright_data_proxy_pass
        ):
            print(
                "[PROXY CONFIG ERROR] Bright Data proxy credentials "
                "are missing."
            )
            return None

        proxies = {
            "http://": self.proxy_url,
            "https://": self.proxy_url,
        }

        try:
            async with httpx.AsyncClient(
                proxies=proxies,
                timeout=30,
            ) as client:
                response = await client.get(url)

            response.raise_for_status()
            return response.text

        except httpx.HTTPStatusError as error:
            print(
                "[PROXY HTTP ERROR] "
                f"status={error.response.status_code}"
            )
            return None

        except httpx.RequestError as error:
            print(
                "[PROXY NETWORK ERROR] "
                f"{type(error).__name__}"
            )
            return None

        except Exception as error:
            print(
                "[PROXY ERROR] "
                f"{type(error).__name__}: {error}"
            )
            return None


class BrightDataMCPClient:
    """
    MCP-style compatibility adapter for Sentinel agents.

    Search routes through the real SERP client. Scraping routes through
    Web Unlocker. This class does not independently open a remote MCP session.
    """

    MCP_TOOL_DESCRIPTIONS = {
        "search_engine": "Search the live web for any query in real time",
        "scrape_as_markdown": (
            "Scrape a URL and return content for downstream processing"
        ),
        "web_data_feed": "Access configured structured web-data feeds",
    }

    def __init__(self) -> None:
        self.api_key = settings.bright_data_api_key

    def get_tools_config(self) -> Dict[str, object]:
        """Return the Bright Data MCP-style tool configuration."""
        return {
            "mcp_url": "https://mcp.brightdata.com",
            "api_key": self.api_key,
            "tools": list(self.MCP_TOOL_DESCRIPTIONS.keys()),
        }

    async def search(
        self,
        query: str,
    ) -> List[SearchResult]:
        """Route search through the SERP pipeline with traceability tags."""
        serp = BrightDataSERPClient()
        results = await serp.search(query)

        for result in results:
            result["source"] = "bright_data_mcp"

        return results

    async def scrape(
        self,
        url: str,
    ) -> Optional[str]:
        """Route scraping through Web Unlocker."""
        unlocker = BrightDataWebUnlocker()
        return await unlocker.fetch_url(url)


serp_client = BrightDataSERPClient()
web_unlocker = BrightDataWebUnlocker()
proxy_client = BrightDataProxyClient()
mcp_client = BrightDataMCPClient()
