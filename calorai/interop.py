"""Interop exports — Forma-friendly handoff of audit results.

Option A of the Autodesk-Forma plan: the audit ships as open, tool-
agnostic files a design team can load elsewhere (Forma site context,
building data layers, spreadsheets) without any Autodesk account:

- ``heat_tiles_geojson``   — Point FeatureCollection of the tile layer
                             (WGS84), with threshold flags + district meta.
- ``audit_table_csv``      — one flat row of every headline number.
- ``interventions_csv``    — one row per ranked intervention.
- ``export_audit``         — writes the three files (CLI path).
- ``export_zip_bytes``     — in-memory ZIP (``GET /api/export`` path).

No new dependencies: json/csv/zipfile from the stdlib.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any


def heat_tiles_geojson(
    snapshot: Any,
    threshold_c: float = 30.0,
    hottest: dict[str, float] | None = None,
) -> dict:
    """GeoJSON FeatureCollection of the district's tile temperatures.

    Each Point is a tile centroid at (lon, lat) with ``temp_c``,
    ``above_threshold_c`` (bool) and ``is_hottest_tile`` (bool).
    """
    heatmap = snapshot.heatmap
    features = []
    for tile in heatmap.tiles:
        is_hottest = bool(
            hottest
            and tile.get("lat") == hottest.get("lat")
            and tile.get("lon") == hottest.get("lon")
        )
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [tile["lon"], tile["lat"]],
                },
                "properties": {
                    "temp_c": round(float(tile["value"]), 2),
                    "above_threshold_c": float(tile["value"]) > threshold_c,
                    "is_hottest_tile": is_hottest,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "name": f"calorai-heat-{snapshot.date}",
        "meta": {
            "district": snapshot.name,
            "date": snapshot.date,
            "source": snapshot.source,
            "layer": heatmap.analytic_type,
            "units": "celsius",
            "threshold_c": threshold_c,
            "n_cells": heatmap.n_cells,
            "min_c": round(heatmap.min, 2),
            "mean_c": round(heatmap.mean, 2),
            "max_c": round(heatmap.max, 2),
            "generator": "calorai (FortyGuard Hackathon'26)",
        },
        "features": features,
    }


def audit_table_csv(report: dict[str, Any]) -> str:
    """One flat row of every headline number, for spreadsheets/Forma."""
    snap = report.get("snapshot", {})
    attr = report.get("attribution", {})
    exposure = report.get("exposure", {})
    roi = report.get("retrofit_roi", {})
    vuln = report.get("vulnerability", {})
    facade = report.get("facade", {})
    analysis = report.get("analysis", {}) or {}
    equity = analysis.get("equity", {}) or {}
    productivity = analysis.get("productivity", {}) or {}
    economy = analysis.get("economy", {}) or {}
    circ = report.get("thermal_wind", {}) or {}
    hot_tile = snap.get("hottest_tile", {})
    row = {
        "district": report.get("district", ""),
        "date": report.get("date", ""),
        "hour": snap.get("hour", ""),
        "source": report.get("source", ""),
        "n_cells": snap.get("n_cells", ""),
        "min_c": snap.get("min_c", ""),
        "mean_c": snap.get("mean_c", ""),
        "max_c": snap.get("max_c", ""),
        "hottest_tile_lat": hot_tile.get("lat", ""),
        "hottest_tile_lon": hot_tile.get("lon", ""),
        "hottest_tile_c": hot_tile.get("value", ""),
        "solar_share_pct": attr.get("solar_share", ""),
        "longwave_share_pct": attr.get("longwave_share", ""),
        "convection_share_pct": attr.get("convection_share", ""),
        "equilibrium_surface_c": attr.get("equilibrium_surface_temperature_c", ""),
        "wbgt_c": exposure.get("wbgt_c", ""),
        "exposure_level": exposure.get("level", ""),
        "exceedance_hours": exposure.get("exceedance_hours", ""),
        "vulnerability_score": (vuln.get("score") or {}).get("score", ""),
        "vulnerability_band": (vuln.get("score") or {}).get("band", ""),
        "roi_annual_kwh": roi.get("annual_energy_kwh", ""),
        "roi_annual_usd": roi.get("annual_savings_usd", ""),
        "roi_payback_years": roi.get("payback_years", ""),
        "facade_hottest": facade.get("hottest", ""),
        "facade_coolest": facade.get("coolest", ""),
        "equity_gini": equity.get("gini", ""),
        "equity_quintile_gap_c": equity.get("quintile_gap_c", ""),
        "equity_share_above_threshold_pct": equity.get("share_above_threshold_pct", ""),
        "productivity_loss_pct": (productivity.get("moderate") or {}).get("loss_pct", ""),
        "productivity_usd_per_year": (productivity.get("moderate") or {}).get("usd_per_year", ""),
        "economy_cooling_usd_per_year": economy.get("cooling_usd_per_year", ""),
        "economy_productivity_usd_per_year": economy.get("productivity_usd_per_year", ""),
        "economy_total_usd_per_year": economy.get("total_usd_per_year", ""),
        "thermal_gradient_k_per_km": circ.get("gradient_k_per_km", ""),
        "thermal_pressure_deficit_hpa": circ.get("pressure_deficit_hpa", ""),
        "thermal_inflow_direction": circ.get("inflow_direction", ""),
        "thermal_inflow_speed_scale_m_s": circ.get("inflow_speed_scale_m_s", ""),
        "thermal_ventilation_corridors": circ.get("ventilation_corridors", ""),
    }
    return _csv_string([row])


def interventions_csv(report: dict[str, Any]) -> str:
    """One row per ranked intervention (delta °C, flux removed, scope)."""
    rows = []
    for i, iv in enumerate(report.get("interventions", []), start=1):
        rows.append(
            {
                "rank": i,
                "name": iv.get("name", ""),
                "delta_t_c": iv.get("delta_t_c", ""),
                "removed_flux_w_m2": iv.get("removed_flux_w_m2", ""),
                "scope": iv.get("scope", ""),
                "basis": iv.get("basis", ""),
            }
        )
    return _csv_string(rows)


def export_audit(
    report: dict[str, Any],
    snapshot: Any,
    threshold_c: float = 30.0,
    out_dir: str | Path = "outputs",
) -> list[Path]:
    """Write the three interop files; returns their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = _slug(report)
    files = {
        f"calorai_{slug}_tiles.geojson": json.dumps(
            heat_tiles_geojson(snapshot, threshold_c), indent=2
        ),
        f"calorai_{slug}_audit.csv": audit_table_csv(report),
        f"calorai_{slug}_interventions.csv": interventions_csv(report),
    }
    paths = []
    for name, content in files.items():
        path = out / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def export_zip_bytes(
    report: dict[str, Any],
    snapshot: Any,
    threshold_c: float = 30.0,
) -> bytes:
    """In-memory ZIP of the three interop files (for the API endpoint)."""
    slug = _slug(report)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{slug}_tiles.geojson",
            json.dumps(heat_tiles_geojson(snapshot, threshold_c), indent=2),
        )
        zf.writestr(f"{slug}_audit.csv", audit_table_csv(report))
        zf.writestr(f"{slug}_interventions.csv", interventions_csv(report))
    return buffer.getvalue()


def _csv_string(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _slug(report: dict[str, Any]) -> str:
    name = report.get("district", "district").replace(" ", "-").replace(",", "")
    return f"{name}_{report.get('date', 'date')}"