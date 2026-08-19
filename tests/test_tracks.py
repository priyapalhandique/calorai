"""Track 2 + Track 5 tests — facade-orientation advisor (Future
Buildings & Energy), retrofit economics (degree-hours × envelope ×
COP), and the packaged vulnerability / worker-safety models (Model
Designing).

Sources: Oke, Mills, Christen & Voogt (2017) Urban Climates (facade
solar geometry, Ch. 4-5); Campbell & Norman (1998) Environmental
Biophysics (tilted-plane irradiance); OSHA-style WBGT work-rest
guidance via calorai.physics.stress.
"""

import math

import pytest

from calorai.physics.economics import (
    cooling_degree_hours,
    cooling_energy_avoided_kwh,
    retrofit_roi,
)
from calorai.physics.facade import (
    facade_heat_load_ranking,
    facade_hourly_flux_w_m2,
    facade_solar_load_kwh_m2_per_day,
)
from calorai.physics.solar import (
    clear_sky_ghi_w_m2,
    solar_azimuth_degrees,
)
from calorai.physics.vulnerability import (
    heat_vulnerability_score,
    worker_safety_alert,
)


# ------------------------------------------------------------ solar (T2 base)


def test_solar_azimuth_at_noon_is_south_in_northern_hemisphere():
    az = solar_azimuth_degrees(latitude_deg=33.4, declination_deg=20.0, hour_angle_deg=0.0)
    assert az == pytest.approx(180.0, abs=0.5)


def test_solar_azimuth_morning_east_afternoon_west():
    lat, decl = 33.4, 20.0
    morning = solar_azimuth_degrees(lat, decl, hour_angle_deg=-45.0)
    afternoon = solar_azimuth_degrees(lat, decl, hour_angle_deg=45.0)
    assert morning < 180.0 < afternoon
    assert morning == pytest.approx(360.0 - afternoon, abs=1.0)


def test_clear_sky_ghi_zero_below_horizon():
    assert clear_sky_ghi_w_m2(-5.0) == 0.0
    assert clear_sky_ghi_w_m2(45.0) == pytest.approx(1361.0 * 0.75 * math.sin(math.radians(45.0)), rel=1e-6)


# ------------------------------------------------------------- facade (T2)


def test_facade_flux_zero_at_night():
    flux = facade_hourly_flux_w_m2(
        latitude_deg=33.4, longitude_deg=-112.07, day_of_year=200,
        clock_hour=2.0, utc_offset_hours=-7.0, wall_azimuth_deg=180.0,
    )
    assert flux["incident_w_m2"] == 0.0


def test_facade_ranking_south_hottest_roof_beats_walls_at_equinox():
    ranking = facade_heat_load_ranking(
        latitude_deg=33.4, longitude_deg=-112.07, day_of_year=80, utc_offset_hours=-7.0,
    )
    by_name = {r["orientation"]: r["load_kwh_m2_per_day"] for r in ranking["ranking"]}
    assert by_name["roof"] > by_name["south"] > by_name["east"] > by_name["north"]
    assert ranking["hottest"] == "roof"
    assert ranking["coolest"] == "north"


def test_facade_ranking_north_coldest_at_equinox():
    ranking = facade_heat_load_ranking(
        latitude_deg=33.4, longitude_deg=-112.07, day_of_year=80, utc_offset_hours=-7.0,
    )
    north = next(r for r in ranking["ranking"] if r["orientation"] == "north")
    south = next(r for r in ranking["ranking"] if r["orientation"] == "south")
    # Vertical north wall: no direct beam at equinox; diffuse+reflected only.
    assert north["load_kwh_m2_per_day"] < 0.5 * south["load_kwh_m2_per_day"]


def test_facade_ranking_deep_summer_flip_south_coldest():
    # Phoenix July: sun nearly overhead — the south wall's beam incidence
    # is steep and small, and the north wall catches ENE morning sun, so
    # the classic "south is hottest" flips. Seasonality is the point.
    ranking = facade_heat_load_ranking(
        latitude_deg=33.4, longitude_deg=-112.07, day_of_year=200, utc_offset_hours=-7.0,
    )
    by_name = {r["orientation"]: r["load_kwh_m2_per_day"] for r in ranking["ranking"]}
    assert by_name["roof"] > by_name["east"] >= by_name["west"] > by_name["north"] > by_name["south"]


def test_facade_ranking_east_west_split_symmetric_peak():
    east = facade_solar_load_kwh_m2_per_day(
        33.4, -112.07, 200, -7.0, wall_azimuth_deg=90.0,
    )
    west = facade_solar_load_kwh_m2_per_day(
        33.4, -112.07, 200, -7.0, wall_azimuth_deg=270.0,
    )
    assert east["load_kwh_m2_per_day"] == pytest.approx(west["load_kwh_m2_per_day"], rel=0.05)
    assert east["peak_hour"] <= 12.0 <= west["peak_hour"]


