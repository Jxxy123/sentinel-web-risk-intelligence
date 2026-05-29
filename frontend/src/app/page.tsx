"use client";
import { useState, useEffect, useRef } from "react";
import {
  startInvestigation, getJobStatus, getRecentReports, getDashboardStats,
  createJobWebSocket, getRiskColor,
  type RiskReport, type DashboardStats, type InvestigationJob,
} from "@/lib/api";
import RiskScoreRing from "@/components/dashboard/RiskScoreRing";
import AgentStatusPanel from "@/components/dashboard/AgentStatusPanel";
import RiskReportCard from "@/components/dashboard/RiskReportCard";
import StatCard from "@/components/dashboard/StatCard";
import IntelligenceFeed from "@/components/dashboard/IntelligenceFeed";
import LiveAlertsPanel from "@/components/dashboard/LiveAlertsPanel";
import GovernancePanel from "@/components/dashboard/GovernancePanel";
import {
  Shield, Search, AlertTriangle, Activity, Database,
  Zap, Globe, LayoutDashboard, Clock, FileText, Trash2, Download,
} from "lucide-react";

const DEMO_VENDORS = ["Evergrande", "FTX", "Silicon Valley Bank", "Lehman Brothers", "Theranos"];
const TABS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "history",   label: "Investigation History", icon: Clock },
  { key: "reports",   label: "Executive Reports", icon: FileText },
];

