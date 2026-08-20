# Physics References & Implementation Notes

Where every equation in calorai comes from, and how the shipped code
maps onto it. The four source texts live locally in `Resources/`
(never committed — cited, not redistributed).

## Tier A (shipped 2026-08-19, 73 tests)

| Model | Equation | Source |
|---|---|---|
| Brutsaert clear-sky emissivity | ε_sky = 1.24·(e_a/T_a)^(1/7) | Campbell & Norman 1998, *Introduction to Environmental Biophysics*, Ch. 10 (p. 163; the formula they present as "Brutsaert 1984") |
| Cloud-blended sky temperature | ε_eff = (1−c)·ε_clear + c; T_sky = T_a·ε_eff^0.25 | Oke et al. 2017, *Urban Climates*, §5.2 longwave exchange |
| Wind-aware convection h_c = 5.7 + 3.8·u | McAdams forced-convection flat-plate correlation | Oke 1987, *Boundary Layer Climates*, Table (street values); verified range 5.7–43.7 W/m²·K |
| Globe-estimated WBGT 0.7·T_wb + 0.2·T_g + 0.1·T_db | Natural-ventilation globe form | Yaglou & Minard 1957 (US Navy); NOAA/NWS operational method |
| WBGT forecast accuracy context | SERCC/CISA within 0.6 °C of observations; wind sheltering is the main error source | Clark, Konrad & Grundstein 2024, *Development and Accuracy Assessment of Wet Bulb Globe Temperature Forecasts* (NOAA technical report 65112) |
| Solar geometry (declination, hour angle, elevation, tilted-plane) | δ = 23.44°·sin(360°(284+n)/365); H = 15°(t−12) + (λ_sm − λ) | Campbell & Norman Ch. 11 (radiation geometry); Oke 1987 §2.4 |

## Tier B (shipped 2026-08-19, 88 tests total)

### B1 — Street-canyon radiation trapping (`calorai/physics/canyon.py`)
- **Sky view factor** ψ_sky = √(1 + (H/W)²) − (H/W) for the mid-street
  floor of an infinitely long canyon — Oke et al. 2017 Fig. 5.10
  (after Johnson & Watson 1984). Roofs: ψ = 1; deep canyons → 0.
- **Effective canyon albedo** α_surf = (W·α_f + H·(α_w1 + α_w2))/(2H + W)
  — Oke et al. Eq. 5.18. Walls darker than the street (shadowed
  facades) lower the effective albedo below the open floor's; the
  multiple-reflection "trapping efficiency" R_c (their Eq. 5.19 and
  Fig. 5.11) is noted but not yet parameterized.
- **Longwave environment** L↓ = ψ·L_sky + (1−ψ)·ε_w·σ·T_w⁴ — the floor
  sees warm walls through (1−ψ) instead of the cool sky (their §5.2.3);
  implemented as an effective radiative-environment temperature fed
  into the existing `net_longwave_flux`.
- **Wind sheltering** f(H/W) — Oke et al. Ch. 4 flow regimes: isolated
  roughness (< 0.35) keeps ~100% of the above-roof wind, wake
  interference (0.35–0.65) ~75%, skimming flow (> 0.65) ~55% at street
  level; the street-level h_c is scaled accordingly (Clark, Konrad &
  Grundstein 2024 identify wind sheltering as the dominant WBGT
  forecast error). Phoenix live: 12.0 → 9.3 W/m²·K; Manhattan: 6.6.
- Live check (Phoenix, 2024-07-15 14:00): H/W = 0.5 → ψ_sky = 0.618
  (exact book value √1.25 − 0.5), canyon environment 28.9 °C vs open
  sky 25.6 °C (+3.3 K of wall shielding).

### B2 — Thermal admittance, damping depth, force-restore storage (`calorai/physics/inertia.py`)
- **Thermal admittance** μ = √(k·ρ·c) — Campbell & Norman Ch. 8
  (Eq. 8.9 region); identical to the thermal effusivity for a
  semi-infinite medium. Asphalt: ~1683 J·m⁻²·K⁻¹·s⁻¹/².
