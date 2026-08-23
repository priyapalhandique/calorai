# calorai — Orchestration Guide: Codex + Cursor AI + Muse Spark

> How to run calorai with three agents in parallel without merge collisions,
> credit blowups, or lost context. Solo entry — Priyapal Handique.
> Track 6 Agentic, submission Aug 30 11:59 GST, live URL through Sep 14.

This file is the **single source of truth** for who does what. Read it before
opening Codex or Cursor. `plan.md` owns *what* we build; this file owns *how*
we build it together.

---

## 1. Goal & non-goals

**Goal:** Ship a physics-first city heat-budget auditor that passes judging
read-only: one district, one heat problem, three interventions, every number
traceable to an equation and the FortyGuard Temperature API layer.

**Non-goals (explicitly not in this repo):** Next.js port of the UI, Laravel
rewrite, hardcoded API keys, large NDJSON dumps in git, multi-year history
(pinned catalog dates only), real IoT valve hardware.

**Current state (2026-08-20, commit `dae1a10`):** 229 tests green, D8 stats +
N2 trajectories + PQ UI + voice + personal shipped, D9 24-h validation
(phoenix 2024-07-15, env+24×tcm cached) + N5 street-level/synoptic/elevation
shipped, 208k/2M credits (10.4%), `M scripts/validate_live.py` 5-line patch
pending in this commit.

---

## 2. Topology — who is what

```
                    ┌─────────────────────┐
                    │  Muse Spark         │
                    │  (opencode)         │
                    │  Orchestrator       │
                    │  Integrator / QA    │
                    └────────┬────────────┘
                             │  owns main, merges, credit guard
              ┌──────────────┼──────────────┐
              ▼              │               ▼
     ┌────────────────┐      │      ┌────────────────┐
     │  Codex         │      │      │  Cursor AI     │
     │  Backend /     │      │      │  Frontend /    │
     │  Physics /     │      │      │  Report /      │
     │  Analyst       │      │      │  Tools         │
     └────────────────┘      │      └────────────────┘
                             ▼
                    ┌─────────────────────┐
                    │  git origin/main    │
                    │  single shared repo │
                    └─────────────────────┘
```

| Agent | Role | Strength | When to use |
|-------|------|----------|-------------|
| **Muse Spark (opencode)** | Orchestrator & integrator. Owns `main`, `plan.md`, `orchestration.md`, `render.yaml`, `Procfile`, `CONCEPT.md`, final QA and pushes. | Cross-file reasoning, credit accounting, merge conflict resolution. | Every wave boundary, every merge to `main`. |
| **Codex** (CLI or codex.openai.com) | Backend / physics / analyst worker. | Test-driven physics, deterministic analyst modules, ML. | `calorai/physics/**`, `calorai/analyst/**`, `sentinel`, `ml`, `scripts`, `data_source`. |
| **Cursor AI** (IDE) | Frontend / report / tools worker. | Iterative UI/report preview, canvas charting, tool wiring. | `ui/**`, `calorai/report.py`, `calorai/tools.py`, `calorai/planner.py`, `calorai/personal.py`, `calorai/main.py`. |

**Single rule:** Codex and Cursor never push directly to `origin/main`. They work
on short-lived topic branches and hand a diff to the orchestrator, who merges.

---

## 3. File ownership matrix (avoid collisions)

| Path | Owner (writes) | Readers | Notes |
|------|----------------|---------|-------|
| `calorai/physics/**` (radiation, canyon, inertia, equilibrium, thermal_wind, downburst, facade) | **Codex** | Cursor (as callee) | Equations cite `docs/physics-references.md`. No UI imports. |
| `calorai/analyst/**` (equity, productivity, economy, statistics, landcover, synoptic, aviation) | **Codex** | Cursor | Each module returns a block dict; never calls the API directly — receives `tiles`/`env` from agent. |
| `calorai/data_source.py` (District catalog, Mock/Live sources, cache) | **Codex** | Cursor (read District) | `elevation_m` lives here. Mock free, live cached. |
| `calorai/sentinel/alerts.py` | **Codex** | Cursor | Declarative `ALERT_RULES` R1–R10. Adding a rule requires an agent block first. |
| `calorai/ml/**` | **Codex** | Orchestrator | `forecast_v1.joblib` is committed; training is synthetic, zero credits. |
| `scripts/**` | **Codex** | Orchestrator | `validate_live.py` is cache-only by design. |
| `tests/test_*.py` for above | **Codex** | Orchestrator | Must stay mock-pinned (`conftest.py` `CALORAI_DATA_SOURCE=mock`). |
| `ui/index.html`, `ui/app.js`, `ui/app.css` | **Cursor** | Codex (read payload contract) | Vanilla JS + canvas, no CDN, no Next.js. PQ tokens: bg #08111f, glass blur 18px, cyan #7dd3fc + amber #ff8600, serif display. |
| `calorai/report.py` | **Cursor** | Codex | PDF sections 12–14 + chart M. `pageCompression=0` (greppable). |
| `calorai/tools.py` | **Cursor** (with contract) | Codex | Thin wrappers over `AgentContext.report()` blocks. Each tool returns `{**block, district}`. |
| `calorai/main.py` (`/api/analysis` payload) | **Cursor** | Codex | Curated payload; adds `elevation`+`landcover`+`synoptic`. |
| `calorai/planner.py`, `calorai/personal.py` | **Cursor** | Codex | Follow-up memory, tldr, translation. |
| `calorai/agent.py` | **Shared — orchestrator-mediated** | Both | The chokepoint. Codex proposes a block, Cursor proposes tool wiring — orchestrator merges. No direct concurrent edits. |
| `plan.md`, `orchestration.md`, `render.yaml`, `Procfile`, `CONCEPT.md`, `AI_DISCLOSURE.md` | **Orchestrator** | Both | |

