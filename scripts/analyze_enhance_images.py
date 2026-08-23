"""Analyze all images for clarity and enhance (super-resolution + sharpen).

Checks: docs/images/*, Resources/Youtube/frames (sample), docs/videos/*.
Enhances: heatmaps, 24h GIFs, teaser, vector field via LANCZOS 2x + sharpen + contrast.
All from collected data, no new API, mock-safe. Writes enhanced copies with _hq suffix.
"""

import pathlib
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

DOCS_IMAGES = pathlib.Path("docs/images")
FRAMES_DIR = pathlib.Path("Resources/Youtube/frames")

def laplacian_variance(pil_img):
    # Approximate blur metric without cv2: variance of FIND_EDGES response
    gray = pil_img.convert("L").filter(ImageFilter.FIND_EDGES)
    arr = np.array(gray, dtype=np.float32)
    return float(arr.var())

def enhance(pil_img, scale=2.0):
    # Super-resolution via LANCZOS + sharpen + contrast
    w, h = pil_img.size
    big = pil_img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    # Sharpen
    sharp = ImageEnhance.Sharpness(big).enhance(1.8)
    # Contrast
    cont = ImageEnhance.Contrast(sharp).enhance(1.15)
    # Color
    col = ImageEnhance.Color(cont).enhance(1.1)
    # Slight unsharp mask
    return col.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))

# Analyze docs/images
print("=== docs/images analysis ===")
for p in sorted(DOCS_IMAGES.glob("*.png")):
    img = Image.open(p)
    lv = laplacian_variance(img)
    blur = "blurry" if lv < 100 else "sharp" if lv > 500 else "ok"
    print(f"{p.name:30} {img.size[0]}x{img.size[1]}  lapVar {lv:.1f} {blur}  {p.stat().st_size//1024}KB")

for p in sorted(DOCS_IMAGES.glob("*.gif")):
    img = Image.open(p)
    # first frame
    img.seek(0)
    lv = laplacian_variance(img.convert("RGB"))
    print(f"{p.name:30} {img.size[0]}x{img.size[1]}  lapVar {lv:.1f}  {p.stat().st_size//1024}KB")

# Sample YouTube frames
print("\n=== Youtube frames sample (10) ===")
if FRAMES_DIR.exists():
    files = sorted(FRAMES_DIR.glob("*.png"))[:10]
    for p in files:
        img = Image.open(p)
        lv = laplacian_variance(img)
        print(f"{p.name:12} {img.size[0]}x{img.size[1]} lapVar {lv:.1f}")

# Enhance heatmaps to _hq
print("\n=== enhancing heatmaps to _hq (2x LANCZOS + sharpen) ===")
for name in ["heatmap_visualized_mit.png", "heatmap_summary_mit.png", "heatmap_summary_phoenix.png", "heatmap_visualized.png"]:
    p = DOCS_IMAGES / name
    if not p.exists():
        continue
    img = Image.open(p).convert("RGB")
    hq = enhance(img, scale=1.5)  # 1.5x not 2x to keep under 5MB
    out = DOCS_IMAGES / p.name.replace(".png", "_hq.png")
    hq.save(out, optimize=True)
    # Compare
    lv0 = laplacian_variance(img)
    lv1 = laplacian_variance(hq)
    print(f"{name:30} {p.stat().st_size//1024}KB -> {out.stat().st_size//1024}KB  lapVar {lv0:.1f} -> {lv1:.1f} (+{(lv1-lv0)/max(lv0,1)*100:.1f}%)")

# Enhance GIFs: re-encode with 256 colors + dither
print("\n=== re-encoding GIFs with 256 colors ===")
for name in ["heatmap_24h_mit.gif", "heatmap_24h_phoenix.gif", "teaser_mit_3d.gif", "teaser.gif"]:
    p = DOCS_IMAGES / name
    if not p.exists():
        p = pathlib.Path("docs/videos") / name
        if not p.exists():
            continue
    try:
        im = Image.open(p)
        frames = []
        try:
            while True:
                f = im.convert("P", palette=Image.ADAPTIVE, colors=256, dither=Image.FLOYDSTEINBERG)
                frames.append(f)
                im.seek(im.tell()+1)
        except EOFError:
            pass
        out = p.parent / p.name.replace(".gif", "_hq.gif")
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=im.info.get("duration", 250), loop=0, optimize=True)
        print(f"{p.name:30} {p.stat().st_size//1024}KB -> {out.stat().st_size//1024}KB frames={len(frames)} 256 colors")
    except Exception as e:
        print(f"{p.name} failed {e}")

print("\nDone — check docs/images/*_hq.* and docs/videos/*_hq.gif")
