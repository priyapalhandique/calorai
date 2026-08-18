# FortyGuard API — developer reference (extracted from docs-api.fortyguard.com)

Source: the SPA bundle served at `docs-api.fortyguard.com/docs` (2026-08-18).
This is the docs-site content in condensed form; wire behavior verified against the **Hackathon** plan key.

## 1. Authentication

- Every request sends `api-key: YOUR_API_KEY` as a header. No OAuth/token exchange.
- Base URL: `https://api.fortyguard.com` (docs are served from `docs-api.fortyguard.com`).
- Failed tasks are **free** — credits are deducted only on successful task completion.
- Unused credits do **not** roll over; they reset on the billing-cycle date.

## 2. Plans

| Plan | Credits | Heatmap AOI | Env params | Extras |
|---|---|---|---|---|
| API Basic | 1,000,000 / month | ≤ 10 mi² | ≤ 3 per request | full Map Statistics, commercial license |
| API Premium | 5,000,000 / month | ≤ 50 mi² | all | satellite, streetview, heat intelligence, Temperature Property API |
| Startup | — | ≤ 10 mi² | ≤ 3 per request | — |
| Hackathon (ours) | 2,000,000 one-time (2026-08-18 → 09-22) | confirmed 3 km works | **returned full set in practice** | — |

## 3. Endpoints

### POST /v1/heatmap — Heatmap Generation

Payload:

| Field | Type | Notes |
|---|---|---|
| `polygon_aoi` | GeoJSON FeatureCollection | Polygon of `[lon, lat]`, ring closed (first == last point) |
| `date_time.start_date` | string | YYYY-MM-DD |
| `date_time.start_time` | string | HH:MM 24 h |
| `date_time.end_date` | string | required for filter_type 4; auto-populated 1–3 |
| `date_time.end_time` | string | required for filter_type 2; auto-calculated for 1 (`start_time + 1h`) |
| `date_time.filter_type` | int | **1** Single Hour (needs start_date+start_time); **2** Range of Hours same day (+end_time); **3** Single Day (only start_date; covers 00:00–23:59 UTC+offset); **4** Range of Days, week/month, ≤ 1 month (+end_date) |
| `granularity` | int | 60 / 80 / 100 m (smaller = finer = more credits) |
| `analytic_type` | string | `tcm` (default; °C per tile), `time_of_measure` (peak hour 0–23 UTC), `exceedance` (hours above threshold), `persistence` (longest continuous run past threshold). Analytics return hours (`stats_data.units = "hour"`); tcm returns °C |
| `threshold` | float | °C for exceedance/persistence, default 30 °C; ignored by tcm/time_of_measure |
| `direction` | string | `'above'` (default) or `'below'`; ignored by tcm/time_of_measure |

Result (`stats_data` per docs — "Map Statistics"):
- `Temperature_stats` — minimum / maximum / mean / standard deviation across tiles
- `Overall_temperature_distribution` — sorted temperature array
- `Normal_temperature_distribution` — {x_axis, y_axis} probability density
- `Temperature_frequency` — histogram-style frequency counts per temperature bin
- plus `map_data` = GeoJSON tiles.
  ⚠️ **Docs-vs-live gap:** live completions on the Hackathon plan return `stats_data` with only `activity_id` + `n_cells` (no statistics). We compute min/mean/max from tiles — the doc schema is aspirational for this plan.

### POST /v1/env_params — Environmental Parameters

Payload: `latitude`, `longitude`, `temperature` (°C ambient anchor), `date_time {start_date, start_time, filter_type}`.