- **Damping depth** d = √(2k/(ρ·c·ω)) — Campbell & Norman Eq. 8.5/8.6;
  asphalt ≈ 0.14 m, i.e. the diurnal wave lives in the top ~14 cm.
- **Diurnal phase lag** P/8 = 3 h for the homogeneous semi-infinite
  ideal (Campbell & Norman Ch. 8); Oke et al. 2017 §5 reports 2–5 h
  for real urban fabric — the auditor's peak-lag fingerprint for how
  much a district stores heat. The report now compares the *measured*
  peak lag (env-series peak hour vs local solar noon; solar noon from
  the district's longitude + UTC offset) against the ideal: Phoenix
  live 2.5 h vs 3.0 h ideal; Manhattan's layer peaks essentially at
  solar noon (0.1 h) — a live-data finding that this layer tracks the
  sun directly.
- **Force-restore storage** Q_G = μ·√(ω/2)·(T_s − T̄) + (μ/√(2ω))·dT_s/dt
  (Blackadar 1976 form, as used in Oke et al. §5.4). Independent of
  slab-thickness assumptions. Cross-check (Phoenix): 119.4 W/m² vs
  the slab model's 112.4 W/m² — within 6%.

### B3 — Latent heat, Priestley–Taylor (`calorai/physics/latent.py`)
- λE = α·s/(s+γ)·(Q* − G), α = 1.26 — Monteith & Unsworth 2014,
  *Principles of Environmental Physics* (4th ed.), Eq. 13.40–13.41
  (equilibrium evaporation + Priestley–Taylor); de Bruin 1983 for the
  parameter range.
- Psychrometric constant γ = c_p·P/(0.622·λ) ≈ 0.067 kPa/K at sea
  level; saturation-vapor-pressure slope s via the Tetens/Magnus form
  (s(30 °C) ≈ 0.243 kPa/K).
- Scaled by the surface's evaporative fraction (0 dry fabric, 1 open
  water). Dry districts (all five demo districts) credit 0; green-roof
  interventions draw from it (≈7.1 °C relief at f_evap = 0.5,
  Phoenix live conditions).

### B4 — Equilibrium solver + sensitivity bands (`calorai/physics/sensitivity.py`)
- Quasi-steady equilibrium surface temperature via Newton iteration on
  F(T) = Q_sol − Q_lw − Q_conv − Q_store − Q_lat with the analytic
  derivative F′ = −(4εσT³ + h_c).
- Symmetric ±ΔT bands from finite-difference parameter perturbations
  (albedo ±0.02, emissivity ±0.02, h_c ±2.0, G ±50 W/m², T_env ±2 K).
  Phoenix live: irradiance dominates (±2.2 K), wind (±1.4 K), albedo
  (±0.5 K) — the honest uncertainty envelope for every headline number.

## Track 2 / Track 5 (shipped 2026-08-19, 108 tests total)

### T2a — Facade-orientation advisor (`calorai/physics/facade.py`)
- Wall flux via the tilted-plane beam projection at tilt = 90°:
  G_wall = (1−k_d)·GHI·max(cos el·cos(az−ψ), 0)/sin el + k_d·GHI/2 +
  ρ_g·GHI/2 — Campbell & Norman Ch. 11 (radiation geometry on tilted
  planes); Oke 1987 §2.4.
- `solar_azimuth_degrees` added to `solar.py` (NOAA cosine formula);
  `clear_sky_ghi_w_m2` = S₀·sin(el)·τ, τ = 0.75, used for orientation
  *ranking* when only a daily scalar exists (documented caveat).
- Seasonality is the point: at the equinox the south facade is hottest
  (Phoenix: 4.84 kWh/m²/day vs north 1.22); in deep summer the sun is
  nearly overhead and the south wall is *coldest* (2.27 vs north 2.69,
  which catches ENE morning beam) — glazing advice must be seasonal.

### T2b — Retrofit economics (`calorai/physics/economics.py`)
- E_avoided = U·A·DH·ΔT / (1000·COP) — transmission-physics reduction
  of the cooling load, ΔT being the physics engine's intervention
  number (°C). COP = 3.5, U = 0.5 W/m²·K defaults; assumptions are
  returned with the numbers.
