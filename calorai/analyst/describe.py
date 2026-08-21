"""Heatmap screen-context description — VoxMind-inspired.

Like VoxMind's describe_screen() but for the tcm tile field:
what district, what pattern, what it means. No OCR — the tiles are structured data.
"""

from __future__ import annotations

from typing import Any


def describe_heatmap(report: dict[str, Any]) -> dict[str, Any]:
    snap = report.get("snapshot", {}) or {}
    eq = (report.get("analysis", {}) or {}).get("equity", {}) or {}
    st = (report.get("analysis", {}) or {}).get("statistics", {}) or {}
    tvd = report.get("theory_vs_data", {}) or {}
    uhi = report.get("uhi", {}) or {}
    s = st.get("summary", {}) or {}

    district = report.get("district", "")
    hour = snap.get("hour", "?")
    n = snap.get("n_cells", 0)
    min_c, mean_c, max_c = snap.get("min_c"), snap.get("mean_c"), snap.get("max_c")

    # Keywords like VoxMind
    keywords = []
    if (eq.get("gini") or 0) > 0.01:
        keywords.append("unequal heat")
    if (uhi.get("score") or 0) > 50:
        keywords.append("strong island")
    if (s.get("skewness") or 0) > 0.5:
        keywords.append("hot tail")
    if not keywords:
        keywords = ["diffuse heat", "flat field"]

    # Natural language description
    parts = []
    parts.append(f"You are looking at {district} at {hour}:00 — {n} tiles from {min_c:.1f} to {max_c:.1f} °C (mean {mean_c:.1f} °C).")
    if eq:
        parts.append(f"Equity: Gini {eq.get('gini', 0):.3f}, quintile gap {eq.get('quintile_gap_c', 0):.1f} K, hot-core {eq.get('hot_core_share_pct', 0):.1f}%.")
    if uhi:
        parts.append(f"UHI prevalence {uhi.get('score', 0):.0f}/100 — {uhi.get('band', '')}, {uhi.get('why', '')}.")
    if tvd:
        parts.append(tvd.get("verdict", "")[:180])
    suggested = []
    if (report.get("alerts", {}) or {}).get("present"):
        suggested.append("check alerts")
    if uhi.get("band") in ("high", "extreme"):
        suggested.append("prioritize shade on hot-core tiles")
    if (report.get("exposure", {}) or {}).get("level") in ("high", "extreme"):
        suggested.append("adjust work-rest schedule")
    suggested.append("try 'what-if cool roof 0.5'")

    return {
        "present": True,
        "district": district,
        "app": "heat-map",
        "title": f"{district} {hour}:00 heat field",
        "keywords": keywords,
        "description": " ".join(parts),
        "suggested_actions": suggested[:5],
        "all_text": f"min {min_c:.1f} mean {mean_c:.1f} max {max_c:.1f} gini {eq.get('gini', 0):.3f}",
    }
