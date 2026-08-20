"""District cost of heat — the USD price tag of the heat budget.

Two documented cost streams, both computed from already-audited
numbers (no new physics, no new API calls):

1. **Cooling energy** — the electricity currently spent keeping the
   district's hot surfaces from boiling interiors: the retrofit
   module's ``annual_energy_avoided_kwh`` (kWh the top intervention
   would save) valued at the module's implicit electricity price, i.e.
   the same ``annual_savings_usd`` the ROI block reports. Documented
   as the *avoidable* cooling spend of the top intervention.

2. **Productivity** — the labour-capacity loss at the district WBGT
   from :mod:`calorai.analyst.productivity` (Dunne 2013 curves),
   annualized with documented planning assumptions.

Both assumption sets are returned with the totals — never hidden.
"""

from __future__ import annotations

from typing import Any

from .productivity import (
    DEFAULT_HOT_DAYS_PER_YEAR,
    DEFAULT_WAGE_USD_HOUR,
    DEFAULT_WORK_HOURS_DAY,
    DEFAULT_WORKERS,
    annualized_loss,
)


def district_cost_of_heat(
    roi: dict[str, Any],
    wbgt_c: float,
    workers: int = DEFAULT_WORKERS,
    hot_days: int = DEFAULT_HOT_DAYS_PER_YEAR,
    wage_usd_hour: float = DEFAULT_WAGE_USD_HOUR,
    work_hours_day: float = DEFAULT_WORK_HOURS_DAY,
    intensity: str = "moderate",
) -> dict[str, Any]:
    """Annual cost of heat for the district (USD), both streams + total."""
    cooling_usd = float(roi.get("annual_savings_usd") or 0.0)
    energy_kwh = float(roi.get("annual_energy_avoided_kwh") or 0.0)
    prod = annualized_loss(
        wbgt_c=wbgt_c,
        work_hours_day=work_hours_day,
        workers=workers,
        hot_days=hot_days,
        wage_usd_hour=wage_usd_hour,
        intensity=intensity,
    )
    productivity_usd = float(prod["usd_per_year"])
    total = cooling_usd + productivity_usd
    return {
        "cooling_usd_per_year": round(cooling_usd, 0),
        "cooling_energy_kwh_per_year": round(energy_kwh, 0),
        "productivity_usd_per_year": round(productivity_usd, 0),
        "total_usd_per_year": round(total, 0),
        "assumptions": {
            "cooling": (
                "top-intervention avoided cooling energy valued at the ROI "
                "module's electricity price (same annual_savings_usd)"
            ),
            "productivity": {
                "workers": workers,
                "hot_days_per_year": hot_days,
                "wage_usd_hour": wage_usd_hour,
                "work_hours_day": work_hours_day,
                "intensity": intensity,
            },
        },
        "note": (
            "Bottom-up district estimate from audited physics; the two "
            "streams are independent and additive. Health costs are not "
            "included — that would require epidemiological modelling."
        ),
    }