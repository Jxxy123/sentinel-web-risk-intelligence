"use client";
import { useEffect, useRef, useState } from "react";
import { type InvestigationJob } from "@/lib/api";
import { Terminal } from "lucide-react";

const STAGE_LOGS: Record<string, string[]> = {
  recon: [
    "> INIT recon_agent.py — Bright Data SERP API connected",
    "> Querying: '{vendor} financial crisis 2024 2025'",
    "> Querying: '{vendor} layoffs hiring freeze operations'",
    "> Querying: '{vendor} legal lawsuit regulatory violation'",
    "> Querying: '{vendor} supply chain disruption warning'",
    "> Signal extraction: parsing organic results...",
  ],
  scraping: [
    "> INIT scraping_agent.py — Web Unlocker armed",
    "> Accessing SEC EDGAR: /cgi-bin/browse-edgar?company={vendor}",
    "> Bypassing CAPTCHA protection... ✓",
    "> Fetching geo-restricted portals via proxy network...",
    "> Extracting legal filings and regulatory notices...",
  ],
  analysis: [
    "> INIT verification_agent.py",
    "> Cross-referencing {n} intelligence sources...",
    "> Credibility scoring: Official=0.95 News=0.82 Forum=0.41",
    "> Filtering low-confidence signals...",
    "> Verification complete — {m} confirmed signals",
  ],
  agents: [
    "> INIT intelligence_agent.py",
    "> Synthesizing Financial risk signals...",
    "> Synthesizing Operational risk signals...",
    "> Synthesizing Legal exposure signals...",
    "> Risk pattern analysis: cross-category correlation detected",
    "> Generating risk intelligence profile...",
  ],
  scoring: [
    "> INIT prediction_agent.py",
    "> Loading historical failure pattern database...",
    "> Calculating disruption probability matrix...",
    "> Time-horizon modeling: 0-90 day window",
    "> Confidence interval computation complete",
  ],
  reporting: [
    "> INIT reporting_agent.py",
    "> Generating executive summary...",
    "> Formatting risk score and confidence metrics...",
    "> Compiling source citations...",
    "> Report generation complete ✓",
  ],
};

const STAGE_ORDER = ["recon", "scraping", "analysis", "agents", "scoring", "reporting"];
const STAGE_LABELS: Record<string, string> = {
  recon: "RECON AGENT",
  scraping: "SCRAPING AGENT",
  analysis: "VERIFICATION AGENT",
  agents: "INTELLIGENCE AGENT",
  scoring: "PREDICTION AGENT",
  reporting: "REPORTING AGENT",
};

interface LogLine { text: string; ts: string; stage: string; }

interface Props { job: InvestigationJob; }

