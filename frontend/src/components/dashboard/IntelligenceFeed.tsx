"use client";
import { Shield, Globe, Brain, Zap, Database, Lock } from "lucide-react";

const FEED_DICTIONARY: Record<string, { topLabel: string; title: string; desc: string; items: any[] }> = {
  EN: {
    topLabel: "SENTINEL CAPABILITIES",
    title: "What Becomes Possible With Bright Data",
    desc: "Traditional risk tools are blocked by CAPTCHAs, geo-restrictions, and stale data. Sentinel breaks through every barrier.",
    items: [
      { title: "Live Web Intelligence", description: "Bright Data SERP API scans thousands of sources in real time across all regions", icon: Globe, accent: "#0066FF" },
      { title: "Protected Source Access", description: "Scraping Browser + Web Unlocker bypasses CAPTCHAs and geo-restrictions", icon: Lock, accent: "#00D4FF" },
      { title: "6 Autonomous AI Agents", description: "Recon, Scraping, Verification, Intelligence, Prediction, and Reporting agents", icon: Brain, accent: "#7B61FF" },
      { title: "Zero-Trust Architecture", description: "Never relies on vendor self-reporting — independently verifies all data", icon: Shield, accent: "#00E87A" },
      { title: "Predictive Risk Scoring", description: "ML-powered signals across Financial, Operational, Legal, and Cyber dimensions", icon: Zap, accent: "#F5A623" },
      { title: "Multilingual Intelligence", description: "Processes regional news, foreign legal filings, and global data sources", icon: Database, accent: "#FF6B00" }
    ]
  },
  ZH: {
    topLabel: "SENTINEL 系统功能",
    title: "Bright Data 赋能的无限可能",
    desc: "传统风险评估工具极易受验证码、地理位置及过时数据限制。Sentinel 突破一切技术屏障。",
    items: [
      { title: "实时网络情报", description: "Bright Data SERP API 跨全球所有地区实时扫描数千个数据源", icon: Globe, accent: "#0066FF" },
      { title: "受保护源访问", description: "Scraping Browser + Web Unlocker 自动绕过验证码及地理位置限制", icon: Lock, accent: "#00D4FF" },
      { title: "6个自主AI代理", description: "侦察、抓取、验证、分析、预测和报告代理协调作业", icon: Brain, accent: "#7B61FF" },
      { title: "零信任安全架构", description: "从不依赖供应商的自我报告 — 独立验证所有底层数据", icon: Shield, accent: "#00E87A" },
      { title: "预测性风险评分", description: "基于机器学习的高级信号，涵盖财务、运营、法律和网络多维层面", icon: Zap, accent: "#F5A623" },
      { title: "多语言智能解析", description: "深度处理区域新闻、外国法律诉讼文件及全球化异构数据源", icon: Database, accent: "#FF6B00" }
    ]
  },
  AR: {
    topLabel: "قدرات نظام SENTINEL",
    title: "ما يصبح ممكنًا مع Bright Data",
    desc: "تتعطل أدوات المخاطر التقليدية بسبب تصفية الكابتشا، والقيود الجغرافية، والبيانات القديمة. Sentinel يخترق كل حاجز.",
    items: [
      { title: "استخبارات الويب الحية", description: "يمسح Bright Data SERP API آلاف المصادر في الوقت الفعلي عبر جميع المناطق", icon: Globe, accent: "#0066FF" },
      { title: "الوصول المحمي للمصادر", description: "يتجاوز متصفح الكشط وأداة فك الحظر الجغرافي رموز الكابتشا والقيود الجغرافية", icon: Lock, accent: "#00D4FF" },
      { title: "6 وكلاء ذكاء اصطناعي مستقلين", description: "وكلاء الاستطلاع، والكشط، والتحقق، والاستخبارات، والتنبؤ، وإعداد التقارير", icon: Brain, accent: "#7B61FF" },
      { title: "بنية الثقة الصفرية", description: "لا يعتمد أبدًا على التقارير الذاتية للبائعين — يتحقق بشكل مستقل من جميع البيانات", icon: Shield, accent: "#00E87A" },
      { title: "التسجيل التنبؤي للمخاطر", description: "إشارات مدعومة بالتعلم الآلي عبر الأبعاد المالية والتشغيلية والقانونية والسيبرانية", icon: Zap, accent: "#F5A623" },
      { title: "استخبارات متعددة اللغات", description: "يعالج الأخبار الإقليمية، والملفات القانونية الأجنبية، ومصادر البيانات العالمية", icon: Database, accent: "#FF6B00" }
    ]
  },
  BN: {
    topLabel: "SENTINEL সক্ষমতা",
    title: "ব্রাইট ডাটার মাধ্যমে যা কিছু সম্ভব",
    desc: "ঐতিহ্যবাহী ঝুঁকি সরঞ্জামগুলো ক্যাপচা, ভূ-নিষেধাজ্ঞা এবং বাসি ডাটা দ্বারা অবরুদ্ধ হয়। Sentinel প্রতিটি বাধা ভেঙে ফেলে।",
    items: [
      { title: "লাইভ ওয়েব ইন্টেলিজেন্স", description: "Bright Data SERP API সমস্ত অঞ্চল জুড়ে রিয়েল টাইমে হাজার হাজার উৎস স্ক্যান করে", icon: Globe, accent: "#0066FF" },
      { title: "সুরক্ষিত উৎস অ্যাক্সেস", description: "স্ক্র্যাপিং ব্রাউজার + ওয়েব আনলকার ক্যাপচা এবং ভূ-নিষেধাজ্ঞা বাইপাস করে", icon: Lock, accent: "#00D4FF" },
      { title: "৬টি স্বায়ত্তশাসিত এআই এজেন্ট", description: "রিকন, স্ক্র্যাপিং, ভেরিফিকেশন, ইন্টেলিজেন্স, প্রেডিকশন এবং রিপোর্টিং এজেন্ট", icon: Brain, accent: "#7B61FF" },
      { title: "জিরো-ট্রাস্ট আর্কিটেকচার", description: "কখনোই বিক্রেতার স্ব-প্রতিবেদনের ওপর নির্ভর করে না — স্বাধীনভাবে সব ডাটা যাচাই করে", icon: Shield, accent: "#00E87A" },
      { title: "ঝুঁকির পূর্বাভাস স্কোরিং", description: "আর্থিক, অপারেশনাল, আইনি এবং সাইবার মাত্রা জুড়ে এমএল-চালিত সংকেত", icon: Zap, accent: "#F5A623" },
      { title: "বহুভাষী বুদ্ধিমত্তা", description: "আঞ্চলিক সংবাদ, একটী বিদেশী আইনি ফাইলিং এবং বৈশ্বিক ডাটা উৎস প্রক্রিয়াকরণ করে", icon: Database, accent: "#FF6B00" }
    ]
  },
  DE: {
    topLabel: "SENTINEL FUNKTIONEN",
    title: "Was mit Bright Data möglich wird",
    desc: "Herkömmliche Risiko-Tools werden durch CAPTCHAs, Geo-Restriktionen und veraltete Daten blockiert. Sentinel durchbricht jede Barriere.",
    items: [
      { title: "Live-Web-Intelligenz", description: "Die Bright Data SERP API scannt Tausende von Quellen in Echtzeit über alle Regionen hinweg", icon: Globe, accent: "#0066FF" },
      { title: "Geschützter Quellzugriff", description: "Scraping Browser + Web Unlocker umgehen CAPTCHAs und geografische Einschränkungen", icon: Lock, accent: "#00D4FF" },
      { title: "6 autonome KI-Agenten", description: "Agenten für Aufklärung, Scraping, Verifizierung, Intelligenz, Vorhersage und Berichterstattung", icon: Brain, accent: "#7B61FF" },
      { title: "Zero-Trust-Architektur", description: "Verlässt sich niemals auf Selbsterklärungen von Anbietern — verifiziert alle Daten unabhängig", icon: Shield, accent: "#00E87A" },
      { title: "Prädiktive Risikobewertung", description: "ML-gestützte Signale über finanzielle, operationelle, rechtliche und Cyber-Dimensionen", icon: Zap, accent: "#F5A623" },
      { title: "Mehrsprachige Intelligenz", description: "Verarbeitet regionale Nachrichten, ausländische Gerichtsakten und globale Datenquellen", icon: Database, accent: "#FF6B00" }
    ]
  },
  JA: {
    topLabel: "SENTINEL 機能一覧",
    title: "Bright Data が可能にする新次元インテリジェンス",
    desc: "従来の評価ツールは、CAPTCHAや地理的制限、データの風化に阻まれていました。Sentinel はすべての障壁を破壊します。",
    items: [
      { title: "ライブウェブインテリジェンス", description: "Bright Data SERP API が全地域の数千ものソースをリアルタイムにスキャン", icon: Globe, accent: "#0066FF" },
      { title: "保護されたソースへのアクセス", description: "Scraping Browser + Web Unlocker が画像認証や地域制限を自動でバイパス", icon: Lock, accent: "#00D4FF" },
      { title: "6つの自律型AIエージェント", description: "偵察、スクレイピング、検証、インテリジェンス、予測、レポート作成エージェントが連携", icon: Brain, accent: "#7B61FF" },
      { title: "ゼロトラストアーキテクチャ", description: "ベンダーの自己申告には一切依存せず、すべてのデータを独立検証", icon: Shield, accent: "#00E87A" },
      { title: "予測型リスクスコアリング", description: "財務、運用、法務、サイバー空間を跨ぐ機械学習駆動のシグナル分析", icon: Zap, accent: "#F5A623" },
      { title: "多言語対応インテリジェンス", description: "地域ニュース、海外の法的文書、世界中のデータソースを自然言語処理", icon: Database, accent: "#FF6B00" }
    ]
  }
};

