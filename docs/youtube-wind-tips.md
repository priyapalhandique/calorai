# Wind Analysis Tips — Autodesk Forma Video (Resources/Youtube)

Source: `Resources/Youtube/Autodesk Forma Series - Episode 03 - Wind Analysis + Proposals.txt` (transcript) + `Resources/Youtube/frames/*.png` (780 frames, gitignored via `Resources/` in `.gitignore:222`). Video file `Resources/Youtube/vidssave.com ... 720P.mp4` stays gitignored (not committed).

Video: **CFD-based wind analysis** — how design impacts site + adjacent context + occupant comfort, via Forma proposals side-by-side for passive strategies.

## Tips Extracted (Forma → calorai)

### 1. Two Wind Modes
- **Rapid AI wind** — real-time, updates almost immediately when you move a building or add geometry (e.g., opaque wall for outdoor dining → green area added). Use for instant feedback.
- **Detailed CFD** — 30–90 min, cloud-based, blue button, saved results (no recalc unless geometry changes). Use for final validation.
- **Calorai mapping:** `wind_corridor` rapid = thermal proxy + canyon sheltering + tree porosity (instant). No detailed CFD in hackathon — caveat: `wind_corridor.caveat: rapid thermal proxy, not CFD. Detailed CFD would be 30–90 min (Forma).`

### 2. Comfort vs Direction
- **Comfort mode:** scale across bottom — red = uncomfortable. Categories: `comfortable sitting`, `standing`, `strolling`, `uncomfortable`. Click area → category.
- **Direction mode:** wind speed in mph. Add streamlines.
- **Calorai mapping:** `COMFORT_BANDS` sitting <2.5, standing 2.5–3.9, strolling 3.9–6.0, uncomfortable >6 (m/s), street wind `street_speed_m_s` + `comfort` in `wind_corridor`.

### 3. Streamlines by Importance
- **Streamlines set to `importance`** = most dominant wind streams. Wind rows show dominant direction (e.g., south across river 35%, north 14%). Inspect tool gives specific wind speed + dominant direction at point.
- **Calorai mapping:** `thermal_wind.continuous_field` vectors decimated to 42, `inflow` orange solid + `thermal` teal dashed, `wind_rose` 8 sectors with 35% dominant at `inflow_deg`, opposite 14%.

### 4. Area of Analysis
- **Custom circle** with radius slider to place analysis area. Hot spot on West Street next to building is *created* by towers vs existing conditions → check existing first.
- **Calorai mapping:** `wind_corridor` is per-square (city square). Add `GET /api/analysis?district=...&hour=...` custom circle via AOI polygon in future; for now district = square.

### 5. Proposals & Comparison
- **Duplicate proposal** → rotate towers → hot spot on West Street goes away (rapid AI). Duplicate again → add tree line where wall was.
- **Trees are not opaque:** leaf density `25%` default or `10%` dense, calculated correctly (Forma vegetation, tree tool, close + tall exaggerates). Wall is opaque.
- **Compare tool:** side-by-side 3 runs (baseline, rotated, trees) in Comfort mode, 2D top view helpful. Labels in upper left show proposal name, inspect gives category + dominant wind. Save: results are saved, only recalc if geometry changes. Toggle heat map on ground/roof, sun hours on ground only.
- **Calorai mapping:** `wind_corridor.proposals` 5 variants: `baseline`, `rotated towers 15° (h/w*0.85)`, `opaque wall (leaf 0.05)`, `tree line 25%`, `dense trees 10%` → each `street_speed` + `comfort`. Report §18 shows proposal table side-by-side, UI Analytics wind corridor panel will show same.

### 6. Passive Strategies & Comfort Scale
- Rotating towers affects wind *and* daylight hours → electricity + heating/cooling passive strategies. Check June and December sun hours (direct sun on ground only, not facade).
- **Comfort scale is academic** — what might be comfortable at different wind speeds in certain areas, not the CFD math itself.

### 7. How to Apply in calorai (Street View 3D + Google Maps-like)

- **Street View 3D as geometry source:** Use `data/satellite` (building, tree, earth) + `data/street_view` (building, sky, tree) to derive `h_over_w`, `sky%` → `openness`, `tree_pct` → `leaf_density`/`tree_porosity`. For true 3D mesh, use `Map Tiles API` Photorealistic 3D Tiles via `ui/grand-simulation.html` with Re:Earth fallback (free, no Google key) — already in `ui/grand-simulation.html`.
- **Wind corridors in city square:** `wind_corridor` already gives `corridor_quality` (strong/moderate/weak, weak if h/w>1) + `ventilation_corridors` count from thermal_wind (cool tiles along inflow axis ±45°). Use for `M` continuous field + isotherms already in report chart H and UI `circulation` canvas.
- **For the grand simulation:** Dive deep into `mit-campus` AOI with `pitch 58°` → streets locality names (CAMBRIDGE, MIT CAMPUS, CHARLES RIVER) faint underneath, heatmap draped (alpha 0.62), wind corridors pulsing.

## Implementation in Repo

- Code: `calorai/analyst/wind_corridor.py` (rapid, canyon regime, shelter, porosity, openness, street_speed, corridor_quality, wind_rose, proposals)
- Wired: `calorai/agent.py: wind_corridor_block_data`, `calorai/report.py:18`, `calorai/main.py: /api/analysis wind_corridor`, `calorai/tools.py: wind_corridor`, `ui/grand-simulation.html` + `ui/app.js` + `ui/index.html` Analytics panel
- Docs: this file, `docs/street-view-3d-wind.md` (Google Maps-like 3D), `Resources/Youtube/*` remains gitignored

## Next (if you want more Forma fidelity)

- Add `leaf_density` slider in grand simulation HUD (25% ↔ 10%) to see trees vs wall in real time (rapid AI).
- Add `custom circle` radius slider for wind analysis area in UI (like Forma's radius slider).
- Keep detailed CFD as `caveat` — do not block hackathon submission waiting for it.
