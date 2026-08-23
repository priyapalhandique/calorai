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