**Frozen (no one edits without orchestrator approval):** `tests/conftest.py` (mock pin),
committed parcel imagery (`data/satellite/satellite_parcel_*.json`,
`data/street_view/streetview_parcel_*.json`), `.env` (gitignored).

---

## 4. Branch & merge contract

- **Naming:** `codex/<short-kebab>` and `cursor/<short-kebab>` (e.g. `codex/synoptic-edge-cases`, `cursor/evidence-panel-polish`).
- **Lifetime:** one task per branch, squash-merged by orchestrator, branch deleted.
- **Handoff packet (required from Codex/Cursor):**
  1) `git diff --stat` + full diff
  2) `git status --porcelain`
  3) Test output: `.venv/Scripts/python -m pytest -q` (must be ≥229, show last 10 lines)
  4) For Cursor: `node --check ui/app.js` + `/api/analysis?district=phoenix` payload keys assertion
  5) For Codex: `python -m py_compile <touched>` if physics
- **Orchestrator merge steps:**
  1) `git fetch origin` + `git checkout main` + `git merge --no-ff <topic>` (resolve `agent.py` by keeping both blocks if additive)
  2) Re-run full suite + `build_pdf_report` smoke (`python -c "from calorai.report import build_pdf_report; ..."`)
  3) `git push` + update `plan.md` checklist

---

## 5. Prompt templates (copy-paste)

### 5a. Codex — backend/physics/analyst

```
You are Codex working on calorai (FortyGuard Hackathon'26, Track 6 Agentic).
Repo: priyapalhandique/calorai, branch codex/<task>. Read plan.md §2.6-2.7 before editing.

Task: <ONE sentence, e.g. "Make synoptic_block handle humidity_pct None entries and add missing-hour tests.">

Allowed files: <e.g. calorai/analyst/synoptic.py, tests/test_synoptic_landcover_elevation.py>
Forbidden: ui/*, calorai/report.py writes beyond adding a block key, calorai/main.py payload shape.

Steps:
1) Read the target file + its tests + calorai/agent.py report dict shape.
2) Implement the change. Keep functions pure, deterministic, mock-safe. No API calls.
3) Extend tests/test_<module>.py — mock, deterministic, no live. Assert present True/False branches.
4) Run: D:\Projects\calorai\.venv\Scripts\python.exe -m pytest -q (must stay ≥229, last 10 lines).
5) Return: diff, test output, git status --porcelain.

Constraints: never remove tests/conftest.py CALORAI_DATA_SOURCE=mock pin; with_exceedance=False on live (see §7);
no secrets in git; no Set-Content PowerShell corruption (use Python rewrites).
```

Hints — use these verbatim:
- N5 live pull gate: `"Add scripts/pull_phoenix_parcel.py with --live flag: 1 satellite + 1 streetview for Phoenix center (33.4484,-112.0740), writes to data/satellite/satellite_parcel_phoenix_2024-07-15.json and data/street_view/streetview_parcel_phoenix.json matching the !data/... re-include globs, skips if exists, prints cost."`
- Elevation edge: `"District.elevation_m may be 0.0 — lapse 0; test vegas-strip 620m sea-level delta."`
- Synoptic none: `"synoptic_block(None, None, None, None, None) must return present False with reason."`

### 5b. Cursor — frontend/report/tools

```
You are Cursor on calorai UI. Branch cursor/<task>. Read ui/index.html + ui/app.js + ui/app.css + calorai/report.py + calorai/agent.py report dict before editing.

Task: <ONE sentence, e.g. "Polish Analytics Evidence panel — show satellite segments as a bar, add empty-state for present False.">

Contract: /api/analysis returns {elevation, landcover, synoptic, alerts, diurnal, ...} — see calorai/agent.py:524-552 and calorai/main.py:174-202. Keep it.

Steps:
1) Edit html+js+css (vanilla JS + canvas only, no CDN, no Next.js, keep PQ tokens, starfield, fade-up).
2) node --check ui/app.js
3) Manual: fetch /api/analysis?district=phoenix&date=2026-08-18&hour=14 and assert keys elevation|landcover|synoptic.
4) Return: diff, node check, payload keys.

Constraints: keep 4-act tabs (Overview/Physics/Analytics/Ask), glass blur 18px, dark/light toggle, localStorage only.
```

Hints:
- Keep `app.js:493 renderAnalytics()` idempotent; new renderers `renderSynoptic`/`renderLandcover`/`renderElevation` already wired.
- `report.py` sections 12-14 must stay `pageCompression=0` (diff-friendly), chart M `_synoptic_chart` uses band color `low #4a7a5a / moderate #c2600a / high #a02020`.

### 5c. Orchestrator — self merge

```
Merge codex/<task> + cursor/<task> into main. Resolve calorai/agent.py by keeping both additive blocks.
Run: .venv/Scripts/python -m pytest -q (229+), node --check, build_pdf_report smoke, then push and update plan.md §2 checklist.
```

---

## 6. Work — remaining waves

### Wave 1 (parallel, 1 session each)
- **Codex:** Commit pending `M scripts/validate_live.py` always-write patch (5 lines, `raise` → append error + continue). Extend `tests/test_synoptic_landcover_elevation.py` with None-edge cases and vegas-strip elevation check.
- **Cursor:** Polish `ui/app.js` analytics cards (empty-state wording, bar width 0.82 already), `ui/index.html` heading `R1–R7 + R8–R10`, `calorai/report.py` chart M legend.

### Wave 2 (orchestrator, after Wave 1 merges)
- Credit ledger in `plan.md` already corrected (208k/2M, 10.4%); `docs/ml-validation.md` Stage 2 already filled (phoenix 24-h, surrogate 9.54 vs physics 11.74, surrogate-physics 2.46, layer offset -2.24). Draft `CONCEPT.md` 500-word (problem → user → FortyGuard → result) and 3-min video storyboard. Add `render.yaml` + `Procfile` + `.github/workflows/keepalive.yml`.

### Wave 3 (user-gated, C2 deploy)
- User: create Render free Web Service from `priyapalhandique/calorai`, add env `FORTYGUARD_API_KEY`, share URL.
- Orchestrator: set `LIVE_URL` repo variable, GH Actions keepalive ping `/api/health` ~10 min, incognito verify (no install, no login), screenshot for README.

All waves keep mock-first guarantee — demo never requires a live key to run.

---

## 7. How to improve the project further (scoring levers, Impact 40 / Technical 35 / Innovation 15 / Communication 10)

- **Impact:** Default the Overview district picker to the flagship equity story (Maryvale, Phoenix — redlined tract-housing) alongside Phoenix/Vegas Strip. Surface the cross-city equity leaderboard (`analyst/equity.py:cross_district_leaderboard`) as a scheduled brief, not a hidden API.
- **Technical:** Keep every number traceable. The `report.py:564` provenance string already cites Oke Eq. 5.18, Brutsaert sky, Wallace & Hobbs Eq. 7.20, Caracena 1990. Mirror the `docs/ml-validation.md` layer-offset caveat into a UI tooltip on the theory-vs-data card.
- **Innovation:** Street-level evidence is the judge-visible differentiator — make it the Act 4 hero card with real percentages (Diridon sky 39.7%, building 7.69%) and a one-line *"why this block is hot"* explanation, not a footnote. Synoptic VPD chart is the climate-physics depth that other teams lack.
- **Communication:** Video 3-min beats: 0:00 problem (Phoenix 111 d >100°F) → 0:30 API (tcm layer) → 1:00 audit (one district, one hour) → 1:30 agent chat + trace table → 2:00 interventions + PDF → 2:30 live URL incognito. README hero equation + architecture diagram (4 modules × NL loop) stays above the fold.

---

## 8. Further scopes (presumptive — per `docs/roadmap.md`, not built, breadth without bloat)

**Short-term (credit-gated, honest):**
- Multi-day heat-wave pull (3 dates × 1 district, ~3 env + 3 tcm) for a true heat-wave day definition.
- Census ACS income overlay for equity (external, cited, not redistributed).
- Bus-stop shade ranking (planned D4–5, `analyst` + `physics/canyon.py` + OSM stops — zero credits).

**Mid-term (portfolio scale):**
- Parcel portfolio heat-screening at scale — the two notebooks in `notebooks/use_cases/` already demo it with committed imagery.
- Facade seasonality advisor (“when to shade which orientation” — `physics/facade.py` deep-summer flip already exists).
- Real IoT mist rig integration (valves, not just `responder/misting.py` physics).

