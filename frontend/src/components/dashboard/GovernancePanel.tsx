"use client";
import { Cpu, DollarSign, Database, ShieldCheck } from "lucide-react";

interface Props {
  serpCalls: number;
  llmCost: number;
  sourcesCount: number;
  signalsCount: number;
}

const MAX_SERP = 10;

export default function GovernancePanel({ serpCalls, llmCost, sourcesCount, signalsCount }: Props) {
  const serpPct = Math.min((serpCalls / MAX_SERP) * 100, 100);
  const costStatus = llmCost < 1.0 ? "OPTIMAL" : llmCost < 2.5 ? "NORMAL" : "ELEVATED";
  const costColor = llmCost < 1.0 ? "#00E87A" : llmCost < 2.5 ? "#F5A623" : "#FF6B00";

  return (
    <div className="panel rounded-2xl p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <ShieldCheck size={13} className="text-[#0066FF]" />
        <span className="mono text-[10px] text-sentinel-muted tracking-[0.2em]">AI GOVERNANCE</span>
        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-[#00E87A] animate-pulse" />
      </div>

      <div className="divider-glow" />

      {/* SERP usage */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5">
            <Database size={11} className="text-sentinel-muted" />
            <span className="mono text-[9px] text-sentinel-muted tracking-wider">SERP CALLS</span>
          </div>
          <span className="mono text-[10px] text-sentinel-text">{serpCalls}/{MAX_SERP}</span>
        </div>
        <div className="h-1 rounded-full" style={{ background: "rgba(26,37,64,0.8)" }}>
          <div className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${serpPct}%`,
              background: serpPct > 80 ? "#FF6B00" : "#0066FF",
            }} />
        </div>
      </div>

      {/* LLM Cost */}
      <div className="flex items-center justify-between p-2.5 rounded-xl"
        style={{ background: "rgba(13,21,37,0.6)", border: "1px solid rgba(26,37,64,0.4)" }}>
        <div className="flex items-center gap-1.5">
          <DollarSign size={11} className="text-sentinel-muted" />
          <span className="mono text-[9px] text-sentinel-muted tracking-wider">LLM COST</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="mono text-[9px] px-1.5 py-0.5 rounded"
            style={{ background: `${costColor}15`, color: costColor, border: `1px solid ${costColor}30` }}>
            {costStatus}
          </span>
          <span className="mono text-[10px] text-sentinel-text">${llmCost.toFixed(2)}</span>
        </div>
      </div>

      {/* Sources + Signals */}
      <div className="grid grid-cols-2 gap-2">
        <div className="p-2.5 rounded-xl text-center"
          style={{ background: "rgba(0,102,255,0.06)", border: "1px solid rgba(0,102,255,0.12)" }}>
          <div className="display-font font-bold text-lg text-sentinel-text">{sourcesCount}</div>
          <div className="mono text-[8px] text-sentinel-muted tracking-wider">SOURCES</div>
        </div>
        <div className="p-2.5 rounded-xl text-center"
          style={{ background: "rgba(0,232,122,0.06)", border: "1px solid rgba(0,232,122,0.12)" }}>
          <div className="display-font font-bold text-lg text-[#00E87A]">{signalsCount}</div>
          <div className="mono text-[8px] text-sentinel-muted tracking-wider">SIGNALS</div>
        </div>
      </div>

      {/* Status row */}
      <div className="flex items-center gap-2 pt-1">
        <Cpu size={10} className="text-sentinel-muted" />
        <span className="mono text-[9px] text-sentinel-muted tracking-wider flex-1">SCRAPING STATUS</span>
        <span className="mono text-[9px] text-[#00E87A]">COMPLIANT</span>
      </div>
    </div>
  );
}