# GeoJSON/CSV Export Package

calorai ships an open export package that a planning, GIS, or analytics team
can load into downstream tools without a proprietary connector.

## Endpoint

```text
GET /api/export?district=phoenix&date=2026-08-18&hour=14&source=mock
```

The response is a ZIP file containing:

| File | Purpose |
|---|---|
| `<slug>_tiles.geojson` | Point FeatureCollection of tile centroids with temperature and threshold flags. |
| `<slug>_audit.csv` | One flat row of headline audit numbers for spreadsheet/model intake. |
| `<slug>_interventions.csv` | Ranked intervention table with cooling, flux removed, scope, and basis. |

## CLI

```bash
python -m calorai audit phoenix --date 2026-08-18 --hour 14 --mock --export-out outputs/interop
```

This writes the same three files without starting the web app.

## Data Contract

### GeoJSON

The GeoJSON is WGS84 point data:

```json
{
  "type": "FeatureCollection",
  "name": "calorai-heat-2026-08-18",
  "meta": {
    "district": "Phoenix, AZ",
    "date": "2026-08-18",
    "source": "mock",
    "layer": "tcm",
    "units": "celsius",
    "threshold_c": 30.0
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [-112.074, 33.4484]},
      "properties": {
        "temp_c": 39.7,
        "above_threshold_c": true,
        "is_hottest_tile": true
      }
    }
  ]
}
```

### Audit CSV

The flat audit row includes district/date/hour/source, heatmap min/mean/max,
hottest tile coordinates, attribution shares, equilibrium surface temperature,
WBGT, exceedance hours, vulnerability band, ROI, facade ranking, equity,
productivity, economy, and thermal-wind proxy fields.

### Interventions CSV

Each row has:

```text
rank,name,delta_t_c,removed_flux_w_m2,scope,basis
```

## Intended Workflow

1. Export the ZIP from the live or mock app.
2. Load the GeoJSON in a GIS, dashboard, or planning tool.
3. Join the audit/intervention CSVs in a spreadsheet or BI layer.
4. Use the hottest-tile and above-threshold flags to guide where a planner
   tests shade, cool-roof, pavement, or shift-schedule scenarios.

## Boundary

This is an open-file handoff, not a live integration with an external planning
platform. A production connector would need authentication, project/site IDs,
schema mapping, and round-trip editing semantics. Those are deliberately outside
the hackathon scope.
