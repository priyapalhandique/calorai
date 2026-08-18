"""Street-level urban energy balance — why a place is hot.

Per unit surface area, the instantaneous heat budget is:

    C dT/dt = (1−α)G  −  εσ(T_s⁴ − T_sky⁴)  −  h_c(T_s − T_air)

- absorbed shortwave     (1−α)G          — solar load, albedo-mediated
- net longwave           εσ(T_s⁴−T_sky⁴) — grey-body exchange (radiation)
- convective exchange    h_c(T_s−T_air)  — Newton's law of cooling
- storage                C dT/dt         — thermal inertia of the mass

The auditor reports every term at the measured temperature, attributes
the net heat load across mechanisms, and explains the diurnal swing via
the storage term.
"""

from __future__ import annotations

from dataclasses import dataclass

from .radiation import (
    STEFAN_BOLTZMANN,
    absorbed_solar_flux,
    net_longwave_flux,
)
from .units import celsius_to_kelvin


@dataclass(frozen=True)
class SurfaceBudget:
    """One instantaneous energy-balance snapshot for one surface."""

    absorbed_solar: float   # W/m²
    net_longwave: float     # W/m², positive = leaving the surface
    convection: float       # W/m², positive = leaving the surface
    storage: float          # W/m², positive = warming up
    net_flux: float         # W/m², positive = net heat INTO the surface

    def attribution(self) -> dict[str, float]:
        """Share of the *positive* heat load by mechanism (0-100%).

        Negative terms are sinks and contribute zero to the load.
        """
        terms = {
            "solar_absorption": max(self.absorbed_solar, 0.0),
            "net_longwave_retention": -min(self.net_longwave, 0.0),
            "convection_suppression": -min(self.convection, 0.0),
        }
        total = sum(terms.values())
        if total <= 0.0:
            return {k: 0.0 for k in terms}
        return {k: 100.0 * v / total for k, v in terms.items()}

    def as_dict(self) -> dict[str, float]:
        return {
            "absorbed_solar_w_m2": self.absorbed_solar,
            "net_longwave_w_m2": self.net_longwave,
            "convection_w_m2": self.convection,
            "storage_w_m2": self.storage,
            "net_flux_w_m2": self.net_flux,
            "attribution_percent": self.attribution(),
        }


def convective_flux(
    surface_temperature_c: float,
    air_temperature_c: float,
    convective_coefficient: float = 12.0,
) -> float:
    """Newton's law of cooling, W/m².

    Q_conv = h_c (T_s − T_air)

    ``convective_coefficient`` defaults to a calm-conditions street
    value (~12 W/m²·K); wind raises it toward 20-30 W/m²·K.
    """
    return convective_coefficient * (surface_temperature_c - air_temperature_c)


def storage_capacity(
    density_kg_m3: float,
    specific_heat_j_kg_k: float,
    thickness_m: float,
) -> float:
    """Area-specific thermal storage capacity (J/m²·K).

    C = ρ c d — the heat needed to warm a slab of the surface one kelvin.
    """
    if density_kg_m3 <= 0.0 or specific_heat_j_kg_k <= 0.0 or thickness_m <= 0.0:
        raise ValueError("density, specific heat and thickness must be positive")
    return density_kg_m3 * specific_heat_j_kg_k * thickness_m


def storage_flux(
    storage_capacity_j_m2_k: float,
    temperature_change_c: float,
    time_span_hours: float,
) -> float:
    """Stored heat flux (W/m²): C · ΔT / Δt, positive = warming."""
    if time_span_hours <= 0.0:
        raise ValueError("time span must be positive")
    return storage_capacity_j_m2_k * temperature_change_c / (time_span_hours * 3600.0)


def energy_balance(
    surface_temperature_c: float,
    air_temperature_c: float,
    irradiance_w_m2: float,
    albedo: float,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
    storage_capacity_j_m2_k: float = 0.0,
    temperature_change_c: float = 0.0,
    time_span_hours: float = 1.0,
) -> SurfaceBudget:
    """Full street-level budget for one surface (per m²).

    Parameters follow the API's vocabulary: ``surface_temperature_c`` is
    the tile reading, ``irradiance_w_m2`` the ``solar_irradiance``
    environmental parameter, ``albedo``/``emissivity`` material
    properties, ``convective_coefficient`` an estimate for the street
    environment, and the storage terms come from the material slab.
    """
    q_sol = absorbed_solar_flux(irradiance_w_m2, albedo)
    q_lw = net_longwave_flux(
        surface_temperature_c, air_temperature_c, emissivity
    )
    q_conv = convective_flux(
        surface_temperature_c, air_temperature_c, convective_coefficient
    )
    q_store = storage_flux(
        storage_capacity_j_m2_k, temperature_change_c, time_span_hours
    )
    # Flux convention: sinks leave the surface (negative in the balance),
    # so net flux into the surface is solar − radiation − convection − storage.
    net = q_sol - q_lw - q_conv - q_store
    return SurfaceBudget(
        absorbed_solar=q_sol,
        net_longwave=q_lw,
        convection=q_conv,
        storage=q_store,
        net_flux=net,
    )


def linearized_conductance(
    surface_temperature_c: float,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
) -> float:
    """Total linearized surface-to-air conductance H (W/m²·K).

    H = 4εσT_s³ + h_c — the slope of the loss terms vs. temperature.
    """
    t_s = celsius_to_kelvin(surface_temperature_c)
    return 4.0 * emissivity * STEFAN_BOLTZMANN * t_s**3 + convective_coefficient