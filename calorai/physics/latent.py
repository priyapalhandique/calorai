"""Latent heat — evaporative cooling, Priestley-Taylor (Monteith & Unsworth 2014, Ch. 13).

Dry urban fabric converts almost no absorbed radiation into water
vapor; vegetation and wet surfaces do. The Priestley-Taylor
equilibrium-evaporation formulation (their Eq. 13.40-13.41) gives the
latent heat flux from the available energy without needing stomatal
resistance data:

    lambda E = alpha_PT * s / (s + gamma) * (Q* - G)

- Q* is the net all-wave radiation at the surface (W/m2)
- G the ground heat flux (W/m2)
- s the slope of the saturation vapor pressure curve (kPa/K)
- gamma the psychrometric constant (kPa/K), ~0.067 at sea level
- alpha_PT = 1.26 for well-watered short vegetation (Priestley &
  Taylor 1972; de Bruin 1983 discusses the range)

The fraction of the surface that is evaporating (0 dry pavement, 1
open water) scales the flux — urban fabric sits near 0, green roofs
and tree canopies higher.
"""

from __future__ import annotations

import math


def saturation_vapor_pressure_kpa(air_temperature_c: float) -> float:
    """Saturation vapor pressure e_s (kPa) — Tetens/Magnus form."""
    return 0.6108 * math.exp(17.27 * air_temperature_c / (237.3 + air_temperature_c))


def saturation_vapor_pressure_slope_kpa_k(air_temperature_c: float) -> float:
    """Slope s of e_s(T) (kPa/K) at the air temperature."""
    e_s = saturation_vapor_pressure_kpa(air_temperature_c)
    return 4098.0 * e_s / (237.3 + air_temperature_c) ** 2


def psychrometric_constant_kpa(atm_pressure_kpa: float = 101.325) -> float:
    """Psychrometric constant gamma = c_p * P / (0.622 * lambda) (kPa/K).

    ~0.067 kPa/K at sea level (Monteith & Unsworth Eq. 13.13 region).
    """
    if atm_pressure_kpa <= 0.0:
        raise ValueError("atmospheric pressure must be positive")
    cp_air = 1005.0  # J/kg/K
    latent_vaporization = 2.45e6  # J/kg
    return cp_air * atm_pressure_kpa / (0.622 * latent_vaporization)


def priestley_taylor_latent_flux(
    net_radiation_w_m2: float,
    ground_flux_w_m2: float,
    air_temperature_c: float,
    evaporative_fraction: float = 1.0,
    alpha: float = 1.26,
    atm_pressure_kpa: float = 101.325,
) -> float:
    """Evaporative cooling flux lambda E (W/m2), positive = leaving surface.

    lambda E = alpha * s/(s+gamma) * (Q* - G) * f_evap

    ``net_radiation_w_m2`` is the *net* all-wave radiation (absorbed
    shortwave minus net longwave loss). With dry fabric (f_evap = 0)
    the flux is zero — latent cooling must be earned by green
    surfaces.
    """
    if not 0.0 <= evaporative_fraction <= 1.0:
        raise ValueError("evaporative fraction must be in [0, 1]")
    if alpha <= 0.0:
        raise ValueError("Priestley-Taylor alpha must be positive")
    s = saturation_vapor_pressure_slope_kpa_k(air_temperature_c)
    gamma = psychrometric_constant_kpa(atm_pressure_kpa)
    available = net_radiation_w_m2 - ground_flux_w_m2
    if available <= 0.0:
        return 0.0
    return (
        alpha * (s / (s + gamma)) * available * evaporative_fraction
    )