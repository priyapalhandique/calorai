# calorai — Build Timeline & Plan (FortyGuard Hackathon'26, Track 6 Agentic)

> Physics-first city heat-budget auditor: Stefan–Boltzmann/Newton energy balance over
> FortyGuard LTM temperature layers, delivered as an auditable agentic pipeline.
> Solo entry — Priyapal Handique.

---

## 1. Hard deadlines (all times 11:59 PM GST = UTC+4)

| Milestone | Date |
|---|---|
| Registration | Jun 20 – Aug 17 |
| Kickoff (today) | **Aug 18** |
| Mentor webinars | announced on Slack during program |
| **Submission deadline** | **Aug 30, 11:59 PM GST** |
| Judging window | Sep 1 – Sep 14 |
| Winners announced | Sep 16 |

Judging weights: **Impact & Relevance 40% • Technical Execution 35% • Innovation 15% • Communication 10%**.

Submission checklist (all required):
1. **Official submission form** (Slack-confirmed, mandatory even for solo) — fields:
   - Team name (own name or project name) → `calorai`
   - Member names/emails → Priyapal Handique (solo)
   - Project title + pitch
   - Primary track **Track 6 — Agentic** + up to 2 optional secondary tags (e.g. Resilient Cities, Government & Environment)
   - Who it's for, where & when (city/area + time period)
   - How the Temperature API was used
   - **FortyGuard API key ID** (to confirm real API use — pull from Dashboard Profile)
   - AI tools disclosure (what was used and for what)
   - Three links: live demo URL (must stay up **through judging, Sep 14**), video (YouTube or Loom, ≤ 3 min), code repo (GitHub; README with setup, "what doesn't work yet", one real API request + response; no hardcoded keys)
2. Public/judge-accessible repo — **add `hackathon@fortyguard.com` as GitHub collaborator**
3. Demo video **≤ 3 min** (hosted on YouTube or Loom)
4. Written summary **≤ 500 words**, structured exactly: problem → user → FortyGuard usage → measured result

Track 6 ground truth (verified by OCR of the handbook): §10 agentic ideas (goal-driven heat agent, monitoring agent, tool-using research assistant with auditable calls) + §11 checklist above — the handbook has **no separate per-track proof-item table** (0 hits for "proof"/"per-track" in the 20-page PDF).

Prizes: top-3 teams each win an Nvidia GPU; plus incubation, internships, API discounts; all finishers get a certificate + social asset.

---

## 2. Where we are (build day 1 — Aug 18)

- [x] Fork of `FortyGuard-Tech/temperature-api-quickstart` → `priyapalhandique/calorai` (verified fork; backup repo `calorai-template-base`; upstream remote)
- [x] venv + deps, `.env` gitignored (key must be rotated after hackathon)
- [x] Physics engine (28 tests): units, radiation, budget, inertia, stress (WBGT), mitigation
- [x] Data layer (11 tests): mock (5 US districts) + live FortyGuard source with SHA-256 disk cache, auto-fallback
- [x] Agent pipeline + narration cascade (7 tests) — 47 tests total, all green
- [x] FastAPI (`/api/health`, `/api/districts`, `/api/audit`) + single-page UI
- [x] **Live verified end-to-end** (Phoenix, 2024-07-15 14:00): 2,891 cells, 39.57–39.76 °C,
      solar absorption 96% of heat load, WBGT 28.5 °C "high", top mitigation cool roofs **−13.0 °C**,
      full narrative via API, source=live
- [x] Credits: ~26k / 2,000,000 used (~1.3%); cached repeat calls cost nothing
- [x] Findings from our live runs: today's date returns **zero cells** (catalog lags); live env schema
      (`locations[].parameters` flat name→series dict; `solar_irradiance` = single clear-sky `ghi` scalar)
- [x] FortyGuard product research: full product/plan inventory + **8 evidence-led improvement
      recommendations** (Map Statistics payload empty, solar irradiance scalar, date-range messaging,
      silent `null` premium params, filter_type 1–4 vs 5, SPA docs, no credit preview, temp PDF links)
      → `docs/fortyguard-products.md` (they asked for product improvements)