def test_facade_wall_flux_matches_tilted_plane_model():
    flux = facade_hourly_flux_w_m2(
        latitude_deg=33.4, longitude_deg=-112.07, day_of_year=200,
        clock_hour=12.0, utc_offset_hours=-7.0, wall_azimuth_deg=180.0,
    )
    assert flux["incident_w_m2"] >= flux["diffuse_w_m2"]
    assert flux["beam_w_m2"] >= 0.0


# ---------------------------------------------------------- economics (T2)


def test_cooling_energy_scales_linearly_with_delta_t_and_dh():
    base = cooling_energy_avoided_kwh(degree_hours_c=10_000.0, delta_t_c=10.0, envelope_area_m2=400.0)
    double_dt = cooling_energy_avoided_kwh(10_000.0, 20.0, 400.0)
    double_dh = cooling_energy_avoided_kwh(20_000.0, 10.0, 400.0)
    assert double_dt == pytest.approx(2.0 * base)
    assert double_dh == pytest.approx(2.0 * base)


def test_cooling_energy_unit_check():
    # U=0.5 W/m²K, A=400 m², DH=10 000 °C·h, ΔT=10 °C, COP=3.5
    kwh = cooling_energy_avoided_kwh(10_000.0, 10.0, 400.0, u_value_w_m2_k=0.5, cop=3.5)
    assert kwh == pytest.approx(0.5 * 400.0 * 10_000.0 * 10.0 / 1000.0 / 3.5)


def test_retrofit_roi_payback_math():
    roi = retrofit_roi(
        degree_hours_c=10_000.0,
        delta_t_c=10.0,
        envelope_area_m2=400.0,
        retrofit_cost_usd=10_000.0,
        electricity_price_usd_kwh=0.15,
    )
    annual_savings = roi["annual_savings_usd"]
    assert roi["payback_years"] == pytest.approx(10_000.0 / annual_savings, rel=0.02)
    assert roi["lifespan_net_savings_usd"] == pytest.approx(
        annual_savings * 10 - 10_000.0, rel=0.02
    )


def test_retrofit_roi_zero_delta_t_never_pays_back():
    roi = retrofit_roi(10_000.0, 0.0, 400.0, retrofit_cost_usd=10_000.0)
    assert roi["annual_savings_usd"] == 0
    assert roi["payback_years"] is None


def test_cooling_degree_hours_proxy_cold_district_zero():
    assert cooling_degree_hours(base_mean_c=15.0) == 0.0
    phoenix = cooling_degree_hours(base_mean_c=36.0)
    san_jose = cooling_degree_hours(base_mean_c=26.0)
    assert phoenix > san_jose > 0.0


# -------------------------------------------------------- vulnerability (T5)


def test_vulnerability_score_bounds_and_band_ladder():
    low = heat_vulnerability_score(wbgt_c=15.0)
    high = heat_vulnerability_score(wbgt_c=40.0, exceedance_hours=12.0, above_threshold_c_hours=200.0)
    assert 0.0 <= low["score"] <= 100.0
    assert 0.0 <= high["score"] <= 100.0
    assert high["score"] > low["score"]
    assert low["band"] == "low"
    assert high["band"] in ("high", "critical")


def test_vulnerability_score_monotone_in_each_component():
    base = heat_vulnerability_score(28.0, exceedance_hours=4.0)
    more_dose = heat_vulnerability_score(28.0, exceedance_hours=4.0, above_threshold_c_hours=50.0)
    more_sensitive = heat_vulnerability_score(28.0, exceedance_hours=4.0, vulnerable_population_share=0.8)
    longer = heat_vulnerability_score(28.0, exceedance_hours=10.0)
    assert more_dose["score"] > base["score"]
    assert more_sensitive["score"] > base["score"]
    assert longer["score"] > base["score"]


def test_vulnerability_score_components_sum():
    result = heat_vulnerability_score(
        wbgt_c=32.0, exceedance_hours=6.0, above_threshold_c_hours=40.0, vulnerable_population_share=0.3
    )
    total = sum(result["components"].values())
    assert result["score"] == pytest.approx(total, abs=0.2)


def test_worker_safety_alert_intensity_adjusts_band():
    base = worker_safety_alert(wbgt_c=28.0, work_intensity="moderate")
    heavy = worker_safety_alert(wbgt_c=28.0, work_intensity="heavy")
    light = worker_safety_alert(wbgt_c=28.0, work_intensity="light")
    assert heavy["effective_wbgt_c"] == pytest.approx(29.0)
    assert light["effective_wbgt_c"] == pytest.approx(27.5)
    level_rank = {"minimal": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4, "extreme": 5}
    assert level_rank[heavy["level"]] >= level_rank[base["level"]]
    assert level_rank[light["level"]] <= level_rank[base["level"]]


def test_worker_safety_alert_rejects_bad_intensity():
    with pytest.raises(ValueError):
        worker_safety_alert(wbgt_c=30.0, work_intensity="sprinting")