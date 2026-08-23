"""Analyst module M4 — equity, productivity and economy of heat."""

from .aviation import runway_heat_analysis
from .economy import district_cost_of_heat
from .equity import gini, heat_burden, cross_district_leaderboard
from .productivity import work_capacity_loss_pct, daily_hours_lost, annualized_loss
from .landcover import landcover_block
from .schedule import work_rest_schedule
from .statistics import (
    describe,
    hourly_reconstruction,
    normality,
    outliers,
    tile_statistics_block,
)
from .synoptic import synoptic_block
from .carbon import carbon_block
from .citizen import mesh as citizen_mesh, report_heat as citizen_report
from .geomorphology import geomorphology_block
from .heatwave_landuse import heatwave_landuse_block
from .lake_effect import lake_effect_block
from .pollutants import pollutants_block
from .resilience import resilience_block
from .terrain import flight_overlay, terrain_block
from .time_machine import time_machine_block
from .uhi import rank_districts, uhi_prevalence_block
from .whatif import whatif_cool_roof

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
    "terrain_block",
    "flight_overlay",
    "geomorphology_block",
    "lake_effect_block",
    "uhi_prevalence_block",
    "rank_districts",
    "carbon_block",
    "citizen_mesh",
    "citizen_report",
    "geomorphology_block",
    "heatwave_landuse_block",
    "lake_effect_block",
    "pollutants_block",
    "resilience_block",
    "time_machine_block",
    "whatif_cool_roof",
    "work_rest_schedule",
]