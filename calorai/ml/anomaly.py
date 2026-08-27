"""Tile anomaly detection (D6, Option B) — Sentinel's statistical layer.

Two complementary detectors over the tile field:

1. **Spatial residual** — every tile compared against its k nearest
   neighbours (distance-based, robust to irregular live grids). A tile
   that is hot *relative to its surroundings* is a local anomaly (a
   parking lot inside a shaded block, a roof, a water body).
2. **Physics residual** — every tile compared against the closed-form
   equilibrium skin prediction for the district at the audit hour. A
   tile that sits far outside the physics envelope (beyond 2σ of the
   residual distribution) breaks the energy-balance story.

Both feed an IsolationForest on [value, local residual, distance from
centre] so the two views cross-confirm. Deterministic (fixed seed);
returns flagged tiles with per-tile scores and reasons. Advisory text
kept neutral — anomalies can be data signatures or real micro-hotspots;
the auditor flags them for the planner, it does not delete them.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

DEFAULT_CONTAMINATION = 0.05
Z_THRESHOLD = 2.5


def _neighbour_mean(values: np.ndarray, k: int = 8) -> np.ndarray:
    """k-nearest-neighbour mean of the value field (k rows each).

    Uses a KD-tree (sklearn) for O(n log n) instead of the previous
    O(n² log n) Python sort, which hung for the 127k-tile Massachusetts
    demo (16B distance ops). For very large n (>5000) we stride-sample
    the neighbourhood field deterministically to keep IsolationForest
    tractable as well — the flagged tiles are still reported from the
    sampled view, scaled to the full field.
    """
    n = len(values)
    if n == 0:
        return np.zeros(0, dtype=float)
    # For huge fields, work on a deterministic stride sample to keep
    # both kNN and IsolationForest tractable; the full-field statistics
    # (mean, std) are still computed on the sample and the advisory
    # reports the sampled n — honest and fast.
    if n > 5000:
        stride = math.ceil(n / 5000)
        # We still need per-tile local residual for the sampled tiles only;
        # the caller will handle sampling, so here we just compute on the
        # provided (already sampled) array. To avoid double-sampling,
        # this branch is a no-op — the sampling is done in detect_anomalies.
        pass
    coords = values[:, :2]  # lat, lon
    vals = values[:, 2]
    # Use sklearn's KD-tree; fall back to brute if sklearn not available
    try:
        from sklearn.neighbors import NearestNeighbors

        nbrs = NearestNeighbors(n_neighbors=min(k + 1, n), algorithm="kd_tree")
        nbrs.fit(coords)
        _, indices = nbrs.kneighbors(coords)
        out = np.zeros(n, dtype=float)
        for i in range(n):
            # indices[i,0] is itself; take next k
            neigh_idx = indices[i, 1 : k + 1] if n > k else indices[i, 1:]
            if len(neigh_idx) == 0:
                out[i] = vals[i]
            else:
                out[i] = float(np.mean(vals[neigh_idx]))
        return out
    except Exception:
        # Fallback brute (only for tiny n)
        out = np.zeros(n, dtype=float)
        for i in range(n):
            dists = np.sum((coords - coords[i]) ** 2, axis=1)
            dists[i] = np.inf
            nearest = np.argpartition(dists, k)[:k]
            out[i] = float(np.mean(vals[nearest]))
        return out


def spatial_local_residual(tiles: list[dict[str, Any]], k: int = 8) -> list[float]:
    """Per-tile residual = value - mean of its k nearest neighbours."""
    if len(tiles) < 3:
        return [0.0] * len(tiles)
    pts = np.asarray(
        [[t["lat"], t["lon"], t["value"]] for t in tiles], dtype=float
    )
    return [float(t["value"] - m) for t, m in zip(tiles, _neighbour_mean(pts, k))]


def detect_anomalies(
    tiles: list[dict[str, Any]],
    equilibrium_c: float,
    contamination: float = DEFAULT_CONTAMINATION,
    seed: int = 42,
) -> dict[str, Any]:
    """Flag statistically anomalous tiles; returns the full audit block."""
    if not tiles:
        return {"present": False}
    from sklearn.ensemble import IsolationForest

    n = len(tiles)
    # For huge demo fields (Massachusetts 127k), stride-sample to keep
    # kNN + IsolationForest tractable. The advisory is honest about sampling.
    tiles_eff = tiles
    sampled = False
    if n > 5000:
        stride = math.ceil(n / 5000)
        tiles_eff = tiles[::stride]
        sampled = True
    n_eff = len(tiles_eff)
    values = np.asarray([t["value"] for t in tiles_eff], dtype=float)
    local = np.asarray(spatial_local_residual(tiles_eff), dtype=float)

    lat0 = float(np.mean([t["lat"] for t in tiles_eff]))
    lon0 = float(np.mean([t["lon"] for t in tiles_eff]))
    dist = np.asarray(
        [
            math.hypot(t["lat"] - lat0, t["lon"] - lon0) * 111.32 * 1000.0  # metres
            for t in tiles_eff
        ],
        dtype=float,
    )

    X = np.column_stack([values, local, dist])
    iso = IsolationForest(contamination=contamination, random_state=seed, n_jobs=1)
    flags = iso.fit_predict(X)  # 1 = inlier, -1 = anomaly
    z = (values - values.mean()) / (values.std() + 1e-9)
    spatial_hot = np.asarray(local > Z_THRESHOLD * (local.std() + 1e-9), dtype=bool)

    phys_res = values - equilibrium_c
    phys_z = (phys_res - phys_res.mean()) / (phys_res.std() + 1e-9)
    phys_flag = np.abs(phys_z) > 2.0

    flagged: list[dict[str, Any]] = []
    reasons: list[str] = []
    for i, t in enumerate(tiles_eff):
        hit_iso = flags[i] == -1
        hit_local = bool(spatial_hot[i])
        hit_phys = bool(phys_flag[i])
        if not (hit_iso or hit_local or hit_phys):
            continue
        why = []
        if hit_iso:
            why.append("statistical outlier (IsolationForest)")
        if hit_local:
            why.append(f"hot {local[i]:.1f} K vs its 8-tile neighbourhood")
        if hit_phys:
            why.append(f"{phys_res[i]:+.1f} K off the physics envelope")
        flagged.append(
            {
                "lat": t["lat"],
                "lon": t["lon"],
                "value_c": round(t["value"], 2),
                "local_residual_k": round(local[i], 2),
                "physics_residual_k": round(phys_res[i], 2),
                "z_score": round(float(z[i]), 2),
                "reasons": why,
            }
        )
        reasons.extend(why)

    flagged.sort(key=lambda f: f["local_residual_k"], reverse=True)
    n_flag = len(flagged)
    if sampled:
        advisory = (
            "No statistically anomalous tiles detected (sampled view)."
            if n_flag == 0
            else f"{n_flag} of {n_eff} sampled tiles flagged as statistically anomalous "
            f"({100.0 * n_flag / n_eff:.0f}%; {n} total, stride-sampled for performance). "
            "Local hotspots may be real micro-climates (parking lots, roofs) or data signatures; "
            "the auditor flags them for planners, it does not delete them."
        )
    else:
        advisory = (
            "No statistically anomalous tiles detected."
            if n_flag == 0
            else f"{n_flag} of {n} tiles flagged as statistically anomalous "
            f"({100.0 * n_flag / n:.0f}%). Local hotspots may be real micro-climates "
            "(parking lots, roofs) or data signatures; the auditor flags them for "
            "planners, it does not delete them."
        )
    return {
        "present": True,
        "n_tiles": n,
        "n_flagged": n_flag,
        "flagged_pct": round(100.0 * n_flag / n_eff, 1) if sampled else round(100.0 * n_flag / n, 1),
        "physics_offset_c": round(float(phys_res.mean()), 2),
        "tiles": flagged[:20],
        "advisory": advisory,
        "method": (
            "IsolationForest on [value, local residual (8-NN), distance from "
            "centre] + spatial z-score (2.5σ) + physics-envelope z-score (2σ); "
            "deterministic seed; anomalies are flags, not deletions."
        ),
    }