"""Cut the turnaround views and props out of the concept sheet: fit a smooth background from the crop
border, derive alpha from colour distance (border-connected only), and un-mix the background from
semi-transparent pixels so translucent sleeves keep their colour.

Usage: python scripts/cutout_turnaround.py [sheet.png] [out_dir] [preview_prefix]
Defaults regenerate static/art/hero/ from assets/protagonist_xianxia_character_concept_turnaround_v001.png.png.
Needs numpy and Pillow (development only; the game server does not import this).
"""
import sys
from pathlib import Path
from collections import deque
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[1:] + [None] * 3
SRC = args[0] or str(ROOT / 'assets' / 'protagonist_xianxia_character_concept_turnaround_v001.png.png')
OUT = args[1] or str(ROOT / 'static' / 'art' / 'hero')
PREVIEW = args[2]
BOXES = {'front': (15, 88, 350, 712), 'side': (365, 88, 625, 712), 'back': (615, 88, 895, 712),
         'sword': (1100, 95, 1215, 488), 'circle': (1226, 96, 1420, 270), 'jade': (1205, 283, 1285, 448), 'talisman': (1300, 306, 1420, 482)}
T0 = {'front': 16, 'side': 16, 'back': 16}
sheet = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32)

def background(img):
    h, w, _ = img.shape
    k = 5
    left = np.median(img[:, :k], axis=1); right = np.median(img[:, -k:], axis=1)
    # smooth the border columns vertically so stray strokes do not leak in
    ker = np.ones(41) / 41
    left = np.stack([np.convolve(np.pad(left[:, c], 20, mode='edge'), ker, 'valid') for c in range(3)], 1)
    right = np.stack([np.convolve(np.pad(right[:, c], 20, mode='edge'), ker, 'valid') for c in range(3)], 1)
    u = np.linspace(0, 1, w)[None, :, None]
    return left[:, None, :] * (1 - u) + right[:, None, :] * u

def cut(name, box):
    x0, y0, x1, y1 = box
    img = sheet[y0:y1, x0:x1]
    bg = background(img)
    d = np.sqrt(((img - bg) ** 2).sum(-1))
    t0 = T0.get(name, 22); t1 = t0 + 42
    alpha = np.clip((d - t0) / (t1 - t0), 0, 1)
    # keep only background regions that touch the border (dark hair against dark sky stays opaque)
    h, w = d.shape
    isbg = d < t0 + 6
    seen = np.zeros_like(isbg)
    q = deque([(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)])
    while q:
        y, x = q.popleft()
        if seen[y, x] or not isbg[y, x]:
            continue
        seen[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and not seen[yy, xx]:
                q.append((yy, xx))
    alpha = np.where(seen, alpha, np.maximum(alpha, .9 * (d >= 6)))
    if name in ('front', 'side', 'back'):
        # floor shadow: in the bottom band keep only the dark boots
        lum = img.mean(-1)
        band = np.arange(h)[:, None] > h - 48
        alpha = np.where(band & (lum > 95), 0, alpha)
    # drop stray cloud blobs: keep connected components that are a sizeable part of the figure
    solid = alpha > .15
    label = np.zeros((h, w), np.int32); sizes = [0]
    for sy, sx in zip(*np.nonzero(solid)):
        if label[sy, sx]:
            continue
        n = len(sizes); label[sy, sx] = n; q = deque([(sy, sx)]); c = 0
        while q:
            y, x = q.popleft(); c += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and solid[yy, xx] and not label[yy, xx]:
                    label[yy, xx] = n; q.append((yy, xx))
        sizes.append(c)
    keep = np.array([s >= max(sizes) * .02 for s in sizes]); keep[0] = False
    grown = Image.fromarray((keep[label] * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    alpha = alpha * (np.asarray(grown) > 0)
    a = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))
    alpha = np.asarray(a).astype(np.float32) / 255
    safe = np.maximum(alpha, .08)[..., None]
    rgb = np.clip(bg + (img - bg) / safe, 0, 255)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    # trim to the opaque bounds with a small margin
    ys, xs = np.where(alpha > .04)
    m = 4
    out = out[max(0, ys.min() - m):ys.max() + m, max(0, xs.min() - m):xs.max() + m]
    Image.fromarray(out, 'RGBA').save(f'{OUT}/{name}.png', optimize=True)
    return Image.fromarray(out, 'RGBA')

cuts = {k: cut(k, b) for k, b in BOXES.items()}
H = max(c.height for c in cuts.values()); W = sum(c.width + 10 for c in cuts.values())
for tag, col in (('dark', (30, 34, 40)), ('sky', (80, 140, 210))) if PREVIEW else ():
    prev = Image.new('RGBA', (W, H), col + (255,)); x = 0
    for c in cuts.values():
        prev.alpha_composite(c, (x, 0)); x += c.width + 10
    prev.convert('RGB').save(f'{PREVIEW}-{tag}.png')
print({k: c.size for k, c in cuts.items()})
