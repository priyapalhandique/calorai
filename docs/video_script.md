# calorai — Video Script (≤3 min, Track 6 Agentic)

**Target:** 2:45, single take screen capture + voiceover, no music, captions on.

---

### 0:00-0:15 — Problem
> "Phoenix hits 111 days above 100°F. A heatmap tells a mayor *where* it's hot. It doesn't tell them *why* that block is hot, *what* to do, or *what it costs*. calorai is a physics-first auditor that turns a FortyGuard temperature layer into an auditable action plan."

*Show: README hero GIF — Phoenix 24h island breathing, fixed scale 28.6–40.6°C.*

### 0:15-0:35 — User + FortyGuard usage
> "Built for a city heat officer. We call three FortyGuard endpoints: `POST /v1/heatmap` for the tile field, `POST /v1/env_params` for the 24-hour diurnal series — humidity, wet bulb, solar, cloud, precipitation — and cached satellite + street-view segmentation for ground-truth landcover. All cache-first, so the demo runs with zero key in mock mode."

*Show: `POST /v1/heatmap` + `POST /v1/env_params` in `notebooks/00_setup.ipynb`, then `data/cache` with 46 files, then `data/satellite` + `data/street_view` Diridon parcel.*

### 0:35-1:05 — Measured result (Phoenix 2024-07-15 14:00 live)
> "Live, Phoenix is 2,891 tiles at 39.6 mean. Solar is 96% of the load, WBGT 28.5 high, vulnerability 84 of 100 critical. Cool roofs model −13.0°C — the top lever — with a 3.3-year payback at $3k per year. The surrogate reproduces the physics within 0.75°C on synthetic holdout, and on the real 24-hour series it sits 2.46°C from the closed-form physics — the documented gap is skin vs canopy layer, not a bug."

*Show: `/api/analysis?district=phoenix&date=2024-07-15&hour=14` JSON → UI Overview act — headline numbers, attribution bar (solar 96%), intervention table.*

### 1:05-1:35 — Why lakes and canyons matter (3D)
> "Manhattan traps heat — H/W 1.5, sky view 0.35, walls warm the air. Chicago is cooled by Lake Michigan, about 2 to 3 Kelvin, free evaporative lever. Vegas Strip has neither. The same physics, different city."

*Show: `ui/skyline-3d.html` toggle — 2.5D Phoenix ground heat 45% opacity, 3D Manhattan drape on Re:Earth terrain, thermal-wind vectors pulsing.*

### 1:35-2:20 — Agentic centerpiece: "Should we mist Maryvale tomorrow?"
> "Hey calorai, should we mist Maryvale tomorrow?"

*Show: click mic in Ask act → Web Speech API → `POST /api/ask` → trace table:*
> "Agent thinks: audit Maryvale → forecast 24h → risk WBGT high → misting limited by humidity 85%? No, 24% dry — active. Wind-aware: inflow 112° from thermal wind, 1.8 m/s, place on inflow axis, pause if >4 m/s. Heat response: extreme → stop work, act with mist schedule + water budget $42."

*Show: trace `tool, args, status, ms` → answer + `answer_tldr` spoken via SpeechSynthesis. Then click Evidence panel: Diridon satellite tree 6.5% + street-view sky 39.7% + shade 14.2% — shade cuts solar 8.5%, SVF cools longwave — the block's physics, not a generic city mean.*

### 2:20-2:45 — Exports + honesty + close
> "Every number is from the API or an equation in `docs/physics-references.md`. Exports are a PDF report plus GeoJSON/CSV ZIP — the officer's evidence pack. What doesn't work yet is on the README and in the report — tiled."

*Show: `GET /api/report` PDF (charts G, J/K/L, M) + `GET /api/export` ZIP → close on 4-act UI with your Render URL in incognito, no install, mock fallback. End card: GitHub + 237 tests + `hackathon@fortyguard.com` collaborator.*

---

**Credits on screen:** `calorai` · Track 6 Agentic · Solo — Priyapal Handique · 2M credits, 111k used (5.6%), live verified Phoenix 2,891 tiles.
