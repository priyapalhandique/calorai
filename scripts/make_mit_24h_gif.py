"""MIT 24h tiles changing over time — like Phoenix 24h GIF but for MIT.

Each hour, tile temperature = base + southeast island * island_strength(hour) + river + diurnal sinusoid.
Island breathes with sun (strongest 14:00), river cool strip constant.
Outputs docs/images/heatmap_24h_mit.gif (24 frames, tile-by-tile, fixed scale).
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

out = pathlib.Path("docs/images/heatmap_24h_mit.gif")
out.parent.mkdir(parents=True, exist_ok=True)

# MIT AOI grid 129x128 = 16,512 tiles (same as accurate heatmap)
nx, ny = 129, 128
lon0, lon1 = -71.12, -71.06
lat0, lat1 = 42.34, 42.38
lons_grid, lats_grid = np.meshgrid(np.linspace(lon0, lon1, nx), np.linspace(lat0, lat1, ny))
dx = (lons_grid - lon0) / (lon1 - lon0)
dy = (lat1 - lats_grid) / (lat1 - lat0)
se_gradient = 0.62*dx + 0.38*dy
river_mask = np.exp(-((lats_grid - 42.355)**2)/0.000018) * 1.4
mit_dist = np.sqrt((lats_grid - 42.3601)**2 + (lons_grid + 71.0942)**2)
kendall_dist = np.sqrt((lats_grid - 42.3625)**2 + (lons_grid + 71.0862)**2)

# Fixed scale for honest diurnal pulse (like Phoenix GIF 28.6-40.6)
# For MIT daily, range ~26.5-29.5 at night to 28-31 at peak
vmin, vmax = 26.0, 30.5

import io
from PIL import Image

frames = []
for hour in range(24):
    # Diurnal sinusoid: peak 14:00, trough 04:00, amplitude 2.2K
    hour_angle = (hour - 14) * 15  # degrees from solar noon
    diurnal = 2.2 * np.cos(np.radians(hour_angle * 0.9))  # 0.9 for broader peak
    # Island strength breathes: 0.7 at night -> 1.3 at peak
    island_strength = 0.75 + 0.55 * np.cos(np.radians((hour - 14)*15))
    island_strength = max(0.5, island_strength)
    vals = 26.35 + se_gradient * 2.05 * island_strength + diurnal - river_mask*0.9 + 0.6*np.exp(-mit_dist*180) + 0.4*np.exp(-kendall_dist*220) + np.random.normal(0, 0.12, size=lons_grid.shape)
    # Clip
    vals = np.clip(vals, vmin, vmax)

    fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=140)
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect("equal")
    # Try CARTO basemap, fallback to faint grid (full AOI, earlier style)
    basemap_ok = False
    try:
        import contextily as ctx
        ctx.add_basemap(ax, crs="EPSG:4326", source=ctx.providers.CartoDB.Positron, zoom=14, attribution=False)
        basemap_ok = True
    except Exception:
        ax.set_facecolor("#f6f6f4")
        for lon in np.linspace(lon0, lon1, 6):
            ax.plot([lon, lon], [lat0, lat1], color="#e8e8e6", lw=0.5, alpha=0.6, zorder=0)
        for lat in np.linspace(lat0, lat1, 5):
            ax.plot([lon0, lon1], [lat, lat], color="#e8e8e6", lw=0.5, alpha=0.6, zorder=0)
    # Locality labels (always on top, like San Jose image)
    import matplotlib.patheffects as pe
    for txt, lon, lat, fs, col in [
        ("MIT CAMPUS", -71.0942, 42.3601, 7, "#d32f2f"),
        ("CAMBRIDGE", -71.11, 42.375, 6, "#2c3e50"),
    ]:
        ax.text(lon, lat, txt, fontsize=fs, color=col, ha="center", va="center", fontweight="bold", zorder=5,
                path_effects=[pe.withStroke(linewidth=1.8, foreground="white", alpha=0.9)])
    # Heat tiles as pcolormesh for speed (discrete but continuous)
    # Use lower alpha over basemap so streets locality names stay legible (user saw only Cambridge)
    sc = ax.scatter(lons_grid.ravel(), lats_grid.ravel(), c=vals.ravel(), cmap="coolwarm", vmin=vmin, vmax=vmax, s=3, marker="s", alpha=0.62 if basemap_ok else 0.92, edgecolors="none", zorder=2)
    # Always add locality labels on top (so MIT is visible even over hot tiles)
    import matplotlib.patheffects as pe
    for txt, lon, lat, fs, col, fw in [
        ("MIT CAMPUS", -71.0942, 42.3601, 8, "#d32f2f", "bold"),
        ("MASSACHUSETTS", -71.09, 42.365, 7, "#222222", "bold"),
        ("CAMBRIDGE", -71.11, 42.375, 6, "#2c3e50", "bold"),
        ("CHARLES RIVER", -71.07, 42.355, 6, "#2980b9", "normal"),
        ("KENDALL SQ", -71.086, 42.363, 6, "#34495e", "normal"),
    ]:
        ax.text(lon, lat, txt, fontsize=fs, color=col, ha="center", va="center", fontweight=fw, zorder=5,
                path_effects=[pe.withStroke(linewidth=2.2, foreground="white", alpha=0.9)])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    # Title with hour and island strength
    ax.set_title(f"MIT Campus  {hour:02d}:00  —  {vals.mean():.1f}°C mean  island ×{island_strength:.2f}", fontsize=8, color="#16283f", pad=4)
    # Colorbar hint
    cbar = plt.colorbar(sc, ax=ax, shrink=0.72, pad=0.02)
    cbar.set_label("°C", fontsize=7)
    # Time label
    fig.suptitle(f"MIT 24h tiles changing over time — frame {hour+1}/24", fontsize=9, color="#16283f")
    plt.tight_layout(rect=[0,0.02,1,0.96])
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG")
    plt.close(fig)
    buf.seek(0)
    frames.append(Image.open(buf).convert("P", palette=Image.ADAPTIVE, colors=128))

frames[0].save(out, save_all=True, append_images=frames[1:], duration=280, loop=0, optimize=True)
print(f"wrote {out} {out.stat().st_size} bytes frames={len(frames)} vmin {vmin} vmax {vmax}")
