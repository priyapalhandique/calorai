# FortyGuard products & improvement recommendations (inventory + evidence)

Research snapshot 2026-08-18 from fortyguard.com (/products, /api-pricing, FAQ, case studies)
and **live API behavior** (Hackathon plan key) during the calorai build.
Companion doc: `docs/fortyguard-api-reference.md` (extracted API reference).

---

## 1. Who they are / tech

- **tOS** — "Temperature Operating System", the core AI engine (data → heatmaps → analytics → insights)
- **LTMs** — Large Temperature Models trained on years of data for macro-scale prediction
- **tCMap™** — Temperature Classification Mapping: NxN-meter² tile temperature layers
- **TaaS** — Temperature as a Service (the business model)
- Marketing claims: 52B temperature data points/day, 2 m granularity (up to 10 m² described on MS marketplace),
  "115x more accurate", NVIDIA recognition, listed on Google Cloud + Microsoft AppSource + DHL programs
- Offices: San Jose CA (Riverpark Tower) + Abu Dhabi ADGM Hub71

## 2. Product lineup

| Product | What it is | Price/access |
|---|---|---|
| **Temperature Dashboard®** | Browser app: real-time/historical/predictive heat maps, time-series player, comparisons, per-tile Heat Intelligence. Free access. Mobile version "currently working on"; software integrations likewise in progress | Free (login at dashboard.fortyguard.com) |
| **Temperature API®** | Programmatic access to tOS: `/v1/heatmap`, `/v1/env_params`, `/v1/satellite`, `/v1/streetview`, `/v1/heat_intelligence`, `/v1/status/{activity_id}`, `/v1/system/fetch-api-key-usage` | Basic $79 / Pro $289 / bulk packs / Startup & Hackathon programs |
| **Temperature Property®** | property.fortyguard.com — input coordinates → tailored property heat report via "advanced prompts" (ESG + financial risk angle) | Marketed to real estate/EPC |
| **Advisory Projects** | Bespoke studies (e.g., Masdar City assessment, Greater Tripoli, DATS data-center screens) | Custom quote |

API plans (pricing page ground truth):

| | Basic $79/mo | Pro $289/mo |
|---|---|---|
| Credits | 1,000,000/mo | 5,000,000/mo |
| Heatmap AOI | ≤ 10 mi² | ≤ 50 mi² |
| Map Statistics | ✓ advertised | ✓ |
| Env parameters | ≤ 3 per request | full access |
| Satellite / Street View segmentation | — | ✓ |
| Heat Intelligence | — | 2 of 5 report types |

Bulk credit packs 100k/250k/500k from $7.99 (Basic rate) / $5.99 (Pro). Annual billing = 20% off,
lump-sum refundable ≤14 days, monthly non-refundable. Credits reset each cycle (no rollover).
Industries: urban systems (gov/municipalities, developers/smart cities, EPC, architects, policy), enterprise
(logistics, insurance/finance, manufacturing, risk), energy (data centers & nuclear, O&G, utilities).

## 3. Improvement recommendations (ranked, evidence-led)

Priority P1 = we hit it during live development; P2 = visible inconsistency; P3 = developer-experience polish.

### P1-1. Map Statistics is advertised but the payload is empty
Pricing page lists Map Statistics on Basic; docs promise `stats_data` (tcm, exceedance, persistence
analytics); **live `/v1/status` returns `stats_data` = only `activity_id` + `n_cells`** — no statistics.
Either ship the promised statistics or rename the field to `metadata` so clients don't build on thin air.
*Evidence: live Phoenix run 2024-07-15; docs §analytics in `fortyguard-api-reference.md`.*

### P1-2. `solar_irradiance` env parameter is a single clear-sky scalar, not a series
`/v1/env_params` returns `solar_irradiance` as one `ghi` value (577 W/m² clear-sky), so consumers who
need the solar diurnal cycle (radiation budget modeling, HVAC sizing, solar-cooker siting) must synthesize
the curve themselves — we built a solar-geometry re-synthesis in calorai to compensate.
Recommendation: return a 24-h `ghi` (optionally `dni`/`dhi`) series, or rename the field to
`clear_sky_ghi_scalar` and document that it is not a time series.
*Evidence: live env payload (source=live, 2024-07-15).*

