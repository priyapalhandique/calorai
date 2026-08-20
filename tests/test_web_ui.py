"""D8 — web endpoints: /api/analysis payload + /api/ask with profile."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("GITHUB_MODELS_TOKEN", None)
os.environ.pop("GITHUB_TOKEN", None)

from fastapi.testclient import TestClient

from calorai.data_source import MAX_UI_TILES
from calorai.main import app

client = TestClient(app)


def test_analysis_payload_shape():
    res = client.get("/api/analysis?district=phoenix&date=2026-08-18&hour=14&source=mock")
    assert res.status_code == 200
    d = res.json()
    assert d["source"] == "mock"
    assert d["district"]
    assert d["tile_count_total"] >= d["tile_count_shown"]
    assert 0 < len(d["tiles"]) <= MAX_UI_TILES
    assert d["heatmap"]["min_c"] <= d["heatmap"]["max_c"]
    assert d["attribution"]["solar_flux"] is not None
    assert d["thermal_wind"]["gradient_lines"]["present"] is True
    assert d["analysis"]["statistics"]["present"] is True
    assert d["analysis"]["anomaly"]["present"] is True
    assert d["response"]["misting"]["headline"]
    assert isinstance(d["alerts"], list)
    assert d["diurnal"]["hours"] == list(range(24))


def test_analysis_bad_district():
    res = client.get("/api/analysis?district=nope&source=mock")
    assert res.status_code == 400


def test_ask_profile_tldr():
    res = client.post(
        "/api/ask",
        json={
            "query": "audit phoenix",
            "source": "mock",
            "profile": {"units": "f", "intensity": "heavy", "home_district": "maryvale"},
        },
    )
    assert res.status_code == 200
    d = res.json()
    assert "°F" in d["answer_tldr"]
    assert d["trace"]
    assert d["answer"]


def test_ask_home_district_fallback():
    res = client.post(
        "/api/ask",
        json={
            "query": "how hot is it today",
            "source": "mock",
            "profile": {"home_district": "maryvale"},
        },
    )
    assert res.status_code == 200
    d = res.json()
    districts = [
        t["result"]["district"] for t in d["trace"] if t.get("result", {}).get("district")
    ]
    assert districts and all("Maryvale" in str(x) for x in districts)


def test_ui_assets_served():
    for path in ("/", "/ui/app.css", "/ui/app.js"):
        res = client.get(path)
        assert res.status_code == 200
    assert "data-theme" in client.get("/").text
    assert "starfield" in client.get("/ui/app.js").text