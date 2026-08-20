# calorai — location analysis & hypothesis-fit (evidence memo)

*Aug 20, 2026. Decides which US locations the audit is demonstrated on and why
our physics should hold there. Web research below is cited; live coverage probes
(pin **2024-07-15**) confirm the FortyGuard catalog before any credit spend.*

---

## 1. Selection criteria (what the hypothesis needs)

| Our physics | Needs |
|---|---|
| Solar-absorption attribution (core) | Strong sun, low cloud, high tile spread |
| Street-canyon trapping (H/W, SVF) | Dense, tall building canyons |
| Misting / evaporative cooling (M3) | **Dry air** — evaporative efficiency collapses with humidity |
| WBGT worker safety (M2) | Hot + sunny outdoor sites |
| Facade seasonality (deep-summer flip) | High summer solar elevation (low latitudes) |
| Equity Gini (M4) | Large intra-city temperature contrast |
| Impact headline (40% rubric) | **Large exposed population** |

## 2. Evidence — hottest big US cities (summer)

| City | Avg summer temp | 100 °F+ days/yr | Humidity | Clear sky | Source |
|---|---|---|---|---|---|
| Phoenix, AZ | 93.7–96.4 °F | **111** | 24.9% | 68.7% | apartmentlist.com; cw33.com study (2026) |
| Las Vegas, NV | 90.8–93.7 °F | **78** | **18.5%** | **99.2%** | apartmentlist.com; cw33.com |
| Dallas, TX | 84.5–86.5 °F | 22 | 57.3% | 72.8% | cw33.com; usaleaders.com |
| Austin, TX | ~85 °F | 29 | ~50% | — | homegrail.com |
| Houston, TX | 94.5 °F | 3 | Gulf moisture | — | usaleaders.com |

Ranking context: Phoenix leads US peak heat (record 122 °F); Yuma/Tucson are
smaller AZ cities; Miami is warm year-round but humid. Sources disagree on exact
values but are unanimous on the **top tier: Phoenix, Las Vegas, Texas metros**.

## 3. Evidence — population exposure / urban heat island (Climate Central 2024)

- NYC: **highest per-capita UHI of 65 cities (9.7 °F)**; **7.27M residents (83%)**
  live where the built environment adds ≥8 °F (climatecentral.org, 65-city analysis).
- Chicago 8.7 °F (1.70M / 62%); Los Angeles 1.98M / 51%; Houston 1.77M / 77%;
  Dallas 1.06M / 81%; San Antonio 1.27M / 88%; Newark 9.0 (97%).
- Equity: 33.8M of 50M studied (68%) live in UHI ≥8 °F zones; Hsu et al.
  (*Nature Communications* 2021, open access) find people of color and those below
  the poverty line disproportionately exposed in **169/175** largest urbanized areas
  — the empirical backbone of our M4 equity analysis.

## 4. Hypothesis-fit scores (candidate locations)

| Location | Solar | Canyon | Misting | WBGT | Equity | Population | Fit |
|---|---|---|---|---|---|---|---|
| **Phoenix (city)** | A | B | A | A | B | 1.6M | ★★★★★ |
| **Las Vegas Strip** | A | A (hotel canyons) | **A+** (driest) | A | C | 2.3M metro | ★★★★★ |
| **Manhattan/NYC** | C | **A+** (deep canyons) | D (humid) | B | **A+** | **7.3M** | ★★★★☆ |
| **Maryvale, Phoenix** | A | C (low-rise) | A | A | **A+** (redlined) | ~130k | ★★★★☆ |
| **East Harlem, NYC** | C | A | D | B | A+ | ~120k | ★★★☆☆ |
| Dallas | A− | B | B | A | B | 1.3M | ★★★★☆ |
| Houston | C | B | D (humid) | A+ | A | 2.3M | ★★★☆☆ |
| Chicago (mock) | C | B | D | B | B | 2.6M | ★★☆☆☆ |

## 5. Decision (two-tier)

**Tier 1 — city leaderboard (breadth, mock-first):** Phoenix, San Jose, Lower
Manhattan, Chicago, Austin, + subdivision districts below. Feeds the M4
cross-city comparison + comparative agent (U6).

**Tier 2 — subdivision deep-dive (the demo):**
- **Maryvale, Phoenix — flagship.** Historically redlined west-Phoenix
  neighborhood, repeatedly documented as one of the hottest and most
  heat-inequitable areas in the US; solar + misting + WBGT + equity all hold.
- **Las Vegas Strip — misting showcase.** Driest + clearest big-city sky
  (18.5% humidity, 99.2% clear), extreme hotel canyons; the Strip *already mists
  in reality* — our model tells operators when/where, with a water budget.
- **East Harlem, NYC — equity contrast.** Dense canyons, humidity-limited misting
  (honest boundary), strongest public-policy population story next to Manhattan.

**Live pulls (deferred until infra is green):** Las Vegas + Manhattan/NYC
(+ Dallas optional) on **2024-07-15** at ~4.5k credits each. Protocol: small-AOI
coverage probe first → full heatmap + env only if cells return → cache everything.
Zero-cell response = drop the location (catalog lag), fall back to mock.

## 6. Credit ledger (planned)

| Item | Est. credits |
|---|---|
| Vegas: heatmap + env | ~4.5k |
| Manhattan/NYC: heatmap + env | ~4.5k |
| Dallas (optional) | ~4.5k |
| Forecast validation (held-out live 24-h env) | ~4.5k |
| **Total new** | **~9–18k** (4.8–9% of 2M) |

## 7. Deliverables fed by this memo

- New mock districts: `maryvale`, `vegas-strip`, `east-harlem` (data_source.py)
- M4 cross-city leaderboard (equity Gini, WBGT, vulnerability, productivity)
- U6 comparative agent ("Phoenix vs Las Vegas, July 15")
- Video: per-city headline numbers with the population-exposure framing