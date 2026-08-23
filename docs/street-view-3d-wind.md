# Street View 3D + Wind Corridors — Implementation Ideas from Autodesk Forma Video

Source: `Resources/Youtube/LEc_Jclop6A` — Autodesk Forma Series Episode 03 — Wind Analysis + Proposals (transcript `Autodesk Forma Series - Episode 03 - Wind Analysis + Proposals.txt`, frames `Resources/Youtube/frames/000001.png` …). Video and frames stay gitignored via `Resources/` (`.gitignore:222`), not committed.

## Video Takeaways (what Forma does)

- **Two wind modes:** Comfort (activity-based: sitting `0–2.5 m/s`, standing `2.5–3.9`, strolling `3.9–6.0`, uncomfortable `>6`) vs Direction (mph per wind rose sector). Scale across bottom, red = uncomfortable.
- **Rapid AI vs Detailed CFD:** Rapid AI is real-time (move a building, wall, or tree and the wind updates almost immediately, green area added). Detailed takes 30–90 min (blue button), cloud-based, saved per proposal, no need to recalc until geometry changes.
- **Interactivity:** Streamlines set to `importance` (most dominant wind streams), wind rows show dominant direction (e.g., south across river 35%, north 14%). Inspect tool gives wind speed + category at a point + dominant direction.
- **Proposals:** Duplicate proposal → rotate towers → hot spot on West Street disappears in rapid AI. Add opaque wall vs tree line: trees are not fully opaque, leaf density 25% default (10% dense), Forma understands porosity. Compare 3 runs side-by-side in Comfort mode (2D top view helpful), see trees improve dining area.
- **Existing vs Design:** Custom circle + radius slider to set analysis area; hot spot on West Street next to building is *created* by our towers vs existing conditions (compare).
- **Saving:** Results saved, no recalc unless geometry changes. Heat map and roof toggles, 2D comparison.
- **Limitations noted:** Gap on left of wall still leaks wind → not perfectly accurate, hence detailed CFD.

## How calorai Implements Them (street view 3D + Google Maps-like)

### 1. Street View 3D as Geometry Source (Google Maps-like)
- **Satellite segmentation** (`fortyguard` `satellite_segmentation`, 5 classes: building, tree, earth/ground, plant, others) + **Street View** (6 classes: building, sky 39.67%, tree 6.48%, road 43.08% for Diridon) give `sky_view_factor` (SVF), `building_pct`, `tree_pct` per parcel. These feed:
  - `leaf_density = 0.10 + tree_pct*0.012` (10% dense → 50% max) → `tree_porosity = 1 - leaf_density` (Forma 25% default → 75% porous)
  - `openness = sky_pct/100` (square vs canyon)
  - `h_over_w` from district already gives canyon regime, but we now also derive building height proxy from `building_pct` + `sky` via SVF.
- **Google Maps-like 3D:** Use `ui/grand-simulation.html` with MapLibre/Carto Positron + Re:Earth terrain (free, no key) — draped heat tiles (16,512) + wind vectors + isotherms. Street View 3D is not Google's mesh but our satellite+street-view derived canyon.

### 2. Wind Corridors — Continuous Flow (Forma “importance” Streamlines + Ventilation)
- **Existing:** `calorai/physics/thermal_wind.py: continuous_vector_field(n_grid=14, 320 vectors, inflow + grad + thermal k×grad) + isotherm_contours(1K, 15 contours)` — already the continuous thermal field, visualized in `ui/app.js: drawCirculation()` (orange inflow solid, teal thermal dashed) and report chart **H**.
- **New:** `calorai/analyst/wind_corridor.py` — Forma-style rapid wind:
  - `canyon_regime` (isolated <0.3, wake 0.3–0.7, skimming >0.7) → `shelter_factor` 0.95/0.72/0.55 (Oke)
  - `street_speed = speed_scale * shelter * (0.6+0.4*openness) * tree_porosity` → `comfort` via `COMFORT_BANDS`
  - `wind_rose` 8 sectors (dominant 35% at `inflow_deg`, opposite 14% like Austin video) — thermal proxy, not anemometer
  - `proposals` 5 variants: baseline, rotated towers 15° (`h/w*0.85`), opaque wall (`leaf 0.05`), tree line 25%, dense 10% → each `street_speed` + `comfort` (compare side-by-side like Forma)

