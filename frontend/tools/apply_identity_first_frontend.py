#!/usr/bin/env python3
'''Apply Sentinel's identity-first frontend investigation flow.

Scope:
- Extend frontend API types and functions for vendor resolution.
- Require the single-use identity authorization for /api/investigate.
- Add a compact inline identity-resolution panel.
- Preserve the existing visual design, Speechmatics flow, job progress,
  report rendering, and backend behavior.
'''

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
API_FILE = FRONTEND / "src" / "lib" / "api.ts"
PAGE_FILE = FRONTEND / "src" / "app" / "page.tsx"
PANEL_FILE = (
    FRONTEND
    / "src"
    / "components"
    / "dashboard"
    / "VendorIdentityPanel.tsx"
)

PATCH_VERSION = "2026-07-29-identity-first-frontend-v1"


API_CONTENT = r'''const API_BASE =
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
'''


PANEL_CONTENT = r'''"use client";

import {
  AlertTriangle,
  Building2,
  Globe2,
  MapPin,
  ShieldCheck,
  X,
} from "lucide-react";
import type {
  VendorCandidate,
  VendorResolutionResponse,
} from "@/lib/api";

export type VendorIdentityDetails = {
  website: string;
  country: string;
  city: string;
  industry: string;
};

type VendorIdentityPanelProps = {
  resolution: VendorResolutionResponse;
  details: VendorIdentityDetails;
  isResolving: boolean;
  onDetailsChange: (
    details: VendorIdentityDetails,
  ) => void;
  onRetry: () => void;
  onSelectCandidate: (
    candidate: VendorCandidate,
  ) => void;
  onDismiss: () => void;
};

function candidateLocation(
  candidate: VendorCandidate,
): string {
  return [
    candidate.city,
    candidate.country,
  ].filter(Boolean).join(", ");
}

export default function VendorIdentityPanel({
  resolution,
  details,
  isResolving,
  onDetailsChange,
  onRetry,
  onSelectCandidate,
  onDismiss,
}: VendorIdentityPanelProps) {
  if (resolution.resolution_status === "CONFIRMED") {
    return (
      <div
        className="mt-5 max-w-2xl mx-auto p-4 rounded-xl"
        style={{
          background: "rgba(0,232,122,0.08)",
          border: "1px solid rgba(0,232,122,0.24)",
        }}
      >
        <div className="flex items-start gap-3">
          <ShieldCheck
            size={17}
            className="text-[#00E87A] mt-0.5"
          />
          <div>
            <p className="text-sm font-semibold text-white">
              Identity confirmed
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Sentinel authenticated the target before
              starting the investigation.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const needsSelection =
    resolution.resolution_status
    === "SELECTION_REQUIRED";

  return (
    <div
      className="mt-5 max-w-2xl mx-auto p-5 rounded-xl"
      style={{
        background: "rgba(13,21,37,0.92)",
        border: "1px solid rgba(0,102,255,0.28)",
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <AlertTriangle
            size={17}
            className="text-amber-400 mt-0.5"
          />
          <div>
            <p className="text-sm font-semibold text-white">
              {needsSelection
                ? "Select the correct company"
                : "More identity context is required"}
            </p>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              {resolution.message}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onDismiss}
          className="text-slate-500 hover:text-white transition-colors"
          aria-label="Close identity resolution panel"
        >
          <X size={16} />
        </button>
      </div>

      {needsSelection && resolution.candidates.length > 0 && (
        <div className="mt-4 space-y-2">
          {resolution.candidates.map((candidate) => (
            <button
              type="button"
              key={candidate.candidate_id}
              disabled={isResolving}
              onClick={() => onSelectCandidate(candidate)}
              className="w-full p-3.5 rounded-xl text-left transition-all disabled:opacity-50"
              style={{
                background: "rgba(2,8,23,0.58)",
                border: "1px solid rgba(71,85,105,0.48)",
              }}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Building2
                      size={14}
                      className="text-blue-400"
                    />
                    <span className="text-sm font-semibold text-white">
                      {candidate.legal_name}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                    {candidate.website_domain && (
                      <span className="flex items-center gap-1">
                        <Globe2 size={12} />
                        {candidate.website_domain}
                      </span>
                    )}

                    {candidateLocation(candidate) && (
                      <span className="flex items-center gap-1">
                        <MapPin size={12} />
                        {candidateLocation(candidate)}
                      </span>
                    )}

                    {candidate.industry && (
                      <span>{candidate.industry}</span>
                    )}
                  </div>
                </div>

                <span className="mono text-[10px] text-[#00E87A]">
                  {Math.round(
                    candidate.identity_confidence * 100,
                  )}% MATCH
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <input
          type="url"
          value={details.website}
          onChange={(event) => {
            onDetailsChange({
              ...details,
              website: event.target.value,
            });
          }}
          placeholder="Official website (recommended)"
          className="search-input px-3.5 py-3 rounded-lg text-sm text-white placeholder-slate-500 bg-slate-950/50 border border-slate-800 focus:border-blue-500"
        />

        <input
          type="text"
          value={details.country}
          onChange={(event) => {
            onDetailsChange({
              ...details,
              country: event.target.value,
            });
          }}
          placeholder="Country"
          className="search-input px-3.5 py-3 rounded-lg text-sm text-white placeholder-slate-500 bg-slate-950/50 border border-slate-800 focus:border-blue-500"
        />

        <input
          type="text"
          value={details.city}
          onChange={(event) => {
            onDetailsChange({
              ...details,
              city: event.target.value,
            });
          }}
          placeholder="City"
          className="search-input px-3.5 py-3 rounded-lg text-sm text-white placeholder-slate-500 bg-slate-950/50 border border-slate-800 focus:border-blue-500"
        />

        <input
          type="text"
          value={details.industry}
          onChange={(event) => {
            onDetailsChange({
              ...details,
              industry: event.target.value,
            });
          }}
          placeholder="Industry"
          className="search-input px-3.5 py-3 rounded-lg text-sm text-white placeholder-slate-500 bg-slate-950/50 border border-slate-800 focus:border-blue-500"
        />
      </div>

      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="text-[11px] text-slate-500 leading-relaxed">
          Sentinel will not start risk scoring until one
          company identity is strongly confirmed.
        </p>

        <button
          type="button"
          disabled={isResolving}
          onClick={onRetry}
          className="btn-primary px-5 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-50 whitespace-nowrap"
        >
          {isResolving
            ? "Resolving..."
            : "Resolve & Continue"}
        </button>
      </div>

      {resolution.coverage_notice && (
        <p className="mt-3 text-[10px] text-slate-600">
          {resolution.coverage_notice}
        </p>
      )}
    </div>
  );
}
'''


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        content.rstrip() + "\n",
        encoding="utf-8",
    )


