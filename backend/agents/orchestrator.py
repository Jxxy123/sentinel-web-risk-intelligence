"""
Sentinel Web-Risk — Multi-Agent Orchestration System (CrewAI)
Six specialized AI agents working autonomously to investigate vendor risk.
"""
import asyncio
import json
import os
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from crewai import Agent, Task, Crew, Process

from crewai import LLM

from core.config import settings
from core.brightdata import serp_client, web_unlocker, mcp_client, proxy_client
from core.risk_engine import (
    analyze_text_for_signals,
    calculate_risk_score,
    calculate_disruption_probability,
    format_signals_for_report,
)


def get_llm():
    """
    Build the LLM client using ChatGroq directly.
    ⚠️  llama-3.3-70b-versatile = 12K TPM on free tier  ← USE THIS
        llama-3.1-8b-instant    =  6K TPM on free tier  ← AVOID (lower limit)
    """
    groq_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    raw_model = os.getenv("FREE_TIER_MODEL", "llama-3.3-70b-versatile").split("/")[-1]

    return LLM(
        model=f"groq/{raw_model}",
        api_key=groq_key,
        temperature=0.1,
        max_retries=3,
        request_timeout=90,
    )


# ─────────────────────────────────────────────
# AGENT DEFINITIONS
# ─────────────────────────────────────────────