- [x] **Physics Tier A shipped** (73 tests): wind-aware h_c (McAdams; live API has no wind → calm
      12 W/m²·K, mock exercises the wind path at h_c≈20), Brutsaert clear-sky emissivity + cloud-blended
      sky temperature (live: Phoenix 14:00 sky 25.6 °C, air −15 K; cloud series now fetched), solar
      geometry (declination/elevation/hour-angle/tilted-plane module), balance closure audit
      (residual + implied h_c; live run honestly flags layers disagree: tile 39.8 < air 40.7 °C),
      globe-estimated WBGT 0.7/0.2/0.1 (live 31.8 °C "extreme" vs two-term 28.5 "high" before),
      humidex (44.9 °C live) + exposure dose, direct/diffuse solar split from real dni/dhi scalars.
      Live headline intact: cool roofs −13.0 °C, solar share 97%
- [ ] **Physics Tier B parked** (decide D2+): B1 street-canyon view factors + albedo paradox;
      B2 peak-lag analysis (time_of_measure layer vs solar noon → effusivity fingerprint);
      B3 latent heat (Priestley–Taylor ET for green mitigation); B4 sensitivity bands (±ΔT from
      h_c/albedo uncertainty). All four sketched in session notes; not implemented.

## 3. Day-by-day plan (Aug 18 → Aug 30)

### D0–D1 (Aug 18–19) — Foundations locked ✅ (mostly done)
- [x] Live pipeline fix (date-coverage, env schema, stale-cache guard) — committed `561d781`
- [x] Regression test for live env schema — 47 tests green
- [x] `docs/fortyguard-products.md` — product inventory + improvement recommendations (submitted with project)
- [ ] `CONCEPT.md` — problem → user → FortyGuard usage → measured result (feeds the 500-word summary)
- [ ] README: hero equation Q̇ = εσA(T⁴ − T_amb⁴), architecture diagram, quickstart, credits note,
      setup steps, **"what doesn't work yet"** section, **one real API request + response** sample,
      no hardcoded keys (`.env.example` only)
- [ ] `plan.md` (this file) in repo
- [ ] AI-tools disclosure draft: AI-assisted development (code, tests, docs, planning) via a coding
      assistant — no AI inside the shipped product's core loop

### D2–D3 (Aug 20–21) — Agentic core (Track 6 requirement)
- [ ] `calorai/tools.py` tool registry: `fetch_heatmap`, `fetch_env_params`, `run_energy_balance`,
      `rank_interventions`, `get_usage` — uniform tool schema (name, description, params, handler)
- [ ] Goal-driven loop: plain-language brief → tool selection → sequenced calls → source-cited action plan
      (e.g. "hottest bus stops in Phoenix last July → shade memo"); log each API call for auditability
- [ ] Monitoring agent (sketch): sweep portfolio of sites on current-day conditions, threshold alerts
- [ ] Unit tests for tools + planner

### D4–D5 (Aug 22–23) — Demo portfolio: real-world applications
Core demo stays the city audit; these three ship as the showcase set (all Basic-plan endpoints, cheap in credits):
- [ ] **Bus-stop shade prioritization (city planner)** — agent ingests stops CSV → env_params per stop (point-based, cheap) → WBGT + absorbed-flux ranking → per-stop shade memo ("these 12 stops breach WBGT 30 °C, shade first, −ΔT each"). Handbook Track 1 starting point, upgraded with physics
- [ ] **Retrofit ROI in dollars (building/utility owners)** — smallest lift, largest judging upside: add degree-hours × envelope area × cooling-efficiency model to existing ΔT outputs → annual $ saved + payback years ("−13 °C peak, ~$41k/yr cooling avoided, ~6 yr payback")
- [ ] **Worker heat-safety sweep + memo (construction/logistics)** — monitoring agent sweeps site portfolio on current-day conditions (env_params), WBGT vs OSHA-style thresholds, auto alert + compliance memo; = handbook's Track 6 monitoring idea made concrete
- [ ] Stretch (only if credits/time allow): cool-route exposure path using hourly tcm layers
- [ ] Add 2nd/3rd live districts (e.g. miami, las vegas) with one heatmap+env each (≈9k credits, cached after)
- [ ] Cross-city comparison feature (rank cities by WBGT / absorbed flux / mitigation lift)
- [ ] UI polish: live report rendering, per-tile hottest-street view, warning banners for non-covered dates

### D6 (Aug 24) — Deploy → live demo link
- [ ] Hugging Face Spaces (Streamlit/FastAPI mirror) with `.env` secret and mock fallback in demo mode
- [ ] Pin demo AOIs/dates to catalog-proven timestamps; verify public URL + zero-credit path
- [ ] Screenshots/gif capture for README + video
- [ ] Note: **URL must stay up through Sep 14 (judging)** — no teardown after Aug 30

