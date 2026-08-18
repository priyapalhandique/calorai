"""Radiative heat exchange — Stefan-Boltzmann physics.

The radiative term dominates urban heat at street level. A surface
exchanges longwave energy with its surroundings as a grey body:

    Q_rad = ε σ A (T_s^4 - T_amb^4)

where ε is the surface emissivity (dimensionless), σ the Stefan-
Boltzmann constant, and temperatures are in kelvin. Solar loading is
handled alongside it: absorbed shortwave is (1 - α) G with α the
surface albedo and G the incoming solar irradiance (W/m²).
"""

from __future__ import annotations

import math

from .units import celsius_to_kelvin

#: Stefan-Boltzmann constant, W·m⁻²·K⁻⁴
STEFAN_BOLTZMANN = 5.670374419e-8

#: Solar constant used only as a sanity ceiling for irradiance inputs.
SOLAR_CONSTANT = 1361.0


def clear_sky_emissivity(
    air_temperature_c: float,
    relative_humidity_pct: float,
) -> float:
    """Clear-sky emissivity from humidity (Brutsaert, 1975).

    ε_sky = 1.24 (e_a / T_a)^(1/7)

    with e_a the near-surface vapor pressure in hPa and T_a in kelvin.
    Dry desert air → low ε_sky (cold sky); humid air → higher ε_sky.
    """
    if relative_humidity_pct < 0.0 or relative_humidity_pct > 100.0:
        raise ValueError("relative humidity must be in [0, 100]")
    t_a = celsius_to_kelvin(air_temperature_c)
    e_a = _vapor_pressure_hpa(air_temperature_c, relative_humidity_pct)
    sky_emissivity = 1.24 * (e_a / t_a) ** (1.0 / 7.0)
    return max(0.0, min(1.0, sky_emissivity))


def sky_temperature_c(
    air_temperature_c: float,
    relative_humidity_pct: float,
    cloud_fraction: float = 0.0,
) -> float:
    """Effective sky temperature (°C) seen by a horizontal surface.

    Clear: T_sky = T_a · ε_sky^0.25 (well below T_a — the real
    longwave sink). Clouds radiate near-air temperature, so the
    effective emissivity is blended:

        ε_eff = (1 − c) · ε_clear + c

    Fully overcast skies push T_sky up toward T_a.
    """
    if not 0.0 <= cloud_fraction <= 1.0:
        raise ValueError("cloud fraction must be in [0, 1]")
    if relative_humidity_pct <= 0.0:
        return air_temperature_c
    epsilon = (1.0 - cloud_fraction) * clear_sky_emissivity(
        air_temperature_c, relative_humidity_pct
    ) + cloud_fraction
    t_a = celsius_to_kelvin(air_temperature_c)
    return t_a * epsilon**0.25 - 273.15


def _vapor_pressure_hpa(air_temperature_c: float, relative_humidity_pct: float) -> float:
    """Saturation-weighted near-surface vapor pressure e_a (hPa)."""
    t = air_temperature_c
    sat = 6.112 * math.exp(17.62 * t / (243.12 + t))
    return sat * relative_humidity_pct / 100.0


def net_longwave_flux(
    surface_temperature_c: float,
    ambient_temperature_c: float,
    emissivity: float = 0.93,
    area: float = 1.0,
    sky_temperature_c: float | None = None,
) -> float:
    """Net longwave radiative flux leaving a grey surface (W).

    Q_net = ε σ A (T_s⁴ − T_sky⁴)

    Positive means the surface is losing heat to its surroundings.
    ``sky_temperature_c`` defaults to the ambient air temperature; for
    night/deep-sky exchange use the Brutsaert sky model
    (``sky_temperature_c`` in this module) — real skies sit far below
    air temperature, and a surface facing the open sky cools against
    them.
    """
    t_s = celsius_to_kelvin(surface_temperature_c)
    t_amb = celsius_to_kelvin(
        ambient_temperature_c
        if sky_temperature_c is None
        else sky_temperature_c
    )
    return emissivity * STEFAN_BOLTZMANN * area * (t_s**4 - t_amb**4)


def absorbed_solar_flux(
    irradiance_w_m2: float,
    albedo: float,
    area: float = 1.0,
) -> float:
    """Shortwave absorbed by the surface (W).

    Q_sol = (1 − α) · G · A

    ``irradiance_w_m2`` comes straight from the API's
    ``solar_irradiance`` environmental parameter.
    """
    if irradiance_w_m2 < 0.0:
        raise ValueError("irradiance cannot be negative")
    if albedo < 0.0 or albedo > 1.0:
        raise ValueError("albedo must be in [0, 1]")
    return (1.0 - albedo) * irradiance_w_m2 * area


def radiative_conductance(
    surface_temperature_c: float,
    emissivity: float = 0.93,
    area: float = 1.0,
) -> float:
    """Linearized radiative conductance dQ/dT (W/K).

    H_rad = 4 ε σ A T_s³

    Used to convert a removed flux into a temperature drop — the
    quasi-steady linearization that makes mitigation math tractable.
    """
    t_s = celsius_to_kelvin(surface_temperature_c)
    return 4.0 * emissivity * STEFAN_BOLTZMANN * area * t_s**3


def stefan_boltzmann_surface_temperature(
    net_radiative_flux_w: float,
    ambient_temperature_c: float,
    emissivity: float = 0.93,
    area: float = 1.0,
) -> float:
    """Invert the grey-body law for surface temperature (°C).

    T_s = (T_amb⁴ + Q_net / (ε σ A))^{1/4}

    Returns None physically if the surface must be hotter than the
    surroundings to shed the flux — callers should then note the
    surface is a net *absorber*.
    """
    t_a = celsius_to_kelvin(ambient_temperature_c)
    radicand = t_a**4 + net_radiative_flux_w / (
        emissivity * STEFAN_BOLTZMANN * area
    )
    if radicand <= 0.0:
        raise ValueError(
            "net radiative flux implies an impossible surface temperature; "
            "check inputs"
        )
    return radicand**0.25 - 273.15