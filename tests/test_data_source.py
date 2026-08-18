"""Data-source tests — mock determinism + district catalog sanity."""

import pytest

from calorai.data_source import (
    DISTRICTS,
    LiveFortyGuardSource,
    MockDataSource,
    get_district,
    resolve_source,
)


def test_district_catalog():
    for name, district in DISTRICTS.items():
        assert district.lat != 0.0
        assert -125 <= district.lon <= -65  # US only per API coverage
        assert 20.0 < district.base_mean_c < 45.0
        assert 0.0 <= district.albedo <= 1.0


def test_get_district_normalizes_names():
    assert get_district("Phoenix") is DISTRICTS["phoenix"]
    assert get_district("San-Jose") is DISTRICTS["san-jose"]


def test_get_district_unknown_raises():
    with pytest.raises(ValueError):
        get_district("tokyo")


def test_mock_tcm_layer_shape():
    source = MockDataSource()
    layer = source.get_heatmap("phoenix", "2026-08-18", hour=14)
    assert layer.analytic_type == "tcm"
    assert layer.units == "celsius"
    assert layer.n_cells == len(layer.tiles) == 81
    assert 0.0 < layer.min <= layer.mean <= layer.max < 60.0
    assert all("lat" in t and "lon" in t and "value" in t for t in layer.tiles)


def test_mock_diurnal_peak_in_afternoon():
    source = MockDataSource()
    morning = source.get_heatmap("austin", "2026-08-18", hour=10)
    afternoon = source.get_heatmap("austin", "2026-08-18", hour=15)
    assert afternoon.mean > morning.mean


def test_mock_exceedance_counts_units_hours():
    source = MockDataSource()
    layer = source.get_heatmap("phoenix", "2026-08-18", hour=14, analytic_type="exceedance", threshold=35.0)
    assert layer.units == "hour"
    assert 0.0 <= layer.min <= layer.max <= 24.0
    # Phoenix in August: most tiles cross 35 C at least once.
    assert layer.max >= 1.0


def test_mock_persistence_runs_bounded():
    source = MockDataSource()
    layer = source.get_heatmap("phoenix", "2026-08-18", analytic_type="persistence", threshold=35.0)
    assert layer.units == "hour"
    assert layer.max <= 24.0


def test_mock_env_series_plausible():
    source = MockDataSource()
    env = source.get_environmental_parameters("phoenix", "2026-08-18")
    assert len(env.hours) == 24
    assert len(env.apparent_c) == 24
    assert len(env.wet_bulb_c) == 24
    assert max(env.solar_w_m2) > 700.0
    assert min(env.solar_w_m2) == 0.0
    # Wet bulb is never above dry bulb (apparent).
    assert all(w <= a + 1e-6 for w, a in zip(env.wet_bulb_c, env.apparent_c))
    assert 0.0 <= min(env.humidity_pct) <= max(env.humidity_pct) <= 100.0


def test_mock_snapshot_assembles_layers():
    source = MockDataSource()
    snapshot = source.get_district_snapshot("manhattan", "2026-08-18")
    assert snapshot.heatmap is not None
    assert snapshot.exceedance is not None
    assert snapshot.persistence is not None
    assert snapshot.env is not None
    assert snapshot.source == "mock"
    payload = snapshot.as_dict()
    assert payload["name"] == "Lower Manhattan, NYC"
    assert "sample_tiles" in payload["heatmap"]
    assert payload["warnings"]


def test_mock_deterministic():
    a = MockDataSource().get_district_snapshot("san-jose", "2026-08-18")
    b = MockDataSource().get_district_snapshot("san-jose", "2026-08-18")
    assert a.as_dict() == b.as_dict()


def test_resolve_source_mock_forced():
    source, mode = resolve_source("mock")
    assert mode == "mock"
    assert isinstance(source, MockDataSource)


def test_parse_env_live_schema():
    """Regression fixture shaped exactly like a real environmental_parameters
    completion: locations[].parameters is a flat name -> 24-h series dict,
    solar_irradiance carries only a single clear-sky ghi aggregate, and some
    series contain None placeholders (e.g. premium-only co2_ppm)."""
    hours = list(range(24))
    apparent = [32.0, 31.7, 32.2, 33.1, 34.6, 36.8, 38.9, 40.1, 40.6,
                40.7, 40.9, 41.0, 40.8, 40.6, 40.1, 39.4, 38.6, 37.5,
                36.3, 35.2, 34.1, 33.2, 32.6, 32.1]
    payload = {
        "metadata": {
            "timezone": "America/Phoenix",
            "timezone_offset_hours": -7,
            "time_range": {"start": "2024-07-15T00:00:00-07:00",
                           "end": "2024-07-15T23:00:00-07:00",
                           "interval": "1h", "count": 24},
            "timestamps": [f"2024-07-15T{h:02d}:00:00-07:00" for h in hours],
        },
        "locations": [{
            "lat": 33.4484, "lon": -112.0740, "elevation": 331.2,
            "temperature": 39.68,
            "parameters": {
                "apparent_temperature_celsius": apparent,
                "wet_bulb_temperature_celsius": [a - 17.0 for a in apparent],
                "relative_humidity_percent": [22.9] * 24,
                "co2_ppm": [None] * 24,
                "heat_index_celsius": apparent,
            },
            "solar_irradiance": {"clear_sky": {"ghi": 576.92, "dni": 691.43,
                                               "dhi": 85.61},
                                 "description": "clear-sky aggregate"},
        }],
    }
    env = LiveFortyGuardSource._parse_env(payload)
    assert len(env.hours) == 24
    assert env.apparent_c[14] == pytest.approx(40.1)
    assert len(env.wet_bulb_c) == 24
    assert env.humidity_pct[0] == pytest.approx(22.9)
    assert env.co2_ppm == []  # all-None series dropped, not crashed
    assert env.solar_w_m2[12] == pytest.approx(576.92, rel=1e-3)  # peak at solar noon
    assert env.solar_w_m2[6] == 0.0
    assert env.solar_w_m2[19] == 0.0