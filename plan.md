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
   - **Primary track: Track 6 — Agentic (single-track decision, Aug 19). Secondary tags: left blank.**
     Tracks 2 (buildings/energy), 5 (model designing), 7 (data analysis) are implemented as
     **use cases the agent can execute**, not as tags — per handbook guidance, one track, many missions.
   - Who it's for, where & when (city/area + time period)
   - How the Temperature API was used
   - **FortyGuard API key ID** (to confirm real API use — pull from Dashboard Profile)
   - AI tools disclosure (what was used and for what)
   - Three links: live demo URL (must stay up **through judging, Sep 14**; **must open in a fresh/incognito window, no install**), video (YouTube or Loom, ≤ 3 min), code repo (GitHub; README with setup, "what doesn't work yet", one real API request + response; no hardcoded keys)
2. Public/judge-accessible repo — **add `hackathon@fortyguard.com` as GitHub collaborator**
3. Demo video **≤ 3 min** (hosted on YouTube or Loom)
4. Written summary **≤ 500 words**, structured exactly: problem → user → FortyGuard usage → measured result

Track 6 ground truth (verified by OCR of the handbook): §10 agentic ideas (goal-driven heat agent,
monitoring agent, tool-using research assistant with auditable calls) + §11 checklist above — the
handbook has **no separate per-track proof-item table** (0 hits for "proof"/"per-track" in the 20-page PDF).

Prizes: top-3 teams each win an Nvidia GPU; plus incubation, internships, API discounts; all finishers get a certificate + social asset.

---

## 2. Where we are (build day 3 — Aug 20)

- [x] Fork of `FortyGuard-Tech/temperature-api-quickstart` → `priyapalhandique/calorai` (verified fork; backup repo `calorai-template-base`; upstream remote)
- [x] venv + deps, `.env` gitignored (key must be rotated after hackathon)
- [x] Physics engine (28 tests): units, radiation, budget, inertia, stress (WBGT), mitigation
- [x] Data layer (11 tests): mock (5 US districts) + live FortyGuard source with SHA-256 disk cache, auto-fallback
- [x] Agent pipeline + narration cascade (7 tests) — 47 tests total, all green
- [x] FastAPI (`/api/health`, `/api/districts`, `/api/audit`, `/api/report`) + single-page UI
- [x] **Live verified end-to-end** (Phoenix, 2024-07-15 14:00): 2,891 cells, 39.57–39.76 °C,
      solar absorption 96% of heat load, WBGT 28.5 °C "high", top mitigation cool roofs **−13.0 °C**,
      full narrative via API, source=live
- [x] Credits: **78.5k / 2,000,000 used (3.9%)** — 9 heatmaps (38.0k) + 11 env analyses (31.9k) + 1 heat-intelligence probe (8.6k); 1,921,520 remaining; expiry Sep 22. Usage monitoring verified programmatically:
      `POST /v1/system/fetch-api-key-usage` + `fetch-api-key-custom-usage` (schema reverse-discovered from the SPA bundle)
- [x] Findings from our live runs: today's date returns **zero cells** (catalog lags); live env schema
      (`locations[].parameters` flat name→series dict; `solar_irradiance` = single clear-sky `ghi` scalar)
- [x] FortyGuard product research: full product/plan inventory + **8 evidence-led improvement
      recommendations** → `docs/fortyguard-products.md`
- [x] Physics Tier A shipped (73 tests): wind-aware h_c, Brutsaert sky + cloud blend, solar geometry,
      closure audit, globe-WBGT, humidex + dose, direct/diffuse split. Live headline: cool roofs −13.0 °C, solar share 97%
- [x] Physics Tier B shipped (88 tests): street-canyon trapping (Oke Eq. 5.18, SVF ψ=0.618 Phoenix),
      admittance/damping + force-restore storage, Priestley-Taylor latent (α=1.26), equilibrium solver + sensitivity bands
- [x] Track 2/5 modules shipped (113 tests): `physics/economics.py` (ROI — Phoenix 20,378 kWh/yr, $3,057/yr,
      3.3-yr payback), `physics/facade.py` (orientation ranking; deep-summer flip: south wall coldest in July Phoenix),
      `physics/vulnerability.py` (score 0–100; Phoenix 84/100 critical) — all wired into the report + PDF
