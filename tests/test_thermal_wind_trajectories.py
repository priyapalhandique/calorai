"""N2 — thermal-wind gradient-line trajectories over the tile field."""

import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("GITHUB_MODELS_TOKEN", None)
os.environ.pop("GITHUB_TOKEN", None)

from calorai.agent import AuditAgent, AuditRequest
from calorai.physics.thermal_wind import (
    _TemperatureField,
    _trace_line,
    gradient_line_field,
    temperature_gradient_deg,
)


def _monotonic_tiles(n: int = 25, slope: float = 0.4) -> list[dict]:
    """Temperature rising eastward: hot core on the east rim."""
    return [
        {"lat": 33.44 + 0.001 * i, "lon": -112.07 + 0.001 * j, "value": 40.0 + slope * j}
        for i in range(n)
        for j in range(n)
    ]


def _radial_tiles(n: int = 15) -> list[dict]:
    """Hot core at the centre: concentric temperature field."""
    c = (33.44, -112.07)
    return [
        {
            "lat": c[0] + 0.001 * (i - n // 2),
            "lon": c[1] + 0.001 * (j - n // 2),
            "value": 50.0 - 1.2 * math.hypot(i - n // 2, j - n // 2),
        }
        for i in range(n)
        for j in range(n)
    ]


def test_field_idw_regular_grid():
    f = _TemperatureField(_monotonic_tiles())
    assert f.field().shape == (f.n_lat, f.n_lon)
    assert f.cell_km > 0.0
    # grid covers the tile bounding box
    assert f.lat_min <= min(t["lat"] for t in _monotonic_tiles())


def test_grad_direction_east():
    f = _TemperatureField(_monotonic_tiles())
    i, j = f.index_of(33.44, -112.069)
    ge, gn = f.grad_at(i, j)
    assert ge > 0.0  # temperature rises eastward
    assert abs(gn) < 0.5 * ge  # north gradient negligible after smoothing


def test_trace_converges_to_core():
    gl = gradient_line_field(_monotonic_tiles(), n_lines=4, steps=15)
    assert gl["present"] is True
    assert gl["n_lines"] == 4
    reached = [ln for ln in gl["lines"] if ln["termination"] == "reached core"]
    assert reached, gl["terminations"]
    for ln in reached:
        assert ln["length_km"] > 0.0
        # eastward travel: lon strictly increases toward the core
        lons = [p[1] for p in ln["path"]]
        assert lons[-1] > lons[0]


def test_radial_field_lines_terminate_at_core():
    gl = gradient_line_field(_radial_tiles(), n_lines=6)
    assert gl["present"] is True
    for ln in gl["lines"]:
        assert ln["termination"] == "reached core"
    core = gl["core"]
    # core is at the centre of the field
    assert abs(core["lat"] - 33.44) < 0.01
    assert abs(core["lon"] + 112.07) < 0.01
    assert core["temp_c"] > 49.0


def test_flat_field_stalls():
    tiles = [{"lat": 33.44 + 0.001 * i, "lon": -112.07 + 0.001 * j, "value": 41.0}
             for i in range(10) for j in range(10)]
    gl = gradient_line_field(tiles, n_lines=4)
    assert gl["present"] is True
    assert all(ln["termination"] == "stalled (flat field)" for ln in gl["lines"])


def test_paths_within_bounds():
    tiles = _radial_tiles()
    gl = gradient_line_field(tiles)
    lat_lo = min(t["lat"] for t in tiles)
    lat_hi = max(t["lat"] for t in tiles)
    lon_lo = min(t["lon"] for t in tiles)
    lon_hi = max(t["lon"] for t in tiles)
    for ln in gl["lines"]:
        for lat, lon in ln["path"]:
            assert lat_lo - 1e-4 <= lat <= lat_hi + 1e-4
            assert lon_lo - 1e-4 <= lon <= lon_hi + 1e-4


def test_deterministic():
    a = gradient_line_field(_monotonic_tiles())
    b = gradient_line_field(_monotonic_tiles())
    assert a == b


def test_terminations_exhausted_capped():
    tiles = _monotonic_tiles(n=15)
    gl = gradient_line_field(tiles, steps=60)
    for ln in gl["lines"]:
        assert len(ln["path"]) <= 61
    counts = gl["terminations"]
    assert sum(counts.values()) == gl["n_lines"]


def test_trace_line_rk4_moves():
    f = _TemperatureField(_monotonic_tiles())
    ln = _trace_line(f, (33.44, -112.069), steps=10, step_m=250.0)
    assert 1 < len(ln["path"]) <= 11
    assert ln["length_km"] > 0.0
    lons = [p[1] for p in ln["path"]]
    assert lons[-1] > lons[0]  # steps move eastward toward the core


def test_gradient_lines_in_report():
    report = AuditAgent(
        AuditRequest(district="phoenix", date="2026-08-18", hour=14)
    ).run(narrate=False)
    gl = report["thermal_wind"]["gradient_lines"]
    assert gl["present"] is True
    assert gl["n_lines"] >= 1
    assert isinstance(gl["terminations"], dict)
    assert "core" in gl and "temp_c" in gl["core"]


def test_gradient_lines_empty_tiles():
    assert gradient_line_field([]) == {"present": False}


def test_gradient_deg_unchanged():
    tiles = _monotonic_tiles()
    assert temperature_gradient_deg(tiles)["b"] > 0.0