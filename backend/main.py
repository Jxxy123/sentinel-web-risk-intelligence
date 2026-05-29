"""
Sentinel Web-Risk — FastAPI Backend
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.config import settings
from core.database import init_db, save_report, get_recent_reports, get_report_by_id, delete_report_by_id
from agents.orchestrator import SentinelOrchestrator


# ─────────────────────────────────────────────
# App Init
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    print("🛡️  Sentinel Web-Risk API started.")


# ─────────────────────────────────────────────
# In-memory job store
# ─────────────────────────────────────────────

active_jobs: Dict[str, Dict] = {}
job_connections: Dict[str, WebSocket] = {}


# ─────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────

class VendorInvestigationRequest(BaseModel):
    vendor_name: str
    job_id: Optional[str] = None
    language: str = "EN"  # 🌐 Added to capture the real-time frontend language matrix selector token


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "operational",
        "service": "Sentinel Web-Risk",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/investigate")
async def start_investigation(request: VendorInvestigationRequest, background_tasks: BackgroundTasks):
    """Start an autonomous vendor investigation."""
    import uuid

    job_id = request.job_id or str(uuid.uuid4())
    vendor_name = request.vendor_name.strip()
    language = request.language  # 🌐 Extracted tracking language configuration

    if not vendor_name:
        raise HTTPException(status_code=400, detail="vendor_name is required")

    active_jobs[job_id] = {
        "job_id": job_id,
        "vendor_name": vendor_name,
        "language": language,  # 🌐 Storing language parameter directly inside job metadata tracking logs
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "message": "Investigation queued...",
        "report": None,
        "error": None,
        "started_at": datetime.utcnow().isoformat(),
    }

    # 🚀 Passing language down to the asynchronous worker thread pipeline execution stack
    background_tasks.add_task(_run_investigation, job_id, vendor_name, language)

    return {"job_id": job_id, "status": "queued", "vendor_name": vendor_name}


async def _run_investigation(job_id: str, vendor_name: str, language: str):
    """Background task: run full investigation and update job state."""

    async def progress_callback(update: Dict):
        active_jobs[job_id].update({
            "status": "running",
            "stage": update["stage"],
            "message": update["message"],
            "progress": update["progress"],
        })
        # Push to WebSocket if connected
        ws = job_connections.get(job_id)
        if ws:
            try:
                await ws.send_text(json.dumps({
                    "type": "progress",
                    "data": active_jobs[job_id],
                }))
            except Exception:
                pass

    try:
        active_jobs[job_id]["status"] = "running"
        orchestrator = SentinelOrchestrator(progress_callback=progress_callback)
        
        # 🚀 FIX: Actively forward the language string variable to the multi-agent execution pipeline
        report = await orchestrator.investigate_vendor(vendor_name, language=language)

        report_id = save_report(report)
        report["id"] = report_id

        active_jobs[job_id].update({
            "status": "completed",
            "progress": 100,
            "stage": "complete",
            "message": "Investigation complete.",
            "report": report,
        })

        ws = job_connections.get(job_id)
        if ws:
            try:
                await ws.send_text(json.dumps({
                    "type": "completed",
                    "data": active_jobs[job_id],
                }))
            except Exception:
                pass

    except Exception as e:
        active_jobs[job_id].update({
            "status": "failed",
            "error": str(e),
            "message": f"Investigation failed: {e}",
        })
        print(f"[JOB ERROR] {job_id}: {e}")


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the current status of an investigation job."""
    job = active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/reports")
async def list_reports(limit: int = 20):
    """Get recent investigation reports."""
    reports = get_recent_reports(limit=limit)
    return {"reports": reports, "count": len(reports)}


@app.get("/api/reports/{report_id}")
async def get_report(report_id: int):
    """Get a specific report by ID."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: int):
    """🌐 NEW: HTTP DELETE handler that safely purges report keys out of SQLite database fields."""
    success = delete_report_by_id(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found or already deleted")
    return {"status": "success", "message": f"Report {report_id} deleted successfully."}


@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics."""
    reports = get_recent_reports(limit=100)
    level_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for r in reports:
        level = r.get("risk_level", "LOW")
        level_counts[level] = level_counts.get(level, 0) + 1

    return {
        "total_investigations": len(reports),
        "risk_distribution": level_counts,
        "recent_critical": [
            r for r in reports if r.get("risk_level") == "CRITICAL"
        ][:3],
        "average_risk_score": (
            sum(r.get("risk_score", 0) for r in reports) / len(reports)
            if reports else 0
        ),
    }


# ─────────────────────────────────────────────
# WebSocket for real-time progress
# ─────────────────────────────────────────────

@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time investigation progress."""
    await websocket.accept()
    job_connections[job_id] = websocket

    try:
        # Send current state immediately
        if job_id in active_jobs:
            await websocket.send_text(json.dumps({
                "type": "status",
                "data": active_jobs[job_id],
            }))

        # Keep alive and poll
        while True:
            await asyncio.sleep(1)
            job = active_jobs.get(job_id)
            if not job:
                break
            if job["status"] in ("completed", "failed"):
                await websocket.send_text(json.dumps({
                    "type": job["status"],
                    "data": job,
                }))
                break

    except WebSocketDisconnect:
        pass
    finally:
        job_connections.pop(job_id, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)