- [x] PDF deliverable shipped: `calorai/report.py` — reportlab PDF (TOC + 6 charts), `/api/report` + CLI `--pdf` + UI button
- [x] Demo notebook shipped: `notebooks/calorai_demo.ipynb` (11 cells, verified end-to-end on mock)
- [x] Premium probe shipped: `/v1/heat_intelligence` → 27-page PDF at Phoenix (~8.6k credits); premium risk retired
- [x] `AI_DISCLOSURE.md` (first-person, portfolio style; planner model name TBD — user to supply) +
      `CONTRIBUTIONS.md` (findings + 8 recommendations + usage footprint)
- [x] Git: everything committed + pushed to GitHub (`4a5f48d` + 4 prior commits); repo public-ready

### 2.1 Q&A intel (Aug 19) — mandatory web demo + judging guidance

- **Web-based demo is mandatory, not optional.** URL must work in a **fresh/incognito window, no install**.
  → FastAPI + single-page UI already satisfies the shape; remaining work is hosting + incognito-proofing.
- **Judging criteria re-confirmed:** Impact 40% • Technical 35% • Innovation 15% • Communication 10%.
- **Focused beats broad.** → One narrative: "**one district, one heat problem, three interventions**".

### 2.2 Unified model — single track, four modules, NL front end (decision Aug 19–20)

**One product, one track (Track 6 Agentic), four modules sharing one physics core, one report
contract, one PDF, one UI, one deployment.** Tracks 2/5/7 live inside it as use cases.

```
calorai/
├── physics/             # shared core (radiation, canyon, inertia, WBGT, facade, economics, vulnerability,
│                        #   + NEW: thermal_wind, convection/downburst)
├── auditor.py           # M1 Auditor  — energy balance, facade, retrofit ROI            (T2 spirit)  ✅
├── sentinel/            # M2 Sentinel — vulnerability, worker safety, anomaly, alerts   (T5 spirit)  🟡
├── responder/           # M3 Responder— heat response agent, misting, alert automation (T6 heart)   🟡
└── analyst/             # M4 Analyst  — equity, productivity, economic impact           (T7 spirit)  🟡
```

| Module | Ships | Status |
|---|---|---|
| M1 Auditor | energy balance, attribution, canyon, inertia, facade, retrofit ROI | ✅ done |
| M2 Sentinel | vulnerability score + worker-safety alert ✅ · **anomaly** (tile-vs-physics residual z-score + IsolationForest) ✅ · **alerts** (threshold rules → webhook-ready payloads, escalation) ⬜ · **downburst "outflow watch"** advisory ✅ | 🟢 |
| M3 Responder | **mist cooling physics** (evaporative latent extraction, 2.26 MJ/kg, nozzle eff. 0.7 → ΔT + water budget) ⬜ · **Heat Response Agent** (WBGT/forecast breach → mist schedule, water cost vs cooling, ranked actions) ⬜ · **wind-aware misting** (thermal-wind proxy: high flow = mist disperses = skip) ⬜ | 🟡 |
| M4 Analyst | **equity** (Gini + hottest/coolest quintile ratio on tile °C; cross-district leaderboard) ✅ · **productivity** (WBGT → work-capacity loss %, Dunne 2013/Kjellstrom, cited; annualized lost h + $) ✅ · **economy** (district-scale cost of heat = cooling $ + productivity $) ✅ · **thermal-wind proxy** (hydrostatic Δp from ΔT → urban-breeze circulation direction + relative magnitude; ventilation corridors; caveated as relative, not absolute) ✅ | 🟢 |

**ML layer (Option B, hybrid — decision Aug 20):**
- `ml/forecast.py` — physics-informed forecast surrogate: gradient-boosted regressor (sklearn
  `HistGradientBoosting`) trained on **physics-generated synthetic data** (5 districts × dates × hours ×
  canyon/albedo sweeps, ~100k rows, 0 credits), features = solar geometry + district params +
  env (humidity, cloud, wind) → target = air/surface °C from the validated energy balance.
  **Honest validation:** held-out real API 24-h env series (Phoenix cache + 1 new live pull ≈4.5k) →
  MAE/RMSE vs physics-only baseline in docs + report block. Scope: **24-h nowcast** (API has no
  multi-year history — documented boundary). Artifact: `data/models/forecast_v1.joblib`, retrain CLI.
