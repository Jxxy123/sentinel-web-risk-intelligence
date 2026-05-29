import type { Metadata } from "next";
import "./globals.css";
import AnimatedBackground from "@/components/ui/AnimatedBackground";

export const metadata: Metadata = {
  title: "Sentinel Web-Risk | Autonomous Vendor Intelligence",
  description:
    "Predictive AI-powered third-party vendor risk intelligence platform using live web intelligence.",
  keywords: ["vendor risk", "supply chain", "AI agents", "Bright Data", "enterprise intelligence"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=JetBrains+Mono:wght@300;400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {/* Animated background layers */}
        <div className="sentinel-bg" />
        <div className="scan-overlay" />
        <div className="noise-overlay" />
        <AnimatedBackground />

        {/* Main content */}
        <div className="relative z-10">
          {children}
        </div>
      </body>
    </html>
  );
}