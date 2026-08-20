"""Thermal-wind proxy — the circulation the temperature field implies.

The FortyGuard API ships no wind (see docs/fortyguard-products.md P2-4),
so this module derives the *relative* circulation a hot district should
induce, from first principles:

1. **Hydrostatic pressure perturbation.** A warm column is a lighter
   column: at the same surface elevation, the column of mean temperature
   ``T + dT`` over depth ``H`` carries less mass than its surroundings, so
   surface pressure falls by

       dp/p ~= g*H*dT / (R*T^2)            (Wallace & Hobbs, Eq. 3.29 family)

2. **Thermal wind (Wallace & Hobbs §7.2.7, Eq. 7.20).** The vertical
   shear of the geostrophic wind is proportional to the horizontal
   temperature gradient, ``k x grad(T)`` — aloft, the flow runs parallel
   to the isotherms with warm air to the right (northern hemisphere).

3. **Urban-breeze inflow.** The surface pressure deficit over the hot
   core drives street-level inflow toward it (the UHI circulation; Oke
   et al. 2017, Ch. 4) — the branch we can act on (misting placement,
   ventilation corridors).

Honesty contract (documented in the report): this is a *relative*
circulation pattern from the temperature field alone, not an absolute
wind forecast — the API has no wind to validate against. Magnitudes use
the documented UHI-circulation scale (≈1–3 m/s) and carry that caveat.
"""

from __future__ import annotations

import math
from typing import Any

GRAVITY_M_S2 = 9.81
GAS_CONSTANT_AIR_J_KG_K = 287.0
REF_PRESSURE_PA = 95_000.0  # ~950 hPa at urban surface
COLUMN_DEPTH_M = 1000.0  # mixed-layer depth of the UHI circulation

#: Documented UHI-circulation scale: ≈1–3 m/s for a 4–8 K core excess
#: (Oke et al. 2017 Ch. 4; urban-breeze literature). We use 0.4 m/s per K.
SPEED_SCALE_M_S_PER_K = 0.4


def temperature_gradient_deg(tiles: list[dict]) -> dict[str, float]:
    """Best-fit horizontal temperature gradient (K per degree lat/lon).

    Least-squares plane ``T = a + bx*lon + cy*lat`` over all tiles —
    robust to irregular grids (live API points are not a perfect mesh).
    Returns the plane coefficients plus the per-km gradient using
    ~111.32 km per degree of latitude and lon-scaled by cos(lat).
    """
    if not tiles:
        return {"a": 0.0, "b": 0.0, "c": 0.0, "k_per_deg": 0.0, "k_per_km": 0.0}
    xs = [t["lon"] for t in tiles]
    ys = [t["lat"] for t in tiles]
    zs = [t["value"] for t in tiles]
    n = len(tiles)
    sx = sum(xs)
    sy = sum(ys)
    sz = sum(zs)
    x_bar = sx / n
    y_bar = sy / n
    z_bar = sz / n
    # Centered normal equations for the plane T = a + b*x + c*y:
    #   b = (B*Dyy - C*Dxy) / (Dxx*Dyy - Dxy^2),  c = (C*Dxx - B*Dxy) / denom
    B = sum((x - x_bar) * (z - z_bar) for x, z in zip(xs, zs))
    C = sum((y - y_bar) * (z - z_bar) for y, z in zip(ys, zs))
    Dxx = sum((x - x_bar) ** 2 for x in xs)
    Dyy = sum((y - y_bar) ** 2 for y in ys)
    Dxy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    denom = Dxx * Dyy - Dxy * Dxy
    if abs(denom) < 1e-12:
        # Collinear (or near-collinear) grid: fall back to a 1-D fit on
        # the axis that actually varies, so a single street row still
        # yields a gradient direction instead of a silent zero.
        if Dxx > 1e-12:
            b = B / Dxx
            c = 0.0
        elif Dyy > 1e-12:
            b = 0.0
            c = C / Dyy
        else:
            return {"a": z_bar, "b": 0.0, "c": 0.0, "k_per_deg": 0.0, "k_per_km": 0.0}
    else:
        b = (B * Dyy - C * Dxy) / denom
        c = (C * Dxx - B * Dxy) / denom
    a = z_bar - b * x_bar - c * y_bar
    lat0 = sum(ys) / n
    cos_lat = max(math.cos(math.radians(lat0)), 1e-4)
    k_per_deg = math.hypot(b, c)
    k_per_km = math.hypot(b / cos_lat, c) / 111.32
    return {
        "a": round(a, 4),
        "b": round(b, 4),
        "c": round(c, 4),
        "k_per_deg": round(k_per_deg, 4),
        "k_per_km": round(k_per_km, 4),
    }


