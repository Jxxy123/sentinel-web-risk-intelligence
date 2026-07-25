from core.serp_parser import parse_google_serp_html


SAMPLE_SERP_HTML = """
<html>
  <body>
    <div class="g">
      <a href="https://brightdata.com/">
        <h3>Bright Data Official Website</h3>
      </a>
      <div class="VwiC3b">
        Web data platform and scraping infrastructure.
      </div>
    </div>

    <div class="MjjYud">
      <a href="https://docs.brightdata.com/">
        <h3>Bright Data Documentation</h3>
      </a>
      <div class="IsZvec">
        Official product documentation and API guides.
      </div>
    </div>

    <div class="g">
      <a href="https://brightdata.com/">
        <h3>Duplicate Bright Data Result</h3>
      </a>
    </div>

    <div class="g">
      <a href="https://www.google.com/search?q=internal">
        <h3>Google Internal Link</h3>
      </a>
    </div>
  </body>
</html>
"""


def test_parser_extracts_structured_results() -> None:
    results = parse_google_serp_html(SAMPLE_SERP_HTML)

    assert len(results) == 2

    assert results[0] == {
        "title": "Bright Data Official Website",
        "url": "https://brightdata.com/",
        "snippet": "Web data platform and scraping infrastructure.",
        "source": "bright_data_serp",
    }

    assert results[1]["title"] == "Bright Data Documentation"
    assert results[1]["url"] == "https://docs.brightdata.com/"
    assert results[1]["snippet"] == (
        "Official product documentation and API guides."
    )


def test_parser_removes_duplicate_urls() -> None:
    results = parse_google_serp_html(SAMPLE_SERP_HTML)

    urls = [result["url"] for result in results]

    assert urls.count("https://brightdata.com/") == 1


def test_parser_ignores_google_internal_links() -> None:
    results = parse_google_serp_html(SAMPLE_SERP_HTML)

    assert all(
        "google.com" not in result["url"]
        for result in results
    )


def test_parser_respects_result_limit() -> None:
    results = parse_google_serp_html(
        SAMPLE_SERP_HTML,
        limit=1,
    )

    assert len(results) == 1


def test_parser_handles_empty_html() -> None:
    assert parse_google_serp_html("") == []
    assert parse_google_serp_html("   ") == []


def test_parser_handles_non_positive_limit() -> None:
    assert parse_google_serp_html(
        SAMPLE_SERP_HTML,
        limit=0,
    ) == []
