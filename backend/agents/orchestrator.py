"""
Sentinel Web-Risk — Multi-Agent Orchestration System.

Coordinates live Bright Data intelligence collection, deterministic risk
grounding, and six sequential CrewAI agents for vendor-risk assessment.
"""

import asyncio
import inspect
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import quote, quote_plus

from crewai import Agent, Crew, LLM, Process, Task

from core.brightdata import (
    proxy_client,
    serp_client,
    web_unlocker,
)
from core.brightdata_remote_mcp import remote_mcp_client
from core.config import settings
from core.orchestrator_truth import (
    assess_search_results,
    build_insufficient_evidence_language,
    build_verified_key_findings,
    serialize_evidence_record,
)
from core.report_calibration import (
    build_calibrated_report_language,
    build_evidence_provenance,
    select_balanced_sources,
)
from core.risk_engine import (
    calculate_disruption_probability,
    format_signals_for_report,
)


SearchResult = dict[str, str]
ProgressCallback = Callable[
    [dict[str, Any]],
    Optional[Awaitable[None]],
]


MCP_SEARCH_TIMEOUT_SECONDS = 90
MCP_SCRAPE_TIMEOUT_SECONDS = 90
SERP_TIMEOUT_SECONDS = 120
WEB_UNLOCKER_TIMEOUT_SECONDS = 90
PROXY_TIMEOUT_SECONDS = 60
CREW_TIMEOUT_SECONDS = 420

MAX_VENDOR_NAME_LENGTH = 200
MAX_SEARCH_RESULTS_FOR_TASK = 8
MAX_SCRAPED_CONTENT_FOR_TASK = 4_000
MAX_PROXY_CONTEXT_CHARACTERS = 1_000
MAX_SOURCE_RECORDS_IN_REPORT = 12

CREW_MAX_ATTEMPTS = 4
CREW_MAX_RATE_LIMIT_WAIT_SECONDS = 90


def get_llm() -> LLM:
    """
    Build the OpenAI-compatible LLM used by CrewAI.

    Settings are environment-backed, allowing the provider endpoint and
    model to change without modifying the orchestration code.
    """
    return LLM(
        model=f"openai/{settings.free_tier_model}",
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.1,
        max_retries=3,
        request_timeout=90,
    )


def _normalize_vendor_name(vendor_name: str) -> str:
    """Validate and normalize a vendor name before external requests."""
    normalized = " ".join(vendor_name.split())

    if not normalized:
        raise ValueError("Vendor name cannot be empty.")

    if len(normalized) > MAX_VENDOR_NAME_LENGTH:
        raise ValueError(
            "Vendor name exceeds the supported length of "
            f"{MAX_VENDOR_NAME_LENGTH} characters."
        )

    return normalized


def _normalize_language(language: str) -> str:
    """Return a normalized language token for reports and SERP requests."""
    normalized = language.strip().upper()
    return normalized or "EN"


def _normalize_confirmed_identity_context(
    identity_context: dict[str, Any],
) -> dict[str, Any]:
    """Validate and minimize confirmed identity context for a report."""
    if not isinstance(identity_context, dict):
        raise ValueError("Confirmed identity context is required.")

    if str(identity_context.get("status", "")).upper() != "CONFIRMED":
        raise ValueError("Investigation requires CONFIRMED identity status.")

    canonical_name = _normalize_vendor_name(
        str(identity_context.get("canonical_name", ""))
    )
    confidence = identity_context.get("identity_confidence")

    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or float(confidence) < 0.90
    ):
        raise ValueError("Confirmed identity confidence is below 0.90.")

    return {
        "status": "CONFIRMED",
        "requested_name": str(identity_context.get("requested_name", "")).strip(),
        "canonical_name": canonical_name,
        "website": identity_context.get("website"),
        "website_domain": identity_context.get("website_domain"),
        "country": identity_context.get("country"),
        "city": identity_context.get("city"),
        "industry": identity_context.get("industry"),
        "identity_confidence": round(float(confidence), 2),
        "confidence_label": str(identity_context.get("confidence_label", "HIGH")),
        "source_quality_labels": list(identity_context.get("source_quality_labels") or []),
        "evidence_urls": list(identity_context.get("evidence_urls") or []),
    }


def _append_tool_once(
    tools_used: list[str],
    tool_name: str,
) -> None:
    """Record a provider only once and preserve execution order."""
    if tool_name not in tools_used:
        tools_used.append(tool_name)


