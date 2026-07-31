"""
Sentinel Web-Risk — FastAPI Backend.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.orchestrator import SentinelOrchestrator
from core.config import settings
from core.investigation_authorization import (
    InvestigationAuthorizationError,
    consume_investigation_authorization,
)
from core.database import (
    delete_report_by_id,
    get_recent_reports,
    get_report_by_id,
    init_db,
    save_report,
)
from core.vendor_resolution_api import router as vendor_resolution_router


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sentinel Web-Risk API",
    description="Autonomous Predictive Vendor Risk Intelligence Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adds POST /api/vendors/resolve without changing /api/investigate or the UI.
app.include_router(vendor_resolution_router)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    """Initialize backend services when the API starts."""
    init_db()
    print("🛡️  Sentinel Web-Risk API started.")


# ---------------------------------------------------------------------------
# In-memory job state
# ---------------------------------------------------------------------------

active_jobs: dict[str, dict[str, Any]] = {}
job_connections: dict[str, WebSocket] = {}


def _utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


async def _send_job_event(
    job_id: str,
    event_type: str,
) -> None:
    """Send the current job state when a WebSocket client is connected."""
    websocket = job_connections.get(job_id)

    if websocket is None:
        return

    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": event_type,
                    "data": active_jobs.get(job_id, {}),
                },
                default=str,
            )
        )
    except Exception:
        # A disconnected browser must not stop the investigation.
        job_connections.pop(job_id, None)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class VendorInvestigationRequest(BaseModel):
    """Request body for a confirmed vendor investigation."""

    vendor_name: str
    identity_authorization_id: str | None = None
    job_id: str | None = None
    language: str = "EN"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    """Return API health information."""
    return {
        "status": "operational",
        "service": "Sentinel Web-Risk",
        "version": "1.0.0",
        "timestamp": _utc_now_iso(),
    }


# ---------------------------------------------------------------------------
# Investigation jobs
# ---------------------------------------------------------------------------

@app.post("/api/investigate")
async def start_investigation(
    request: VendorInvestigationRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Start an autonomous vendor investigation.

    A short-lived authorization from POST /api/vendors/resolve is
    required. Unconfirmed, expired, mismatched, or replayed identity
    authorizations cannot create investigation jobs.
    """
    vendor_name = " ".join(
        request.vendor_name.split()
    ).strip()

    if not vendor_name:
        raise HTTPException(
            status_code=400,
            detail="vendor_name is required",
        )

    language = (
        " ".join(
            request.language.split()
        ).strip()
        or "EN"
    ).upper()

    job_id = (
        request.job_id.strip()
        if request.job_id
        and request.job_id.strip()
        else str(uuid.uuid4())
    )

    if job_id in active_jobs:
        raise HTTPException(
            status_code=409,
            detail="job_id already exists",
        )

    try:
        confirmed_identity = (
            consume_investigation_authorization(
                request.identity_authorization_id,
                requested_vendor_name=request.vendor_name,
            )
        )
    except InvestigationAuthorizationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error

    vendor_name = confirmed_identity["canonical_name"]

    active_jobs[job_id] = {
        "job_id": job_id,
        "vendor_name": vendor_name,
        "language": language,
        "identity": confirmed_identity,
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "message": "Investigation queued...",
        "report": None,
        "error": None,
        "started_at": _utc_now_iso(),
        "completed_at": None,
    }

    background_tasks.add_task(
        _run_investigation,
        job_id,
        vendor_name,
        language,
        confirmed_identity,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "vendor_name": vendor_name,
    }


