const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface InvestigationJob {
  job_id: string;
  vendor_name: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  stage: string;
  message: string;
  report: RiskReport | null;
  error: string | null;
  started_at: string;
}

export interface RiskSignal {
  category: string;
  severity: string;
  indicators: string[];
  weight: number;
}

export interface RiskReport {
  id?: number;
  vendor_name: string;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence_score: number;
  disruption_probability: number;
  executive_summary: string;
  risk_headline: string;
  primary_risk_category: string;
  key_findings: string[];
  risk_trajectory: string;
  recommended_actions: string[];
  monitoring_signals: string[];
  time_horizon: string;
  signals: RiskSignal[];
  sources: { url: string; title: string }[];
  raw_intelligence: Record<string, any>;
  status: string;
  generated_at: string;
}

export interface DashboardStats {
  total_investigations: number;
  risk_distribution: Record<string, number>;
  recent_critical: RiskReport[];
  average_risk_score: number;
}

// ─────────────────────────────────────────
// API Functions
// ─────────────────────────────────────────

export async function startInvestigation(vendorName: string): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vendor_name: vendorName }),
  });
  if (!res.ok) throw new Error(`Investigation failed: ${res.statusText}`);
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<InvestigationJob> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Job not found: ${jobId}`);
  return res.json();
}

export async function getRecentReports(): Promise<{ reports: RiskReport[]; count: number }> {
  const res = await fetch(`${API_BASE}/api/reports`);
  if (!res.ok) throw new Error("Failed to fetch reports");
  return res.json();
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await fetch(`${API_BASE}/api/dashboard/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export function createJobWebSocket(
  jobId: string,
  onProgress: (data: InvestigationJob) => void,
  onComplete: (data: InvestigationJob) => void,
  onError: (error: string) => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/jobs/${jobId}`);

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "progress" || msg.type === "status") {
      onProgress(msg.data);
    } else if (msg.type === "completed") {
      onComplete(msg.data);
    } else if (msg.type === "failed") {
      onError(msg.data?.error || "Investigation failed");
    }
  };

  ws.onerror = () => onError("WebSocket connection error");

  return ws;
}

export function getRiskColor(level: string): string {
  const colors: Record<string, string> = {
    CRITICAL: "#FF2D55",
    HIGH: "#FF6B00",
    MEDIUM: "#F5A623",
    LOW: "#00E87A",
  };
  return colors[level] || "#00E87A";
}

export function getRiskClass(level: string): string {
  const classes: Record<string, string> = {
    CRITICAL: "risk-critical badge-critical",
    HIGH: "risk-high badge-high",
    MEDIUM: "risk-medium badge-medium",
    LOW: "risk-low badge-low",
  };
  return classes[level] || "risk-low badge-low";
}