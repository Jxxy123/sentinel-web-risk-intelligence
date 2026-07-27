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



def test_cpsc_recall_is_context_not_identity_evidence() -> None:
    quality = classify_identity_source(
        (
            "https://www.cpsc.gov/Recalls/1973/"
            "consumer-product-safety-commission-recall"
        ),
        requested_name="ABC Trading",
        requested_website_domain=None,
        combined_text=(
            "ABC Trading product recall hazard safety warning"
        ),
    )

    assert quality == "AUTHORITATIVE_CONTEXT"

    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Trading product recall",
            "url": (
                "https://www.cpsc.gov/Recalls/1973/"
                "consumer-product-safety-commission-recall"
            ),
            "snippet": "Product recall and hazard notice.",
        },
    )

    assert record is None


def test_government_registry_record_is_identity_evidence() -> None:
    quality = classify_identity_source(
        "https://registry.example.gov/company/ABC-123",
        requested_name="ABC Trading",
        requested_website_domain=None,
        combined_text=(
            "ABC Trading legal name registration number ABC-123 "
            "registered office company status active"
        ),
    )

    assert quality == "AUTHORITATIVE_IDENTITY"


def test_generic_government_page_defaults_to_context() -> None:
    quality = classify_identity_source(
        "https://agency.example.gov/public-information",
        requested_name="ABC Trading",
        requested_website_domain=None,
        combined_text="ABC Trading public information page",
    )

    assert quality == "AUTHORITATIVE_CONTEXT"


def test_collector_keeps_accepted_identity_audit() -> None:
    collector = LiveVendorIdentityCollector(
        serp=FakeSERP(
            responses=[
                [
                    {
                        "title": "ABC Trading company record",
                        "url": (
                            "https://registry.example.gov/"
                            "company/ABC-123"
                        ),
                        "snippet": (
                            "ABC Trading legal name registration "
                            "number ABC-123"
                        ),
                    }
                ],
                [],
            ]
        ),
        mcp=FakeMCP(results=[]),
    )

    batch = asyncio.run(
        collector.collect(
            _request()
        )
    )

    assert len(batch.records) == 1
    assert len(batch.accepted_results) == 1
    audit = batch.accepted_results[0]
    assert set(audit) == {
        "url",
        "title",
        "source_quality",
        "proposed_legal_name",
        "acceptance_reason",
    }
    assert audit["source_quality"] == "AUTHORITATIVE_IDENTITY"
    assert "registry" in audit["acceptance_reason"].lower()



def test_linkedin_post_is_rejected_not_directory_evidence() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "Business Trading Name Register in Namibia – Easy Guide",
            "url": (
                "https://www.linkedin.com/posts/example_"
                "business-trading-name-register-activity-123"
            ),
            "snippet": "General registration guidance.",
        },
    )

    assert record is None


def test_zoominfo_different_company_name_is_rejected() -> None:
    record = result_to_candidate_evidence(
        _request(),
        {
            "title": "ABC Box - Overview, News & Similar companies",
            "url": "https://www.zoominfo.com/c/abc-box-co/530495",
            "snippet": "ABC Box company profile.",
        },
    )

    assert record is None


def test_matching_directory_profile_is_a_non_scoring_lead() -> None:
    collector = LiveVendorIdentityCollector(
        serp=FakeSERP(
            responses=[
                [
                    {
                        "title": "ABC Trading Ltd. - Company Profile",
                        "url": (
                            "https://www.linkedin.com/company/"
                            "abc-trading-ltd"
                        ),
                        "snippet": "ABC Trading Ltd. company profile.",
                    }
                ],
                [],
            ]
        ),
        mcp=FakeMCP(results=[]),
    )

    batch = asyncio.run(collector.collect(_request()))

    assert batch.records == ()
    assert batch.accepted_results == ()
    assert len(batch.directory_leads) == 1
    lead = batch.directory_leads[0]
    assert lead["source_quality"] == "DIRECTORY_LEAD"
    assert "not used for identity scoring" in lead["lead_reason"]


