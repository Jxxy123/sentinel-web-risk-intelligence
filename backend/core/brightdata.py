"""
Sentinel Web-Risk — Bright Data Integration Layer.

All live web-intelligence access flows through this module.
"""

import asyncio
from typing import Dict, List, Optional
from urllib.parse import quote, quote_plus, urlparse

import httpx

from core.config import ProxyType, settings
from core.serp_parser import parse_google_serp_html


SearchResult = Dict[str, str]

MAX_SERP_RESULTS = 20
SERP_TIMEOUT_SECONDS = 45
WEB_UNLOCKER_TIMEOUT_SECONDS = 45
PROXY_TIMEOUT_SECONDS = 30

WEB_UNLOCKER_ERROR_MARKERS = (
    "request failed",
    "bad_endpoint",
    "not available for immediate access mode",
    "ask your account manager",
    "access denied",
    "zone is not active",
    "invalid zone",
)


def _is_valid_http_url(url: str) -> bool:
    """Return True only for absolute HTTP or HTTPS URLs."""
    parsed = urlparse(url)

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


class BrightDataSERPClient:
    """
    Bright Data SERP API client for real-time search intelligence.

    The client requests raw HTML from the configured Bright Data SERP zone
    and converts it into structured Sentinel search results using the tested
    local parser.
    """

    def __init__(self) -> None:
        self.api_key = settings.bright_data_api_key
        self.base_url = settings.bright_data_serp_api_url

        # Retained as a public attribute for compatibility with existing
        # tests and integrations that safely override test credentials.
        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_headers(self) -> Dict[str, str]:
        """
        Return a copy of the configured request headers.

        Returning a copy prevents callers from accidentally changing the
        client's stored header dictionary during a request.
        """
        return dict(self.headers)

    async def search(
        self,
        query: str,
        num_results: int = 10,
        lang: str = "en",
    ) -> List[SearchResult]:
        """Search the live web and return structured organic results."""
        normalized_query = query.strip()
        normalized_language = lang.strip().lower() or "en"

        if not normalized_query or num_results <= 0:
            return []

        if not self.api_key:
            print("[SERP CONFIG ERROR] BRIGHT_DATA_API_KEY is missing.")
            return []

        if not settings.bright_data_serp_zone:
            print("[SERP CONFIG ERROR] BRIGHT_DATA_SERP_ZONE is missing.")
            return []

        if not self.base_url:
            print(
                "[SERP CONFIG ERROR] "
                "BRIGHT_DATA_SERP_API_URL is missing."
            )
            return []

        result_limit = min(num_results, MAX_SERP_RESULTS)
        encoded_query = quote_plus(normalized_query)

        payload = {
            "zone": settings.bright_data_serp_zone,
            "url": (
                "https://www.google.com/search"
                f"?q={encoded_query}"
                f"&hl={normalized_language}"
                f"&num={result_limit}"
            ),
            "format": "raw",
            "data_format": "html",
        }

        try:
            async with httpx.AsyncClient(
                timeout=SERP_TIMEOUT_SECONDS,
            ) as client:
                response = await client.post(
                    self.base_url,
                    headers=self._build_headers(),
                    json=payload,
                )

            response.raise_for_status()

            results = parse_google_serp_html(
                response.text,
                limit=result_limit,
            )

            if results:
                print(
                    f"[SERP SUCCESS] query='{normalized_query[:50]}' "
                    f"results={len(results)}"
                )
            else:
                print(
                    f"[SERP PARSER WARN] query='{normalized_query[:50]}' "
                    "Bright Data returned HTML, but no structured "
                    "organic results were extracted."
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
                f"error={type(error).__name__}"
            )
            return []

        except Exception as error:
            print(
                "[SERP PARSER ERROR] "
                f"error={type(error).__name__}: {error}"
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

        compact_vendor = normalized_vendor.lower().replace(" ", "")

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
                result_url = result.get("url", "").strip()

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

    @staticmethod
    def _is_error_response(
        content: str,
    ) -> bool:
        """
        Detect Bright Data error messages returned with HTTP 200.

        Bright Data can return a successful HTTP status while placing an
        error such as ``bad_endpoint`` inside the response body. Such text
        must never be passed to CrewAI as retrieved evidence.
        """
        normalized = content.strip().lower()

        if not normalized:
            return True

        inspected_content = normalized[:2000]

        return any(
            marker in inspected_content
            for marker in WEB_UNLOCKER_ERROR_MARKERS
        )

    async def fetch_url(
        self,
        url: str,
        render_js: bool = True,
    ) -> Optional[str]:
        """Fetch one URL through Bright Data Web Unlocker."""
        normalized_url = url.strip()

        if not normalized_url:
            print("[WEB UNLOCKER INPUT ERROR] URL is empty.")
            return None

        if not _is_valid_http_url(normalized_url):
            print(
                "[WEB UNLOCKER INPUT ERROR] "
                "URL must use http:// or https://."
            )
            return None

        if not self.api_key:
            print(
                "[WEB UNLOCKER CONFIG ERROR] "
                "BRIGHT_DATA_API_KEY is missing."
            )
            return None

        if not settings.bright_data_web_unlocker_zone:
            print(
                "[WEB UNLOCKER CONFIG ERROR] "
                "BRIGHT_DATA_WEB_UNLOCKER_ZONE is missing."
            )
            return None

        if not self.base_url:
            print(
                "[WEB UNLOCKER CONFIG ERROR] "
                "BRIGHT_DATA_WEB_UNLOCKER_URL is missing."
            )
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "zone": settings.bright_data_web_unlocker_zone,
            "url": normalized_url,
            "format": "raw",
        }

        if render_js:
            payload["render"] = "html"

        try:
            async with httpx.AsyncClient(
                timeout=WEB_UNLOCKER_TIMEOUT_SECONDS,
            ) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )

            response.raise_for_status()

            content = response.text.strip()

            if self._is_error_response(content):
                print(
                    "[WEB UNLOCKER REJECTED] "
                    "Bright Data returned an error body "
                    f"for url={normalized_url}"
                )
                return None

            print(
                "[WEB UNLOCKER SUCCESS] "
                f"status={response.status_code}; "
                f"characters={len(content)}"
            )
            return content

        except httpx.HTTPStatusError as error:
            print(
                "[WEB UNLOCKER HTTP ERROR] "
                f"status={error.response.status_code}; "
                f"url={normalized_url}"
            )
            return None

        except httpx.RequestError as error:
            print(
                "[WEB UNLOCKER NETWORK ERROR] "
                f"error={type(error).__name__}; "
                f"url={normalized_url}"
            )
            return None

        except Exception as error:
            print(
                "[WEB UNLOCKER ERROR] "
                f"error={type(error).__name__}: {error}; "
                f"url={normalized_url}"
            )
            return None

    async def fetch_legal_filing(
        self,
        company_name: str,
    ) -> Optional[str]:
        """Attempt to fetch public SEC company filings."""
        normalized_company = company_name.strip()

        if not normalized_company:
            return None

        encoded_company = quote_plus(normalized_company)
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
    Bright Data dual-proxy client.

    Data Center is the default proxy route. ISP is available as an explicit
    higher-trust route or as a fallback after Data Center failure.
    """

    def __init__(
        self,
        default_proxy_type: ProxyType = "data_center",
    ) -> None:
        self.default_proxy_type = self._validate_proxy_type(
            default_proxy_type
        )

    @staticmethod
    def _validate_proxy_type(proxy_type: str) -> ProxyType:
        """Validate and normalize the selected proxy product."""
        if proxy_type == "data_center":
            return "data_center"

        if proxy_type == "isp":
            return "isp"

        raise ValueError(
            "proxy_type must be 'data_center' or 'isp'."
        )

    def _build_proxy_url(
        self,
        proxy_type: ProxyType,
    ) -> Optional[str]:
        """Build a safely encoded authenticated Bright Data proxy URL."""
        username, password = settings.get_proxy_credentials(
            proxy_type
        )

        if not username or not password:
            return None

        encoded_username = quote(username, safe="")
        encoded_password = quote(password, safe="")

        return (
            f"http://{encoded_username}:{encoded_password}@"
            f"{settings.bright_data_proxy_host}:"
            f"{settings.bright_data_proxy_port}"
        )

    async def fetch_with_proxy(
        self,
        url: str,
        country: str = "us",
        proxy_type: Optional[ProxyType] = None,
    ) -> Optional[str]:
        """
        Fetch one URL using the selected Bright Data proxy product.

        Existing Sentinel calls continue using Data Center by default.
        ISP is used only when explicitly selected.

        Country routing remains controlled by the Bright Data username or
        zone configuration. The country argument is retained for compatibility
        with the existing orchestrator.
        """
        _ = country
        normalized_url = url.strip()

        if not normalized_url:
            print("[PROXY INPUT ERROR] URL is empty.")
            return None

        if not _is_valid_http_url(normalized_url):
            print(
                "[PROXY INPUT ERROR] "
                "URL must use http:// or https://."
            )
            return None

        try:
            selected_proxy = self._validate_proxy_type(
                proxy_type or self.default_proxy_type
            )
        except ValueError as error:
            print(f"[PROXY CONFIG ERROR] {error}")
            return None

        proxy_url = self._build_proxy_url(selected_proxy)

        if not proxy_url:
            print(
                "[PROXY CONFIG ERROR] "
                f"Missing {selected_proxy} proxy credentials."
            )
            return None

        proxies = {
            "http://": proxy_url,
            "https://": proxy_url,
        }

        try:
            async with httpx.AsyncClient(
                proxies=proxies,
                timeout=PROXY_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(normalized_url)

            response.raise_for_status()

            content = response.text.strip()

            if not content:
                print(
                    "[PROXY EMPTY RESPONSE] "
                    f"type={selected_proxy}"
                )
                return None

            print(
                "[PROXY SUCCESS] "
                f"type={selected_proxy}; "
                f"status={response.status_code}; "
                f"characters={len(content)}"
            )
            return content

        except httpx.HTTPStatusError as error:
            print(
                "[PROXY HTTP ERROR] "
                f"type={selected_proxy}; "
                f"status={error.response.status_code}"
            )
            return None

        except httpx.RequestError as error:
            print(
                "[PROXY NETWORK ERROR] "
                f"type={selected_proxy}; "
                f"error={type(error).__name__}"
            )
            return None

        except Exception as error:
            print(
                "[PROXY ERROR] "
                f"type={selected_proxy}; "
                f"error={type(error).__name__}: {error}"
            )
            return None

    async def fetch_with_fallback(
        self,
        url: str,
        country: str = "us",
    ) -> Optional[str]:
        """
        Try Data Center first and use ISP only when Data Center fails.

        This method can make two paid proxy requests when Data Center fails.
        """
        data_center_result = await self.fetch_with_proxy(
            url=url,
            country=country,
            proxy_type="data_center",
        )

        if data_center_result:
            return data_center_result

        if not settings.has_proxy_credentials("isp"):
            print(
                "[PROXY FALLBACK SKIPPED] "
                "ISP credentials are not configured."
            )
            return None

        print(
            "[PROXY FALLBACK] "
            "Data Center failed; attempting ISP."
        )

        return await self.fetch_with_proxy(
            url=url,
            country=country,
            proxy_type="isp",
        )


class BrightDataMCPClient:
    """
    Deprecated compatibility adapter for Sentinel's former MCP interface.

    This class does not open a genuine Remote MCP session. Search requests
    route through the SERP client and scrape requests route through Web
    Unlocker. Production orchestration should use
    ``core.brightdata_remote_mcp.remote_mcp_client`` instead.
    """

    MCP_TOOL_DESCRIPTIONS = {
        "search_engine": "Search the live web through the SERP client",
        "scrape_as_markdown": (
            "Retrieve page content through Web Unlocker"
        ),
    }

    def __init__(self) -> None:
        self.api_key = settings.bright_data_api_key

    def get_tools_config(self) -> Dict[str, object]:
        """Describe this compatibility adapter without claiming remote MCP."""
        return {
            "mode": "compatibility_adapter",
            "remote_mcp_session": False,
            "mcp_url": "https://mcp.brightdata.com",
            "api_key_configured": bool(self.api_key),
            "tools": list(self.MCP_TOOL_DESCRIPTIONS.keys()),
        }

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Route search through SERP with an accurate traceability tag."""
        normalized_query = query.strip()

        if not normalized_query or limit <= 0:
            return []

        serp = BrightDataSERPClient()
        results = await serp.search(
            normalized_query,
            num_results=limit,
        )

        for result in results:
            result["source"] = "bright_data_serp_adapter"

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
