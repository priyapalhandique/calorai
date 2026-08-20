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

import datetime as _dt
import math
from dataclasses import dataclass
from typing import Any

from .analyst import annualized_loss, district_cost_of_heat, heat_burden
from .data_source import District, get_district, resolve_source
from .ml.anomaly import detect_anomalies
from .narrator import make_narrator
from .physics import (
    EquilibriumInputs,
    MATERIALS,
    albedo_delta_temperature,
    canyon_albedo,
    canyon_longwave_environment_c,
    canyon_wind_shelter_factor,
    closure_analysis,
    convective_coefficient_from_wind,
    damping_depth_m,
    diurnal_phase_lag_hours,
    energy_balance,
    equilibrium_surface_temperature_c,
    exposure_risk,
    humidex,
    overnight_retention_ratio,
    priestley_taylor_latent_flux,
    sensitivity_bands,
    shade_delta_temperature,
    sky_temperature_c,
    sky_view_factor,
    storage_capacity,
    storage_heat_flux_force_restore,
    temperature_drop_from_flux_removal,
    thermal_admittance,
)
from .physics.economics import (
    cooling_degree_hours,
    retrofit_roi,
)
from .physics.downburst import downburst_risk_series
from .physics.facade import facade_heat_load_ranking
from .physics.thermal_wind import urban_circulation
from .physics.vulnerability import heat_vulnerability_score, worker_safety_alert

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

    def fetch_snapshot(self) -> Any:
        """Fetch (and cache) the district snapshot for this request."""
        req = self.request
        return self.source.get_district_snapshot(
            req.district,
            req.date,
            hour=req.hour,
            with_exceedance=req.with_exceedance,
            threshold=req.threshold_c,
        )

    def run(self, narrate: bool = True) -> dict[str, Any]:
        """Execute the full audit; returns the structured report (and an
        optional narration string under ``narrative``)."""
        req = self.request
        snapshot = self.fetch_snapshot()
        heatmap = snapshot.heatmap
        if heatmap is None:
            raise AuditError("heatmap layer unavailable")

        hour_env = snapshot.env.at_hour(req.hour) if snapshot.env else {
            "apparent_c": heatmap.mean,
            "wet_bulb_c": heatmap.mean - 6.0,
            "solar_w_m2": 850.0,
            "wind_speed_m_s": 0.0,
            "cloud_cover_pct": 0.0,
        }
        hottest = max(heatmap.tiles, key=lambda t: t["value"])
        surface_c = hottest["value"]
        air_c = hour_env["apparent_c"]
        irradiance = hour_env["solar_w_m2"]
        wind = max(hour_env.get("wind_speed_m_s", 0.0) or 0.0, 0.0)
        cloud_pct = min(max(hour_env.get("cloud_cover_pct", 0.0) or 0.0, 0.0), 100.0)
        humidity_pct = hour_env.get("humidity_pct", 0.0) or 0.0
        # Wind-aware convection: live API exposes no wind series, so calm
        # conditions (12 W/m²·K) apply there; the mock atmosphere has wind.
        h_c = (
            convective_coefficient_from_wind(wind)
            if wind > 0.0
            else CONVECTIVE_COEFFICIENT
        )
        # Canyon wind sheltering (Oke Ch. 4): the street-level flow that
        # actually cools the surface is a fraction of the free-stream
        # wind — skimming flow in dense canyons keeps only ~55%.
        wind_shelter = canyon_wind_shelter_factor(self.district.h_over_w)
        h_c_street = h_c * wind_shelter
        # Street canyon geometry (Oke et al. 2017): darker walls lower the
        # effective albedo (trapping, Eq. 5.18) and walls block the cool
        # sky, so the floor's radiative environment is warmer than open
        # sky — both make canyons hotter than a flat-site model admits.
        eff_albedo = canyon_albedo(
            self.district.albedo, self.district.wall_albedo, self.district.h_over_w
        )
        # The longwave sink is the sky, not the air: Brutsaert clear-sky
        # emissivity from humidity, blended with cloud, then canyon-blended
        # with the warm walls the floor actually sees.
        sky_c = (
            sky_temperature_c(air_c, humidity_pct, cloud_pct / 100.0)
            if humidity_pct > 0.0
            else None
        )
        radiative_env_c = (
            canyon_longwave_environment_c(
                air_c,
                humidity_pct,
                cloud_pct / 100.0,
                wall_temperature_c=surface_c,
                h_over_w=self.district.h_over_w,
                wall_emissivity=EMISSIVITY_DEFAULT,
            )
            if sky_c is not None
            else None
        )

        slab_capacity = storage_capacity(
            self.district.material_density_kg_m3,
            self.district.material_specific_heat_j_kg_k,
            SLAB_THICKNESS_M,
        )
        budget = energy_balance(
            surface_temperature_c=surface_c,
            air_temperature_c=air_c,
            irradiance_w_m2=irradiance,
            albedo=eff_albedo,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=h_c_street,
            storage_capacity_j_m2_k=slab_capacity,
            temperature_change_c=self.district.base_amplitude_c,
            time_span_hours=6.0,
            sky_temperature_c=radiative_env_c,
        )
        # Evaporative cooling (Priestley-Taylor, Monteith & Unsworth
        # Ch. 13): the available energy (absorbed solar minus net
        # longwave, minus storage) that wet/vegetated fabric would send
        # into latent heat instead of the air. Dry districts credit 0.
        net_radiation = budget.absorbed_solar - budget.net_longwave
        latent_flux = priestley_taylor_latent_flux(
            net_radiation_w_m2=net_radiation,
            ground_flux_w_m2=budget.storage,
            air_temperature_c=air_c,
            evaporative_fraction=self.district.evaporative_fraction,
        )
        budget = energy_balance(
            surface_temperature_c=surface_c,
            air_temperature_c=air_c,
            irradiance_w_m2=irradiance,
            albedo=eff_albedo,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=h_c_street,
            storage_capacity_j_m2_k=slab_capacity,
            temperature_change_c=self.district.base_amplitude_c,
            time_span_hours=6.0,
            sky_temperature_c=radiative_env_c,
            latent_flux_w_m2=latent_flux,
        )
        attribution = budget.attribution()

        excess = snapshot.exceedance
        exceedance_hrs = excess.mean if excess else 0.0
        exposure = exposure_risk(
            wet_bulb_celsius=hour_env["wet_bulb_c"],
            dry_bulb_celsius=air_c,
            exceedance_hours=exceedance_hrs,
            threshold_celsius=req.threshold_c,
            irradiance_w_m2=irradiance,
            wind_speed_m_s=wind,
        )
        exposure["exceedance_hours"] = round(exceedance_hrs, 2)
        if humidity_pct > 0.0:
            exposure["humidex_c"] = round(humidex(air_c, humidity_pct), 1)

        tau = self.district.night_persistence_hours
        retention = overnight_retention_ratio(tau)
        effusivity = _effusivity_for(self.district.albedo)
        admittance = thermal_admittance(
            self.district.material_k_w_m_k,
            self.district.material_density_kg_m3,
            self.district.material_specific_heat_j_kg_k,
        )
        damping = damping_depth_m(
            self.district.material_k_w_m_k,
            self.district.material_density_kg_m3,
            self.district.material_specific_heat_j_kg_k,
        )
        # Diurnal slope at the audit hour (dT/dt of the district curve)
        # for the force-restore storage term.
        omega_day = 2.0 * math.pi / 24.0
        rate_c_s = (
            self.district.base_amplitude_c
            * omega_day
            * math.cos(omega_day * (req.hour - 14))
            / 3600.0
        )
        storage_force_restore = storage_heat_flux_force_restore(
            admittance,
            surface_c,
            self.district.base_mean_c,
            temperature_rate_c_per_s=rate_c_s,
        )
        # Measured peak-lag fingerprint (B2): the observed hour of the
        # diurnal temperature maximum vs local solar noon, against the
        # ideal semi-infinite lag of P/8 = 3 h (Campbell & Norman Ch. 8;
        # real urban fabric 2-5 h, Oke et al. §5). Short measured lags
        # mean the canopy responds faster than the ideal surface.
        solar_noon_h = 12.0 + (
            15.0 * self.district.utc_offset_hours - self.district.lon
        ) / 15.0
        measured_peak_lag_h: float | None = None
        if snapshot.env is not None and getattr(snapshot.env, "apparent_c", None):
            series = snapshot.env.apparent_c
            if len(series) == 24 and any(v is not None for v in series):
                peak_hour = max(
                    range(24),
                    key=lambda h: series[h] if series[h] is not None else -1e9,
                )
                measured_peak_lag_h = peak_hour - solar_noon_h

        closure = closure_analysis(
            surface_temperature_c=surface_c,
            air_temperature_c=air_c,
            irradiance_w_m2=irradiance,
            albedo=eff_albedo,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=h_c_street,
            storage_capacity_j_m2_k=slab_capacity,
            temperature_change_c=self.district.base_amplitude_c,
            time_span_hours=6.0,
            sky_temperature_c=radiative_env_c,
            latent_flux_w_m2=latent_flux,
        )

        sensitivity = sensitivity_bands(
            EquilibriumInputs(
                irradiance_w_m2=irradiance,
                albedo=eff_albedo,
                emissivity=EMISSIVITY_DEFAULT,
                convective_coefficient=h_c_street,
                air_temperature_c=air_c,
                radiative_environment_c=radiative_env_c,
                storage_flux_w_m2=budget.storage,
                latent_flux_w_m2=budget.latent,
            ),
            {
                "albedo": 0.02,
                "emissivity": 0.02,
                "convective_coefficient": 2.0,
                "irradiance_w_m2": 50.0,
                "radiative_environment_c": 2.0,
            },
        )
        equilibrium_c = round(
            equilibrium_surface_temperature_c(
                EquilibriumInputs(
                    irradiance_w_m2=irradiance,
                    albedo=eff_albedo,
                    emissivity=EMISSIVITY_DEFAULT,
                    convective_coefficient=h_c_street,
                    air_temperature_c=air_c,
                    radiative_environment_c=radiative_env_c,
                    storage_flux_w_m2=budget.storage,
                    latent_flux_w_m2=budget.latent,
                )
            ),
            1,
        )
        # Theory-vs-data verdict: the physics predicts a *skin*
        # temperature; the API layer may read as canopy/comfort
        # temperature instead. A tile at/below air temperature cannot
        # be sunlit skin — the residual is the layer-semantics offset.
        tile_excess = surface_c - air_c
        skin_excess = equilibrium_c - air_c
        if tile_excess <= 1.0:
            layer_verdict = (
                "API tile reads at or below air temperature — this layer "
                "behaves like canopy/comfort temperature, not sunlit skin; "
                "the physics predicts the skin temperature separately "
                f"({equilibrium_c:.0f} C, +{skin_excess:.1f} K above air). "
                "Skin temperature drives touch/WBGT impacts; the tile layer "
                "drives comfort impacts."
            )
        elif tile_excess >= 5.0:
            layer_verdict = (
                "API tile reads >5 K above air — behaves like a skin/"
                "surface layer; the equilibrium prediction and the tile "
                "should converge as inputs harden."
            )
        else:
            layer_verdict = (
                "API tile reads mildly above air — mixed canopy/surface "
                "layer; treat the equilibrium skin prediction as the "
                "upper physical bound."
            )

        interventions = self._prescribe(
            irradiance=irradiance,
            surface_c=surface_c,
            exceedance_hrs=exceedance_hrs,
            convective_coefficient=h_c_street,
            net_radiation=net_radiation,
            storage_flux=budget.storage,
            air_c=air_c,
        )

        # M4 — heat equity, productivity and the district cost of heat.
        # All from already-audited numbers: no new API calls, no new
        # physics beyond the documented Dunne (2013) / Kjellstrom (2009)
        # work-capacity curves and the ROI module's energy figures.
        equity_block = heat_burden(heatmap.tiles)
        wbgt_c = float(exposure["wbgt_c"])
        productivity_block = {
            "moderate": annualized_loss(wbgt_c=wbgt_c, intensity="moderate"),
            "heavy": annualized_loss(wbgt_c=wbgt_c, intensity="heavy"),
            "wbgt_c": round(wbgt_c, 2),
            "curve": "logistic parameterization of Dunne 2013 / Kjellstrom 2009",
        }
        roi_block = self._retrofit_roi(interventions[0])
        economy_block = district_cost_of_heat(roi_block, wbgt_c=wbgt_c)

        # Thermal-wind proxy (Wallace & Hobbs §7.2.7, Eq. 7.20) and the
        # downburst wet-bulb-depression diagnostic (Caracena 1990) —
        # both relative/caveated; both computed from data already fetched.
        thermal_wind_block = urban_circulation(heatmap.tiles, heatmap.mean)
        anomaly_block = detect_anomalies(heatmap.tiles, equilibrium_c=equilibrium_c)
        env_dict = {
            "hour": snapshot.env.hours if snapshot.env else None,
            "apparent_c": snapshot.env.apparent_c if snapshot.env else None,
            "wet_bulb_c": snapshot.env.wet_bulb_c if snapshot.env else None,
            "precipitation_mm": snapshot.env.precipitation_mm if snapshot.env else None,
        }
        downburst_block = downburst_risk_series(env_dict) if snapshot.env else {"present": False}

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
                "min_c": round(heatmap.min, 2),
                "mean_c": round(heatmap.mean, 2),
                "max_c": round(heatmap.max, 2),
                "hottest_tile": {k: round(v, 3) for k, v in hottest.items()},
            },
            "attribution": {
                "solar_flux": round(budget.absorbed_solar, 1),
                "longwave_flux": round(budget.net_longwave, 1),
                "convection_flux": round(budget.convection, 1),
                "storage_flux": round(budget.storage, 1),
                "latent_flux": round(budget.latent, 1),
                "net_flux": round(budget.net_flux, 1),
                "solar_share": round(attribution["solar_absorption"], 1),
                "longwave_share": round(attribution["net_longwave_retention"], 1),
                "convection_share": round(attribution["convection_suppression"], 1),
                "equilibrium_surface_temperature_c": equilibrium_c,
                "sensitivity": {
                    k: v for k, v in sensitivity.items()
                },
            },
            "canyon": {
                "aspect_ratio_h_over_w": self.district.h_over_w,
                "sky_view_factor": round(sky_view_factor(self.district.h_over_w), 3),
                "effective_albedo": round(eff_albedo, 3),
                "radiative_environment_c": (
                    round(radiative_env_c, 1) if radiative_env_c is not None else None
                ),
                "wind_shelter_factor": round(wind_shelter, 3),
                "street_level_h_c_w_m2k": round(h_c_street, 1),
            },
            "inertia": {
                "time_constant_hours": tau,
                "thermal_effusivity": round(effusivity, 1),
                "thermal_admittance": round(admittance, 1),
                "damping_depth_m": round(damping, 3),
                "ideal_peak_lag_hours": round(diurnal_phase_lag_hours(), 1),
                "measured_peak_lag_hours": (
                    round(measured_peak_lag_h, 1) if measured_peak_lag_h is not None else None
                ),
                "solar_noon_local_h": round(solar_noon_h, 2),
                "storage_flux_force_restore_w_m2": round(storage_force_restore, 1),
                "overnight_retention": round(retention, 3),
                "persistence_layer_max_hours": (
                    snapshot.persistence.max if snapshot.persistence else None
                ),
            },
            "atmosphere": {
                "air_temperature_c": round(air_c, 2),
                "wind_speed_m_s": round(wind, 2),
                "cloud_cover_pct": round(cloud_pct, 1),
                "relative_humidity_pct": round(humidity_pct, 1),
                "sky_temperature_c": round(sky_c, 1) if sky_c is not None else None,
                "convective_coefficient": round(h_c, 1),
                "street_level_convective_coefficient": round(h_c_street, 1),
            },
            "diurnal": self._diurnal_block(snapshot),
            "closure": closure,
            "theory_vs_data": {
                "measured_tile_c": round(surface_c, 2),
                "predicted_skin_c": equilibrium_c,
                "air_temperature_c": round(air_c, 2),
                "tile_excess_above_air_c": round(tile_excess, 1),
                "skin_excess_above_air_c": round(skin_excess, 1),
                "verdict": layer_verdict,
            },
            "exposure": {
                **exposure,
                "wbgt_c": round(exposure["wbgt_c"], 2),
            },
            "interventions": interventions,
            # Track 2 — retrofit economics: the top intervention's ΔT
            # converted into annual savings and payback (transmission
            # physics: U·A·DH·ΔT / COP). Assumptions are returned with
            # the numbers, not hidden.
            "retrofit_roi": self._retrofit_roi(interventions[0]),
            # Track 5 — packaged vulnerability model: composite score
            # (intensity + duration + sensitivity + dose) and the
            # WBGT worker-safety alert at the audit hour.
            "vulnerability": self._vulnerability_block(
                exposure, exceedance_hrs, hour_env, air_c, irradiance, wind
            ),
            "facade": facade_heat_load_ranking(
                self.district.lat,
                self.district.lon,
                _dt.date.fromisoformat(req.date).timetuple().tm_yday,
                self.district.utc_offset_hours,
                ground_albedo=eff_albedo,
            ),
            # M4 — equity, productivity, economy of the heat burden.
            "analysis": {
                "equity": equity_block,
                "productivity": productivity_block,
                "economy": economy_block,
                # M2 Sentinel (D6) — statistical anomaly flags over the tiles.
                "anomaly": anomaly_block,
            },
            "thermal_wind": thermal_wind_block,
            "downburst": downburst_block,
            "provenance": (
                f"temperature layer: {snapshot.source}; "
                f"env series: {snapshot.env.source if snapshot.env else 'n/a'}; "
                f"equations: Stefan-Boltzmann with Brutsaert sky (humidity + cloud) "
                f"blended for street-canyon walls (Oke et al. Eq. 5.18 + sky view "
                f"factor), Newton's law (wind-aware h_c, canyon-sheltered to street "
                f"level), force-restore storage (thermal admittance), "
                f"Priestley-Taylor latent cooling (α=1.26), "
                f"equilibrium solve + sensitivity bands, "
                f"WBGT = 0.7T_wb+0.2T_g+0.1T_db (globe from solar load); "
                f"M4: Gini/quintile-gap equity, Dunne 2013 work-capacity curves, "
                f"thermal-wind proxy (Wallace & Hobbs §7.2.7 Eq. 7.20), "
                f"downburst wet-bulb-depression diagnostic (Caracena 1990); "
                f"ML: IsolationForest + 2σ z-scores for tile anomalies; units: °C"
            ),
            "warnings": snapshot.warnings,
        }
        if narrate:
            report["narrative"] = self.narrator.narrate(report)
        return report

    # ------------------------------------------------------------ prescribe

    def _prescribe(
        self,
        irradiance: float,
        surface_c: float,
        exceedance_hrs: float,
        convective_coefficient: float = CONVECTIVE_COEFFICIENT,
        net_radiation: float = 0.0,
        storage_flux: float = 0.0,
        air_c: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Ranked interventions with quantified °C, best first."""
        albedo_old = self.district.albedo
        cool = albedo_delta_temperature(
            irradiance_w_m2=irradiance,
            albedo_before=albedo_old,
            albedo_after=0.60,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=convective_coefficient,
        )
        trees = shade_delta_temperature(
            irradiance_w_m2=irradiance,
            albedo=albedo_old,
            shade_fraction=0.50,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=convective_coefficient,
        )
        concrete = albedo_delta_temperature(
            irradiance_w_m2=irradiance,
            albedo_before=albedo_old,
            albedo_after=0.35,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=convective_coefficient,
        )
        # Evaporative green surfaces: the latent flux a 50%-wetted canopy
        # would draw from the available energy (Priestley-Taylor).
        green = priestley_taylor_latent_flux(
            net_radiation_w_m2=net_radiation,
            ground_flux_w_m2=storage_flux,
            air_temperature_c=air_c,
            evaporative_fraction=0.5,
        )
        green_drop = temperature_drop_from_flux_removal(
            removed_flux_w_m2=green,
            surface_temperature_c=surface_c,
            emissivity=EMISSIVITY_DEFAULT,
            convective_coefficient=convective_coefficient,
        )
        interventions = [
            {
                "name": "Cool roofs on hottest tiles (albedo 0.12→0.60)",
                "delta_t_c": cool["delta_temperature_c"],
                "removed_flux_w_m2": cool["removed_flux_w_m2"],
                "basis": (
                    f"ΔT = Δα·G/H at G={irradiance:.0f} W/m², "
                    f"H from Stefan-Boltzmann + h_c={convective_coefficient:.1f}"
                ),
                "scope": "top 20% tiles by peak temperature",
            },
            {
                "name": "Street-tree shade canopy (50% coverage)",
                "delta_t_c": trees["delta_temperature_c"],
                "removed_flux_w_m2": trees["removed_flux_w_m2"],
                "basis": "ΔT = s·(1−α)·G/H; latent cooling credited separately below",
                "scope": "high-exposure streets",
            },
            {
                "name": "Reflective pavement (albedo 0.12→0.35)",
                "delta_t_c": concrete["delta_temperature_c"],
                "removed_flux_w_m2": concrete["removed_flux_w_m2"],
                "basis": "same lever equation, smaller Δα",
                "scope": "all district roads",
            },
            {
                "name": "Green roofs on hottest tiles (50% evaporative cover)",
                "delta_t_c": green_drop,
                "removed_flux_w_m2": green,
                "basis": (
                    f"Priestley-Taylor λE = α·s/(s+γ)·(Q*−G) at "
                    f"f_evap=0.5, Q*−G={net_radiation - storage_flux:.0f} W/m², "
                    "α=1.26 (Monteith & Unsworth Ch. 13)"
                ),
                "scope": "top 20% tiles by peak temperature",
            },
        ]
        interventions.sort(key=lambda iv: iv["delta_t_c"], reverse=True)
        return [
            {**iv, "delta_t_c": round(iv["delta_t_c"], 2)} for iv in interventions
        ]

    # ---------------------------------------------------------- track 2 / 5

    def _diurnal_block(self, snapshot: Any) -> dict[str, Any]:
        """24 h apparent-temperature + solar series for the PDF chart.

        Kept out of the audit math (aggregates only); present for
        visualization. None values (missing live hours) stay None.
        """
        block: dict[str, Any] = {"hours": list(range(24))}
        if snapshot.env is not None:
            if getattr(snapshot.env, "apparent_c", None):
                block["apparent_c"] = [
                    round(v, 2) if v is not None else None
                    for v in snapshot.env.apparent_c
                ]
            if getattr(snapshot.env, "solar_w_m2", None):
                block["solar_w_m2"] = [
                    round(v, 1) if v is not None else None
                    for v in snapshot.env.solar_w_m2
                ]
        return block

    def _retrofit_roi(self, top_intervention: dict[str, Any]) -> dict[str, Any]:
        """Annual savings / payback for the top intervention.

        One 20×20 m tile (400 m²) of cool-roof coating at ~$25/m², with
        the district's cooling-season degree-hours from its hot-season
        mean (proxy, documented). The ΔT is the intervention's peak
        reduction applied across the sunlit cooling hours embedded in
        the degree-hour estimate.
        """
        degree_hours = cooling_degree_hours(self.district.base_mean_c)
        roi = retrofit_roi(
            degree_hours_c=degree_hours,
            delta_t_c=top_intervention["delta_t_c"],
            envelope_area_m2=400.0,
            retrofit_cost_usd=400.0 * 25.0,
        )
        roi["intervention"] = top_intervention["name"]
        roi["cooling_season_degree_hours_c"] = round(degree_hours, 0)
        return roi

    def _vulnerability_block(
        self,
        exposure: dict[str, Any],
        exceedance_hrs: float,
        hour_env: dict[str, Any],
        air_c: float,
        irradiance: float,
        wind: float,
    ) -> dict[str, Any]:
        """Composite vulnerability score + worker-safety alert."""
        dose = exposure.get("dose", {}) or {}
        above = dose.get("above_threshold_c_hours") or 0.0
        score = heat_vulnerability_score(
            wbgt_c=exposure["wbgt_c"],
            exceedance_hours=exceedance_hrs,
            above_threshold_c_hours=above,
        )
        alert = worker_safety_alert(
            wet_bulb_c=hour_env["wet_bulb_c"],
            dry_bulb_c=air_c,
            irradiance_w_m2=irradiance,
            wind_speed_m_s=wind,
            work_intensity="moderate",
        )
        return {"score": score, "safety_alert": alert}


def _effusivity_for(albedo: float) -> float:
    """Rough effusivity proxy from the material table (W·s^0.5/m²K)."""
    from .physics.inertia import thermal_effusivity

    props = MATERIALS["vegetation"] if albedo >= 0.28 else MATERIALS["gray_concrete"]
    if props is MATERIALS["vegetation"]:
        return thermal_effusivity(0.5, 700.0, 1450.0)
    return thermal_effusivity(1.4, 2200.0, 900.0)