"use client";
import { useEffect, useState } from "react";

interface Props {
  score: number;
  level: string;
  color: string;
  size?: number;
}

export default function RiskScoreRing({ score, level, color, size = 140 }: Props) {
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(score), 100);
    return () => clearTimeout(timer);
  }, [score]);

  const radius = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (animated / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      {/* Outer glow ring */}
      <div
        className="absolute rounded-full"
        style={{
          inset: -4,
          background: `radial-gradient(circle, ${color}15 0%, transparent 70%)`,
          animation: "glowPulse 2s ease-in-out infinite",
        }}
      />

      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(26,37,64,0.6)"
          strokeWidth={8}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{
            transition: "stroke-dashoffset 1.5s cubic-bezier(0.34, 1.56, 0.64, 1)",
            filter: `drop-shadow(0 0 8px ${color}80)`,
          }}
        />
        {/* Inner track (decorative) */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius - 14}
          fill="none"
          stroke="rgba(26,37,64,0.3)"
          strokeWidth={1}
          strokeDasharray="3 6"
        />
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div
          className="display-font font-bold leading-none"
          style={{
            fontSize: size * 0.22,
            color: color,
            textShadow: `0 0 20px ${color}60`,
          }}
        >
          {score}
        </div>
        <div className="mono text-[9px] tracking-[0.15em] mt-1" style={{ color: color + "80" }}>
          / 100
        </div>
        <div
          className="mono text-[8px] tracking-[0.2em] mt-1.5 px-2 py-0.5 rounded-full"
          style={{
            background: color + "15",
            border: `1px solid ${color}30`,
            color: color,
          }}
        >
          {level}
        </div>
      </div>
    </div>
  );
}