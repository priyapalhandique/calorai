"""UHI prevalence — where is the island strongest and why.

Five axes, each already computed elsewhere:
- Intensity: core excess K (thermal_wind), max-mean
- Extent: hot-core share % (equity)
- Distribution: gini + quintile gap (equity)
- Morphology: h/w, SVF, radial UHI slope (canyon + statistics)
- Persistence: exceedance hours, overnight retention (inertia + exposure)

Ranking is a simple, transparent weighted score (weights documented, not hidden).
"""

from __future__ import annotations

from typing import Any


def uhi_prevalence_block(report: dict[str, Any]) -> dict[str, Any]:
    tw = report.get("thermal_wind", {}) or {}
    eq = (report.get("analysis", {}) or {}).get("equity", {}) or {}
    st = (report.get("analysis", {}) or {}).get("statistics", {}) or {}
    inertia = report.get("inertia", {}) or {}
    exposure = report.get("exposure", {}) or {}
    canyon = report.get("canyon", {}) or {}
    snap = report.get("snapshot", {}) or {}

    # raw metrics (None-safe)
    core_excess = float(tw.get("core_excess_k") or 0.0)
    max_mean = float((snap.get("max_c") or 0) - (snap.get("mean_c") or 0))
    hot_core_share = float(eq.get("hot_core_share_pct") or 0.0)
    gini = float(eq.get("gini") or 0.0)
    qgap = float(eq.get("quintile_gap_c") or 0.0)
    h_w = float(canyon.get("aspect_ratio_h_over_w") or 0.0)
    radial_slope = float(((st.get("radial_uhi") or {}).get("slope_c_per_km") or 0.0))
    # radial slope is negative (cooler outward) — take abs for strength
    radial_strength = abs(radial_slope)
    exceedance = float(exposure.get("exceedance_hours") or 0.0)
    retention = float(inertia.get("overnight_retention") or 0.0)

    # normalized 0..1 proxies (heuristics, documented)
    # core excess 0..8K -> 0..1
    s_intensity = min(1.0, max(0.0, core_excess / 6.0) * 0.7 + min(1.0, max_mean / 4.0) * 0.3)
    s_extent = min(1.0, hot_core_share / 30.0)
    s_dist = min(1.0, gini / 0.15 * 0.5 + min(1.0, qgap / 5.0) * 0.5)
    s_morph = min(1.0, h_w / 1.5 * 0.5 + radial_strength / 3.0 * 0.5)
    s_persist = min(1.0, exceedance / 12.0 * 0.6 + retention / 0.5 * 0.4)

    # weights: intensity 30, extent 15, distribution 20, morphology 15, persistence 20
    score = round(
        30 * s_intensity + 15 * s_extent + 20 * s_dist + 15 * s_morph + 20 * s_persist, 1
    )
    # band
    if score >= 65:
        band, why = "extreme", "core + morphology + persistence all high"
    elif score >= 50:
        band, why = "high", "strong core or strong heterogeneity"
    elif score >= 35:
        band, why = "moderate", "either core or fabric drives it"
    else:
        band, why = "low", "diffuse heat, little core"

    return {
        "present": True,
        "score": score,
        "band": band,
        "why": why,
        "components": {
            "intensity": round(s_intensity, 3),
            "extent": round(s_extent, 3),
            "distribution": round(s_dist, 3),
            "morphology": round(s_morph, 3),
            "persistence": round(s_persist, 3),
        },
        "metrics": {
            "core_excess_k": round(core_excess, 2),
            "max_minus_mean_k": round(max_mean, 2),
            "hot_core_share_pct": round(hot_core_share, 1),
            "gini": round(gini, 4),
            "quintile_gap_c": round(qgap, 2),
            "h_over_w": round(h_w, 2),
            "radial_slope_c_per_km": round(radial_slope, 2),
            "exceedance_hours": round(exceedance, 1),
            "overnight_retention": round(retention, 3),
        },
        "weights": {"intensity": 30, "extent": 15, "distribution": 20, "morphology": 15, "persistence": 20},
    }


def rank_districts(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in reports:
        u = uhi_prevalence_block(r)
        rows.append({
            "district": r.get("district", ""),
            "key": r.get("district", "").lower().replace(" ", "-").replace(",", ""),
            "score": u["score"],
            "band": u["band"],
            "components": u["components"],
            "metrics": u["metrics"],
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows
