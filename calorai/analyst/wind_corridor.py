"""Wind corridors — city square ventilation, Forma-inspired.

Imitates Autodesk Forma's wind analysis (video LEc_Jclop6A, transcript in
Resources/Youtube/frames): rapid AI wind + detailed CFD, comfort vs
direction, streamlines by importance, dominant wind rose, proposals
(rotated towers, wall, trees with leaf density), all from temperature
+ street view 3D + satellite — no Google key, mock-safe.

Uses thermal_wind's gradient + inflow as the honest physics backbone,
then layers canyon sheltering (Oke) + tree porosity (Forma leaf density
25% default, 10% dense) + street-view sky/building fractions.
"""

from __future__ import annotations

import math
from typing import Any

# Forma-style comfort thresholds (m/s) — sitting <2.5, standing 2.5-3.9, strolling 3.9-6.0, uncomfortable >6
COMFORT_BANDS = [
    (0.0, 2.5, "comfortable sitting"),
    (2.5, 3.9, "comfortable standing"),
    (3.9, 6.0, "comfortable strolling"),
    (6.0, 99.0, "uncomfortable"),
]

# Dominant wind rose for the site — honest: we have no observed wind, so we report the
# thermal-wind-derived inflow as the dominant direction (south across river 35% in Austin video).
# The rose is synthetic but documented as thermal proxy, not anemometer.

def _comfort_band(speed_m_s: float) -> str:
    for lo, hi, label in COMFORT_BANDS:
        if lo <= speed_m_s < hi:
            return label
    return "uncomfortable"


def wind_corridor_block(
    thermal_wind: dict[str, Any] | None,
    h_over_w: float,
    tree_pct: float | None = None,
    building_pct: float | None = None,
    sky_pct: float | None = None,
) -> dict[str, Any]:
    tw = thermal_wind or {}
    grad = float(tw.get("gradient_k_per_km") or 0.0)
    inflow_deg = tw.get("inflow_direction_deg")
    speed_scale = float(tw.get("inflow_speed_scale_m_s") or 0.0)
    uniform = bool(tw.get("uniform_field"))

    # Street canyon sheltering: high h/w = skimming flow, low ventilation
    # Oke flow regimes: isolated <0.3, wake 0.3-0.7, skimming >0.7
    if h_over_w < 0.3:
        regime = "isolated roughness (ventilated)"
        shelter = 0.95
    elif h_over_w < 0.7:
        regime = "wake interference"
        shelter = 0.72
    else:
        regime = "skimming flow (sheltered, poor ventilation)"
        shelter = 0.55

    # Tree porosity: Forma leaf density 25% default (10% dense = more opaque)
    # street view tree% maps to leaf density proxy
    leaf_density = 0.25
    if tree_pct is not None:
        # tree 0-20% -> leaf 0.1-0.35
        leaf_density = max(0.1, min(0.5, 0.10 + tree_pct * 0.012))
    tree_porosity = 1.0 - leaf_density  # 0.75 default

    # Street view sky% controls openness — low sky = canyon, high sky = square
    openness = (sky_pct or 35.0) / 100.0  # 0..1

    # Effective street-level wind in the square
    street_speed = speed_scale * shelter * (0.6 + 0.4 * openness) * tree_porosity

    # Corridor quality: wide straight streets along inflow axis are corridors
    # ventilation_corridors from thermal_wind is count of cool tiles along axis
    n_corridors = int(tw.get("ventilation_corridors") or 0)
    corridor_quality = "strong" if n_corridors >= 8 and not uniform else "moderate" if n_corridors >= 3 else "weak"
    if h_over_w > 1.0:
        corridor_quality = "weak (canyon traps)"

    # Wind rose: dominant from inflow bearing, like Forma's 35% south
    # We synthesize a rose with inflow dominant 35%, opposite 14%, others low
    rose: list[dict[str, Any]] = []
    if inflow_deg is not None and not uniform:
        # 8 sectors N, NE, E, SE, S, SW, W, NW
        for sector, deg in [("N",0),("NE",45),("E",90),("SE",135),("S",180),("SW",225),("W",270),("NW",315)]:
            delta = abs((deg - inflow_deg + 180) % 360 - 180)
            if delta < 22.5:
                pct = 35.0
            elif delta > 157.5:
                pct = 14.0
            elif delta < 67.5:
                pct = 8.0
            else:
                pct = 4.0
            rose.append({"sector": sector, "deg": deg, "pct": pct, "dominant": delta < 22.5})
    else:
        for sector, deg in [("N",0),("NE",45),("E",90),("SE",135),("S",180),("SW",225),("W",270),("NW",315)]:
            rose.append({"sector": sector, "deg": deg, "pct": 12.5, "dominant": False})

    # Proposals comparison (Forma proposals): baseline vs rotated towers vs wall vs trees
    # We simulate by varying h_over_w and tree porosity
    proposals: list[dict[str, Any]] = []
    for name, hw, td in [
        ("baseline (existing)", h_over_w, leaf_density),
        ("rotated towers 15°", max(0.2, h_over_w*0.85), leaf_density),
        ("opaque wall (dining area)", h_over_w, 0.05),  # wall = very low porosity
        ("tree line (25% leaf)", h_over_w, 0.25),
        ("dense trees (10% leaf)", h_over_w, 0.10),
    ]:
        p_shelter = 0.95 if hw < 0.3 else 0.72 if hw < 0.7 else 0.55
        p_por = 1.0 - td
        p_speed = speed_scale * p_shelter * (0.6 + 0.4 * openness) * p_por
        proposals.append({
            "name": name,
            "h_over_w": round(hw, 2),
            "leaf_density": round(td, 2),
            "street_speed_m_s": round(p_speed, 2),
            "comfort": _comfort_band(p_speed),
        })

    return {
        "present": True,
        "canyon_regime": regime,
        "street_speed_m_s": round(street_speed, 2),
        "comfort": _comfort_band(street_speed),
        "corridor_quality": corridor_quality,
        "ventilation_corridors": n_corridors,
        "shelter_factor": round(shelter, 3),
        "tree_porosity": round(tree_porosity, 3),
        "leaf_density": round(leaf_density, 3),
        "openness": round(openness, 3),
        "wind_rose": rose,
        "proposals": proposals,
        "caveat": "Forma-style rapid wind: thermal proxy + canyon sheltering + tree porosity; not CFD. Detailed CFD would take 30-90 min (Forma).",
    }
