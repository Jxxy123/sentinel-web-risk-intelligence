/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
      "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
      "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
      extend: {
        fontFamily: {
          display: ["'Syne'", "sans-serif"],
          mono: ["'JetBrains Mono'", "monospace"],
          body: ["'DM Sans'", "sans-serif"],
        },
        colors: {
          sentinel: {
            bg: "#050810",
            surface: "#080D1A",
            panel: "#0D1525",
            border: "#1A2540",
            accent: "#0066FF",
            "accent-glow": "#0044CC",
            critical: "#FF2D55",
            high: "#FF6B00",
            medium: "#F5A623",
            low: "#00E87A",
            text: "#E8EDF8",
            muted: "#5C6A88",
            cyan: "#00D4FF",
          },
        },
        animation: {
          "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
          "scan-line": "scanLine 3s linear infinite",
          "glow-pulse": "glowPulse 2s ease-in-out infinite",
          "float": "float 6s ease-in-out infinite",
          "data-stream": "dataStream 8s linear infinite",
          "radar": "radar 4s linear infinite",
        },
        keyframes: {
          scanLine: {
            "0%": { transform: "translateY(-100%)", opacity: 0 },
            "10%": { opacity: 1 },
            "90%": { opacity: 1 },
            "100%": { transform: "translateY(2000%)", opacity: 0 },
          },
          glowPulse: {
            "0%, 100%": { boxShadow: "0 0 20px rgba(0, 102, 255, 0.3)" },
            "50%": { boxShadow: "0 0 40px rgba(0, 102, 255, 0.7)" },
          },
          float: {
            "0%, 100%": { transform: "translateY(0px)" },
            "50%": { transform: "translateY(-10px)" },
          },
          dataStream: {
            "0%": { backgroundPosition: "0 0" },
            "100%": { backgroundPosition: "0 -200px" },
          },
          radar: {
            "0%": { transform: "rotate(0deg)" },
            "100%": { transform: "rotate(360deg)" },
          },
        },
        backgroundImage: {
          "grid-pattern":
            "linear-gradient(rgba(0,102,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0,102,255,0.05) 1px, transparent 1px)",
          "noise":
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E\")",
        },
        backgroundSize: {
          "grid": "40px 40px",
        },
      },
    },
    plugins: [],
  };