interface IntelligenceFeedProps {
  currentLanguage?: string;
}

export default function IntelligenceFeed({ currentLanguage = "EN" }: IntelligenceFeedProps) {
  const data = FEED_DICTIONARY[currentLanguage] || FEED_DICTIONARY.EN;

  return (
    <div className="space-y-6">
      <div className="text-center py-6 space-y-3">
        <div className="mono text-xs text-slate-400 tracking-[0.25em] font-semibold">
          {data.topLabel}
        </div>
        <h3 className="display-font font-bold text-2xl sm:text-3xl text-white">
          {data.title}
        </h3>
        <p className="text-slate-300 text-sm sm:text-base max-w-xl mx-auto leading-relaxed font-normal opacity-95">
          {data.desc}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.items.map((cap, i) => {
          const Icon = cap.icon;
          return (
            <div key={i}
              className="panel rounded-xl p-6 group hover:scale-[1.01] transition-transform duration-200"
              style={{
                border: `1px solid ${cap.accent}38`,
              }}>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{
                  background: `${cap.accent}12`,
                  border: `1px solid ${cap.accent}25`,
                }}>
                <Icon size={18} style={{ color: cap.accent }} />
              </div>
              <h4 className="display-font font-semibold text-white text-base mb-2">
                {cap.title}
              </h4>
              <p className="text-slate-300 text-sm leading-relaxed font-normal opacity-90">
                {cap.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}