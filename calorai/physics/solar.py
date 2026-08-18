"""Solar geometry — where the irradiance actually comes from.

The API reports clear-sky ``ghi``/``dni``/``dhi`` aggregate scalars, but
the *instantaneous* solar load on a surface follows the sun position:

    sin(elev)  = sin φ · sin δ + cos φ · cos δ · cos H
    δ (declination) ≈ −23.44° · cos(2π/365 · (N + 10))
    H (hour angle)  = 15° · (h − 12) + (15°·ΔTZ − λ)

For tilted surfaces (roofs, facades) the beam component is projected
onto the plane via cos θ_inc; the sky-diffuse and ground-reflected
components follow the classic isotropic model.
"""

from __future__ import annotations

import math

from .radiation import SOLAR_CONSTANT

DEG = math.pi / 180.0


def solar_declination_degrees(day_of_year: int) -> float:
    """Solar declination δ (°) for the given day-of-year (1..366).

    −23.44° at the winter solstice, +23.44° at the summer solstice,
    ≈ 0° at both equinoxes.
    """
    if not 1 <= day_of_year <= 366:
        raise ValueError("day of year must be in [1, 366]")
    return -23.44 * math.cos(2.0 * math.pi * (day_of_year + 10.0) / 365.0)


def hour_angle_degrees(
    clock_hour: float,
    utc_offset_hours: float,
    longitude_deg: float,
) -> float:
    """Solar hour angle H (°), east of solar noon positive.

    H = 15°·(h − 12) + (15°·ΔTZ − λ) with the local standard meridian
    taken as 15°·ΔTZ. Positive after solar noon.
    """
    return 15.0 * (clock_hour - 12.0) + (15.0 * utc_offset_hours - longitude_deg)


def solar_elevation_degrees(
    latitude_deg: float,
    declination_deg: float,
    hour_angle_deg: float,
) -> float:
    """Solar elevation angle (°) above the horizon.

    sin(elev) = sin φ sin δ + cos φ cos δ cos H; returns negative
    values below the horizon (elevation is the asin of the expression).
    """
    sin_elev = (
        math.sin(latitude_deg * DEG) * math.sin(declination_deg * DEG)
        + math.cos(latitude_deg * DEG)
        * math.cos(declination_deg * DEG)
        * math.cos(hour_angle_deg * DEG)
    )
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))


def _diffuse_fraction(ghi_w_m2: float, elevation_deg: float) -> float:
    """Diffuse share of horizontal GHI from the clearness index.

    Erbs-style piecewise fit on k_t = GHI / (S₀ · sin(elev)); a clear
    midday sky returns ~10-15% diffuse.
    """
    if ghi_w_m2 <= 0.0 or elevation_deg <= 0.5:
        return 1.0  # dawn/dusk or night: everything is diffuse
    kt = ghi_w_m2 / (SOLAR_CONSTANT * math.sin(elevation_deg * DEG))
    kt = max(0.0, min(1.0, kt))
    if kt <= 0.22:
        return max(0.0, 1.0 - 1.13 * kt)
    if kt <= 0.8:
        return max(0.0, min(1.0, 1.557 - 1.84 * kt))
    return 0.14


def tilted_incident_irradiance(
    ghi_w_m2: float,
    elevation_deg: float,
    tilt_deg: float = 0.0,
    surface_azimuth_deg: float = 180.0,
    solar_azimuth_deg: float = 180.0,
    ground_albedo: float = 0.20,
    diffuse_fraction: float | None = None,
) -> dict:
    """Incident irradiance on a tilted plane (W/m²) + decomposition.

    Beam is projected via cos(θ_inc) / sin(elev); sky diffuse uses the
    isotropic (1+cos t)/2 view factor; ground reflection the
    (1−cos t)/2 complement. A horizontal plane (tilt=0) returns GHI.
    """
    if ghi_w_m2 < 0.0:
        raise ValueError("irradiance cannot be negative")
    if not 0 <= tilt_deg <= 90:
        raise ValueError("tilt must be in [0, 90]")
    kd = (
        diffuse_fraction
        if diffuse_fraction is not None
        else _diffuse_fraction(ghi_w_m2, elevation_deg)
    )
    kd = max(0.0, min(1.0, kd))
    sin_elev = max(math.sin(elevation_deg * DEG), 1e-6)
    cos_tilt = math.cos(tilt_deg * DEG)
    cos_inc = (
        math.cos(elevation_deg * DEG) * math.sin(tilt_deg * DEG)
        * math.cos((solar_azimuth_deg - surface_azimuth_deg) * DEG)
        + math.sin(elevation_deg * DEG) * cos_tilt
    )
    beam_incident = (1.0 - kd) * ghi_w_m2 * max(cos_inc, 0.0) / sin_elev
    diffuse_incident = kd * ghi_w_m2 * (1.0 + cos_tilt) / 2.0
    reflected = ghi_w_m2 * ground_albedo * (1.0 - cos_tilt) / 2.0
    return {
        "incident_w_m2": round(beam_incident + diffuse_incident + reflected, 1),
        "beam_w_m2": round(beam_incident, 1),
        "diffuse_w_m2": round(diffuse_incident, 1),
        "reflected_w_m2": round(reflected, 1),
        "diffuse_fraction": round(kd, 3),
    }