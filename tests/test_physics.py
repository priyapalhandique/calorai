"""Physics engine tests — every formula checked against hand values."""

import math

import pytest

from calorai.physics import (
    MATERIALS,
    absorbed_solar_flux,
    albedo_delta_temperature,
    convective_flux,
    cooling_curve_temperature,
    energy_balance,
    exposure_risk,
    fahrenheit_to_celsius,
    heat_stress_level,
    net_longwave_flux,
    normalize_celsius,
    overnight_retention_ratio,
    radiative_conductance,
    shade_delta_temperature,
    storage_capacity,
    storage_flux,
    thermal_effusivity,
    time_to_cool,
    wbgt,
)


# ----------------------------------------------------------------- units


def test_fahrenheit_to_celsius():
    assert fahrenheit_to_celsius(212.0) == pytest.approx(100.0)
    assert fahrenheit_to_celsius(32.0) == pytest.approx(0.0)


def test_normalize_celsius_passes_celsius_through():
    assert normalize_celsius(37.2) == pytest.approx(37.2)


def test_normalize_celsius_converts_fahrenheit():
    assert normalize_celsius(99.0) == pytest.approx(37.222, abs=1e-3)
    assert fahrenheit_to_celsius(99.0) == pytest.approx(37.222, abs=1e-3)


# ------------------------------------------------------------- radiation


def test_net_longwave_flux_zero_at_equilibrium():
    flux = net_longwave_flux(25.0, 25.0, emissivity=0.93)
    assert flux == pytest.approx(0.0, abs=1e-9)


def test_net_longwave_flux_hot_surface_loses_heat():
    flux = net_longwave_flux(60.0, 30.0, emissivity=0.93)
    assert flux > 0
    # Hand check: 0.93 * 5.67e-8 * (333.15^4 - 303.15^4)
    expected = 0.93 * 5.670374419e-8 * (333.15**4 - 303.15**4)
    assert flux == pytest.approx(expected, rel=1e-9)


def test_absorbed_solar_flux():
    assert absorbed_solar_flux(800.0, 0.10) == pytest.approx(720.0)
    assert absorbed_solar_flux(800.0, 0.65) == pytest.approx(280.0)


def test_absorbed_solar_rejects_bad_albedo():
    with pytest.raises(ValueError):
        absorbed_solar_flux(800.0, 1.5)


def test_radiative_conductance_magnitude():
    h = radiative_conductance(40.0, emissivity=0.93)
    expected = 4 * 0.93 * 5.670374419e-8 * 313.15**3
    assert h == pytest.approx(expected, rel=1e-9)
    # ~6.4 W/m2K — radiative conductance is comparable to convection.
    assert 5.0 < h < 8.0


# ---------------------------------------------------------------- budget


def test_convective_flux_newtons_law():
    assert convective_flux(40.0, 30.0, 12.0) == pytest.approx(120.0)


def test_storage_capacity_and_flux():
    cap = storage_capacity(2200.0, 920.0, 0.10)
    assert cap == pytest.approx(202400.0, rel=1e-9)
    flux = storage_flux(cap, 10.0, 1.0)
    # 202400 J/m2K * 10 K / 3600 s
    assert flux == pytest.approx(202400.0 * 10.0 / 3600.0, rel=1e-9)
    assert flux > 0


def test_energy_balance_attribution_counts_only_positive_loads():
    budget = energy_balance(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
        convective_coefficient=12.0,
    )
    assert budget.net_flux > 0
    attribution = budget.attribution()
    assert set(attribution) == {
        "solar_absorption",
        "net_longwave_retention",
        "convection_suppression",
    }
    total = sum(attribution.values())
    assert total == pytest.approx(100.0, abs=0.1)
    assert attribution["solar_absorption"] > 50.0  # solar dominates daytime


def test_energy_balance_net_flux_is_conserved():
    budget = energy_balance(
        surface_temperature_c=45.0,
        air_temperature_c=32.0,
        irradiance_w_m2=700.0,
        albedo=0.20,
        convective_coefficient=15.0,
        storage_capacity_j_m2_k=1e5,
        temperature_change_c=5.0,
        time_span_hours=2.0,
    )
    recomputed = (
        budget.absorbed_solar
        - budget.net_longwave
        - budget.convection
        - budget.storage
    )
    assert budget.net_flux == pytest.approx(recomputed, rel=1e-9)


# --------------------------------------------------------------- inertia


