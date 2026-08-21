"""Community Resilience OS — single 0-100 score + ranked actions.

Weighted: UHI 25 + vulnerability 25 + lake 10 (free cooling) + bus shelter 15 + work-rest 15 + green 10
Mock-safe, zero new API.
"""

from __future__ import annotations

from typing import Any


def resilience_block(report: dict[str, Any]) -> dict[str, Any]:
    uhi = (report.get("uhi", {}) or {}).get("score", 50)
    vuln = ((report.get("vulnerability", {}) or {}).get("score", {}) or {}).get("score", 50)
    lake = report.get("lake_effect", {}) or {}
    lc = report.get("landcover", {}) or {}
    geo = report.get("geomorphology", {}) or {}
    schedule = report.get("schedule", {}) or {}

    # components 0..100 each, higher = worse (needs resilience)
    c_uhi = min(100, max(0, float(uhi)))
    c_vuln = min(100, max(0, float(vuln)))
    c_lake = 0 if lake.get("lake_detected") else 30  # no lake = need more
    c_shelter = 0 if (lc.get("green_pct", 0) or 0) > 10 else 40
    # work-rest: worst hour work% low = high need
    rows = (schedule.get("rows") or [])
    worst_work = min([r.get("work_pct", 100) for r in rows if r.get("work_pct") is not None], default=100)
    c_work = 100 - worst_work
    c_green = max(0, 30 - float(lc.get("green_pct", 0) or 0) * 2)

    score = round(100 - (0.25*c_uhi + 0.25*c_vuln + 0.10*c_lake + 0.15*c_shelter + 0.15*c_work + 0.10*c_green), 0)
    score = max(0, min(100, score))
    band = "high" if score >= 70 else "moderate" if score >= 45 else "low"

    actions: list[str] = []
    if c_uhi > 50:
        actions.append("Prioritize shade on hot-core tiles (UHI high)")
    if c_vuln > 60:
        actions.append("Activate heat-response + misting schedule")
    if c_lake > 20:
        actions.append("No lake breeze — add evaporative shade")
    if c_shelter > 30:
        actions.append("Plant trees / add shelter at bus stops")
    if c_work > 50:
        actions.append("Shift outdoor work to 06-10h (work-rest)")
    if not actions:
        actions.append("Monitor — no immediate action")

    return {
        "present": True,
        "score": int(score),
        "band": band,
        "components": {"uhi": c_uhi, "vuln": c_vuln, "lake": c_lake, "shelter": c_shelter, "work": c_work, "green": c_green},
        "ranked_actions": actions[:5],
        "note": "0-100 resilience (100 = most resilient). Text 'HEAT' to check my block — mock citizen report.",
    }
