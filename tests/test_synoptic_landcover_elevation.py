"""N5: elevation, landcover, synoptic — cached-only smoke checks."""
from calorai.agent import AuditAgent, AuditRequest
from calorai.analyst.landcover import landcover_block
from calorai.analyst.synoptic import synoptic_block
from calorai.data_source import DISTRICTS


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