def _merge_search_results(
    primary_results: list[SearchResult],
    supplementary_results: list[SearchResult],
) -> int:
    """Merge unique supplementary results and return the number added."""
    existing_urls = {
        result.get("url", "").strip()
        for result in primary_results
        if result.get("url", "").strip()
    }

    added = 0

    for result in supplementary_results:
        result_url = result.get("url", "").strip()

        if not result_url or result_url in existing_urls:
            continue

        primary_results.append(result)
        existing_urls.add(result_url)
        added += 1

    return added


def _build_search_summary(
    search_results: list[SearchResult],
    vendor_name: str,
) -> str:
    """Build a compact evidence summary for the CrewAI context."""
    lines: list[str] = []

    for result in search_results[:MAX_SEARCH_RESULTS_FOR_TASK]:
        title = result.get("title", "").strip()
        url = result.get("url", "").strip()
        snippet = result.get("snippet", "").strip()

        if not title or not url:
            continue

        lines.append(
            f"- [{title}]({url}): {snippet[:250]}"
        )

    if lines:
        return "\n".join(lines)

    return (
        f"No verified live-web results were retrieved for {vendor_name}. "
        "Do not invent company facts or incidents. Explicitly state that "
        "the available evidence is insufficient, keep confidence low, and "
        "recommend additional evidence collection."
    )


def _parse_crew_json(raw_output: str) -> dict[str, Any]:
    """Parse a CrewAI JSON result with a fenced-output fallback."""
    normalized = raw_output.strip()

    if not normalized:
        return {}

    try:
        parsed = json.loads(normalized)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    cleaned = (
        normalized
        .replace("```json", "")
        .replace("```JSON", "")
        .replace("```", "")
        .strip()
    )

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1

    if start < 0 or end <= start:
        print("[JSON WARN] No JSON object found in CrewAI output.")
        return {}

    try:
        parsed = json.loads(cleaned[start:end])
        print("[JSON] Parsed CrewAI output through fallback extraction.")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        print(
            "[JSON WARN] CrewAI output could not be parsed: "
            f"{type(error).__name__}"
        )
        return {}


def _normalize_string_list(value: Any) -> list[str]:
    """Return a clean list of non-empty strings."""
    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------