def patch_imports(text: str) -> str:
    old_api_import = '''import {
  startInvestigation, getJobStatus, getRecentReports, getDashboardStats,
  createJobWebSocket, getRiskColor,
  type RiskReport, type DashboardStats, type InvestigationJob,
} from "@/lib/api";'''

    new_api_import = '''import {
  resolveVendorIdentity,
  startInvestigation,
  getJobStatus,
  getRecentReports,
  getDashboardStats,
  createJobWebSocket,
  getRiskColor,
  type RiskReport,
  type DashboardStats,
  type InvestigationJob,
  type VendorCandidate,
  type VendorResolutionResponse,
} from "@/lib/api";'''

    require(
        old_api_import in text
        or new_api_import in text,
        "Could not find the frontend API import block.",
    )
    text = text.replace(
        old_api_import,
        new_api_import,
        1,
    )

    panel_import = '''import VendorIdentityPanel, {
  type VendorIdentityDetails,
} from "@/components/dashboard/VendorIdentityPanel";
'''

    governance_anchor = (
        'import GovernancePanel from '
        '"@/components/dashboard/GovernancePanel";\n'
    )

    if panel_import not in text:
        require(
            governance_anchor in text,
            "Could not find GovernancePanel import anchor.",
        )
        text = text.replace(
            governance_anchor,
            governance_anchor + panel_import,
            1,
        )

    return text


