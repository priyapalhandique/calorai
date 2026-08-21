"""Analyst module M4 — equity, productivity and economy of heat."""

from .aviation import runway_heat_analysis
from .economy import district_cost_of_heat
from .equity import gini, heat_burden, cross_district_leaderboard
from .productivity import work_capacity_loss_pct, daily_hours_lost, annualized_loss
from .landcover import landcover_block
from .statistics import (
    describe,
    hourly_reconstruction,
    normality,
    outliers,
    tile_statistics_block,
)
from .synoptic import synoptic_block

__all__ = [
    "gini",
    "heat_burden",
    "cross_district_leaderboard",
    "work_capacity_loss_pct",
    "daily_hours_lost",
    "annualized_loss",
    "district_cost_of_heat",
    "runway_heat_analysis",
    "describe",
    "outliers",
    "normality",
    "hourly_reconstruction",
    "tile_statistics_block",
    "landcover_block",
    "synoptic_block",
]