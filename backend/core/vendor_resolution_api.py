"""FastAPI contract for pre-investigation vendor identity resolution.

The router is isolated from the investigation endpoint. It never creates jobs,
runs CrewAI, writes reports, or starts vendor-risk scoring.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.live_vendor_identity import (
    IdentityEvidenceBatch,
    collect_live_vendor_identity_evidence,
)
from core.vendor_resolution import (
    resolve_vendor_candidates,
)


router = APIRouter(
    prefix="/api/vendors",
    tags=["Vendor Identity"],
)


class VendorResolutionRequest(BaseModel):
    """User-supplied identity context used before investigation."""

    vendor_name: str = Field(
        min_length=1,
        max_length=200,
    )
    country: str | None = Field(
        default=None,
        max_length=120,
    )
    city: str | None = Field(
        default=None,
        max_length=120,
    )
    website: str | None = Field(
        default=None,
        max_length=500,
    )
    industry: str | None = Field(
        default=None,
        max_length=160,
    )
    language: str = Field(
        default="EN",
        max_length=20,
    )


IdentityEvidenceCollector = Callable[
    [VendorResolutionRequest],
    Awaitable[IdentityEvidenceBatch],
]


identity_evidence_collector: IdentityEvidenceCollector = (
    collect_live_vendor_identity_evidence
)


def _clean_optional(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = " ".join(
        value.split()
    ).strip()

    return cleaned or None


@router.post("/resolve")
async def resolve_vendor_identity(
    request: VendorResolutionRequest,
) -> dict:
    """
    Resolve a vendor name before investigation.

    Response states:
    - CONFIRMED
    - SELECTION_REQUIRED
    - MORE_INFORMATION_REQUIRED

    No investigation job is created by this endpoint.
    """
    vendor_name = " ".join(
        request.vendor_name.split()
    ).strip()

    if not vendor_name:
        raise HTTPException(
            status_code=400,
            detail="vendor_name is required",
        )

    normalized_request = request.model_copy(
        update={
            "vendor_name": vendor_name,
            "country": _clean_optional(
                request.country
            ),
            "city": _clean_optional(
                request.city
            ),
            "website": _clean_optional(
                request.website
            ),
            "industry": _clean_optional(
                request.industry
            ),
            "language": (
                _clean_optional(
                    request.language
                )
                or "EN"
            ).upper(),
        }
    )

    try:
        evidence_batch = await identity_evidence_collector(
            normalized_request
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Vendor identity search is temporarily unavailable."
            ),
        ) from error

    result = resolve_vendor_candidates(
        normalized_request.vendor_name,
        evidence_batch.records,
        country=normalized_request.country,
        city=normalized_request.city,
        website=normalized_request.website,
        industry=normalized_request.industry,
    )

    payload = result.to_dict()
    payload["identity_search"] = {
        "search_performed": (
            evidence_batch.search_performed
        ),
        "providers": list(
            evidence_batch.providers
        ),
        "warnings": list(
            evidence_batch.warnings
        ),
        "candidate_evidence_records": len(
            evidence_batch.records
        ),
        "queries_executed": list(
            evidence_batch.queries_executed
        ),
        "started_at": (
            evidence_batch.started_at
        ),
        "completed_at": (
            evidence_batch.completed_at
        ),
        "assessment_type": (
            "pre_investigation_identity_resolution"
        ),
        "llm_used": False,
        "risk_scoring_started": False,
        "database_writes": 0,
    }

    return payload
