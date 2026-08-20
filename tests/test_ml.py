"""D6 ML layer tests — forecast surrogate + anomaly detector.

The surrogate test trains on a small sweep (fast in CI) and checks the
physics is reproduced on held-out rows; the anomaly tests use a
synthetic field with an implanted hot tile.
"""

import numpy as np
import pytest

from calorai.ml.anomaly import detect_anomalies, spatial_local_residual
from calorai.ml.forecast import (
    FEATURES,
    forecast_skin_temp,
    generate_synthetic_data,
    train_forecast,
    validate_vs_real,
)


def test_synthetic_data_shape_and_ranges():
    X, y = generate_synthetic_data(n_rows=2_000, seed=1)
    assert X.shape == (2_000, len(FEATURES))
    assert y.shape == (2_000,)
    assert np.all(np.isfinite(X)) and np.all(np.isfinite(y))
    assert y.min() > -30.0 and y.max() < 120.0


def test_surrogate_reproduces_physics_on_holdout(tmp_path):
    # Small CI train (3000 rows) must still reproduce the physics within
    # a couple of degrees; the committed production artifact (100k rows)
    # reaches MAE 0.75 °C / R² 0.9966 (see data/models/forecast_v1.meta.json).
    meta = train_forecast(n_rows=3_000, out_path=tmp_path / "forecast.joblib", report=False)
    assert meta["holdout_mae_c"] < 2.5
    assert meta["holdout_rmse_c"] < 4.0
    assert meta["r2"] > 0.97
    assert meta["improvement_pct"] > 80.0
    assert (tmp_path / "forecast.joblib").exists()
    assert (tmp_path / "forecast.meta.json").exists()


def test_forecast_skin_temp_sane_range(tmp_path):
    train_forecast(n_rows=2_000, out_path=tmp_path / "f.joblib", report=False)
    t = forecast_skin_temp(
        {
            "irradiance_w_m2": 900.0,
            "albedo": 0.12,
            "emissivity": 0.93,
            "convective_coefficient": 12.0,
            "air_temperature_c": 40.0,
            "radiative_environment_c": 35.0,
            "storage_flux_w_m2": 120.0,
            "latent_flux_w_m2": 50.0,
        },
        model=None,
    )
    # Hot, dark, calm desert conditions -> well above air temperature.
    assert 50.0 < t < 90.0


def test_validate_vs_real_reports_all_metrics(tmp_path):
    train_forecast(n_rows=2_000, out_path=tmp_path / "f.joblib", report=False)
    from calorai.ml.forecast import load_forecast

    model = load_forecast(tmp_path / "f.joblib")
    series = []
    for h in range(24):
        row = {
            "irradiance_w_m2": 100.0 * h,
            "albedo": 0.12,
            "emissivity": 0.93,
            "convective_coefficient": 12.0,
            "air_temperature_c": 30.0 + 5.0 * np.sin(2 * np.pi * (h - 8) / 24),
            "radiative_environment_c": 28.0,
            "storage_flux_w_m2": 100.0,
            "latent_flux_w_m2": 30.0,
            "observed_c": 40.0 + 3.0 * np.sin(2 * np.pi * (h - 12) / 24),
        }
        series.append(row)
    out = validate_vs_real(series, model=model)
    assert out["present"] is True
    assert out["n_hours"] == 24
    assert 0.0 <= out["surrogate_mae_c"] < 60.0
    assert "layer_offset_c" in out


def test_anomaly_detects_implanted_hot_tile():
    # Uniform field with one tile 6 K hotter than its surroundings.
    tiles = [
        {"lat": 33.0 + 0.001 * i, "lon": -112.0 + 0.001 * j, "value": 46.0}
        for i in range(10) for j in range(10)
    ]
    tiles[45]["value"] = 52.0
    out = detect_anomalies(tiles, equilibrium_c=47.0)
    assert out["present"] is True
    assert out["n_flagged"] >= 1
    assert any(
        abs(t["lat"] - tiles[45]["lat"]) < 1e-9 and abs(t["lon"] - tiles[45]["lon"]) < 1e-9
        for t in out["tiles"]
    )
    assert out["advisory"]
    assert "flags" in out["method"].lower() or "anomalies" in out["method"].lower()


def test_spatial_residual_surface_consistency():
    tiles = [
        {"lat": 33.0 + 0.001 * i, "lon": -112.0 + 0.001 * j, "value": 46.0}
        for i in range(8) for j in range(8)
    ]
    res = spatial_local_residual(tiles)
    assert len(res) == 64
    assert all(abs(r) < 1e-6 for r in res)  # uniform field -> zero residual


def test_agent_report_has_anomaly_block():
    from calorai.agent import AuditAgent, AuditRequest

    report = AuditAgent(
        AuditRequest(district="phoenix", date="2026-08-18", hour=14, data_source="mock")
    ).run(narrate=False)
    anomaly = report["analysis"]["anomaly"]
    assert anomaly["present"] is True
    assert anomaly["n_tiles"] == 81
    assert 0 <= anomaly["n_flagged"] <= anomaly["n_tiles"]
    assert "IsolationForest" in anomaly["method"]