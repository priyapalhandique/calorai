"""Street-level landcover evidence — satellite + street-view segmentation.

Uses committed parcel responses (data/satellite/*, data/street_view/*).
No live API needed. District-mapped: san-jose shows Diridon evidence;
other districts report present=False with explanation (honest demo).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SAT_DIR = Path("data/satellite")
SV_DIR = Path("data/street_view")

# district -> (satellite_file, streetview_file)
_PARCEL_MAP: dict[str, tuple[str, str]] = {
    "san-jose": (
        "satellite_parcel_diridon_san_jose_2024-07-15.json",
        "streetview_parcel_diridon_san_jose.json",
    ),
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def landcover_block(district: str) -> dict[str, Any]:
    """Build landcover evidence block for a district.

    Returns present=False when no parcel evidence is committed for this
    district (honest: not every district has ground-truth imagery).
    """
    key = district.strip().lower().replace(" ", "-")
    if key not in _PARCEL_MAP:
        return {
            "present": False,
            "district": district,
            "reason": "no committed parcel imagery for this district; demo uses San Jose Diridon parcel as flagship example",
            "available_parcels": sorted(_PARCEL_MAP.keys()),
        }
    sat_file, sv_file = _PARCEL_MAP[key]
    sat = _load_json(SAT_DIR / sat_file)
    sv_raw = _load_json(SV_DIR / sv_file)
    sv = (sv_raw or {}).get("front", sv_raw) if sv_raw else None
    if sat is None or sv is None:
        return {"present": False, "district": district, "reason": "parcel files missing on disk"}

    sat_seg: dict[str, float] = (sat.get("segmentation", {}) or {}).get("segments", {}) or {}
    sv_seg: dict[str, float] = (sv.get("segments", {}) or {}) if isinstance(sv, dict) else {}

    # sky-view factor is the street-level sky fraction
    svf = float(sv_seg.get("sky", 0.0))
    shade_pct = float(sv_seg.get("tree", 0.0) + sv_seg.get("building", 0.0))
    green_pct = float(sat_seg.get("tree", 0.0) + sat_seg.get("plant", 0.0))
    impervious_pct = float(sat_seg.get("building", 0.0) + sat_seg.get("earth, ground", 0.0))

    return {
        "present": True,
        "district": district,
        "parcel": "Diridon, San Jose (flagship)",
        "satellite": {
            "file": sat_file,
            "segments": {k: round(float(v), 2) for k, v in sat_seg.items()},
            "green_pct": round(green_pct, 2),
            "impervious_pct": round(impervious_pct, 2),
        },
        "streetview": {
            "file": sv_file,
            "segments": {k: round(float(v), 2) for k, v in sv_seg.items()},
            "sky_view_factor_pct": round(svf, 2),
            "shade_pct": round(shade_pct, 2),
            "image_date": sv.get("image_date") if isinstance(sv, dict) else None,
        },
        "svf_sky_pct": round(svf, 2),
        "shade_pct": round(shade_pct, 2),
        "green_pct": round(green_pct, 2),
        "impervious_pct": round(impervious_pct, 2),
        "note": "sky% is a ground-truth sky-view factor; tree% is shade proxy",
    }
