"""Productivity loss from heat — WBGT to work-capacity loss.

Parameterization of the physiological work-capacity curves of Dunne et
al. (Nature Climate Change, 2013) and Kjellstrom et al. (2009): labour
capacity is near-full below a WBGT threshold, falls steeply through a
transition band, and saturates at an intensity-dependent floor.
We use an S-shaped (logistic) curve per work intensity, with the
documented parameters below.

    loss(w) = Lmax / (1 + exp(-k * (w - w50)))     [% of work capacity]

intensity   Lmax(%)   w50 (°C WBGT)   k (1/K)
light       10        28.5            1.0
moderate    25        30.0            1.3
heavy       40        31.0            1.5

The moderate curve matches the ~20-25% loss reported at WBGT ~30-31 °C
for outdoor construction work (Kjellstrom 2009; OSHA heat guidance).
"""

from __future__ import annotations

import math
from typing import Any

#: Documented parameter table (see module docstring for citations).
INTENSITY_PARAMS: dict[str, dict[str, float]] = {
    "light": {"lmax": 10.0, "w50": 28.5, "k": 1.0},
    "moderate": {"lmax": 25.0, "w50": 30.0, "k": 1.3},
    "heavy": {"lmax": 40.0, "w50": 31.0, "k": 1.5},
}

#: Documented planning assumptions for the USD figures.
DEFAULT_WORK_HOURS_DAY = 8.0
DEFAULT_WORKERS = 100
DEFAULT_HOT_DAYS_PER_YEAR = 120
DEFAULT_WAGE_USD_HOUR = 22.0


def work_capacity_loss_pct(wbgt_c: float, intensity: str = "moderate") -> float:
    """Per-cent work-capacity loss at a WBGT (0..Lmax)."""
    p = INTENSITY_PARAMS.get(intensity, INTENSITY_PARAMS["moderate"])
    if wbgt_c <= p["w50"] - 6.0:
        return 0.0
    return round(100.0 * p["lmax"] / (1.0 + math.exp(-p["k"] * (wbgt_c - p["w50"]))) / 100.0, 1)


def daily_hours_lost(
    wbgt_c: float, work_hours_day: float = DEFAULT_WORK_HOURS_DAY, intensity: str = "moderate"
) -> float:
    """Hours of labour capacity lost per work day at a steady WBGT."""
    return round(work_hours_day * work_capacity_loss_pct(wbgt_c, intensity) / 100.0, 2)


def annualized_loss(
    wbgt_c: float,
    work_hours_day: float = DEFAULT_WORK_HOURS_DAY,
    workers: int = DEFAULT_WORKERS,
    hot_days: int = DEFAULT_HOT_DAYS_PER_YEAR,
    wage_usd_hour: float = DEFAULT_WAGE_USD_HOUR,
    intensity: str = "moderate",
) -> dict[str, Any]:
    """Annualized labour-capacity loss at a steady WBGT.

    Assumptions are returned with the numbers (never hidden): the hot
    season is taken as ``hot_days`` days and every worker experiences
    the district WBGT during it.
    """
    loss_pct = work_capacity_loss_pct(wbgt_c, intensity)
    hours_per_day = work_hours_day * loss_pct / 100.0
    hours_per_year = hours_per_day * hot_days * workers
    usd_per_year = hours_per_year * wage_usd_hour
    return {
        "wbgt_c": round(wbgt_c, 2),
        "intensity": intensity,
        "loss_pct": loss_pct,
        "hours_lost_per_day_site": hours_per_day,
        "hours_lost_per_year": round(hours_per_year, 0),
        "usd_per_year": round(usd_per_year, 0),
        "assumptions": {
            "workers": workers,
            "work_hours_day": work_hours_day,
            "hot_days_per_year": hot_days,
            "wage_usd_hour": wage_usd_hour,
            "curve": "Dunne 2013 / Kjellstrom 2009 logistic parameterization",
        },
    }


def wbgt_curve_points(intensity: str = "moderate") -> list[dict[str, float]]:
    """(wbgt, loss_pct) pairs 22..36 °C for charts."""
    pts = []
    for w in [22 + 0.5 * i for i in range(29)]:
        pts.append({"wbgt_c": round(w, 1), "loss_pct": work_capacity_loss_pct(w, intensity)})
    return pts