def test_thermal_effusivity_hand_value():
    # Water: k=0.6, rho=1000, c=4186 -> e ~ 1585
    e = thermal_effusivity(0.6, 1000.0, 4186.0)
    assert e == pytest.approx(math.sqrt(0.6 * 1000.0 * 4186.0), rel=1e-9)
    assert 1500.0 < e < 1700.0


def test_effusivity_ordering_water_vs_asphalt():
    e_water = thermal_effusivity(0.6, 1000.0, 4186.0)
    e_asphalt = thermal_effusivity(1.2, 2200.0, 920.0)
    # Water resists temperature swings better than asphalt at the surface.
    assert e_water > e_asphalt


def test_cooling_curve_exponential_decay():
    t = cooling_curve_temperature(50.0, 25.0, 2.0, 2.0)
    assert t == pytest.approx(25.0 + 25.0 * math.exp(-1.0), rel=1e-9)


def test_cooling_curve_reaches_air_temperature():
    t = cooling_curve_temperature(50.0, 25.0, 1.0, 100.0)
    assert t == pytest.approx(25.0, abs=1e-9)


def test_time_to_cool():
    t = time_to_cool(50.0, 30.0, 25.0, 2.0)
    assert t == pytest.approx(-2.0 * math.log(5.0 / 25.0), rel=1e-9)
    assert 0 < t < 10


def test_time_to_cool_unreachable_target():
    assert time_to_cool(50.0, 20.0, 25.0, 2.0) == math.inf


def test_overnight_retention_ratio():
    assert overnight_retention_ratio(3.0, 10.0) == pytest.approx(
        math.exp(-10.0 / 3.0), rel=1e-9
    )
    # Large time constant -> block stays warm; small -> cools fast.
    assert overnight_retention_ratio(50.0) > overnight_retention_ratio(1.0)


# ---------------------------------------------------------------- stress


def test_wbgt_two_term():
    assert wbgt(20.0, 35.0) == pytest.approx(0.7 * 20 + 0.3 * 35)


def test_wbgt_three_term_with_globe():
    assert wbgt(20.0, 35.0, globe_celsius=40.0) == pytest.approx(
        0.7 * 20 + 0.2 * 40 + 0.1 * 35
    )


def test_heat_stress_bands_monotonic():
    levels = [heat_stress_level(x)["level"] for x in (15, 20, 24, 27, 30, 33)]
    assert levels == ["minimal", "low", "moderate", "high", "very_high", "extreme"]


def test_exposure_risk_joins_intensity_and_duration():
    low = exposure_risk(18.0, 30.0, exceedance_hours=2.0)
    high = exposure_risk(25.0, 38.0, exceedance_hours=10.0)
    assert low["overall_risk"] == "low"
    assert high["overall_risk"] == "high"


# ------------------------------------------------------------ mitigation


def test_albedo_delta_temperature_hand_value():
    # Moderate conditions: dark asphalt (0.10) -> cool coating (0.60),
    # G = 800 W/m2 at 45 C surface.
    result = albedo_delta_temperature(
        irradiance_w_m2=800.0,
        albedo_before=0.10,
        albedo_after=0.60,
        surface_temperature_c=45.0,
    )
    # Δα·G = 400 W/m2 removed; H ≈ 4*0.93*σ*318.15^3 + 12 ≈ 18.4 W/m2K
    # Expected drop ≈ 400 / 18.4 ≈ 21.7 C (quasi-steady linear estimate)
    assert 15.0 < result["delta_temperature_c"] < 30.0
    assert result["delta_albedo"] == pytest.approx(0.5)


def test_albedo_delta_temperature_zero_change():
    result = albedo_delta_temperature(
        irradiance_w_m2=800.0,
        albedo_before=0.30,
        albedo_after=0.30,
        surface_temperature_c=45.0,
    )
    assert result["delta_temperature_c"] == 0.0


def test_shade_delta_temperature_no_shade_is_zero():
    result = shade_delta_temperature(
        irradiance_w_m2=800.0,
        albedo=0.12,
        shade_fraction=0.0,
        surface_temperature_c=45.0,
    )
    assert result["delta_temperature_c"] == 0.0


def test_shade_delta_temperature_full_tree_cover():
    result = shade_delta_temperature(
        irradiance_w_m2=800.0,
        albedo=0.12,
        shade_fraction=1.0,
        surface_temperature_c=45.0,
    )
    assert 10.0 < result["delta_temperature_c"] < 45.0


def test_materials_table_has_usable_ranges():
    for name, props in MATERIALS.items():
        assert 0.0 <= props["albedo"] <= 1.0
        assert 0.0 <= props["emissivity"] <= 1.0
        assert name