"""Heat Time-Machine — past / present / future / what-if slider.

Past: cached live Phoenix 2024-07-15 24× tcm (data/cache, already pulled)
Present: mock today (AuditAgent mock, zero credits)
Future: 24h forecast surrogate (ml/forecast)
What-if: cool-roof albedo 0.50 on hottest 20% (analyst/whatif)

No new live calls — all from cache/mock/forecast. One slider = time travel.
"""

from __future__ import annotations

from typing import Any

from ..data_source import DISTRICTS


def time_machine_block(
    district: str = "phoenix",
    date: str = "2026-08-18",
    present_max: float | None = None,
    present_series: list[float | None] | None = None,
    whatif_delta: float | None = None,
) -> dict[str, Any]:
    # Present: prefer values passed in by the outer audit (avoids recursion). Fallback to a nested
    # mock audit for standalone calls (tests, /api/time_machine without present data).
    if present_series is None and present_max is None and whatif_delta is None:
        try:
            from ..agent import AuditAgent, AuditRequest

            present = AuditAgent(AuditRequest(district=district, date=date, hour=14, data_source="mock")).run(narrate=False)
            present_series = (present.get("diurnal", {}) or {}).get("apparent_c", []) or []
            present_max = present.get("snapshot", {}).get("max_c")
            whatif_delta = (present.get("whatif", {}) or {}).get("delta_t_c")
        except Exception:
            present_series = []
            present_max = None
            whatif_delta = None
    if present_series is None:
        present_series = []

    # Past: try cached live Phoenix 2024-07-15 env apparent series (no live call, read cache if present)
    past_series: list[float | None] = []
    past_max = None
    try:
        from pathlib import Path
        import json, hashlib

        def ckey(endpoint, **args):
            raw = json.dumps({"endpoint": endpoint, **args}, sort_keys=True, default=str)
            return hashlib.sha256(raw.encode()).hexdigest()[:20]

        cache = Path("data/cache")
        k = ckey("env_params", district="phoenix", date="2024-07-15", temperature_anchor_c=None, schema_version=2)
        p = cache / f"{k}.json"
        if p.exists():
            j = json.loads(p.read_text())
            past_series = j.get("apparent_c", [])
            past_max = max([v for v in past_series if v is not None], default=None)
    except Exception:
        past_series = []

    # Future: forecast surrogate peak (mock-safe)
    future_peak = None
    try:
        from ..ml.forecast import load_forecast, forecast_skin_temp

        model = load_forecast()
        # use present apparent at 14:00 as anchor
        ta = present_series[14] if len(present_series) > 14 and present_series[14] is not None else 35.0
        feats = {"irradiance_w_m2": 900, "albedo": 0.12, "emissivity": 0.93, "convective_coefficient": 12.0, "air_temperature_c": ta, "radiative_environment_c": ta - 5, "storage_flux_w_m2": 100, "latent_flux_w_m2": 30}
        future_peak = round(float(forecast_skin_temp(feats, model=model)), 1)
    except Exception:
        future_peak = None

    # whatif_delta is supplied by caller (whatif_block); no nested audit here.
    return {
        "present": True,
        "district": district,
        "past": {"date": "2024-07-15 (cached live Phoenix)", "apparent_series": past_series[:8], "max_c": past_max, "note": "past = cached live tcm 24×, present = mock today"},
        "present_block": {"date": date, "apparent_series": present_series[:8], "max_c": present_max},
        "future": {"peak_skin_c": future_peak, "note": "forecast surrogate, 24h peak"},
        "whatif": {"albedo_0_5_delta_c": whatif_delta, "note": "cool-roof 0.50 on hottest 20%"},
        "slider": ["past", "present", "future", "whatif"],
    }
