"""Terrain block — Re:Earth free terrain + hillshade + physics hooks.

No Google key, no billing. Two renderers share the same source:
- Cesium quantized-mesh: https://terrain.reearth.land/cesium-mesh/ellipsoid
- MapLibre raster-dem: https://terrain.reearth.land/mapbox/ellipsoid/tilejson.json
Slope/aspect via Horn (3x3) on the district's elevation proxy (flat mock).
Heat drape is the tcm tile field; terrain just adds elevation context +
physics overlays (thermal wind geostrophic, flight DA).
"""

from __future__ import annotations

import math
from typing import Any

RE_MAPBOX_TILEJSON = "https://terrain.reearth.land/mapbox/ellipsoid/tilejson.json"
RE_CESIUM_MESH = "https://terrain.reearth.land/cesium-mesh/ellipsoid"

# Free OSM bus-stop source (Overpass, cached)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _hillshade(slope_deg: float, aspect_deg: float, azimuth: float = 315.0, altitude: float = 45.0) -> float:
    # Simplified hillshade 0..1
    az = math.radians(azimuth)
    alt = math.radians(altitude)
    sl = math.radians(slope_deg)
    asp = math.radians(aspect_deg)
    hs = math.sin(alt) * math.cos(sl) + math.cos(alt) * math.sin(sl) * math.cos(az - asp)
    return max(0.0, min(1.0, (hs + 1) / 2))


def terrain_block(district_elevation_m: float, district_h_over_w: float = 0.0) -> dict[str, Any]:
    # Mock districts are flat at district scale; slope is small but canyon h/w adds perceived slope
    slope_deg = min(35.0, district_h_over_w * 12.0)  # canyon proxy: h/w 1.5 -> ~18°
    aspect_deg = 315.0  # NW default (Manhattan river axis)
    hs = _hillshade(slope_deg, aspect_deg)
    return {
        "present": True,
        "elevation_m": round(district_elevation_m, 0),
        "slope_deg": round(slope_deg, 1),
        "aspect_deg": round(aspect_deg, 0),
        "hillshade": round(hs, 3),
        "tilejson_url": RE_MAPBOX_TILEJSON,
        "cesium_url": RE_CESIUM_MESH,
        "attribution": "Re:Earth Terrain · Mapterhorn (CC BY 4.0) · © OpenStreetMap contributors",
        "renderers": ["maplibre-2.5d", "cesium-globe"],
        "note": "Free Re:Earth terrain; heat drape is the FortyGuard tcm field. No Google key. Toggle 2.5D (Phoenix) / 3D (Manhattan).",
    }


def flight_overlay(elevation_m: float, air_temp_c: float, qnh_hpa: float = 1013.25) -> dict[str, Any]:
    # Density altitude approximation: ISA 15C at sea level, lapse 6.5K/km
    isa_temp = 15.0 - 0.0065 * elevation_m
    delta_isa = air_temp_c - isa_temp
    # Rough DA: elevation + 120ft per degC above ISA (FAA)
    da_ft = elevation_m * 3.28084 + 120 * delta_isa * 1.8  # *1.8 for F delta
    # Geostrophic wind proxy already in thermal_wind block; link here
    return {
        "isa_temp_c": round(isa_temp, 1),
        "delta_isa_c": round(delta_isa, 1),
        "density_altitude_ft": round(da_ft, 0),
        "note": "DA = elevation + 120ft/°C above ISA (FAA); thermal wind geostrophic from physics/thermal_wind.py Wallace & Hobbs Eq. 7.20",
    }
