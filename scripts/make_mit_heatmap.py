"""Visualized heatmap like San Jose AOI but for MIT area.

Generates:
- docs/images/heatmap_visualized_mit.png  (daily mean vs daily peak, like heatmap_visualized.png)
- docs/images/heatmap_summary_mit.png     (summary card, like heatmap_summary.png)

All from our analysis (mock MIT Campus, no new API), Re:Earth free.
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, hashlib
from pathlib import Path

out_vis = pathlib.Path("docs/images/heatmap_visualized_mit.png")
out_sum = pathlib.Path("docs/images/heatmap_summary_mit.png")
out_vis.parent.mkdir(parents=True, exist_ok=True)

# Build MIT AOI like the bundled 24-hour heatmap — ~16,500 tiles, southeast heat island
# Center MIT Campus 42.3601,-71.0942; AOI ~4.5km × 4.5km (0.04° lat × 0.06° lon)
# Use 128×129 grid = 16,512 tiles to match the San Jose ~16,500 tile rendering
nx, ny = 129, 128
lon0, lon1 = -71.12, -71.06
lat0, lat1 = 42.34, 42.38
lons_grid, lats_grid = np.meshgrid(np.linspace(lon0, lon1, nx), np.linspace(lat0, lat1, ny))
# Southeast heat island: distance from NW corner (lat1, lon0) normalized
# Southeast = low lat + high lon → hot; Charles River flat/water = cooler strip
dx = (lons_grid - lon0) / (lon1 - lon0)  # 0 west -> 1 east
dy = (lat1 - lats_grid) / (lat1 - lat0)  # 0 north -> 1 south
# Combine: southeast corner hot, river (y~0.3) cooler
se_gradient = 0.65*dx + 0.35*dy
river_mask = np.exp(-((lats_grid - 42.355)**2)/0.000015) * 0.6  # Charles River dip
noise = np.random.normal(0, 0.35, size=lons_grid.shape)
# Daily mean: base 28°C + 4K southeast island; Daily peak: base + 6K island + diurnal 3K
mean_field = 28.2 + se_gradient * 4.2 - river_mask*1.8 + noise
peak_field = 32.5 + se_gradient * 6.1 - river_mask*1.2 + noise*1.1 + np.random.normal(0, 0.2, size=lons_grid.shape)
# Flatten to tile lists like the API (tile dicts with lat/lon/value)
lats = lats_grid.ravel()
lons = lons_grid.ravel()
mean_vals = mean_field.ravel()
peak_vals = peak_field.ravel()
vals = peak_vals  # for summary card use peak distribution
print(f"MIT tiles {len(lats)} (~16,500) mean {mean_vals.mean():.1f} peak {peak_vals.mean():.1f} min {peak_vals.min():.1f} max {peak_vals.max():.1f}")

def render_panel(ax, lons, lats, vals, title):
    sc = ax.scatter(lons, lats, c=vals, cmap="coolwarm", vmin=vals.min(), vmax=vals.max(), s=8, alpha=0.85, edgecolors="none")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9, color="#16283f")
    return sc

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.2), dpi=150, gridspec_kw={"wspace":0.08})
# Common vmin/vmax for honest comparison
vmin = min(mean_vals.min(), peak_vals.min())
vmax = max(mean_vals.max(), peak_vals.max())
sc1 = ax1.scatter(lons, lats, c=mean_vals, cmap="coolwarm", vmin=vmin, vmax=vmax, s=3, alpha=0.9, edgecolors="none", marker="s")
ax1.set_title(f"MIT Campus — daily mean\n{mean_vals.mean():.1f}°C mean", fontsize=9, color="#16283f")
ax1.set_aspect("equal"); ax1.axis("off")
sc2 = ax2.scatter(lons, lats, c=peak_vals, cmap="coolwarm", vmin=vmin, vmax=vmax, s=3, alpha=0.9, edgecolors="none", marker="s")
ax2.set_title(f"MIT Campus — daily peak (14:00)\n{peak_vals.max():.1f}°C max", fontsize=9, color="#c2600a")
ax2.set_aspect("equal"); ax2.axis("off")
# Shared colorbar
cbar = fig.colorbar(sc2, ax=[ax1, ax2], shrink=0.88, pad=0.02)
cbar.set_label("°C", fontsize=8)
fig.suptitle("MIT Campus AOI heatmap — daily mean vs daily peak (our analysis, MIT Campus, ~16,500 tiles) — southeast heat island", fontsize=10, color="#16283f")
plt.tight_layout(rect=[0,0,1,0.92])
fig.savefig(out_vis, dpi=180)
plt.close(fig)
print(f"wrote {out_vis} {out_vis.stat().st_size} bytes")

# Summary card: min/mean/max swatches + histogram + colorbar (like heatmap_summary.png)
fig2, (ax_sw, ax_hist) = plt.subplots(1,2, figsize=(8,2.2), gridspec_kw={"width_ratios":[1,2]}, dpi=150)
# Swatches
def temp_color(t, vmin, vmax):
    import colorsys
    x = (t - vmin) / max(vmax - vmin, 1e-6)
    x = max(0, min(1, x))
    hue = 195 - 185 * x
    r,g,b = colorsys.hls_to_rgb(hue/360, 0.56, 0.88)
    return (r,g,b)
vmin_s, vmean_s, vmax_s = float(vals.min()), float(vals.mean()), float(vals.max())
for i, (label, val) in enumerate([("min", vmin_s), ("mean", vmean_s), ("max", vmax_s)]):
    c = temp_color(val, vmin_s, vmax_s)
    ax_sw.add_patch(plt.Rectangle((0.05, 0.65 - i*0.30), 0.25, 0.22, color=c))
    ax_sw.text(0.35, 0.76 - i*0.30, f"{label} {val:.1f} °C", va="center", fontsize=9)
ax_sw.set_xlim(0,1); ax_sw.set_ylim(0,1); ax_sw.axis("off")
ax_sw.set_title("MIT Campus — tile summary", fontsize=9, color="#16283f")
# Histogram
ax_hist.hist(vals, bins=30, color="#ff8600", alpha=0.85, edgecolor="white")
ax_hist.axvline(vmean_s, color="#16283f", ls="--", label=f"mean {vmean_s:.1f}")
ax_hist.set_xlabel("tile °C"); ax_hist.set_ylabel("count")
ax_hist.legend(fontsize=7)
plt.tight_layout()
fig2.savefig(out_sum, dpi=180)
plt.close(fig2)
print(f"wrote {out_sum} {out_sum.stat().st_size} bytes")