def pressure_perturbation_pa(
    tiles: list[dict],
    mean_temp_c: float,
    depth_m: float = COLUMN_DEPTH_M,
    p_ref_pa: float = REF_PRESSURE_PA,
) -> float:
    """Surface pressure deficit (Pa) of the warmest tile vs the district.

    Hydrostatic column argument (Wallace & Hobbs Ch. 3): a column of
    mean temperature ``T + dT`` over depth ``H`` weighs less by

        dp = p_ref * g * H * dT / (R * T^2)
    """
    if not tiles:
        return 0.0
    dT = max(t["value"] for t in tiles) - mean_temp_c
    if dT <= 0.0:
        return 0.0
    t_k = mean_temp_c + 273.15
    return p_ref_pa * GRAVITY_M_S2 * depth_m * dT / (GAS_CONSTANT_AIR_J_KG_K * t_k * t_k)


def _compass_bearing(east: float, north: float) -> float:
    """Compass bearing (0=N, clockwise) of the vector (east, north)."""
    if abs(east) < 1e-12 and abs(north) < 1e-12:
        return 0.0
    return (math.degrees(math.atan2(east, north)) + 360.0) % 360.0


def urban_circulation(tiles: list[dict], mean_temp_c: float) -> dict[str, Any]:
    """The circulation the temperature field implies (relative, caveated).

    Returns pressure deficit, inflow direction toward the hot core,
    the aloft thermal-wind direction (warm air on the right, NH),
    a scaled street-level speed, and the ventilation-corridor axis.
    """
    if not tiles:
        return {"present": False}
    grad = temperature_gradient_deg(tiles)
    b, c = grad["b"], grad["c"]  # K per degree lon/lat
    deficit_pa = pressure_perturbation_pa(tiles, mean_temp_c)
    deficit_hpa = deficit_pa / 100.0
    core_excess_k = max(t["value"] for t in tiles) - mean_temp_c
    uniform = grad["k_per_deg"] < 0.05  # no net planar gradient

    # Inflow: toward the hot core. The warm column carries less mass, so
    # surface pressure is LOW over the core; air flows from the cool,
    # high-pressure surroundings toward it — i.e. along +grad(T).
    inflow_bearing = _compass_bearing(b, c)
    # Thermal wind aloft: k x grad(T) -> (E,N) = (-c, b); warm right (NH).
    thermal_wind_bearing = _compass_bearing(-c, b)
    speed_m_s = SPEED_SCALE_M_S_PER_K * max(core_excess_k, 0.0)

    # Ventilation corridors: cool tiles lying along the inflow axis
    # (within +-45 deg of it, either direction) are on the path outside
    # air takes to reach the core.
    corridor_count = 0
    corridor_tiles: list[dict] = []
    for t in tiles:
        if t["value"] >= mean_temp_c:
            continue
        dx = t["lon"] - sum(x["lon"] for x in tiles) / len(tiles)
        dy = t["lat"] - sum(x["lat"] for x in tiles) / len(tiles)
        if math.hypot(dx, dy) < 1e-9:
            continue
        tile_bearing = _compass_bearing(dx, dy)
        for axis in (inflow_bearing, inflow_bearing + 180.0):
            delta = (tile_bearing - axis + 180.0 + 360.0) % 360.0 - 180.0
            if abs(delta) <= 45.0:
                corridor_count += 1
                corridor_tiles.append(t)
                break
    corridor_tiles.sort(key=lambda t: t["value"])
    return {
        "present": True,
        "uniform_field": uniform,
        "gradient_k_per_km": grad["k_per_km"],
        "pressure_deficit_hpa": round(deficit_hpa, 3),
        "core_excess_k": round(core_excess_k, 2),
        "inflow_direction_deg": (
            None if uniform else round(inflow_bearing, 1)
        ),
        "inflow_direction": "uniform (no net gradient)" if uniform else _compass_label(inflow_bearing),
        "thermal_wind_direction_deg": round(thermal_wind_bearing, 1),
        "inflow_speed_scale_m_s": round(speed_m_s, 2),
        "ventilation_corridors": corridor_count,
        "corridor_sample": [
            {"lat": t["lat"], "lon": t["lon"], "temp_c": round(t["value"], 2)}
            for t in corridor_tiles[:5]
        ],
        "caveat": (
            "relative circulation from the tile temperature field only; "
            "not an absolute wind forecast (the API ships no wind). "
            "Speed uses the documented UHI-circulation scale (Oke et al. "
            "2017 Ch. 4), not a momentum solve."
        ),
    }


def _compass_label(bearing_deg: float) -> str:
    labels = [
        "N", "NE", "E", "SE", "S", "SW", "W", "NW",
    ]
    return labels[int(round(bearing_deg / 45.0)) % 8]