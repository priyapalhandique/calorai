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
  much a district stores heat.
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
  fabric properties (Table 2.2).
- Campbell & Norman 1998, *Introduction to Environmental Biophysics*,
  2nd ed., Springer — Ch. 8 (soil heat, admittance), Ch. 10 (sky
  emissivity), Ch. 11 (radiation geometry).
- Monteith & Unsworth 2014, *Principles of Environmental Physics*, 4th
  ed., Academic Press — Ch. 13 (evaporation, Priestley–Taylor).

## Verification of experimental-vs-theory agreement
1. ψ_sky(H/W=0.5) = 0.618 exactly matches √(1.25) − 0.5 (Oke Fig. 5.10).
2. Force-restore vs slab storage agree within 6% on live Phoenix data.
3. Brutsaert sky emissivity values (0.71–0.85 across our districts'
   humidity range) sit in the published range (C&N Fig. 10.6).
4. Equilibrium-solver surface temperature (53.1 °C Phoenix at noon)
   reproduces the explicit energy-balance zero to <1e-6.
5. Priestley–Taylor flux never exceeds the available energy
   (α·s/(s+γ) ≤ 1 at T ≤ ~31 °C) — the book's bound.