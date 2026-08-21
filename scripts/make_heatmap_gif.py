"""Generate 24h animated heatmap GIF + summary card from our Phoenix 2024-07-15 24× cached tcm."""
import hashlib, json, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

def cache_key(endpoint, **args):
    raw = json.dumps({"endpoint": endpoint, **args}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

cache = pathlib.Path("data/cache")
out_gif = pathlib.Path("docs/images/heatmap_24h_phoenix.gif")
out_card = pathlib.Path("docs/images/heatmap_summary_phoenix.png")
out_gif.parent.mkdir(parents=True, exist_ok=True)

# Collect 24h phoenix tiles
frames = []
for h in range(24):
    k = cache_key("heatmap", district="phoenix", date="2024-07-15", hour=h, analytic_type="tcm", threshold=None, granularity=100)
    p = cache / f"{k}.json"
    if not p.exists():
        print(f"missing hour {h}")
        continue
    j = json.loads(p.read_text())
    frames.append((h, j))

print(f"frames {len(frames)}")
# Render GIF
from PIL import Image
import io

# Prepare colormap cyan -> amber -> red
def temp_color(t, vmin, vmax):
    x = (t - vmin) / max(vmax - vmin, 1e-6)
    x = max(0, min(1, x))
    # hue 195 -> 10
    hue = 195 - 185 * x
    # convert hsl to rgb via colorsys
    import colorsys
    r, g, b = colorsys.hls_to_rgb(hue/360, 0.56, 0.88)
    return (int(r*255), int(g*255), int(b*255))

pil_frames = []
# compute global min/max for consistent scale
all_vals = [v for _,j in frames for v in [t["value"] for t in j["tiles"]]]
gmin, gmax = min(all_vals), max(all_vals)
print(f"global min {gmin:.1f} max {gmax:.1f}")

for h, j in frames:
    tiles = j["tiles"]
    # Use matplotlib to render scatter
    fig, ax = plt.subplots(figsize=(4,4), dpi=120)
    lats = [t["lat"] for t in tiles]
    lons = [t["lon"] for t in tiles]
    vals = [t["value"] for t in tiles]
    sc = ax.scatter(lons, lats, c=vals, cmap="coolwarm", vmin=gmin, vmax=gmax, s=6)
    ax.set_title(f"Phoenix 2024-07-15 {h:02d}:00 — {j['mean']:.1f}°C mean ({j['n_cells']} tiles)", fontsize=9)
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.set_aspect("equal", adjustable="datalim")
    plt.colorbar(sc, ax=ax, label="°C", shrink=0.85)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG")
    plt.close(fig)
    buf.seek(0)
    pil_frames.append(Image.open(buf).convert("P", palette=Image.ADAPTIVE, colors=128))

# Save animated GIF
if pil_frames:
    pil_frames[0].save(out_gif, save_all=True, append_images=pil_frames[1:], duration=600, loop=0, optimize=True)
    print(f"wrote {out_gif} {out_gif.stat().st_size} bytes")

# Summary card for hour 14 (flagship)
h14 = next((j for h,j in frames if h==14), frames[len(frames)//2][1] if frames else None)
if h14:
    tiles = h14["tiles"]
    vals = np.array([t["value"] for t in tiles])
    vmin, vmean, vmax = float(np.min(vals)), float(np.mean(vals)), float(np.max(vals))
    fig, (ax_sw, ax_hist) = plt.subplots(1,2, figsize=(8,2.2), gridspec_kw={"width_ratios":[1,2]}, dpi=150)
    # swatches
    for i, (label, val, color) in enumerate([("min", vmin, temp_color(vmin,gmin,gmax)), ("mean", vmean, temp_color(vmean,gmin,gmax)), ("max", vmax, temp_color(vmax,gmin,gmax))]):
        ax_sw.add_patch(plt.Rectangle((0.05, 0.65 - i*0.30), 0.25, 0.22, color=np.array(color)/255))
        ax_sw.text(0.35, 0.76 - i*0.30, f"{label} {val:.1f} °C", va="center", fontsize=9)
    ax_sw.set_xlim(0,1); ax_sw.set_ylim(0,1); ax_sw.axis("off")
    ax_sw.set_title("Phoenix 2024-07-15 14:00 — tile summary", fontsize=9)
    # histogram
    ax_hist.hist(vals, bins=30, color="#ff8600", alpha=0.85, edgecolor="white")
    ax_hist.axvline(vmean, color="#16283f", ls="--", label=f"mean {vmean:.1f}")
    ax_hist.set_xlabel("tile °C"); ax_hist.set_ylabel("count")
    ax_hist.legend(fontsize=7)
    plt.tight_layout()
    fig.savefig(out_card, dpi=180)
    plt.close(fig)
    print(f"wrote {out_card} {out_card.stat().st_size} bytes")
