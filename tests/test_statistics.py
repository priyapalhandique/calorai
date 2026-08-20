"""D8 — statistical layer over the tile field."""

import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("GITHUB_MODELS_TOKEN", None)
os.environ.pop("GITHUB_TOKEN", None)

import numpy as np

from calorai.agent import AuditAgent, AuditRequest
from calorai.analyst.statistics import (
    describe,
    fig_histogram_normal,
    fig_hourly_boxplot,
    fig_radial_uhi,
    hourly_reconstruction,
    normality,
    outliers,
    tile_statistics_block,
    tile_values,
)

GRID_TILES = [
    {"lat": 33.44 + 0.001 * i, "lon": -112.07 + 0.001 * j, "value": 42.0 + 0.5 * (i + j)}
    for i in range(15)
    for j in range(15)
]


@pytest.fixture
def report():
    return AuditAgent(
        AuditRequest(district="phoenix", date="2026-08-18", hour=14)
    ).run(narrate=False)


def test_values_flat():
    assert tile_values([]).size == 0
    v = tile_values(GRID_TILES)
    assert v.size == 225
    assert abs(v.mean() - np.mean([t["value"] for t in GRID_TILES])) < 1e-9


def test_describe_math():
    d = describe(np.array([10.0, 20.0, 30.0, 40.0]))
    assert d["min_c"] == 10.0
    assert d["max_c"] == 40.0
    assert d["mean_c"] == 25.0
    assert d["median_c"] == 25.0
    assert d["p25_c"] == 17.5
    assert d["p75_c"] == 32.5
    assert d["iqr_c"] == 15.0
    assert d["n"] == 4
    assert d["std_c"] == pytest.approx(11.18, abs=0.01)


def test_describe_empty():
    assert describe(np.array([])) == {}


def test_outliers_tukey_fences():
    # 3.5 is beyond Q3 + 1.5*IQR of a 0..10 ramp; 11.5 likewise
    values = np.array(list(range(11)) + [100.0, -100.0], dtype=float)
    o = outliers(values)
    assert o["count"] == 2
    assert o["low_fence_c"] < 0.0
    assert o["high_fence_c"] < 100.0
    assert set(o["values_c"]) == {-100.0, 100.0}


def test_outliers_small_sample():
    o = outliers(np.array([1.0, 2.0, 3.0]))
    assert o["count"] == 0


def test_normality_gaussian():
    rng = np.random.default_rng(7)
    n = normality(rng.normal(40.0, 2.0, 300))
    assert n["test"] == "shapiro-wilk"
    assert n["normal"] is True
    assert n["p_value"] > 0.05


def test_normality_skewed():
    n = normality(np.random.default_rng(3).exponential(2.0, 300))
    assert n["normal"] is False
    assert n["p_value"] <= 0.05


def test_normality_capped_sample_deterministic():
    big = np.random.default_rng(1).normal(30.0, 1.0, 20000)
    n1, n2 = normality(big), normality(big)
    assert n1["sampled"] is True
    assert n1 == n2


def test_radial_uhi_monotonic_core():
    # core hotter than rim -> positive slope, near-unity R2
    tiles = [
        {"lat": 33.0 + 0.001 * i, "lon": -112.0, "value": 50.0 - 2.0 * abs(i - 10)}
        for i in range(21)
    ]
    b = tile_statistics_block(tiles)
    uhi = b["radial_uhi"]
    assert uhi["slope_c_per_km"] < -10.0
    assert uhi["r2"] > 0.95


def test_radial_uhi_flat_field():
    tiles = [{"lat": 33.0 + 0.001 * i, "lon": -112.0, "value": 40.0} for i in range(11)]
    uhi = tile_statistics_block(tiles)["radial_uhi"]
    assert abs(uhi["slope_c_per_km"]) < 1e-6
    assert uhi["r2"] >= 0.0


def test_hourly_reconstruction_shape_preserving():
    tiles = [{"lat": 33.0, "lon": -112.0, "value": 45.0 + i} for i in range(10)]
    apparent = [30.0 + 10.0 * math.sin(math.pi * (h - 8) / 14.0) for h in range(24)]
    hourly = hourly_reconstruction(tiles, apparent, audit_hour=14)
    assert len(hourly) == 24
    h14 = hourly[14]
    assert h14["median_c"] == pytest.approx(np.median([45.0 + i for i in range(10)]), abs=0.01)
    spread14 = h14["q3_c"] - h14["q1_c"]
    spread0 = hourly[0]["q3_c"] - hourly[0]["q1_c"]
    assert spread0 == pytest.approx(spread14, abs=0.01)  # shape preserved


def test_hourly_reconstruction_missing_series():
    hourly = hourly_reconstruction(GRID_TILES, None, 14)
    assert hourly == [None] * 24


def test_block_in_report(report):
    stats = report["analysis"]["statistics"]
    assert stats["present"] is True
    assert stats["n_tiles"] >= 50
    s = stats["summary"]
    assert s["p05_c"] <= s["median_c"] <= s["p95_c"]
    assert s["std_c"] >= 0.0
    assert stats["histogram"]["n"] == stats["n_tiles"]
    assert len(stats["histogram"]["bin_edges_c"]) == len(stats["histogram"]["counts"]) + 1
    assert stats["radial_profile"]["present"] is True
    assert 0.0 <= stats["radial_uhi"]["r2"] <= 1.0


def test_block_absent_for_empty():
    b = tile_statistics_block([])
    assert b == {"present": False}


def test_hourly_spread_in_report(report):
    hourly = report["analysis"]["statistics"]["hourly_spread"]
    assert len(hourly) == 24
    assert all(h["hour"] == h_i for h_i, h in enumerate(hourly) if h is not None)


def test_charts_build_without_error():
    import matplotlib

    matplotlib.use("Agg")
    tiles = [
        {"lat": 33.0 + 0.001 * i, "lon": -112.0 + 0.001 * j, "value": 40.0 + 0.4 * i + 0.3 * j}
        for i in range(20)
        for j in range(20)
    ]
    b = tile_statistics_block(tiles)
    for fig in (
        fig_histogram_normal(b["histogram"]),
        fig_hourly_boxplot(b["hourly_spread"]),
        fig_radial_uhi(b["radial_profile"]),
    ):
        fig.canvas.draw()
        assert fig.axes


def test_charts_tolerate_empty():
    import matplotlib

    matplotlib.use("Agg")
    for fig in (
        fig_histogram_normal({"n": 0, "bin_edges_c": [], "counts": [], "bin_width_c": 0.0}),
        fig_hourly_boxplot([None] * 24),
        fig_radial_uhi({"present": False}),
    ):
        fig.canvas.draw()
        assert fig.axes