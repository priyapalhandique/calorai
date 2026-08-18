"""Tier A physics tests — wind convection, solar geometry, Brutsaert sky
model, balance closure, globe-WBGT, humidex and exposure dose."""

import math

import pytest

from calorai.physics import (
    clear_sky_emissivity,
    closure_analysis,
    convective_coefficient_from_wind,
    energy_balance,
    exposure_risk,
    globe_temperature_c,
    heat_exposure_dose,
    hour_angle_degrees,
    humidex,
    implied_convective_coefficient,
    sky_temperature_c,
    solar_declination_degrees,
    solar_elevation_degrees,
    tilted_incident_irradiance,
    wbgt,
)


# ------------------------------------------------------- wind convection


def test_mcadams_wind_coefficient():
    assert convective_coefficient_from_wind(0.0) == pytest.approx(5.7)
    # 5.7 + 3.8·u = 12 exactly at u = 1.66 m/s — the calm-street default.
    assert convective_coefficient_from_wind(1.66) == pytest.approx(12.0, abs=0.1)
    assert convective_coefficient_from_wind(10.0) == pytest.approx(43.7)
    assert convective_coefficient_from_wind(0.5) < convective_coefficient_from_wind(5.0)


def test_wind_coefficient_floor_and_validation():
    assert convective_coefficient_from_wind(0.01) >= 5.0
    with pytest.raises(ValueError):
        convective_coefficient_from_wind(-1.0)


# -------------------------------------------------------- solar geometry


def test_declination_equinox_and_solstices():
    # Day 80 (Mar 21) ≈ 0°; day 172 (Jun 21) ≈ +23.44°; day 355 ≈ −23.44°.
    assert abs(solar_declination_degrees(80)) < 1.0
    assert solar_declination_degrees(172) == pytest.approx(23.44, abs=0.1)
    assert solar_declination_degrees(355) == pytest.approx(-23.44, abs=0.1)


def test_hour_angle_phoenix_solar_noon():
    # Phoenix λ=−112.074, UTC−7: solar noon lands at 12:28 local
    # (H = 15·(12−12) + (−105 + 112.074) = +7.07° = +28 min).
    assert hour_angle_degrees(12.0, -7.0, -112.074) == pytest.approx(7.074, abs=0.01)
    assert hour_angle_degrees(14.0, -7.0, -112.074) == pytest.approx(37.074, abs=0.01)


def test_elevation_zenith_at_equator_equinox_noon():
    assert solar_elevation_degrees(0.0, 0.0, 0.0) == pytest.approx(90.0, abs=1e-6)


def test_elevation_phoenix_summer_noon_high_sky():
    elev = solar_elevation_degrees(33.4484, 23.44, 7.074)
    assert 77.5 < elev < 79.0  # July midday Phoenix: high but not zenith


def test_elevation_negative_at_night():
    assert solar_elevation_degrees(33.4484, 23.44, 180.0) < 0.0


def test_tilted_horizontal_returns_ghi():
    result = tilted_incident_irradiance(800.0, 60.0, tilt_deg=0.0)
    assert result["incident_w_m2"] == pytest.approx(800.0, abs=0.5)
    assert result["reflected_w_m2"] == pytest.approx(0.0, abs=1e-6)


def test_tilted_vertical_facade_beam_and_shaded_face():
    sunny = tilted_incident_irradiance(
        800.0, 60.0, tilt_deg=90.0, surface_azimuth_deg=180.0,
        solar_azimuth_deg=180.0, ground_albedo=0.2,
    )
    shaded = tilted_incident_irradiance(
        800.0, 60.0, tilt_deg=90.0, surface_azimuth_deg=0.0,
        solar_azimuth_deg=180.0, ground_albedo=0.2,
    )
    assert sunny["beam_w_m2"] > 0.0  # sun-facing facade catches the beam
    assert sunny["incident_w_m2"] > shaded["incident_w_m2"]
    assert shaded["beam_w_m2"] == pytest.approx(0.0, abs=1e-6)  # shaded face
    assert shaded["incident_w_m2"] > 0.0  # still diffuse + ground-reflected


# ------------------------------------------------------------ sky model


def test_clear_sky_emissivity_brutsaert_hand_value():
    # 30 °C, 50% RH: e_a = 6.112·exp(17.62·30/273.12)·0.5 ≈ 21.16 hPa;
    # ε = 1.24·(21.16/303.15)^(1/7) ≈ 0.848.
    assert clear_sky_emissivity(30.0, 50.0) == pytest.approx(0.848, abs=0.01)


def test_sky_temperature_well_below_air_clear_night():
    sky = sky_temperature_c(30.0, 25.0, cloud_fraction=0.0)
    assert sky == pytest.approx(10.6, abs=0.5)
    assert sky < 30.0 - 10.0  # clear sky is the real longwave sink


