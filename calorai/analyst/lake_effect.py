"""Great Lake evaporative cooling — lake-detected breeze + latent lever.

Detects water tiles as the cold cluster in the tcm field (k-means-like
2-cluster on value), checks centroid against Great Lakes bounding boxes,
then reports lake cool ΔT, breeze proxy (0.4 m/s per K), evaporative boost.

No new API, mock-safe, diagnostic only — does not mutate the audit balance.
"""

from __future__ import annotations

from typing import Any

# Great Lakes bounding boxes (approx, for heuristic lake detection)
GREAT_LAKES_BBOX = {
    "Michigan": (41.5, -88.0, 46.0, -84.5),
    "Erie": (41.3, -83.5, 43.0, -78.5),
    "Superior": (46.0, -92.5, 49.0, -84.0),
    "Huron": (43.0, -84.5, 46.0, -80.5),
    "Ontario": (43.2, -79.8, 44.5, -76.0),
}


def _in_any_lake(lat: float, lon: float) -> str | None:
    for name, (lat0, lon0, lat1, lon1) in GREAT_LAKES_BBOX.items():
        if lat0 <= lat <= lat1 and lon0 <= lon <= lon1:
            return name
    return None


def lake_effect_block(
    tiles: list[dict[str, Any]] | None,
    district_lat: float,
    district_lon: float,
    district_name: str,
) -> dict[str, Any]:
    if not tiles or len(tiles) < 20:
        return {"present": False, "reason": "no tiles"}
    vals = [float(t["value"]) for t in tiles]
    # 2-cluster by median split (cheap k-means proxy)
    median = sorted(vals)[len(vals)//2]
    cold = [t for t in tiles if float(t["value"]) <= median - 0.8]
    # lake share heuristic: cold cluster 5–40% and cooler by ≥1.5K from hot cluster
    if not cold or len(cold) / len(tiles) < 0.05 or len(cold) / len(tiles) > 0.45:
        return {"present": True, "lake_detected": False, "lake_name": None, "reason": "no cold-cluster lake signature (land-locked or no lake tiles)"}
    hot = [t for t in tiles if float(t["value"]) > median]
    if not hot:
        return {"present": True, "lake_detected": False, "reason": "no hot cluster"}
    lake_mean = sum(float(t["value"]) for t in cold) / len(cold)
    land_mean = sum(float(t["value"]) for t in hot) / len(hot)
    delta = land_mean - lake_mean
    if delta < 1.5:
        return {"present": True, "lake_detected": False, "lake_cool_K": round(delta, 2), "reason": "cold cluster not cool enough for lake (<1.5K)"}
    # centroid of cold cluster
    clat = sum(float(t["lat"]) for t in cold) / len(cold)
    clon = sum(float(t["lon"]) for t in cold) / len(cold)
    lake_name = _in_any_lake(clat, clon) or _in_any_lake(district_lat, district_lon)
    # Also allow Chicago/Milwaukee/Detroit/Cleveland/Buffalo by name heuristic even without cold cluster centroid in lake bbox (district is near lake)
    near_lake_districts = {"chicago", "milwaukee", "detroit", "cleveland", "buffalo", "mit-campus"}
    # mitigate: mit-campus not Great Lakes (Atlantic) — treat as no lake
    if district_name.lower().replace(" ", "-") in {"chicago", "milwaukee", "detroit", "cleveland", "buffalo"}:
        lake_name = lake_name or ("Michigan" if district_name.lower() in ("chicago", "milwaukee") else "Erie")
    else:
        # inland: require cold cluster centroid in lake bbox
        if lake_name is None:
            return {"present": True, "lake_detected": False, "lake_cool_K": round(delta, 2), "lake_tile_share_pct": round(len(cold)/len(tiles)*100,1)}

    # breeze proxy 0.4 m/s per K
    breeze_speed = round(delta * 0.4, 2)
    # bearing lake -> district center
    import math
    dlat = district_lat - clat
    dlon = district_lon - clon
    bearing = (math.degrees(math.atan2(dlon, dlat)) + 360) % 360
    # evaporative boost: lake share *0.15 capped 0.30 → extra latent lever K (via Priestley-Taylor proxy: 0.15*share≈extra Q, ~0.6K per 0.1 share)
    lake_share = len(cold) / len(tiles)
    boost = min(0.30, lake_share * 0.15)
    # cooling lever K ≈ boost * 6K (heuristic: 0.15 share → ~0.9K)
    lever_k = round(boost * 6.0, 2)
    return {
        "present": True,
        "lake_detected": True,
        "lake_name": lake_name,
        "lake_cool_K": round(delta, 2),
        "lake_tile_share_pct": round(lake_share*100, 1),
        "breeze_proxy": {"speed_m_s": breeze_speed, "bearing_deg": round(bearing, 0), "from_lake": lake_name},
        "evaporative_boost": round(boost, 3),
        "cooling_lever_K": lever_k,
        "caveat": "Lake-detected proxy (cold-cluster tiles); breeze 0.4 m/s per K ΔT, no observed wind — diagnostic only.",
    }