def test_run_003_false_matches_produce_zero_identity_records() -> None:
    collector = LiveVendorIdentityCollector(
        serp=FakeSERP(
            responses=[
                [
                    {
                        "title": (
                            "Business Trading Name Register in Namibia – "
                            "Easy Guide"
                        ),
                        "url": (
                            "https://www.linkedin.com/posts/example_"
                            "business-trading-name-register-activity-123"
                        ),
                        "snippet": "General business-name guidance.",
                    }
                ],
                [
                    {
                        "title": (
                            "ABC Box - Overview, News & Similar companies"
                        ),
                        "url": (
                            "https://www.zoominfo.com/c/"
                            "abc-box-co/530495"
                        ),
                        "snippet": "ABC Box company profile.",
                    }
                ],
            ]
        ),
        mcp=FakeMCP(results=[]),
    )

    batch = asyncio.run(collector.collect(_request()))

    assert batch.records == ()
    assert batch.accepted_results == ()
    assert batch.directory_leads == ()



def test_official_page_title_does_not_become_legal_name() -> None:
    record = result_to_candidate_evidence(
        _request(
            vendor_name="Microsoft",
            website="https://www.microsoft.com",
            country="United States",
            industry="Technology",
        ),
        {
            "title": (
                "Microsoft Trademark and Brand Guidelines"
            ),
            "url": (
                "https://www.microsoft.com/en-us/legal/"
                "intellectualproperty/trademarks"
            ),
            "snippet": (
                "Microsoft trademark guidance for customers."
            ),
        },
    )

    assert record is not None
    assert record.legal_name == "Microsoft"
    assert record.website == "https://www.microsoft.com"


def test_official_subdomain_uses_supplied_root_website() -> None:
    record = result_to_candidate_evidence(
        _request(
            vendor_name="Microsoft",
            website="https://www.microsoft.com",
            country="United States",
        ),
        {
            "title": "Facts About Microsoft - Stories",
            "url": (
                "https://news.microsoft.com/"
                "facts-about-microsoft/"
            ),
            "snippet": "Facts about Microsoft.",
        },
    )

    assert record is not None
    assert record.legal_name == "Microsoft"
    assert record.website == "https://www.microsoft.com"
    assert record.source_url.startswith(
        "https://news.microsoft.com/"
    )


def test_directory_lead_uses_requested_company_name() -> None:
    collector = LiveVendorIdentityCollector(
        serp=FakeSERP(
            responses=[
                [
                    {
                        "title": (
                            "Microsoft - Overview, News & "
                            "Similar companies"
                        ),
                        "url": (
                            "https://www.zoominfo.com/c/"
                            "microsoft/24904409"
                        ),
                        "snippet": "Microsoft company profile.",
                    }
                ],
                [],
            ]
        ),
        mcp=FakeMCP(results=[]),
    )

    batch = asyncio.run(
        collector.collect(
            _request(
                vendor_name="Microsoft"
            )
        )
    )

    assert len(batch.directory_leads) == 1
    assert (
        batch.directory_leads[0][
            "proposed_legal_name"
        ]
        == "Microsoft"
    )



def test_official_report_does_not_replace_requested_country() -> None:
    record = result_to_candidate_evidence(
        _request(
            vendor_name="Microsoft",
            website="https://www.microsoft.com",
            country="United States",
            industry="Technology",
        ),
        {
            "title": (
                "Microsoft and its contribution to Brazil"
            ),
            "url": (
                "https://www.microsoft.com/content/dam/"
                "microsoft/report.pdf"
            ),
            "snippet": (
                "A regional report about Microsoft in Brazil."
            ),
        },
    )

    assert record is not None
    assert record.legal_name == "Microsoft"
    assert record.country is None
    assert record.industry is None
