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


def thermal_admittance(
    thermal_conductivity_w_m_k: float,
    density_kg_m3: float,
    specific_heat_j_kg_k: float,
) -> float:
    """Thermal admittance μ = √(kρc), J·m⁻²·K⁻¹·s⁻¹/² (Campbell & Norman Ch. 8).

    Identical to the thermal effusivity for a semi-infinite medium —
    the quantity that decides how absorbed radiation splits between
    the atmosphere and the fabric. High-μ surfaces (asphalt, concrete)
    store the day's heat; low-μ ones (dry soil, mulch) hand it to the
    air. See ``thermal_effusivity``.
    """
    return thermal_effusivity(
        thermal_conductivity_w_m_k, density_kg_m3, specific_heat_j_kg_k
    )


def damping_depth_m(
    thermal_conductivity_w_m_k: float,
    density_kg_m3: float,
    specific_heat_j_kg_k: float,
    period_hours: float = 24.0,
) -> float:
    """Depth where the diurnal temperature wave decays to e^-1 (m).

    d = sqrt(2k / (rho c omega))  (Campbell & Norman Eq. 8.5/8.6)

    Asphalt (~0.14 m) feels the day's swing only in its top few cm;
    the mass below stores it all day and releases it at night.
    """
    if period_hours <= 0.0:
        raise ValueError("period must be positive")
    if thermal_conductivity_w_m_k <= 0.0:
        raise ValueError("thermal conductivity must be positive")
    if density_kg_m3 <= 0.0 or specific_heat_j_kg_k <= 0.0:
        raise ValueError("density and specific heat must be positive")
    omega = 2.0 * math.pi / (period_hours * 3600.0)
    return math.sqrt(
        2.0 * thermal_conductivity_w_m_k
        / (density_kg_m3 * specific_heat_j_kg_k * omega)
    )


def diurnal_phase_lag_hours(period_hours: float = 24.0) -> float:
    """Ideal surface-temperature lag behind the heat wave (hours).

    For a homogeneous semi-infinite medium the surface temperature
    wave lags the surface flux by one-eighth of the period (45°);
    real urban fabric shows 2-5 h (Oke et al. 2017, §5). The lag
    between solar noon and the measured peak layer temperature is
    the auditor's fingerprint of how much the fabric stores heat.
    """
    if period_hours <= 0.0:
        raise ValueError("period must be positive")
    return period_hours / 8.0


def storage_heat_flux_force_restore(
    thermal_admittance_j_m2_k_s05: float,
    surface_temperature_c: float,
    mean_temperature_c: float,
    temperature_rate_c_per_s: float = 0.0,
    period_hours: float = 24.0,
) -> float:
    """Blackadar force-restore ground heat flux (W/m2), positive = warming.

    Q_G = μ·sqrt(ω/2)·(T_s − T̄) + μ/sqrt(2ω)·dT_s/dt

    Two terms: the temperature anomaly today (the slab has been
    absorbing all day) and the instantaneous rate of change. At the
    daily peak the rate term vanishes and Q_G = μ·sqrt(ω/2)·A — a
    material-only storage estimate that needs no slab-thickness
    assumption.
    """
    if thermal_admittance_j_m2_k_s05 <= 0.0:
        raise ValueError("thermal admittance must be positive")
    if period_hours <= 0.0:
        raise ValueError("period must be positive")
    omega = 2.0 * math.pi / (period_hours * 3600.0)
    anomaly = surface_temperature_c - mean_temperature_c
    return (
        thermal_admittance_j_m2_k_s05
        * math.sqrt(omega / 2.0)
        * anomaly
        + thermal_admittance_j_m2_k_s05 / math.sqrt(2.0 * omega) * temperature_rate_c_per_s
    )