### P2-1. Date-range story is inconsistent across channels
- Microsoft marketplace: "historical data 2014–2024"
- API docs site: `2019-01-01 → now + 12 h`
- Participant handbook: `2021-01-01 → now (no future)`
- Live: dates outside catalog coverage return a **success with 0 cells** — indistinguishable from an
  empty/uncovered area. Recommend explicit coverage error code (e.g., `date_out_of_range`) and one
  canonical date-range statement in docs.
*Evidence: 2026-08-18 request → 0 cells, status success; handbook OCR + docs-grid extraction.*

### P2-2. Premium-only env parameters silently return all-`null` arrays on non-premium plans
`co2_ppm` etc. appear as 24 x `null` on the Hackathon plan instead of being omitted. Recommend omitting
unavailable parameters (or a clean `omitted` flag) so clients can detect them cheaply.
*Evidence: live env payload.*

### P2-3. `filter_type` semantics diverge between handbook and docs site
Handbook documents `filter_type 5` (single month); docs site lists 1–4 only. Analytics types
(`tcm`/`time_of_measure`/`exceedance`/`persistence`) are sparse in both. Recommend a single canonical
reference (curated API docs we extracted demonstrate it can be a ~100-line markdown file).

### P2-4. No wind-speed parameter — and cloud units are mislabeled
Full default `env_params` probe (2026-08-18, no `analysis` restriction) returns 15 parameter
families — **wind speed is not among them**, which blocks convective modeling (we fall back to a
calm-conditions coefficient and exercise wind physics only in our mock). Meanwhile
`cloud_cover_octas` ships 0–100 *percent* values under an octas name (e.g. 43, 98, 85 within the
same night), and `elevation`/`methane_ppb`/`co2_ppm` come back empty on the Hackathon plan.
Recommend a `wind_speed_m_s` series (the sky model and convective losses are the largest single
sources of uncertainty in urban heat budgets) and either octas 0–8 or percent semantics, clearly
named.
*Evidence: probe payload `probe_env_full.json`; live env cache.*

### P3-1. Docs are a heavy Angular SPA; no curl-able reference
The entire API reference lives in a 1.6 MB JS bundle behind `docs-api.fortyguard.com/docs`. A static
markdown/OpenAPI reference would remove a huge hurdle for the developer personas you advertise.
*Evidence: `main.108dec8185160983.js` 1,609,045 bytes.*

### P3-2. No credit-cost preview before committing
Credits are a paid resource and don't roll over, but a POST returns no estimated cost until the task
finishes. A `credit_estimate` field in the response (and documented cost per granularity × AOI) would
help budget-conscious builders use the API more.
*Evidence: pricing FAQ + live `fetch-api-key-usage`.*

### P3-3. Heat Intelligence PDF arrives as a temporary signed link
`/v1/heat_intelligence` returns a temp-expiring download URL. Direct attachment-style delivery (or a
long-lived download endpoint keyed by `activity_id`) would fit automated pipelines better.

## 4. What works well (balanced feedback)

- Failed tasks are **free** — probe-culture friendly; credits only on success
- `null`, not `-999`, for missing values — clean JSON contract
- Bounded polling with 429-sense retry handling is reasonable
- Stable payload shapes → SHA-256 disk caching works perfectly (our repeat calls cost 0 credits)
- `fetch-api-key-usage` is a free, thoughtful endpoint for budget transparency

## 5. How calorai used/uses the API (relevance)

1. `POST /v1/heatmap` (Basic, tcm) → per-tile °C layers for the energy-balance engine
2. `POST /v1/env_params` (Basic) → air temp, humidity, wet-bulb, **cloud cover, precipitation** +
   **beam/diffuse solar split anchored to the real dni/dhi scalar ratio**
3. `GET /v1/status` → polling + **n_cells** for coverage QA
4. `GET /v1/system/fetch-api-key-usage` → budget dashboard in the UI
5. Whole pipeline is auditable (every live call logged with credits) — matches Track 6 agentic brief

Deliverable: this list is submitted to the organizers with the project (Dashboard feedback form +
README + 500-word summary) as the "we lived in your API" contribution.