- Cooling-season degree-hours proxy DH = hot_days·h_day·max(0, T̄ −
  18.3 °C balance) with a hot-days scaling 100 + 12·(T̄ − 26), capped
  at 200 days — documented proxy, not a load model.
- Live Phoenix audit: cool-roof ΔT 16.8 °C over 21 240 °C·h → 20 378
  kWh/yr avoided, $3 057/yr, 3.3-yr simple payback on one 400 m² tile
  at $25/m².

### T5 — Packaged vulnerability & safety models (`calorai/physics/vulnerability.py`)
- Vulnerability score (0–100) = WBGT intensity (40) + exceedance
  duration (20) + population sensitivity (20) + dose past the
  very-high band (20); bands low/medium/high/critical. Transparent
  weights so a heat officer can see *why* a score is high.
- Worker-safety alert: effective WBGT = measured + work-intensity
  offset (light −0.5, heavy +1.0 °C), band guidance from the OSHA-style
  ladder in `stress.py`. Phoenix audit hour: WBGT 42.8 °C → 84/100
  critical, "Stop heavy outdoor work".

## Ground-truth validation sources
- **NOAA 65112** (Clark, Konrad & Grundstein 2024): WBGT forecast
  accuracy ±0.6 °C, wind sheltering as dominant error → motivates our
  canyon wind treatment (B1) and h_c sensitivity (B4).
- Garg, Bansal & Ghosh, *Thermal Physics*, Tata McGraw-Hill — Ch. 11:
  Stefan's law E = σT⁴ (Eq. 11.8, σ = 5.672×10⁻⁸ W·m⁻²·K⁻⁴) and the
  exact linearization of the fourth-power exchange to Newton's law of
  cooling, E = 4σA·T̄³·ΔT (Eq. 11.10) — the derivation-grade basis of
  our `linearized_conductance`/`radiative_conductance` and every
  ΔT = ΔQ/H mitigation lever; Appendix IV (conduction) grounds the
  damping-depth/storage terms. Chapters 1–10, 12–15 (kinetic theory,
  statistics) are not used.
- Oke, Mills, Christen & Voogt 2017, *Urban Climates*, Cambridge Univ.
  Press — canyon geometry (§5.2), urban energy balance (§5.4), LCZ
  fabric properties (Table 2.2), UHI circulation scale (Ch. 4).
- Campbell & Norman 1998, *Introduction to Environmental Biophysics*,
  2nd ed., Springer — Ch. 8 (soil heat, admittance), Ch. 10 (sky
  emissivity), Ch. 11 (radiation geometry).
- Monteith & Unsworth 2014, *Principles of Environmental Physics*, 4th
  ed., Academic Press — Ch. 13 (evaporation, Priestley–Taylor).

## M4 — analyst, circulation & downburst (shipped 2026-08-20, 140 tests total)

### M4a — Heat equity (`calorai/analyst/equity.py`)
- Gini coefficient on the tile temperature distribution (standard
  definition, computed from the sorted distribution) + quintile gap
  (hottest 20% minus coolest 20%, K) + exposure share above threshold.
- Why it matters: Hsu et al. 2021, *Nature* 598, "Disproportionate
  exposure to urban heat island intensity across major US cities" —
  169 of 175 cities burden low-income / non-white neighbourhoods more;
  Climate Central 2024 UHI exposure analysis (NYC highest per-capita
  UHI at 9.7 °F, 7.27 M residents / 83% exposed). Our mock flagships
  (Maryvale PHX, East Harlem NYC) are redlined / equity-contrast AOIs.

### M4b — Productivity (`calorai/analyst/productivity.py`)
- Work-capacity loss vs WBGT via an S-shaped curve per work intensity
  (light/moderate/heavy): parameterization of the physiological curves
  of Dunne et al. 2013, *Nature Climate Change* 3, "Reductions in
  labour capacity from heat stress under climate warming", and
  Kjellstrom et al. 2009, *Glob. Health Action* 2 — near-full capacity
  below ~28–29 °C WBGT, steep transition, intensity-dependent
  saturation (10/25/40 %). Assumptions (workers, hours, hot days,
  wage) are returned with the USD figures, never hidden.