async def _run_investigation(
    job_id: str,
    vendor_name: str,
    language: str,
    identity_context: dict[str, Any],
) -> None:
    """Run one investigation and keep its job state synchronized."""

    async def progress_callback(
        update: dict[str, Any],
    ) -> None:
        job = active_jobs.get(job_id)

        if job is None:
            return

        job.update(
            {
                "status": "running",
                "stage": update.get(
                    "stage",
                    "running",
                ),
                "message": update.get(
                    "message",
                    "Investigation running...",
                ),
                "progress": update.get(
                    "progress",
                    job.get(
                        "progress",
                        0,
                    ),
                ),
            }
        )

        await _send_job_event(
            job_id,
            "progress",
        )

    try:
        job = active_jobs.get(job_id)

        if job is None:
            return

        job.update(
            {
                "status": "running",
                "stage": "starting",
                "message": "Starting vendor investigation...",
            }
        )

        orchestrator = SentinelOrchestrator(
            progress_callback=progress_callback
        )

        report = await orchestrator.investigate_confirmed_vendor(
            identity_context,
            language=language,
        )

        report_id = save_report(report)
        report["id"] = report_id

        job.update(
            {
                "status": "completed",
                "progress": 100,
                "stage": "complete",
                "message": "Investigation complete.",
                "report": report,
                "error": None,
                "completed_at": _utc_now_iso(),
            }
        )

        await _send_job_event(
            job_id,
            "completed",
        )

    except Exception as error:
        job = active_jobs.get(job_id)

        if job is not None:
            job.update(
                {
                    "status": "failed",
                    "stage": "failed",
                    "message": "Investigation failed.",
                    "error": str(error),
                    "completed_at": _utc_now_iso(),
                }
            )

        print(
            f"[JOB ERROR] {job_id}: "
            f"{type(error).__name__}: {error}"
        )

        await _send_job_event(
            job_id,
            "failed",
        )


@app.get("/api/jobs/{job_id}")
async def get_job_status(
    job_id: str,
) -> dict[str, Any]:
    """Return the current state of an investigation job."""
    job = active_jobs.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.get("/api/reports")
async def list_reports(
    limit: int = 20,
) -> dict[str, Any]:
    """Return recent investigation reports."""
    safe_limit = max(
        1,
        min(
            limit,
            100,
        ),
    )

    reports = get_recent_reports(
        limit=safe_limit
    )

    return {
        "reports": reports,
        "count": len(reports),
    }


@app.get("/api/reports/{report_id}")
async def get_report(
    report_id: int,
) -> dict[str, Any]:
    """Return one saved investigation report."""
    report = get_report_by_id(report_id)

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    return report


@app.delete("/api/reports/{report_id}")
async def delete_report(
    report_id: int,
) -> dict[str, str]:
    """Delete one saved report."""
    success = delete_report_by_id(report_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Report not found or already deleted",
        )

    return {
        "status": "success",
        "message": f"Report {report_id} deleted successfully.",
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard/stats")
async def get_dashboard_stats() -> dict[str, Any]:
    """
    Return dashboard statistics.

    Reports without a defensible numeric score are excluded from the average
    and are not falsely counted as LOW risk.
    """
    reports = get_recent_reports(
        limit=100
    )

    valid_levels = {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }

    level_counts = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    }

    scored_values: list[float] = []

    for report in reports:
        level = report.get("risk_level")

        if level in valid_levels:
            level_counts[level] += 1

        score = report.get("risk_score")

        if (
            isinstance(
                score,
                (int, float),
            )
            and not isinstance(
                score,
                bool,
            )
        ):
            scored_values.append(
                float(score)
            )

    average_risk_score = (
        sum(scored_values)
        / len(scored_values)
        if scored_values
        else 0
    )

    return {
        "total_investigations": len(reports),
        "risk_distribution": level_counts,
        "recent_critical": [
            report
            for report in reports
            if report.get("risk_level") == "CRITICAL"
        ][:3],
        "average_risk_score": average_risk_score,
    }


# ---------------------------------------------------------------------------
# WebSocket progress
# ---------------------------------------------------------------------------

@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(
    websocket: WebSocket,
    job_id: str,
) -> None:
    """Stream real-time investigation progress for one job."""
    await websocket.accept()
    job_connections[job_id] = websocket

    try:
        if job_id in active_jobs:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "status",
                        "data": active_jobs[job_id],
                    },
                    default=str,
                )
            )

        while True:
            await asyncio.sleep(1)
            job = active_jobs.get(job_id)

            if job is None:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "failed",
                            "data": {
                                "job_id": job_id,
                                "status": "failed",
                                "error": "Job not found",
                            },
                        }
                    )
                )
                break

            if job.get("status") in {
                "completed",
                "failed",
            }:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": job["status"],
                            "data": job,
                        },
                        default=str,
                    )
                )
                break

    except WebSocketDisconnect:
        pass

    finally:
        job_connections.pop(
            job_id,
            None,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
