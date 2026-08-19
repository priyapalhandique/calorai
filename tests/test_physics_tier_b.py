"""Tier B physics tests — street-canyon radiation trapping, thermal
admittance / force-restore storage, Priestley-Taylor latent cooling and
equilibrium sensitivity bands.

Sources: Oke, Mills, Christen & Voogt (2017) Urban Climates §5.2
(canyon view factors, Eq. 5.18 albedo); Campbell & Norman (1998)
Environmental Biophysics Ch. 8 (admittance, damping depth); Monteith &
Unsworth (2014) Ch. 13 (Priestley-Taylor, Eq. 13.40-13.41).
"""

import math

import pytest

from calorai.physics import (
    EquilibriumInputs,
    canyon_albedo,
    canyon_longwave_environment_c,
    canyon_wind_shelter_factor,
    damping_depth_m,
    diurnal_phase_lag_hours,
    energy_balance,
    equilibrium_surface_temperature_c,
    net_longwave_flux,
    priestley_taylor_latent_flux,
    psychrometric_constant_kpa,
    saturation_vapor_pressure_slope_kpa_k,
    sensitivity_bands,
    sky_view_factor,
    storage_heat_flux_force_restore,
    thermal_admittance,
)


# ------------------------------------------------------- street canyon (B1)


def test_sky_view_factor_open_site_and_deep_canyon():
    assert sky_view_factor(0.0) == pytest.approx(1.0)
    # Mid-street floor of an H/W = 1 canyon: sqrt(2) - 1 = 0.4142
    assert sky_view_factor(1.0) == pytest.approx(math.sqrt(2.0) - 1.0, abs=1e-4)
    assert sky_view_factor(2.0) == pytest.approx(math.sqrt(5.0) - 2.0, abs=1e-4)
    # Monotonic: deeper canyons see less sky.
    assert sky_view_factor(0.5) > sky_view_factor(1.0) > sky_view_factor(2.0)
    with pytest.raises(ValueError):
        sky_view_factor(-1.0)


def test_canyon_albedo_is_area_weighted_mean():
    # Oke Eq. 5.18 with W=1: alpha_surf = (a_f + 2H/W·a_w) / (1 + 2H/W).
    assert canyon_albedo(0.12, 0.25, 0.0) == pytest.approx(0.12)
    # H/W=1, walls 0.30, floor 0.12: (0.12 + 0.60)/3 = 0.24
    assert canyon_albedo(0.12, 0.30, 1.0) == pytest.approx(0.24)
    assert canyon_albedo(0.12, 0.30, 2.0) == pytest.approx((0.12 + 4 * 0.30) / 5.0)


def test_canyon_traps_more_solar_than_open_lot():
    # With walls darker than the street (shadowed facades, dark glass),
    # the facet-area-mean albedo (Oke Eq. 5.18) falls below the open
    # floor's — the canyon absorbs more shortwave than an open lot.
    open_absorbed = energy_balance(
        40.0, 30.0, 900.0, albedo=canyon_albedo(0.12, 0.10, 0.0)
    ).absorbed_solar
    canyon_absorbed = energy_balance(
        40.0, 30.0, 900.0, albedo=canyon_albedo(0.12, 0.10, 1.0)
    ).absorbed_solar
    assert canyon_absorbed > open_absorbed
    # With walls lighter than the street (concrete/glass), the canyon
    # mean rises instead — the honest direction of Eq. 5.18.
    assert canyon_albedo(0.12, 0.30, 1.0) > 0.12


def test_canyon_walls_warm_the_radiative_environment():
    # Deep canyon: the floor sees hot walls instead of the cool sky, so
    # its net longwave loss shrinks vs the open site.
    env_open = canyon_longwave_environment_c(35.0, 20.0, 0.0, wall_temperature_c=45.0, h_over_w=0.0)
    env_canyon = canyon_longwave_environment_c(35.0, 20.0, 0.0, wall_temperature_c=45.0, h_over_w=2.0)
    assert env_canyon > env_open
    lw_open = net_longwave_flux(50.0, 30.0, sky_temperature_c=env_open)
    lw_canyon = net_longwave_flux(50.0, 30.0, sky_temperature_c=env_canyon)
    assert lw_canyon < lw_open
    assert lw_canyon >= 0.0


def test_canyon_wind_shelter_flow_regimes():
    # Oke Ch. 4 regimes: open/widely-spaced keeps the wind, skimming
    # flow (H/W > 0.65) leaves ~55% at street level.
    assert canyon_wind_shelter_factor(0.0) == pytest.approx(1.0)
    assert canyon_wind_shelter_factor(0.2) == pytest.approx(1.0)
    assert canyon_wind_shelter_factor(1.0) == pytest.approx(0.55)
    assert canyon_wind_shelter_factor(2.0) == pytest.approx(0.55)
    # Monotone non-increasing between the regimes.
    assert canyon_wind_shelter_factor(0.5) > canyon_wind_shelter_factor(0.8)
    with pytest.raises(ValueError):
        canyon_wind_shelter_factor(-1.0)


# ------------------------------------------- thermal admittance / storage (B2)


def test_thermal_admittance_asphalt_magnitude():
    # asphalt: k=1.4 W/mK, rho=2200 kg/m3, cp=920 J/kgK
    mu = thermal_admittance(1.4, 2200.0, 920.0)
    assert mu == pytest.approx(math.sqrt(1.4 * 2200 * 920), rel=1e-6)
    assert 1400.0 < mu < 1900.0  # W·s^0.5/(m2·K)