def build_recon_agent(llm: LLM) -> Agent:
    """Build the live-web reconnaissance agent."""
    return Agent(
        role="Intelligence Recon Specialist",
        goal=(
            "Assess current vendor risk using verified live-web evidence "
            "from Bright Data SERP and Remote MCP search. Identify recent "
            "financial, operational, legal, reputational, and cyber signals."
        ),
        backstory=(
            "You are an evidence-first intelligence analyst. You separate "
            "facts from inference, preserve source traceability, and never "
            "invent incidents when evidence is incomplete."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_scraping_agent(llm: LLM) -> Agent:
    """Build the protected-source extraction agent."""
    return Agent(
        role="Deep Web Extraction Specialist",
        goal=(
            "Extract risk evidence from permitted public pages retrieved "
            "through Bright Data Web Unlocker, Remote MCP scraping, and the "
            "configured proxy network."
        ),
        backstory=(
            "You specialize in extracting useful evidence from complex, "
            "JavaScript-heavy, geo-sensitive, and access-restricted public "
            "sources while keeping every conclusion grounded in retrieved "
            "content."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_verification_agent(llm: LLM) -> Agent:
    """Build the source-credibility and entity-resolution agent."""
    return Agent(
        role="Source Credibility Analyst",
        goal=(
            "Validate source credibility, relevance, recency, corroboration, "
            "and whether each risk signal actually concerns the target vendor."
        ),
        backstory=(
            "You are an expert fact-checker. You distinguish official records "
            "and reputable reporting from rumor, unrelated industry news, "
            "duplicate claims, and outdated information."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_intelligence_agent(llm: LLM) -> Agent:
    """Build the risk-synthesis agent."""
    return Agent(
        role="Risk Intelligence Synthesizer",
        goal=(
            "Synthesize verified evidence into a coherent vendor-risk profile "
            "without overstating certainty."
        ),
        backstory=(
            "You are a senior enterprise risk analyst skilled at connecting "
            "corroborated signals while preserving evidence boundaries."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_prediction_agent(llm: LLM) -> Agent:
    """Build the forward-looking risk agent."""
    return Agent(
        role="Predictive Risk Modeler",
        goal=(
            "Estimate disruption probability and time horizon using the "
            "verified evidence and deterministic risk guidance supplied."
        ),
        backstory=(
            "You create calibrated, evidence-aware forecasts. You avoid false "
            "precision and reduce confidence when evidence is sparse."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_reporting_agent(llm: LLM) -> Agent:
    """Build the executive-reporting agent."""
    return Agent(
        role="Executive Intelligence Reporter",
        goal=(
            "Produce a concise, actionable, evidence-grounded JSON report for "
            "procurement, compliance, and business-continuity teams."
        ),
        backstory=(
            "You translate complex intelligence into clear executive language "
            "without unsupported claims, hidden assumptions, or inflated risk."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------


def build_tasks(
    vendor_name: str,
    search_results: list[SearchResult],
    scraped_content: str,
    agents: dict[str, Agent],
    language: str = "EN",
    pre_score: int | None = None,
    pre_level: str | None = None,
    tools_used: Optional[list[str]] = None,
) -> list[Task]:
    """Build the six sequential, evidence-grounded CrewAI tasks."""
    normalized_tools = tools_used or []
    tools_json = json.dumps(
        normalized_tools,
        ensure_ascii=False,
    )
    search_summary = _build_search_summary(
        search_results,
        vendor_name,
    )
    scrape_context = (
        scraped_content[:MAX_SCRAPED_CONTENT_FOR_TASK]
        if scraped_content
        else (
            "No protected-source content was accepted as verified supplementary "
            "evidence. Do not infer facts from missing data; continue only with "
            "accepted search evidence and reduce confidence accordingly."
        )
    )
    deterministic_guidance = (
        (
            f"- Verified-evidence score: {pre_score}/100\n"
            f"- Algorithmic threat level: {pre_level}"
        )
        if pre_score is not None and pre_level is not None
        else (
            "- Evidence assessment: INSUFFICIENT_EVIDENCE\n"
            "- No defensible risk score or threat level is available.\n"
            "- Do not reinterpret missing evidence as LOW risk."
        )
    )

    task_recon = Task(
        description=f"""
Analyze the live intelligence collected for **{vendor_name}**.

VERIFIED SEARCH EVIDENCE:
{search_summary}

Your responsibilities:
1. Identify material risk signals.
2. Categorize each signal as Financial, Operational, Legal,
   Reputational, or Cybersecurity.
3. Assign CRITICAL, HIGH, MEDIUM, or LOW severity.
4. Preserve the source URL beside every factual claim.
5. Prioritize recent evidence and identify its publication timeframe.
6. Clearly distinguish verified facts, inference, and missing evidence.
7. Do not invent facts when the live evidence is insufficient.

Return a structured evidence analysis.
""",
        agent=agents["recon"],
        expected_output=(
            "Evidence-linked risk signals with categories, severity, "
            "recency, and source traceability"
        ),
    )

    task_scraping = Task(
        description=f"""
Review the accepted, source-linked evidence context for **{vendor_name}**.

VERIFIED SUPPLEMENTARY EVIDENCE:
{scrape_context}

Your responsibilities:
1. Extract legal, regulatory, compliance, operational, and financial signals.
2. Ignore navigation text, boilerplate, unrelated entities, and duplicates.
3. Mark every conclusion as verified fact or analyst inference.
4. Do not claim an incident unless the retrieved content supports it.
5. Supplement rather than repeat the reconnaissance findings.

Return concise supplementary intelligence.
""",
        agent=agents["scraping"],
        expected_output=(
            "Supplementary evidence extracted from retrieved public content"
        ),
        context=[task_recon],
    )

    task_verification = Task(
        description=f"""
Validate all intelligence gathered about **{vendor_name}**.

Your responsibilities:
1. Classify each source as Official, Reputable News, Specialist,
   Forum/Social, or Unknown.
2. Evaluate recency, direct relevance, and corroboration.
3. Confirm that the target vendor—not a similarly named entity—is the subject.
4. Remove rumors, unrelated industry news, duplicates, and stale evidence.
5. Assign confidence from 0.0 to 1.0 to major findings.
6. Flag contradictions and unresolved uncertainty.

Return a credibility-assessed evidence package.
""",
        agent=agents["verification"],
        expected_output=(
            "Verified findings with confidence, corroboration, and exclusions"
        ),
        context=[task_recon, task_scraping],
    )

    task_intelligence = Task(
        description=f"""
Synthesize the verified evidence about **{vendor_name}** into an
enterprise vendor-risk profile.

Your responsibilities:
1. Identify up to five material risk factors.
2. Assess financial, operational, legal, reputational, and cyber exposure.
3. Explain the strongest evidence supporting each material risk.
4. Identify converging patterns without double-counting duplicate evidence.
5. Classify trajectory as Improving, Stable, Deteriorating, or Critical.
6. Reduce certainty when evidence is limited or contradictory.

Return a structured, evidence-grounded profile.
""",
        agent=agents["intelligence"],
        expected_output="Comprehensive verified vendor-risk profile",
        context=[task_verification],
    )

    task_prediction = Task(
        description=f"""
Generate a calibrated forward-looking assessment for **{vendor_name}**.

DETERMINISTIC GUIDANCE:
{deterministic_guidance}

Your responsibilities:
1. Estimate operational disruption probability for the next 90 days.
2. Select Immediate, Near-term, or Medium-term as the time horizon.
3. Identify the evidence driving the forecast.
4. Explain what would increase or reduce the estimated risk.
5. Avoid false precision and reduce confidence when evidence is sparse.
6. Treat deterministic metrics as guidance, not unquestionable truth.

Return a predictive assessment with uncertainty.
""",
        agent=agents["prediction"],
        expected_output=(
            "Calibrated disruption forecast with evidence and uncertainty"
        ),
        context=[task_intelligence],
    )

    task_reporting = Task(
        description=f"""
Generate the final executive intelligence report for **{vendor_name}**.

DETERMINISTIC GUIDANCE:
{deterministic_guidance}

ACTUALLY USED BRIGHT DATA SERVICES:
{tools_json}

SANITY REQUIREMENTS:
- Override an inflated algorithmic level when verified evidence does not
  support it.
- Do not convert INSUFFICIENT_EVIDENCE into a LOW-risk conclusion.
- Do not claim continuous monitoring or streaming unless explicitly enabled.
- Do not list a Bright Data service that is absent from the supplied list.
- State evidence limitations clearly.
- Translate executive_summary and risk_headline into language code {language}.
- Return valid JSON only, with no Markdown fences.

Return exactly these fields:
{{
  "executive_summary": "3-4 sentences. The first sentence describes the vendor's verified business or states that business details could not be verified.",
  "risk_headline": "One evidence-grounded sentence in {language}",
  "primary_risk_category": "Financial|Operational|Legal|Reputational|Cybersecurity",
  "key_findings": ["finding 1", "finding 2", "finding 3"],
  "risk_trajectory": "Improving|Stable|Deteriorating|Critical",
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "monitoring_signals": ["signal 1", "signal 2"],
  "time_horizon": "Immediate|Near-term|Medium-term",
  "bright_data_sources_used": {tools_json}
}}
""",
        agent=agents["reporting"],
        expected_output="Valid JSON executive vendor-risk report",
        context=[task_intelligence, task_prediction],
    )

    return [
        task_recon,
        task_scraping,
        task_verification,
        task_intelligence,
        task_prediction,
        task_reporting,
    ]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


class SentinelOrchestrator:
    """Coordinate evidence collection, CrewAI analysis, and final scoring."""

    def __init__(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        llm: Optional[LLM] = None,
        serp: Any = None,
        unlocker: Any = None,
        mcp: Any = None,
        proxy: Any = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.llm = llm
        self.serp_client = serp or serp_client
        self.web_unlocker = unlocker or web_unlocker
        self.mcp_client = mcp or remote_mcp_client
        self.proxy_client = proxy or proxy_client

    async def _emit_progress(
        self,
        stage: str,
        message: str,
        progress: int,
    ) -> None:
        """Emit a progress event to either an async or synchronous callback."""
        if self.progress_callback is None:
            return

        result = self.progress_callback(
            {
                "stage": stage,
                "message": message,
                "progress": progress,
            }
        )

        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _kickoff_crew_with_retry(crew: Crew) -> str:
        """Run CrewAI with bounded rate-limit retries."""
        for attempt in range(1, CREW_MAX_ATTEMPTS + 1):
            try:
                return str(crew.kickoff())
            except Exception as error:
                error_text = str(error)
                normalized_error = error_text.lower()

                is_rate_limit = (
                    "rate_limit" in normalized_error
                    or "ratelimit" in normalized_error
                    or "rate limit" in normalized_error
                )

                if not is_rate_limit:
                    print(
                        "[CREW ERROR] Non-rate-limit failure: "
                        f"{type(error).__name__}"
                    )
                    return "{}"

                if attempt >= CREW_MAX_ATTEMPTS:
                    break

                wait_match = re.search(
                    r"try again in ([\d.]+)s",
                    normalized_error,
                )
                suggested_wait = (
                    float(wait_match.group(1))
                    if wait_match
                    else 60.0
                )
                wait_seconds = min(
                    max(suggested_wait + 5.0, 10.0),
                    CREW_MAX_RATE_LIMIT_WAIT_SECONDS,
                )

                print(
                    "[CREW RETRY] "
                    f"attempt={attempt}/{CREW_MAX_ATTEMPTS}; "
                    f"waiting={wait_seconds:.0f}s"
                )
                time.sleep(wait_seconds)

        print("[CREW ERROR] All retry attempts were exhausted.")
        return "{}"

    async def investigate_confirmed_vendor(
        self,
        identity_context: dict[str, Any],
        language: str = "EN",
    ) -> dict[str, Any]:
        """Investigate only a strongly confirmed canonical identity."""
        confirmed = _normalize_confirmed_identity_context(
            identity_context
        )
        report = await self.investigate_vendor(
            confirmed["canonical_name"],
            language=language,
            identity_context=confirmed,
        )
        report["identity_context"] = confirmed
        raw = report.setdefault("raw_intelligence", {})
        raw["identity_gate"] = "confirmed"
        return report

    async def investigate_vendor(
        self,
        vendor_name: str,
        language: str = "EN",
        identity_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run the complete vendor investigation pipeline.

        External provider failures are isolated so one unavailable source does
        not prevent generation of a transparent, lower-confidence report.
        """
        normalized_vendor = _normalize_vendor_name(vendor_name)
        normalized_language = _normalize_language(language)

        tools_used: list[str] = []
        search_results: list[SearchResult] = []
        scraped_sections: list[str] = []
        evidence_provenance: list[dict[str, Any]] = []
        mcp_results_added = 0

        await self._emit_progress(
            "recon",
            (
                "Recon Agent collecting live intelligence for "
                f"{normalized_vendor}..."
            ),
            10,
        )

        # Step 1: direct Bright Data SERP collection.
        try:
            direct_results = await asyncio.wait_for(
                self.serp_client.search_vendor_news(
                    normalized_vendor,
                    lang=normalized_language.lower(),
                ),
                timeout=SERP_TIMEOUT_SECONDS,
            )
            search_results.extend(direct_results)

            if direct_results:
                _append_tool_once(tools_used, "SERP API")

            print(
                "[SERP] "
                f"vendor='{normalized_vendor}'; "
                f"results={len(direct_results)}"
            )
        except Exception as error:
            print(
                "[SERP WARN] "
                f"error={type(error).__name__}"
            )

        # Step 1b: genuine Remote MCP supplementary search.
        current_year = datetime.now(timezone.utc).year
        mcp_query = (
            f'"{normalized_vendor}" vendor risk warning '
            f"financial operational legal {current_year - 1} {current_year}"
        )

        try:
            mcp_results = await asyncio.wait_for(
                self.mcp_client.search(
                    mcp_query,
                    limit=10,
                ),
                timeout=MCP_SEARCH_TIMEOUT_SECONDS,
            )
            mcp_results_added = _merge_search_results(
                search_results,
                mcp_results,
            )

            if mcp_results:
                _append_tool_once(
                    tools_used,
                    "Remote MCP search_engine",
                )

            print(
                "[REMOTE MCP] "
                f"results={len(mcp_results)}; "
                f"unique_added={mcp_results_added}"
            )
        except Exception as error:
            print(
                "[REMOTE MCP WARN] "
                f"error={type(error).__name__}"
            )

        await self._emit_progress(
            "recon",
            (
                f"Collected {len(search_results)} unique live "
                "intelligence signals."
            ),
            25,
        )

        # Step 2: Web Unlocker for a public legal-filing search page.
        await self._emit_progress(
            "scraping",
            "Scraping Agent retrieving protected public evidence...",
            35,
        )

        legal_filing_url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?company={quote_plus(normalized_vendor)}"
            "&action=getcompany"
        )

        try:
            unlocker_content = await asyncio.wait_for(
                self.web_unlocker.fetch_legal_filing(
                    normalized_vendor
                ),
                timeout=WEB_UNLOCKER_TIMEOUT_SECONDS,
            )

            if unlocker_content:
                scraped_sections.append(
                    "[Web Unlocker Legal Filing Context]\n"
                    + unlocker_content
                )
                _append_tool_once(
                    tools_used,
                    "Web Unlocker",
                )
                evidence_provenance.append(
                    build_evidence_provenance(
                        provider="Web Unlocker",
                        url=legal_filing_url,
                        content=unlocker_content,
                        status="success",
                    )
                )
            else:
                evidence_provenance.append(
                    build_evidence_provenance(
                        provider="Web Unlocker",
                        url=legal_filing_url,
                        content=None,
                        status="no_usable_content",
                    )
                )

            print(
                "[WEB UNLOCKER] "
                f"characters={len(unlocker_content or '')}"
            )
        except Exception as error:
            evidence_provenance.append(
                build_evidence_provenance(
                    provider="Web Unlocker",
                    url=legal_filing_url,
                    content=None,
                    status=(
                        "error:"
                        f"{type(error).__name__}"
                    ),
                )
            )
            print(
                "[WEB UNLOCKER WARN] "
                f"error={type(error).__name__}"
            )

        # Step 2b: use genuine MCP scraping only as an extraction fallback.
        if not scraped_sections:
            scrape_target = next(
                (
                    result.get("url", "").strip()
                    for result in search_results
                    if result.get("url", "").startswith(
                        ("http://", "https://")
                    )
                ),
                "",
            )

            if scrape_target:
                try:
                    mcp_markdown = await asyncio.wait_for(
                        self.mcp_client.scrape(
                            scrape_target
                        ),
                        timeout=MCP_SCRAPE_TIMEOUT_SECONDS,
                    )

                    if mcp_markdown:
                        scraped_sections.append(
                            "[Remote MCP Markdown Context]\n"
                            + mcp_markdown
                        )
                        _append_tool_once(
                            tools_used,
                            "Remote MCP scrape_as_markdown",
                        )
                        evidence_provenance.append(
                            build_evidence_provenance(
                                provider=(
                                    "Remote MCP "
                                    "scrape_as_markdown"
                                ),
                                url=scrape_target,
                                content=mcp_markdown,
                                status="success",
                            )
                        )
                    else:
                        evidence_provenance.append(
                            build_evidence_provenance(
                                provider=(
                                    "Remote MCP "
                                    "scrape_as_markdown"
                                ),
                                url=scrape_target,
                                content=None,
                                status="no_usable_content",
                            )
                        )

                    print(
                        "[REMOTE MCP SCRAPE] "
                        f"characters={len(mcp_markdown or '')}"
                    )
                except Exception as error:
                    evidence_provenance.append(
                        build_evidence_provenance(
                            provider=(
                                "Remote MCP "
                                "scrape_as_markdown"
                            ),
                            url=scrape_target,
                            content=None,
                            status=(
                                "error:"
                                f"{type(error).__name__}"
                            ),
                        )
                    )
                    print(
                        "[REMOTE MCP SCRAPE WARN] "
                        f"error={type(error).__name__}"
                    )

        # Step 2c: Data Center proxy with ISP fallback for regional context.
        wiki_slug = quote(
            normalized_vendor.replace(" ", "_"),
            safe="_()-",
        )
        regional_url = (
            "https://en.wikipedia.org/wiki/"
            + wiki_slug
        )

        try:
            regional_content = await asyncio.wait_for(
                self.proxy_client.fetch_with_fallback(
                    regional_url,
                    country="us",
                ),
                timeout=PROXY_TIMEOUT_SECONDS,
            )

            if regional_content:
                scraped_sections.append(
                    "[Proxy Network Regional Context]\n"
                    + regional_content[
                        :MAX_PROXY_CONTEXT_CHARACTERS
                    ]
                )
                _append_tool_once(
                    tools_used,
                    "Proxy Network",
                )
                evidence_provenance.append(
                    build_evidence_provenance(
                        provider="Proxy Network",
                        url=regional_url,
                        content=regional_content,
                        status="success",
                    )
                )
            else:
                evidence_provenance.append(
                    build_evidence_provenance(
                        provider="Proxy Network",
                        url=regional_url,
                        content=None,
                        status="no_usable_content",
                    )
                )

            print(
                "[PROXY NETWORK] "
                f"characters={len(regional_content or '')}"
            )
        except Exception as error:
            evidence_provenance.append(
                build_evidence_provenance(
                    provider="Proxy Network",
                    url=regional_url,
                    content=None,
                    status=(
                        "error:"
                        f"{type(error).__name__}"
                    ),
                )
            )
            print(
                "[PROXY NETWORK WARN] "
                f"error={type(error).__name__}"
            )

        scraped_content = "\n\n".join(
            scraped_sections
        )

        await self._emit_progress(
            "analysis",
            "Grounding the AI analysis with deterministic risk signals...",
            50,
        )

        evidence_bundle = assess_search_results(
            normalized_vendor,
            identity_context,
            search_results,
        )
        evidence_assessment = evidence_bundle.assessment
        verified_records = evidence_bundle.verified_records
        rejected_records = evidence_bundle.rejected_records
        pre_signals = list(
            evidence_bundle.legacy_signals
        )
        score_available = evidence_bundle.score_available
        pre_score = (
            evidence_bundle.score
            if score_available
            else None
        )
        pre_level = (
            evidence_bundle.level
            if score_available
            else None
        )
        pre_confidence = evidence_bundle.confidence
        crew_search_results = list(
            evidence_bundle.crew_search_results
        )
        crew_evidence_context = (
            evidence_bundle.crew_evidence_context
        )

        print(
            "[EVIDENCE VALIDATION] "
            f"verified={len(verified_records)}; "
            f"rejected={len(rejected_records)}; "
            f"status={evidence_assessment.status}"
        )

        raw_output = "{}"
        llm_execution_status = (
            "skipped_insufficient_verified_evidence"
        )

        if score_available:
            active_llm = self.llm or get_llm()

            agents = {
                "recon": build_recon_agent(active_llm),
                "scraping": build_scraping_agent(active_llm),
                "verification": build_verification_agent(
                    active_llm
                ),
                "intelligence": build_intelligence_agent(
                    active_llm
                ),
                "prediction": build_prediction_agent(
                    active_llm
                ),
                "reporting": build_reporting_agent(
                    active_llm
                ),
            }

            tasks = build_tasks(
                normalized_vendor,
                crew_search_results,
                crew_evidence_context,
                agents,
                language=normalized_language,
                pre_score=pre_score,
                pre_level=pre_level,
                tools_used=tools_used,
            )

            await self._emit_progress(
                "agents",
                "Six AI agents are reviewing verified evidence...",
                65,
            )

            crew = Crew(
                agents=list(agents.values()),
                tasks=tasks,
                process=Process.sequential,
                max_rpm=3,
                verbose=False,
            )
            llm_execution_status = "running"

            try:
                raw_output = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._kickoff_crew_with_retry,
                        crew,
                    ),
                    timeout=CREW_TIMEOUT_SECONDS,
                )
                llm_execution_status = (
                    "completed"
                    if raw_output.strip() not in {"", "{}"}
                    else "completed_without_structured_output"
                )
                print(
                    "[CREW] Completed; "
                    f"output_characters={len(raw_output)}"
                )
            except asyncio.TimeoutError:
                llm_execution_status = "timeout_fallback"
                print(
                    "[CREW ERROR] Investigation exceeded "
                    f"{CREW_TIMEOUT_SECONDS} seconds."
                )
            except Exception as error:
                llm_execution_status = "error_fallback"
                print(
                    "[CREW ERROR] "
                    f"error={type(error).__name__}"
                )
        else:
            await self._emit_progress(
                "verification",
                (
                    "Verification found insufficient directly attributed "
                    "evidence; AI synthesis was skipped."
                ),
                65,
            )

        await self._emit_progress(
            "scoring",
            "Calculating calibrated risk scores and predictions...",
            80,
        )

        llm_report = _parse_crew_json(
            raw_output
        )

        # Final metrics are derived only from verified, source-linked evidence.
        # LLM wording and rejected candidates never influence the score.
        signals = pre_signals
        score = (
            evidence_bundle.score
            if score_available
            else 0
        )
        level = (
            evidence_bundle.level
            if score_available
            else "LOW"
        )
        confidence = pre_confidence

        disruption_probability = (
            calculate_disruption_probability(
                score,
                signals,
            )
            if score_available
            else 0.0
        )
        formatted_signals = format_signals_for_report(
            signals
        )

        await self._emit_progress(
            "reporting",
            "Compiling the calibrated evidence-grounded report...",
            92,
        )

        source_count = (
            evidence_assessment.unique_source_count
        )

        if score_available:
            calibrated_language = (
                build_calibrated_report_language(
                    vendor_name=normalized_vendor,
                    score=score,
                    level=level,
                    confidence=confidence,
                    disruption_probability=(
                        disruption_probability
                    ),
                    formatted_signals=(
                        formatted_signals
                    ),
                    source_count=source_count,
                    tools_used=tools_used,
                    llm_report=llm_report,
                )
            )
            verified_findings = build_verified_key_findings(
                verified_records
            )

            if verified_findings:
                calibrated_language["key_findings"] = (
                    verified_findings
                )
        else:
            calibrated_language = (
                build_insufficient_evidence_language(
                    normalized_vendor,
                    evidence_assessment,
                )
            )

        selected_sources = select_balanced_sources(
            crew_search_results,
            max_total=MAX_SOURCE_RECORDS_IN_REPORT,
            max_serp=8,
            max_mcp=4,
        )

        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

        final_report: dict[str, Any] = {
            "vendor_name": normalized_vendor,
            "evidence_assessment_status": (
                evidence_assessment.status
            ),
            "risk_score_available": score_available,
            "risk_score": score,
            "risk_level": level,
            "confidence_score": confidence,
            "disruption_probability": (
                disruption_probability
            ),
            "executive_summary": (
                calibrated_language[
                    "executive_summary"
                ]
            ),
            "risk_headline": (
                calibrated_language[
                    "risk_headline"
                ]
            ),
            "primary_risk_category": (
                calibrated_language[
                    "primary_risk_category"
                ]
            ),
            "key_findings": (
                calibrated_language[
                    "key_findings"
                ]
            ),
            "risk_trajectory": (
                calibrated_language[
                    "risk_trajectory"
                ]
            ),
            "recommended_actions": (
                calibrated_language[
                    "recommended_actions"
                ]
            ),
            "monitoring_signals": (
                calibrated_language[
                    "monitoring_signals"
                ]
            ),
            "time_horizon": (
                calibrated_language[
                    "time_horizon"
                ]
            ),
            "signals": formatted_signals,
            "sources": selected_sources,
            "evidence_provenance": (
                evidence_provenance
            ),
            "raw_intelligence": {
                "evidence_assessment_status": (
                    evidence_assessment.status
                ),
                "risk_score_available": score_available,
                "risk_metric_compatibility_note": (
                    "risk_score, risk_level, and disruption_probability are "
                    "compatibility placeholders when risk_score_available "
                    "is false."
                ),
                "verified_evidence_count": len(
                    verified_records
                ),
                "rejected_evidence_count": len(
                    rejected_records
                ),
                "verified_source_count": (
                    evidence_assessment.unique_source_count
                ),
                "authoritative_source_count": (
                    evidence_assessment.authoritative_source_count
                ),
                "evidence_coverage_message": (
                    evidence_assessment.coverage_message
                ),
                "verified_evidence": [
                    serialize_evidence_record(record)
                    for record in verified_records
                ],
                "rejected_evidence": [
                    serialize_evidence_record(record)
                    for record in rejected_records
                ],
                "search_results_count": len(
                    search_results
                ),
                "verified_search_result_count": len(
                    crew_search_results
                ),
                "mcp_unique_results_added": (
                    mcp_results_added
                ),
                "scraped_content_chars": len(
                    scraped_content
                ),
                "bright_data_tools_used": (
                    tools_used
                ),
                "primary_risk_category": (
                    calibrated_language[
                        "primary_risk_category"
                    ]
                ),
                "risk_headline": (
                    calibrated_language[
                        "risk_headline"
                    ]
                ),
                "risk_trajectory": (
                    calibrated_language[
                        "risk_trajectory"
                    ]
                ),
                "time_horizon": (
                    calibrated_language[
                        "time_horizon"
                    ]
                ),
                "key_findings": (
                    calibrated_language[
                        "key_findings"
                    ]
                ),
                "recommended_actions": (
                    calibrated_language[
                        "recommended_actions"
                    ]
                ),
                "evidence_provenance": (
                    evidence_provenance
                ),
                "llm_execution_status": (
                    llm_execution_status
                ),
                "llm_supporting_fields_received": (
                    sorted(
                        llm_report.keys()
                    )
                    if llm_report
                    else []
                ),
                "scoring_source": (
                    "verified_source_linked_evidence"
                ),
                "scoring_method": (
                    "verified_sentence_level_evidence"
                ),
                "language_authority": (
                    "deterministic_report_calibration"
                ),
                "assessment_type": (
                    "point_in_time"
                ),
            },
            "status": "completed",
            "generated_at": generated_at,
        }

        await self._emit_progress(
            "complete",
            "Investigation complete.",
            100,
        )

        return final_report
