"""Heat data sources — normalized FortyGuard access with an offline mock.

Two interchangeable backends behind the same protocol:

- ``LiveFortyGuardSource`` wraps the official template client with
  result caching (credits are only deducted on task completion, so
  caching a completed response saves real credits) and graceful
  handling of Premium-plan endpoints on a Basic key.
- ``MockDataSource`` is a deterministic, physically-plausible synthetic
  district model so the entire demo runs with zero credits, zero keys,
  anywhere. Clearly labeled in every payload it produces.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from .physics.units import normalize_celsius  # noqa: E402


# ------------------------------------------------------------------ models


@dataclass
class HeatmapLayer:
    """One heatmap layer (tcm snapshot or an analysis layer)."""

    analytic_type: str
    units: str  # "celsius" for tcm, "hour" for analysis layers
    n_cells: int
    min: float
    mean: float
    max: float
    tiles: list[dict[str, float]]  # [{lat, lon, value}]
    source: str = "live"

    @property
    def range_c(self) -> float:
        return self.max - self.min


@dataclass
class EnvSeries:
    """Hourly environmental parameters for one anchor point (24 h)."""

    hours: list[int] = field(default_factory=lambda: list(range(24)))
    wet_bulb_c: list[float] = field(default_factory=list)
    apparent_c: list[float] = field(default_factory=list)
    humidity_pct: list[float] = field(default_factory=list)
    solar_w_m2: list[float] = field(default_factory=list)
    heat_index_c: list[float] = field(default_factory=list)
    co2_ppm: list[float] = field(default_factory=list)
    source: str = "live"

    def at_hour(self, hour: int) -> dict[str, float]:
        idx = hour % 24
        return {
            "hour": self.hours[idx] if idx < len(self.hours) else hour,
            "wet_bulb_c": self._get(self.wet_bulb_c, idx),
            "apparent_c": self._get(self.apparent_c, idx),
            "humidity_pct": self._get(self.humidity_pct, idx),
            "solar_w_m2": self._get(self.solar_w_m2, idx),
            "heat_index_c": self._get(self.heat_index_c, idx),
        }

    @staticmethod
    def _get(values: list[float], idx: int) -> float:
        return values[idx] if idx < len(values) else (values[-1] if values else 0.0)


@dataclass
class DistrictSnapshot:
    """Everything the auditor needs for one district/date."""

    name: str
    center_lat: float
    center_lon: float
    date: str
    heatmap: HeatmapLayer | None = None
    exceedance: HeatmapLayer | None = None
    persistence: HeatmapLayer | None = None
    env: EnvSeries | None = None
    warnings: list[str] = field(default_factory=list)
    source: str = "live"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "center_lat": self.center_lat,
            "center_lon": self.center_lon,
            "date": self.date,
            "source": self.source,
            "warnings": self.warnings,
        }
        for key, layer in (
            ("heatmap", self.heatmap),
            ("exceedance", self.exceedance),
            ("persistence", self.persistence),
        ):
            if layer is not None:
                payload[key] = {
                    "analytic_type": layer.analytic_type,
                    "units": layer.units,
                    "n_cells": layer.n_cells,
                    "min": round(layer.min, 2),
                    "mean": round(layer.mean, 2),
                    "max": round(layer.max, 2),
                    "sample_tiles": layer.tiles[:20],
                }
        if self.env is not None:
            payload["env"] = {
                "hours": self.env.hours,
                "wet_bulb_c": [round(v, 1) for v in self.env.wet_bulb_c],
                "apparent_c": [round(v, 1) for v in self.env.apparent_c],
                "humidity_pct": [round(v, 1) for v in self.env.humidity_pct],
                "solar_w_m2": [round(v, 1) for v in self.env.solar_w_m2],
                "heat_index_c": [round(v, 1) for v in self.env.heat_index_c],
                "co2_ppm": [round(v, 1) for v in self.env.co2_ppm],
            }
        return payload


# ------------------------------------------------------------- districts


@dataclass
class District:
    """Static geography + material assumptions for a demo district."""

    name: str
    lat: float
    lon: float
    base_mean_c: float
    base_amplitude_c: float
    heat_island_c: float  # how much hotter the core is than surroundings
    albedo: float
    humidity_base_pct: float
    exceedance_threshold_c: float = 30.0
    night_persistence_hours: float = 12.0  # effective cooling time constant


#: US districts with distinct thermal personalities — all mock-safe.
DISTRICTS: dict[str, District] = {
    "phoenix": District(
        name="Phoenix, AZ", lat=33.4484, lon=-112.0740,
        base_mean_c=36.0, base_amplitude_c=8.0, heat_island_c=4.0,
        albedo=0.12, humidity_base_pct=25.0,
    ),
    "san-jose": District(
        name="San Jose, CA", lat=37.3382, lon=-121.8863,
        base_mean_c=26.0, base_amplitude_c=7.0, heat_island_c=3.0,
        albedo=0.25, humidity_base_pct=45.0,
    ),
    "manhattan": District(
        name="Lower Manhattan, NYC", lat=40.7110, lon=-74.0120,
        base_mean_c=28.0, base_amplitude_c=6.0, heat_island_c=5.0,
        albedo=0.20, humidity_base_pct=60.0,
    ),
    "chicago": District(
        name="Chicago, IL", lat=41.8781, lon=-87.6298,
        base_mean_c=24.0, base_amplitude_c=6.0, heat_island_c=3.5,
        albedo=0.25, humidity_base_pct=55.0,
    ),
    "austin": District(
        name="Austin, TX", lat=30.2672, lon=-97.7431,
        base_mean_c=33.0, base_amplitude_c=7.0, heat_island_c=3.0,
        albedo=0.18, humidity_base_pct=50.0,
    ),
}


def get_district(name: str) -> District:
    key = name.strip().lower().replace(" ", "-")
    if key not in DISTRICTS:
        available = ", ".join(sorted(DISTRICTS))
        raise ValueError(f"Unknown district {name!r}. Available: {available}")
    return DISTRICTS[key]


# ------------------------------------------------------------------ mock


def _diurnal_series(base_c: float, amplitude_c: float, peak_hour: int = 14) -> list[float]:
    """A daily temperature curve peaking at ``peak_hour`` local time."""
    return [
        base_c + amplitude_c * math.sin(math.pi * (h - (peak_hour - 6)) / 12.0)
        for h in range(24)
    ]


class MockDataSource:
    """Deterministic, physically-plausible synthetic district data."""

    source_name = "mock"

    def __init__(self) -> None:
        self._calls = 0

    def _tile_grid(self, district: District, size: int = 9) -> list[tuple[float, float]]:
        """A coarse grid of tile centers around the district anchor."""
        step = 0.02  # ~2 km spacing
        half = step * (size - 1) / 2
        tiles = []
        for i in range(size):
            for j in range(size):
                lat = district.lat - half + i * step
                lon = district.lon - half + j * step
                dist = math.hypot(lat - district.lat, lon - district.lon)
                tiles.append((lat, lon, dist))
        return tiles

    def _tile_temperature_c(self, dist: float, hour: int, district: District) -> float:
        core = math.exp(-dist / 0.03)  # heat island decays with distance
        return (
            district.base_mean_c
            + district.base_amplitude_c
            * math.sin(math.pi * (hour - 8) / 12.0)
            + district.heat_island_c * core
            - 3.0 * district.albedo  # reflective zones run cooler
        )

    def get_heatmap(
        self,
        district_name: str,
        date: str,
        hour: int = 14,
        analytic_type: str = "tcm",
        threshold: float | None = None,
    ) -> HeatmapLayer:
        self._calls += 1
        district = get_district(district_name)
        thresh = threshold or district.exceedance_threshold_c
        tiles: list[dict[str, float]] = []
        series_by_tile: list[list[float]] = []
        for lat, lon, dist in self._tile_grid(district):
            daily = _diurnal_series(
                district.base_mean_c
                - 3.0 * district.albedo
                + district.heat_island_c * math.exp(-dist / 0.03),
                district.base_amplitude_c,
            )
            series_by_tile.append(daily)
            value = daily[hour % 24]
            tiles.append({"lat": lat, "lon": lon, "value": round(value, 2)})

        if analytic_type == "tcm":
            units = "celsius"
            values = [t["value"] for t in tiles]
        elif analytic_type == "exceedance":
            units = "hour"
            values = [sum(1 for v in s if v >= thresh) for s in series_by_tile]
            for tile, v in zip(tiles, values):
                tile["value"] = v
        elif analytic_type == "persistence":
            units = "hour"
            values = [_longest_run(s, thresh) for s in series_by_tile]
            for tile, v in zip(tiles, values):
                tile["value"] = v
        else:
            raise ValueError(f"mock does not support analytic_type={analytic_type!r}")

        return HeatmapLayer(
            analytic_type=analytic_type,
            units=units,
            n_cells=len(tiles),
            min=min(values),
            mean=sum(values) / len(values),
            max=max(values),
            tiles=tiles,
            source=self.source_name,
        )

    def get_environmental_parameters(
        self,
        district_name: str,
        date: str,
        temperature_anchor_c: float | None = None,
    ) -> EnvSeries:
        self._calls += 1
        district = get_district(district_name)
        anchor = temperature_anchor_c or district.base_mean_c + 4.0
        hours = list(range(24))
        solar = [
            max(0.0, 900.0 * math.sin(math.pi * (h - 6) / 12.0))
            for h in hours
        ]
        apparent = _diurnal_series(anchor - 5.0, min(district.base_amplitude_c + 2.0, 9.0))
        humidity = [
            district.humidity_base_pct
            + 22.0 * math.exp(-((h - 5) ** 2) / 8.0)
            - 4.0 * math.sin(math.pi * (h - 8) / 12.0)
            for h in hours
        ]
        wet_bulb = [
            a - (100.0 - h_pct) * 0.06 for a, h_pct in zip(apparent, humidity)
        ]
        heat_index = [w + (a - w) * 0.55 for a, w in zip(apparent, wet_bulb)]
        co2 = [418 + 8.0 * math.sin(math.pi * (h - 6) / 12.0) for h in hours]
        return EnvSeries(
            hours=hours,
            wet_bulb_c=[round(v, 2) for v in wet_bulb],
            apparent_c=[round(v, 2) for v in apparent],
            humidity_pct=[round(v, 1) for v in humidity],
            solar_w_m2=[round(v, 1) for v in solar],
            heat_index_c=[round(v, 1) for v in heat_index],
            co2_ppm=[round(v, 1) for v in co2],
            source=self.source_name,
        )

    def get_district_snapshot(
        self,
        district_name: str,
        date: str,
        hour: int = 14,
        with_exceedance: bool = True,
        threshold: float | None = None,
    ) -> DistrictSnapshot:
        district = get_district(district_name)
        snapshot = DistrictSnapshot(
            name=district.name,
            center_lat=district.lat,
            center_lon=district.lon,
            date=date,
            heatmap=self.get_heatmap(district_name, date, hour),
            exceedance=self.get_heatmap(
                district_name, date, hour, "exceedance", threshold
            ) if with_exceedance else None,
            persistence=self.get_heatmap(
                district_name, date, hour, "persistence", threshold
            ) if with_exceedance else None,
            env=self.get_environmental_parameters(district_name, date),
            warnings=["mock data source: synthetic, deterministic, zero-credit demo data"],
            source=self.source_name,
        )
        return snapshot


def _longest_run(series: list[float], threshold: float) -> float:
    best = current = 0
    for v in series:
        if v >= threshold:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


# ------------------------------------------------------------- live


class LiveFortyGuardSource:
    """Caching wrapper around the official template client."""

    source_name = "live"

    def __init__(self, cache_dir: str | Path = "data/cache") -> None:
        from fortyguard import FortyGuardClient  # imported lazily so the
        # physics-only path never needs the live client.

        self.client = FortyGuardClient()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------- helpers

    def _cache_key(self, endpoint: str, **args: Any) -> str:
        raw = json.dumps(
            {"endpoint": endpoint, **args}, sort_keys=True, default=str
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    def _cached(self, key: str) -> dict | None:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _store(self, key: str, payload: dict) -> dict:
        path = self.cache_dir / f"{key}.json"
        path.write_text(
            json.dumps(payload, default=str), encoding="utf-8"
        )
        return payload

    # ------------------------------------------------------- tiles

    @staticmethod
    def _polygon_around(lat: float, lon: float, km: float = 3.0) -> dict:
        """A small square polygon (Basic-plan safe, ~9 km² area)."""
        deg = km / 111.0
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [lon - deg, lat - deg],
                            [lon + deg, lat - deg],
                            [lon + deg, lat + deg],
                            [lon - deg, lat + deg],
                            [lon - deg, lat - deg],
                        ]],
                    },
                }
            ],
        }

    @staticmethod
    def _parse_tiles(result: dict, analytic_type: str) -> tuple[list[dict], float, float, float]:
        """Read tile values and stats defensively from either schema.

        Live responses for ``tcm`` historically omit aggregate stats (only
        ``activity_id`` + ``n_cells``) — never trust the absence; fall back
        to computing min/mean/max from the tile values themselves.
        """
        has_map = isinstance(result, dict) and isinstance(result.get("map_data"), dict)
        stats = result.get("stats_data") or {}
        tiles: list[dict[str, float]] = []
        if has_map:
            features = result["map_data"].get("features") or []
            for feature in features:
                props = feature.get("properties") or {}
                geometry = feature.get("geometry") or {}
                coords = geometry.get("coordinates") or []
                center = _polygon_center(coords)
                if analytic_type == "tcm":
                    value = _num(props, "average_temperature") or _num(
                        props, "temperature"
                    )
                    if value is not None:
                        value = normalize_celsius(value)
                else:
                    value = _num(props, "value")
                if value is not None and center:
                    tiles.append({"lat": center[1], "lon": center[0], "value": round(value, 2)})
        values = [t["value"] for t in tiles]
        min_v = _num(stats, "min")
        mean_v = _num(stats, "mean")
        max_v = _num(stats, "max")
        if analytic_type == "tcm":
            temp_stats = stats.get("temperature_stats") or {}
            min_v = _num(temp_stats, "min")
            mean_v = _num(temp_stats, "mean")
            max_v = _num(temp_stats, "max")
        if min_v is None and values:
            min_v, max_v, mean_v = min(values), max(values), sum(values) / len(values)
        return tiles, min_v, mean_v, max_v

    def get_heatmap(
        self,
        district_name: str,
        date: str,
        hour: int = 14,
        analytic_type: str = "tcm",
        threshold: float | None = None,
        granularity: int = 100,
    ) -> HeatmapLayer:
        from fortyguard.samples import FILTER_TYPES

        district = get_district(district_name)
        key = self._cache_key(
            "heatmap",
            district=district_name,
            date=date,
            hour=hour,
            analytic_type=analytic_type,
            threshold=threshold,
            granularity=granularity,
        )
        cached = self._cached(key)
        if cached:
            cached["source"] = "live-cached"
            return HeatmapLayer(
                analytic_type=analytic_type,
                units=cached["units"],
                n_cells=cached["n_cells"],
                min=cached["min"],
                mean=cached["mean"],
                max=cached["max"],
                tiles=cached["tiles"],
                source="live-cached",
            )
        payload = {
            "polygon_aoi": self._polygon_around(district.lat, district.lon),
            "start_date": date,
            "start_time": f"{hour:02d}:00",
            "filter_type": FILTER_TYPES["single_hour"],
            "granularity": granularity,
            "analytic_type": analytic_type,
        }
        if threshold is not None:
            payload["threshold"] = threshold
        response = self.client.create_heatmap(
            polygon_aoi=payload["polygon_aoi"],
            start_date=date,
            start_time=payload["start_time"],
            filter_type=payload["filter_type"],
            granularity=granularity,
            analytic_type=analytic_type,
            threshold=threshold,
            verbose=False,
            timeout=900,
        )
        result = response["result"] if isinstance(response, dict) else response
        tiles, min_v, mean_v, max_v = self._parse_tiles(result, analytic_type)
        if analytic_type == "tcm":
            # Normalize aggregate stats to °C like the tiles above.
            min_v, mean_v, max_v = [
                normalize_celsius(v) if v is not None else None
                for v in (min_v, mean_v, max_v)
            ]
        units = "celsius" if analytic_type == "tcm" else "hour"
        layer = HeatmapLayer(
            analytic_type=analytic_type,
            units=units,
            n_cells=len(tiles),
            min=round(min_v, 2),
            mean=round(mean_v, 2),
            max=round(max_v, 2),
            tiles=tiles,
            source=self.source_name,
        )
        self._store(
            key,
            {
                "units": layer.units,
                "n_cells": layer.n_cells,
                "min": layer.min,
                "mean": layer.mean,
                "max": layer.max,
                "tiles": layer.tiles,
            },
        )
        return layer

    def get_environmental_parameters(
        self,
        district_name: str,
        date: str,
        temperature_anchor_c: float | None = None,
    ) -> EnvSeries:
        from fortyguard.samples import FILTER_TYPES

        district = get_district(district_name)
        key = self._cache_key(
            "env_params",
            district=district_name,
            date=date,
            temperature_anchor_c=temperature_anchor_c,
        )
        cached = self._cached(key)
        if cached and cached.get("apparent_c"):
            env = EnvSeries(source="live-cached")
            env.hours = cached["hours"]
            for field_name in (
                "wet_bulb_c",
                "apparent_c",
                "humidity_pct",
                "solar_w_m2",
                "heat_index_c",
                "co2_ppm",
            ):
                setattr(env, field_name, cached[field_name])
            return env
        anchor = temperature_anchor_c or (self.get_heatmap(district_name, date).mean)
        response = self.client.environmental_parameters(
            latitude=district.lat,
            longitude=district.lon,
            temperature=anchor,
            start_date=date,
            filter_type=FILTER_TYPES["single_day"],
            analysis=[
                "wet_bulb_temperature_celsius",
                "apparent_temperature_celsius",
                "relative_humidity_percent",
                "solar_irradiance",
                "heat_index_celsius",
                "co2_ppm",
            ],
            verbose=False,
            timeout=900,
        )
        result = response["result"] if isinstance(response, dict) else response
        env = self._parse_env(result)
        env.source = self.source_name
        self._store(
            key,
            {
                "hours": env.hours,
                "wet_bulb_c": env.wet_bulb_c,
                "apparent_c": env.apparent_c,
                "humidity_pct": env.humidity_pct,
                "solar_w_m2": env.solar_w_m2,
                "heat_index_c": env.heat_index_c,
                "co2_ppm": env.co2_ppm,
            },
        )
        return env

    @staticmethod
    def _parse_env(result: dict) -> EnvSeries:
        """Parse the verified live schema.

        ``result.locations[].parameters`` is a flat dict of *name → 24-h
        series*. ``solar_irradiance`` is *not* a series — it carries a
        single clear-sky ``ghi`` (W/m²) aggregate, so the diurnal solar
        curve is re-synthesized as a sine profile peaking at solar noon
        with amplitude anchored to that API-provided ghi.
        """
        env = EnvSeries()
        locations = result.get("locations") or []
        if not locations:
            return env
        params = locations[0].get("parameters") or {}
        series_map = {
            "wet_bulb_c": params.get("wet_bulb_temperature_celsius"),
            "apparent_c": params.get("apparent_temperature_celsius"),
            "humidity_pct": params.get("relative_humidity_percent"),
            "heat_index_c": params.get("heat_index_celsius"),
            "co2_ppm": params.get("co2_ppm"),
        }
        for field, values in series_map.items():
            if values:
                setattr(env, field, [float(v) for v in values if v is not None])
        n = len(env.apparent_c) or 24
        env.hours = list(range(n))
        ghi = _num((locations[0].get("solar_irradiance") or {}).get("clear_sky") or {}, "ghi")
        if ghi and ghi > 0.0:
            env.solar_w_m2 = [
                round(max(0.0, ghi * math.sin(math.pi * (h - 6) / 12.0)), 1)
                if 6 <= h <= 18 else 0.0
                for h in range(n)
            ]
        if not env.wet_bulb_c and env.apparent_c:
            env.wet_bulb_c = [a - 6.0 for a in env.apparent_c]
        return env

    def get_district_snapshot(
        self,
        district_name: str,
        date: str,
        hour: int = 14,
        with_exceedance: bool = True,
        threshold: float | None = None,
    ) -> DistrictSnapshot:
        district = get_district(district_name)
        warnings: list[str] = []
        heatmap = self.get_heatmap(district_name, date, hour)
        exceedance = persistence = None
        if with_exceedance:
            try:
                exceedance = self.get_heatmap(
                    district_name, date, hour, "exceedance", threshold
                )
                persistence = self.get_heatmap(
                    district_name, date, hour, "persistence", threshold
                )
            except Exception as exc:  # analysis layers may be plan-limited
                warnings.append(f"analysis layers unavailable: {exc}")
        try:
            env = self.get_environmental_parameters(district_name, date)
        except Exception as exc:
            warnings.append(f"env params unavailable: {exc}")
            env = None
        return DistrictSnapshot(
            name=district.name,
            center_lat=district.lat,
            center_lon=district.lon,
            date=date,
            heatmap=heatmap,
            exceedance=exceedance,
            persistence=persistence,
            env=env,
            warnings=warnings,
            source=self.source_name,
        )


# ------------------------------------------------------------------ util


def _num(mapping: dict, key: str) -> float | None:
    value = mapping.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _polygon_center(coords: Any) -> tuple[float, float] | None:
    """First ring centroid (lon, lat) of a GeoJSON polygon ring."""
    if not coords:
        return None
    ring = coords[0] if isinstance(coords[0], list) else coords
    if not ring:
        return None
    lons = [pt[0] for pt in ring if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    lats = [pt[1] for pt in ring if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if not lons:
        return None
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def resolve_source(source: str | None = None):
    """Pick a data source; live falls back to mock when no key is set."""
    mode = source or os.getenv("CALORAI_DATA_SOURCE", "").strip().lower()
    if mode == "mock":
        return MockDataSource(), "mock"
    try:
        return LiveFortyGuardSource(), "live"
    except Exception:
        return MockDataSource(), "mock"