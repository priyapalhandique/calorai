"""Narrator — turns the deterministic audit into natural language.

The auditor's numbers are computed by physics + FortyGuard data and
never change based on the narrator. This layer only *writes the prose*
over a finished structured report, with a cascade of backends:

1. ``TemplateNarrator`` — deterministic markdown from the report. Always
   available, zero API keys, zero cost.
2. ``GitHubModelsNarrator`` — a free LLM (GitHub Models tier, needs a
   Personal Access Token with Models permission in ``GITHUB_MODELS_TOKEN``
   or ``GITHUB_TOKEN``) that rewrites the same content in livelier prose.
   Any failure falls back to the template silently.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

TEMPLATE_INTRO = """# {district} — Heat-Budget Audit ({date})

{one_liner}

> Source: {source} · {pipeline}

## 1. Thermal snapshot

At {hour:02d}:00 the district's {n_cells}-cell heatmap reads {min_c}–{max_c} °C
(mean {mean_c} °C, spread {spread_c} °C). {spread_note}

## 2. Why it is hot — energy balance attribution

At the audit hour the surface energy balance was dominated by:

| Mechanism | Share of load | Flux |
|---|---|---|
{attribution_rows}

{attribution_sentence}

## 3. Overnight persistence — thermal inertia

With an effective cooling time constant of {tau_c} hours, an estimated
{overnight_pct:.0f}% of the day's excess heat lingers past nightfall.
{persistence_sentence}

## 4. Human exposure — WBGT and duration

At the hot hour: WBGT {wbgt_c} °C ({risk_level}) — {risk_guidance}. The
{threshold_c:.0f} °C threshold was exceeded on average {exceedance_hrs:.1f}
hours per cell of the audit day ({duration_risk} duration risk).

## 5. Ranked interventions

| Rank | Intervention | Est. relief | Basis |
|---|---|---|---|
{intervention_rows}

## 6. Audit trail

- Every °C above traces to a physics equation and an API payload; no
  number is guessed.
- Equations: Stefan-Boltzmann Q_rad = εσA(T⁴−T_amb⁴); Newton cooling
  Q = h_c(T_s−T_air); albedo lever ΔT = Δα·G/H; WBGT = 0.7T_wb+0.3T_db.
