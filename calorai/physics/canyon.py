"""Street-canyon radiation trapping — why canyons are hotter than open lots.

Urban fabric is not a flat horizontal surface: buildings block the cool
sky and trap shortwave radiation. For an infinitely long street canyon
of height H and width W (aspect ratio H/W, Oke et al. 2017, Urban
Climates, §5.2):

- Sky view factor at mid-street floor (their Fig. 5.10; Johnson &
  Watson 1984):

      psi_sky = sqrt(1 + (H/W)^2) - H/W

  A roof has psi_sky = 1 (open horizon); a deep canyon approaches 0.

- Effective canyon-surface albedo (their Eq. 5.18):

      alpha_surf = (W*alpha_floor + H*(alpha_wall1 + alpha_wall2)) / (2H + W)

  Walls are usually darker than streets, so canyons absorb more solar
  energy than an open lot of the same floor material — the "albedo
  paradox" (higher H/W -> lower effective albedo, their Fig. 5.15).

- Longwave: the floor sees the sky through psi_sky and warm walls
  through (1 - psi_sky), so its radiative environment is warmer than
  the open-sky value:

      L_down = psi_sky * L_sky + (1 - psi_sky) * eps_wall * sigma * T_wall^4

  This cuts the net longwave loss that the flat-surface model assumes
  (their §5.2.3) — canyons keep their heat.
"""

from __future__ import annotations

import math

from .radiation import STEFAN_BOLTZMANN, sky_temperature_c
from .units import celsius_to_kelvin


def sky_view_factor(h_over_w: float) -> float:
    """Sky view factor psi_sky of the mid-street floor of a canyon.

    psi = sqrt(1 + (H/W)^2) - H/W  (infinite canyon, Oke et al. 2017,
    Fig. 5.10). Open site (H/W = 0) -> 1; deep canyon -> 0.
    """
    if h_over_w < 0.0:
        raise ValueError("aspect ratio H/W must be >= 0")
    return math.sqrt(1.0 + h_over_w * h_over_w) - h_over_w


def canyon_albedo(
    albedo_floor: float,
    albedo_wall: float,
    h_over_w: float,
) -> float:
    """Effective mean albedo of canyon surfaces (Oke Eq. 5.18).

    alpha_surf = (W*alpha_f + H*(alpha_w1 + alpha_w2)) / (2H + W) with
    W = 1. Open site -> alpha_floor. Canyons with darker walls absorb
    more than the open floor alone would — the trapping effect.
    """
    if not 0.0 <= albedo_floor <= 1.0:
        raise ValueError("floor albedo must be in [0, 1]")
    if not 0.0 <= albedo_wall <= 1.0:
        raise ValueError("wall albedo must be in [0, 1]")
    if h_over_w < 0.0:
        raise ValueError("aspect ratio H/W must be >= 0")
    return (albedo_floor + 2.0 * h_over_w * albedo_wall) / (1.0 + 2.0 * h_over_w)


def canyon_longwave_environment_c(
    air_temperature_c: float,
    relative_humidity_pct: float,
    cloud_fraction: float,
    wall_temperature_c: float,
    h_over_w: float,
    wall_emissivity: float = 0.97,
) -> float:
    """Effective radiative environment temperature of a canyon floor (°C).

    Blends the Brutsaert sky (through psi_sky) with the warm walls
    (through 1 - psi_sky):

        T_env = (psi*L_sky + (1-psi)*eps_w*sigma*T_w^4)^(1/4) / sigma^(1/4)

    In canyons the floor "sees" hot walls instead of the cold sky, so
    its net longwave loss is smaller than the flat-surface model
    assumes. Pass the result as ``sky_temperature_c`` to
    ``net_longwave_flux`` / ``energy_balance``.
    """
    if not 0.0 <= relative_humidity_pct <= 100.0:
        raise ValueError("relative humidity must be in [0, 100]")
    if not 0.0 <= cloud_fraction <= 1.0:
        raise ValueError("cloud fraction must be in [0, 1]")
    if h_over_w < 0.0:
        raise ValueError("aspect ratio H/W must be >= 0")
    if not 0.0 <= wall_emissivity <= 1.0:
        raise ValueError("wall emissivity must be in [0, 1]")
    psi = sky_view_factor(h_over_w)
    l_sky = (
        STEFAN_BOLTZMANN
        * celsius_to_kelvin(
            sky_temperature_c(air_temperature_c, relative_humidity_pct, cloud_fraction)
        )
        ** 4
    )
    l_wall = (
        wall_emissivity
        * STEFAN_BOLTZMANN
        * celsius_to_kelvin(wall_temperature_c) ** 4
    )
    l_env = psi * l_sky + (1.0 - psi) * l_wall
    return (l_env / STEFAN_BOLTZMANN) ** 0.25 - 273.15


def canyon_wind_shelter_factor(h_over_w: float) -> float:
    """Fraction of the above-roof wind that reaches street level.

    Oke et al. 2017 Ch. 4 flow regimes: isolated roughness flow
    (H/W < 0.35) leaves the wind largely intact; wake interference
    (0.35–0.65) cuts it to ~75%; skimming flow (H/W > 0.65) leaves
    ~55% in the canyon. Street-level convective coefficients must be
    scaled by this factor — wind sheltering is the dominant error
    source in WBGT forecasts (Clark, Konrad & Grundstein 2024).
    """
    if h_over_w < 0.0:
        raise ValueError("aspect ratio H/W must be >= 0")
    if h_over_w <= 0.35:
        return 1.0
    if h_over_w >= 0.65:
        return 0.55
    ramp = (h_over_w - 0.35) / 0.30
    return 1.0 - 0.45 * ramp