def test_dry_desert_sky_colder_than_humid():
    dry = sky_temperature_c(40.0, 10.0, 0.0)
    humid = sky_temperature_c(40.0, 80.0, 0.0)
    assert dry < humid < 40.0


def test_overcast_sky_pushes_toward_air_temperature():
    assert sky_temperature_c(30.0, 25.0, cloud_fraction=1.0) == pytest.approx(30.0, abs=1e-9)
    with pytest.raises(ValueError):
        sky_temperature_c(30.0, 25.0, cloud_fraction=1.5)


def test_sky_emissivity_stays_in_unit_range():
    for rh in (5.0, 25.0, 50.0, 80.0, 95.0):
        for t in (0.0, 20.0, 45.0):
            # Very dry, cold air can dip below 0.5 (Brutsaert) — still valid.
            assert 0.3 < clear_sky_emissivity(t, rh) <= 1.0


# ---------------------------------------------------- balance closure


def test_implied_hc_matches_used_coefficient():
    # implied h_c recovers the h_c that closes the balance exactly:
    # (Q_sol − Q_lw − Q_store)/(T_s − T_air). With no storage terms the
    # closure value falls out of the radiative + solar fluxes alone.
    h_implied = implied_convective_coefficient(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
    )
    assert 20.0 < h_implied < 35.0  # radiant + convective load, 22 K gradient


def test_closure_analysis_closed_when_layers_agree():
    h_implied = implied_convective_coefficient(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
    )
    report = closure_analysis(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
        convective_coefficient=h_implied,
    )
    assert report["closed"] is True
    assert abs(report["residual_w_m2"]) < 1e-6
    assert report["implied_convective_coefficient"] == pytest.approx(h_implied, abs=0.06)


def test_closure_analysis_flags_open_balance():
    report = closure_analysis(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
        convective_coefficient=12.0,  # far from the implied ~27
    )
    assert report["closed"] is False
    assert report["residual_w_m2"] > 150.0


def test_implied_hc_infinite_without_temperature_gradient():
    assert (
        implied_convective_coefficient(
            surface_temperature_c=33.0,
            air_temperature_c=33.0,
            irradiance_w_m2=850.0,
            albedo=0.12,
        )
        == math.inf
    )


def test_energy_balance_accepts_sky_temperature():
    with_sky = energy_balance(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
        sky_temperature_c=12.0,
    )
    without_sky = energy_balance(
        surface_temperature_c=55.0,
        air_temperature_c=33.0,
        irradiance_w_m2=850.0,
        albedo=0.12,
    )
    # A cold sky pulls more longwave out of the surface: less retention.
    assert with_sky.net_longwave > without_sky.net_longwave


# ----------------------------------------------------------- stress aids


def test_globe_temperature_from_solar():
    assert globe_temperature_c(40.0, 800.0) == pytest.approx(64.0)
    # Wind deflates the globe excess: 24 · (1 − 0.15·2) = 16.8.
    assert globe_temperature_c(40.0, 800.0, wind_speed_m_s=2.0) == pytest.approx(56.8)


def test_wbgt_estimates_globe_from_solar_load():
    result = wbgt(23.7, 40.7, irradiance_w_m2=800.0)
    expected = 0.7 * 23.7 + 0.2 * (40.7 + 24.0) + 0.1 * 40.7
    assert result == pytest.approx(expected)
    assert result > wbgt(23.7, 40.7)  # sun exposure raises outdoor WBGT


def test_wbgt_two_term_fallback_unchanged():
    assert wbgt(20.0, 35.0) == pytest.approx(0.7 * 20 + 0.3 * 35)


def test_humidex_hand_value():
    # Phoenix midday: 40.7 °C, 22.9% RH → e ≈ 17.5 hPa → humidex ≈ 44.9.
    assert humidex(40.7, 22.9) == pytest.approx(44.87, abs=0.1)


def test_humidex_never_below_air_temperature():
    assert humidex(10.0, 5.0) == 10.0


def test_heat_exposure_dose():
    dose = heat_exposure_dose(33.6, 8.0, threshold_celsius=31.0)
    assert dose["wbgt_hours"] == pytest.approx(268.8)
    assert dose["above_threshold_c_hours"] == pytest.approx(20.8)
    assert heat_exposure_dose(33.6, 8.0, None)["above_threshold_c_hours"] is None


def test_exposure_risk_includes_globe_wbgt_and_dose():
    risk = exposure_risk(
        23.7, 40.7, exceedance_hours=10.0,
        threshold_celsius=30.0, irradiance_w_m2=800.0,
    )
    assert risk["wbgt_c"] == pytest.approx(
        0.7 * 23.7 + 0.2 * 64.7 + 0.1 * 40.7, abs=0.01
    )
    assert risk["overall_risk"] == "high"
    assert "dose" in risk