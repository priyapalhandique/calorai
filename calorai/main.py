"""FastAPI application — the calorai audit service.

Endpoints
---------
GET  /                  single-page audit UI
GET  /api/health        source mode + credit diagnostics
GET  /api/districts     district catalog
POST /api/audit         run a full district heat-budget audit
POST /api/ask           agentic natural-language query (D7)
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
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
app.mount("/ui", StaticFiles(directory=_UI_PATH.parent), name="ui")


class AuditBody(BaseModel):
    district: str = Field("phoenix", description="district key from /api/districts")
    date: str = Field("2026-08-18", description="YYYY-MM-DD within catalog coverage")
    hour: int = Field(14, ge=0, le=23, description="audit hour, local")
    threshold_c: float = Field(30.0, description="exceedance threshold °C")
    with_exceedance: bool = Field(
        False,
        description="include exceedance/persistence layers (plan-limited on live; "
        "costs heatmap credits even when unavailable)",
    )
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
    """
    Return the list of districts with their details.
    """
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


@app.get("/api/google-config")
def google_config() -> dict[str, Any]:
    """Return the browser-safe Google Maps configuration for the 3D preview."""
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    return {"enabled": bool(key), "api_key": key}


class AskBody(BaseModel):
    query: str = Field(..., min_length=3, description="natural-language request")
    district: str | None = Field(None, description="default district if the query names none")
    date: str | None = Field(None, description="default date if the query names none")
    hour: int | None = Field(None, ge=0, le=23, description="default audit hour")
    threshold_c: float | None = Field(None, description="exceedance threshold °C")
    source: str | None = Field(None, description="auto | mock | live")
    profile: dict[str, Any] | None = Field(
        None,
        description="demo persona: units c|f, intensity, threshold_c, home_district, voice",
    )


@app.post("/api/ask")
def ask(body: AskBody) -> dict[str, Any]:
    """Agentic endpoint (D7): plan -> tools -> trace -> answer + spoken tldr."""
    from .personal import UserProfile
    from .planner import plan_and_run
    from .tools import AgentContext

    ctx = AgentContext(
        district=body.district or "phoenix",
        date=body.date or "2026-08-18",
        hour=body.hour if body.hour is not None else 14,
        threshold_c=body.threshold_c if body.threshold_c is not None else 30.0,
        source=body.source,
    )
    return plan_and_run(body.query, ctx, profile=UserProfile.from_dict(body.profile))


@app.get("/api/uhi")
def uhi(
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    threshold_c: float = Query(30.0),
    source: str | None = Query(None, description="auto | mock | live"),
) -> dict[str, Any]:
    """UHI prevalence ranking — where is the island strongest and why."""
    from .analyst.uhi import rank_districts
    from .data_source import DISTRICTS

    reports: list[dict[str, Any]] = []
    for key in sorted(DISTRICTS):
        try:
            req = AuditRequest(district=key, date=date, hour=14, threshold_c=threshold_c, data_source=source, narrator_kind=None)
            reports.append(AuditAgent(req).run(narrate=False))
        except Exception as exc:
            reports.append({"district": key, "error": str(exc)})
    ranked = rank_districts([r for r in reports if "uhi" in r])
    return {"date": date, "threshold_c": threshold_c, "ranked": ranked, "n_districts": len(ranked)}


@app.get("/api/time_machine")
def time_machine(
    district: str = Query("phoenix", description="district key"),
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    source: str | None = Query(None, description="auto | mock | live"),
) -> dict[str, Any]:
    """Heat Time-Machine — past / present / future / what-if slider."""
    from .analyst.time_machine import time_machine_block

    return time_machine_block(district=district, date=date)


@app.get("/api/citizen/mesh")
def citizen_mesh() -> dict[str, Any]:
    from .analyst.citizen import mesh

    return mesh()


@app.post("/api/citizen/report")
def citizen_report(payload: dict[str, Any]) -> dict[str, Any]:
    from .analyst.citizen import report_heat

    try:
        lat = float(payload.get("lat"))
        lon = float(payload.get("lon"))
    except Exception:
        raise HTTPException(status_code=400, detail="lat/lon required")
    return report_heat(lat=lat, lon=lon, district=str(payload.get("district", "phoenix")), note=str(payload.get("note", "")))


@app.get("/api/resilience")
def resilience(
    district: str = Query("phoenix", description="district key"),
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    threshold_c: float = Query(30.0),
    source: str | None = Query(None, description="auto | mock | live"),
) -> dict[str, Any]:
    req = AuditRequest(district=district, date=date, hour=14, threshold_c=threshold_c, data_source=source, narrator_kind=None)
    rep = AuditAgent(req).run(narrate=False)
    return rep.get("resilience", {})


@app.get("/api/brief")
def brief(
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    threshold_c: float = Query(30.0),
    source: str | None = Query(None, description="auto | mock | live"),
) -> dict[str, Any]:
    """Morning brief: sweep all districts, rank by vulnerability/WBGT."""
    from .data_source import DISTRICTS

    rows: list[dict[str, Any]] = []
    for key in sorted(DISTRICTS):
        try:
            req = AuditRequest(district=key, date=date, hour=14, threshold_c=threshold_c, data_source=source, narrator_kind=None)
            rep = AuditAgent(req).run(narrate=False)
            rows.append({
                "district": rep["district"],
                "key": key,
                "wbgt_c": rep["exposure"]["wbgt_c"],
                "max_c": rep["snapshot"]["max_c"],
                "vuln_score": (rep.get("vulnerability", {}).get("score", {}) or {}).get("score"),
                "vuln_band": (rep.get("vulnerability", {}).get("score", {}) or {}).get("band"),
            })
        except Exception as exc:
            rows.append({"district": key, "error": str(exc)})
    rows.sort(key=lambda r: r.get("vuln_score", -1) if isinstance(r.get("vuln_score"), (int, float)) else -1, reverse=True)
    return {"date": date, "threshold_c": threshold_c, "source": rows[0].get("source", source) if rows else source, "districts": rows}


@app.get("/api/analysis")
def analysis(
    district: str = Query("phoenix", description="district key from /api/districts"),
    date: str = Query("2026-08-18", description="YYYY-MM-DD within catalog coverage"),
    hour: int = Query(14, ge=0, le=23),
    threshold_c: float = Query(30.0),
    source: str | None = Query(None, description="auto | mock | live"),
) -> dict[str, Any]:
    """Curated UI payload: tiles + every dashboard block, server-computed.

    Tiles are stride-subsampled (deterministic) so live grids of any
    size stay light on the wire.
    """
    from .data_source import MAX_UI_TILES

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
    heatmap = snapshot.heatmap
    tiles = heatmap.tiles if heatmap else []
    n_total = len(tiles)
    stride = max(1, math.ceil(n_total / MAX_UI_TILES))
    shown = tiles[::stride][:MAX_UI_TILES]
    return {
        "district": report["district"],
        "date": report["date"],
        "hour": report["snapshot"]["hour"],
        "threshold_c": threshold_c,
        "source": report["source"],
        "one_liner": report["one_liner"],
        "tiles": shown,
        "tile_count_total": n_total,
        "tile_count_shown": len(shown),
        "heatmap": {
            "min_c": round(heatmap.min, 2),
            "mean_c": round(heatmap.mean, 2),
            "max_c": round(heatmap.max, 2),
            "units": heatmap.units,
        },
        "diurnal": report["diurnal"],
        "attribution": report["attribution"],
        "exposure": report["exposure"],
        "vulnerability": report["vulnerability"],
        "interventions": report["interventions"][:3],
        "thermal_wind": report["thermal_wind"],
        "downburst": report["downburst"],
        "elevation": report.get("elevation", {}),
        "landcover": report.get("landcover", {}),
        "synoptic": report.get("synoptic", {}),
        "whatif": report.get("whatif", {}),
        "schedule": report.get("schedule", {}),
        "terrain": report.get("terrain", {}),
        "flight": report.get("flight", {}),
        "geomorphology": report.get("geomorphology", {}),
        "lake_effect": report.get("lake_effect", {}),
        "wind_corridor": report.get("wind_corridor", {}),
        "time_machine": report.get("time_machine", {}),
        "carbon": report.get("carbon", {}),
        "citizen": report.get("citizen", {}),
        "resilience": report.get("resilience", {}),
        "heatwave_landuse": report.get("heatwave_landuse", {}),
        "pollutants": report.get("pollutants", {}),
        "uhi": report.get("uhi", {}),
        "response": report["response"],
        "analysis": report["analysis"],
        "alerts": (report.get("alerts") or {}).get("alerts", []),
        "warnings": report.get("warnings", []),
        "provenance": report.get("provenance", ""),
    }


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
    """Open export package: tile GeoJSON + audit CSV + interventions CSV (ZIP)."""
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