### D7 (Aug 25) — Demo video (≤3 min)
- [ ] Script: problem (urban heat invisible) → user (city/planner + building owner) → FYG endpoints (heatmap + env_params) →
      measured results (−13.0 °C on hottest tiles, 96% solar attribution, bus-stop ranking, **ROI in $**) → auditable agent trace
- [ ] Record (OBS or Loom), captions, ≤3 min hard cap; **upload to YouTube or Loom** (form fields)

### D8 (Aug 26) — 500-word summary + submission form prep
- [ ] Write structured summary: problem → user → FortyGuard usage → measured result
- [ ] Reflect rubric: measurable outcome ≠ flashy demo (handbook §"What makes a project win")
- [ ] **Pull FortyGuard API key ID from Dashboard Profile** (required by the form)
- [ ] Fill submission form draft: team name, members, title+pitch, track + tags, who/where/when,
      API usage, key ID, AI-tools disclosure, three links (placeholders until D6/D7)
- [ ] **Submit product improvement recommendations** via Dashboard/Account feedback form + link
      `docs/fortyguard-products.md` in README; cite the empty-`stats_data` gap in the summary
      (Impact angle: we audited the API by living in it, not by reading the brochure)

### D9–D12 (Aug 27–30) — Buffer, QA, submit
- [ ] Aug 27: full dry-run of demo from clean clone (README instructions; `pip install -r requirements.txt`)
- [ ] Aug 28: repo hygiene — `.gitignore` check (`.env`, caches, probes), add collaborator
      `hackathon@fortyguard.com`, repo visibility public
- [ ] Aug 29: **submit early** (form + live link + video + summary + repo shared) — buffer before hard deadline
- [ ] Aug 30: final check 10:00 AM GST; no last-day fire-fighting (11:59 PM GST cutoff, no late entries)
- [ ] Sep 1–14: **keep demo URL up through judging**; answer any judge queries on Slack fast

### Post-build
- [ ] Sep 1–14: judging window — answer any judge queries on Slack fast
- [ ] Sep 16: winners announced

---

## 4. Credit budget (2,000,000 total, active to Sep 22)

| Use | Est. cost | Done |
|---|---|---|
| Probes + failed experiments (irrecoverable) | ~26k | ✅ |
| 2–3 new cities (heatmap + env each) | ~13k | ⬜ |
| Demo/misc headroom | ~10k | ⬜ |
| **Total planned** | **~50k (2.5%)** | |

Discipline rules: cache every layer by area+date/time (already); no scope creep on live calls;
failed tasks are free — retry liberally at zero cost; verify coverage (US-only, 2021-01-01 → now +12 h)
**before** spending on any new AOI/date.

---

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Today's date returns zero cells (catalog lag) | All demos pinned to catalog-proven dates (2024-07-15); UI warns on non-covered dates |
| Premium endpoints (heat_intelligence PDF, satellite, street view) unavailable on Basic plan | Agentic story leans on heatmap + env_params (both Basic); no dependency on premium |
| LLM narrator needs API key we don't have | Cascade: auto → GitHub Models → template narrator; fully deterministic without LLM |
| Team unresponsive → effectively solo | Solo entries welcome (§3); keep scope shippable alone |
| API access ends when hackathon ends | Ship demo + video + summary before Sep 1; mock mode keeps repo runnable forever |
| 3-min video cap / 500-word cap | Script and summary drafted at D7/D8, trimmed with time to spare |
| GST timezone confusion on Aug 30 | Submit Aug 29, well ahead of 11:59 PM GST |
| Live demo dies before judging ends | HF Spaces has no sleep for paid tier — else keep-alive cron; verify URL Sep 1 + Sep 8 |
| Key ID missing from form | Pull from Dashboard Profile at D8; if absent, note it in "what doesn't work yet" |

---

## 6. Definition of done

- [ ] Repo: public, clean README (setup + "what doesn't work yet" + one real request/response) + CONCEPT.md,
      tests green (47), collaborator added, no secrets in history
- [ ] Live demo: public URL up through Sep 14, works on catalog-proven Phoenix + ≥2 more US cities,
      zero-credit-after-first-run
- [ ] Agentic: plain-language brief → tool-sequenced calls → ranked, source-cited action plan, auditable trace
- [ ] Demos: bus-stop shade ranking + retrofit ROI ($ + payback) + worker-safety sweep; measured °C **and** $ outcomes
- [ ] Form submitted: key ID, AI-tools disclosure, YouTube/Loom link ≤3 min, summary ≤500 words structured
      problem → user → FortyGuard → result (−13.0 °C, WBGT high→threshold, ROI $)
- [ ] Product feedback delivered: improvement list submitted to organizers (dashboard form), linked in README