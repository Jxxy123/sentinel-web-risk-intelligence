"""
Sentinel Web-Risk — Bright Data Integration Layer
All web intelligence access flows through this module.
"""
import httpx
import json
import asyncio
from urllib.parse import quote_plus
from typing import List, Dict, Optional, Any
from core.config import settings


class BrightDataSERPClient:
    """
    Bright Data SERP API — real-time search intelligence.
    Used by the Recon Agent to gather live news and signals.
    """

    BASE_URL = "https://api.brightdata.com/request"

    def __init__(self):
        self.api_key = settings.bright_data_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def search(self, query: str, num_results: int = 10, lang: str = "en") -> List[Dict]:
        """Search the live web via Bright Data SERP API."""
        encoded_query = quote_plus(query)

        payload = {
            "zone": "serp_api1",
            "url": f"https://www.google.com/search?q={encoded_query}&hl={lang}",
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                organic = data.get("organic")  # Path 1: direct

                if not organic:
                    raw_body = data.get("body", "")
                    if isinstance(raw_body, str) and raw_body.strip():
                        try:
                            # Path 2: body is a JSON string
                            body_json = json.loads(raw_body)
                            organic = body_json.get("organic", [])
                        except (json.JSONDecodeError, ValueError):
                            # Path 3: body is HTML — try a lightweight BeautifulSoup parse
                            try:
                                from bs4 import BeautifulSoup
                                soup = BeautifulSoup(raw_body, "lxml")
                                organic = []
                                # Extract search result blocks (Google's standard markup)
                                for g in soup.select("div.g")[:num_results]:
                                    title_el = g.select_one("h3")
                                    link_el = g.select_one("a")
                                    snippet_el = g.select_one("div[data-sncf], span.aCOpRe, div.IsZvec")
                                    if title_el and link_el:
                                        organic.append({
                                            "title": title_el.get_text(),
                                            "link": link_el.get("href", ""),
                                            "snippet": snippet_el.get_text() if snippet_el else "",
                                        })
                            except Exception as bs_err:
                                print(f"[SERP BS4 WARN] {bs_err}")
                                organic = []
                    elif isinstance(raw_body, dict):
                        # Path 2b: body is already a parsed dict
                        organic = raw_body.get("organic", [])

                results = []
                for item in (organic or []):
                    title = item.get("title", "")
                    url = item.get("link", "") or item.get("url", "")
                    snippet = item.get("snippet", "") or item.get("description", "")
                    if title or url:
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "source": "bright_data_serp",
                        })

                print(f"[SERP] query='{query[:50]}' → {len(results)} results (body keys: {list(data.keys())})")
                return results

        except Exception as e:
            print(f"[SERP ERROR] {e}")
            return []

    async def search_vendor_news(self, vendor_name: str, lang: str = "en") -> List[Dict]:
        """
        Multi-query vendor news intelligence with dynamic domain isolation boundaries.
        Removes hardcoded lists and works dynamically for any company searched.
        """
        clean_input = vendor_name.lower().strip().replace(" ", "")
        
        if "." in clean_input:
            target_domain = clean_input
        else:
            target_domain = f"{clean_input}.com"

        exclusion_syntax = f" -site:{target_domain}"

        # Objective, unbiased queries to track raw performance without hallucinating synthetic macro crashes
        queries = [
            f'"{vendor_name}" corporate financial stability{exclusion_syntax}',
            f'"{vendor_name}" corporate layoffs OR "restructuring" operations{exclusion_syntax}',
            f'"{vendor_name}" regulatory lawsuit OR investigation violation{exclusion_syntax}',
            f'"{vendor_name}" risk advisory OR operational performance telemetry{exclusion_syntax}',
        ]
        
        all_results = []
        vendor_lower = vendor_name.lower().strip()

        for query in queries:
            results = await self.search(query, num_results=5, lang=lang)
            
            # Anti-hallucination Filter: Only accept sources explicitly naming the vendor entity context
            for r in results:
                combined_text = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
                if vendor_lower in combined_text:
                    all_results.append(r)
                    
            await asyncio.sleep(0.5)  # Rate limit protection
            
        return all_results


class BrightDataWebUnlocker:
    """
    Bright Data Web Unlocker — bypasses geo-restrictions, JS rendering,
    and CAPTCHAs to access protected intelligence sources.
    """

    def __init__(self):
        self.api_key = settings.bright_data_api_key
        self.base_url = settings.bright_data_web_unlocker_url

    async def fetch_url(self, url: str, render_js: bool = True) -> Optional[str]:
        """Fetch any URL through Bright Data Web Unlocker."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "zone": "web_unlocker1",
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
        except Exception as e:
            print(f"[WEB UNLOCKER ERROR] URL: {url} — {e}")
            return None

    async def fetch_legal_filing(self, company_name: str) -> Optional[str]:
        """Attempt to fetch EDGAR or public legal filings."""
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?company={company_name}&action=getcompany"
        return await self.fetch_url(url, render_js=False)

    async def fetch_news_portal(self, url: str) -> Optional[str]:
        """Fetch geo-restricted news portals."""
        return await self.fetch_url(url, render_js=True)


class BrightDataProxyClient:
    """
    Bright Data Proxy Network — access regionally-restricted intelligence.
    """

    def __init__(self):
        self.proxy_url = (
            f"http://{settings.bright_data_proxy_user}:"
            f"{settings.bright_data_proxy_pass}@"
            f"{settings.bright_data_proxy_host}:{settings.bright_data_proxy_port}"
        )

    async def fetch_with_proxy(self, url: str, country: str = "us") -> Optional[str]:
        """Fetch URL through a specific country's proxy."""
        proxies = {
            "http://": self.proxy_url,
            "https://": self.proxy_url,
        }
        try:
            async with httpx.AsyncClient(proxies=proxies, timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            print(f"[PROXY ERROR] {e}")
            return None


class BrightDataMCPClient:
    """
    Bright Data MCP Server Integration.
    Provides AI agents with direct web access capability.
    """

    MCP_TOOL_DESCRIPTIONS = {
        "search_engine": "Search the live web for any query in real time",
        "scrape_as_markdown": "Scrape any URL and return structured Markdown",
        "web_data_feed": "Access structured web data feeds",
    }

    def __init__(self):
        self.api_key = settings.bright_data_api_key

    def get_tools_config(self) -> Dict:
        """Return MCP tool configuration for CrewAI agents."""
        return {
            "mcp_url": "https://mcp.brightdata.com",
            "api_key": self.api_key,
            "tools": list(self.MCP_TOOL_DESCRIPTIONS.keys()),
        }

    async def search(self, query: str) -> List[Dict]:
        """Route search through Bright Data MCP -> SERP pipeline with traceability tags."""
        serp = BrightDataSERPClient()
        results = await serp.search(query)
        for r in results:
            r["source"] = "bright_data_mcp"
        return results

    async def scrape(self, url: str) -> Optional[str]:
        """Proxy to Web Unlocker for MCP-style scraping."""
        unlocker = BrightDataWebUnlocker()
        return await unlocker.fetch_url(url)


# Singleton instances
serp_client = BrightDataSERPClient()
web_unlocker = BrightDataWebUnlocker()
proxy_client = BrightDataProxyClient()
mcp_client = BrightDataMCPClient()