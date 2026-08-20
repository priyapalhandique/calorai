"""Statistical layer over the tile field (D8).

Surface-temperature tiles are a *distribution*, and heat-policy
decisions hinge on how that distribution behaves: the spread of
micro-hotspots, the tail beyond action thresholds, and the radial
UHI cross-section. This module turns the tile field into the
classic diagnostics —

- summary statistics: mean / std / P05–P95 percentiles / IQR /
  min-max, skewness, kurtosis
- outliers: Tukey 1.5×IQR fences with counts and fence values
- normality: Shapiro–Wilk (scipy; deterministic stride-sampled when
  the field exceeds scipy's 5000-sample cap), with a skew/kurtosis
  heuristic fallback if scipy is unavailable
- radial UHI profile: tile temperature vs distance from the district
  centre, least-squares slope (°C/km) and R² — the canonical
  cross-sectional UHI signature (Oke et al. 2017)
- per-hour reconstruction: shape-preserving shift of the tile field
  by the apparent-temperature series, for hourly boxplots and the
  24 h UI slider

Deterministic by construction: no randomness, no API calls.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

try:  # scipy ships with the sklearn dependency; guarded for portability
    from scipy import stats as _scipy_stats

    _HAS_SCIPY = True
except Exception:  # pragma: no cover - scipy is a declared dependency
    _HAS_SCIPY = False

_SHAPIRO_MAX_N = 5000  # scipy hard cap
_KILOMETRES_PER_DEGREE = 111.32


# ------------------------------------------------------------------ helpers


def tile_values(tiles: list[dict[str, Any]]) -> np.ndarray:
    """Flat numpy array of tile temperatures (°C); empty if no tiles."""
    if not tiles:
        return np.asarray([], dtype=float)
    return np.asarray([t["value"] for t in tiles], dtype=float)


def _fences(values: np.ndarray) -> tuple[float, float]:
    """Tukey 1.5×IQR low/high fences."""
    q1, q3 = np.percentile(values, [25.0, 75.0])
    iqr = float(q3 - q1)
    return float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)


def _skewness(values: np.ndarray) -> float:
    """Sample skewness (adjusted Fisher–Pearson, scipy-compatible)."""
    n = len(values)
    if n < 3:
        return 0.0
    mu = float(values.mean())
    m2 = float(np.mean((values - mu) ** 2))
    m3 = float(np.mean((values - mu) ** 3))
    if m2 <= 0.0:
        return 0.0
    g1 = m3 / m2 ** 1.5
    return float(g1 * math.sqrt(n * (n - 1)) / (n - 2))


def _kurtosis(values: np.ndarray) -> float:
    """Sample excess kurtosis (adjusted Fisher–Pearson, scipy-compatible)."""
    n = len(values)
    if n < 4:
        return 0.0
    mu = float(values.mean())
    m2 = float(np.mean((values - mu) ** 2))
    m4 = float(np.mean((values - mu) ** 4))
    if m2 <= 0.0:
        return 0.0
    g2 = m4 / m2 ** 2 - 3.0
    return float(((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6.0))


# ------------------------------------------------------------------ data


def describe(values: np.ndarray) -> dict[str, float]:
    """Summary statistics of a tile field."""
    n = int(values.size)
    if n == 0:
        return {}
    p = np.percentile(values, [5.0, 25.0, 50.0, 75.0, 95.0])
    return {
        "n": n,
        "min_c": round(float(values.min()), 2),
        "p05_c": round(float(p[0]), 2),
        "p25_c": round(float(p[1]), 2),
        "median_c": round(float(p[2]), 2),
        "p75_c": round(float(p[3]), 2),
        "p95_c": round(float(p[4]), 2),
        "max_c": round(float(values.max()), 2),
        "mean_c": round(float(values.mean()), 2),
        "std_c": round(float(values.std()), 2),
        "iqr_c": round(float(p[3] - p[1]), 2),
        "skewness": round(_skewness(values), 3),
        "kurtosis": round(_kurtosis(values), 3),
    }


def outliers(values: np.ndarray, top_n: int = 10) -> dict[str, Any]:
    """Tukey 1.5×IQR outliers: count, fences and the most extreme values."""
    if values.size < 4:
        return {"count": 0, "pct": 0.0, "low_fence_c": None, "high_fence_c": None, "values_c": []}
    low, high = _fences(values)
    sel = values[(values < low) | (values > high)]
    count = int(sel.size)
    extremes = sorted(
        (float(v) for v in sel), key=lambda v: abs(v - float(np.median(values))), reverse=True
    )[:top_n]
    return {
        "count": count,
        "pct": round(100.0 * count / values.size, 1),
        "low_fence_c": round(low, 2),
        "high_fence_c": round(high, 2),
        "values_c": [round(v, 2) for v in extremes],
    }


def normality(values: np.ndarray) -> dict[str, Any]:
    """Shapiro–Wilk normality test with a deterministic sample cap."""
    n = int(values.size)
    if n < 3:
        return {"test": "insufficient samples", "normal": None, "advisory": "Fewer than 3 tiles."}
    if n > _SHAPIRO_MAX_N:
        stride = math.ceil(n / _SHAPIRO_MAX_N)
        sample = values[::stride][:_SHAPIRO_MAX_N]
        sampled = True
    else:
        sample, sampled = values, False
    if _HAS_SCIPY:
        if float(sample.std()) <= 1e-12:  # constant field: shapiro divides by zero
            return {
                "test": "shapiro-wilk",
                "statistic": 1.0,
                "p_value": 1.0,
                "normal": True,
                "sampled": sampled,
                "advisory": "Tile field is uniform (zero variance).",
            }
        stat, p = _scipy_stats.shapiro(sample)
        normal = bool(p > 0.05)
        return {
            "test": "shapiro-wilk",
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 4),
            "normal": normal,
            "sampled": sampled,
            "advisory": (
                "Tile distribution is consistent with a normal model"
                if normal
                else "Tile distribution deviates from normal (p ≤ 0.05) — "
                "expect skewed micro-hotspot tails."
            ),
        }
    skew, kurt = _skewness(sample), _kurtosis(sample)
    normal = abs(skew) <= 2.0 and abs(kurt) <= 7.0
    return {
        "test": "skew/kurtosis heuristic",
        "skewness": round(skew, 3),
        "kurtosis": round(kurt, 3),
        "normal": normal,
        "sampled": sampled,
        "advisory": (
            "consistent with normal" if normal else "deviates from normal"
        ),
    }


def _histogram(values: np.ndarray) -> dict[str, Any]:
    """Freedman–Diaconis histogram payload (bin edges + counts)."""
    n = int(values.size)
    if n == 0:
        return {"n": 0, "bin_edges_c": [], "counts": [], "bin_width_c": 0.0}
    iqr = float(np.percentile(values, 75) - np.percentile(values, 25))
    bin_w = 2.0 * iqr / max(1, int(n ** (1.0 / 3.0)))
    n_bins = max(8, int(math.ceil((float(values.max()) - float(values.min())) / max(bin_w, 1e-6))))
    edges = np.linspace(float(values.min()), float(values.max()), n_bins + 1)
    counts, _ = np.histogram(values, bins=edges)
    return {
        "n": n,
        "bin_edges_c": [round(float(e), 2) for e in edges],
        "counts": [int(c) for c in counts],
        "bin_width_c": round(float(edges[1] - edges[0]), 2),
    }


def _radial_profile(tiles: list[dict[str, Any]], n_bins: int = 12) -> dict[str, Any]:
    """Distance-binned mean temperature profile + OLS fit (°C/km, R²)."""
    if len(tiles) < 3:
        return {"present": False}
    lat0 = float(np.mean([t["lat"] for t in tiles]))
    lon0 = float(np.mean([t["lon"] for t in tiles]))
    dist = np.asarray(
        [
            math.hypot(t["lat"] - lat0, t["lon"] - lon0) * _KILOMETRES_PER_DEGREE
            for t in tiles
        ],
        dtype=float,
    )
    values = tile_values(tiles)
    slope, intercept = np.polyfit(dist, values, 1)
    pred = slope * dist + intercept
    ss_res = float(np.sum((values - pred) ** 2))
    ss_tot = float(np.sum((values - values.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0
    edges = np.linspace(float(dist.min()), float(dist.max()), n_bins + 1)
    centres, means = [], []
    for i in range(n_bins):
        mask = (dist >= edges[i]) & (dist < edges[i + 1])
        if not mask.any():
            continue
        centres.append(float((edges[i] + edges[i + 1]) / 2.0))
        means.append(float(values[mask].mean()))
    return {
        "present": True,
        "n_tiles": len(tiles),
        "dist_km": [round(c, 3) for c in centres],
        "mean_c": [round(m, 2) for m in means],
        "slope_c_per_km": round(float(slope), 3),
        "intercept_c": round(float(intercept), 2),
        "r2": round(float(r2), 3),
        "peak_distance_km": round(float(dist[np.argmax(values)]), 3),
        "advisory": (
            f"Tile temperature rises {slope:+.2f} °C per km from the centre "
            f"(R²={r2:.2f}) — the radial UHI cross-section."
        ),
    }


def hourly_reconstruction(
    tiles: list[dict[str, Any]],
    apparent_c: list[float | None] | None,
    audit_hour: int,
) -> list[dict[str, float] | None]:
    """Shape-preserving per-hour tile spread for boxplots and the slider.

    Each tile shifts by the hour's apparent-temperature delta from the
    audit hour:  tile_c(h) = tile_c(audit) + (apparent(h) - apparent(audit)).
    Spread (std, IQR) is preserved; hours with missing data yield None.
    """
    if not tiles or not apparent_c or len(apparent_c) != 24:
        return [None] * 24
    base = apparent_c[audit_hour]
    if base is None:
        return [None] * 24
    values = tile_values(tiles)
    out: list[dict[str, float] | None] = []
    for h in range(24):
        ref = apparent_c[h]
        if ref is None:
            out.append(None)
            continue
        shifted = values + (float(ref) - float(base))
        q = np.percentile(shifted, [0.0, 25.0, 50.0, 75.0, 100.0])
        out.append(
            {
                "hour": h,
                "min_c": round(float(q[0]), 2),
                "q1_c": round(float(q[1]), 2),
                "median_c": round(float(q[2]), 2),
                "q3_c": round(float(q[3]), 2),
                "max_c": round(float(q[4]), 2),
            }
        )
    return out


def tile_statistics_block(
    tiles: list[dict[str, Any]],
    apparent_c: list[float | None] | None = None,
    audit_hour: int = 14,
) -> dict[str, Any]:
    """The complete statistics block for the audit report."""
    if not tiles:
        return {"present": False}
    values = tile_values(tiles)
    summary = describe(values)
    out = outliers(values)
    norm = normality(values)
    hist = _histogram(values)
    prof = _radial_profile(tiles)
    uhi = {
        "slope_c_per_km": prof.get("slope_c_per_km", 0.0),
        "r2": prof.get("r2", 0.0),
    } if prof.get("present") else {"present": False}
    hourly = hourly_reconstruction(tiles, apparent_c, audit_hour)
    spread = summary["p95_c"] - summary["p05_c"]
    advisory = (
        f"Tile spread {spread:.1f} °C (P05–P95); {out['count']} outlier(s) beyond the "
        f"1.5×IQR fences; skewness {summary['skewness']:+.2f}; radial UHI "
        f"{uhi.get('slope_c_per_km', 0.0):+.2f} °C/km (R²={uhi.get('r2', 0.0):.2f})."
    )
    return {
        "present": True,
        "n_tiles": summary["n"],
        "summary": summary,
        "histogram": hist,
        "outliers": out,
        "normality": norm,
        "radial_uhi": uhi,
        "radial_profile": prof,
        "hourly_spread": hourly,
        "advisory": advisory,
    }


# ------------------------------------------------------------------ charts


def fig_histogram_normal(hist: dict[str, Any]) -> Any:
    """Histogram (Freedman–Diaconis bins) + fitted normal overlay."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    edges = hist.get("bin_edges_c", [])
    counts = hist.get("counts", [])
    n = hist.get("n", 0)
    if not edges or not counts or n == 0:
        ax.text(0.5, 0.5, "no tiles", ha="center", va="center")
        return fig
    edges = np.asarray(edges)
    counts = np.asarray(counts)
    bin_w = float(edges[1] - edges[0])
    centres = (edges[:-1] + edges[1:]) / 2.0
    ax.bar(centres, counts, width=bin_w * 0.95, color="#c2600a", alpha=0.75, edgecolor="white", label="tiles")
    xs = np.linspace(float(edges[0]), float(edges[-1]), 200)
    # mean/std recovered from the bin midpoint distribution (weighted)
    mu = float(np.average(centres, weights=counts))
    sd = float(np.sqrt(np.average((centres - mu) ** 2, weights=counts)))
    pdf = np.exp(-0.5 * ((xs - mu) / max(sd, 1e-9)) ** 2) / (max(sd, 1e-9) * math.sqrt(2 * math.pi))
    ax.plot(xs, pdf * n * bin_w, color="#16283f", lw=2, label="normal fit")
    ax.set_title("J · Tile temperature distribution (°C)", fontsize=9, color="#16283f")
    ax.set_xlabel("°C", fontsize=8)
    ax.tick_params(labelsize=7.5)
    ax.legend(fontsize=7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return fig


def fig_hourly_boxplot(hourly: list[dict[str, float] | None]) -> Any:
    """24 h boxplot of the reconstructed tile spread."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    hours, data = [], []
    for h in hourly:
        if h is None:
            continue
        hours.append(h["hour"])
        data.append([h["min_c"], h["q1_c"], h["median_c"], h["q3_c"], h["max_c"]])
    if not data:
        ax.text(0.5, 0.5, "no hourly data", ha="center", va="center")
        return fig
    ax.boxplot(
        data,
        positions=hours,
        widths=0.7,
        patch_artist=True,
        boxprops=dict(facecolor="#d9c9b3", edgecolor="#16283f"),
        medianprops=dict(color="#c2600a", lw=1.6),
        whiskerprops=dict(color="#16283f"),
        capprops=dict(color="#16283f"),
        flierprops=dict(marker="o", markersize=2.5, markerfacecolor="#7a8aa0"),
    )
    ax.set_title("K · Hourly tile spread (reconstructed, °C)", fontsize=9, color="#16283f")
    ax.set_xlabel("Hour (local)", fontsize=8)
    ax.set_ylabel("°C", fontsize=8)
    ax.set_xticks(hours)
    ax.set_xticklabels(hours, fontsize=7)
    ax.tick_params(labelsize=7.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return fig


def fig_radial_uhi(profile: dict[str, Any]) -> Any:
    """Radial UHI cross-section: binned mean temperature + OLS fit."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    if not profile.get("present") or not profile.get("dist_km"):
        ax.text(0.5, 0.5, "too few tiles", ha="center", va="center")
        return fig
    dist = np.asarray(profile["dist_km"])
    means = np.asarray(profile["mean_c"])
    ax.scatter(dist, means, s=16, color="#c2600a", alpha=0.75, edgecolor="none", label="binned mean")
    slope = float(profile.get("slope_c_per_km", 0.0))
    intercept = float(profile.get("intercept_c", 0.0))
    xs = np.linspace(float(dist.min()), float(dist.max()), 100)
    ax.plot(xs, slope * xs + intercept, color="#16283f", lw=1.8, label=f"fit {slope:+.2f} °C/km")
    ax.set_title("L · Radial UHI cross-section (°C vs km from centre)", fontsize=9, color="#16283f")
    ax.set_xlabel("distance from centre (km)", fontsize=8)
    ax.set_ylabel("°C", fontsize=8)
    ax.tick_params(labelsize=7.5)
    ax.legend(fontsize=7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return fig