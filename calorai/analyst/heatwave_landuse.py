"""Heatwave effects — residential vs industrial (UHI land-use lens).

Mock district mapping:
- Residential: maryvale, east-harlem, mit-campus, san-jose, chicago, austin (housing, schools, hospitals)
- Industrial: vegas-strip, manhattan, phoenix (commercial, parking, dense core)

The block itself is per-district (where does this district sit), but the full
comparison is via rank_districts or /api/heatwave-compare. No new API, mock-safe.
"""

from __future__ import annotations

from typing import Any

RESIDENTIAL_KEYS = {"maryvale", "east-harlem", "mit-campus", "san-jose", "chicago", "austin"}
INDUSTRIAL_KEYS = {"vegas-strip", "manhattan", "phoenix"}

# Heuristic land-use from district key (honest proxy, not zoning API)
_LANDUSE = {
    "maryvale": "residential (tract housing, redlined, low canyon h/w 0.3)",
    "east-harlem": "residential (dense, h/w 1.0, low green)",
    "mit-campus": "residential / campus (h/w 0.9, river flat)",
    "san-jose": "residential (suburban, albedo 0.25)",
    "chicago": "mixed residential / commercial (lake moderated)",
    "austin": "mixed",
    "vegas-strip": "industrial / commercial (hotel canyons + parking, h/w 1.2)",
    "manhattan": "industrial / commercial (Financial District, h/w 1.5)",
    "phoenix": "industrial / urban core (h/w 0.5, low albedo 0.12)",
}


def heatwave_landuse_block(report: dict[str, Any]) -> dict[str, Any]:
    # Infer district key from report district name
    name = (report.get("district") or "").lower()
    key = None
    for k in RESIDENTIAL_KEYS | INDUSTRIAL_KEYS:
        if k.replace("-", " ") in name.lower() or k in name.lower():
            key = k
            break
    # Fallback by h/w and albedo proxy
    if key is None:
        h_w = (report.get("canyon", {}) or {}).get("aspect_ratio_h_over_w") or 0
        key = "manhattan" if h_w >= 1.2 else "maryvale"

    landuse = _LANDUSE.get(key, "unknown")
    is_res = key in RESIDENTIAL_KEYS
    snap = report.get("snapshot", {}) or {}
    exp = report.get("exposure", {}) or {}
    vuln = (report.get("vulnerability", {}) or {}).get("score", {}) or {}
    prod = (report.get("analysis", {}) or {}).get("productivity", {}) or {}
    eq = (report.get("analysis", {}) or {}).get("equity", {}) or {}

    # Effects differ by land-use
    if is_res:
        # Residential: health + equity + night pooling matters more
        effects = {
            "health_risk": f"Residential night heat {exp.get('level', '—')} — pooling {report.get('geomorphology', {}).get('cold_air_pooling_risk', '—')} affects sleep & elderly",
            "equity": f"Quintile gap {eq.get('quintile_gap_c', 0):.1f} K — housing quality split",
            "productivity": f"Home/study loss moderate {prod.get('moderate', {}).get('loss_pct', 0)}% at WBGT {exp.get('wbgt_c', 0):.1f}°C",
            "priority": "Shade bus stops + cool roofs on housing + night ventilation corridors",
        }
    else:
        # Industrial: core intensity + worker shift + grid + downburst
        effects = {
            "health_risk": f"Industrial core {snap.get('max_c', 0):.1f}°C — worker WBGT {exp.get('wbgt_c', 0):.1f}°C {exp.get('level', '')} — shift work/rest {prod.get('heavy', {}).get('loss_pct', 0)}% heavy loss",
            "grid_risk": f"Peak grid shave {report.get('carbon', {}).get('grid_mw_peak_shave', 0)} MW if cool-roof applied",
            "downburst": f"Downburst peak {report.get('downburst', {}).get('peak_risk', 'low')} — outflow watch for industrial yards",
            "priority": "Cool roofs on hottest 20% + misting on inflow axis + shift schedule",
        }

    return {
        "present": True,
        "district": report.get("district", ""),
        "district_key": key,
        "landuse": landuse,
        "is_residential": is_res,
        "is_industrial": not is_res,
        "effects": effects,
        "metrics": {
            "max_c": snap.get("max_c"),
            "wbgt_c": exp.get("wbgt_c"),
            "vuln_score": vuln.get("score"),
            "vuln_band": vuln.get("band"),
            "quintile_gap_c": eq.get("quintile_gap_c"),
            "hot_core_share_pct": eq.get("hot_core_share_pct"),
        },
        "note": "Residential = night pooling + equity + home health; Industrial = core intensity + worker + grid. No zoning API — h/w + albedo proxy, honest.",
    }
