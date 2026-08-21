# calorai Roadmap and Boundaries

This document records useful next scopes without turning them into shipped
claims. The hackathon submission stays focused on one district, one heat
problem, three interventions, and an auditable agent trace.

## Shipped Scope

- District heat-budget audit from FortyGuard heatmap/env layers or mock data.
- Physics attribution, WBGT, vulnerability, equity, productivity, economy,
  facade, anomaly, thermal-wind proxy, downburst diagnostic, landcover and
  synoptic blocks.
- Natural-language agent with deterministic fallback and visible tool trace.
- PDF report and GeoJSON/CSV export package.
- Mock-first operation for fresh clones and incognito judging.

## Short-Term Extensions

| Scope | What it would need | Why not shipped now | Hook |
|---|---|---|---|
| Multi-day heat-wave validation | 3-7 catalog-proven dates per district, env + tcm cache | Credits and submission focus | `scripts/validate_live.py`, `analyst/synoptic.py` |
| Census/ACS equity overlay | External ACS tables, tract join, citation and redistribution review | Avoid unreviewed external data in the core demo | `analyst/equity.py` |
| Bus-stop shade ranking | OSM/GTFS stop list, sidewalk geometry, shade assumptions | Needs local transit data QA | `physics/canyon.py`, `interop.py` |
| Phoenix parcel live evidence | Approved street-view + satellite pulls for a Phoenix parcel | Premium endpoint credit gate | `analyst/landcover.py`, `data/satellite/`, `data/street_view/` |
| City comparison live set | Vegas, Manhattan/NYC, optional Dallas coverage probes | User-gated credit spend | `docs/location-analysis.md` |

## Mid-Term Product Ideas

- Parcel portfolio screening at scale, using one AOI for many parcels and
  spending premium segmentation only on top candidates.
- Facade seasonality advisor for building owners: when each orientation needs
  shade, glass treatment, or roof intervention.
- Work-rest scheduler for crews by WBGT, intensity, and shift length.
- Daily monitoring brief across districts with alert escalation payloads.
- Real mist-system integration once hardware and valve telemetry exist.

## Out of Scope for This Submission

| Topic | Boundary |
|---|---|
| Cyclone coupling | Needs synoptic pressure, SST, steering flow, and storm track data not present in the API layer. |
| Downburst forecasting | The project ships a thermodynamic diagnostic only; forecasting needs radar, CAPE, vertical wind profile, and nowcasting data. |
| Energy-grid demand coupling | Would require utility load curves, building stock, tariff schedules, and calibration. |
| Insurance risk pricing | Would require actuarial loss data and regulatory review. |
| Real IoT actuation | The responder produces a schedule and water budget, not hardware control. |
| Direct tcm forecasting | The ML model reproduces physics; it is not calibrated as a direct tcm tile-layer forecaster. |

## Operating Principle

Every future feature should keep the current discipline: cache-first, no secrets
in git, mock-safe tests, explicit credit approval for live pulls, and honest
labels whenever a value is a proxy rather than an observation.
