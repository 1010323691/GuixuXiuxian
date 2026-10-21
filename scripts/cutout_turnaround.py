"""Cut the turnaround views and props out of the concept sheets: fit a smooth background from the crop
border, derive alpha from colour distance (border-connected only), and un-mix the background from
semi-transparent pixels so translucent sleeves and crystal wings keep their colour.

Usage: python scripts/cutout_turnaround.py [hero|lion|all] [preview_prefix]
Each SHEETS entry names its source under assets/ (see assets/NAMING.md), its output folder under static/art/
and crop boxes in sheet pixels. Boxes listed in 'glow' become additive light (background subtracted, opaque
black = no light). Needs numpy and Pillow (development only; the game server does not import this).
"""
import sys
from pathlib import Path
from collections import deque
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SHEETS = {
    'hero': {'src': 'char_protagonist_turnaround_v001.png', 'out': 'hero', 'views': ('front', 'side', 'back'),
             'boxes': {'front': (15, 88, 350, 712), 'side': (365, 88, 625, 712), 'back': (615, 88, 895, 712),
                       'sword': (1100, 95, 1215, 488), 'circle': (1226, 96, 1420, 270), 'jade': (1205, 283, 1285, 448), 'talisman': (1300, 306, 1420, 482)}},
    # 紫晶翼狮王: three views plus the crystal sigil (灵气凝聚); 'erase' paints the neighbouring view out of a box
    'lion': {'src': 'mon_amethyst_winged_lion_king_sheet_v001.png', 'out': 'lion', 'views': ('front', 'side', 'back'),
             'boxes': {'front': (0, 121, 348, 574), 'side': (336, 90, 862, 574), 'back': (796, 132, 1038, 574), 'sigil': (1388, 492, 1505, 586)},
             'erase': {'side': [(814, 160, 862, 574)], 'back': [(796, 250, 808, 292), (796, 430, 816, 574)]},
             'glow': ('sigil',), 'fit': 'poly', 'pockets': True, 't0': 24},
}
T0 = {'front': 16, 'side': 16, 'back': 16}
args = sys.argv[1:] + [None] * 2
WHICH = [k for k in SHEETS if args[0] in (None, 'all', k)]
PREVIEW = args[1]


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


def background_poly(img, rounds=4):
    """Misty, vertically graded backgrounds: fit a cubic surface to pixels judged background, refit as
    the figure is excluded. Starts from the crop border, which is mostly background."""
    h, w, _ = img.shape
    yy, xx = np.mgrid[0:h, 0:w]
    u, v = xx / w - .5, yy / h - .5
    basis = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v, u ** 3, u * u * v, u * v * v, v ** 3], -1).reshape(-1, 10)
    mask = np.zeros((h, w), bool); mask[:6] = mask[-6:] = True; mask[:, :6] = mask[:, -6:] = True
    flat = img.reshape(-1, 3)
    for _ in range(rounds):
        idx = np.flatnonzero(mask.ravel())[::7]
        coef, *_ = np.linalg.lstsq(basis[idx], flat[idx], rcond=None)
        bg = (basis @ coef).reshape(h, w, 3)
        d = np.sqrt(((img - bg) ** 2).sum(-1))
        sat = img.max(-1) - img.min(-1)
        mask = (d < 20) & (sat < 80)
    return bg


def cut(sheet, spec, name, box):
    x0, y0, x1, y1 = box
    img = sheet[y0:y1, x0:x1].copy()
    bg = background_poly(img) if spec.get('fit') == 'poly' and name in spec['views'] else background(img)
    for ex0, ey0, ex1, ey1 in spec.get('erase', {}).get(name, ()):
        sl = (slice(max(0, ey0 - y0), max(0, ey1 - y0)), slice(max(0, ex0 - x0), max(0, ex1 - x0)))
        img[sl] = bg[sl]
    if name in spec.get('glow', ()):
        light = np.clip((img - bg * .85) * 1.6, 0, 255)
        out = np.dstack([light, np.full(light.shape[:2], 255.)]).astype(np.uint8)
        return out
    d = np.sqrt(((img - bg) ** 2).sum(-1))
    t0 = spec.get('t0', T0.get(name, 22)) if name in spec['views'] else T0.get(name, 22); t1 = t0 + 42
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
    if not spec.get('pockets'):  # enclosed low-contrast pockets stay opaque unless the sheet allows pockets
        alpha = np.where(seen, alpha, np.maximum(alpha, .9 * (d >= 6)))
    if name in spec['views']:
        # floor shadow: in the bottom band keep only the dark feet
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
    return out[max(0, ys.min() - m):ys.max() + m, max(0, xs.min() - m):xs.max() + m]


cuts = {}
for key in WHICH:
    spec = SHEETS[key]
    folder = ROOT / 'static' / 'art' / spec['out']
    folder.mkdir(parents=True, exist_ok=True)
    sheet = np.asarray(Image.open(ROOT / 'assets' / spec['src']).convert('RGB')).astype(np.float32)
    for name, box in spec['boxes'].items():
        image = Image.fromarray(cut(sheet, spec, name, box), 'RGBA')
        image.save(folder / ('%s.png' % name), optimize=True)
        cuts['%s/%s' % (key, name)] = image

if PREVIEW:
    H = max(c.height for c in cuts.values()); W = sum(c.width + 10 for c in cuts.values())
    for tag, col in (('dark', (30, 34, 40)), ('sky', (80, 140, 210))):
        prev = Image.new('RGBA', (W, H), col + (255,)); x = 0
        for c in cuts.values():
            prev.alpha_composite(c, (x, 0)); x += c.width + 10
        prev.convert('RGB').save('%s-%s.png' % (PREVIEW, tag))
print({k: c.size for k, c in cuts.items()})
