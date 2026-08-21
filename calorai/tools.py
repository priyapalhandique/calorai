"""Tool registry (D7) — the agent's hands, uniformly callable.

Every capability the auditor owns is exposed as a tool with a uniform
schema: name, description, keywords (for the deterministic intent
matcher), params, and a handler. Tools are thin: most delegate to the
AuditAgent pipeline and return one of the report blocks, so a tool
result is always a structured, physics-traceable dict — never a free
string.

Context memoizes the audit per (district, date, hour, threshold,
source), so a multi-step plan ("plan tomorrow for Maryvale") runs the
heavy audit once and reuses its blocks for every later tool call.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_DISTRICT = "phoenix"
DEFAULT_DATE = "2026-08-18"
DEFAULT_HOUR = 14


@dataclass
class ToolResult:
    """One tool execution: structured result + one-line summary."""

    name: str
    ok: bool
    result: dict[str, Any]
    summary: str
    duration_ms: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "ok": self.ok,
            "summary": self.summary,
            "duration_ms": self.duration_ms,
            "result": self.result,
            "error": self.error,
        }


class AgentContext:
    """Carries defaults + a memoized audit report between tool calls."""

    def __init__(
        self,
        district: str = DEFAULT_DISTRICT,
        date: str = DEFAULT_DATE,
        hour: int = DEFAULT_HOUR,
        threshold_c: float = 30.0,
        source: str | None = None,
    ) -> None:
        self.district = district
        self.date = date
        self.hour = hour
        self.threshold_c = threshold_c
        self.source = source
        self._memo: dict[tuple, dict[str, Any]] = {}
        # Follow-up memory (D8): last scope actually audited, so "what
        # about its cost?" resolves against the previous district/date.
        self.last_district: str | None = None
        self.last_date: str | None = None
        self.last_hour: int | None = None

    def _key(self, district: str, date: str, hour: int, threshold_c: float, source: str | None):
        return (district, date, hour, round(threshold_c, 2), source)

    def report(
        self,
        district: str | None = None,
        date: str | None = None,
        hour: int | None = None,
        threshold_c: float | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Run (or reuse) the audit for the requested scope."""
        from .agent import AuditAgent, AuditRequest

        d = district or self.district
        dt = date or self.date
        h = hour if hour is not None else self.hour
        t = threshold_c if threshold_c is not None else self.threshold_c
        src = source if source is not None else self.source
        key = self._key(d, dt, h, t, src)
        if key not in self._memo:
            agent = AuditAgent(
                AuditRequest(
                    district=d,
                    date=dt,
                    hour=h,
                    threshold_c=t,
                    data_source=src,
                    narrator_kind=None,
                )
            )
            self._memo[key] = agent.run(narrate=False)
        self.last_district = d
        self.last_date = dt
        self.last_hour = h
        return self._memo[key]


#: keyword -> tool name, for the deterministic intent matcher.
_TOOL_KEYWORDS: dict[str, list[str]] = {}


