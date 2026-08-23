"""Sentinel alerts (D7) — threshold rules over the audited report.

Runs a small rule set over a finished audit report and emits
webhook-ready alert payloads: severity, trigger, message, and the
exact numbers that fired the rule. Rules are declarative, so a heat
officer can read *why* an alert exists without trusting a black box.

Rules (all thresholded on the report's own numbers):
- R1 tile_max      — hottest tile above 50 °C (skin-scale hot)
- R2 wbgt          — WBGT in the high/extreme band
- R3 exceedance    — mean exceedance hours above 12 h
- R4 retention     — overnight retention above 50%
- R5 downburst     — downburst peak risk medium/high
- R6 anomaly       — flagged-tile share above 10%
- R7 equity        — quintile gap above 3 K (intra-district skew)
- R8 heat_wave     — heat-wave-day signature
- R9 fire_weather  — VPD high band
- R10 landcover    — green cover <5%
- R11 uhi          — UHI prevalence extreme
- R12 pooling      — cold-air pooling risk high
- R13 lake_breeze  — lake breeze detected
- R14 pollutant    — worst pollutant unhealthy band
- R15 industrial   — industrial heatwave land-use
"""

from __future__ import annotations

from typing import Any

ALERT_RULES: list[dict[str, Any]] = [
    {
        "id": "R1_tile_max",
        "field": ("snapshot", "max_c"),
        "op": "gt",
        "value": 50.0,
        "severity": "high",
        "message": "Hottest tile at {value:.1f} C — skin-scale heat hazard.",
    },
    {
        "id": "R2_wbgt",
        "field": ("exposure", "wbgt_c"),
        "op": "gt",
        "value": 30.9,
        "severity": "high",
        "message": "WBGT {value:.1f} C is in the high-to-extreme band.",
    },
    {
        "id": "R3_exceedance",
        "field": ("exposure", "exceedance_hours"),
        "op": "gt",
        "value": 12.0,
        "severity": "medium",
        "message": "Threshold exceeded {value:.1f} h/cell on the audit day.",
    },
    {
        "id": "R4_retention",
        "field": ("inertia", "overnight_retention"),
        "op": "gt",
        "value": 0.5,
        "severity": "medium",
        "message": "Overnight retention {value:.0%} — night stays hot.",
    },
    {
        "id": "R5_downburst",
        "field": ("downburst", "peak_risk"),
        "op": "in",
        "value": ["medium", "high"],
        "severity": "medium",
        "message": "Downburst signature {value} — outflow watch.",
    },
    {
        "id": "R6_anomaly",
        "field": ("analysis", "anomaly", "flagged_pct"),
        "op": "gt",
        "value": 10.0,
        "severity": "low",
        "message": "{value:.0f}% of tiles statistically anomalous — inspect.",
    },
    {
        "id": "R7_equity",
        "field": ("analysis", "equity", "quintile_gap_c"),
        "op": "gt",
        "value": 3.0,
        "severity": "low",
        "message": "Quintile gap {value:.1f} K — intra-district heat skew.",
    },
    {
        "id": "R8_heat_wave",
        "field": ("synoptic", "heat_wave_day"),
        "op": "in",
        "value": [True],
        "severity": "high",
        "message": "Heat-wave-day signature — {value} (≥3 h above threshold).",
    },
    {
        "id": "R9_fire_weather",
        "field": ("synoptic", "fire_band"),
        "op": "in",
        "value": ["high"],
        "severity": "high",
        "message": "Fire-weather VPD {value} — dry, hot, windy proxy.",
    },
    {
        "id": "R10_landcover_deficit",
        "field": ("landcover", "green_pct"),
        "op": "lt",
        "value": 5.0,
        "severity": "low",
        "message": "Green cover {value:.1f}% — shade deficit (landcover).",
    },
    {
        "id": "R11_uhi_extreme",
        "field": ("uhi", "score"),
        "op": "gt",
        "value": 65.0,
        "severity": "high",
        "message": "UHI prevalence {value:.0f}/100 — extreme island (core + persistence).",
    },
    {
        "id": "R12_pooling_risk",
        "field": ("geomorphology", "cold_air_pooling_risk"),
        "op": "in",
        "value": ["high"],
        "severity": "medium",
        "message": "Cold-air pooling risk {value} — valley traps night heat.",
    },
    {
        "id": "R13_lake_breeze",
        "field": ("lake_effect", "lake_detected"),
        "op": "in",
        "value": [True],
        "severity": "low",
        "message": "Lake breeze detected {value} — evaporative cooling lever active.",
    },
    {
        "id": "R14_pollutant_worst",
        "field": ("pollutants", "worst", "band"),
        "op": "in",
        "value": ["unhealthy", "very unhealthy", "unhealthy for sensitive"],
        "severity": "high",
        "message": "Pollutant {value} — heat-driven {value} (O3/PM2.5).",
    },
    {
        "id": "R15_industrial_heatwave",
        "field": ("heatwave_landuse", "is_industrial"),
        "op": "in",
        "value": [True],
        "severity": "medium",
        "message": "Industrial heatwave land-use {value} — worker + grid risk.",
    },
]


def _get_path(report: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = report
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def evaluate_alerts(report: dict[str, Any]) -> dict[str, Any]:
    """Run the rule set over a report; returns alerts + summary."""
    alerts: list[dict[str, Any]] = []
    for rule in ALERT_RULES:
        value = _get_path(report, rule["field"])
        if value is None:
            continue
        hit = False
        if rule["op"] == "gt":
            hit = value > rule["value"]
        elif rule["op"] == "lt":
            hit = value < rule["value"]
        elif rule["op"] == "in":
            hit = value in rule["value"]
        if hit:
            alerts.append(
                {
                    "id": rule["id"],
                    "severity": rule["severity"],
                    "message": rule["message"].format(value=value),
                    "field": ".".join(rule["field"]),
                    "value": value,
                    "threshold": rule["value"],
                }
            )
    alerts.sort(key=lambda a: {"high": 0, "medium": 1, "low": 2}[a["severity"]])
    severities = [a["severity"] for a in alerts]
    top = severities[0] if severities else "none"
    return {
        "present": bool(alerts),
        "n_alerts": len(alerts),
        "top_severity": top,
        "alerts": alerts,
        "summary": (
            f"{len(alerts)} alert(s) fired; top severity {top}"
            if alerts else "No threshold rules fired."
        ),
        "webhook_payload": {
            "service": "calorai-sentinel",
            "district": report.get("district", ""),
            "date": report.get("date", ""),
            "severity": top,
            "alerts": [a["id"] for a in alerts],
        },
    }