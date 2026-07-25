"""
Pure HTML parser for Google-style SERP pages returned by Bright Data.

This module performs no network requests.
"""

from typing import Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup


SNIPPET_SELECTORS = (
    ".VwiC3b",
    ".aCOpRe",
    ".IsZvec",
    "[data-sncf]",
    "[data-snhf]",
)


def _is_valid_result_url(url: str) -> bool:
    """Return True only for normal public HTTP(S) result URLs."""
    if not url:
        return False

    parsed = urlparse(url)

    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and "google.com" not in parsed.netloc.lower()
    )


def parse_google_serp_html(
    html: str,
    limit: int = 10,
) -> List[Dict[str, str]]:
    """
    Extract organic search-result titles, URLs, and snippets.

    The parser is deterministic and makes no external calls.
    """
    if not html or not html.strip() or limit <= 0:
        return []

    soup = BeautifulSoup(html, "lxml")
    results: List[Dict[str, str]] = []
    seen_urls: set[str] = set()

    # Common containers used in Google search-result HTML.
    containers = soup.select("div.g, div.MjjYud")

    # Fallback for layouts where result containers have changed.
    if not containers:
        containers = [
            heading.parent
            for heading in soup.select("h3")
            if heading.parent is not None
        ]

    for container in containers:
        heading = container.select_one("h3")

        if heading is None:
            continue

        anchor = heading.find_parent("a")

        if anchor is None:
            anchor = container.select_one("a[href]")

        if anchor is None:
            continue

        url = str(anchor.get("href", "")).strip()

        if not _is_valid_result_url(url):
            continue

        if url in seen_urls:
            continue

        title = heading.get_text(" ", strip=True)

        if not title:
            continue

        snippet = ""

        for selector in SNIPPET_SELECTORS:
            snippet_element = container.select_one(selector)

            if snippet_element is not None:
                snippet = snippet_element.get_text(" ", strip=True)
                break

        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": "bright_data_serp",
            }
        )

        seen_urls.add(url)

        if len(results) >= limit:
            break

    return results
