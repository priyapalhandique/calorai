"""Thermal inertia — why some blocks stay hot after sunset.

The key to a heat-budget *auditor* (vs. a thermometer) is the time
dimension: which surfaces store daytime heat and release it at night.
The governing quantity is thermal effusivity,

    e = √(k ρ c)

which sets how fast a surface heats under a given load — and the
Newtonian cooling time constant of an exposed slab:

    T(t) = T_air + (T_0 − T_air) exp(−t / τ),   τ = C / H

with C the area-specific heat capacity and H the linearized
conductance. Blocks with high effusivity/low τ cool fast; dense
pavement with high C stays warm — the persistence signal FortyGuard's
``persistence`` heatmap layer captures directly.
"""

from __future__ import annotations

import math


def thermal_effusivity(
    thermal_conductivity_w_m_k: float,
    density_kg_m3: float,
    specific_heat_j_kg_k: float,
) -> float:
    """Thermal effusivity e = √(kρc), J·m⁻²·K⁻¹·s⁻¹/².

    Higher effusivity → surface resists temperature swings (feels
    cooler by day, warmer at night).
    """
    if thermal_conductivity_w_m_k <= 0.0:
        raise ValueError("thermal conductivity must be positive")
    if density_kg_m3 <= 0.0:
        raise ValueError("density must be positive")
    if specific_heat_j_kg_k <= 0.0:
        raise ValueError("specific heat must be positive")
    return math.sqrt(
        thermal_conductivity_w_m_k * density_kg_m3 * specific_heat_j_kg_k
    )


def cooling_curve_temperature(
    initial_temperature_c: float,
    air_temperature_c: float,
    time_constant_hours: float,
    elapsed_hours: float,
) -> float:
    """Newton's law of cooling: T(t) = T_air + (T_0 − T_air)e^(−t/τ)."""
    if time_constant_hours <= 0.0:
        raise ValueError("time constant must be positive")
    delta = initial_temperature_c - air_temperature_c
    return air_temperature_c + delta * math.exp(-elapsed_hours / time_constant_hours)


def time_to_cool(
    initial_temperature_c: float,
    target_temperature_c: float,
    air_temperature_c: float,
    time_constant_hours: float,
) -> float:
    """Hours to cool from T_0 to T_target under Newton's law.

    t = −τ ln((T_target − T_air) / (T_0 − T_air))

    Returns ``inf`` when the target is unreachable (at/below T_air).
    """
    if time_constant_hours <= 0.0:
        raise ValueError("time constant must be positive")
    target_gap = target_temperature_c - air_temperature_c
    initial_gap = initial_temperature_c - air_temperature_c
    if target_gap <= 0.0:
        return math.inf
    if initial_gap <= 0.0:
        return 0.0
    if target_gap >= initial_gap:
        return 0.0
    return -time_constant_hours * math.log(target_gap / initial_gap)


def overnight_retention_ratio(
    time_constant_hours: float,
    night_length_hours: float = 10.0,
) -> float:
    """Fraction of the daytime excess temperature still present at dawn.

    R = e^(−night/τ) — a persistence index in [0, 1]. Above ~0.3 the
    block measurably "keeps" the day's heat overnight.
    """
    if time_constant_hours <= 0.0:
        raise ValueError("time constant must be positive")
    return math.exp(-night_length_hours / time_constant_hours)


def slab_time_constant(
    storage_capacity_j_m2_k: float,
    conductance_w_m2_k: float,
) -> float:
    """Newtonian time constant of a slab τ = C / H (hours)."""
    if storage_capacity_j_m2_k <= 0.0 or conductance_w_m2_k <= 0.0:
        raise ValueError("capacity and conductance must be positive")
    return storage_capacity_j_m2_k / conductance_w_m2_k / 3600.0