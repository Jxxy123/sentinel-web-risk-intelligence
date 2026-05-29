"use client";
import { useState } from "react";
import { type RiskReport, getRiskColor } from "@/lib/api";
import {
  AlertTriangle, TrendingUp, TrendingDown, Minus,
  CheckCircle, ExternalLink, Activity, Shield,
  FileWarning, Globe, Zap, ChevronDown, ChevronUp, Sparkles, Trash2,
} from "lucide-react";

interface Props { 
  report: RiskReport; 
  riskColor: string; 
  currentLanguage?: string;
  onDelete?: (id: number, e: React.MouseEvent) => void; // 🌐 NEW: Added action callback property hooks
}

const CATEGORY_ICONS: Record<string, any> = {
  Financial: AlertTriangle, Operational: Activity,
  Legal: FileWarning, Reputational: Globe, Cybersecurity: Shield,
};

// 🌐 INNER EXECUTIVE CARD CONTAINER TEXT METRICS
const CARD_DICTIONARY: Record<string, Record<string, string>> = {
  EN: { banner: "RISK REPORT —", exSummary: "EXECUTIVE INTELLIGENCE SUMMARY", primary: "PRIMARY RISK", horizon: "TIME HORIZON", used: "SOURCES USED", live: "live", findings: "KEY FINDINGS", actions: "RECOMMENDED ACTIONS", signals: "DETECTED RISK SIGNALS", sourcesHeader: "INTELLIGENCE SOURCES" },
  ZH: { banner: "企业风险报告 —", exSummary: "核心执行安全情报摘要", primary: "首要风险类别", horizon: "评估时间范围", used: "已调用数据源", live: "实时节点", findings: "核心风险点核查", actions: "系统推荐应对措施", signals: "已捕获风险特征信号", sourcesHeader: "底层情报源文件" },
  AR: { banner: "تقرير المخاطر —", exSummary: "ملخص الاستخبارات التنفيذي", primary: "المخاطر الرئيسية", horizon: "الأفق الزمني", used: "المصادر المستخدمة", live: "حي", findings: "النتائج الرئيسية", actions: "الإجراءات الموصى بها", signals: "إشارات المخاطر المكتشفة", sourcesHeader: "مصادر الاستخبارات" },
  BN: { banner: "ঝুঁকি প্রতিবেদন —", exSummary: "এক্সিকিউティブ ইন্টেলিজেন্স সারাংশ", primary: "প্রধান ঝুঁকি", horizon: "সময়সীমা", used: "ব্যবহৃত উৎস", live: "সরাসري", findings: "প্রধান ফলাফল সমূহ", actions: "সুপারিশকৃত পদক্ষেপ", signals: "শনাক্তকৃত ঝুঁকি সংকেত", sourcesHeader: "ইন্টেলিজেন্স সোর্স সমূহ" },
  DE: { banner: "RISIKOBERICHT —", exSummary: "EXEKUTIVE ZUSAMMENFASSUNG", primary: "HAUPTRISIKO", horizon: "ZEITHORIZONT", used: "QUELLEN", live: "aktiv", findings: "SCHLÜSSELERNKENNTNISSE", actions: "EMPFOHLENE MASSNAHMEN", signals: "ERFASSTE RISIKOSIGNALE", sourcesHeader: "INTELLIGENZQUELLEN" },
  JA: { banner: "リスク評価報告書 —", exSummary: "エグゼクティブ・インテリジェンス・サマリー", primary: "最優先リスク分野", horizon: "予測タイムホライズン", used: "解析ソース数", live: "稼働中", findings: "主な検出事項", actions: "推奨される対応策", signals: "検知されたリスクシグナル群", sourcesHeader: "参照インテリジェンスソース" }
};