- `ml/anomaly.py` — anomaly detector: interpretable physics-residual z-score **+** trained IsolationForest
  on tile features; flags "tiles that defy physics" with explanation (feeds U8 anomaly investigator).

**Natural-language agent loop (decision Aug 20 — "they must understand natural lang"):**
- `calorai/tools.py` — tool registry, uniform schema (name, description, JSON params, handler, cost).
  Tools: `audit`, `forecast`, `anomaly`, `risk`, `respond_mist`, `equity`, `productivity`, `economy`,
  `usage`, `export`.
- `calorai/planner.py` — LLM (GitHub Models cascade, reuses narrator token) reads brief → picks tools →
  JSON args → executes → repeats (max 6 calls) → final narrated answer. **Every call logged
  `{tool, args, status, credits, ms}` and rendered as the auditable trace in the UI** (Track 6 §10).
- **Deterministic fallback:** keyword intent matcher → direct tool + template narration — demo works
  with **zero LLM keys** (incognito-safe). Numbers enter answers only from tools, never from the LLM.
- Surfaces: `POST /api/ask` · UI chat box · CLI `python -m calorai ask "…"`.

### 2.3 Agentic use-case menu (Track 6 foothold)

| # | Use case | Status |
|---|---|---|
| U1 | **"Why is this tile hot?"** — click tile → energy-balance decomposition in plain English | 🟡 ship set |
| U2 | **What-if planner** — "raise albedo to 0.5 on top 10% tiles" → before/after ΔT + $ | 🟡 ship set |
| U3 | **"Plan tomorrow" chain (flagship)** — one brief → forecast → risk → misting → shift schedule; multi-tool chain with trace | 🟡 ship set |
| U4 | Heat-emergency escalation — breach → alert payload + simulated actions (cooling centers, mist) | 🟡 fold into M2/M3 |
| U5 | Portfolio sweep / monitoring agent — daily brief over all districts, ranked risk | 🟡 fold into M2 |
| U6 | Comparative agent — "Phoenix vs Las Vegas, July 15" head-to-head | ⬜ optional (needs live pulls) |
| U7 | Bus-stop shade ranking (planned D4–D5 item) | 🟡 planned |
| U8 | Anomaly investigator — flagged tile → agent investigates → verdict | 🟡 cheap, after ml/anomaly |
| U9 | Seasonality advisor — "when to shade which facade" (deep-summer flip) | 🟡 ~0 (facade.py exists) |
| U10 | **Water-budget responder** — mist vs shade vs cool roof by **cost per °C per m²** | 🟡 ship set |
| U11 | Work-rest scheduler — WBGT forecast → OSHA-style shift plan per intensity | 🟡 fold into M3 |
| U12 | Retrofit portfolio planner — multi-building scan → ranked retrofit schedule | ⬜ optional |

Demo shows **U1 + U2 + U3 + U10**; U4/U5/U11 fold into modules; U6/U12 only if credits/time allow;
U8/U9 ship if the ML/anomaly slot stays on schedule.

### 2.4 Location strategy — two-tier, hyperlocal flagship (decision Aug 20)

**Tier 1 — city leaderboard (breadth):** existing 5 districts (Phoenix, San Jose, Lower Manhattan,
Chicago, Austin) for cross-city equity/Gini/WBGT comparison → M4 leaderboard + U6 comparative agent.
Mock-first; live where cached.

**Tier 2 — subdivision deep-dive (the demo):** one AOI, per-tile distribution, hottest blocks, all
three acts + NL agent. Evidence base (web research Aug 20):
- Hottest big cities: Phoenix #1 (111 d >100 °F), Las Vegas #2 (78 d; **18.5% humidity, 99.2% clear sky**),
  Dallas (1.06M people in UHI ≥8 °F zones, 81%), Houston (1.77M, 77%).
- UHI exposure (Climate Central 2024): **NYC highest per-capita 9.7 °F, 7.27M people (83%) exposed**;
  Chicago 1.70M (62%); equity links (Hsu et al. *Nature* 2021: people of color/poverty disproportionate in 169/175 cities).
