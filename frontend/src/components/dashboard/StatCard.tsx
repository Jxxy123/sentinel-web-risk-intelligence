"use client";
import { ReactNode } from "react";
import { TrendingUp } from "lucide-react";

interface Props {
  label: string;
  value: string;
  icon: ReactNode;
  trend?: string;
  valueColor?: string;
}

export default function StatCard({ label, value, icon, trend, valueColor }: Props) {
  return (
    <div className="panel rounded-xl p-5 relative overflow-hidden group hover:border-[#0066FF]/20
      transition-colors cursor-default">
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ background: "radial-gradient(ellipse at top right, rgba(0,102,255,0.04), transparent 70%)" }} />

      <div className="flex items-start justify-between mb-3">
        <div className="p-2 rounded-lg"
          style={{ background: "rgba(0,102,255,0.1)", border: "1px solid rgba(0,102,255,0.15)" }}>
          <div className="text-[#0066FF]">{icon}</div>
        </div>
        {trend && (
          <div className="flex items-center gap-1 text-[#00E87A]">
            <TrendingUp size={10} />
            <span className="mono text-[9px]">{trend}</span>
          </div>
        )}
      </div>

      <div
        className="display-font font-bold text-2xl mb-1"
        style={{ color: valueColor || "#E8EDF8" }}
      >
        {value}
      </div>
      <div className="mono text-[10px] text-sentinel-muted tracking-widest">{label.toUpperCase()}</div>
    </div>
  );
}