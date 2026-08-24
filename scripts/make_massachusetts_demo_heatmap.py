"""Massachusetts Demo heatmap — from user-provided 50MB GeoJSON (like San Jose AOI).

Generates docs/images/heatmap_massachusetts_demo.png in the same layout as
heatmap_visualized_mit.png / San Jose AOI: left legend 12 equal-interval classes,
right map with CARTO Positron basemap + heatmap tiles centered inside, title on top.
Uses the real demo heatmap data (data/massachusetts_heatmap.geojson) with temperature_f -> °C.
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import json

out_path = Path("docs/images/heatmap_massachusetts_demo.png")
out_path.parent.mkdir(parents=True, exist_ok=True)

# Load demo heatmap via our data_source helper (to ensure same conversion)
from calorai.data_source import _load_massachusetts_tiles
tiles = _load_massachusetts_tiles()
if not tiles:
    raise SystemExit("No demo tiles found at data/massachusetts_heatmap.geojson")

vals = np.array([t["value"] for t in tiles])
lats = np.array([t["lat"] for t in tiles])
lons = np.array([t["lon"] for t in tiles])
print(f"Massachusetts demo tiles {len(tiles)} min {vals.min():.2f} max {vals.max():.2f} mean {vals.mean():.2f}")

# Bounds from tiles
lon0, lon1 = lons.min(), lons.max()
lat0, lat1 = lats.min(), lats.max()
# Equal-interval 12 classes (like San Jose 0.17°C wide)
n_classes = 12
vmin, vmax = float(vals.min()), float(vals.max())
width = (vmax - vmin) / n_classes
print(f"Classes {n_classes} width {width:.3f} range {vmin:.2f}-{vmax:.2f}")

palette_hex = [
    "#c1272d", "#d44a2e", "#e76e2e", "#ef8a2d", "#f4a63a", "#f7c76a",
    "#e8e8a0", "#c8e0a0", "#a8d5a8", "#86c5a8", "#6aaebd", "#3d8abf",
]
# Class indices: hot = 0
class_indices = np.clip(((vals - vmin) / width).astype(int), 0, n_classes-1)
class_indices = (n_classes - 1) - class_indices

# Figure like San Jose / MIT: legend left 26%, map right 74%, bigger basemap with AOI inside
fig = plt.figure(figsize=(12, 6), dpi=180)
gs = fig.add_gridspec(1, 2, width_ratios=[0.26, 0.74], wspace=0.02)

# Left legend
ax_leg = fig.add_subplot(gs[0, 0])
ax_leg.set_xlim(0, 1)
ax_leg.set_ylim(0, 1)
ax_leg.axis("off")
ax_leg.add_patch(plt.Rectangle((0.02, 0.02), 0.96, 0.96, fill=False, edgecolor="#999999", lw=0.8))
# Title for legend: daily snapshot? The demo file is a snapshot (timestamp 2022-01-20T00:00:00, temp 44F)
ax_leg.text(0.05, 0.96, "Avg temperature (demo)", fontsize=9, fontweight="bold", va="top", ha="left", color="#222222")
ax_leg.text(0.05, 0.93, f"equal-interval · {n_classes} classes · {width:.2f} °C wide", fontsize=6.5, va="top", ha="left", color="#666666")
for i in range(n_classes):
    y = 0.86 - i * 0.065
    ax_leg.add_patch(plt.Rectangle((0.05, y), 0.12, 0.045, facecolor=palette_hex[i], edgecolor="#333333", lw=0.5))
    low = vmax - (i+1)*width
    high = vmax - i*width
    low = max(low, vmin)
    high = min(high, vmax)
    ax_leg.text(0.20, y+0.022, f"{low:5.2f} — {high:5.2f} °C", fontsize=6.5, va="center", ha="left", color="#222222", family="monospace")

# Right map — bigger basemap with AOI inside (like San Jose)
map_lon0, map_lon1 = lon0 - 0.03, lon1 + 0.03
map_lat0, map_lat1 = lat0 - 0.02, lat1 + 0.02
ax_map = fig.add_subplot(gs[0, 1])
ax_map.set_xlim(map_lon0, map_lon1)
ax_map.set_ylim(map_lat0, map_lat1)
ax_map.set_aspect("equal")
basemap_ok = False
try:
    import contextily as ctx
    ctx.add_basemap(ax_map, crs="EPSG:4326", source=ctx.providers.CartoDB.Positron, zoom=13, attribution=False)
    basemap_ok = True
    print("added CARTO Positron basemap")
except Exception as e:
    print(f"basemap failed {e}")
    ax_map.set_facecolor("#f6f6f4")

# Heatmap tiles
alpha = 0.45 if basemap_ok else 0.92
for i in range(n_classes):
    mask = class_indices == i
    if not np.any(mask):
        continue
    ax_map.scatter(lons[mask], lats[mask], c=[palette_hex[i]], s=3, marker="s", alpha=alpha, edgecolors="none", linewidths=0, zorder=2)

# AOI border
import matplotlib.patches as mpatches
ax_map.add_patch(mpatches.Rectangle((lon0, lat0), lon1-lon0, lat1-lat0, fill=False, edgecolor="#b0b0b0", lw=0.9, alpha=0.8, zorder=4))
# Locality labels (center of AOI)
import matplotlib.patheffects as pe
cx, cy = (lon0+lon1)/2, (lat0+lat1)/2
for txt, lon, lat, fs, col in [
    ("MASSACHUSETTS DEMO", cx, cy, 9, "#d32f2f"),
    ("CHARLES RIVER", -71.07, 42.355, 7, "#2980b9"),
]:
    ax_map.text(lon, lat, txt, fontsize=fs, color=col, ha="center", va="center", fontweight="bold", zorder=5,
                path_effects=[pe.withStroke(linewidth=2.5, foreground="white", alpha=0.9)])

fig.suptitle(f"Massachusetts Demo AOI · heatmap ({len(tiles):,} tiles)", fontsize=11, fontweight="bold", x=0.63, y=0.98, ha="center", color="#222222")
fig.text(0.63, 0.02, "(C) OpenStreetMap contributors (C) CARTO  —  Demo Heatmap - Massachusetts .geojson (50MB, temperature_f)", fontsize=6, ha="center", va="bottom", color="#666666")
ax_map.set_xticks([])
ax_map.set_yticks([])
for spine in ax_map.spines.values():
    spine.set_edgecolor("#cccccc")
    spine.set_linewidth(0.8)
    spine.set_visible(True)

plt.tight_layout(rect=[0, 0.02, 1, 0.96])
fig.savefig(out_path, dpi=220, facecolor="white")
plt.close(fig)
print(f"wrote {out_path} {out_path.stat().st_size} bytes")
