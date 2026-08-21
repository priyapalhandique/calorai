# My Contributions to FortyGuard

*FortyGuard Hackathon'26 · "Building the World's Temperature AI" · Solo entry — Priyapal Handique, the calorai project.*

This document records what I contributed back to FortyGuard during the build. I did not review the product from the brochure — I lived in the API: 7 endpoints exercised, about 208,240 of 2,000,000 credits spent on real requests by the latest ledger, and a 27-page Heat Intelligence premium probe at Phoenix. Everything below is evidence-led and verifiable in the repository (`docs/fortyguard-products.md` holds the full inventory and payload evidence).

---

## 1. Live API findings (bugs and behaviors discovered)

| # | Finding | Evidence |
|---|---|---|
| F1 | Requests for dates outside catalog coverage return **success with 0 cells** — indistinguishable from an empty area; no coverage error code | 2026-08-18 request → 0 cells, status success |
| F2 | **Map Statistics is advertised but empty**: `/v1/status` returns `stats_data` containing only `activity_id` + `n_cells`, no statistics | Live Phoenix run 2024-07-15 |
| F3 | `solar_irradiance` env parameter is a **single clear-sky scalar** (one `ghi` value), not the 24-h series consumers need for radiation-budget modeling; I built a solar-geometry re-synthesis to compensate | Live env payload, 2024-07-15 |
| F4 | **No wind-speed parameter** in the 15 parameter families probed — the largest single source of uncertainty in urban heat budgets stays unobservable (I fall back to calm conditions) | Full env probe, no `analysis` restriction |
| F5 | `cloud_cover_octas` ships **0–100 percent values under an octas name** (e.g. 43, 98, 85 within one night) | Live env payload |
| F6 | Premium-only env parameters (e.g. `co2_ppm`) silently return **all-`null` arrays** on non-premium plans instead of being omitted | Live env payload |
| F7 | The credit-usage response schema was not documented; I **reverse-discovered it from the SPA bundle** (nested `plan_details` / `credit_summary` / `activity_breakdown`; key `total_available_credits`) and verified it against the docs tracker | `fortyguard/client.py` + live probes |
| F8 | Heat Intelligence PDFs arrive as **temporary expiring signed links**, awkward for automated pipelines | `/v1/heat_intelligence` probe |

## 2. Improvement recommendations (8, ranked)

| Priority | Recommendation |
|---|---|
| P1-1 | Ship the promised Map Statistics or rename `stats_data` to `metadata` so clients don't build on thin air |
| P1-2 | Return a 24-h `ghi` (optionally `dni`/`dhi`) series for `solar_irradiance`, or rename it `clear_sky_ghi_scalar` |
| P2-1 | One canonical date-range statement across marketplace/docs/handbook + a `date_out_of_range` error code |
| P2-2 | Omit unavailable premium parameters (or add a clean `omitted` flag) instead of all-`null` arrays |
| P2-3 | A single canonical API reference — handbook `filter_type 5` vs docs-site 1–4 diverge |
| P2-4 | Add a `wind_speed_m_s` series; ship octas 0–8 or percent semantics, clearly named |
| P3-1 | Publish a static markdown/OpenAPI reference — the docs are a 1.6 MB Angular SPA bundle |
| P3-2 | Add a `credit_estimate` field to POST responses (credits don't roll over; cost is unknown until the task finishes) |
| P3-3 | Deliver Heat Intelligence as an attachment or a long-lived download keyed by `activity_id` |

## 3. What works well (balanced feedback)

- Failed tasks are **free** — probe-culture friendly; credits only charge on success
- `null`, not `-999`, for missing values — a clean JSON contract
- Stable payload shapes — my SHA-256 disk cache makes repeat calls cost **0 credits**
- `fetch-api-key-usage` is a free, thoughtful endpoint for budget transparency
- Bounded async polling with sensible retry handling

## 4. My real usage footprint

| Endpoint | Use | Cost |
|---|---|---|
| `POST /v1/heatmap` (tcm) | Per-tile °C layers feeding the energy-balance engine | 9 calls · 38.0k credits |
| `POST /v1/env_params` | Air temp, humidity, wet-bulb, cloud, solar split anchored to real dni/dhi | 11 calls · 31.9k credits |
| `GET /v1/status` | Polling + `n_cells` coverage QA | free |
| `GET /v1/system/fetch-api-key-usage` (+custom) | Budget dashboard, schema verification | free |
| `POST /v1/heat_intelligence` | Premium capability probe — 27-page PDF at Phoenix | 1 call · 8.6k credits |

Every live call is logged with its credit cost in the auditable pipeline — the agentic-track brief taken literally.

---

*Companion: `docs/fortyguard-products.md` (full inventory, payload evidence, and the recommendations in depth). This list is submitted to the organizers with the project (Dashboard feedback form + README) as the "we lived in your API" contribution.*