- Units: °C throughout (API-native unless noted).
- {provenance}
{warnings_section}
"""


class Narrator(Protocol):
    """Something that renders a structured audit report as text."""

    def narrate(self, report: dict) -> str:
        ...


class TemplateNarrator:
    """Deterministic markdown narrator — the always-on backend."""

    name = "template"

    def narrate(self, report: dict) -> str:
        try:
            return self._render(report)
        except KeyError:
            return json.dumps(report, indent=2, default=str)

    @staticmethod
    def _render(r: dict) -> str:
        snapshot = r["snapshot"]
        attribution = r["attribution"]
        inertia = r["inertia"]
        exposure = r["exposure"]
        interventions = r["interventions"]

        spreads = snapshot["max_c"] - snapshot["min_c"]
        spread_note = (
            f"The {spreads:.1f} °C spread inside one district is the heat-island "
            "signature — the exact pattern physics can attribute."
            if spreads > 2.0 else
            "A tight spread: this district behaves as one thermal unit."
        )
        attribution_rows = "\n".join(
            f"| {label.replace('_', ' ').title()} | {share:.0f}% | {flux:+.0f} W/m² |"
            for label, share, flux in (
                ("solar_absorption", attribution["solar_share"], attribution["solar_flux"]),
                ("longwave_retention", attribution["longwave_share"], attribution["longwave_flux"]),
                ("convection_suppression", attribution["convection_share"], attribution["convection_flux"]),
            )
        )
        if attribution["solar_share"] >= 50.0:
            att_sentence = (
                "Solar loading is the dominant mechanism — the district is hot "
                "because it absorbs more shortwave than it can shed. Albedo is "
                "the lever physics points to first."
            )
        else:
            att_sentence = "The load is distributed across mechanisms; no single lever dominates."

        persistence_sentence = (
            "High overnight retention means daytime interventions also cool "
            "the night, not just the peak hour."
            if inertia["overnight_retention"] > 0.3 else
            "This district sheds its heat quickly — interventions should target "
            "the daytime peak directly."
        )
        intervention_rows = "\n".join(
            f"| {i + 1} | {iv['name']} | −{iv['delta_t_c']:.1f} °C | {iv['basis']} |"
            for i, iv in enumerate(interventions)
        )
        warnings_section = ""
        if r.get("warnings"):
            warnings_section = "\n> Caveats: " + "; ".join(r["warnings"])
        return TEMPLATE_INTRO.format(
            district=r["district"],
            date=r["date"],
            one_liner=r["one_liner"],
            source=r["source"],
            pipeline=r["pipeline"],
            hour=snapshot["hour"],
            n_cells=snapshot["n_cells"],
            min_c=snapshot["min_c"],
            max_c=snapshot["max_c"],
            mean_c=snapshot["mean_c"],
            spread_c=spreads,
            spread_note=spread_note,
            attribution_rows=attribution_rows,
            attribution_sentence=att_sentence,
            tau_c=inertia["time_constant_hours"],
            overnight_pct=inertia["overnight_retention"] * 100.0,
            persistence_sentence=persistence_sentence,
            wbgt_c=exposure["wbgt_c"],
            risk_level=exposure["level"],
            risk_guidance=exposure.get("guidance", ""),
            threshold_c=exposure["threshold_c"],
            exceedance_hrs=exposure["exceedance_hours"],
            duration_risk=exposure["duration_risk"],
            intervention_rows=intervention_rows,
            provenance=r["provenance"],
            warnings_section=warnings_section,
        )


class GitHubModelsNarrator:
    """Free-tier LLM narrator via GitHub Models (Azure AI Foundry).

    Needs a GitHub Personal Access Token with the *Models* permission:
    set ``GITHUB_MODELS_TOKEN`` (or fall back to ``GITHUB_TOKEN``).
    Best-effort: any failure (no token, quota, network) falls back to the
    template narrator — the audit never depends on this backend.
    """

    name = "github-models"

    BASE_URL = "https://models.github.ai/api/inference"

    def __init__(self, model: str = "gpt-4o-mini", timeout: float = 60.0) -> None:
        self.model = model
        self.timeout = timeout
        self._token: str | None = os.getenv("GITHUB_MODELS_TOKEN") or os.getenv("GITHUB_TOKEN")
        self._fallback = TemplateNarrator()

    def narrate(self, report: dict) -> str:
        if not self._token:
            return self._fallback.narrate(report)
        try:
            return self._call(report)
        except Exception:
            return self._fallback.narrate(report)

    def _call(self, report: dict) -> str:
        import requests

        system = (
            "You are the reporting engine of calorai, a physics-first urban "
            "heat-budget auditor. The numbers below were computed "
            "deterministically from physics equations and the FortyGuard "
            "Temperature API. NEVER invent, change, round, or reinterpret a "
            "number. Write a crisp, readable audit report in Markdown using "
            "exactly the values given. Markdown headings, one table for "
            "interventions, and a short 'Audit trail' section at the end. "
            "No preamble, no conclusion beyond the report."
        )
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(report, default=str)},
            ],
            "temperature": 0.2,
            "max_tokens": 1200,
        }
        resp = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def make_narrator(kind: str | None = None) -> Narrator:
    """Factory: 'template' (default), 'github-models', or auto-cascade."""
    if kind == "template":
        return TemplateNarrator()
    if kind == "github-models":
        return GitHubModelsNarrator()
    if kind in (None, "auto"):
        return GitHubModelsNarrator()  # internally falls back to template
    raise ValueError(f"unknown narrator kind {kind!r}")