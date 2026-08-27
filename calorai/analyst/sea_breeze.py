"""Land and sea breezes — coastal counterpart to Great Lake breeze.

Physics: day — land heats faster than sea → land warm low, sea cool high → sea breeze onshore
(≈0.5 m/s per K land-sea ΔT, Simpson 1994); night — reverse land breeze.
We detect the sea as the cold cluster in the tcm field for coastal districts,
like lake_effect does for Great Lakes, and report the onshore breeze proxy.

No new API, mock-safe, diagnostic (no observed wind), honest caveat.
"""

from __future__ import annotations

from typing import Any

# Coastal districts in our catalog (distance to ocean <60 km)
COASTAL_DISTRICTS = {"manhattan", "east-harlem", "san-jose", "austin"}  # san-jose ~50km to Pacific, austin ~250km to Gulf (weak)
OCEAN_BBOX = {
    "Atlantic": (36.0, -76.0, 45.0, -71.0),  # US East Coast
    "Pacific": (32.0, -124.0, 42.0, -117.0),  # US West Coast
}


def _in_ocean(lat: float, lon: float) -> str | None:
    for name, (lat0, lon0, lat1, lon1) in OCEAN_BBOX.items():
        if lat0 <= lat <= lat1 and lon0 <= lon <= lon1:
            return name
    return None


def sea_breeze_block(
    tiles: list[dict[str, Any]] | None,
    district_lat: float,
    district_lon: float,
    district_name: str,
) -> dict[str, Any]:
    # District is passed as either the catalog key (manhattan) or human name
    # (Lower Manhattan, NYC). Normalise to a key-like form and allow substring
    # matching so both forms correctly route to the coastal check.
    lower = district_name.strip().lower()
    key = lower.replace(" ", "-")
    is_coastal = key in COASTAL_DISTRICTS or any(c in key for c in COASTAL_DISTRICTS)
    if not is_coastal:
        return {"present": True, "sea_breeze": False, "reason": "inland district — no sea breeze (land-locked)"}
    if not tiles or len(tiles) < 20:
        return {"present": False, "reason": "no tiles"}
    vals = [float(t["value"]) for t in tiles]
    median = sorted(vals)[len(vals)//2]
    cold = [t for t in tiles if float(t["value"]) <= median - 0.8]
    if not cold or len(cold) / len(tiles) < 0.04 or len(cold) / len(tiles) > 0.40:
        return {"present": True, "sea_breeze": False, "reason": "no cold-cluster sea signature (likely inland tiles only)"}
    hot = [t for t in tiles if float(t["value"]) > median]
    if not hot:
        return {"present": True, "sea_breeze": False, "reason": "no hot cluster"}
    sea_mean = sum(float(t["value"]) for t in cold) / len(cold)
    land_mean = sum(float(t["value"]) for t in hot) / len(hot)
    delta = land_mean - sea_mean
    if delta < 1.2:
        return {"present": True, "sea_breeze": False, "land_sea_delta_K": round(delta, 2), "reason": "land-sea ΔT <1.2K — no sea breeze"}
    clat = sum(float(t["lat"]) for t in cold) / len(cold)
    clon = sum(float(t["lon"]) for t in cold) / len(cold)
    sea_name = _in_ocean(clat, clon) or _in_ocean(district_lat, district_lon) or ("Atlantic" if key in ("manhattan", "east-harlem") else "Pacific")
    # Sea breeze proxy: 0.5 m/s per K (Simpson 1994 sea breeze scaling, slightly stronger than lake 0.4)
    speed = round(delta * 0.5, 2)
    import math
    dlat = district_lat - clat
    dlon = district_lon - clon
    bearing = (math.degrees(math.atan2(dlon, dlat)) + 360) % 360
    # Diurnal: sea breeze day (onshore), land breeze night (offshore) — we report day (onshore) for 14:00 audit
    return {
        "present": True,
        "sea_breeze": True,
        "sea_name": sea_name,
        "land_sea_delta_K": round(delta, 2),
        "sea_cool_K": round(delta, 2),
        "sea_tile_share_pct": round(len(cold)/len(tiles)*100, 1),
        "breeze_proxy": {"speed_m_s": speed, "bearing_deg": round(bearing, 0), "from_sea": sea_name, "diurnal": "day onshore (land warm) / night offshore (land cool)"},
        "caveat": "Sea-breeze proxy (cold-cluster sea tiles, 0.5 m/s per K land-sea ΔT, Simpson 1994) — diagnostic, no observed wind, like lake_effect.",
    }
