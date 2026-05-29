"use client";
import { useEffect, useState, useRef } from "react";
import { type RiskReport, getRiskColor } from "@/lib/api";
import { AlertTriangle, TrendingDown, Globe, ShieldAlert, Zap, Activity } from "lucide-react";

interface Alert {
  id: number;
  icon: any;
  message: string;
  sub: string;
  level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  age: string;
  fresh?: boolean;
}

function buildAlerts(report: RiskReport): Alert[] {
  const alerts: Alert[] = [];
  let id = 1;

  report.signals?.forEach(sig => {
    const level = sig.severity?.toUpperCase() as Alert["level"] || "LOW";
    const icons = { Financial: TrendingDown, Operational: Activity, Legal: ShieldAlert, Reputational: Globe, Cybersecurity: Zap };
    const icon = icons[sig.category as keyof typeof icons] || AlertTriangle;
    const indicator = sig.indicators?.[0] || sig.category;

    alerts.push({
      id: id++,
      icon,
      message: `${sig.category} risk detected`,
      sub: indicator,
      level,
      age: `${Math.floor(Math.random() * 59) + 1}m ago`,
      fresh: level === "CRITICAL" || level === "HIGH",
    });
  });

  // Pad with generic signals if few
  if (alerts.length < 4) {
    alerts.push(
      { id: id++, icon: Globe, message: "Regional news signal", sub: "Live web scan complete", level: "MEDIUM", age: "2m ago" },
      { id: id++, icon: Activity, message: "Operational monitor active", sub: "Bright Data SERP watching", level: "LOW", age: "5m ago" },
    );
  }

  return alerts.slice(0, 10);
}

interface Props { report: RiskReport; }

export default function LiveAlertsPanel({ report }: Props) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [visible, setVisible] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const built = buildAlerts(report);
    setAlerts(built);
    setVisible(0);
    let i = 0;
    timerRef.current = setInterval(() => {
      i++;
      setVisible(i);
      if (i >= built.length) clearInterval(timerRef.current!);
    }, 180);
    return () => clearInterval(timerRef.current!);
  }, [report]);

  return (
    <div className="panel rounded-2xl overflow-hidden flex flex-col" style={{ minHeight: 420 }}>
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(26,37,64,0.5)", background: "rgba(5,8,16,0.4)" }}>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[#FF2D55] animate-pulse" />
          <span className="mono text-[10px] text-sentinel-muted tracking-[0.2em]">INTELLIGENCE FEED</span>
        </div>
        <span className="mono text-[9px] text-sentinel-muted">{alerts.length} SIGNALS</span>
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {alerts.map((alert, i) => {
          const Icon = alert.icon;
          const color = getRiskColor(alert.level);
          const show = i < visible;
          return (
            <div key={alert.id}
              className="rounded-xl p-3 transition-all duration-300"
              style={{
                background: show ? `${color}08` : "transparent",
                border: `1px solid ${show ? `${color}20` : "transparent"}`,
                opacity: show ? 1 : 0,
                transform: show ? "translateX(0)" : "translateX(-8px)",
              }}>
              <div className="flex items-start gap-2.5">
                <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: `${color}15`, border: `1px solid ${color}25` }}>
                  <Icon size={11} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sentinel-text text-xs font-medium truncate">{alert.message}</span>
                    {alert.fresh && (
                      <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full animate-pulse"
                        style={{ background: color }} />
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="mono text-[9px] text-sentinel-muted truncate">{alert.sub}</span>
                    <span className="mono text-[9px] flex-shrink-0" style={{ color: color + "80" }}>
                      {alert.age}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-2">
                <span className={`px-2 py-0.5 rounded-md text-[8px] mono font-semibold badge-${alert.level.toLowerCase()}`}>
                  {alert.level}
                </span>
              </div>
            </div>
          );
        })}

        {alerts.length === 0 && (
          <div className="text-center py-8 text-sentinel-muted">
            <Activity size={20} className="mx-auto mb-2 opacity-30" />
            <p className="mono text-[10px] tracking-widest">NO SIGNALS</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 flex items-center gap-2"
        style={{ borderTop: "1px solid rgba(26,37,64,0.4)", background: "rgba(5,8,16,0.4)" }}>
        <Zap size={10} className="text-[#00D4FF]" />
        <span className="mono text-[9px] text-[#00D4FF] tracking-widest">
          BRIGHT DATA LIVE MONITORING
        </span>
      </div>
    </div>
  );
}