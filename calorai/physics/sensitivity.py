"""Sensitivity bands — how much the verdict moves with input uncertainty.

Every audit input (albedo, emissivity, convective coefficient,
irradiance, sky) carries uncertainty. Instead of quoting one surface
temperature, the auditor solves the implicit energy balance at the
nominal and perturbed parameters and reports the band:

    T_band(theta) = T_eq(theta +/- delta_theta) - T_eq(theta)

The equilibrium temperature solves

    (1-alpha)G  =  eps*sigma*(T^4 - T_env^4)  +  h_c*(T - T_air)
                +  Q_store  +  Q_latent

nonlinearly (Stefan-Boltzmann is quartic), via Newton iteration with
an analytical derivative dF/dT = 4*eps*sigma*T^3 + h_c.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .radiation import STEFAN_BOLTZMANN, absorbed_solar_flux, net_longwave_flux
from .units import celsius_to_kelvin


@dataclass(frozen=True)
class EquilibriumInputs:
    """Parameters of the quasi-steady surface energy balance."""

    irradiance_w_m2: float
    albedo: float
    emissivity: float = 0.93
    convective_coefficient: float = 12.0
    air_temperature_c: float = 30.0
    radiative_environment_c: float | None = None  # sky/canyon T_env
    storage_flux_w_m2: float = 0.0
    latent_flux_w_m2: float = 0.0


def equilibrium_surface_temperature_c(
    inputs: EquilibriumInputs,
    initial_guess_c: float | None = None,
    tolerance_c: float = 1e-6,
    max_iterations: int = 50,
) -> float:
    """Surface temperature at which the energy balance closes (°C).

    Newton iteration on F(T) = Q_sol - Q_lw - Q_conv - Q_store - Q_lat
    with F' = -(4 eps sigma T^3 + h_c). Raises ``ValueError`` if the
    iteration does not converge within ``max_iterations``.
    """
    q_sol = absorbed_solar_flux(inputs.irradiance_w_m2, inputs.albedo)
    t_air_k = celsius_to_kelvin(inputs.air_temperature_c)
    t_env_k = celsius_to_kelvin(
        inputs.radiative_environment_c
        if inputs.radiative_environment_c is not None
        else inputs.air_temperature_c
    )
    t_k = celsius_to_kelvin(
        initial_guess_c if initial_guess_c is not None else inputs.air_temperature_c + 5.0
    )
    for _ in range(max_iterations):
        flux = (
            q_sol
            - inputs.emissivity
            * STEFAN_BOLTZMANN
            * (t_k**4 - t_env_k**4)
            - inputs.convective_coefficient * (t_k - t_air_k)
            - inputs.storage_flux_w_m2
            - inputs.latent_flux_w_m2
        )
        dflux_dt = -(
            4.0 * inputs.emissivity * STEFAN_BOLTZMANN * t_k**3
            + inputs.convective_coefficient
        )
        step = flux / dflux_dt
        t_k -= step
        if abs(step) <= tolerance_c:
            return t_k - 273.15
    raise ValueError("equilibrium solve did not converge")


def sensitivity_bands(
    nominal: EquilibriumInputs,
    perturbations: dict[str, float],
) -> dict[str, dict[str, float]]:
    """±ΔT (°C) from perturbing each parameter by its given amount.

    ``perturbations`` maps parameter name -> absolute perturbation
    (e.g. ``{"albedo": 0.02, "convective_coefficient": 2.4}``).
    Returns {param: {"low_c": ..., "high_c": ...}} with the symmetric
    band of equilibrium temperature change.
    """
    t_nominal = equilibrium_surface_temperature_c(nominal)
    bands: dict[str, dict[str, float]] = {}
    for name, delta in perturbations.items():
        if delta == 0.0:
            continue
        lo = _perturbed(nominal, name, -delta)
        hi = _perturbed(nominal, name, +delta)
        t_lo = equilibrium_surface_temperature_c(lo)
        t_hi = equilibrium_surface_temperature_c(hi)
        bands[name] = {
            "low_c": round(t_lo - t_nominal, 2),
            "high_c": round(t_hi - t_nominal, 2),
        }
    return bands


def _perturbed(
    inputs: EquilibriumInputs, name: str, delta: float
) -> EquilibriumInputs:
    """Copy of ``inputs`` with one parameter shifted (clamped to domain)."""
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    if name == "irradiance_w_m2":
        return EquilibriumInputs(
            **{**inputs.__dict__, "irradiance_w_m2": max(0.0, inputs.irradiance_w_m2 + delta)}
        )
    if name == "albedo":
        return EquilibriumInputs(
            **{**inputs.__dict__, "albedo": _clamp(inputs.albedo + delta, 0.0, 1.0)}
        )
    if name == "emissivity":
        return EquilibriumInputs(
            **{**inputs.__dict__, "emissivity": _clamp(inputs.emissivity + delta, 0.05, 1.0)}
        )
    if name == "convective_coefficient":
        return EquilibriumInputs(
            **{
                **inputs.__dict__,
                "convective_coefficient": max(1.0, inputs.convective_coefficient + delta),
            }
        )
    if name == "air_temperature_c":
        return EquilibriumInputs(
            **{**inputs.__dict__, "air_temperature_c": inputs.air_temperature_c + delta}
        )
    if name == "radiative_environment_c":
        env = inputs.radiative_environment_c
        return EquilibriumInputs(
            **{
                **inputs.__dict__,
                "radiative_environment_c": (
                    env + delta if env is not None else None
                ),
            }
        )
    if name == "storage_flux_w_m2":
        return EquilibriumInputs(
            **{**inputs.__dict__, "storage_flux_w_m2": inputs.storage_flux_w_m2 + delta}
        )
    if name == "latent_flux_w_m2":
        return EquilibriumInputs(
            **{**inputs.__dict__, "latent_flux_w_m2": inputs.latent_flux_w_m2 + delta}
        )
    raise ValueError(f"unknown parameter {name!r}")