def patch_state(text: str) -> str:
    state_anchor = (
        '  const [error, setError] = useState<string | null>(null);\n'
    )
    state_block = r'''  const [identityResolution, setIdentityResolution] =
    useState<VendorResolutionResponse | null>(null);
  const [identityDetails, setIdentityDetails] =
    useState<VendorIdentityDetails>({
      website: "",
      country: "",
      city: "",
      industry: "",
    });
  const [isResolvingIdentity, setIsResolvingIdentity] =
    useState(false);
'''

    if "const [identityResolution" not in text:
        require(
            state_anchor in text,
            "Could not find state insertion anchor.",
        )
        text = text.replace(
            state_anchor,
            state_anchor + state_block,
            1,
        )

    speech_old = '''      if (cleanedInput) {
        setVendorInput(cleanedInput);
      }'''
    speech_new = '''      if (cleanedInput) {
        setVendorInput(cleanedInput);
        setIdentityResolution(null);
      }'''

    require(
        speech_old in text
        or speech_new in text,
        "Could not find Speechmatics final-transcript handler.",
    )
    text = text.replace(
        speech_old,
        speech_new,
        1,
    )

    return text


def patch_investigation_flow(text: str) -> str:
    pattern = re.compile(
        r'''  const handleInvestigate = async \(vendor\?: string\) => \{
.*?
  \};

  const startPolling = \(''',
        re.DOTALL,
    )

    replacement = r'''  const launchAuthorizedInvestigation = async ({
    vendorName,
    authorizationId,
  }: {
    vendorName: string;
    authorizationId: string;
  }) => {
    const { job_id } = await startInvestigation({
      vendor_name: vendorName,
      identity_authorization_id: authorizationId,
      language: currentLanguage,
    });

    setCurrentJob({
      job_id,
      vendor_name: vendorName,
      status: "queued",
      progress: 0,
      stage: "queued",
      message: "Confirmed identity — investigation queued...",
      report: null,
      error: null,
      started_at: new Date().toISOString(),
    });

    const onProgress = (data: InvestigationJob) => {
      setCurrentJob(data);
      setSerpCalls((previous) =>
        Math.min(
          previous + Math.floor(Math.random() * 2),
          10,
        ),
      );
      setLlmCost((previous) =>
        parseFloat(
          (
            previous
            + 0.08
            + Math.random() * 0.12
          ).toFixed(2),
        ),
      );
    };

    const onComplete = (data: InvestigationJob) => {
      setCurrentJob(data);
      setCurrentReport(data.report);
      setIsLoading(false);
      setIdentityResolution(null);
      loadDashboardData();
    };

    const onError = (message: string) => {
      setError(message);
      setIsLoading(false);
    };

    try {
      wsRef.current?.close();
      wsRef.current = createJobWebSocket(
        job_id,
        onProgress,
        onComplete,
        onError,
      );
    } catch {
      startPolling(
        job_id,
        onProgress,
        onComplete,
        onError,
      );
    }
  };

  const handleInvestigate = async (
    vendor?: string,
    context?: Partial<VendorIdentityDetails>,
  ) => {
    const name = (vendor || vendorInput).trim();

    if (!name) {
      return;
    }

    const details = {
      ...identityDetails,
      ...context,
    };

    setIsLoading(true);
    setIsResolvingIdentity(true);
    setError(null);
    setCurrentReport(null);
    setCurrentJob(null);
    setSerpCalls(0);
    setLlmCost(0);

    try {
      const resolution = await resolveVendorIdentity({
        vendor_name: name,
        website: details.website,
        country: details.country,
        city: details.city,
        industry: details.industry,
        language: currentLanguage,
      });

      setIdentityResolution(resolution);

      if (
        resolution.resolution_status !== "CONFIRMED"
        || !resolution.selected_candidate
        || !resolution.investigation_authorization
      ) {
        setIsLoading(false);
        return;
      }

      const canonicalName =
        resolution.selected_candidate.legal_name;
      setVendorInput(canonicalName);

      await launchAuthorizedInvestigation({
        vendorName: canonicalName,
        authorizationId:
          resolution.investigation_authorization
            .authorization_id,
      });
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to start the identity-first investigation.",
      );
      setIsLoading(false);
    } finally {
      setIsResolvingIdentity(false);
    }
  };

  const handleCandidateSelection = (
    candidate: VendorCandidate,
  ) => {
    const candidateDetails: VendorIdentityDetails = {
      website: candidate.website || "",
      country: candidate.country || "",
      city: candidate.city || "",
      industry: candidate.industry || "",
    };

    setVendorInput(candidate.legal_name);
    setIdentityDetails(candidateDetails);

    void handleInvestigate(
      candidate.legal_name,
      candidateDetails,
    );
  };

  const startPolling = ('''

    if "const launchAuthorizedInvestigation" in text:
        return text

    text, count = pattern.subn(
        replacement,
        text,
        count=1,
    )
    require(
        count == 1,
        "Could not replace the legacy investigation function.",
    )

    return text


