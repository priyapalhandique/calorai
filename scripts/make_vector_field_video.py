"""Separate video: continuous thermal vector field + isotherm contours.

For the judge/user who doesn't see the vector field inside the 36-frame teaser.
Phoenix 2026-08-18 14:00 mock — 14×14 continuous field (320 vectors, 15 contours).

Outputs:
- docs/videos/vector_field.mp4 (if imageio) else docs/videos/vector_field.gif
- docs/images/vector_field_preview.png
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

out_mp4 = pathlib.Path("docs/videos/vector_field.mp4")
out_gif = pathlib.Path("docs/videos/vector_field.gif")
out_preview = pathlib.Path("docs/images/vector_field_preview.png")
out_mp4.parent.mkdir(parents=True, exist_ok=True)
out_gif.parent.mkdir(parents=True, exist_ok=True)

# Get Phoenix continuous field + contours (no live API, mock-safe)
try:
    from calorai.agent import AuditAgent, AuditRequest
    rep = AuditAgent(AuditRequest(district="phoenix", date="2026-08-18", hour=14, data_source="mock")).run(narrate=False)
    tw = rep.get("thermal_wind", {}) or {}
    cont = tw.get("contours", {}) or {}
    cfield = tw.get("continuous_field", {}) or {}
    # Heat grid for background
    from calorai.physics.thermal_wind import _TemperatureField
    from calorai.data_source import MockDataSource
    snap = MockDataSource().get_district_snapshot("phoenix", "2026-08-18", hour=14)
    tiles = snap.heatmap.tiles
    field = _TemperatureField(tiles)
    grid = field.field()
    lats, lons = field.lat_axis, field.lon_axis
    gmin, gmax = float(grid.min()), float(grid.max())
    vectors = cfield.get("vectors", []) or []
    contours = cont.get("contours", []) or []
    print(f"Phoenix vectors {len(vectors)} contours {len(contours)} range {gmin:.1f}-{gmax:.1f}°C")
except Exception as e:
    print(f"fetch failed {e}, using synthetic fallback")
    import math
    # synthetic fallback
    lons = np.linspace(-112.1, -112.0, 48)
    lats = np.linspace(33.4, 33.5, 48)
    grid = 35 + 5*np.exp(-((np.add.outer(lats, np.zeros(48))-33.45)**2 + (np.add.outer(np.zeros(48), lons)+112.05)**2)/0.0005)
    gmin, gmax = float(grid.min()), float(grid.max())
    vectors = []
    contours = []

import io
from PIL import Image

frames = []
n_frames = 20
for i in range(n_frames):
    fig, ax = plt.subplots(figsize=(6, 4), dpi=140)
    ax.set_xlim(lons.min(), lons.max())
    ax.set_ylim(lats.min(), lats.max())
    ax.set_aspect("equal")
    ax.axis("off")
    # Heat background
    ax.imshow(grid, cmap="coolwarm", vmin=gmin, vmax=gmax, origin="lower", extent=[lons.min(), lons.max(), lats.min(), lats.max()], alpha=0.38)
    # Isotherms: thin gray, labeled every 2K, animate dash offset
    for c in contours:
        seg = np.array(c["polyline"])  # [[lat, lon], ...]
        lats_c, lons_c = seg[:,0], seg[:,1]
        ax.plot(lons_c, lats_c, color="#9aa6b6", lw=0.7, alpha=0.82, linestyle=(0, (2+(i%3), 2)))
        if c["level_c"] % 2 == 0 and len(seg) > 10:
            mid = seg[len(seg)//2]
            ax.text(mid[1], mid[0], f"{c['level_c']:.0f}°", fontsize=5, color="#5a6a7a", ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
    # Vectors: pulse length
    pulse = 0.9 + 0.35*np.sin(i*0.8)
    step = max(1, len(vectors)//48)
    for v in vectors[::step]:
        x, y = v["lon"], v["lat"]
        scale = 0.0009 * (0.12 + min(v["mag_k_per_km"], 3.0)*0.04) * 111.32
        # inflow orange
        ax.annotate("", xy=(x + v["inflow_u"]*scale*pulse, y + v["inflow_v"]*scale*pulse), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color="#c2600a", lw=0.95, alpha=0.68))
        # thermal teal dashed
        ax.annotate("", xy=(x + v["thermal_u"]*scale*0.75*pulse, y + v["thermal_v"]*scale*0.75*pulse), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color="#4a7a5a", lw=0.8, ls="--", alpha=0.48))
    ax.plot((lons.min()+lons.max())/2, (lats.min()+lats.max())/2, "o", ms=7, color="#c2600a", zorder=3)
    ax.set_title(f"Continuous thermal vector field + isotherms (1 K)\n{len(contours)} contours · {len(vectors)} vectors · orange=inflow, teal=thermal wind", fontsize=8, color="#16283f")
    fig.suptitle(f"calorai — continuous field (separate video) • frame {i+1}/{n_frames}", fontsize=9, color="#16283f")
    plt.tight_layout(rect=[0,0,1,0.92])
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG")
    plt.close(fig)
    buf.seek(0)
    frames.append(Image.open(buf).convert("P", palette=Image.ADAPTIVE, colors=128))

# Save GIF + preview + MP4
frames[0].save(out_gif, save_all=True, append_images=frames[1:], duration=220, loop=0, optimize=True)
print(f"wrote {out_gif} {out_gif.stat().st_size} bytes frames={len(frames)}")
frames[0].save(out_preview)
print(f"wrote {out_preview}")
try:
    import imageio
    with imageio.get_writer(str(out_mp4), fps=5, macro_block_size=1) as w:
        for f in frames:
            w.append_data(np.array(f.convert("RGB")))
    print(f"wrote {out_mp4} {out_mp4.stat().st_size} bytes")
except Exception as e:
    print(f"mp4 skipped {e}")
    # fallback copy gif with mp4 name? keep gif
    print(f"keep {out_gif} as video fallback")