- Hypothesis fit: **misting needs dry air** (Vegas > Phoenix > Dallas ≫ humid cities); **canyon physics
  needs tall buildings** (NYC, Vegas Strip); **WBGT/workers** (Phoenix/Vegas/Dallas); **equity needs
  intra-city contrast** (NYC, Maryvale).
- **Live set: Phoenix ✅ (have) + Las Vegas + Manhattan/NYC (+ Dallas optional 4th)** — ~4.5k each,
  pin **2024-07-15**, small-AOI coverage probe before full pull, zero-cell → drop.
- **Flagship subdivision: Maryvale, Phoenix** (hottest + most famous US heat-equity neighborhood,
  historically redlined) with **Vegas Strip as the misting showcase** (hotels already mist in reality —
  our model says when/where); East Harlem/South Bronx as NYC equity alternative. New mock district
  entries (free) + optional live probes.

Deliverable: `docs/location-analysis.md` — evidence memo (rankings, UHI/equity stats, per-city
hypothesis-fit score, probe plan, credit ledger, leaderboard design).

### 2.5 Presumptive topics (documented in `docs/roadmap.md`, not built)

Cyclone coupling (needs synoptic pressure/SST/steering — out of our data scope) · downburst *forecasting*
(needs radar/CAPE — we ship only the thermodynamic diagnostic) · real IoT actuator hardware (mist rigs,
valves) · energy-grid demand coupling · insurance risk pricing · census income-overlay equity (external
ACS data) · multi-city catalog expansion. Each: what it would need, why we didn't build it. **Breadth in
the repo, depth in the demo, honesty in "what doesn't work yet".**

---

## 3. Day-by-day plan (Aug 18 → Aug 30)

### D0–D1 (Aug 18–19) — Foundations ✅
- [x] Live pipeline fix, regression tests, product research, physics tiers A+B, Track 2/5 modules,
      PDF report, demo notebook, premium probe, disclosures (113 tests) — all committed/pushed
- [ ] `CONCEPT.md` — problem → user → FortyGuard usage → measured result (feeds the 500-word summary)
- [ ] README: hero equation, architecture diagram (4-module + NL loop), quickstart, "what doesn't work yet",
      one real API request + response, no hardcoded keys
- [ ] `AI_DISCLOSURE.md` **update** (post-B): ML trained + validated on API data; LLM selects tools only;
      numbers always from physics/API; fill planner-model name when user supplies it

### D2–D3 (Aug 20–21) — Deploy, interop, locations (de-risk first)
- [ ] **D6 pulled forward: Render free web service + keep-alive** — `render.yaml` + `Procfile`
      (`gunicorn calorai.main:app --bind 0.0.0.0:$PORT`), `FORTYGUARD_API_KEY` as Render env var,
      GH Actions cron ping `/api/health` ~10 min (keeps free tier awake through Sep 14 judging)
- [ ] Verify public URL **in a fresh incognito window** (no install, no login); zero-credit-after-first-run path;
      screenshot/gif capture for README + video
- [ ] **Interop export (Forma, Option A)**: `calorai/interop.py` — heat-tile GeoJSON FeatureCollection +
      audit-table CSV + interventions CSV; `GET /api/export` (ZIP) + CLI `--export-out` + UI button +
      `docs/interop-forma.md`; ~6 tests
- [ ] **Location analysis**: `docs/location-analysis.md` + new mock subdivision districts (Maryvale,
      Vegas Strip, NYC East Harlem) + live probes (Vegas, NYC; Dallas optional) on 2024-07-15,
      small-AOI first, cache everything

### D4–D5 (Aug 22–23) — Analysis layer + new physics (M4, T7 spirit) ✅ shipped 2026-08-20
- [x] `analyst/equity.py` — Gini + quintile ratio per district + cross-city leaderboard (tile °C, WBGT,
      exceedance, vulnerability, Gini) — charts into PDF
- [x] `analyst/productivity.py` — WBGT → work-capacity loss % (Dunne 2013/Kjellstrom, cited) →
      annualized lost hours + $ per site/intensity