### 3. City Square Ventilation Diagrams (Architecture)
- For a square (e.g., MIT Campus 42.3601,-71.0942, Charles River), the square is `MAP = AOI + street_view 3D`. Wind corridors are `thermal_wind.ventilation_corridors` (cool tiles along inflow axis within ±45°) plus `wind_corridor.corridor_quality` (strong/moderate/weak, weak if h/w>1). Street-level `inflow` toward hot core is the ventilation axis; `thermal_corridor` tiles are where to place trees/walls.
- **Proposals in report:** `PDF §18` shows rose + proposal table (h/w, leaf, street wind, comfort) side-by-side, like Forma's compare. `UI Analytics` will show the same (next).
- **Grand Simulation:** `ui/grand-simulation.html` is the interactive Forma-like view — heat draped to roads/buildings (MapLibre fill + 3D buildings via CARTO vector), wind corridors as animated lines (continuous field), isotherms as contours, all divable (zoom/pitch/bearing). MIT 3D terrain already, Phoenix 2.5D, toggle.

### 4. Google Maps Street View 3D — How to Get It (Free vs Key)
- **Free (shipped):** Re:Earth terrain + Carto Positron + OSM Overpass bus stops + FortyGuard satellite/street-view segmentation (already cached `data/satellite/*`, `data/street_view/*`). No `GOOGLE_MAPS_API_KEY`, works offline (mock 81 tiles → we synthesize 16k for the dive).
- **Gated (if you add a key):** `GOOGLE_MAPS_API_KEY` in `.env` (gitignored) → `scripts/pull_google_terrain.py --live` for `Map Tiles API` Photorealistic 3D Tiles (Manhattan skyline) + `Elevation API` for true 3D mesh. Code checks `if not GOOGLE_MAPS_API_KEY: skip` and `if exists: skip` so judges never trigger billing.
- **Street View 3D geometry:** Google's `street_view_segmentation` is already wrapped by FortyGuard (`street_view_segmentation` 6 classes). For true 3D mesh, use `Map Tiles API` 3D Tiles + `street_view` depth? Not needed for hackathon — our satellite `building_pct` + `h_over_w` is the height proxy.

## Next Steps (if you want more Forma fidelity)

- Add `ui` wind corridor overlay: draw `wind_corridor.proposals` as 5 small maps side-by-side in Analytics (like Forma compare) — 5 canvases, same `continuous_field` but with varied `h_over_w`/`leaf_density`.
- Add `leaf_density` slider in the grand simulation HUD (25% → 10% dense) to see trees vs wall in real time (rapid AI).
- Keep detailed CFD as `caveat: rapid thermal proxy, not CFD (Forma detailed 30–90 min)` in `wind_corridor.caveat` and `report.py:18`.

## Files

- Video: `Resources/Youtube/vidssave.com Autodesk Forma Series - Episode 03 - Wind Analysis + Proposals 720P.mp4` (gitignored)
- Frames: `Resources/Youtube/frames/000001.png` … `000780.png` (gitignored)
- Transcript: `Resources/Youtube/Autodesk Forma Series - Episode 03 - Wind Analysis + Proposals.txt` (gitignored)
- Code: `calorai/analyst/wind_corridor.py`, `ui/grand-simulation.html`, `calorai/physics/thermal_wind.py: continuous_vector_field + isotherm_contours` (committed)

No video, frame, or transcript is committed — only this doc and the code that *learns* from them.
