# Submission Draft — FortyGuard Hackathon'26 Track 6 Agentic (calorai)

**Prepared 2026-08-21, deadline Aug 30 11:59 GST (UTC+4). All links must stay live through Sep 14 judging, incognito, no install.**

---

### 1. Official submission form (Slack-confirmed, mandatory even for solo)

| Field | Draft |
|---|---|
| **Team name** | `calorai` |
| **Member names/emails** | Priyapal Handique (solo) — *your email* |
| **Project title + pitch** | **calorai — physics-first city heat-budget auditor**: turns a FortyGuard temperature layer into an auditable action plan — where a district is hot, why it is hot (Stefan-Boltzmann/Brutsaert/Oke/Newton), which intervention cools it most, what it costs, and what an agent would do next, with every number traceable to API or equation. |
| **Primary track** | **Track 6 — Agentic** (single track, per handbook §10). Secondary tags: **left blank**. Tracks 2 (buildings/energy), 5 (model), 7 (data) are implemented as *use cases the agent can execute* (retrofit ROI, facade ranking, equity/productivity), not as tags. |
| **Who it's for** | City heat officers, resilience planners, real-estate asset managers, outdoor-work operators needing a defensible district audit in minutes. |
| **Where & when** | Tier 1: 10 districts (Phoenix, Maryvale, Vegas Strip, San Jose, Manhattan, East Harlem, Chicago, Austin, MIT Campus, Massachusetts) — demo flagship **Maryvale, Phoenix (33.463,-112.161) + Vegas Strip** for misting showcase. Time: catalog-proven **2024-07-15 14:00** (today's date returns zero tiles, catalog lags — documented). 24-h diurnal validated on Phoenix 2024-07-15 00-23. |
| **How the Temperature API was used** | `POST /v1/heatmap` (tcm tile field, single-hour, granularity 100, plus exceedance/persistence when available), `POST /v1/env_params` (24-h series: apparent_temp, wet_bulb, humidity, solar irradiance clear-sky GHI → sine diurnal, cloud octas, precipitation, heat_index, co2), `POST /v1/satellite` + `POST /v1/streetview` (cached Diridon + 3 portfolio parcels, **+2 live pulls deferred, Premium ~2–6k**), `POST /v1/heat_intelligence` (27-page PDF probe, 8.6k, premium risk retired), `POST /v1/system/fetch-api-key-usage` + `fetch-api-key-custom-usage` (usage monitoring, reverse-discovered). Cache-first `LiveFortyGuardSource` with SHA-256 disk cache (`data/cache` 46 files), mock fallback, `CALORAI_DATA_SOURCE` pin in `tests/conftest.py` (zero-credit suite). |
| **FortyGuard API key ID** | *Pull from Dashboard → Profile → API Key ID at D9* (not the secret). Paste here. |
| **AI tools disclosure** | See `AI_DISCLOSURE.md` — Codex (backend/physics), Cursor (UI/report), Muse Spark/opencode (orchestration), DeepSeek v4 flash (early backend), planning model TBD — owner reviews every diff. |
| **Live demo URL** | `https://<your-render-service>.onrender.com` — must open in fresh incognito, no login, no install. Health: `/api/health` 200. Mock fallback if key absent. Keepalive: `.github/workflows/keepalive.yml` pings `/api/health` every ~10 min via `LIVE_URL` repo variable. **Add after C2 deploy.** |
| **Video URL** | YouTube or Loom, **≤3 min** — script in `docs/video_script.md` (2:45, screen capture, trace shown). **Upload after recording, paste here.** |
| **Code repo URL** | `https://github.com/priyapalhandique/calorai` — public, `hackathon@fortyguard.com` collaborator, README with setup + "what doesn't work yet" + one real API request/response, no hardcoded keys, `CONCEPT.md` 397w, `AI_DISCLOSURE.md`, `ACKNOWLEDGEMENTS.md`. |

### 2. Public repo checklist

- [ ] `git push` main is public (fork of `FortyGuard-Tech/temperature-api-quickstart` verified, backup `calorai-template-base`)
- [ ] `.env` gitignored, no key in history (`git log -p | grep -i fortyguard` clean)
- [ ] `README.md` has live demo + video URLs (after C2/D10), 237 tests badge, hero GIF + summary card
- [ ] Add `hackathon@fortyguard.com` as GitHub collaborator (Settings → Collaborators)
- [ ] Clean-clone dry run: `git clone <url> && cd calorai && python -m venv .venv && pip install -r requirements.txt && python -m calorai serve` → incognito `http://127.0.0.1:8000` 200

### 3. Demo video checklist (≤3 min)

- [ ] Record per `docs/video_script.md` — problem → user → FYG endpoints → measured −13.0°C / 84/100 / Gini / VPD → **centerpiece voice `hey calorai` → `audit→forecast→risk→respond_mist` trace** → Evidence panel (Diridon sky 39.7% / shade 14.2%) → PDF/ZIP exports → close on Render URL incognito
- [ ] Host on YouTube (unlisted) or Loom, captions on, link in form + README
- [ ] Thumbnail: Phoenix 24h GIF or Massachusetts 127k heatmap (45% opacity)

### 4. Written summary checklist (≤500 words)

- [ ] `CONCEPT.md` is the summary: **problem → user → FortyGuard usage → measured result**, 397 words, ≤500, structured exactly
- [ ] Also paste same text into form field (plain text, no markdown)

### 5. Product feedback

- [ ] Submit `docs/fortyguard-products.md` (8 evidence-led recommendations) via Dashboard feedback form, link in README

### 6. Credit & cost to quote in form

- 2,000,000 total, **111,180 used (5.6%)** at `34ae729`, reset Sep 22 — 9 heatmaps 38k + 11 env 32k + 1 heat_intelligence 8.6k + 24-h validation 117k (20× plan estimate, cache-first now zero). Live set Phoenix 2,891 tiles 39.57–39.76°C.

### 7. Final 10:00 AM GST Aug 30 check

- [ ] Repo public, collaborator added, no secrets
- [ ] `LIVE_URL` repo variable set, keepalive green, incognito 200 in 2 browsers
- [ ] Submit **early Aug 29** (buffer before Aug 30 11:59 GST), keep URL live through Sep 14