- [x] `analyst/economy.py` — district-scale cost of heat = cooling energy $ + productivity-loss $
- [x] `physics/thermal_wind.py` — hydrostatic Δp from ΔT field → urban-breeze circulation direction +
      relative magnitude, ventilation corridors; caveated (relative, not absolute — the API ships no wind);
      uniform-field flag for symmetric districts; robust LSQ plane fit with collinear fallback
- [x] `physics/downburst.py` — downburst thermodynamic diagnostic from env series (T, RH, wet-bulb,
      precip): wet-bulb depression D = T−Tw with rain onset → low/med/high bands (Caracena 1990;
      Wakimoto 1985); "outflow watch" advisory; documented boundary
      (diagnostic, not forecast — no radar/CAPE)
- [x] Tests (+20, 140 total), `docs/physics-references.md` citations (M4a–M4e), PDF charts (equity table,
      productivity curves, circulation diagram, downburst risk series); interop CSV extended with
      equity/productivity/economy/thermal-wind columns

### D6 (Aug 24–25) — ML layer (forecast + anomaly) ✅ shipped 2026-08-20 (offline half)
- [x] `ml/forecast.py` — synthetic-data generator (physics sweeps) → train HistGradientBoosting →
      hold-out validation vs physics (MAE 0.75 °C / R² 0.9966 at 100k rows) →
      artifact `data/models/forecast_v1.joblib` (committed) + `python -m calorai train-forecast`;
      `validate_vs_real()` implemented, real-series run deferred post-deploy (docs/ml-validation.md)
- [x] `ml/anomaly.py` — physics-residual z-score + IsolationForest on tile features; flagged tiles with
      explanation; feeds U8 + report block
- [x] `requirements.txt` += `scikit-learn`, `joblib`; tests (+7, 147 total); docs section (docs/ml-validation.md)

### D7 (Aug 26–27) — NL agent loop + Heat Response Agent (Track 6 heart)
- [ ] `tools.py` registry (uniform schema) with all 10 tools incl. `respond_mist`, `export`, `usage`
- [ ] `planner.py` — LLM tool-selection loop (GitHub Models cascade) + **keyword-intent fallback** +
      auditable trace `{tool, args, status, credits, ms}`; max 6 calls; numbers only from tools
- [ ] `POST /api/ask` + UI chat box + CLI `python -m calorai ask "…"`; trace rendered in UI
- [ ] `responder/misting.py` — evaporative mist physics (latent 2.26 MJ/kg, nozzle eff. 0.7) →
      ΔT + water budget (L/m²·h); **wind-aware** via thermal-wind proxy (calm = mist, flow = skip)
- [ ] `responder/heat_response.py` — Heat Response Agent: breach (WBGT + forecast) → mist schedule,
      water cost vs cooling, ranked actions; U10 water-budget comparison (mist vs shade vs roof per °C per $)
- [ ] `sentinel/alerts.py` + anomaly packaging — threshold rules → webhook-ready payloads, escalation,
      outflow watch; U4/U5/U11 folded in
- [ ] Tests (~+15); notebook v2 (NL brief → trace → PDF)

### D8 (Aug 28) — Unified deliverable
- [ ] **Tabbed 4-act UI** — Act 1 retrofit ROI → Act 2 shade/bus-stop ranking → Act 3 risk/safety →
      Act 4 response (mist) — every act closes on a headline number; chat panel with trace;
      CDN-hosted deps only; no localStorage dependencies
- [ ] PDF v2 (+equity, productivity, thermal-wind, downburst, forecast charts); notebook v2; README
      (architecture diagram + screenshots); `docs/roadmap.md` presumptive topics; `docs/interop-forma.md`
- [ ] Full suite green (~150 tests); incognito re-verify; mock-mode full pass

### D9 (Aug 29) — Video + summary + submit
- [ ] Video ≤3 min: problem → user → FYG endpoints → measured results (−13.0 °C, ROI $, 84/100 risk,
      equity Gini, productivity %) → **centerpiece: "should we mist?" → agent thinks (forecast + anomaly
      + thermal wind) → acts (schedule + water cost) → trace shown**
- [ ] 500-word summary: problem → user → FortyGuard usage → measured result
- [ ] Submission form: key ID, disclosure, 3 links, product feedback (`docs/fortyguard-products.md` →
      Dashboard feedback form); **submit early Aug 29**