### M4c — Economy (`calorai/analyst/economy.py`)
- District cost of heat = cooling-energy spend (the top intervention's
  avoided kWh valued at the ROI module's implicit price) + labour-
  productivity loss (M4b at the district WBGT). Bottom-up from audited
  physics; health costs explicitly excluded (documented).

### M4d — Thermal-wind proxy (`calorai/physics/thermal_wind.py`)
- **Hydrostatic pressure perturbation** of a warm column: dp/p ≈
  g·H·dT/(R·T²) over a 1 km mixed layer (Wallace & Hobbs 2006,
  *Atmospheric Science*, 2nd ed., Ch. 3 hypsometric equation; Eq. 3.29
  family). Phoenix-scale check: ΔT = 4 K over 1 km → ~1.4 hPa surface
  deficit — matches the published UHI pressure deficit scale.
- **Thermal wind** V_T = (R/f)·ln(p₁/p₂)·(k × ∇T̄) — Wallace & Hobbs
  §7.2.7, Eq. 7.20: vertical shear ∝ horizontal temperature gradient;
  aloft flow parallel to isotherms, warm air on the right (NH). Used
  for the upper-branch direction only.
- **Urban-breeze inflow** toward the low-pressure core (Oke et al.
  2017 Ch. 4 UHI circulation; ~1–3 m/s for 4–8 K core excess — speed
  scale 0.4 m/s per K, documented).
- Honesty contract: *relative* circulation from the temperature field
  alone; the API ships no wind (P2-4 in docs/fortyguard-products.md),
  so magnitudes are scale estimates, not a momentum solve. The report
  states this caveat verbatim. Gradient via a robust least-squares
  plane over (lon, lat, T) with a 1-D collinear fallback (single street
  rows still yield a direction).

### M4e — Downburst diagnostic (`calorai/physics/downburst.py`)
- Wet-bulb depression D = T_app − T_wb per hour; bands from Caracena
  1990, "Downbursts: meteorological conditions associated with their
  generation" (AMS *Meteorological Monographs* 25; dry microbursts
  need D ≳ 12–15 K below cloud base) and Wakimoto 1985 (composite
  microburst life cycle) — implemented as a documented parameterization:
  no rain in the trailing 3 h → low; rain & D < 8 K → low; 8–14 K →
  medium; ≥ 14 K → high.
- Diagnostic, not forecast: the env series is the district meso-scale
  environment, not a storm-scale sounding; apparent temperature proxies
  dry-bulb. Both caveats ship in the report block.

## Verification of experimental-vs-theory agreement
1. ψ_sky(H/W=0.5) = 0.618 exactly matches √(1.25) − 0.5 (Oke Fig. 5.10).
2. Force-restore vs slab storage agree within 6% on live Phoenix data.
3. Brutsaert sky emissivity values (0.71–0.85 across our districts'
   humidity range) sit in the published range (C&N Fig. 10.6).
4. Equilibrium-solver surface temperature (53.1 °C Phoenix at noon)
   reproduces the explicit energy-balance zero to <1e-6.
5. Priestley–Taylor flux never exceeds the available energy
   (α·s/(s+γ) ≤ 1 at T ≤ ~31 °C) — the book's bound.
6. Thermal-wind scale sanity: ΔT = 4 K over a 1 km column → ~1.4 hPa
   (mock Maryvale: 5.5 K core excess → 1.6 hPa deficit) — within the
   published UHI pressure-deficit range; inflow direction always points
   at the fitted hot core (unit-tested, incl. collinear single-row
   fallback); thermal-wind bearing ⊥ gradient with warm air on the
   right (NH) — verified against W&H §7.2.7 Fig. 7.15 geometry.
7. Downburst discrimination (unit-tested): rain through dry air
   (D = 18 K) → high; rain through humid air (D = 3 K) → low; dry with
   no rain → low. Mock east-harlem shower (D ≈ 2.5 K) correctly stays
   low — rain alone is not a microburst signature.