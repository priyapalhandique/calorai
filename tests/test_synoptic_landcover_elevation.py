"""N5: elevation, landcover, synoptic — cached-only smoke checks."""
import json

from calorai.agent import AuditAgent, AuditRequest
from calorai.analyst.landcover import landcover_block
from calorai.analyst.synoptic import synoptic_block
from calorai.data_source import DISTRICTS, District


def test_elevation_lapse_present_and_sea_level():
    for district in ("phoenix", "san-jose", "manhattan"):
        report = AuditAgent(AuditRequest(district=district, date="2026-08-18")).run(narrate=False)
        ev = report["elevation"]
        assert ev["elevation_m"] == DISTRICTS[district].elevation_m
        # ISA 6.5 K/km
        assert ev["lapse_correction_c"] == round(ev["elevation_m"] * 0.0065, 2)
        assert ev["air_sea_level_c"] == round(ev["air_raw_c"] + ev["lapse_correction_c"], 2)
        # vegas highest
        assert DISTRICTS["vegas-strip"].elevation_m == 620.0


def test_elevation_lapse_zero_and_vegas_strip_delta(monkeypatch):
    monkeypatch.setitem(
        DISTRICTS,
        "sea-level-test",
        District(
            name="Sea Level Test",
            lat=33.0,
            lon=-112.0,
            base_mean_c=30.0,
            base_amplitude_c=5.0,
            heat_island_c=2.0,
            albedo=0.2,
            humidity_base_pct=45.0,
            elevation_m=0.0,
        ),
    )
    sea = AuditAgent(
        AuditRequest(district="sea-level-test", date="2026-08-18", data_source="mock")
    ).run(narrate=False)["elevation"]
    assert sea["elevation_m"] == 0
    assert sea["lapse_correction_c"] == 0.0
    assert sea["air_sea_level_c"] == sea["air_raw_c"]

    vegas = AuditAgent(
        AuditRequest(district="vegas-strip", date="2026-08-18", data_source="mock")
    ).run(narrate=False)["elevation"]
    assert vegas["elevation_m"] == 620
    assert vegas["lapse_correction_c"] == 4.03
    assert vegas["air_sea_level_c"] == round(vegas["air_raw_c"] + 4.03, 2)


def test_landcover_san_jose_present_and_phoenix_absent():
    sj = landcover_block("san-jose")
    assert sj["present"] is True
    assert 0 <= sj["svf_sky_pct"] <= 100
    assert sj["satellite"]["green_pct"] >= 0

    phx = landcover_block("phoenix")
    assert phx["present"] is False
    assert "san-jose" in phx["available_parcels"]


def test_synoptic_from_mock_audit():
    report = AuditAgent(AuditRequest(district="phoenix", date="2026-08-18")).run(narrate=False)
    syn = report["synoptic"]
    assert syn["present"] is True
    assert syn["fire_band"] in ("low", "moderate", "high")
    assert syn["heat_wave_band"] in ("low", "moderate", "high")
    assert "caveat" in syn


def test_synoptic_standalone_with_none():
    out = synoptic_block(None, None, None, None, None, threshold_c=30.0)
    assert out["present"] is False
    assert out["reason"] == "no diurnal apparent series"


def test_synoptic_missing_hours_break_stretch_and_skip_none_humidity():
    out = synoptic_block(
        apparent_c=[31.0, 31.5, None, 32.0, 32.5],
        humidity_pct=[20.0, None, 15.0, 10.0, None],
        solar_w_m2=[850.0, 900.0, 875.0, 910.0, 920.0],
        cloud_cover_pct=[5.0, 10.0, 15.0, 20.0, 25.0],
        wbgt_c=27.0,
        threshold_c=30.0,
    )
    assert out["present"] is True
    assert out["longest_hot_stretch_hours"] == 2
    assert out["heat_wave_day"] is False
    assert len(out["vpd_series_kpa"]) == 2


def test_validate_live_main_writes_error_rows(monkeypatch, tmp_path, capsys):
    from scripts import validate_live

    out_path = tmp_path / "validation_live.json"
    monkeypatch.setattr(validate_live, "DISTRICTS", ["phoenix"])
    monkeypatch.setattr(validate_live, "OUT", out_path)

    def fail_validation(name, date):
        raise RuntimeError(f"missing cache for {name} {date}")

    monkeypatch.setattr(validate_live, "validate_district", fail_validation)
    validate_live.main()

    rows = json.loads(out_path.read_text(encoding="utf-8"))
    assert rows == [
        {
            "district": "phoenix",
            "error": "RuntimeError: missing cache for phoenix 2024-07-15",
        }
    ]
    stdout = capsys.readouterr().out
    assert "wrote" in stdout
    assert "phoenix    ERROR RuntimeError: missing cache for phoenix 2024-07-15" in stdout
