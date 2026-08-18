"""Mitigation impact — quantified degrees Celsius per intervention.

The auditor's payoff is answering "what change in °C does this fix
buy?" Under a quasi-steady linearization of the surface balance
(H = 4εσT³ + h_c total conductance), a removed heat flux ΔQ becomes a
temperature drop

    ΔT = ΔQ / H

Standard levers, each with its flux term:

- cool roof / reflective pavement  ΔQ = Δα·G        (albedo up)
- shade (trees, canopies)          ΔQ = s·(1−α)·G   (solar blocked)
- permeable/porous surface         ΔQ ≈ C·dT/dt     (storage flattened)
- added vegetation (evapotransp.)  ΔQ = λ·ET        (latent cooling)
"""

from __future__ import annotations

from .budget import linearized_conductance


def temperature_drop_from_flux_removal(
    removed_flux_w_m2: float,
    surface_temperature_c: float,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
) -> float:
    """ΔT = ΔQ / H — degrees Celsius of relief from a removed W/m²."""
    conductance = linearized_conductance(
        surface_temperature_c, emissivity, convective_coefficient
    )
    return removed_flux_w_m2 / conductance


def albedo_delta_temperature(
    irradiance_w_m2: float,
    albedo_before: float,
    albedo_after: float,
    surface_temperature_c: float,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
) -> dict:
    """Cool-surface retrofit: ΔT = Δα·G / H.

    ``albedo_before``/``albedo_after`` in [0, 1] — e.g. 0.10 (dark
    asphalt) to 0.60 (cool coating). Returns the drop and the inputs
    that produced it, so the audit trail stays explicit.
    """
    if not 0.0 <= albedo_before <= 1.0 or not 0.0 <= albedo_after <= 1.0:
        raise ValueError("albedo values must be in [0, 1]")
    delta_albedo = albedo_after - albedo_before
    removed = delta_albedo * irradiance_w_m2
    drop = temperature_drop_from_flux_removal(
        removed, surface_temperature_c, emissivity, convective_coefficient
    )
    return {
        "delta_albedo": round(delta_albedo, 3),
        "removed_flux_w_m2": round(removed, 1),
        "delta_temperature_c": round(drop, 2),
        "note": "quasi-steady linearized surface balance",
    }


def shade_delta_temperature(
    irradiance_w_m2: float,
    albedo: float,
    shade_fraction: float,
    surface_temperature_c: float,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
) -> dict:
    """Shade intervention: ΔT = s·(1−α)·G / H.

    ``shade_fraction`` in [0, 1] — the share of the day the surface is
    covered (trees, canopies, umbrellas).
    """
    if not 0.0 <= shade_fraction <= 1.0:
        raise ValueError("shade fraction must be in [0, 1]")
    removed = shade_fraction * (1.0 - albedo) * irradiance_w_m2
    drop = temperature_drop_from_flux_removal(
        removed, surface_temperature_c, emissivity, convective_coefficient
    )
    return {
        "shade_fraction": round(shade_fraction, 3),
        "removed_flux_w_m2": round(removed, 1),
        "delta_temperature_c": round(drop, 2),
        "note": "quasi-steady linearized surface balance; evapotranspiration not included",
    }


def heat_capacity_delta_peak_temperature(
    storage_capacity_j_m2_k: float,
    temperature_swing_c: float,
    time_span_hours: float,
    surface_temperature_c: float,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
) -> dict:
    """Thermal-mass intervention: flattening the diurnal peak.

    A slab that absorbs a share of the daytime load into storage rises
    less. The fraction of the swing absorbed by added capacity is
    estimated from the balance's conductance ratio.
    """
    conductance = linearized_conductance(
        surface_temperature_c, emissivity, convective_coefficient
    )
    # Energy that goes into storage comes out of the temperature rise:
    # ΔT_peak_removed ≈ C·ΔT_swing / (H·Δt + C)
    capacity_flux = storage_capacity_j_m2_k * temperature_swing_c / (
        time_span_hours * 3600.0
    )
    total_flux = conductance * temperature_swing_c + capacity_flux
    peak_reduction = temperature_swing_c * capacity_flux / max(total_flux, 1e-9)
    return {
        "storage_capacity_j_m2_k": storage_capacity_j_m2_k,
        "estimated_peak_reduction_c": round(peak_reduction, 2),
        "note": "first-order partition of swing between conductance and storage",
    }


#: Material reference table for albedo/emissivity interventions.
#: Values are published engineering defaults (ASTM / EPA Heat Island
#: guidance); surface-specific measurements replace them when available.
MATERIALS: dict[str, dict[str, float]] = {
    "dark_asphalt": {"albedo": 0.08, "emissivity": 0.92},
    "fresh_asphalt": {"albedo": 0.12, "emissivity": 0.90},
    "gray_concrete": {"albedo": 0.30, "emissivity": 0.88},
    "white_concrete": {"albedo": 0.55, "emissivity": 0.90},
    "cool_roof_coating": {"albedo": 0.65, "emissivity": 0.90},
    "dark_metal_roof": {"albedo": 0.20, "emissivity": 0.30},
    "vegetation": {"albedo": 0.25, "emissivity": 0.95},
    "bare_soil": {"albedo": 0.25, "emissivity": 0.93},
    "water": {"albedo": 0.07, "emissivity": 0.96},
}