- `analysis`: *"Optional list of environmental parameters to return. **Omit to receive all of them. API Basic and API Startup are limited to 3 parameters per request; API Premium has full access.**"* (We pass a list and receive the full set on Hackathon plan.)
- Parameter catalog (verified field names):
  - Thermal & atmospheric: `heat_index_celsius`, `apparent_temperature_celsius`, `wet_bulb_temperature_celsius`, `relative_humidity_percent`, `precipitation_mm`, `cloud_cover_octas`, `elevation`
  - Air quality (US AQI) & gases: `air_quality:idx`, `air_quality_pm2p5:idx`, `air_quality_pm10:idx`, `air_quality_no2:idx`, `aqi_us_co`, `air_quality_o3:idx`, `air_quality_so2:idx`, `methane_ppb`, `co2_ppm`
  - Solar: `solar_irradiance` (clear-sky GHI / DNI / DHI)
- Result: `metadata {timezone, timezone_offset_hours, time_range, timestamps[]}`, `locations[0] {lat, lon, elevation, temperature, parameters{name → 24-h array}, solar_irradiance{clear_sky {ghi,dni,dhi}, description}}`.
- Missing values: **new missing numerics are JSON `null`**; older stored responses may contain legacy `-999`; null means unavailable — **never interpret as zero**.
- Noted from the docs CSV sample (San Jose example): tile properties in *cached* sample data are °F; live tcm is °C.

### POST /v1/satellite — Satellite Segmentation (Premium)

Payload: `sat {latitude, longitude}`, `date_time`, `granularity` (60/80/100).
Result: location metadata; `original_image` (Base64, may need `data:image/png;base64,` prefix); `segmentation` with `segments` (class coverage %), `image_legend` (RGB legend), `image_content` (Base64 mask), `image_dimensions {height,width}`, `mode`, `processing_time_seconds`, `request_id`, imagery `year`.

### POST /v1/streetview — Street View Segmentation (Premium)

Payload: `latitude`, `longitude`, `vertical_angle` (tilt °), `horizontal_angle` (pan °, 0–360), `back_view` (bool).
Result: `original_image`, `segments`, `image_legend`, `segmented_image` (all Base64-ish), `image_date` (YYYY-MM-DD).

### POST /v1/heat_intelligence — Heat Intelligence Reports (Premium)

Payload: `latitude`, `longitude`, `temperature` (°C), `date`, `analysis` (categories: geographic / environmental / urban / events / anthropogenic).
Result: status endpoint returns `data.result.download_link` (JSON, not a PDF stream). The link is a **temporary signed URL** — use immediately, don't log/share, stop polling once Completed, `Failed` is terminal, generation can take minutes.

### GET /v1/status/{activity_id}

Unified status/result retrieval for every asynchronous submission. Terminal states: `succeeded` / `completed` (result in `data.result`), `failed` / `error` (free task).

### POST /v1/system/fetch-api-key-usage and fetch-api-key-custom-usage

Credit usage at billing-cycle and custom date-range granularity (`{"start_date": ..., "end_date": ...}`).

## 4. Global constraints (Known Limitations page)

- **US-only coverage** in the current release; out-of-country coordinates rejected.
- Dates: **2019-01-01 → now + 12 h** forecast (docs site value; the handbook states 2021-01-01 — the *lowest* of the two is what's safe; both verified fine for 2024-07-15). Out-of-range → 400 Bad Request.
- Satellite/streetview/env/heat-intelligence dates should match the heatmap date/time for the same location.
- AOI caps: 10 mi² Basic/Startup vs 50 mi² Premium; ring must close (first == last coordinate).
- Poll politely: back off rather than hammering `status`; bounded polling (docs example: 120 attempts).
- Segmentation outputs: Base64 images — prepend MIME prefix if absent.
- Violating constraints → requests rejected **and not charged**.

## 5. Changelog (latest release)

First GA release: core Temperature API surface, two subscription plans, credit tracking, complete endpoint documentation, per-endpoint plan-availability badges, quickstart, Known Limitations page, Release Notes page, Credit Usage Tracker.

---
*Extracted 2026-08-18 from the SPA bundle; live-behavior annotations from our own calls (Hackathon plan, sub_vecxagt6v7).*