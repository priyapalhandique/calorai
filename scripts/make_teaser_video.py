"""Teaser video: 3D terrain around MIT + thermal wind animation + all capabilities montage.

Uses collected data: MIT mock audit (thermal wind, terrain, heat), Phoenix 24h GIF already exists,
and stitches into a teaser GIF for README + a longer MP4 outline.

Outputs:
- docs/images/teaser_mit_3d.gif (3D terrain MIT, hillshade, heat drape)
- docs/videos/teaser.mp4 (if ffmpeg available) else docs/videos/teaser.gif fallback
- docs/images/teaser_preview.png (first frame)

All from our analysis, no Google key, Re:Earth terrain URLs cited.
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

out_gif = pathlib.Path("docs/images/teaser_mit_3d.gif")
out_preview = pathlib.Path("docs/images/teaser_preview.png")
out_video_dir = pathlib.Path("docs/videos")
out_video_dir.mkdir(parents=True, exist_ok=True)
out_mp4 = out_video_dir / "teaser.mp4"
out_gif2 = out_video_dir / "teaser.gif"

# Get MIT live-collected (mock) data for realism
try:
    from calorai.agent import AuditAgent, AuditRequest
    rep = AuditAgent(AuditRequest(district="mit-campus", date="2026-08-18", hour=14, data_source="mock")).run(narrate=False)
    tw = rep.get("thermal_wind", {}) or {}
    heat_max = rep.get("snapshot", {}).get("max_c", 33.0)
    heat_mean = rep.get("snapshot", {}).get("mean_c", 31.0)
    terrain = rep.get("terrain", {}) or {}
    slope = terrain.get("slope_deg", 9.6)
    hillshade = terrain.get("hillshade", 0.62)
    print(f"MIT thermal wind: gradient {tw.get('gradient_k_per_km')} K/km inflow {tw.get('inflow_direction_deg')}°")
except Exception as e:
    print(f"audit fetch failed {e}, using fallback")
    tw = {"gradient_k_per_km": 1.2, "inflow_direction_deg": 315, "inflow_direction": "northwest"}
    heat_max, heat_mean = 33.5, 31.2
    slope, hillshade = 9.6, 0.62

# Build synthetic terrain around MIT (400m grid, 30x30)
nx, ny = 30, 30
x = np.linspace(-0.01, 0.01, nx)  # lon offset
y = np.linspace(-0.01, 0.01, ny)  # lat offset
X, Y = np.meshgrid(x, y)
# Elevation: base 4m + slope * radial distance + Charles River dip
R = np.sqrt(X**2 + Y**2)
el = 4.0 + slope * 10 * np.exp(-R*80) + np.sin(X*300)*0.8 + np.cos(Y*300)*0.5 - 2.0*np.exp(-((X+0.005)**2 + (Y+0.003)**2)/0.00002)  # river dip
# Heat drape: hot core at (0,0) = campus center
heat = heat_mean + (heat_max - heat_mean) * np.exp(-R*120) + np.random.normal(0, 0.15, size=R.shape)

# Thermal wind vectors: inflow toward hot core (center) + geostrophic offset
# Use gradient direction: k x grad(T) => aloft wind parallel to isotherms, inflow toward core
inflow_deg = tw.get("inflow_direction_deg") or 315
inflow_rad = np.radians(inflow_deg)
# Sample vector field every 6 cells
skip = 6
Xq, Yq = X[::skip, ::skip], Y[::skip, ::skip]
# Inflow toward center: vector = -position normalized * speed scale
U = -Xq / np.maximum(R[::skip, ::skip], 1e-6) * 0.4 + np.cos(inflow_rad)*0.15
V = -Yq / np.maximum(R[::skip, ::skip], 1e-6) * 0.4 + np.sin(inflow_rad)*0.15

# Render frames rotating azimuth for teaser
import io
from PIL import Image

frames = []
n_frames = 24
for i in range(n_frames):
    fig = plt.figure(figsize=(6, 3.5), dpi=140)
    # 3D terrain left
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    az = 30 + i * 15  # rotate
    ax1.view_init(elev=28, azim=az)
    surf = ax1.plot_surface(X*1000, Y*1000, el, facecolors=plt.cm.coolwarm((heat - heat_mean)/(heat_max - heat_mean + 1e-6)), shade=True, rstride=1, cstride=1, alpha=0.95)
    ax1.set_title(f"MIT Campus 3D terrain\nheat drape {heat_mean:.1f}–{heat_max:.1f}°C", fontsize=8)
    ax1.set_xlabel("lon offset (m)", fontsize=7)
    ax1.set_ylabel("lat offset (m)", fontsize=7)
    ax1.set_zlabel("elev (m)", fontsize=7)
    ax1.tick_params(labelsize=6)
    # Thermal wind 2D right
    ax2 = fig.add_subplot(1, 2, 2)
    im = ax2.imshow(heat, cmap="coolwarm", vmin=heat_mean, vmax=heat_max, origin="lower", extent=[-500,500,-500,500])
    # animate wind wobble
    wobble = 0.15 * np.sin(i * 0.6)
    ax2.quiver(Xq*1000, Yq*1000, U*(1+wobble), V*(1+wobble), color="#16283f", scale=6, width=0.006, alpha=0.9)
    ax2.set_title(f"Thermal wind (Wallace & Hobbs 7.20)\n{tw.get('gradient_k_per_km', 1.2):.1f} K/km → {tw.get('inflow_direction','northwest')}", fontsize=8)
    ax2.set_xlabel("m"); ax2.set_ylabel("m")
    fig.suptitle(f"calorai teaser — 3D terrain MIT + thermal wind + all capabilities  •  frame {i+1}/{n_frames}", fontsize=9, color="#16283f")
    plt.tight_layout(rect=[0,0,1,0.92])
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG")
    plt.close(fig)
    buf.seek(0)
    frames.append(Image.open(buf).convert("P", palette=Image.ADAPTIVE, colors=128))

# --- NEW FRAME: continuous vector field + isotherm contours (Phoenix) ---
try:
    from calorai.agent import AuditAgent as _AA2, AuditRequest as _AR2
    rep2 = _AA2(_AR2(district="phoenix", date="2026-08-18", hour=14, data_source="mock")).run(narrate=False)
    tw2 = rep2.get("thermal_wind", {}) or {}
    cont = tw2.get("contours") or {}
    cfield = tw2.get("continuous_field") or {}
    # Heat grid for Phoenix for contour background
    from calorai.physics.thermal_wind import _TemperatureField
    tiles2 = rep2.get("_tiles_for_debug") or None
    # Fallback: get tiles from snapshot via agent internals (use mock source directly)
    if tiles2 is None:
        from calorai.data_source import MockDataSource
        snap2 = MockDataSource().get_district_snapshot("phoenix", "2026-08-18", hour=14)
        tiles2 = snap2.heatmap.tiles
    # Build field for background heat (re-use if we can)
    field2 = _TemperatureField(tiles2)
    grid2 = field2.field()
    gmin2, gmax2 = float(grid2.min()), float(grid2.max())
    lats2, lons2 = field2.lat_axis, field2.lon_axis
    vectors2 = cfield.get("vectors", []) or []
    contours2 = cont.get("contours", []) or []
    for j in range(12):
        fig2 = plt.figure(figsize=(6, 3.5), dpi=140)
        ax = fig2.add_subplot(1, 1, 1)
        ax.set_xlim(lons2.min(), lons2.max())
        ax.set_ylim(lats2.min(), lats2.max())
        ax.set_aspect("equal")
        ax.axis("off")
        # Heat background as faint imshow
        ax.imshow(grid2, cmap="coolwarm", vmin=gmin2, vmax=gmax2, origin="lower",
                  extent=[lons2.min(), lons2.max(), lats2.min(), lats2.max()], alpha=0.35)
        # Isotherms: thin gray, labeled every 2K, animate dash offset
        for c in contours2:
            seg = np.array(c["polyline"])  # [[lat, lon], ...]
            lats_c, lons_c = seg[:, 0], seg[:, 1]
            ax.plot(lons_c, lats_c, color="#9aa6b6", lw=0.7, alpha=0.85,
                    linestyle=(0, (3+j%3, 3)))
            if c["level_c"] % 2 == 0 and len(seg) > 10:
                mid = seg[len(seg)//2]
                ax.text(mid[1], mid[0], f"{c['level_c']:.0f}°", fontsize=5, color="#5a6a7a", ha="center", va="center",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
        # Continuous vectors: orange inflow + teal thermal, decimated, pulsing length
        step = max(1, len(vectors2)//42)
        pulse = 0.85 + 0.3 * np.sin(j * 0.9)
        for v in vectors2[::step]:
            x, y = v["lon"], v["lat"]
            scale = 0.0009 * (0.12 + min(v["mag_k_per_km"], 3.0) * 0.04) * 111.32  # deg scale
            # inflow orange
            ax.annotate("", xy=(x + v["inflow_u"]*scale*pulse, y + v["inflow_v"]*scale*pulse), xytext=(x, y),
                        arrowprops=dict(arrowstyle="-|>", color="#c2600a", lw=0.9, alpha=0.65))
            # thermal wind teal dashed
            ax.annotate("", xy=(x + v["thermal_u"]*scale*0.75*pulse, y + v["thermal_v"]*scale*0.75*pulse), xytext=(x, y),
                        arrowprops=dict(arrowstyle="-|>", color="#4a7a5a", lw=0.8, ls="--", alpha=0.45))
        ax.plot((lons2.min()+lons2.max())/2, (lats2.min()+lats2.max())/2, "o", ms=7, color="#c2600a", zorder=3)
        ax.set_title(f"Continuous field + isotherms (1 K) — {len(contours2)} contours · {len(vectors2)} vectors\norange=inflow, teal=thermal wind aloft (k×grad) — frame {j+1}/12", fontsize=8, color="#16283f")
        # Colorbar hint
        fig.suptitle("calorai teaser — continuous thermal vector field (new frame)", fontsize=9, color="#16283f")
        plt.tight_layout(rect=[0,0,1,0.92])
        buf2 = io.BytesIO()
        fig2.savefig(buf2, format="PNG")
        plt.close(fig2)
        buf2.seek(0)
        frames.append(Image.open(buf2).convert("P", palette=Image.ADAPTIVE, colors=128))
    print(f"added continuous field frames: 12, total frames now {len(frames)}")
except Exception as e:
    print(f"continuous field teaser frames skipped: {e}")

# Save GIF teaser (README)
out_gif.parent.mkdir(parents=True, exist_ok=True)
frames[0].save(out_gif, save_all=True, append_images=frames[1:], duration=250, loop=0, optimize=True)
print(f"wrote {out_gif} {out_gif.stat().st_size} bytes frames={len(frames)}")
# Preview first frame
frames[0].save(out_preview)
print(f"wrote {out_preview}")

# Try MP4 via imageio if available, else GIF copy
try:
    import imageio
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    # Convert PIL frames to numpy for imageio
    with imageio.get_writer(str(out_mp4), fps=4, macro_block_size=1) as writer:
        for f in frames:
            writer.append_data(np.array(f.convert("RGB")))
    print(f"wrote {out_mp4} {out_mp4.stat().st_size} bytes")
except Exception as e:
    print(f"mp4 skipped {e}, copying GIF to videos/teaser.gif")
    import shutil
    shutil.copy(out_gif, out_gif2)
    print(f"wrote {out_gif2}")