def test_damping_depth_asphalt_top_cm():
    d = damping_depth_m(1.4, 2200.0, 920.0, period_hours=24.0)
    # ~0.14 m — the diurnal wave lives in the top ~14 cm of asphalt.
    assert d == pytest.approx(0.138, abs=0.01)


def test_diurnal_phase_lag_is_one_eighth_period():
    assert diurnal_phase_lag_hours(24.0) == pytest.approx(3.0)
    assert 2.0 < diurnal_phase_lag_hours() < 5.0  # Oke: real urban 2-5 h


def test_force_restore_storage_at_peak():
    # At the daily peak the rate term vanishes: Q_G = mu·sqrt(omega/2)·A.
    mu = thermal_admittance(1.4, 2200.0, 920.0)
    omega = 2.0 * math.pi / (24.0 * 3600.0)
    expected = mu * math.sqrt(omega / 2.0) * 8.0  # A = 8 K anomaly
    q = storage_heat_flux_force_restore(mu, surface_temperature_c=40.0, mean_temperature_c=32.0)
    assert q == pytest.approx(expected, rel=1e-6)
    assert 40.0 < q < 120.0  # W/m2 — a real storage sink


# ------------------------------------------------ latent heat, Priestley-Taylor (B3)


def test_psychrometric_constant_near_066():
    assert psychrometric_constant_kpa() == pytest.approx(0.0668, rel=1e-3)


def test_vapor_pressure_slope_at_30c():
    s = saturation_vapor_pressure_slope_kpa_k(30.0)
    assert s == pytest.approx(0.243, abs=0.01)


def test_priestley_taylor_latent_flux_scales_with_evaporative_fraction():
    # 600 W/m2 available energy, 30 C: lambda E ≈ α·s/(s+γ)·600 at f_evap=1.
    full = priestley_taylor_latent_flux(600.0, 0.0, 30.0, evaporative_fraction=1.0)
    half = priestley_taylor_latent_flux(600.0, 0.0, 30.0, evaporative_fraction=0.5)
    none = priestley_taylor_latent_flux(600.0, 0.0, 30.0, evaporative_fraction=0.0)
    assert none == 0.0
    assert half == pytest.approx(full / 2.0, rel=1e-6)
    assert 0.0 < full < 600.0  # latent never exceeds the available energy
    assert 400.0 < full < 600.0  # s/(s+γ) ≈ 0.79, α = 1.26 -> ~0.99×Q*


def test_priestley_taylor_zero_when_no_available_energy():
    assert priestley_taylor_latent_flux(100.0, 200.0, 30.0) == 0.0


# ------------------------------------------------------- sensitivity bands (B4)


def test_equilibrium_solver_reproduces_energy_balance_zero():
    inputs = EquilibriumInputs(
        irradiance_w_m2=900.0,
        albedo=0.12,
        emissivity=0.93,
        convective_coefficient=12.0,
        air_temperature_c=35.0,
        radiative_environment_c=25.0,
        storage_flux_w_m2=0.0,
        latent_flux_w_m2=20.0,
    )
    t_eq = equilibrium_surface_temperature_c(inputs)
    budget = energy_balance(
        surface_temperature_c=t_eq,
        air_temperature_c=35.0,
        irradiance_w_m2=900.0,
        albedo=0.12,
        emissivity=0.93,
        convective_coefficient=12.0,
        sky_temperature_c=25.0,
        latent_flux_w_m2=20.0,
    )
    # At equilibrium the budget closes: net flux ≈ 0.
    assert abs(budget.net_flux) < 1e-6


def test_higher_albedo_cooler_and_higher_wind_cooler():
    base = EquilibriumInputs(
        irradiance_w_m2=900.0,
        albedo=0.12,
        emissivity=0.93,
        convective_coefficient=12.0,
        air_temperature_c=35.0,
        radiative_environment_c=25.0,
    )
    t_base = equilibrium_surface_temperature_c(base)
    t_cool = equilibrium_surface_temperature_c(
        EquilibriumInputs(**{**base.__dict__, "albedo": 0.60})
    )
    t_windy = equilibrium_surface_temperature_c(
        EquilibriumInputs(**{**base.__dict__, "convective_coefficient": 25.0})
    )
    assert t_cool < t_base
    assert t_windy < t_base
    assert 30.0 < t_base < 80.0  # dark asphalt at noon under 900 W/m2


def test_sensitivity_bands_symmetric_and_ordered():
    base = EquilibriumInputs(
        irradiance_w_m2=900.0,
        albedo=0.12,
        emissivity=0.93,
        convective_coefficient=12.0,
        air_temperature_c=35.0,
        radiative_environment_c=25.0,
    )
    bands = sensitivity_bands(
        base,
        {
            "albedo": 0.02,
            "emissivity": 0.02,
            "convective_coefficient": 2.0,
            "irradiance_w_m2": 50.0,
        },
    )
    # Cooling parameters (albedo, emissivity, wind) are decreasing
    # functions of T: the +perturbation reads negative, the − reads
    # positive. Irradiance warms.
    assert bands["albedo"]["low_c"] > 0.0 > bands["albedo"]["high_c"]
    assert bands["emissivity"]["low_c"] > 0.0 > bands["emissivity"]["high_c"]
    assert (
        bands["convective_coefficient"]["low_c"]
        > 0.0
        > bands["convective_coefficient"]["high_c"]
    )
    assert bands["irradiance_w_m2"]["low_c"] < 0.0 < bands["irradiance_w_m2"]["high_c"]
    for band in bands.values():
        assert abs(band["low_c"]) < 5.0 and abs(band["high_c"]) < 5.0