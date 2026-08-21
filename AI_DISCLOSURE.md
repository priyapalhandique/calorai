# AI Disclosure — calorai

*FortyGuard Hackathon'26 · "Building the World's Temperature AI" · Submitted under the Agentic AI track (Track 6). Track 2-style building energy work and Track 5-style modeling are implemented as use cases inside the single Track 6 submission, not as separate secondary tags.*

This document discloses how AI tools were used to build this project, as required by the hackathon rules. It is written in my own voice, is intentionally modest, and every capability claimed here is verifiable in the repository — in code, tests, or documentation — not in intention.

---

## 1. Tools and models used

| Role | Tool / model | How it was used |
|------|--------------|-----------------|
| Orchestration / integration | **Muse Spark / opencode** | Maintained the build plan, branch handoffs, QA checklist, merge discipline, and credit guardrails |
| Backend / physics worker | **Codex** | Implemented and tested backend, physics, analyst, script, and validation changes under the repo's ownership matrix |
| Frontend / report worker | **Cursor AI** | Implemented UI/report/tooling changes under the repo's ownership matrix |
| Primary coding models | AI coding models available inside those tools | Generated implementation code, tests, and documentation text under my direction |
| Planning / architecture model | planning & architecture model (exact name/version TBD) | Used during early planning and architecture phases to pressure-test the design before implementation |

**Plain statement:** the AI generated the code and most of the prose. I directed it at the level of design, physics, and specification, reviewed every change before it was accepted, and take responsibility for the correctness of what is shipped.

---

## 2. How I worked with the AI — prompt-engineering methodology

The value I contributed was not in the prompts themselves but in how they were structured. Four practices carried the project:

**Domain grounding instead of guessing.** When a physics feature was needed, I did not ask the model to "invent" an equation. I supplied the source, the equation number, and the reference. For example, the street-canyon sky-view factor was implemented from Oke et al. *Urban Climates* Fig. 5.10; the Priestley–Taylor latent-heat term from Monteith & Unsworth (Eq. 13.40–13.41); the Stefan–Boltzmann linearization from Garg, *Thermal Physics* (Eq. 11.10). The book-to-code mapping lives in `docs/physics-references.md`. This kept the physics traceable to the literature rather than to pattern-matching.

**Verification-driven prompting.** Every physics feature carried an acceptance criterion: unit tests plus a live API probe against a real U.S. district (Phoenix, San Jose, Manhattan, Chicago, Austin) plus a comparison of theory against the returned data. A feature was not "done" until all three held. This is why the test suite grew from 47 tests to more than 230 mock-pinned tests across the physics, agent, UI, report, ML, and export layers.

**One feature per prompt, with acceptance criteria.** Instead of a single large specification, I asked for one physical mechanism at a time (sky-view factor → canyon albedo → canyon wind sheltering → force-restore storage → latent flux → sensitivity bands), each in its own prompt with its own tests. This made each change reviewable and revertible.

**Constraint framing.** Each prompt restated the constraints the code had to honor: temperatures in °C throughout, no hardcoded API keys, U.S.-only geography, finite credit budget, and the submit-then-poll async pattern. The most valuable of these was the unit discipline — it is why the live theory-vs-data comparison reads in the API's native Celsius and never drifts from what is displayed.

**Review loops.** I read the diffs, ran the suite, and requested targeted revisions. One concrete example: a tool-side file-rewrite corrupted UTF-8 characters in a Python source file (`W/m²` became mojibake). I caught it in review, restored the file from git, and had the change redone through a byte-safe path. The fix is part of the commit history.

---

## 3. Representative instructions and what they produced

The following are paraphrases of the instructions I gave, mapped to the artifact they produced. They are listed to show the *shape* of the prompting, not as a transcript.

| Instruction I gave (paraphrased) | What it produced |
|---|---|
| "Implement the canyon sky-view factor and canyon albedo from Oke with unit tests, wired into the district model." | `calorai/physics/canyon.py`; live check: Phoenix ψ_sky = 0.618, canyon albedo 0.16 |
| "Add a wind-shelter factor for street canyons from Oke's flow regimes and apply it to the convective coefficient." | Wind-shelter block; Phoenix h_c 12 → 9.3 W/m²·K, Manhattan → 6.6 |
| "Compare the equilibrium solver's predicted surface temperature against the API's tile layer across five districts and report the residual honestly — do not fudge it." | `theory_vs_data` verdict in the audit report; exposed that the tile layer reads like a canopy/comfort temperature (35–40 °C), not sunlit skin (48–53 °C), with a systematic 238–258 W/m² residual |
| "Turn the cool-roof temperature reduction into an annual dollar saving and payback period, with documented assumptions." | Retrofit ROI block in the audit report (degree-hours × envelope × COP economics) |
| "Score a building's facades by daily solar load per orientation using the solar-geometry module." | `calorai/physics/facade.py` — cardinal-facade + roof ranking |
| "Probe both credit-usage endpoints live, decode the actual response schema, and surface the real numbers in the report." | Credit monitoring; corrected a flat-key assumption to the real nested schema (`plan_details` / `credit_summary` / `activity_breakdown`) |
| "Check whether the API key is committed anywhere in the repository." | A leak audit over the working tree and all commits — clean; `.env` is git-ignored |
| "Plan a deployment that a judge can open in a fresh incognito window with zero installs, with a health endpoint and a keep-alive." | Render-free deployment plan with `/api/health` and a scheduled keep-alive (in `plan.md`) |
| "Where does the theory predict a temperature the API's layer cannot explain? Show the boundary." | The explicit model-boundary section of the audit report |

---

## 4. Physics judgment I brought to the project

The model computed; the judgment about *what to compute* was mine. The decisions below are the parts of the project I most directly own.

**I chose to build a first-principles energy-balance model, not another heatmap viewer.** The API returns tile temperatures; anyone can color them. The differentiator is explaining *why* a tile is hot — decomposing the balance into absorbed shortwave, longwave exchange, convective exchange, storage, and latent cooling. I selected which mechanisms mattered (canyon trapping, sky emissivity, thermal inertia, latent partitioning) and which did not (kinetic-theory chapters of the physics texts).

**I identified a real discrepancy and kept it visible instead of hiding it.** When the equilibrium solver predicted sunlit skin temperatures of 48–53 °C while the API's `tcm` layer read 35–40 °C at or below air temperature, the honest conclusion is that the two describe different physical quantities (skin vs. canopy/comfort layer). I asked for that comparison to be run across five districts, reported the systematic residual, and shipped it as an explicit model-boundary section rather than tuning the model to the data.

**I decided when an output was physically meaningful and when it was an artifact.** The `env_params` heat-index series is a humidity-sensitivity curve at a fixed temperature anchor, not a forecast — it peaks at 2 a.m. because humidity does. I chose to use it only at the physically meaningful hour and to take exposure duration from the heatmap `exceedance` layer instead. The README documents this so a reader is not misled.

**I chose the operational indices.** WBGT (0.7/0.2/0.1 outdoor weighting), with the globe temperature estimated from solar load when no globe station exists; humidex as the comfort index; exceedance-hours as the duration axis and WBGT as the intensity axis combined into a single risk verdict. These map the physics onto what a heat officer or employer can actually act on.

**I framed the economics.** Cooling-load reduction as U·A·ΣΔT·h / COP, degree-hour proxies for a district's hot season, and payback from retrofit cost — so the temperature physics becomes a budget decision a city or building owner can make.

---

## 5. Scope of this disclosure

What the AI did: wrote code and prose, ran tests, and drafted documentation — all under my direction and review.

What I did not delegate: problem framing, selection of physical mechanisms, interpretation of the theory-vs-data comparison, the product narrative, and the final review of every change. No code entered the repository without my review.

This document complements `ACKNOWLEDGEMENTS.md`, which separately identifies the portions of the repository that are FortyGuard's template (`fortyguard/`, `notebooks/`) versus original work.

---

*Prepared for the FortyGuard Hackathon'26 AI-tools disclosure. Claims herein are verifiable against the repository's code, tests (`tests/`, 232 passing at the latest packaging check), and documentation (`docs/physics-references.md`, `README.md`).*
