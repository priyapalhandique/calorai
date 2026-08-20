"""ML layer (D6) — physics-informed forecast surrogate + anomaly detector."""

from .anomaly import detect_anomalies, spatial_local_residual
from .forecast import (
    DEFAULT_ARTIFACT,
    FEATURES,
    forecast_skin_temp,
    generate_synthetic_data,
    load_forecast,
    train_forecast,
    validate_vs_real,
)

__all__ = [
    "DEFAULT_ARTIFACT",
    "FEATURES",
    "forecast_skin_temp",
    "generate_synthetic_data",
    "load_forecast",
    "train_forecast",
    "validate_vs_real",
    "detect_anomalies",
    "spatial_local_residual",
]