export default function RiskReportCard({ report, riskColor, currentLanguage = "EN", onDelete }: Props) {
  const [showSources, setShowSources] = useState(false);
  const [showSignals, setShowSignals] = useState(false);
  const color = getRiskColor(report.risk_level);
  
  const rc = CARD_DICTIONARY[currentLanguage] || CARD_DICTIONARY.EN;

  const TrendIcon = report.risk_trajectory === "Improving" ? TrendingDown
    : (report.risk_trajectory === "Deteriorating" || report.risk_trajectory === "Critical") ? TrendingUp
    : Minus;
  const trendColor = report.risk_trajectory === "Improving" ? "#00E87A"
    : (report.risk_trajectory === "Deteriorating" || report.risk_trajectory === "Critical") ? "#FF2D55"
    : "#F5A623";

  return (
    <div className="panel panel-glow rounded-2xl overflow-hidden">

      {/* Risk level banner */}
      <div className="px-6 py-3 flex items-center justify-between"
        style={{ background: `linear-gradient(90deg,${color}12,${color}06,transparent)`, borderBottom: `1px solid ${color}20` }}>
        <div className="flex items-center gap-3">
          <AlertTriangle size={13} style={{ color }} />
          <span className="mono text-[10px] tracking-[0.25em] style={{ color }}">
            {rc.banner} {report.vendor_name?.toUpperCase()}
          </span>
          <span className={`px-2.5 py-0.5 rounded-lg text-[10px] mono font-bold badge-${report.risk_level?.toLowerCase()}`}>
            {report.risk_level}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="mono text-[10px] text-sentinel-muted">
            {report.generated_at ? new Date(report.generated_at).toLocaleString() : "Just now"}
          </span>
          {onDelete && report.id && (
            <button
              onClick={(e) => onDelete(report.id!, e)}
              className="p-1 rounded text-slate-500 hover:text-red-500 hover:bg-red-500/10 transition-colors"
              title="Delete report"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      <div className="p-6 space-y-5">

        {/* ── EXECUTIVE SUMMARY — Visual Centrepiece ── */}
        <div className="rounded-2xl p-6 relative overflow-hidden"
          style={{ background: "rgba(0,102,255,0.04)", border: `1px solid ${color}20` }}>
          <div className="absolute top-0 right-0 w-24 h-24 pointer-events-none"
            style={{ background: `radial-gradient(circle at top right, ${color}10, transparent 70%)` }} />

          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex items-center gap-2">
              <Sparkles size={14} style={{ color }} />
              <span className="mono text-[10px] tracking-[0.2em]" style={{ color }}>
                {rc.exSummary}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <TrendIcon size={13} style={{ color: trendColor }} />
              <span className="mono text-[10px]" style={{ color: trendColor }}>
                {report.risk_trajectory?.toUpperCase()}
              </span>
            </div>
          </div>

          <h2 className="display-font font-bold text-xl text-sentinel-text leading-snug mb-4">
            {report.risk_headline}
          </h2>

          <p className="text-sentinel-text/90 text-sm leading-relaxed">
            {report.executive_summary}
          </p>

          <div className="flex items-center gap-4 mt-4 pt-4" style={{ borderTop: `1px solid ${color}15` }}>
            <div>
              <div className="mono text-[8px] text-sentinel-muted tracking-wider">{rc.primary}</div>
              <div className="mono text-xs text-sentinel-text mt-0.5">{report.primary_risk_category}</div>
            </div>
            <div className="w-px h-8 bg-sentinel-border/50" />
            <div>
              <div className="mono text-[8px] text-sentinel-muted tracking-wider">{rc.horizon}</div>
              <div className="mono text-xs text-sentinel-text mt-0.5">{report.time_horizon || "—"}</div>
            </div>
            <div className="w-px h-8 bg-sentinel-border/50" />
            <div>
              <div className="mono text-[8px] text-sentinel-muted tracking-wider">{rc.used}</div>
              <div className="mono text-xs text-sentinel-text mt-0.5">{report.sources?.length || 0} {rc.live}</div>
            </div>
            <div className="ml-auto flex items-center gap-1.5">
              <Zap size={10} className="text-[#00D4FF]" />
              <span className="mono text-[9px] text-[#00D4FF]">BRIGHT DATA</span>
            </div>
          </div>
        </div>

        {/* ── KEY FINDINGS ── */}
        {report.key_findings?.length > 0 && (
          <div>
            <div className="mono text-[9px] text-sentinel-muted tracking-widest mb-3">{rc.findings}</div>
            <div className="grid grid-cols-1 gap-2">
              {report.key_findings.map((finding, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-xl"
                  style={{ background: "rgba(13,21,37,0.6)", border: "1px solid rgba(26,37,64,0.4)" }}>
                  <div className="w-5 h-5 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: `${color}12`, border: `1px solid ${color}25` }}>
                    <span className="mono text-[9px] font-bold" style={{ color }}>{i + 1}</span>
                  </div>
                  <span className="text-sentinel-text text-sm leading-relaxed">{finding}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="divider-glow" />

        {/* ── RECOMMENDED ACTIONS ── */}
        {report.recommended_actions?.length > 0 && (
          <div>
            <div className="mono text-[9px] text-sentinel-muted tracking-widest mb-3">{rc.actions}</div>
            <div className="grid grid-cols-1 gap-2">
              {report.recommended_actions.map((action, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-xl"
                  style={{ background: "rgba(0,232,122,0.04)", border: "1px solid rgba(0,232,122,0.12)" }}>
                  <CheckCircle size={13} className="text-[#00E87A] flex-shrink-0" />
                  <span className="text-sentinel-text text-sm">{action}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── COLLAPSIBLE RISK SIGNALS ── */}
        {report.signals?.length > 0 && (
          <div>
            <button onClick={() => setShowSignals(!showSignals)} className="w-full flex items-center justify-between py-2 group">
              <span className="mono text-[9px] text-sentinel-muted tracking-widest group-hover:text-sentinel-text transition-colors">
                {rc.signals} ({report.signals.length})
              </span>
              {showSignals ? <ChevronUp size={13} className="text-sentinel-muted" /> : <ChevronDown size={13} className="text-sentinel-muted" />}
            </button>
            {showSignals && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                {report.signals.map((signal, i) => {
                  const sigColor = getRiskColor(signal.severity?.toUpperCase() || "LOW");
                  const Icon = CATEGORY_ICONS[signal.category] || Activity;
                  return (
                    <div key={i} className="rounded-xl p-3.5" style={{ background: `${sigColor}07`, border: `1px solid ${sigColor}18` }}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Icon size={12} style={{ color: sigColor }} />
                          <span className="mono text-[9px] font-medium tracking-wider" style={{ color: sigColor }}>
                            {signal.category?.toUpperCase()}
                          </span>
                        </div>
                        <span className={`px-1.5 py-0.5 rounded text-[8px] mono font-semibold badge-${signal.severity?.toLowerCase()}`}>
                          {signal.severity?.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {signal.indicators?.slice(0, 3).map((ind, j) => (
                          <span key={j} className="text-[10px] px-2 py-0.5 rounded-full text-sentinel-muted" style={{ background: "rgba(26,37,64,0.7)" }}>
                            {ind}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── COLLAPSIBLE SOURCES ── */}
        {report.sources?.length > 0 && (
          <div>
            <button onClick={() => setShowSources(!showSources)} className="w-full flex items-center justify-between py-2 group">
              <span className="mono text-[9px] text-sentinel-muted tracking-widest group-hover:text-sentinel-text transition-colors">
                {rc.sourcesHeader} ({report.sources.length})
              </span>
              {showSources ? <ChevronUp size={13} className="text-sentinel-muted" /> : <ChevronDown size={13} className="text-sentinel-muted" />}
            </button>
            {showSources && (
              <div className="space-y-1.5 mt-2">
                {report.sources.slice(0, 6).map((source, i) => (
                  <a key={i} href={source.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 p-2.5 rounded-lg group hover:bg-[#0066FF]/05 transition-colors" style={{ border: "1px solid rgba(26,37,64,0.3)" }}>
                    <ExternalLink size={10} className="text-sentinel-muted flex-shrink-0 group-hover:text-[#0066FF] transition-colors" />
                    <span className="text-sentinel-muted text-xs truncate group-hover:text-sentinel-text transition-colors">
                      {source.title || source.url}
                    </span>
                  </a>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}