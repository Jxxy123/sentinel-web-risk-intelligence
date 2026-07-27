"""Adversarial offline tests for live vendor identity discovery."""

import asyncio
from types import SimpleNamespace

from core.live_vendor_identity import (
    LiveVendorIdentityCollector,
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
    def __init__(self, responses=None):
        self.responses = list(
            responses or []
        )

    async def search(
        self,
        query,
        num_results=10,
        lang="en",
    ):
        del query, num_results, lang

        if self.responses:
            return self.responses.pop(0)

        return []


class FakeMCP:
    def __init__(self, results=None):
        self.results = list(
            results or []
        )

    async def search(
        self,
        query,
        limit=10,
    ):
        del query, limit
        return list(
            self.results
        )


def test_user_provided_domain_is_official() -> None:
    quality = classify_identity_source(
        "https://www.abctrading.example/about",
        requested_name="ABC Trading",
        requested_website_domain=(
            "abctrading.example"
        ),
        combined_text="ABC Trading About Us",
    )

    assert quality == "OFFICIAL_WEBSITE"


def test_pdf_guide_is_not_a_candidate() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading setup guide",
            "url": (
                "https://www.kaizencpa.com/download/"
                "Guide_to_Setting_up_A_Company.pdf"
            ),
            "snippet": (
                "Guide discussing ABC Trading as an example."
            ),
        },
    )

    assert record is None


def test_blog_article_is_not_a_candidate() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "Trading as ABC Trading",
            "url": (
                "https://www.thecompanywarehouse.co.uk/"
                "blog/trading-as-company-names"
            ),
            "snippet": "General company naming guidance.",
        },
    )

    assert record is None


def test_category_archive_is_not_a_candidate() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading industry news",
            "url": "https://corpprom.com/category/news/page/5/",
            "snippet": "Archive mentioning ABC Trading.",
        },
    )

    assert record is None


def test_directory_is_not_official_website() -> None:
    quality = classify_identity_source(
        "https://pitchbook.com/profiles/company/123",
        requested_name="ABC Trading",
        requested_website_domain=None,
        combined_text="ABC Trading company profile",
    )

    assert quality == "REPUTABLE_BUSINESS_DIRECTORY"


def test_matching_domain_is_only_possible_without_user_confirmation() -> None:
    quality = classify_identity_source(
        "https://abctrading.example/about-us",
        requested_name="ABC Trading",
        requested_website_domain=None,
        combined_text="ABC Trading About Us",
    )

    assert quality == "POSSIBLE_COMPANY_WEBSITE"


def test_unrelated_chamber_article_is_rejected() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading and company law",
            "url": (
                "https://www.handelskammer-hamburg.de/"
                "company-law/article"
            ),
            "snippet": "General legal information.",
        },
    )

    assert record is None


def test_collector_keeps_rejection_audit() -> None:
    collector = LiveVendorIdentityCollector(
        serp=FakeSERP(
            responses=[
                [
                    {
                        "title": "ABC Trading setup guide",
                        "url": (
                            "https://kaizencpa.com/download/"
                            "guide.pdf"
                        ),
                        "snippet": "General guide.",
                    }
                ],
                [
                    {
                        "title": "ABC Trading About Us",
                        "url": (
                            "https://abctrading.example/"
                            "about-us"
                        ),
                        "snippet": "ABC Trading company.",
                    }
                ],
            ]
        ),
        mcp=FakeMCP(
            results=[]
        ),
    )

    batch = asyncio.run(
        collector.collect(
            _request()
        )
    )

    assert len(batch.records) == 1
    assert len(batch.rejected_results) == 1
    assert (
        "PDF"
        in batch.rejected_results[0][
            "reason"
        ]
    )



def test_news_article_is_context_not_identity_candidate() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading announces expansion",
            "url": "https://www.reuters.com/business/abc-trading",
            "snippet": "News coverage about ABC Trading.",
        },
    )

    assert record is None


def test_social_profile_is_not_identity_candidate() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading",
            "url": "https://www.facebook.com/abctrading",
            "snippet": "ABC Trading social page.",
        },
    )

    assert record is None