def _register_tool(
    name: str,
    description: str,
    keywords: list[str],
    handler: Callable[[AgentContext, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    tool = {
        "name": name,
        "description": description,
        "keywords": keywords,
        "handler": handler,
    }
    _TOOL_KEYWORDS[name] = keywords
    return tool


TOOLS: list[dict[str, Any]] = []


def tool(name: str, description: str, keywords: list[str]):
    def deco(fn: Callable[[AgentContext, dict[str, Any]], dict[str, Any]]):
        TOOLS.append(_register_tool(name, description, keywords, fn))
        return fn

    return deco


# ------------------------------------------------------------------ tools


@tool(
    "audit",
    "Full heat-budget audit: snapshot, energy attribution, canyon, inertia, "
    "exposure, interventions, vulnerability, theory-vs-data.",
    ["audit", "report", "hot", "analy", "summary", "check", "how hot", "is it hot"],
)
def _audit(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    return ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))


@tool(
    "forecast",
    "Predict the skin temperature for given conditions with the trained "
    "physics-informed ML surrogate (HistGradientBoosting, MAE 0.75 C).",
    ["forecast", "predict", "future", "tomorrow", "trend", "surrogate"],
)
def _forecast(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    from .ml.forecast import FEATURES, forecast_skin_temp, load_forecast

    model = load_forecast()
    features = {k: args[k] for k in FEATURES if k in args}
    if len(features) == len(FEATURES):
        pred = forecast_skin_temp(features, model=model)
        return {"mode": "explicit", "features": features, "predicted_skin_c": round(pred, 2)}
    # District mode: run the surrogate over the district's 24-h env series.
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    diurnal = report.get("diurnal", {}) or {}
    atmosphere = report.get("atmosphere", {}) or {}
    hours = diurnal.get("hours") or list(range(24))
    apparent = diurnal.get("apparent_c") or []
    series = []
    for i, h in enumerate(hours):
        ta = apparent[i] if i < len(apparent) and apparent[i] is not None else atmosphere.get("air_temperature_c", 30.0)
        feats = {
            "irradiance_w_m2": max(diurnal.get("solar_w_m2", [0.0] * 24)[i], 0.0)
            if i < len(diurnal.get("solar_w_m2", [])) else 0.0,
            "albedo": 0.12,
            "emissivity": 0.93,
            "convective_coefficient": 12.0,
            "air_temperature_c": ta,
            "radiative_environment_c": ta - 5.0,
            "storage_flux_w_m2": 100.0,
            "latent_flux_w_m2": 30.0,
        }
        series.append({"hour": h, **feats, "predicted_skin_c": round(forecast_skin_temp(feats, model=model), 2)})
    peak = max(series, key=lambda s: s["predicted_skin_c"])
    return {
        "mode": "district_24h",
        "district": report["district"],
        "peak_hour": peak["hour"],
        "peak_skin_c": peak["predicted_skin_c"],
        "series": series,
        "model": "forecast_v1.joblib (physics-informed, MAE 0.75 C on held-out synthetic sweep)",
        "caveat": "surrogate reproduces the physics solver; layer semantics (canopy vs skin) still apply",
    }


@tool(
    "anomaly",
    "Statistically anomalous tiles: IsolationForest + spatial/physics z-scores.",
    ["anomaly", "outlier", "weird", "flag", "abnormal", "hotspot"],
)
def _anomaly(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["analysis"]["anomaly"], "district": report["district"]}


@tool(
    "risk",
    "Human heat risk: WBGT level, worker-safety alert, downburst outflow watch.",
    ["risk", "danger", "safe", "worker", "wbgt", "alert", "health", "heatstroke"],
)
def _risk(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {
        "district": report["district"],
        "hour": report["snapshot"]["hour"],
        "exposure": report["exposure"],
        "vulnerability": report["vulnerability"],
        "downburst": report["downburst"],
    }


@tool(
    "respond_mist",
    "Heat-response action plan: wind-aware misting placement, intensity, schedule, "
    "plus worker/outdoor heat actions from WBGT.",
    ["mist", "misting", "cool", "spray", "respond", "action", "mitigate", "deploy", "water"],
)
def _respond_mist(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    from .responder.heat_response import heat_response_plan
    from .responder.misting import misting_plan

    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    exposure = report["exposure"]
    circ = report.get("thermal_wind", {}) or {}
    atmosphere = report.get("atmosphere", {}) or {}
    mist = misting_plan(
        wbgt_c=exposure["wbgt_c"],
        humidity_pct=atmosphere.get("relative_humidity_pct", 0.0),
        wind_speed_m_s=atmosphere.get("wind_speed_m_s", 0.0),
        air_temp_c=atmosphere.get("air_temperature_c", 0.0),
        inflow_direction_deg=circ.get("inflow_direction_deg"),
        inflow_speed_scale_m_s=circ.get("inflow_speed_scale_m_s", 0.0),
    )
    response = heat_response_plan(wbgt_c=exposure["wbgt_c"])
    return {"misting": mist, "heat_response": response, "district": report["district"]}


@tool(
    "equity",
    "Heat-equity metrics for a district, plus the cross-city leaderboard.",
    ["equity", "fair", "gini", "poor", "marginal", "compare", "leaderboard", "rank"],
)
def _equity(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    block = {"equity": report["analysis"]["equity"], "district": report["district"]}
    if args.get("benchmark", True):
        from .analyst import cross_district_leaderboard
        from .data_source import DISTRICTS

        block["leaderboard"] = cross_district_leaderboard(
            list(DISTRICTS), report["date"], source="mock"
        )
        block["n_districts"] = len(block["leaderboard"])
    return block


@tool(
    "productivity",
    "Labour-capacity loss at the district WBGT (Dunne 2013 / Kjellstrom 2009).",
    ["productivity", "labour", "labor", "work", "capacity", "hours lost", "output"],
)
def _productivity(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["analysis"]["productivity"], "district": report["district"]}


@tool(
    "economy",
    "District cost of heat: cooling energy + productivity losses, USD per year.",
    ["economy", "cost", "money", "budget", "dollar", "price", "spend"],
)
def _economy(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["analysis"]["economy"], "district": report["district"]}


@tool(
    "thermal_wind",
    "Circulation the temperature field implies: inflow direction, pressure deficit, "
    "ventilation corridors, gradient vector field.",
    ["wind", "breeze", "circulation", "ventil", "airflow", "gradient", "trajectory"],
)
def _thermal_wind(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["thermal_wind"], "district": report["district"]}


@tool(
    "downburst",
    "Downburst thermodynamic diagnostic: wet-bulb depression + rain onset risk bands.",
    ["downburst", "outflow", "microburst", "storm", "rain", "gust"],
)
def _downburst(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["downburst"], "district": report["district"]}


@tool(
    "aviation",
    "Runway heat & takeoff analysis: density altitude, takeoff-distance factor, "
    "weight-restriction hint, tire/tarmac/brake risk bands.",
    ["aviation", "runway", "airport", "takeoff", "airplane", "flight", "pilot", "aircraft"],
)
def _aviation(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    from .analyst.aviation import runway_heat_analysis

    return runway_heat_analysis(
        air_temp_c=report["atmosphere"]["air_temperature_c"],
        tile_max_c=report["snapshot"]["max_c"],
        humidity_pct=report["atmosphere"]["relative_humidity_pct"],
        wind_speed_m_s=report["atmosphere"]["wind_speed_m_s"],
        elevation_m=args.get("elevation_m"),
        runway_m=args.get("runway_m"),
    )


@tool(
    "landcover",
    "Street-level landcover evidence: satellite + street-view segmentation (sky-view factor, shade, green cover).",
    ["landcover", "satellite", "street view", "streetview", "sky view", "sky-view", "canopy", "green", "impervious", "shade"],
)
def _landcover(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["landcover"], "district": report["district"]}


@tool(
    "synoptic",
    "Synoptic risk: heat-wave-day, omega-block heat dome, fire-weather VPD bands from the 24-h env series.",
    ["synoptic", "heat wave", "heatwave", "omega", "dome", "heat dome", "fire weather", "fire risk", "vpd", "heatwave"],
)
def _synoptic(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    return {**report["synoptic"], "district": report["district"]}


@tool(
    "export",
    "Open export package: tile GeoJSON + audit CSV + interventions CSV (ZIP).",
    ["export", "download", "geojson", "csv", "interop", "package", "gis"],
)
def _export(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    from .interop import export_zip_bytes
    from .data_source import resolve_source

    district_key = (args.get("district") or ctx.district).lower().replace(" ", "-")
    report = ctx.report(district=args.get("district"), date=args.get("date"), hour=args.get("hour"))
    source, _ = resolve_source(args.get("source"))
    snapshot = source.get_district_snapshot(
        district_key,
        report["date"],
        hour=report["snapshot"]["hour"],
        with_exceedance=True,
        threshold=ctx.threshold_c,
    )
    content = export_zip_bytes(report, snapshot, ctx.threshold_c)
    return {
        "filename": f"calorai_{report['district'].replace(' ', '-')}_{report['date']}_interop.zip",
        "bytes": len(content),
        "files": ["tiles.geojson", "audit.csv", "interventions.csv"],
        "ready": True,
    }


@tool(
    "usage",
    "Data-source mode and credit/usage diagnostics.",
    ["usage", "credit", "cost", "api", "calls", "key", "quota"],
)
def _usage(ctx: AgentContext, args: dict[str, Any]) -> dict[str, Any]:
    from .data_source import resolve_source

    source, mode = resolve_source(args.get("source"))
    out: dict[str, Any] = {"mode": mode, "source": source.source_name}
    if mode == "live" and hasattr(source, "client"):
        try:
            out["credits"] = source.client.fetch_api_key_usage()
        except Exception as exc:  # pragma: no cover - depends on API availability
            out["credits_error"] = str(exc)
    else:
        out["calls_made"] = getattr(source, "_calls", 0)
        out["note"] = "mock mode: zero credits, deterministic demo data"
    return out


def list_tools() -> list[dict[str, Any]]:
    """Public registry (name, description, keywords) for planner + UI."""
    return [{"name": t["name"], "description": t["description"], "keywords": t["keywords"]} for t in TOOLS]


def execute_tool(name: str, args: dict[str, Any], ctx: AgentContext) -> ToolResult:
    """Run one tool by name with the given args; never raises."""
    started = time.perf_counter()
    for t in TOOLS:
        if t["name"] == name:
            try:
                result = t["handler"](ctx, args or {})
                summary = _summarize(name, result)
                return ToolResult(
                    name=name, ok=True, result=result, summary=summary,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            except Exception as exc:  # tools degrade to an error result
                return ToolResult(
                    name=name, ok=False, result={}, summary="tool failed",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    error=str(exc),
                )
    return ToolResult(name=name, ok=False, result={}, summary="unknown tool",
                      duration_ms=0, error=f"unknown tool {name!r}")


def _summarize(name: str, result: dict[str, Any]) -> str:
    try:
        if name == "audit":
            r = result
            return (f"{r['district']} {r['date']}: {r['snapshot']['min_c']}-{r['snapshot']['max_c']} C, "
                    f"WBGT {r['exposure']['wbgt_c']} C, top fix {r['interventions'][0]['name']} "
                    f"(-{r['interventions'][0]['delta_t_c']} C)")
        if name == "forecast":
            if result.get("mode") == "district_24h":
                return f"peak skin {result['peak_skin_c']} C at hour {result['peak_hour']}"
            return f"predicted skin {result['predicted_skin_c']} C"
        if name == "anomaly":
            return f"{result['n_flagged']} of {result['n_tiles']} tiles flagged"
        if name == "risk":
            return f"WBGT {result['exposure']['wbgt_c']} C ({result['exposure']['level']})"
        if name == "respond_mist":
            m = result["misting"]
            return m.get("headline", "misting plan ready")
        if name == "equity":
            return f"Gini {result['equity']['gini']}, gap {result['equity']['quintile_gap_c']} K"
        if name == "productivity":
            return f"{result['moderate']['loss_pct']}% capacity lost at WBGT {result['wbgt_c']} C"
        if name == "economy":
            return f"${result['total_usd_per_year']:,}/yr total cost of heat"
        if name == "thermal_wind":
            return (f"inflow {result.get('inflow_direction', 'uniform')}, "
                    f"dp {result.get('pressure_deficit_hpa', 0)} hPa, "
                    f"{result.get('ventilation_corridors', 0)} corridors")
        if name == "downburst":
            return f"peak risk {result.get('peak_risk', 'low')} at hour {result.get('peak_hour', '?')}"
        if name == "aviation":
            return (f"DA {result.get('density_altitude_m', 0):.0f} m, "
                    f"takeoff factor {result.get('takeoff_distance_factor', 0):.2f}")
        if name == "export":
            return f"{result['bytes']} bytes ready ({result['filename']})"
        if name == "usage":
            return f"mode {result['mode']}"
        return json.dumps(result, default=str)[:120]
    except Exception:
        return json.dumps(result, default=str)[:120]