### D10–D12 (Aug 30) — Buffer, QA
- [ ] Clean-clone dry run (README instructions); `.gitignore` check; collaborator
      `hackathon@fortyguard.com`; repo public; 10:00 AM GST final check; URL up through Sep 14

---

## 4. Credit budget (2,000,000 total, active to Sep 22)

| Use | Est. cost | Done |
|---|---|---|
| Probes + failed experiments (irrecoverable) | ~26k | ✅ |
| Probes/experiments to date (heatmaps 38.0k + env 31.9k + premium 8.6k) | ~78.5k total | ✅ |
| Live locations: Las Vegas + Manhattan/NYC (+ Dallas optional) | ~9–13.5k | ⬜ |
| Forecast validation pull (held-out live 24-h series) | ~4.5k | ⬜ |
| Bus-stop shade + misc demo headroom | ~3k | ⬜ |
| **Total projected** | **~95–100k (≈5%)** | |

Discipline rules: cache every layer by area+date/time; no scope creep on live calls; failed tasks are
free — retry liberally; **verify coverage (small-AOI probe) before any new AOI/date**; demo cached so
server-side cost stays ~0 after first run.

---

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Today's date returns zero cells (catalog lag) | All demos pinned to catalog-proven dates (2024-07-15); probe before pulling new AOIs |
| Premium endpoints — **RESOLVED 2026-08-19** | heat_intelligence probe succeeded (27-page PDF); satellite/street-view stay low priority |
| Scope creep (12 use cases + 4 modules + ML + NL) | Ship set locked (U1/U2/U3/U10); everything else fold-in or presumptive; video/summary can only carry 4 acts |
| LLM narrator/planner keys unavailable at judging | Cascade + keyword-intent fallback → demo fully works with zero keys (incognito-safe) |
| ML honesty (synthetic training data) | Held-out real API validation with MAE/RMSE vs physics baseline published in docs + report; no overclaiming |
| sklearn/joblib footprint on Render free tier | Small wheel deps; model artifact tiny; mock-mode never imports ML unless asked |
| Wind proxy / downburst credibility | Strictly labeled relative-diagnostic with literature citations; boundaries in "what doesn't work yet" |
| API access ends when hackathon ends | Ship demo + video + summary before Sep 1; mock mode keeps repo runnable forever |
| Live demo dies before judging ends | Render free tier + GH Actions keep-alive (~10 min); verify URL Sep 1 + Sep 8 |
| Key ID missing from form | Pull from Dashboard Profile at D9; note in "what doesn't work yet" if absent |
| Credits jump unexplained (38.5k in one day) | Usage monitor in UI + `fetch-api-key-usage`; treat as external activity, keep budget guardrails |

---

## 6. Definition of done

- [ ] Repo: public, clean README (setup + "what doesn't work yet" + one real request/response) +
      CONCEPT.md + `docs/roadmap.md` (presumptive topics) + `docs/location-analysis.md` + collaborator
      added, no secrets in history, **~150 tests green**
- [ ] Live demo: public URL up through Sep 14, fresh/incognito window, no install, catalog-proven
      Phoenix + Las Vegas + Manhattan/NYC (+ mock districts), zero-credit-after-first-run
- [ ] Agentic (Track 6 §10): NL brief → **LLM tool selection with auditable trace** → ranked, source-cited
      action plan; deterministic fallback; monitoring/alerts; forecast + anomaly depth
- [ ] Four acts: retrofit ROI ($ + payback) · shade/bus-stop ranking · risk/safety (vulnerability +
      outflow watch) · **heat response (mist schedule, water cost, wind-aware)** — measured °C **and** $
- [ ] Analysis (T7 spirit): equity Gini + cross-city leaderboard, productivity loss %, cost of heat
- [ ] New physics documented: thermal-wind proxy + downburst diagnostic (cited, caveated)
- [ ] Form submitted Aug 29: Track 6 primary (tags blank), key ID, AI-tools disclosure, YouTube/Loom
      ≤3 min, summary ≤500 words structured problem → user → FortyGuard → result
- [ ] Product feedback delivered: `docs/fortyguard-products.md` submitted via Dashboard form, linked in README