def patch_input_and_panel(text: str) -> str:
    old_input = '''<input type="text" value={isListening && partialTranscript ? partialTranscript : vendorInput} onChange={e => setVendorInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleInvestigate()}'''
    new_input = '''<input
                    type="text"
                    value={
                      isListening && partialTranscript
                        ? partialTranscript
                        : vendorInput
                    }
                    onChange={(event) => {
                      setVendorInput(event.target.value);
                      setIdentityResolution(null);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        void handleInvestigate();
                      }
                    }}'''

    require(
        old_input in text
        or new_input in text,
        "Could not find the main vendor input.",
    )
    text = text.replace(
        old_input,
        new_input,
        1,
    )

    text = text.replace(
        '<button onClick={() => handleInvestigate()} disabled={isLoading || !vendorInput.trim()}',
        '<button onClick={() => void handleInvestigate()} disabled={isLoading || !vendorInput.trim()}',
        1,
    )

    text = text.replace(
        'onClick={() => { setVendorInput(v); handleInvestigate(v); }}',
        'onClick={() => { setVendorInput(v); setIdentityResolution(null); void handleInvestigate(v); }}',
        1,
    )

    panel_anchor = '''              {error && (
                <div className="mt-5 max-w-2xl mx-auto p-3.5 rounded-xl flex items-center gap-2.5"'''

    panel_block = '''              {identityResolution && (
                <VendorIdentityPanel
                  resolution={identityResolution}
                  details={identityDetails}
                  isResolving={isResolvingIdentity}
                  onDetailsChange={setIdentityDetails}
                  onRetry={() => {
                    void handleInvestigate();
                  }}
                  onSelectCandidate={
                    handleCandidateSelection
                  }
                  onDismiss={() => {
                    setIdentityResolution(null);
                    setIsLoading(false);
                  }}
                />
              )}

'''

    if "<VendorIdentityPanel" not in text:
        require(
            panel_anchor in text,
            "Could not find the identity panel insertion anchor.",
        )
        text = text.replace(
            panel_anchor,
            panel_block + panel_anchor,
            1,
        )

    return text


def verify(page_text: str) -> None:
    api_text = API_FILE.read_text(encoding="utf-8")
    panel_text = PANEL_FILE.read_text(encoding="utf-8")

    checks = {
        "resolve endpoint connected": (
            "/api/vendors/resolve" in api_text
        ),
        "authorization included": (
            "identity_authorization_id" in api_text
        ),
        "name-only body removed": (
            "JSON.stringify({ vendor_name: vendor_name.trim(), language })"
            not in api_text
        ),
        "frontend resolves before launch": (
            "resolveVendorIdentity({" in page_text
            and "launchAuthorizedInvestigation({" in page_text
        ),
        "selection state handled": (
            "SELECTION_REQUIRED" in panel_text
        ),
        "more-info state handled": (
            "MORE_INFORMATION_REQUIRED" in API_CONTENT
            and "Resolve & Continue" in panel_text
        ),
        "speech remains review-first": (
            "handleInvestigate(cleanedInput)" not in page_text
        ),
        "authorization not persisted": (
            "localStorage" not in page_text
            and "sessionStorage" not in page_text
        ),
    }

    failed = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    for name, passed in checks.items():
        print(
            f"{'PASS' if passed else 'FAIL'}: {name}"
        )

    require(
        not failed,
        "Focused identity-first checks failed: "
        + ", ".join(failed),
    )


def main() -> None:
    require(
        PAGE_FILE.exists(),
        f"Missing page: {PAGE_FILE}",
    )

    page_text = PAGE_FILE.read_text(encoding="utf-8")
    page_text = patch_imports(page_text)
    page_text = patch_state(page_text)
    page_text = patch_investigation_flow(page_text)
    page_text = patch_input_and_panel(page_text)

    write_text(API_FILE, API_CONTENT)
    write_text(PANEL_FILE, PANEL_CONTENT)
    write_text(PAGE_FILE, page_text)

    verify(page_text)

    print(
        "Identity-first frontend applied successfully. "
        f"version={PATCH_VERSION}"
    )


if __name__ == "__main__":
    main()