**Out of scope (document, do not build):** cyclone coupling (needs synoptic pressure/SST/steering), downburst *forecasting* (needs radar/CAPE — we only ship the Caracena thermodynamic diagnostic), energy-grid demand coupling, insurance risk pricing.

Each presumptive item: state what it would need, why we did not build it, and where the hook would be. Honesty in “what doesn't work yet.”

---

## 9. Guard rails for API usage (concrete, enforceable)

**Budget anchor:** 208,240/2,000,000 (10.4%) used: Heatmap 156,140 (7.81%) + Env 43,500 (2.17%) + Heat Intelligence 8,600 (0.43%), expiry Sep 22. Hard stop at 1.2M. Run `POST /v1/system/fetch-api-key-usage` before any live wave (usage monitoring verified via `client.fetch_api_key_usage`).

**Leaks already fixed (keep them fixed):**
- `LiveFortyGuardSource:469-482` now probes analysis layers once per process (`_analysis_layers_unavailable: set[str]`) and skips unavailable exceedance/persistence — previously 2 paid-but-empty heatmap calls per audit (≈8.4k per `/api/analysis` page load on the Basic plan).
- `AuditBody.with_exceedance` in `main.py:44` now defaults `False` (was `True`) — live demo no longer burns plan-limited layers by default.
- `scripts/validate_live.py:18-45` is now cache-only (`cached_hours()` via SHA-256 of endpoint+args, `MAX_UI_TILES=900` analogue for validation) — refuses network on cache miss. The 08-20 validation (phoenix 24 h + san-jose 4 h) already spent ~117k heatmap credits against a ~4.5k plan line; the rerun is zero credits and that ledger correction is in `plan.md`.

**Rules for any worker:**

1. **Cache-first law.** Never pull live if a disk cache hit exists. Key: `hashlib.sha256(json.dumps({"endpoint": endpoint, **args}, sort_keys=True, default=str)).hexdigest()[:20]` under `data/cache/`. Env series is one call per (district,date) with `schema_version=2`.

2. **Mock pin.** `tests/conftest.py` pins `CALORAI_DATA_SOURCE=mock`. Never remove it; never run suite live (suite was burning credits via `.env` before the pin).

3. **Live call discipline.** Any live heatmap call needs orchestrator approval. Default `with_exceedance=False`, `granularity=100`, reuse `snapshot.env` for the 24-h series. No scope creep on live AOI/date — pin `2024-07-15` (catalog-proven) until submission.

4. **Gitignored data.** `data/cache/`, `data/validation_live.json`, `.env`, `.venv`, `outputs/` stay ignored. Committed parcels (`data/satellite/satellite_parcel_*.json`, `data/street_view/streetview_parcel_*.json`, `data/heatmaps/heatmap_parcel_*.json`, `data/env_params/env_params_parcel_*.json`) are the *only* tracked data — new Phoenix live pulls must match `!data/...` re-include globs to be trackable, otherwise they stay local.

5. **PowerShell trap.** `Set-Content` corrupts files — use Python rewrites. Pre-push: `git status --ignored --porcelain` must show only `!!` lines for the set above; `git diff --stat` must not contain `.env`.

6. **Validation honesty.** Report the bad numbers too: surrogate MAE 9.54 vs tile layer reflects canopy-vs-skin layer semantics (offset -2.24), not a model defect. Quote that in `docs/ml-validation.md` Stage 2 and the dashboard tooltip.

---

## Appendix A — File ownership quick-reference

```
Codex owns:  calorai/physics/*, calorai/analyst/*, calorai/sentinel/*,
             calorai/data_source.py, calorai/ml/*, scripts/*
Cursor owns: ui/*, calorai/report.py, calorai/tools.py,
             calorai/planner.py, calorai/personal.py, calorai/main.py
Shared:      calorai/agent.py  (orchestrator merges)
Frozen:      tests/conftest.py, data/satellite/*, data/street_view/*
```

## Appendix B — Branch naming & merge checklist

- `codex/<verb>-<noun>` e.g. `codex/landcover-shade-physics`
- `cursor/<verb>-<noun>` e.g. `cursor/evidence-panel-polish`
- Checklist: `pytest ≥229` + `node --check` + `build_pdf_report` + `/api/analysis` keys + `git push` + `plan.md` checkbox

## Appendix C — Handoff packet template

```
Branch: codex/synoptic-edge-cases
Diff: 2 files, +45 -3
Tests: 229 passed (4 new)
Status: clean (no untracked outside data/cache)
Notes: VPD skips None humidity entries, caveat single-day.
```

---

*Last updated: 2026-08-20. Next update after Wave 1 merge.*
