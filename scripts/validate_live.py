"""D9 stage-2 validation: surrogate vs closed-form physics vs real API series.

For each district on a pinned date, runs the full audit for all 24 hours
(LiveFortyGuardSource, disk-cached; heatmap pull per hour, env series
cached per district+date, exceedance/persistence layers skipped) and
collects, hour by hour:

  observed_max_c  hottest API tile value (skin-layer envelope)
  observed_mean_c mean API tile value
  air_c           district air temperature from the env series
  physics_c       closed-form equilibrium skin prediction (theory_vs_data)
  surrogate_c     forecast_v1.joblib over the same per-hour inputs the
                  app's "forecast" tool feeds it

Aggregates per district: surrogate MAE, physics MAE, surrogate-vs-physics
MAE, layer_offset_c = mean(physics - observed), plus peak-hour rows.
Result JSON is written to data/validation_live.json (gitignored) and the
numbers are mirrored into docs/ml-validation.md by the author after review.
"""
from __future__ import annotations

import json
import hashlib
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calorai.agent import AuditAgent, AuditRequest
from calorai.ml.forecast import forecast_skin_temp, load_forecast

DATE = "2024-07-15"
DISTRICTS = ["phoenix"]
OUT = Path("data/validation_live.json")


def _cache_key(endpoint: str, **args: object) -> str:
    raw = json.dumps({"endpoint": endpoint, **args}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def cached_hours(district: str, date: str) -> list[int]:
    """Hours whose single-hour tcm heatmap is already on disk (live-cached)."""
    from calorai.data_source import LiveFortyGuardSource

    cache_dir = Path(LiveFortyGuardSource().cache_dir)
    present: list[int] = []
    for h in range(24):
        key = _cache_key(
            "heatmap",
            district=district,
            date=date,
            hour=h,
            analytic_type="tcm",
            threshold=None,
            granularity=100,
        )
        if (cache_dir / f"{key}.json").exists():
            present.append(h)
    return present


def surrogate_series(report: dict) -> dict[int, float]:
    """Same per-hour feature recipe as tools._forecast district_24h."""
    diurnal = report.get("diurnal", {}) or {}
    atmosphere = report.get("atmosphere", {}) or {}
    hours = diurnal.get("hours") or list(range(24))
    apparent = diurnal.get("apparent_c") or []
    solar = diurnal.get("solar_w_m2") or []
    model = load_forecast()
    out: dict[int, float] = {}
    for i, h in enumerate(hours):
        ta = (
            apparent[i]
            if i < len(apparent) and apparent[i] is not None
            else atmosphere.get("air_temperature_c", 30.0)
        )
        feats = {
            "irradiance_w_m2": max(solar[i], 0.0) if i < len(solar) else 0.0,
            "albedo": 0.12,
            "emissivity": 0.93,
            "convective_coefficient": 12.0,
            "air_temperature_c": ta,
            "radiative_environment_c": ta - 5.0,
            "storage_flux_w_m2": 100.0,
            "latent_flux_w_m2": 30.0,
        }
        out[h] = float(forecast_skin_temp(feats, model=model))
    return out


def validate_district(name: str, date: str) -> dict:
    from calorai.data_source import LiveFortyGuardSource

    cache_dir = Path(LiveFortyGuardSource().cache_dir)
    env_key = _cache_key(
        "env_params",
        district=name,
        date=date,
        temperature_anchor_c=None,
        schema_version=2,
    )
    if not (cache_dir / f"{env_key}.json").exists():
        raise RuntimeError(
            f"env series not cached for {name} {date} — refusing a live pull; "
            "run once with a key then reuse cached heatmaps"
        )
    hours = cached_hours(name, date)
    if not hours:
        raise RuntimeError(f"no cached tcm heatmaps for {name} {date}")
    rows: list[dict] = []
    last_report: dict | None = None
    for h in hours:
        req = AuditRequest(
            district=name, date=date, hour=h, with_exceedance=False, data_source="live"
        )
        agent = AuditAgent(req)
        report = agent.run(narrate=False)
        last_report = report
        tvs = report["theory_vs_data"]
        tiles = agent.fetch_snapshot().heatmap.tiles
        rows.append(
            {
                "hour": h,
                "air_c": round(float(tvs["air_temperature_c"]), 2),
                "observed_max_c": round(float(tvs["measured_tile_c"]), 2),
                "observed_mean_c": round(
                    float(statistics.mean(t["value"] for t in tiles)), 2
                ),
                "physics_c": round(float(tvs["predicted_skin_c"]), 2),
            }
        )
    surr = surrogate_series(last_report or {})
    for r in rows:
        r["surrogate"] = round(surr[r["hour"]], 2)

    def mae(key: str, pred: str) -> float:
        return round(
            statistics.mean(
                abs(r[pred] - r[key]) for r in rows
            ),
            3,
        )

    peak_tile = max(rows, key=lambda r: r["observed_max_c"])
    peak_air = max(rows, key=lambda r: r["air_c"])
    result = {
        "district": name,
        "date": date,
        "n_hours": len(rows),
        "cached_hours": hours,
        "surrogate_mae_vs_tile_max_c": mae("observed_max_c", "surrogate"),
        "surrogate_mae_vs_tile_mean_c": mae("observed_mean_c", "surrogate"),
        "physics_mae_vs_tile_max_c": mae("observed_max_c", "physics_c"),
        "physics_mae_vs_tile_mean_c": mae("observed_mean_c", "physics_c"),
        "surrogate_vs_physics_mae_c": mae("physics_c", "surrogate"),
        "layer_offset_c": round(
            statistics.mean(r["physics_c"] - r["observed_max_c"] for r in rows), 3
        ),
        "peak_tile_hour": peak_tile["hour"],
        "peak_tile_c": peak_tile["observed_max_c"],
        "peak_air_hour": peak_air["hour"],
        "peak_air_c": peak_air["air_c"],
        "rows": rows,
    }
    return result


def main() -> None:
    # This validator is intentionally live-only when executed, but importing
    # it from tests must not clear the suite's mock pin.
    old_source = os.environ.pop("CALORAI_DATA_SOURCE", None)
    try:
        results: list[dict] = []
        for d in DISTRICTS:
            print(f"--- validating {d} {DATE} ---", flush=True)
            try:
                results.append(validate_district(d, DATE))
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"!! {d}: {type(exc).__name__}: {exc}", flush=True)
                # Record the error for this district and continue so the script
                # always writes `data/validation_live.json` instead of exiting
                # silently when one district fails.
                results.append({"district": d, "error": f"{type(exc).__name__}: {exc}"})
                continue
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"wrote {OUT}", flush=True)
        for res in results:
            if "error" in res:
                print(f"{res['district']:<10} ERROR {res['error']}", flush=True)
                continue
            print(
                f"{res['district']:<10} surrogate_mae {res['surrogate_mae_vs_tile_max_c']:>6} "
                f"physics_mae {res['physics_mae_vs_tile_max_c']:>6} "
                f"surr-vs-phys {res['surrogate_vs_physics_mae_c']:>6} "
                f"layer_offset {res['layer_offset_c']:>+6} "
                f"peak_tile {res['peak_tile_c']} @ {res['peak_tile_hour']}h "
                f"peak_air {res['peak_air_c']} @ {res['peak_air_hour']}h"
            )
    finally:
        if old_source is not None:
            os.environ["CALORAI_DATA_SOURCE"] = old_source


if __name__ == "__main__":
    main()
