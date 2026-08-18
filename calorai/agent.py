"""The calorai auditor — a deterministic agentic pipeline.

The agent is "agentic" in the tool-calling sense: it owns a fixed
workflow (scope → fetch → compute → attribute → prescribe → report),
every step is a tool call, and every tool result is physically
traceable. The LLM narrator (when present) only rewrites prose over the
finished numbers — the audit itself never depends on a model.

Workflow (all deterministic):

1. **Scope**    — validate district, date, audit hour, threshold.
2. **Fetch**    — heatmap (tcm), exceedance + persistence layers,
                 environmental parameters (24 h series) from the data
                 source (live API with cache, or the offline mock).
3. **Compute**  — energy balance at the audit hour on the hottest tile;
                 WBGT heat stress at the same hour; overnight retention
                 via the district's cooling time constant.
4. **Attribute**— share of the heat load by mechanism (solar vs.
                 longwave vs. convection).
5. **Prescribe**— ranked interventions, each with a quantified °C from
                 a closed-form lever equation.
6. **Report**   — structured dict for the narrator layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .data_source import District, get_district, resolve_source
from .narrator import make_narrator
from .physics import (
    MATERIALS,
    albedo_delta_temperature,
    energy_balance,
    exposure_risk,
    heat_stress_level,
    overnight_retention_ratio,
    shade_delta_temperature,
    storage_capacity,
    wbgt,
)

#: Default envelope assumptions for the audit hour (physics constants).
EMISSIVITY_DEFAULT = 0.93
CONVECTIVE_COEFFICIENT = 12.0  # W/m²·K, calm street conditions
SLAB_THICKNESS_M = 0.15  # active asphalt depth for storage estimates


@dataclass
class AuditRequest:
    """What the auditor needs to run one district audit."""

    district: str
    date: str
    hour: int = 14
    threshold_c: float = 30.0
    with_exceedance: bool = True
    data_source: str | None = None  # None -> auto (live w/ mock fallback)
    narrator_kind: str | None = None  # auto cascade


class AuditError(ValueError):
    """Raised when the audit cannot be scoped (bad inputs)."""


class AuditAgent:
    """Deterministic city heat-budget auditor."""

    def __init__(self, request: AuditRequest) -> None:
        self.request = request
        self.source, self.mode = resolve_source(request.data_source)
        self.district: District = get_district(request.district)
        if not 0 <= request.hour <= 23:
            raise AuditError(f"hour must be 0-23, got {request.hour}")
        if not 2021 <= int(request.date[:4]) <= 2026:
            raise AuditError(f"date outside catalog coverage: {request.date}")
        self.narrator = make_narrator(request.narrator_kind)

    # ----------------------------------------------------------------- tools

    def run(self, narrate: bool = True) -> dict[str, Any]:
        """Execute the full audit; returns the structured report (and an
        optional narration string under ``narrative``)."""
        req = self.request
        snapshot = self.source.get_district_snapshot(
            req.district,
            req.date,
            hour=req.hour,
            with_exceedance=req.with_exceedance,
            threshold=req.threshold_c,
        )
        heatmap = snapshot.heatmap
        if heatmap is None:
            raise AuditError("heatmap layer unavailable")

        hour_env = snapshot.env.at_hour(req.hour) if snapshot.env else {
            "apparent_c": heatmap.mean,
            "wet_bulb_c": heatmap.mean - 6.0,
            "solar_w_m2": 850.0,
        }
        hottest = max(heatmap.tiles, key=lambda t: t["value"])
        surface_c = hottest["value"]
        air_c = hour_env["apparent_c"]
        irradiance = hour_env["solar_w_m2"]

        budget = energy_balance(
            surface_temperature_c=surface_c,
            air_temperature_c=air_c,
            irradiance_w_m2=irradiance,
            albedo=self.district.albedo,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=CONVECTIVE_COEFFICIENT,
            storage_capacity_j_m2_k=storage_capacity(
                2200.0, 920.0, SLAB_THICKNESS_M
            ),
            temperature_change_c=self.district.base_amplitude_c,
            time_span_hours=6.0,
        )
        attribution = budget.attribution()

        excess = snapshot.exceedance
        exceedance_hrs = excess.mean if excess else 0.0
        exposure = exposure_risk(
            wet_bulb_celsius=hour_env["wet_bulb_c"],
            dry_bulb_celsius=surface_c,
            exceedance_hours=exceedance_hrs,
            threshold_celsius=req.threshold_c,
        )
        exposure["exceedance_hours"] = round(exceedance_hrs, 2)

        tau = self.district.night_persistence_hours
        retention = overnight_retention_ratio(tau)
        effusivity = _effusivity_for(self.district.albedo)

        interventions = self._prescribe(
            irradiance=irradiance,
            surface_c=surface_c,
            exceedance_hrs=exceedance_hrs,
        )

        report: dict[str, Any] = {
            "district": snapshot.name,
            "date": snapshot.date,
            "one_liner": (
                f"{snapshot.name} peaks at {heatmap.max:.1f} °C with "
                f"{exceedance_hrs:.1f} h above {req.threshold_c:.0f} °C; "
                f"dominant cause: solar absorption ({attribution['solar_absorption']:.0f}%), "
                f"top intervention: {interventions[0]['name']} (−{interventions[0]['delta_t_c']:.1f} °C)."
            ),
            "source": snapshot.source,
            "pipeline": "physics-first deterministic pipeline "
            "(FortyGuard API layers + Stefan-Boltzmann/Newton physics)",
            "snapshot": {
                "hour": req.hour,
                "n_cells": heatmap.n_cells,
                "min_c": heatmap.min,
                "mean_c": heatmap.mean,
                "max_c": heatmap.max,
                "hottest_tile": {k: round(v, 3) for k, v in hottest.items()},
            },
            "attribution": {
                "solar_flux": round(budget.absorbed_solar, 1),
                "longwave_flux": round(budget.net_longwave, 1),
                "convection_flux": round(budget.convection, 1),
                "storage_flux": round(budget.storage, 1),
                "net_flux": round(budget.net_flux, 1),
                "solar_share": round(attribution["solar_absorption"], 1),
                "longwave_share": round(attribution["net_longwave_retention"], 1),
                "convection_share": round(attribution["convection_suppression"], 1),
            },
            "inertia": {
                "time_constant_hours": tau,
                "thermal_effusivity": round(effusivity, 1),
                "overnight_retention": round(retention, 3),
                "persistence_layer_max_hours": (
                    snapshot.persistence.max if snapshot.persistence else None
                ),
            },
            "exposure": {
                **exposure,
                "wbgt_c": round(
                    wbgt(hour_env["wet_bulb_c"], surface_c), 2
                ),
            },
            "interventions": interventions,
            "provenance": (
                f"temperature layer: {snapshot.source}; "
                f"env series: {snapshot.env.source if snapshot.env else 'n/a'}; "
                f"equations: Stefan-Boltzmann, Newton's law, ΔT = ΔQ/H, WBGT; "
                f"units: °C"
            ),
            "warnings": snapshot.warnings,
        }
        if narrate:
            report["narrative"] = self.narrator.narrate(report)
        return report

    # ------------------------------------------------------------ prescribe

    def _prescribe(
        self, irradiance: float, surface_c: float, exceedance_hrs: float
    ) -> list[dict[str, Any]]:
        """Ranked interventions with quantified °C, best first."""
        albedo_old = self.district.albedo
        cool = albedo_delta_temperature(
            irradiance_w_m2=irradiance,
            albedo_before=albedo_old,
            albedo_after=0.60,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=CONVECTIVE_COEFFICIENT,
        )
        trees = shade_delta_temperature(
            irradiance_w_m2=irradiance,
            albedo=albedo_old,
            shade_fraction=0.50,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=CONVECTIVE_COEFFICIENT,
        )
        concrete = albedo_delta_temperature(
            irradiance_w_m2=irradiance,
            albedo_before=albedo_old,
            albedo_after=0.35,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=CONVECTIVE_COEFFICIENT,
        )
        interventions = [
            {
                "name": "Cool roofs on hottest tiles (albedo 0.12→0.60)",
                "delta_t_c": cool["delta_temperature_c"],
                "removed_flux_w_m2": cool["removed_flux_w_m2"],
                "basis": f"ΔT = Δα·G/H at G={irradiance:.0f} W/m², H from Stefan-Boltzmann + h_c={CONVECTIVE_COEFFICIENT}",
                "scope": "top 20% tiles by peak temperature",
            },
            {
                "name": "Street-tree shade canopy (50% coverage)",
                "delta_t_c": trees["delta_temperature_c"],
                "removed_flux_w_m2": trees["removed_flux_w_m2"],
                "basis": "ΔT = s·(1−α)·G/H; latent cooling not credited",
                "scope": "high-exposure streets",
            },
            {
                "name": "Reflective pavement (albedo 0.12→0.35)",
                "delta_t_c": concrete["delta_temperature_c"],
                "removed_flux_w_m2": concrete["removed_flux_w_m2"],
                "basis": "same lever equation, smaller Δα",
                "scope": "all district roads",
            },
        ]
        interventions.sort(key=lambda iv: iv["delta_t_c"], reverse=True)
        return [
            {**iv, "delta_t_c": round(iv["delta_t_c"], 2)} for iv in interventions
        ]


def _effusivity_for(albedo: float) -> float:
    """Rough effusivity proxy from the material table (W·s^0.5/m²K)."""
    from .physics.inertia import thermal_effusivity

    props = MATERIALS["vegetation"] if albedo >= 0.28 else MATERIALS["gray_concrete"]
    if props is MATERIALS["vegetation"]:
        return thermal_effusivity(0.5, 700.0, 1450.0)
    return thermal_effusivity(1.4, 2200.0, 900.0)