def build_recon_agent(llm) -> Agent:
    return Agent(
        role="Intelligence Recon Specialist",
        goal=(
            "Search the live web using Bright Data SERP API to gather the most "
            "current and relevant intelligence about a vendor company. Find news, "
            "financial signals, hiring trends, and any warning signs."
        ),
        backstory=(
            "You are an elite intelligence analyst who specializes in rapid web reconnaissance. "
            "You know exactly which search queries extract the highest-value signals about "
            "company health, financial distress, and operational risk. You never rely on "
            "assumptions — you always verify with live data."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_scraping_agent(llm) -> Agent:
    return Agent(
        role="Deep Web Extraction Specialist",
        goal=(
            "Extract intelligence from protected, JavaScript-heavy, and geo-restricted "
            "websites using Bright Data Web Unlocker. Access legal filings, regional "
            "news, and protected data sources that standard tools cannot reach."
        ),
        backstory=(
            "You are a technical intelligence extraction expert with deep knowledge of "
            "web scraping and data extraction. You specialize in bypassing access barriers "
            "to retrieve intelligence from sources others cannot access — legal databases, "
            "regional portals, protected filings, and dynamic websites."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_verification_agent(llm) -> Agent:
    return Agent(
        role="Source Credibility Analyst",
        goal=(
            "Evaluate and validate the credibility of all gathered intelligence. "
            "Filter noise, identify reliable sources, and assign credibility scores "
            "to each piece of intelligence."
        ),
        backstory=(
            "You are an expert fact-checker and intelligence analyst. You evaluate "
            "sources for credibility, recency, and relevance. You distinguish between "
            "reliable journalism, official filings, and unreliable speculation."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_intelligence_agent(llm) -> Agent:
    return Agent(
        role="Risk Intelligence Synthesizer",
        goal=(
            "Synthesize all gathered intelligence into coherent risk signals. "
            "Identify patterns, cross-reference signals, and produce a structured "
            "risk intelligence profile for the vendor."
        ),
        backstory=(
            "You are a senior risk intelligence analyst with expertise in enterprise "
            "vendor risk assessment. You excel at finding hidden patterns in disparate "
            "data sources and synthesizing them into actionable intelligence."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_prediction_agent(llm) -> Agent:
    return Agent(
        role="Predictive Risk Modeler",
        goal=(
            "Estimate the probability and timeline of vendor operational disruption "
            "based on gathered intelligence signals. Generate forward-looking risk predictions."
        ),
        backstory=(
            "You are a predictive analyst who specializes in enterprise supply chain "
            "risk modeling. You have studied hundreds of corporate collapses and can "
            "identify the early warning signs that precede vendor failure."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_reporting_agent(llm) -> Agent:
    return Agent(
        role="Executive Intelligence Reporter",
        goal=(
            "Generate a clear, professional, executive-level risk intelligence report "
            "that enterprise procurement and compliance teams can act on immediately."
        ),
        backstory=(
            "You are a senior executive communications specialist who translates complex "
            "intelligence analysis into clear, actionable business reports. Your reports "
            "are read by C-suite executives and must be precise, concise, and actionable."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


# ─────────────────────────────────────────────
# TASK DEFINITIONS
# ─────────────────────────────────────────────

def build_tasks(
    vendor_name: str,
    search_results: List[Dict],
    scraped_content: str,
    agents: Dict[str, Agent],
    language: str = "EN",
    pre_score: int = 5,
    pre_level: str = "LOW",
) -> List[Task]:

    search_summary = "\n".join([
        f"- [{r['title']}]({r['url']}): {r['snippet'][:200]}"  # 🧠 Truncate snippets to 200 chars max
        for r in search_results[:5]  # ✅ Safe optimization: Top 5 dense results only
        if r.get("title") and r.get("url")
    ])

    # If SERP returned nothing, give the LLM a clear mandate to use its knowledge
    if not search_summary.strip():
        search_summary = (
            f"No live SERP results were retrieved for {vendor_name} at this time. "
            "Use your training knowledge to assess this company's known risk profile, "
            "public reputation, industry standing, and any historical risk events. "
            "Clearly note that this analysis is based on pre-training knowledge, not live web data."
        )

    task_recon = Task(
        description=f"""
        Analyze the following live web intelligence gathered for vendor: **{vendor_name}**

        SEARCH RESULTS FROM BRIGHT DATA SERP API:
        {search_summary}

        Your task:
        1. Identify the most significant risk signals from these search results
        2. Categorize signals: Financial, Operational, Legal, Reputational, Cybersecurity
        3. Rate severity of each signal: CRITICAL / HIGH / MEDIUM / LOW
        4. List the top 10 most relevant intelligence findings
        5. Note which signals are most recent (last 30-90 days)

        Output as a structured analysis.
        """,
        agent=agents["recon"],
        expected_output="Structured list of risk signals with category, severity, and evidence",
    )

    task_scraping = Task(
        description=f"""
        You have been provided with web content scraped from protected sources for: **{vendor_name}**

        SCRAPED CONTENT (via Bright Data Web Unlocker):
        {scraped_content[:3000] if scraped_content else "No scraped content available — proceed with search intelligence only."}

        Your task:
        1. Extract any additional risk signals from this content
        2. Identify legal filings, regulatory notices, or compliance issues
        3. Find any operational indicators (closures, delays, disruptions)
        4. Note any financial distress indicators

        Supplement the recon findings with this additional intelligence.
        """,
        agent=agents["scraping"],
        expected_output="Supplementary risk intelligence from deep web extraction",
        context=[task_recon],
    )

    task_verification = Task(
        description=f"""
        Review all intelligence gathered about **{vendor_name}** and assess credibility.

        Your task:
        1. Evaluate each intelligence source for credibility (Official/News/Forum/Unknown)
        2. Filter out noise, rumors, or unreliable signals
        3. Assign confidence scores (0-1) to major findings
        4. Identify which signals are corroborated by multiple sources
        5. Flag any potentially misleading or outdated information
        6. CRITICAL HYGIENE DIRECTIVE: Verify if the target vendor is the actual subject
           of the threat signals. Filter out general industry news or unrelated content
           that does not directly reflect the target company's corporate status.

        Output a verified, credibility-assessed intelligence package.
        """,
        agent=agents["verification"],
        expected_output="Credibility-assessed intelligence with confidence scores",
        context=[task_recon, task_scraping],
    )

    task_intelligence = Task(
        description=f"""
        Synthesize all verified intelligence about **{vendor_name}** into a comprehensive risk profile.

        Your task:
        1. Identify the 5 most critical risk factors
        2. Assess overall financial health indicators
        3. Evaluate operational stability signals
        4. Analyze legal and compliance exposure
        5. Assess reputational risk trajectory
        6. Identify any accelerating or converging risk patterns

        Produce a structured risk intelligence profile with:
        - Primary Risk Category (Financial/Operational/Legal/Reputational/Cyber)
        - Secondary risk categories
        - Key risk drivers
        - Risk trajectory (Improving/Stable/Deteriorating/Critical)
        """,
        agent=agents["intelligence"],
        expected_output="Comprehensive risk intelligence profile",
        context=[task_verification]
    )

    task_prediction = Task(
        description=f"""
        Based on all intelligence gathered about **{vendor_name}**, generate predictive risk assessments.

        Your task:
        1. Estimate probability of operational disruption in next 90 days (0-100%)
        2. Identify earliest warning indicators that materialized
        3. Compare signal patterns to known historical vendor failures
        4. Estimate time horizon of risk: Immediate (0-30d), Near-term (31-90d), Medium-term (91-180d)
        5. Identify what would escalate or de-escalate this risk

        Include specific comparisons to any relevant historical cases if applicable.
        """,
        agent=agents["prediction"],
        expected_output="Predictive risk assessment with probability estimates and timeline",
        context=[task_intelligence],
    )

    task_reporting = Task(
        description=f"""
        Generate a complete executive intelligence report for **{vendor_name}**.

        GUIDANCE METRICS (USE FOR CONTEXT, BUT VERIFY VALIDITY):
        - Calculated Keyword Score: {pre_score}/100
        - Algorithmic Threat Level: {pre_level}

        CRITICAL SANITY FILTER:
        If the calculated threat level is HIGH or CRITICAL, but your source analysis reveals 
        the text matches are only referring to routine corporate filings, historical antitrust cases, 
        or standard market news for an otherwise stable company, you are ordered to OVERRIDE the algorithmic 
        threat level. Downgrade the output status to LOW or MEDIUM and write an objective, stable report.

        Create a structured JSON report with these exact fields.
        CRITICAL MULTILINGUAL MANDATE: Translate "executive_summary" and "risk_headline"
        completely into this language code: {language}.

        {{
            "executive_summary": "3-4 sentences for C-suite in {language}. MANDATORY: First sentence MUST describe what {vendor_name} actually is — its core business model, industry, products/services — before any risk commentary.",
            "risk_headline": "One powerful sentence describing the primary risk in {language}",
            "primary_risk_category": "Financial|Operational|Legal|Reputational|Cybersecurity",
            "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4", "finding 5"],
            "risk_trajectory": "Improving|Stable|Deteriorating|Critical",
            "recommended_actions": ["action 1", "action 2", "action 3"],
            "monitoring_signals": ["what to watch 1", "what to watch 2"],
            "time_horizon": "Immediate|Near-term|Medium-term",
            "bright_data_sources_used": ["SERP API", "Web Unlocker", "MCP Server"]
        }}

        Output ONLY the JSON. No preamble. No markdown fences.
        """,
        agent=agents["reporting"],
        expected_output="JSON executive intelligence report",
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


# ─────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────

class SentinelOrchestrator:
    """Main orchestrator that coordinates all agents and produces risk reports."""

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.llm = get_llm()

    async def _emit_progress(self, stage: str, message: str, progress: int):
        if self.progress_callback:
            await self.progress_callback({
                "stage": stage,
                "message": message,
                "progress": progress,
            })

    async def investigate_vendor(self, vendor_name: str, language: str = "EN") -> Dict[str, Any]:
        """
        Full autonomous vendor investigation pipeline.
        Returns complete risk report localized by language token.
        """
        await self._emit_progress("recon", f"Recon Agent searching live web for {vendor_name}...", 10)

        # ── Step 1: Bright Data SERP multi-query sweep ──────────────────────
        search_results = await serp_client.search_vendor_news(vendor_name, lang=language.lower())
        print(f"[SERP] Returned {len(search_results)} results for '{vendor_name}'")

        # ── Step 1b: MCP supplementary signal layer ──────────────────────────
        try:
            mcp_results = await mcp_client.search(f"{vendor_name} risk warning 2025 2026")
            if mcp_results:
                existing_urls = {r["url"] for r in search_results if "url" in r}
                added = 0
                for r in mcp_results:
                    if r.get("url") not in existing_urls:
                        search_results.append(r)
                        added += 1
                print(f"[MCP] Added {added} supplementary signals")
        except Exception as mcp_err:
            print(f"[MCP WARN] {mcp_err}")

        await self._emit_progress("recon", f"Found {len(search_results)} live intelligence signals via SERP + MCP", 25)

        # ── Step 2: Bright Data Web Unlocker — protected sources ─────────────
        await self._emit_progress("scraping", "Scraping Agent accessing protected sources...", 35)
        scraped_content = ""
        try:
            scraped_content = await web_unlocker.fetch_legal_filing(vendor_name) or ""
            print(f"[UNLOCKER] Scraped {len(scraped_content)} chars")
            
            # 🌐 Route cross-border regional intelligence via Proxy Network
            # This fetches supplementary data through residential proxy node to avoid regional filters
            regional_intel = await proxy_client.fetch_with_proxy(f"https://en.wikipedia.org/wiki/{vendor_name}", country="us")
            if regional_intel:
                scraped_content += f"\n\n[Proxy Network Regional Context]: {regional_intel[:1000]}"
                print("[PROXY CLIENT] Live cross-border routing layer successfully appended to context data")
        except Exception as scrape_err:
            print(f"[UNLOCKER WARN] {scrape_err}")

        await self._emit_progress("analysis", "Pre-scoring indicators to ground LLM contexts...", 50)

        # ── Step 2b: Pre-scoring Grounding Layer (Halts Hallucinations) ──
        # Calculate scores using raw metrics first to set immutable textual constraints
        raw_pool = " ".join([r.get("snippet", "") + " " + r.get("title", "") for r in search_results]) + scraped_content[:2000]
        pre_signals = analyze_text_for_signals(raw_pool)
        pre_score, pre_level, _ = calculate_risk_score(pre_signals)

        # ── Step 3: CrewAI multi-agent deep analysis ──────────────────────────
        agents = {
            "recon":        build_recon_agent(self.llm),
            "scraping":     build_scraping_agent(self.llm),
            "verification": build_verification_agent(self.llm),
            "intelligence": build_intelligence_agent(self.llm),
            "prediction":   build_prediction_agent(self.llm),
            "reporting":    build_reporting_agent(self.llm),
        }

        tasks = build_tasks(
            vendor_name, search_results, scraped_content, agents, 
            language=language, pre_score=pre_score, pre_level=pre_level
        )

        await self._emit_progress("agents", "AI Agents running full investigation...", 65)

        crew = Crew(
            agents=list(agents.values()),
            tasks=tasks,
            process=Process.sequential,
            max_rpm=3,
            verbose=False,
        )

        loop = asyncio.get_event_loop()
        raw_output = "{}"

        # Retry wrapper: waits a full 70s on rate-limit to reset Groq's 1-min TPM window.
        import time, re as _re

        def _kickoff_with_retry():
            for attempt in range(4):
                try:
                    return str(crew.kickoff())
                except Exception as err:
                    err_str = str(err)
                    if "rate_limit" not in err_str.lower() and "ratelimit" not in err_str.lower():
                        print(f"[CREW ERROR] Non-rate-limit error: {err}")
                        return "{}"
                    wait_match = _re.search(r"try again in ([\d.]+)s", err_str)
                    suggested = float(wait_match.group(1)) if wait_match else 60.0
                    wait_secs = max(suggested + 5, 70)
                    print(f"[CREW RETRY] Attempt {attempt+1}/4 — TPM limit hit. "
                          f"Waiting {wait_secs:.0f}s for window reset...")
                    time.sleep(wait_secs)
            print("[CREW ERROR] All retries exhausted.")
            return "{}"

        try:
            raw_output = await loop.run_in_executor(None, _kickoff_with_retry)
            print(f"[CREW] Output preview: {raw_output[:300]}")
        except Exception as crew_err:
            print(f"[CREW ERROR] {crew_err}")

        await self._emit_progress("scoring", "Calculating risk scores and predictions...", 80)

        # ── Step 4: Parse LLM JSON output (bulletproof 2-pass) ───────────────
        llm_report: Dict = {}
        try:
            llm_report = json.loads(raw_output)
        except Exception:
            try:
                cleaned = (
                    raw_output
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    llm_report = json.loads(cleaned[start:end])
                    print("[JSON] Parsed via fence-strip fallback")
                else:
                    print("[JSON WARN] No JSON object found in crew output")
            except Exception as parse_err:
                print(f"[JSON WARN] Both parse attempts failed: {parse_err}")

        verified_summary = llm_report.get("executive_summary", "")
        verified_findings = " ".join(llm_report.get("key_findings", []))
        verified_text = f"{verified_summary} {verified_findings}"

        if not verified_summary.strip() or len(verified_text) < 50:
            verified_text = raw_pool

        signals = analyze_text_for_signals(verified_text)
        score, level, confidence = calculate_risk_score(signals)
        disruption_prob = calculate_disruption_probability(score, signals)
        formatted_signals = format_signals_for_report(signals)

        await self._emit_progress("reporting", "Generating executive intelligence report...", 92)

        # ── Step 5: Compile final report ──────────────────────────────────────
        sig_count = len(signals)
        cat_count = len(set(s["category"] for s in signals))
        source_count = len(search_results)

        default_summary = (
            f"{vendor_name} is a company analyzed by Sentinel's autonomous intelligence pipeline. "
            f"Live web intelligence gathered {source_count} sources via Bright Data SERP API and Web Unlocker. "
            f"The signal engine detected {sig_count} risk indicators across {cat_count} categories. "
            f"Overall risk level is assessed as {level} with a disruption probability of {int(disruption_prob * 100)}%."
        )

        final_report = {
            "vendor_name": vendor_name,
            "risk_score": score,
            "risk_level": level,
            "confidence_score": confidence,
            "disruption_probability": disruption_prob,
            "executive_summary": llm_report.get("executive_summary", default_summary),
            "risk_headline": llm_report.get(
                "risk_headline",
                f"{vendor_name} — {level} risk profile based on {source_count} live intelligence sources.",
            ),
            "primary_risk_category": llm_report.get("primary_risk_category", "Operational"),
            "key_findings": llm_report.get("key_findings", [
                f"Sentinel gathered intelligence from {source_count} live web sources via Bright Data",
                f"Signal engine detected {sig_count} risk indicators across {cat_count} risk categories",
                f"Disruption probability estimated at {int(disruption_prob * 100)}% over the next 90 days",
                f"Risk trajectory: {llm_report.get('risk_trajectory', 'Stable')}",
                f"Continuous baseline real-time streaming scans active.",
            ]),
            "risk_trajectory": llm_report.get("risk_trajectory", "Stable"),
            "recommended_actions": llm_report.get("recommended_actions", [
                "Initiate enhanced vendor monitoring via Bright Data live feeds",
                "Request updated financial and operational documentation from vendor",
                "Assess alternative vendor options for business continuity planning",
            ]),
            "monitoring_signals": llm_report.get("monitoring_signals", []),
            "time_horizon": llm_report.get("time_horizon", "Near-term"),
            "signals": formatted_signals,
            "sources": [
                {"url": r["url"], "title": r["title"]}
                for r in search_results[:8]
                if r.get("url") and r.get("title")
            ],
            "raw_intelligence": {
                "search_results_count": source_count,
                "scraped_content_chars": len(scraped_content),
                "bright_data_tools_used": ["SERP API", "Web Unlocker", "MCP Server"],
                "primary_risk_category": llm_report.get("primary_risk_category", "Operational"),
                "risk_headline": llm_report.get(
                    "risk_headline",
                    f"{vendor_name} — {level} risk profile based on {source_count} live intelligence sources.",
                ),
                "risk_trajectory": llm_report.get("risk_trajectory", "Stable"),
                "time_horizon": llm_report.get("time_horizon", "Near-term"),
                "key_findings": llm_report.get("key_findings", []),
                "recommended_actions": llm_report.get("recommended_actions", []),
            },
            "status": "completed",
            "generated_at": datetime.utcnow().isoformat(),
        }

        await self._emit_progress("complete", "Investigation complete.", 100)
        return final_report