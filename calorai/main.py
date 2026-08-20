"""FastAPI application — the calorai audit service.

Endpoints
---------
GET  /                  single-page audit UI
GET  /api/health        source mode + credit diagnostics
GET  /api/districts     district catalog
POST /api/audit         run a full district heat-budget audit
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from .agent import AuditAgent, AuditError, AuditRequest
from .data_source import DISTRICTS

app = FastAPI(
    title="calorai",
    description="Physics-first city heat-budget auditor (FortyGuard Hackathon'26, "
    "Agentic AI track). Every number traces to a physics equation and the "
    "FortyGuard Temperature API.",
    version="0.1.0",
)

_UI_PATH = Path(__file__).resolve().parent.parent / "ui" / "index.html"


class AuditBody(BaseModel):
    district: str = Field("phoenix", description="district key from /api/districts")
    date: str = Field("2026-08-18", description="YYYY-MM-DD within catalog coverage")
    hour: int = Field(14, ge=0, le=23, description="audit hour, local")
    threshold_c: float = Field(30.0, description="exceedance threshold °C")
    with_exceedance: bool = True
    narration: str = Field("auto", description="auto | template | github-models | none")
    source: str | None = Field(
        None,
        description="auto (default) | mock | live — live falls back to mock when keyless",
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _UI_PATH.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, Any]:
    from .data_source import resolve_source

    source, mode = resolve_source()
    usage: dict[str, Any] = {"mode": mode}
    if mode == "live":
        try:
            summary = source.client.fetch_api_key_usage()
            usage["credits"] = summary
        except Exception as exc:
            usage["credits_error"] = str(exc)
    return {"ok": True, "service": "calorai", "data_source": usage}


@app.get("/api/districts")
def districts() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "name": d.name,
            "lat": d.lat,
            "lon": d.lon,
            "base_mean_c": d.base_mean_c,
            "heat_island_c": d.heat_island_c,
        }
        for key, d in sorted(DISTRICTS.items())
    ]


@app.post("/api/audit")
def audit(body: AuditBody) -> dict[str, Any]:
    try:
        request = AuditRequest(
            district=body.district,
            date=body.date,
            hour=body.hour,
            threshold_c=body.threshold_c,
            with_exceedance=body.with_exceedance,
            data_source=body.source,
            narrator_kind=None if body.narration == "none" else body.narration,
        )
        agent = AuditAgent(request)
    except (AuditError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = agent.run(narrate=body.narration != "none")
    return report


@app.get("/api/report")
def report_pdf(
    district: str = Query("phoenix", description="district key from /api/districts"),
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    hour: int = Query(14, ge=0, le=23),
    threshold_c: float = Query(30.0),
    source: str | None = Query(None, description="auto | mock | live"),
) -> Response:
    """Render the audit as a PDF report (table of contents + charts)."""
    from .report import build_pdf_report

    try:
        request = AuditRequest(
            district=district,
            date=date,
            hour=hour,
            threshold_c=threshold_c,
            data_source=source,
            narrator_kind=None,
        )
        agent = AuditAgent(request)
    except (AuditError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = agent.run(narrate=False)
    path = build_pdf_report(report)
    filename = path.name
    return Response(
        content=path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export")
def export_package(
    district: str = Query("phoenix", description="district key from /api/districts"),
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    hour: int = Query(14, ge=0, le=23),
    threshold_c: float = Query(30.0),
    source: str | None = Query(None, description="auto | mock | live"),
) -> Response:
    """Forma-friendly interop package: tile GeoJSON + audit CSV + interventions CSV (ZIP)."""
    from .interop import export_zip_bytes

    try:
        request = AuditRequest(
            district=district,
            date=date,
            hour=hour,
            threshold_c=threshold_c,
            data_source=source,
            narrator_kind=None,
        )
        agent = AuditAgent(request)
    except (AuditError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = agent.run(narrate=False)
    snapshot = agent.fetch_snapshot()
    content = export_zip_bytes(report, snapshot, threshold_c)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=calorai_{report['district'].replace(' ', '-')}"
                f"_{report['date']}_interop.zip"
            )
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("calorai.main:app", host="127.0.0.1", port=8000, reload=True)