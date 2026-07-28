"use client";

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