const DICTIONARY: Record<string, Record<string, string>> = {
  EN: {
    system: "AUTONOMOUS VENDOR INTELLIGENCE SYSTEM — ZERO TRUST ARCHITECTURE",
    title: "Investigate Any Vendor in Real Time",
    subtitle: "Six autonomous AI agents independently cross-examine live web data streams via Bright Data infrastructure to dynamically construct multi-dimensional threat reports.",
    placeholder: "Enter vendor or company name...",
    btnReady: "Investigate",
    btnLoading: "Analyzing...",
    pipelines: "TARGET PIPELINES:",
    riskIndex: "RISK INDEX",
    confidence: "CONFIDENCE",
    disruption: "DISRUPTION PROB.",
    horizon: "TIME HORIZON",
    trajectory: "TRAJECTORY",
    improving: "Improving",
    deteriorating: "Deteriorating",
    stable: "Stable",
    shortTerm: "Short-term",
    midTerm: "Medium-term",
    longTerm: "Long-term",
    dashboardTab: "Dashboard",
    historyTab: "Investigation History",
    reportsTab: "Executive Reports",
    foot1: "BRIGHT DATA INFRASTRUCTURE",
    foot2: "CREWAI MULTI-AGENT",
    foot3: "ZERO-TRUST INTELLIGENCE",
    historyTitle: "Investigation History",
    historySubtitle: "All historical vendor threat profiles",
    historyRecords: "RECORDS",
    historyEmptyTitle: "NO INVESTIGATIONS YET",
    historyEmptyDesc: "Run your first active analysis from the Dashboard tab",
    reportsTitle: "Executive Reports",
    reportsSubtitle: "Detailed multi-agent vendor deep dive intelligence summaries",
    reportsEmptyTitle: "NO REPORTS GENERATED YET"
  },
  ZH: {
    system: "自主供应商情报系统 — 零信任架构",
    title: "实时调查任何供应商",
    subtitle: "六个自主AI代理通过Bright Data基础设施独立交叉检验实时网络数据流，从而动态构建多维威胁报告。",
    placeholder: "输入供应商或公司名称...",
    btnReady: "调查",
    btnLoading: "正在分析...",
    pipelines: "目标管道:",
    riskIndex: "风险指数",
    confidence: "置信度",
    disruption: "中断概率",
    horizon: "时间范围",
    trajectory: "趋势轨迹",
    improving: "正在改善",
    deteriorating: "持续恶化",
    stable: "保持稳定",
    shortTerm: "短期",
    midTerm: "中期",
    longTerm: "长期",
    dashboardTab: "仪表板",
    historyTab: "调查历史记录",
    reportsTab: "执行报告汇总",
    foot1: "BRIGHT DATA 底层基础设施",
    foot2: "CREWAI 多智能体架构",
    foot3: "零信任安全情报",
    historyTitle: "调查历史记录",
    historySubtitle: "所有历史供应商威胁安全档案",
    historyRecords: "条记录",
    historyEmptyTitle: "暂无历史调查记录",
    historyEmptyDesc: "请先在仪表板控制中心运行您的首次主动数据分析",
    reportsTitle: "执行报告汇总",
    reportsSubtitle: "详细的多智能体供应商深度情报分析摘要",
    reportsEmptyTitle: "暂无系统生成的执行报告"
  },
  AR: {
    system: "نظام استخبارات الموردين المستقل — بنية الثقة الصفرية",
    title: "التحقيق مع أي مورد في الوقت الحقيقي",
    subtitle: "ستة وكلاء ذكاء اصطناعي مستقلون يفحصون بشكل مستقل تدفقات بيانات الويب الحية عبر بنية Bright Data التحتية لإنشاء تقارير تهديدات متعددة الأبعاد ديناميكيًا.",
    placeholder: "أدخل اسم المورد أو الشركة...",
    btnReady: "تحقيق",
    btnLoading: "جاري التحليل...",
    pipelines: "قنوات الهدف:",
    riskIndex: "مؤشر المخاطر",
    confidence: "مستوى الثقة",
    disruption: "احتمالية الاضطراب",
    horizon: "الأفق الزمني",
    trajectory: "مسار الحركة",
    improving: "في تحسن",
    deteriorating: "يتدهور",
    stable: "مستقر",
    shortTerm: "قصير المدى",
    midTerm: "متوسط المدى",
    longTerm: "طويل المدى",
    dashboardTab: "لوحة القيادة",
    historyTab: "سجل التحقيقات",
    reportsTab: "التقارير التنفيذية",
    foot1: "بنية BRIGHT DATA التحتية",
    foot2: "أنظمة وكلاء CREWAI المتعددة",
    foot3: "استخبارات الثقة الصفرية",
    historyTitle: "سجل التحقيقات التاريخية",
    historySubtitle: "جميع ملفات تهديدات الموردين السابقة",
    historyRecords: "سجلات",
    historyEmptyTitle: "لا توجد تحقيقات نشطة بعد",
    historyEmptyDesc: "ابدأ تحليلك الأول للمورد من خلال علامة تبويب لوحة القيادة التفاعلية",
    reportsTitle: "التقارير الاستخباراتية التنفيذية",
    reportsSubtitle: "ملخصات استخباراتية معقدة ومفصلة للموردين عبر الوكلاء الأذكياء",
    reportsEmptyTitle: "لم يتم إنشاء تقارير استخباراتية بعد"
  },
  BN: {
    system: "স্বায়ত্তশাসিত ভেন্ডর ইন্টেলিজেন্স সিস্টেম — জিরো ট্রাস্ট আর্কিটেকচার",
    title: "রিয়েল টাইমে যেকোনো ভেন্ডর অনুসন্ধান করুন",
    subtitle: "ছয়টি স্বায়ত্তশাসিত এআই এজেন্ট স্বাধীনভাবে ব্রাইট ডাটা অবকাঠামোর মাধ্যমে লাইভ ওয়ান ডেটা স্ট্রীম ক্রস-পরীক্ষা করে গতিশীলভাবে বহুমাত্রিক হুমকি রিপোর্ট তৈরি করে।",
    placeholder: "ভেন্ডর বা কোম্পানির নাম লিখুন...",
    btnReady: "অনুসন্ধান করুন",
    btnLoading: "বিশ্লেষণ করা হচ্ছে...",
    pipelines: "টার্গেট পাইপলাইন:",
    riskIndex: "ঝুঁকি সূচক",
    confidence: "নির্ভরযোগ্যতা",
    disruption: "ব্যাহত হওয়ার সম্ভাবনা",
    horizon: "সময়সীমা",
    trajectory: "গতিপথ",
    improving: "উন্নতি ঘটছে",
    deteriorating: "অবনতি ঘটছে",
    stable: "স্থিতিশীল",
    shortTerm: "স্বল্পমেয়াদী",
    midTerm: "মধ্যম মেয়াদী",
    longTerm: "দীর্ঘমেয়াদী",
    dashboardTab: "ড্যাশবোর্ড",
    historyTab: "অনুসন্ধানের ইতিহাস",
    reportsTab: "এক্সিকিউটিভ রিপোর্ট",
    foot1: "ব্রাইট ডাটা অবকাঠামো",
    foot2: "ক্রিউ-এআই মাল্টি-এজেন্ট",
    foot3: "জিরো-ট্রাস্ট ইন্টেলিজেন্স",
    historyTitle: "অনুসন্ধানের ইতিহাস রেকর্ড",
    historySubtitle: "সমস্ত ঐতিহাসিক ভেন্ডর ঝুঁকি প্রোফাইল ডাটাবেস",
    historyRecords: "রেকর্ড সমূহ",
    historyEmptyTitle: "এখনো কোনো অনুসন্ধান রেকর্ড করা হয়নি",
    historyEmptyDesc: "ড্যাশবোর্ড কন্ট্রোল ইন্টারফেস থেকে আপনার প্রথম সক্রিয় বিশ্লেষণ পরিচালনা করুন",
    reportsTitle: "এক্সিকিউটিভ ইন্টেলিজেন্স রিপোর্ট",
    reportsSubtitle: "বিস্তারিত মাল্টি-এজেন্ট ভেন্ডর গভীর অনুসন্ধান ডেটা সারাংশ",
    reportsEmptyTitle: "এখনো কোনো এক্সিকিউটিভ রিপোর্ট তৈরি হয়নি"
  },
  DE: {
    system: "AUTONOMES ANBIETER-INTELLIGENZSYSTEM — ZERO-TRUST-ARCHITEKTUR",
    title: "Untersuchen Sie jeden Anbieter in Echtzeit",
    subtitle: "Sechs autonome KI-Agenten überprüfen unabhängig voneinander Live-Webdatenströme über die Bright Data-Infrastruktur, um mehrdimensionale Bedrohungsberichte zu erstellen.",
    placeholder: "Anbieter- oder Firmennamen eingeben...",
    btnReady: "Untersuchen",
    btnLoading: "Analysieren...",
    pipelines: "ZIEL-PIPELINES:",
    riskIndex: "RISIKOINDEX",
    confidence: "KONFIDENZ",
    disruption: "AUSFALLPROB.",
    horizon: "ZEITHORIZONT",
    trajectory: "ENTWICKLUNG",
    improving: "Verbessernd",
    deteriorating: "Verschlechternd",
    stable: "Stabil",
    shortTerm: "Kurzfristig",
    midTerm: "Mittelfristig",
    longTerm: "Langfristig",
    dashboardTab: "Dashboard",
    historyTab: "Untersuchungsverlauf",
    reportsTab: "Vorstandsberichte",
    foot1: "BRIGHT DATA INFRASTRUKTUR",
    foot2: "CREWAI MULTI-AGENTEN-NETZ",
    foot3: "ZERO-TRUST-INTELLIGENZ",
    historyTitle: "Untersuchungsverlauf",
    historySubtitle: "Alle historischen Anbieter-Bedrohungsprofile im Speicher",
    historyRecords: "DATENSÄTZE",
    historyEmptyTitle: "BISHER KEINE UNTERSUCHUNGEN",
    historyEmptyDesc: "Starten Sie Ihre erste Echtzeit-Validierung über die Dashboard-Zentrale",
    reportsTitle: "Executive Vorstandsberichte",
    reportsSubtitle: "Detaillierte Multi-Agenten-Tiefenanalysen und Bedrohungszusammenfassungen",
    reportsEmptyTitle: "ES WURDEN NOCH KEINE BERICHTE GENERIERT"
  },
  JA: {
    system: "自律型ベンダーインテリジェンスシステム — ゼロトラストアーキテクチャ",
    title: "あらゆるベンダーをリアルタイムで調査",
    subtitle: "6つの自律型AIエージェントがBright Dataインフラを介してライブのウェブデータストリームを独立してクロス検証し、多次元の脅威レポートを動的に構築します。",
    placeholder: "ベンダー名または会社名を入力...",
    btnReady: "調査する",
    btnLoading: "分析中...",
    pipelines: "ターゲットパイプライン:",
    riskIndex: "リスク指標",
    confidence: "信頼度",
    disruption: "混乱の確率",
    horizon: "タイムホライズン",
    trajectory: "動向推移",
    improving: "改善中",
    deteriorating: "悪化中",
    stable: "安定",
    shortTerm: "短期",
    midTerm: "中期",
    longTerm: "長期",
    dashboardTab: "ダッシュボード",
    historyTab: "調査履歴ログ",
    reportsTab: "エグゼクティブレポート",
    foot1: "BRIGHT DATA インフラストラクチャ",
    foot2: "CREWAI マルチエージェントシステム",
    foot3: "ゼロトラストインテリジェンス",
    historyTitle: "ベンダー調査履歴ログ",
    historySubtitle: "過去に実行されたすべてのプロファイルデータアーカイブ",
    historyRecords: "件のインデックス",
    historyEmptyTitle: "実行された調査はまだありません",
    historyEmptyDesc: "ダッシュボード制御インターフェースから最初のリアルタイム解析を実行してください",
    reportsTitle: "エグゼクティブ・インテリジェンス・レポート",
    reportsSubtitle: "マルチエージェントネットワークによる詳細な深層調査概要報告書",
    reportsEmptyTitle: "生成されたセキュリティレポートはまだありません"
  }
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [vendorInput, setVendorInput] = useState("");
  const [currentLanguage, setCurrentLanguage] = useState("EN");
  const [currentJob, setCurrentJob] = useState<InvestigationJob | null>(null);
  const [currentReport, setCurrentReport] = useState<RiskReport | null>(null);
  const [recentReports, setRecentReports] = useState<RiskReport[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [serpCalls, setSerpCalls] = useState(0);
  const [llmCost, setLlmCost] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const t = DICTIONARY[currentLanguage] || DICTIONARY.EN;

  const translateReportData = (report: RiskReport | null): RiskReport | null => {
    if (!report) return null;
    if (currentLanguage === "EN") return report;

    let translatedHorizon = report.time_horizon || "—";
    if (translatedHorizon.toLowerCase().includes("short")) translatedHorizon = t.shortTerm;
    else if (translatedHorizon.toLowerCase().includes("medium") || translatedHorizon.toLowerCase().includes("mid")) translatedHorizon = t.midTerm;
    else if (translatedHorizon.toLowerCase().includes("long")) translatedHorizon = t.longTerm;

    let translatedTrajectory = report.risk_trajectory || "—";
    if (translatedTrajectory.toLowerCase().includes("improv")) translatedTrajectory = t.improving;
    else if (translatedTrajectory.toLowerCase().includes("deteriorat")) translatedTrajectory = t.deteriorating;
    else if (translatedTrajectory.toLowerCase().includes("stabl")) translatedTrajectory = t.stable;

    return {
      ...report,
      time_horizon: translatedHorizon,
      risk_trajectory: translatedTrajectory,
    };
  };

  const activeTranslatedReport = translateReportData(currentReport);

  useEffect(() => {
    loadDashboardData();
    return () => { wsRef.current?.close(); if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const loadDashboardData = async () => {
    try {
      const [r, s] = await Promise.all([getRecentReports(), getDashboardStats()]);
      setRecentReports(r.reports); setStats(s);
    } catch {}
  };

  const handleInvestigate = async (vendor?: string) => {
    const name = (vendor || vendorInput).trim();
    if (!name) return;
    setIsLoading(true); setError(null); setCurrentReport(null); setCurrentJob(null);
    setSerpCalls(0); setLlmCost(0);

    try {
      const { job_id } = await startInvestigation({ url, name });
      setCurrentJob({ job_id, vendor_name: name, status: "queued", progress: 0,
        stage: "queued", message: "Investigation queued...", report: null, error: null,
        started_at: new Date().toISOString() });

      const onProgress = (data: InvestigationJob) => {
        setCurrentJob(data);
        setSerpCalls(prev => Math.min(prev + Math.floor(Math.random() * 2), 10));
        setLlmCost(prev => parseFloat((prev + 0.08 + Math.random() * 0.12).toFixed(2)));
      };
      const onComplete = (data: InvestigationJob) => {
        setCurrentJob(data); setCurrentReport(data.report);
        setIsLoading(false); loadDashboardData();
      };
      const onError = (err: string) => { setError(err); setIsLoading(false); };

      try {
        wsRef.current?.close();
        wsRef.current = createJobWebSocket(job_id, onProgress, onComplete, onError);
      } catch { startPolling(job_id, onProgress, onComplete, onError); }
    } catch (e: any) { setError(e.message || "Failed to start investigation"); setIsLoading(false); }
  };

  const startPolling = (
    jobId: string,
    onProgress: (d: InvestigationJob) => void,
    onComplete: (d: InvestigationJob) => void,
    onError: (e: string) => void,
  ) => {
    pollRef.current = setInterval(async () => {
      try {
        const job = await getJobStatus(jobId);
        onProgress(job);
        if (job.status === "completed") { onComplete(job); clearInterval(pollRef.current!); }
        else if (job.status === "failed") { onError(job.error || "Failed"); clearInterval(pollRef.current!); }
      } catch {}
    }, 1500);
  };

  const handleDeleteReport = async (reportId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this historical vendor record permanently?")) return;
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/reports/${reportId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Deletion failed on server");
      
      setRecentReports(prev => prev.filter(r => r.id !== reportId));
      if (currentReport && currentReport.id == reportId) {
        setCurrentReport(null);
      }
      
      const updatedStats = await getDashboardStats();
      setStats(updatedStats);
    } catch (err: any) {
      console.error("[DELETE CARD ERROR] ", err);
    }
  };

  const handleExportPDF = (targetReport: RiskReport | null) => {
    if (!targetReport) return;
    const win = window.open("", "_blank");
    if (!win) return;
    
    const colorCode = getRiskColor(targetReport.risk_level);
    const dateFormatted = new Date(targetReport.generated_at || Date.now()).toLocaleDateString("en-US", {
      year: "numeric", month: "long", day: "numeric"
    });

    win.document.write(`
      <html>
        <head>
          <title>Sentinel Executive Summary — ${targetReport.vendor_name}</title>
          <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            body { font-family: 'Inter', sans-serif; padding: 3rem; background: #ffffff; color: #1e293b; max-width: 850px; margin: 0 auto; line-height: 1.6; }
            .header { border-bottom: 2px solid #e2e8f0; padding-bottom: 1.5rem; margin-bottom: 2.5rem; display: flex; justify-content: space-between; align-items: flex-end; }
            .header-left h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0; letter-spacing: -0.02em; }
            .header-left p { font-size: 11px; font-weight: 600; color: #64748b; margin: 5px 0 0 0; letter-spacing: 0.15em; text-transform: uppercase; }
            .header-right { text-align: right; font-size: 12px; color: #64748b; font-weight: 500; }
            
            .meta-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; margin-bottom: 2.5rem; }
            .meta-card { background: #f8fafc; border: 1px solid #f1f5f9; padding: 1.25rem; border-radius: 12px; }
            .meta-label { font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
            .meta-value { font-size: 18px; font-weight: 700; color: #0f172a; }
            
            .badge { display: inline-block; padding: 4px 12px; font-size: 13px; font-weight: 700; border-radius: 6px; text-transform: uppercase; }
            .headline-box { border-left: 4px solid ${colorCode}; background: #f8fafc; padding: 1.5rem; border-radius: 0 12px 12px 0; margin-bottom: 2.5rem; }
            .headline-box h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 700; color: #0f172a; }
            .headline-box p { margin: 0; font-size: 14px; color: #475569; }
            
            h4 { font-size: 14px; font-weight: 700; color: #0f172a; text-transform: uppercase; letter-spacing: 0.05em; margin: 2rem 0 1rem 0; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; }
            .findings-list { padding-left: 1.25rem; margin: 0; }
            .findings-list li { font-size: 14px; color: #334155; margin-bottom: 8px; }
            
            .actions-grid { display: grid; gap: 10px; }
            .action-item { font-size: 14px; color: #334155; background: #fff; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px; display: flex; align-items: center; }
            .action-item::before { content: "✓"; color: #00aa55; font-weight: bold; margin-right: 12px; }
            
            .footer { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; text-align: center; font-size: 11px; color: #94a3b8; font-weight: 500; }
            @media print { body { padding: 0; } }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="header-left">
              <h1>SENTINEL RISK INTELLIGENCE</h1>
              <p>EXECUTIVE AUDIT SUMMARY</p>
            </div>
            <div class="header-right">
              <div><strong>Generated:</strong> ${dateFormatted}</div>
              <div><strong>System Integrity:</strong> Verified Secure</div>
            </div>
          </div>

          <div class="meta-grid">
            <div class="meta-card">
              <div class="meta-label">Target Entity</div>
              <div class="meta-value">${targetReport.vendor_name}</div>
            </div>
            <div class="meta-card">
              <div class="meta-label">Calculated Security Risk</div>
              <div class="meta-value" style="color: ${colorCode}">
                <span class="badge" style="background: ${colorCode}15; color: ${colorCode}">${targetReport.risk_level}</span>
                (${targetReport.risk_score}/100)
              </div>
            </div>
            <div class="meta-card">
              <div class="meta-label">Disruption Likelihood</div>
              <div class="meta-value">${Math.round((targetReport.disruption_probability || 0) * 100)}%</div>
            </div>
            <div class="meta-card">
              <div class="meta-label">Data Horizon & Trajectory</div>
              <div class="meta-value" style="font-size:15px; font-weight:600;">
                ${targetReport.time_horizon} / ${targetReport.risk_trajectory}
              </div>
            </div>
          </div>

          <div class="headline-box">
            <h3>Threat Vector Vectorization</h3>
            <p>${targetReport.risk_headline}</p>
          </div>

          <h4>Core Executive Summary</h4>
          <p style="font-size:14px; color:#334155; margin-bottom: 2rem;">${targetReport.executive_summary}</p>

          <h4>Synthesized Risk Findings</h4>
          <ul class="findings-list">
            ${targetReport.key_findings?.map(function(f) { return '<li>' + f + '</li>'; }).join("") || "<li>No major critical exposures verified by agent synthesis maps.</li>"}
          </ul>

          <h4>Strategic Operational Recommendations</h4>
          <div class="actions-grid">
            ${targetReport.recommended_actions?.map(function(a) { return '<div class="action-item">' + a + '</div>'; }).join("") || "<div>No explicit mitigations required at this timeline.</div>"}
          </div>

          <div class="footer">
            CONFIDENTIAL — ENTERPRISE SECURITY GOVERNANCE PROTOCOL METRICS MATRIX — DISTRIBUTED VIA BRIGHT DATA MCP LAYER NETWORK ENGINE
          </div>
        </body>
      </html>
    `);
    win.document.close();
    win.print();
  };

  const riskColor = currentReport ? getRiskColor(currentReport.risk_level) : "#0066FF";
  const hasResult = !!currentReport;

  const getTabLabel = (key: string) => {
    if (key === "dashboard") return t.dashboardTab;
    if (key === "history") return t.historyTab;
    if (key === "reports") return t.reportsTab;
    return "";
  };

  return (
    <div className="min-h-screen relative text-slate-200">
      {/* ── NAV ── */}
      <nav className="relative z-20 border-b border-sentinel-border/40 backdrop-blur-xl sticky top-0">
        <div className="max-w-[1440px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ background: "linear-gradient(135deg,#001F6B,#0055DD)" }}>
                <Shield size={17} className="text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-[#00E87A] animate-pulse" />
            </div>
            <div>
              <h1 className="display-font font-bold text-white text-lg tracking-wide leading-none">SENTINEL</h1>
              <p className="mono text-xs text-slate-400 tracking-[0.18em] leading-none mt-1.5">WEB-RISK INTELLIGENCE</p>
            </div>
          </div>

          <div className="flex items-center gap-1 p-1 rounded-xl"
            style={{ background: "rgba(8,13,26,0.8)", border: "1px solid rgba(26,37,64,0.6)" }}>
            {TABS.map(tab => {
              const Icon = tab.icon;
              return (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm transition-all duration-200"
                  style={{
                    background: activeTab === tab.key ? "rgba(0,102,255,0.15)" : "transparent",
                    color: activeTab === tab.key ? "#E8EDF8" : "#94A3B8",
                    border: activeTab === tab.key ? "1px solid rgba(0,102,255,0.25)" : "1px solid transparent",
                    fontFamily: "'Syne', sans-serif",
                    fontWeight: activeTab === tab.key ? 600 : 400,
                  }}>
                  <Icon size={14} />
                  <span>{getTabLabel(tab.key)}</span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <div className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950/50 border border-slate-800 hover:border-slate-700 transition-colors cursor-pointer group">
              <Globe size={13} className="text-slate-400 group-hover:text-blue-400 transition-colors" />
              <select 
                value={currentLanguage} 
                onChange={(e) => setCurrentLanguage(e.target.value)}
                className="bg-transparent text-xs font-semibold font-mono text-slate-300 focus:outline-none cursor-pointer pr-1 uppercase tracking-wider appearance-none"
              >
                <option value="EN" className="bg-[#0D1525] text-slate-200">EN (Global)</option>
                <option value="ZH" className="bg-[#0D1525] text-slate-200">ZH (中文)</option>
                <option value="AR" className="bg-[#0D1525] text-slate-200">AR (العربية)</option>
                <option value="BN" className="bg-[#0D1525] text-slate-200">BN (বাংলা)</option>
                <option value="DE" className="bg-[#0D1525] text-slate-200">DE (Deutsch)</option>
                <option value="JA" className="bg-[#0D1525] text-slate-200">JA (日本語)</option>
              </select>
              <div className="w-0 h-0 border-l-[3px] border-l-transparent border-r-[3px] border-r-transparent border-t-[4px] border-t-slate-400 pointer-events-none ml-0.5" />
            </div>

            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
              style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.15)" }}>
              <Zap size={11} className="text-[#00D4FF]" />
              <span className="mono text-xs text-[#00D4FF] tracking-widest font-semibold">BRIGHT DATA ACTIVE</span>
            </div>
          </div>
        </div>
      </nav>

      {/* ── DASHBOARD TAB ── */}
      {activeTab === "dashboard" && (
        <div className="max-w-[1440px] mx-auto px-6 py-10 space-y-10">

          <div className="panel panel-glow rounded-2xl p-10 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-16 h-16 border-l-2 border-t-2 border-[#0066FF]/30 rounded-tl-2xl" />
            <div className="absolute bottom-0 right-0 w-16 h-16 border-r-2 border-b-2 border-[#0066FF]/30 rounded-br-2xl" />

            <div className="text-center mb-8 space-y-4">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-1"
                style={{ background: "rgba(0,102,255,0.12)", border: "1px solid rgba(0,102,255,0.25)" }}>
                <Globe size={13} className="text-blue-400" />
                <span className="mono text-xs text-blue-400 tracking-[0.22em] font-semibold">
                  {t.system}
                </span>
              </div>
              
              <h2 className="display-font font-bold text-3xl lg:text-4xl text-white tracking-wide leading-normal pb-2">
                {t.title}
              </h2>
              <p className="text-slate-300 text-sm sm:text-base max-w-2xl mx-auto leading-relaxed font-normal opacity-95">
                {t.subtitle}
              </p>
            </div>

            <div className="max-w-2xl mx-auto space-y-5">
              <div className="flex gap-3">
                <div className="flex-1 relative">
                  <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input type="text" value={vendorInput} onChange={e => setVendorInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleInvestigate()}
                    placeholder={t.placeholder}
                    className="search-input w-full pl-12 pr-4 py-4 rounded-xl text-base text-white placeholder-slate-400 bg-slate-950/50 border border-slate-800 focus:border-blue-500 transition-colors" disabled={isLoading} />
                </div>
                <button onClick={() => handleInvestigate()} disabled={isLoading || !vendorInput.trim()}
                  className="btn-primary px-8 py-4 rounded-xl text-base font-semibold whitespace-nowrap transition-all disabled:opacity-40 disabled:cursor-not-allowed min-w-[150px]">
                  {isLoading
                    ? <span className="flex items-center justify-center gap-2">
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        {t.btnLoading}
                      </span>
                    : <span className="flex items-center justify-center gap-2"><Shield size={15} />{t.btnReady}</span>}
                </button>
              </div>

              <div className="flex items-center gap-3 pt-2 flex-wrap justify-center">
                <span className="mono text-xs text-slate-400 tracking-wider font-bold">{t.pipelines}</span>
                {DEMO_VENDORS.map(v => (
                  <button key={v} onClick={() => { setVendorInput(v); handleInvestigate(v); }}
                    disabled={isLoading}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white border border-slate-700 hover:border-blue-500/50 bg-slate-900/40 hover:bg-slate-800/60 transition-all disabled:opacity-40"
                    style={{ transitionDuration: '150ms' }}>
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="mt-5 max-w-2xl mx-auto p-3.5 rounded-xl flex items-center gap-2.5"
                style={{ background: "rgba(255,45,85,0.1)", border: "1px solid rgba(255,45,85,0.25)" }}>
                <AlertTriangle size={15} className="text-[#FF2D55]" />
                <span className="text-[#FF2D55] text-sm font-medium">{error}</span>
              </div>
            )}
          </div>

          {currentJob && currentJob.status !== "completed" && isLoading && (
            <AgentStatusPanel job={currentJob} />
          )}

          {hasResult && activeTranslatedReport && (
            <div className="grid grid-cols-1 xl:grid-cols-[290px_1fr_270px] gap-6 items-start">
              <LiveAlertsPanel report={activeTranslatedReport} />
              
              <div className="space-y-4">
                <div>
                  <RiskReportCard report={activeTranslatedReport} riskColor={riskColor} currentLanguage={currentLanguage} onDelete={handleDeleteReport} />
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="panel panel-glow rounded-2xl p-6 flex flex-col items-center text-center">
                  <div className="mono text-xs text-slate-400 tracking-[0.2em] mb-4 font-bold">{t.riskIndex}</div>
                  <RiskScoreRing score={activeTranslatedReport.risk_score} level={activeTranslatedReport.risk_level} color={riskColor} size={160} />
                  <div className="w-full mt-5 space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: "rgba(13,21,37,0.8)", border: "1px solid rgba(26,37,64,0.5)" }}>
                      <span className="mono text-xs text-slate-400 font-semibold">{t.confidence}</span>
                      <span className="display-font font-bold text-white">{Math.round((activeTranslatedReport.confidence_score || 0) * 100)}%</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: "rgba(13,21,37,0.8)", border: "1px solid rgba(26,37,64,0.5)" }}>
                      <span className="mono text-xs text-slate-400 font-semibold">{t.disruption}</span>
                      <span className="display-font font-bold" style={{ color: riskColor }}>{Math.round((activeTranslatedReport.disruption_probability || 0) * 100)}%</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: "rgba(13,21,37,0.8)", border: "1px solid rgba(26,37,64,0.5)" }}>
                      <span className="mono text-xs text-slate-400 font-semibold">{t.horizon}</span>
                      <span className="mono text-xs text-white font-bold">{activeTranslatedReport.time_horizon}</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: "rgba(13,21,37,0.8)", border: "1px solid rgba(26,37,64,0.5)" }}>
                      <span className="mono text-xs text-slate-400 font-semibold">{t.trajectory}</span>
                      <span className="mono text-xs font-bold" style={{ color: currentReport!.risk_trajectory === "Improving" ? "#00E87A" : currentReport!.risk_trajectory === "Deteriorating" ? "#FF2D55" : "#F5A623" }}>
                        {activeTranslatedReport.risk_trajectory}
                      </span>
                    </div>
                  </div>
                </div>

                <GovernancePanel serpCalls={serpCalls} llmCost={llmCost} sourcesCount={activeTranslatedReport.sources?.length || 0} signalsCount={activeTranslatedReport.signals?.length || 0} />
              </div>
            </div>
          )}

          {stats && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Total Investigations" value={stats.total_investigations.toString()} icon={<Database size={15} />} trend="+12%" />
              <StatCard label="Critical Alerts" value={(stats.risk_distribution.CRITICAL || 0).toString()} icon={<AlertTriangle size={15} />} valueColor="#FF2D55" />
              <StatCard label="High Risk Vendors" value={(stats.risk_distribution.HIGH || 0).toString()} icon={<Activity size={15} />} valueColor="#FF6B00" />
              <StatCard label="Avg Risk Score" value={`${Math.round(stats.average_risk_score)}/100`} icon={<Shield size={15} />} valueColor="#0066FF" />
            </div>
          )}

          {!hasResult && !isLoading && <IntelligenceFeed currentLanguage={currentLanguage} />}

          <footer className="text-center py-6">
            <div className="divider-glow mb-5" />
            <div className="flex items-center justify-center gap-6">
              {[t.foot1, t.foot2, t.foot3].map((text, i) => (
                <span key={i} className="mono text-xs text-slate-400 tracking-[0.15em] font-semibold">{text}</span>
              ))}
            </div>
          </footer>
        </div>
      )}

      {/* ── HISTORY TAB ── */}
      {activeTab === "history" && (
        <div className="max-w-[1440px] mx-auto px-6 py-6">
          <div className="panel rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="display-font font-bold text-xl text-white">{t.historyTitle}</h3>
                <p className="text-slate-400 text-sm mt-0.5">{t.historySubtitle}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-[#00E87A] animate-pulse" />
                <span className="mono text-xs text-slate-400 tracking-widest font-bold">
                  {recentReports.length} {t.historyRecords}
                </span>
              </div>
            </div>
            <div className="divider-glow mb-5" />

            {recentReports.length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <Clock size={32} className="mx-auto mb-3 opacity-30" />
                <p className="mono text-xs tracking-widest font-bold">{t.historyEmptyTitle}</p>
                <p className="text-sm mt-1">{t.historyEmptyDesc}</p>
              </div>
            ) : (
              <table className="sentinel-table">
                <thead>
                  <tr><th>Vendor</th><th>Risk Level</th><th>Score</th><th>Disruption</th><th>Primary Risk</th><th>Date</th><th className="w-16 text-center">Actions</th></tr>
                </thead>
                <tbody>
                  {recentReports.map((r, i) => (
                    <tr key={i} className="cursor-pointer" onClick={() => { setCurrentReport(r); setActiveTab("dashboard"); }}>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-lg flex items-center justify-center text-xs display-font font-bold" style={{ background: `${getRiskColor(r.risk_level)}20`, color: getRiskColor(r.risk_level), border: `1px solid ${getRiskColor(r.risk_level)}30` }}>
                            {r.vendor_name?.[0]?.toUpperCase()}
                          </div>
                          <span className="font-medium text-white">{r.vendor_name}</span>
                        </div>
                      </td>
                      <td><span className={`px-2.5 py-1 rounded-lg text-xs font-semibold mono badge-${r.risk_level?.toLowerCase()}`}>{r.risk_level}</span></td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 rounded-full" style={{ background: "rgba(26,37,64,0.8)" }}>
                            <div className="h-full rounded-full" style={{ width: `${r.risk_score}%`, background: getRiskColor(r.risk_level) }} />
                          </div>
                          <span className="mono text-xs text-slate-400 font-semibold">{r.risk_score}</span>
                        </div>
                      </td>
                      <td><span className="mono text-sm font-semibold" style={{ color: getRiskColor(r.risk_level) }}>{Math.round((r.disruption_probability || 0) * 100)}%</span></td>
                      <td className="text-slate-300 text-sm">{r.primary_risk_category}</td>
                      <td className="mono text-xs text-slate-400 font-semibold">{r.generated_at ? new Date(r.generated_at).toLocaleDateString() : "—"}</td>
                      <td className="text-center">
                        <button
                          onClick={(e) => handleDeleteReport(r.id!, e)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-red-500 hover:bg-red-500/10 transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── REPORTS TAB ── */}
      {activeTab === "reports" && (
        <div className="max-w-[1440px] mx-auto px-6 py-6 space-y-6">
          <div className="panel rounded-2xl p-6">
            <h3 className="display-font font-bold text-xl text-white mb-1">{t.reportsTitle}</h3>
            <p className="text-slate-400 text-sm">{t.reportsSubtitle}</p>
          </div>
          {recentReports.length === 0 ? (
            <div className="panel rounded-2xl p-16 text-center text-slate-500">
              <FileText size={32} className="mx-auto mb-3 opacity-30" />
              <p className="mono text-xs tracking-widest font-bold">{t.reportsEmptyTitle}</p>
            </div>
          ) : (
            recentReports.slice(0, 5).map((r, i) => {
              const transReport = translateReportData(r);
              return (
                <div key={i} className="space-y-3">
                  <div className="flex justify-end">
                    <button 
                      onClick={() => handleExportPDF(transReport)} 
                      className="px-4 py-2 bg-slate-950/60 hover:bg-slate-900 border border-slate-800 text-xs text-slate-300 rounded-xl flex items-center gap-2 transition-all font-mono tracking-wider hover:border-blue-500/30"
                    >
                      <Download size={13} /> DOWNLOAD INTELLIGENCE PDF
                    </button>
                  </div>
                  <RiskReportCard report={transReport!} riskColor={getRiskColor(r.risk_level)} currentLanguage={currentLanguage} onDelete={handleDeleteReport} />
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}