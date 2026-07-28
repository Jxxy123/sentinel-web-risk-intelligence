const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

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
  completed_at?: string | null;
  identity?: {
    status: "CONFIRMED";
    canonical_name: string;
    website_domain?: string | null;
    identity_confidence?: number;
  };
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
  sources: { url: string; title: string; source?: string }[];
  raw_intelligence: Record<string, unknown>;
  status: string;
  generated_at: string;
}

export interface DashboardStats {
  total_investigations: number;
  risk_distribution: Record<string, number>;
  recent_critical: RiskReport[];
  average_risk_score: number;
}

export type VendorResolutionStatus =
  | "CONFIRMED"
  | "SELECTION_REQUIRED"
  | "MORE_INFORMATION_REQUIRED";

export interface VendorCandidate {
  candidate_id: string;
  legal_name: string;
  aliases: string[];
  website: string | null;
  website_domain: string | null;
  country: string | null;
  city: string | null;
  industry: string | null;
  registration_number: string | null;
  parent_company: string | null;
  public_private_status: string | null;
  identity_confidence: number;
  confidence_label: string;
  evidence_source_count: number;
  source_quality_labels: string[];
  evidence_urls: string[];
  match_reasons: string[];
}

export interface InvestigationAuthorization {
  authorization_id: string;
  expires_at: string;
  single_use: true;
  required_for: "/api/investigate";
}

export interface VendorResolutionRequest {
  vendor_name: string;
  country?: string;
  city?: string;
  website?: string;
  industry?: string;
  language?: string;
}

export interface VendorResolutionResponse {
  resolution_status: VendorResolutionStatus;
  requested_name: string;
  selected_candidate: VendorCandidate | null;
  candidates: VendorCandidate[];
  requested_fields: string[];
  message: string;
  coverage_notice: string;
  identity_search: {
    search_performed: boolean;
    providers: string[];
    warnings: string[];
    candidate_evidence_records: number;
    accepted_result_count: number;
    directory_lead_count: number;
    rejected_result_count: number;
    assessment_type: string;
    llm_used: boolean;
    risk_scoring_started: boolean;
    database_writes: number;
  };
  investigation_authorization:
    | InvestigationAuthorization
    | null;
}

async function readApiError(
  response: Response,
  fallback: string,
): Promise<string> {
  const payload = await response
    .json()
    .catch(() => null) as
      | { detail?: unknown }
      | null;

  if (
    payload
    && typeof payload.detail === "string"
    && payload.detail.trim()
  ) {
    return payload.detail.trim();
  }

  return fallback;
}

export async function resolveVendorIdentity(
  request: VendorResolutionRequest,
): Promise<VendorResolutionResponse> {
  const response = await fetch(
    `${API_BASE}/api/vendors/resolve`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        vendor_name: request.vendor_name.trim(),
        country: request.country?.trim() || undefined,
        city: request.city?.trim() || undefined,
        website: request.website?.trim() || undefined,
        industry: request.industry?.trim() || undefined,
        language: request.language || "EN",
      }),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        "Vendor identity resolution failed.",
      ),
    );
  }

  return response.json();
}

export async function startInvestigation({
  vendor_name,
  identity_authorization_id,
  language = "EN",
}: {
  vendor_name: string;
  identity_authorization_id: string;
  language?: string;
}): Promise<{
  job_id: string;
  status: string;
  vendor_name: string;
}> {
  const response = await fetch(
    `${API_BASE}/api/investigate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        vendor_name: vendor_name.trim(),
        identity_authorization_id,
        language,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        "Authorized investigation failed to start.",
      ),
    );
  }

  return response.json();
}

export async function getJobStatus(
  jobId: string,
): Promise<InvestigationJob> {
  const response = await fetch(
    `${API_BASE}/api/jobs/${jobId}`,
  );

  if (!response.ok) {
    throw new Error(`Job not found: ${jobId}`);
  }

  return response.json();
}

export async function getRecentReports(): Promise<{
  reports: RiskReport[];
  count: number;
}> {
  const response = await fetch(
    `${API_BASE}/api/reports`,
  );

  if (!response.ok) {
    throw new Error("Failed to fetch reports");
  }

  return response.json();
}

export async function getDashboardStats(): Promise<
  DashboardStats
> {
  const response = await fetch(
    `${API_BASE}/api/dashboard/stats`,
  );

  if (!response.ok) {
    throw new Error("Failed to fetch stats");
  }

  return response.json();
}

export function createJobWebSocket(
  jobId: string,
  onProgress: (data: InvestigationJob) => void,
  onComplete: (data: InvestigationJob) => void,
  onError: (error: string) => void,
): WebSocket {
  const socket = new WebSocket(
    `${WS_BASE}/ws/jobs/${jobId}`,
  );

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (
      message.type === "progress"
      || message.type === "status"
    ) {
      onProgress(message.data);
    } else if (message.type === "completed") {
      onComplete(message.data);
    } else if (message.type === "failed") {
      onError(
        message.data?.error || "Investigation failed",
      );
    }
  };

  socket.onerror = () => {
    onError("WebSocket connection error");
  };

  return socket;
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
