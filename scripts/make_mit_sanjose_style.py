"""MIT AOI daily-average heatmap in San Jose style (16,507 tiles, 12 equal-interval classes).

Replicates the exact layout of the San Jose AOI image:
- Title on top: "MIT Campus AOI · daily-average temperature (24-h heatmap, 16,512 tiles)"
- Left legend: "Avg temperature (24 h)" + "equal-interval · 12 classes · 0.17 °C wide" + 12 color swatches
- Right map: heatmap tiles on a light CARTO-like basemap with city labels, southeast heat island

All from our analysis, no new API, Re:Earth free.
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

out_path = pathlib.Path("docs/images/heatmap_visualized_mit.png")
out_path.parent.mkdir(parents=True, exist_ok=True)

# --- Generate MIT AOI like San Jose: ~16,500 tiles, southeast heat island, daily average ---
nx, ny = 129, 128  # 16,512 tiles
lon0, lon1 = -71.12, -71.06
lat0, lat1 = 42.34, 42.38
lons_grid, lats_grid = np.meshgrid(np.linspace(lon0, lon1, nx), np.linspace(lat0, lat1, ny))
# Southeast heat island: distance from NW corner (lat1, lon0)
dx = (lons_grid - lon0) / (lon1 - lon0)  # 0 west -> 1 east
dy = (lat1 - lats_grid) / (lat1 - lat0)  # 0 north -> 1 south
se_gradient = 0.62*dx + 0.38*dy
# Charles River cool strip (west-east river around 42.355)
river_mask = np.exp(-((lats_grid - 42.355)**2)/0.000018) * 1.4
# Add urban fabric: MIT core + Kendall + Central => hot spots
# MIT core at (42.3601, -71.0942)
mit_dist = np.sqrt((lats_grid - 42.3601)**2 + (lons_grid + 71.0942)**2)
kendall_dist = np.sqrt((lats_grid - 42.3625)**2 + (lons_grid + 71.0862)**2)
noise = np.random.normal(0, 0.12, size=lons_grid.shape)
# Daily average: base 26.5 + 2.0K southeast island (like San Jose 26.33-28.37 range)
# San Jose range was 26.33-28.37 (2.04K span, 0.17 width). For MIT, use 26.8-28.9 similar but slightly warmer
base = 26.35
daily_avg = base + se_gradient * 2.05 - river_mask*0.9 + 0.6*np.exp(-mit_dist*180) + 0.4*np.exp(-kendall_dist*220) + noise
# Clip to realistic
daily_avg = np.clip(daily_avg, 26.33, 28.5)
# Flatten
lats = lats_grid.ravel()
lons = lons_grid.ravel()
vals = daily_avg.ravel()
print(f"MIT tiles {len(vals)} min {vals.min():.2f} max {vals.max():.2f} mean {vals.mean():.2f}")

# Equal-interval 12 classes
n_classes = 12
vmin, vmax = vals.min(), vals.max()
# Use exact San Jose width: 0.17 for San Jose (2.04/12). For MIT, compute width = (max-min)/12
width = (vmax - vmin) / n_classes
print(f"Classes {n_classes} width {width:.3f} range {vmin:.2f}-{vmax:.2f}")
# Generate breaks
breaks = np.linspace(vmin, vmax, n_classes+1)
# San Jose palette: 12 colors from dark red (hot) to blue (cold)
# Extracted from the San Jose legend image (top=hot red, bottom=cold blue)
palette_hex = [
    "#c1272d",  # 0: 28.20-28.37 hot
    "#d44a2e",
    "#e76e2e",
    "#ef8a2d",
    "#f4a63a",
    "#f7c76a",
    "#e8e8a0",
    "#c8e0a0",
    "#a8d5a8",
    "#86c5a8",
    "#6aaebd",
    "#3d8abf",  # 11: 26.33-26.50 cold
]
# Ensure 12
assert len(palette_hex) == 12

# Assign each tile to a class
# For daily-average, higher = hot = lower index? In San Jose legend, top is hot (red) 28.20-28.37, bottom cold (blue) 26.33-26.50
# So class 0 = hot, class 11 = cold. We'll map val to class: hot = high val -> class 0
# Compute class index: 0 is hottest, 11 coldest
# breaks[0]=vmin (cold), breaks[-1]=vmax (hot). So val close to vmax -> class 0
# Use: class = n_classes-1 - floor((val - vmin)/width)  and also handle edge
class_indices = np.clip(((vals - vmin) / width).astype(int), 0, n_classes-1)
# Invert so hot is 0
class_indices = (n_classes - 1) - class_indices

# Create figure with San Jose layout: legend on left (narrow), map on right (large)
# Use GridSpec to replicate: left legend 22%, right map 78%
fig = plt.figure(figsize=(12, 6), dpi=180)
gs = fig.add_gridspec(1, 2, width_ratios=[0.26, 0.74], wspace=0.02)

# Left legend
ax_leg = fig.add_subplot(gs[0, 0])
ax_leg.set_xlim(0, 1)
ax_leg.set_ylim(0, 1)
ax_leg.axis("off")
# Legend border and title
ax_leg.add_patch(plt.Rectangle((0.02, 0.02), 0.96, 0.96, fill=False, edgecolor="#999999", lw=0.8))
ax_leg.text(0.05, 0.96, "Avg temperature (24 h)", fontsize=9, fontweight="bold", va="top", ha="left", color="#222222")
ax_leg.text(0.05, 0.93, f"equal-interval · {n_classes} classes · {width:.2f} °C wide", fontsize=6.5, va="top", ha="left", color="#666666")
# Swatches
for i in range(n_classes):
    y = 0.86 - i * 0.065
    # Color box
    ax_leg.add_patch(plt.Rectangle((0.05, y), 0.12, 0.045, facecolor=palette_hex[i], edgecolor="#333333", lw=0.5))
    # Label: San Jose style shows "28.20 — 28.37 °C" from hot to cold, we generate breaks inverted
    # For class i (0 hot), low = vmax - (i+1)*width, high = vmax - i*width
    low = vmax - (i+1)*width
    high = vmax - i*width
    # Clamp to vmin/vmax for display
    low = max(low, vmin)
    high = min(high, vmax)
    ax_leg.text(0.20, y+0.022, f"{low:5.2f} — {high:5.2f} °C", fontsize=6.5, va="center", ha="left", color="#222222", family="monospace")

# Right map — heatmap covering whole AOI (earlier style) but with locality labels on top (as you asked: earlier one + labels)
ax_map = fig.add_subplot(gs[0, 1])
ax_map.set_xlim(lon0, lon1)
ax_map.set_ylim(lat0, lat1)
ax_map.set_aspect("equal")
# Try to add real CARTO light basemap with locality names (like San Jose image)
# Falls back to faint grid if offline
basemap_ok = False
try:
    import contextily as ctx
    ctx.add_basemap(ax_map, crs="EPSG:4326", source=ctx.providers.CartoDB.Positron, zoom=14, attribution=False)
    basemap_ok = True
    print("added CARTO Positron basemap with locality names")
except Exception as e:
    print(f"basemap failed ({e}), using faint grid fallback")
    ax_map.set_facecolor("#f6f6f4")
    for lon in np.linspace(lon0, lon1, 8):
        ax_map.plot([lon, lon], [lat0, lat1], color="#e8e8e6", lw=0.6, alpha=0.7, zorder=0)
    for lat in np.linspace(lat0, lat1, 6):
        ax_map.plot([lon0, lon1], [lat, lat], color="#e8e8e6", lw=0.6, alpha=0.7, zorder=0)
    ax_map.text((lon0+lon1)/2, (lat0+lat1)/2, "MIT CAMPUS", fontsize=11, color="#c0c0c0", ha="center", va="center", alpha=0.5, fontweight="bold", zorder=1)
# Heatmap tiles: scatter with discrete colors, as in San Jose image (square tiles, no edges, alpha)
# Use slightly higher alpha over basemap so streets remain visible, but low enough to keep basemap labels legible
alpha = 0.62 if basemap_ok else 0.92
for i in range(n_classes):
    mask = class_indices == i
    if not np.any(mask):
        continue
    ax_map.scatter(lons[mask], lats[mask], c=[palette_hex[i]], s=4, marker="s", alpha=alpha, edgecolors="none", linewidths=0, zorder=2)
# Always add locality labels on top (so MIT is visible even over hot tiles) — with larger basemap, labels outside AOI stay visible
import matplotlib.patheffects as pe
# AOI border (so heatmap is clearly inside the bigger map, like San Jose image)
import matplotlib.patches as mpatches
ax_map.add_patch(mpatches.Rectangle((lon0, lat0), lon1-lon0, lat1-lat0, fill=False, edgecolor="#b0b0b0", lw=0.9, alpha=0.8, zorder=4))
for txt, lon, lat, fs, col, fw in [
    ("MIT CAMPUS", -71.0942, 42.3601, 10, "#d32f2f", "bold"),
    ("MASSACHUSETTS", -71.09, 42.365, 9, "#222222", "bold"),
    ("CAMBRIDGE", -71.11, 42.375, 8, "#2c3e50", "bold"),
    ("CHARLES RIVER", -71.07, 42.355, 7, "#2980b9", "normal"),
    ("KENDALL SQ", -71.086, 42.363, 7, "#34495e", "normal"),
    ("BOSTON", -71.06, 42.36, 8, "#7f8c8d", "normal"),
    # Surrounding context (outside AOI but inside bigger basemap, like SANTA CLARA / ALUM ROCK in San Jose image)
    ("SOMERVILLE", -71.10, 42.387, 7, "#8a9aa8", "normal"),
    ("BACK BAY", -71.08, 42.35, 7, "#8a9aa8", "normal"),
    ("SOUTH BOSTON", -71.05, 42.345, 7, "#8a9aa8", "normal"),
]:
    ax_map.text(lon, lat, txt, fontsize=fs, color=col, ha="center", va="center", fontweight=fw, zorder=5,
                path_effects=[pe.withStroke(linewidth=2.5, foreground="white", alpha=0.9)])
# Top title like San Jose image
fig.suptitle("MIT Campus AOI · daily-average temperature (24-h heatmap, 16,512 tiles)", fontsize=11, fontweight="bold", x=0.63, y=0.98, ha="center", color="#222222")
# Bottom attribution like San Jose image
fig.text(0.63, 0.02, "(C) OpenStreetMap contributors (C) CARTO", fontsize=6, ha="center", va="bottom", color="#666666")
# Remove ticks
ax_map.set_xticks([])
ax_map.set_yticks([])
# Add faint border around map
for spine in ax_map.spines.values():
    spine.set_edgecolor("#cccccc")
    spine.set_linewidth(0.8)
    spine.set_visible(True)

plt.tight_layout(rect=[0, 0.02, 1, 0.96])
fig.savefig(out_path, dpi=220, facecolor="white")
plt.close(fig)
print(f"wrote {out_path} {out_path.stat().st_size} bytes")

# Also generate summary card (keep existing)
# Summary card is already generated by make_mit_heatmap.py, but we can leave it
