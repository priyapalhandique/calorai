"""Interop export tests — open GeoJSON/CSV/ZIP handoff.

Verifies the three-file package is structurally valid: GeoJSON that
parses as a FeatureCollection of Points, CSVs with the right headers
and row counts, a ZIP that round-trips, and the CLI/API paths.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from calorai.agent import AuditAgent, AuditRequest
from calorai.interop import (
    audit_table_csv,
    export_audit,
    export_zip_bytes,
    heat_tiles_geojson,
    interventions_csv,
)


@pytest.fixture(scope="module")
def audit() -> tuple[dict, object]:
    request = AuditRequest("maryvale", "2026-07-15", hour=14, data_source="mock")
    agent = AuditAgent(request)
    report = agent.run(narrate=False)
    return report, agent.fetch_snapshot()


def test_geojson_is_valid_feature_collection(audit: tuple[dict, object]) -> None:
    report, snapshot = audit
    geojson = heat_tiles_geojson(snapshot, threshold_c=30.0)
    assert geojson["type"] == "FeatureCollection"
    assert geojson["meta"]["district"] == "Maryvale, Phoenix"
    assert len(geojson["features"]) == snapshot.heatmap.n_cells
    for feature in geojson["features"][:5]:
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        lon, lat = feature["geometry"]["coordinates"]
        assert -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0
        assert "temp_c" in feature["properties"]
        assert "above_threshold_c" in feature["properties"]
        assert "is_hottest_tile" in feature["properties"]


def test_geojson_flags_hottest_tile(audit: tuple[dict, object]) -> None:
    report, snapshot = audit
    hottest = report["snapshot"]["hottest_tile"]
    geojson = heat_tiles_geojson(snapshot, threshold_c=30.0, hottest=hottest)
    flagged = [
        f for f in geojson["features"] if f["properties"]["is_hottest_tile"]
    ]
    assert len(flagged) == 1
    assert flagged[0]["properties"]["temp_c"] == report["snapshot"]["max_c"]


def test_audit_csv_has_flat_schema(audit: tuple[dict, object]) -> None:
    report, _ = audit
    rows = list(csv.DictReader(io.StringIO(audit_table_csv(report))))
    assert len(rows) == 1
    row = rows[0]
    assert row["district"] == "Maryvale, Phoenix"
    assert row["date"] == "2026-07-15"
    assert row["wbgt_c"]
    assert row["vulnerability_band"]
    assert row["facade_hottest"] in {"north", "east", "south", "west", "roof"}


def test_interventions_csv_one_row_per_intervention(audit: tuple[dict, object]) -> None:
    report, _ = audit
    rows = list(csv.DictReader(io.StringIO(interventions_csv(report))))
    assert len(rows) == len(report["interventions"])
    assert rows[0]["rank"] == "1"
    assert float(rows[0]["delta_t_c"]) == report["interventions"][0]["delta_t_c"]


def test_export_audit_writes_three_files(audit: tuple[dict, object], tmp_path: Path) -> None:
    report, snapshot = audit
    paths = export_audit(report, snapshot, 30.0, tmp_path)
    assert len(paths) == 3
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
    assert any(p.suffix == ".geojson" for p in paths)
    assert any(p.name.endswith("_audit.csv") for p in paths)
    assert any(p.name.endswith("_interventions.csv") for p in paths)


def test_export_zip_round_trips(audit: tuple[dict, object]) -> None:
    report, snapshot = audit
    raw = export_zip_bytes(report, snapshot, 30.0)
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        assert len(names) == 3
        tiles = json.loads(zf.read([n for n in names if n.endswith("_tiles.geojson")][0]))
        assert tiles["type"] == "FeatureCollection"
        assert len(tiles["features"]) == snapshot.heatmap.n_cells


def test_new_subdivision_districts_are_mock_auditable() -> None:
    for key in ("maryvale", "vegas-strip", "east-harlem"):
        report = AuditAgent(
            AuditRequest(key, "2026-07-15", hour=14, data_source="mock")
        ).run(narrate=False)
        assert report["snapshot"]["n_cells"] > 0
        assert report["exposure"]["wbgt_c"] > 0
