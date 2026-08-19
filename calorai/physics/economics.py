"""Retrofit economics — Track 2 (Future Buildings & Energy).

Turns a measured temperature reduction into a budget decision. The
cooling energy a retrofit avoids follows the transmission physics:

    E_avoided = U · A · DH · ΔT / 1000 / COP        (kWh)

with U the envelope conductance (W/m²·K), A the treated area (m²), DH
the cooling-season degree-hours (°C·h) the intervention operates over,
ΔT the surface-temperature reduction (°C) — the number the physics
engine actually produces — and COP the cooling-system efficiency.
"""

from __future__ import annotations

#: Standard cooling-season balance temperature (°C) below which no
#: mechanical cooling is assumed (ASHRAE-style balance point).
BALANCE_TEMPERATURE_C = 18.3


def cooling_energy_avoided_kwh(
    degree_hours_c: float,
    delta_t_c: float,
    envelope_area_m2: float,
    u_value_w_m2_k: float = 0.5,
    cop: float = 3.5,
) -> float:
    """Annual cooling energy avoided by a ΔT retrofit (kWh).

    E = U·A·DH·ΔT / (1000·COP); zero for a no-op retrofit.
    """
    if degree_hours_c < 0.0:
        raise ValueError("degree-hours cannot be negative")
    if delta_t_c < 0.0:
        raise ValueError("delta T cannot be negative")
    if envelope_area_m2 <= 0.0:
        raise ValueError("envelope area must be positive")
    if u_value_w_m2_k <= 0.0:
        raise ValueError("U-value must be positive")
    if cop <= 0.0:
        raise ValueError("COP must be positive")
    return u_value_w_m2_k * envelope_area_m2 * degree_hours_c * delta_t_c / (1000.0 * cop)


def cooling_degree_hours(
    base_mean_c: float,
    hot_days: int | None = None,
    hours_per_day: float = 6.0,
    balance_c: float = BALANCE_TEMPERATURE_C,
) -> float:
    """Proxy cooling-season degree-hours from a district's hot-season mean.

    DH = hot_days · hours_per_day · max(0, base_mean − balance). When
    ``hot_days`` is omitted it is scaled from the mean excess so hotter
    districts get longer seasons: 100 + 12·(base_mean − 26), capped at
    200 days. A documented proxy, not a load model.
    """
    if base_mean_c < -60.0 or base_mean_c > 60.0:
        raise ValueError("unphysical mean temperature")
    excess = max(0.0, base_mean_c - balance_c)
    if hot_days is None:
        hot_days = min(200, 100 + int(12.0 * (base_mean_c - 26.0)))
    hot_days = max(0, int(hot_days))
    return hot_days * hours_per_day * excess


def retrofit_roi(
    degree_hours_c: float,
    delta_t_c: float,
    envelope_area_m2: float,
    retrofit_cost_usd: float,
    electricity_price_usd_kwh: float = 0.15,
    u_value_w_m2_k: float = 0.5,
    cop: float = 3.5,
    lifespan_years: int = 10,
) -> dict:
    """Annual savings, simple payback, and lifespan net from a retrofit.

    Assumptions are returned alongside the numbers so the user can
    judge them: U, COP, electricity price, and that ΔT applies across
    the sunlit cooling hours embedded in the degree-hours input.
    """
    if retrofit_cost_usd < 0.0:
        raise ValueError("retrofit cost cannot be negative")
    if electricity_price_usd_kwh <= 0.0:
        raise ValueError("electricity price must be positive")
    if lifespan_years <= 0:
        raise ValueError("lifespan must be positive")
    annual_kwh = cooling_energy_avoided_kwh(
        degree_hours_c,
        delta_t_c,
        envelope_area_m2,
        u_value_w_m2_k,
        cop,
    )
    annual_savings = annual_kwh * electricity_price_usd_kwh
    payback_years = (
        retrofit_cost_usd / annual_savings if annual_savings > 0.0 else float("inf")
    )
    return {
        "annual_energy_avoided_kwh": round(annual_kwh, 0),
        "annual_savings_usd": round(annual_savings, 0),
        "retrofit_cost_usd": round(retrofit_cost_usd, 0),
        "payback_years": (
            round(payback_years, 1) if payback_years != float("inf") else None
        ),
        "lifespan_years": lifespan_years,
        "lifespan_net_savings_usd": round(
            annual_savings * lifespan_years - retrofit_cost_usd, 0
        ),
        "assumptions": {
            "degree_hours_c": round(degree_hours_c, 0),
            "delta_t_c": round(delta_t_c, 2),
            "envelope_area_m2": envelope_area_m2,
            "u_value_w_m2_k": u_value_w_m2_k,
            "cop": cop,
            "electricity_price_usd_kwh": electricity_price_usd_kwh,
        },
    }