export default function AgentStatusPanel({ job }: Props) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [cursor, setCursor] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);
  const prevStage = useRef<string>("");
  const logIdx = useRef<Record<string, number>>({});

  // Blink cursor
  useEffect(() => {
    const t = setInterval(() => setCursor(c => !c), 530);
    return () => clearInterval(t);
  }, []);

  // Add log lines as stage changes
  useEffect(() => {
    const stage = job.stage;
    if (!stage || stage === "queued" || stage === prevStage.current) return;
    prevStage.current = stage;

    const lines = STAGE_LOGS[stage] || [];
    const vendorName = job.vendor_name;
    let delay = 0;

    if (!logIdx.current[stage]) {
      setLogs(prev => [...prev, {
        text: `\n── ${STAGE_LABELS[stage] || stage.toUpperCase()} ACTIVATED ──`,
        ts: now(),
        stage,
      }]);
    }

    lines.forEach((line, i) => {
      if ((logIdx.current[stage] || 0) > i) return;
      delay += 280 + Math.random() * 180;
      setTimeout(() => {
        const text = line
          .replace("{vendor}", vendorName)
          .replace("{n}", String(8 + Math.floor(Math.random() * 12)))
          .replace("{m}", String(4 + Math.floor(Math.random() * 8)));
        setLogs(prev => [...prev, { text, ts: now(), stage }]);
        logIdx.current[stage] = i + 1;
      }, delay);
    });
  }, [job.stage, job.vendor_name]);

  // Auto-scroll
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const stageColor = (s: string) => {
    if (s === job.stage) return "#00D4FF";
    const idx = STAGE_ORDER.indexOf(s);
    const curIdx = STAGE_ORDER.indexOf(job.stage);
    return idx < curIdx ? "#00E87A" : "#1A2540";
  };

  return (
    <div className="panel panel-glow rounded-2xl overflow-hidden">
      {/* Terminal titlebar */}
      <div className="flex items-center justify-between px-5 py-3"
        style={{ background: "rgba(5,8,16,0.9)", borderBottom: "1px solid rgba(26,37,64,0.6)" }}>
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-[#FF2D55]/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#F5A623]/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#00E87A]/70" />
          </div>
          <div className="flex items-center gap-2">
            <Terminal size={12} className="text-[#0066FF]" />
            <span className="mono text-[10px] text-[#0066FF] tracking-[0.2em]">
              SENTINEL AGENT TERMINAL — {job.vendor_name.toUpperCase()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-1.5 rounded-full bg-[#0066FF] agent-pulse" />
          <span className="mono text-[10px] text-sentinel-muted">{job.progress}% COMPLETE</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="progress-track rounded-none h-[3px]">
        <div className="progress-fill h-full" style={{ width: `${job.progress}%` }} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-0">
        {/* Stage sidebar */}
        <div className="p-4 space-y-1 lg:border-r lg:border-sentinel-border/30"
          style={{ minWidth: 200, background: "rgba(5,8,16,0.5)" }}>
          {STAGE_ORDER.map(s => (
            <div key={s} className="flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all"
              style={{
                background: s === job.stage ? "rgba(0,102,255,0.1)" : "transparent",
                border: `1px solid ${s === job.stage ? "rgba(0,102,255,0.25)" : "transparent"}`,
              }}>
              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ background: stageColor(s), boxShadow: s === job.stage ? `0 0 6px ${stageColor(s)}` : "none" }} />
              <span className="mono text-[9px] tracking-[0.15em]"
                style={{ color: s === job.stage ? "#E8EDF8" : s < job.stage ? "#00E87A" : "#1A2540" }}>
                {STAGE_LABELS[s]}
              </span>
              {s === job.stage && (
                <div className="ml-auto w-2.5 h-2.5 border border-[#0066FF]/40 border-t-[#0066FF] rounded-full animate-spin" />
              )}
            </div>
          ))}
        </div>

        {/* Terminal log */}
        <div className="p-4 h-52 overflow-y-auto font-mono text-[11px] leading-relaxed"
          style={{ background: "rgba(2,4,10,0.6)" }}>
          <div className="mono text-[10px] text-sentinel-muted mb-3 tracking-widest">
            $ sentinel-agent --vendor "{job.vendor_name}" --mode autonomous --bright-data enabled
          </div>
          {logs.map((log, i) => (
            <div key={i} className={`flex gap-3 mb-0.5 ${log.text.startsWith("\n──") ? "mt-2" : ""}`}>
              {!log.text.startsWith("\n──") && (
                <span className="text-sentinel-muted flex-shrink-0 text-[9px] pt-0.5">{log.ts}</span>
              )}
              <span style={{
                color: log.text.startsWith("\n──") ? "#0066FF"
                  : log.text.includes("✓") ? "#00E87A"
                  : log.text.includes("ERROR") ? "#FF2D55"
                  : log.text.includes("Querying") ? "#00D4FF"
                  : "#8899BB",
                fontWeight: log.text.startsWith("\n──") ? 600 : 400,
              }}>
                {log.text.startsWith("\n──") ? log.text.replace("\n", "") : log.text}
              </span>
            </div>
          ))}
          {/* Blinking cursor */}
          <div className="flex items-center gap-1 mt-1">
            <span className="text-[#00E87A] text-[10px]">$</span>
            <span className="w-2 h-3.5 bg-[#00E87A]" style={{ opacity: cursor ? 1 : 0 }} />
          </div>
          <div ref={endRef} />
        </div>
      </div>
    </div>
  );
}

function now() {
  return new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}