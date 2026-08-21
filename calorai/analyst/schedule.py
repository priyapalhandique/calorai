"""Work-rest scheduler — 24h OSHA-style table from WBGT series."""

from __future__ import annotations

from typing import Any

from ..physics.stress import exposure_risk


def work_rest_schedule(
    apparent_c: list[float | None] | None,
    wet_bulb_c: list[float | None] | None,
    solar_w_m2: list[float | None] | None,
    wind_m_s: float = 2.0,
    threshold_c: float = 30.0,
) -> dict[str, Any]:
    if not apparent_c or not any(v is not None for v in apparent_c):
        return {"present": False, "reason": "no diurnal apparent series"}
    n = len(apparent_c)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        ac = apparent_c[i]
        wb = (wet_bulb_c[i] if wet_bulb_c and i < len(wet_bulb_c) else None)
        sol = (solar_w_m2[i] if solar_w_m2 and i < len(solar_w_m2) else 850.0)
        if ac is None:
            rows.append({"hour": i, "present": False})
            continue
        exp = exposure_risk(
            wet_bulb_celsius=wb if wb is not None else ac - 6.0,
            dry_bulb_celsius=ac,
            exceedance_hours=0.0,
            threshold_celsius=threshold_c,
            irradiance_w_m2=sol if sol is not None else 0.0,
            wind_speed_m_s=wind_m_s,
        )
        wbgt = float(exp.get("wbgt_c", ac))
        # OSHA work/rest bands (ACGIH TLV simplified)
        if wbgt < 26.0:
            band, work_pct = "low", 100
        elif wbgt < 28.0:
            band, work_pct = "moderate", 75
        elif wbgt < 30.0:
            band, work_pct = "high", 50
        elif wbgt < 31.5:
            band, work_pct = "very_high", 25
        else:
            band, work_pct = "extreme", 0
        rows.append({
            "hour": i,
            "wbgt_c": round(wbgt, 1),
            "band": band,
            "work_pct": work_pct,
            "rest_pct": 100 - work_pct,
        })
    return {"present": True, "rows": rows, "note": "OSHA/ACGIH TLV work-rest, 24h diurnal WBGT; threshold %.0f C" % threshold_c}
