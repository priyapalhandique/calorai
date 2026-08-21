"""Geomorphology — district-scale landform proxy for the heat audit.

Uses Re:Earth free terrain URL + district elevation + h/w canyon + inertia
to classify landform (Iwahashi & Pike 8-class simplified) and infer
cold-air pooling vs ventilation. No new API, no Google key, mock-safe.
"""

from __future__ import annotations

from typing import Any

from .terrain import RE_CESIUM_MESH, RE_MAPBOX_TILEJSON


def geomorphology_block(
    elevation_m: float,
    slope_deg: float,
    aspect_deg: float,
    hillshade: float,
    h_over_w: float,
    overnight_retention: float | None,
    radial_slope_c_per_km: float | None,
) -> dict[str, Any]:
    # Iwahashi & Pike simplified: slope + curvature proxy (Hillshade as curvature cue)
    if slope_deg < 2.0 and hillshade > 0.55:
        landform = "flat / plain"
    elif slope_deg < 5.0 and hillshade > 0.5:
        landform = "gentle slope"
    elif slope_deg >= 15.0:
        landform = "steep canyon wall / ridge"
    elif hillshade < 0.45:
        landform = "valley bottom"
    else:
        landform = "midslope"

    # Cold-air pooling risk: valley + high retention
    pooling_risk = "low"
    if landform == "valley bottom" and (overnight_retention or 0) > 0.45:
        pooling_risk = "high"
    elif landform in ("valley bottom", "flat / plain") and (overnight_retention or 0) > 0.35:
        pooling_risk = "moderate"

    # Ventilation corridor: ridge/slope + strong thermal gradient
    ventilated = False
    if landform in ("ridge", "steep canyon wall / ridge", "midslope") and abs(radial_slope_c_per_km or 0) > 1.5:
        ventilated = True

    return {
        "present": True,
        "landform": landform,
        "slope_deg": round(slope_deg, 1),
        "aspect_deg": round(aspect_deg, 0),
        "hillshade": round(hillshade, 3),
        "h_over_w": round(h_over_w, 2),
        "cold_air_pooling_risk": pooling_risk,
        "ventilated": ventilated,
        "tilejson_url": RE_MAPBOX_TILEJSON,
        "cesium_url": RE_CESIUM_MESH,
        "caveat": "District-scale 3×3 landform proxy (Iwahashi & Pike simplified, no catchment DEM) — not watershed hydrology.",
    }
