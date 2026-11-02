"""Paint a Dead Space 1 suit in the style of a DLC suit (custom suits).

The DLC suits are repaints of the level 5 suit on the same UV layout, so the style is learned pixel for pixel:
a colour table (32 bins per channel) maps every level 5 colour to the average DLC colour at the same place. A
target suit's colour maps go through that table; the worn, lighter paint at the plate edges of the DLC look is
added where the target's normal map bends (plate edges) and its own grime is lightest.

usage: python -I tools/ds1_suit_style.py STYLE TARGET OUT_DIR   (STYLE: scorpion, TARGET: unilvl3)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ds1_dlc_build as b  # noqa: E402
import ds1_texture as tex  # noqa: E402

STYLES = {
    "scorpion": ("Scorpion_Pack", "uniScorpion", "isaacscorpion"),
    "obsidian": ("Obsidian_Pack", "uniSony", "pdlcisaacsony"),
    "unitology": ("Tank_Pack", "uniUnitology", "isaacunitology"),
    "elite": ("Elite_Pack", "uniMicrosoft", "pdlcisaacmicrosoft"),
    "astronaut": ("Astronaut_Pack", "uniAstronaut", "isaacastronaut"),
    # the level 6 suit itself (the console Military pack's suit): white panels on a dark suit
    "military": (None, "uniMarine", "pdlcisaacmarine"),
}


def style_dir(style):
    """The stage folder of a style's suit: a built DLC pack, or a PC suit for a style without a pack."""
    pack, archive, stem = STYLES[style]
    return b.WORK / "pc" / archive if pack is None else b.DLC / "build" / pack / "stage" / archive
# targets whose armour is white panels instead of copper paint
WHITE_PAINT = {"uniMarine"}
# targets with dark rust plates the copper mask misses
RUST_PAINT = {"unilvl4"}
# targets whose leather is strewn with chipped copper paint: the chips are dropped before the paint mask is
# closed, or the closing grew them into blocks of paint all over the leather (Elite level 2, 2026-10-24)
CHIPPED_PAINT = {"unilvl1", "unilvl2"}
BINS = 32


def textures(folder):
    members = b.read_archive(folder)
    by = {m.key: m for m in members}
    out = {}
    for m in members:
        if m.attrs["type_name"] == "tg4h" and (m.attrs["base_name"], "tg4d") in by:
            try:
                out[m.attrs["base_name"]] = (m, by[(m.attrs["base_name"], "tg4d")])
            except ValueError:
                pass
    return out


def image(pair):
    return tex.read(pair[0].data(), pair[1].data())


def learn_table(style):
    pack, archive, stem = STYLES[style]
    styled = textures(style_dir(style))
    base = textures(b.WORK / "pc" / "unilvl5")
    sums = np.zeros((BINS, BINS, BINS, 3))
    counts = np.zeros((BINS, BINS, BINS))
    for name, pair in styled.items():
        if not name.startswith(stem) or not name.endswith("_c"):
            continue
        source = base.get("isaaclevel5" + name[len(stem):])
        if not source:
            continue
        a = np.asarray(image(source).convert("RGB"), dtype=np.float64)
        t = image(pair).convert("RGB")
        t = np.asarray(t.resize((a.shape[1], a.shape[0]), Image.BILINEAR), dtype=np.float64)
        idx = np.clip((a / 256 * BINS).astype(int), 0, BINS - 1).reshape(-1, 3)
        np.add.at(sums, (idx[:, 0], idx[:, 1], idx[:, 2]), t.reshape(-1, 3))
        np.add.at(counts, (idx[:, 0], idx[:, 1], idx[:, 2]), 1)
    filled = counts > 0
    table = np.zeros_like(sums)
    table[filled] = sums[filled] / counts[filled][:, None]
    # empty bins take the nearest filled one
    coords = np.argwhere(filled)
    for empty in np.argwhere(~filled):
        nearest = coords[np.argmin(((coords - empty) ** 2).sum(1))]
        table[tuple(empty)] = table[tuple(nearest)]
    return table


def apply_table(rgb, table):
    x = np.asarray(rgb, dtype=np.float64) / 256 * BINS - 0.5
    lo = np.clip(np.floor(x).astype(int), 0, BINS - 1)
    hi = np.clip(lo + 1, 0, BINS - 1)
    f = np.clip(x - lo, 0, 1)
    out = 0
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                r = hi[..., 0] if dr else lo[..., 0]
                g = hi[..., 1] if dg else lo[..., 1]
                bb = hi[..., 2] if db else lo[..., 2]
                w = (f[..., 0] if dr else 1 - f[..., 0]) * (f[..., 1] if dg else 1 - f[..., 1]) * \
                    (f[..., 2] if db else 1 - f[..., 2])
                out = out + table[r, g, bb] * w[..., None]
    return out


def edge_wear(normal_img, size, rgb_in):
    """Plate edges: where the normal map bends, on light (painted) parts."""
    n = np.asarray(normal_img.resize(size, Image.BILINEAR), dtype=np.float64)
    nx, ny = n[..., 3] / 255 * 2 - 1, n[..., 1] / 255 * 2 - 1   # DXT5_NM: x in alpha, y in green
    tilt = np.sqrt(nx * nx + ny * ny)
    edges = np.clip((tilt - 0.25) * 3, 0, 1)
    edges = np.asarray(Image.fromarray((edges * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),
                       dtype=np.float64) / 255
    light = rgb_in.mean(-1) / 255
    grime = np.asarray(Image.fromarray(rgb_in.astype(np.uint8)).convert("L").filter(ImageFilter.FIND_EDGES),
                       dtype=np.float64) / 255
    return np.clip(edges * np.clip(light * 1.6, 0, 1) * (0.55 + grime * 2), 0, 1)


def hsv(rgb):
    return np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("HSV"), dtype=np.float64)


def paint_mask(rgb):
    """The painted armour of the original suits: copper orange (hue about 20 degrees), saturated and not dark
    (dark brown is leather and stays)."""
    h = hsv(rgb)
    hue, sat, val = h[..., 0] / 255 * 360, h[..., 1] / 255, h[..., 2] / 255
    hue_ok = np.clip(1 - np.abs(hue - 20) / 26, 0, 1)
    soft = hue_ok * np.clip((sat - 0.25) * 6, 0, 1) * np.clip((val - 0.28) * 6, 0, 1)
    return np.clip((soft - 0.25) * 3, 0, 1)


def white_mask(rgb):
    """White armour panels (the level 6 suit): unsaturated and light."""
    h = hsv(rgb)
    sat, val = h[..., 1] / 255, h[..., 2] / 255
    soft = np.clip((0.22 - sat) * 8, 0, 1) * np.clip((val - 0.45) * 5, 0, 1)
    return np.clip((soft - 0.25) * 3, 0, 1)


def rust_mask(rgb):
    """The level 4 suit's dark rust-red plates next to its copper ones; leather and cloth are less saturated."""
    h = hsv(rgb)
    hue, sat, val = h[..., 0] / 255 * 360, h[..., 1] / 255, h[..., 2] / 255
    hue_ok = np.clip(1 - np.abs(((hue + 180) % 360 - 180) - 17) / 28, 0, 1)
    soft = hue_ok * np.clip((sat - 0.33) * 5, 0, 1) * np.clip((val - 0.14) * 6, 0, 1)
    return np.maximum(paint_mask(rgb), np.clip((soft - 0.2) * 3, 0, 1))


def target_mask(target, rgb):
    if target in WHITE_PAINT:
        return white_mask(rgb)
    return rust_mask(rgb) if target in RUST_PAINT else paint_mask(rgb)


def cyan_mask(rgb):
    h = hsv(rgb)
    return (np.abs(h[..., 0] / 255 * 360 - 165) < 25) & (h[..., 1] > 90) & (h[..., 2] > 120)


def fill_islands(mask, max_share=0.003, border=0.8):
    """Small unpainted islands wholly inside paint (dark trim squares, grime blocks) painted too, so a clean
    style shows no camouflage of grey squares."""
    from scipy import ndimage
    paint = mask > 0.5
    labels, count = ndimage.label(~paint)
    if not count:
        return mask
    out = mask.copy()
    limit = max_share * mask.size
    for index, box in enumerate(ndimage.find_objects(labels), 1):
        if box is None:
            continue
        ys, xs = box
        y0, y1, x0, x1 = max(ys.start - 1, 0), min(ys.stop + 1, mask.shape[0]), max(xs.start - 1, 0),             min(xs.stop + 1, mask.shape[1])
        island = labels[y0:y1, x0:x1] == index
        if island.sum() > limit:
            continue
        ring = ndimage.binary_dilation(island) & ~island
        if ring.any() and paint[y0:y1, x0:x1][ring].mean() >= border:
            out[y0:y1, x0:x1][island] = 1.0
    return out


def drop_specks(mask, max_share=0.00025):
    """Tiny paint islands (copper paint chips on the cloth) dropped, so a clean style shows no white dots there."""
    from scipy import ndimage
    labels, count = ndimage.label(mask > 0.5)
    if not count:
        return mask
    sizes = ndimage.sum(np.ones_like(mask), labels, index=np.arange(1, count + 1))
    small = np.isin(labels, np.nonzero(sizes <= max(60, max_share * mask.size))[0] + 1)
    out = mask.copy()
    out[small] = 0.0
    return out


def muted_copper(rgb, paint, max_share=0.015):
    """Dull or dark rust coloured pieces (the bars across the level 1 visor, the dark patches beside the level 5
    visor slits) as compact areas; large ones of the same tone (the level 1 vent, the level 5 centre stripe)
    stay."""
    from scipy import ndimage
    h = hsv(rgb)
    hue, sat, val = h[..., 0] / 255 * 360, h[..., 1] / 255, h[..., 2] / 255
    muted = (paint < 0.5) & ((hue < 40) | (hue > 340)) & (((sat > 0.12) & (val > 0.25)) | ((sat > 0.33) & (val > 0.14)))
    muted = ndimage.binary_closing(muted, iterations=2)
    labels, count = ndimage.label(muted)
    if not count:
        return np.zeros_like(paint)
    sizes = ndimage.sum(np.ones_like(paint), labels, index=np.arange(1, count + 1))
    keep = np.nonzero((sizes >= 40) & (sizes <= max_share * paint.size))[0] + 1
    return np.isin(labels, keep).astype(np.float64)


def sampled_pixels(target, map_name, shape):
    """Pixels of a colour map the suit's mesh really samples, from the mesh the icon export wrote
    (icon_work/suit_levelN/mesh.npz); None without it."""
    import json
    from PIL import ImageDraw
    levels = {"unilvl1": 1, "unilvl2": 2, "unilvl3": 3, "unilvl4": 4, "unilvl5": 5, "uniMarine": 6}
    folder = b.DLC / "icon_work" / ("suit_level%d" % levels.get(target, 0))
    if not (folder / "mesh.npz").is_file():
        return None
    mesh = np.load(folder / "mesh.npz")
    maps = json.loads((b.DLC / "icon_work" / "manifest_suits.json").read_text(encoding="utf-8"))
    maps = maps["suit_level%d" % levels[target]]["maps"]
    canvas = Image.new("L", (shape[1], shape[0]), 0)
    draw = ImageDraw.Draw(canvas)
    for k, name in enumerate(maps):
        if name != map_name + ".png" or "uv%d" % k not in mesh.files:
            continue
        uv, tris = mesh["uv%d" % k], mesh["tris%d" % k]
        for t in tris:
            draw.polygon([(uv[i][0] % 1 * shape[1], (1 - uv[i][1] % 1) * shape[0]) for i in t], fill=255)
    return np.asarray(canvas) > 0


def green_lens_mask(rgb):
    """The pale green eye lenses of the level 6 helmet."""
    h = hsv(rgb)
    hue = h[..., 0] / 255 * 360
    return (hue > 105) & (hue < 150) & (h[..., 1] > 45) & (h[..., 2] > 80)


def close_mask(mask, size=7):
    """The painted areas without the holes their grime leaves."""
    m = Image.fromarray((mask * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    return np.asarray(m, dtype=np.float64) / 255


def open_mask(mask, size=5):
    """The painted areas without the chips smaller than size."""
    m = Image.fromarray((mask * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MinFilter(size)).filter(ImageFilter.MaxFilter(size))
    return np.asarray(m, dtype=np.float64) / 255


def plate_edges(mask, width=2):
    """A band just inside the border of the painted areas: the plate edges in the texture."""
    m = Image.fromarray((close_mask(mask) * 255).astype(np.uint8))
    inner = np.asarray(m.filter(ImageFilter.MinFilter(width * 2 + 1)), dtype=np.float64) / 255
    band = np.clip(mask - inner, 0, 1)
    return np.asarray(Image.fromarray((band * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)),
                      dtype=np.float64) / 255


def noise(shape, seed, scale=6):
    rng = np.random.default_rng(seed)
    small = rng.random((max(1, shape[0] // scale), max(1, shape[1] // scale)))
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.asarray(img, dtype=np.float64) / 255


def rgb_of(pair, size=None):
    img = image(pair).convert("RGB")
    if size and img.size != size:
        img = img.resize(size, Image.BILINEAR)
    return np.asarray(img, dtype=np.float64)


def aligned_pairs(style, suffixes=("upperbody_c", "lowerbody_c", "helmet_c")):
    """(level 5 pixels, style pixels at the same place) for the maps a level 5 reskin shares with level 5."""
    pack, archive, stem = STYLES[style]
    styled = textures(style_dir(style))
    base = textures(b.WORK / "pc" / "unilvl5")
    for suffix in suffixes:
        if stem + suffix in styled and "isaaclevel5" + suffix in base:
            a = rgb_of(base["isaaclevel5" + suffix])
            yield suffix, a, rgb_of(styled[stem + suffix], (a.shape[1], a.shape[0]))


def paint_pixels(style):
    """The style's paint: what it put where level 5 has its copper paint."""
    pack, archive, stem = STYLES[style]
    styled = textures(style_dir(style))
    if style == "scorpion":
        pixels = []
        for name in ("upperbody_c", "lowerbody_c", "cap_c", "captorso_c", "helmet_c"):
            pair = styled.get(stem + name)
            if pair:
                pixels.append(np.asarray(image(pair).convert("RGB"), dtype=np.float64).reshape(-1, 3))
        px = np.concatenate(pixels)
        return px[(px[:, 0] > px[:, 1] * 1.6) & (px[:, 0] > px[:, 2] * 1.6) & (px[:, 0] > 40)]
    if style == "military":
        # the white panels of the level 6 suit
        px = []
        for n in ("body_c", "helmet_c"):
            rgb = rgb_of(styled[stem + n])
            m = (white_mask(rgb) > 0.6) & ~green_lens_mask(rgb)
            px.append(rgb[m])
        return np.concatenate(px)
    if style == "astronaut":
        # its own UV layout: the orange and red plates
        px = np.concatenate([rgb_of(styled[stem + n]).reshape(-1, 3) for n in ("upperbody_c", "lowerbody_c")])
        h = hsv(px.reshape(-1, 1, 3)).reshape(-1, 3)
        hue, sat, val = h[:, 0] / 255 * 360, h[:, 1] / 255, h[:, 2] / 255
        return px[((hue < 35) | (hue > 350)) & (sat > 0.5) & (val > 0.3)]
    pixels = []
    for _, a, t in aligned_pairs(style):
        m = (close_mask(paint_mask(a)) > 0.6) & ~cyan_mask(a)
        pixels.append(t[m])
    px = np.concatenate(pixels)
    # decals and stripes the style put on the paint (the Obsidian's white bands) are not its paint
    luma = px @ np.array([0.299, 0.587, 0.114])
    return px[luma <= np.percentile(luma, 92)]


def paint_tone(style):
    """Median hue and saturation of the style's paint (0..255 scale)."""
    if style == "scorpion":
        pack, archive, stem = STYLES[style]
        styled = textures(style_dir(style))
        px = np.concatenate([np.asarray(image(styled[stem + n]).convert("RGB"), dtype=np.float64).reshape(-1, 3)
                             for n in ("upperbody_c", "helmet_c") if stem + n in styled])
        px = px[(px[:, 0] > px[:, 1] * 1.8) & (px[:, 0] > 60)]
    else:
        px = paint_pixels(style)
    h = hsv(px.reshape(-1, 1, 3)).reshape(-1, 3)
    return np.median(h[:, 0]), np.median(h[:, 1])


def visor_colour(style):
    """The colour the style gives the cyan visor parts of the colour maps; None keeps them."""
    if style == "scorpion":
        return np.array([255, 32, 16])
    if style == "astronaut":
        # the cyan of the Astronaut suit's visor; without a colour the lenses were painted over (level 4)
        return np.array([90, 208, 178])
    if style == "military":
        # the blue the Military suit's visor shines in (its texture lenses are pale green)
        return np.array([70, 135, 255])
    if style in CLEAN_STYLES:
        # the glow map holds the colour the visor really shines in
        pack, archive, stem = STYLES[style]
        styled = textures(style_dir(style))
        if stem + "helmet_l" in styled:
            px = rgb_of(styled[stem + "helmet_l"]).reshape(-1, 3)
            px = px[px.max(1) > 120]
            if len(px) > 50:
                return np.median(px, 0)
    for _, a, t in aligned_pairs(style, ("helmet_c",)):
        m = cyan_mask(a)
        if m.sum() > 50:
            return np.median(t[m], 0)
    return None


# styles with clean paint over a suit of their own colour (the Elite: white plates, dark grey suit)
CLEAN_STYLES = {"elite", "obsidian", "unitology", "military"}
# typical plate brightness of a clean style whose paint pixels are darkened by what was cut away (lettering)
PLATE_BRIGHTNESS = {"unitology": 115}
# styles whose paint carries lettering; it is cut from the DLC suit and laid on the target's paint
DECAL_STYLES = set()   # the Unitology lettering is hand-painted per plate and does not carry over
DECAL_TILE = 96
_decal_cache = {}


def decal_tiles(style):
    """Lettering tiles of a style: (alpha, colour, source width, helmet?) from its body and helmet maps."""
    if style in _decal_cache:
        return _decal_cache[style]
    pack, archive, stem = STYLES[style]
    styled = textures(style_dir(style))
    tiles = []
    for n in ("upperbody_c", "lowerbody_c", "helmet_c"):
        rgb = rgb_of(styled[stem + n])
        luma = rgb @ np.array([0.299, 0.587, 0.114])
        blur = np.asarray(Image.fromarray(luma.astype(np.uint8)).filter(ImageFilter.MedianFilter(9)),
                          dtype=np.float64)
        sat = hsv(rgb)[..., 1] / 255
        alpha = np.clip((luma - blur - 30) / 30, 0, 1) * (sat < 0.3)
        t = DECAL_TILE
        for y in range(0, rgb.shape[0] - t + 1, t // 2):
            for x in range(0, rgb.shape[1] - t + 1, t // 2):
                a = alpha[y:y + t, x:x + t]
                strong = (a > 0.5).mean()
                if 0.05 < strong < 0.3:
                    colour = np.median(rgb[y:y + t, x:x + t][a > 0.5], 0)
                    tiles.append((strong, a, colour, rgb.shape[1], n == "helmet_c"))
    tiles.sort(key=lambda r: -r[0])
    _decal_cache[style] = [r[1:] for r in tiles[:120]]
    return _decal_cache[style]


def apply_decals(style, out, mask, name, width):
    """Lettering on the paint: tiles that fit wholly on it, not overlapping, faded at their borders."""
    helmet = "helmet" in name
    tiles = [r for r in decal_tiles(style) if r[3] == helmet] or decal_tiles(style)
    rng = np.random.default_rng(sum(name.encode()) * 7919)
    h, w = mask.shape
    used = np.zeros_like(mask, dtype=bool)
    ramp = np.minimum(np.arange(DECAL_TILE), np.arange(DECAL_TILE)[::-1]) / (DECAL_TILE * 0.18)
    window = np.clip(np.minimum.outer(ramp, ramp), 0, 1)
    placed = 0
    wanted = int(mask.sum() / (DECAL_TILE * DECAL_TILE) * 0.5)
    for _ in range(wanted * 60):
        if placed >= wanted:
            break
        alpha, colour, source_width, _ = tiles[rng.integers(len(tiles))]
        # full size where a plate allows it, smaller lettering on narrow plates
        scale = min(1.0, max(0.75, width / source_width))   # half-size maps cover as much body
        size = max(24, int(round(DECAL_TILE * scale * (1.0, 0.7, 0.5)[rng.integers(3)])))
        if size >= min(h, w):
            continue
        y, x = rng.integers(0, h - size), rng.integers(0, w - size)
        if mask[y:y + size, x:x + size].mean() < 0.92 or used[y:y + size, x:x + size].any():
            continue
        a = np.clip(alpha * 1.8, 0, 1) * window
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR),
                       dtype=np.float64)[..., None] / 255 * 0.95
        region = out[y:y + size, x:x + size]
        out[y:y + size, x:x + size] = region * (1 - a) + np.maximum(colour, 185) * a
        used[y:y + size, x:x + size] = True
        placed += 1
    return placed


def spec_colour(style):
    """The style's specular colour on its paint (median of its _s map there)."""
    pack, archive, stem = STYLES[style]
    styled = textures(style_dir(style))
    pixels = []
    if style == "military":
        for n in ("body", "helmet"):
            c = rgb_of(styled[stem + n + "_c"])
            sp = rgb_of(styled[stem + n + "_s"], (c.shape[1], c.shape[0]))
            pixels.append(sp[white_mask(c) > 0.6])
    elif style == "astronaut":
        for n in ("upperbody", "lowerbody"):
            c = rgb_of(styled[stem + n + "_c"])
            sp = rgb_of(styled[stem + n + "_s"], (c.shape[1], c.shape[0]))
            h = hsv(c)
            hue, sat = h[..., 0] / 255 * 360, h[..., 1] / 255
            pixels.append(sp[((hue < 35) | (hue > 350)) & (sat > 0.5)])
    else:
        for suffix, a, _ in aligned_pairs(style):
            name = stem + suffix[:-2] + "_s"
            if name in styled:
                sp = rgb_of(styled[name], (a.shape[1], a.shape[0]))
                pixels.append(sp[(close_mask(paint_mask(a)) > 0.6) & ~cyan_mask(a)])
    px = np.concatenate(pixels) if pixels else np.zeros((0, 3))
    return np.median(px, 0) if len(px) > 100 else None


def paint_curve(style):
    """Colour of the style's paint by brightness: median of its paint pixels per brightness step."""
    red = paint_pixels(style)
    luma = red @ np.array([0.299, 0.587, 0.114])
    curve = np.zeros((256, 3))
    quantiles = np.percentile(luma, np.arange(101))
    steps = np.linspace(luma.min(), luma.max(), 33)
    centres, colours = [], []
    for lo, hi in zip(steps[:-1], steps[1:]):
        sel = red[(luma >= lo) & (luma < hi)]
        if len(sel) > 50:
            centres.append((lo + hi) / 2)
            colours.append(np.median(sel, 0))
    centres, colours = np.array(centres), np.array(colours)
    for c in range(3):
        curve[:, c] = np.interp(np.arange(256), centres, colours[:, c])
    return curve, quantiles


def stylize(style, target, out_dir):
    pack, archive, stem = STYLES[style]
    styled = textures(style_dir(style))
    curve, style_q = paint_curve(style)
    wear_colour = None
    if style == "scorpion":
        # worn gold at the plate edges
        sample = np.asarray(image(styled[stem + "upperbody_c"]).convert("RGB"), dtype=np.float64).reshape(-1, 3)
        warm = sample[(sample[:, 0] > 150) & (sample[:, 1] > 100) & (sample[:, 2] < 90)]
        wear_colour = np.median(warm, 0) if len(warm) else np.array([210, 160, 60])
        wear_colour = np.array([min(255, wear_colour[0]), max(wear_colour[1], 150), min(wear_colour[2], 70)])
    # the style's paint hue and saturation (median of its paint pixels)
    paint_hue, paint_sat = paint_tone(style)
    visor = visor_colour(style)
    clean = style in CLEAN_STYLES
    spec = spec_colour(style)
    own = textures(b.WORK / "pc" / target)
    # the original paint's brightness distribution is matched onto the style's; level 3 keeps the reference
    # of its approved first version (torso and torso caps)
    if target == "unilvl3":
        ref_names = [n for n in own if n.endswith("_c") and n.startswith("playerminera_t")]
    else:
        ref_names = [n for n in own if n.endswith("_c") and "cap" not in n and
                     not n.startswith(("grip", "playerminera_healthbar", "playerminera_stasisbar"))]
    reference = np.concatenate([np.asarray(image(own[n]).convert("RGB"), dtype=np.float64).reshape(-1, 3)
                                for n in ref_names])
    ref_mask = target_mask(target, reference.reshape(-1, 1, 3)).reshape(-1) > 0.5
    ref_luma = reference[ref_mask] @ np.array([0.299, 0.587, 0.114])
    own_q = np.percentile(ref_luma, np.arange(101))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, pair in sorted(own.items()):
        if not name.endswith("_c") or name.startswith(("grip", "playerminera_healthbar", "playerminera_stasisbar")):
            continue
        # the dismemberment caps are mostly flesh; only the Scorpion's red may touch them
        if "cap" in name and style != "scorpion":
            continue
        try:
            src = image(pair)
        except ValueError:
            continue
        rgb = np.asarray(src.convert("RGB"), dtype=np.float64)
        raw_mask = target_mask(target, rgb)
        if target in CHIPPED_PAINT:
            if "helmet" in name:
                # the thin dark copper bars across the level 1 visor are paint too: an opening dropped them and
                # they stayed grey on the Military custom (2026-10-25); the helmet has no leather to chip
                raw_mask = np.maximum(drop_specks(raw_mask), muted_copper(rgb, raw_mask))
            else:
                raw_mask = np.minimum(raw_mask, open_mask(raw_mask))
        if "helmet" in name and target not in WHITE_PAINT and target not in CHIPPED_PAINT:
            # dark rust patches beside the level 5 visor slits stayed black on the Military custom (2026-10-25)
            raw_mask = np.maximum(raw_mask, muted_copper(rgb, raw_mask))
        if target in WHITE_PAINT:
            # coloured prints inside a white panel (the chest emblem, the red helmet stripes) are painted over
            h0 = hsv(rgb)
            prints = (h0[..., 1] > 64) & (h0[..., 2] > 50) & ~cyan_mask(rgb) & ~green_lens_mask(rgb)
            raw_mask = np.maximum(raw_mask, close_mask(raw_mask, 25) * prints)
        if target in RUST_PAINT:
            # the level 4 armour samples the neutral grey filler between the texture's islands on some faces; left
            # unpainted it showed as dark stripes on the arms of the clean styles (2026-10-30)
            used = sampled_pixels(target, name, rgb.shape[:2])
            if used is not None:
                h0 = hsv(rgb)
                filler = used & (h0[..., 1] < 16) & (h0[..., 2] > 70) & (h0[..., 2] < 140)
                raw_mask = np.maximum(raw_mask, filler.astype(np.float64))
        # the closed mask decides; grime spots inside a plate are repainted with it (they stay dark by brightness)
        # Clean styles and the Scorpion on the grimy level 4 suit get tidy paint: grime covered and smoothed away.
        tidy = clean or (style == "scorpion" and target in RUST_PAINT)
        if tidy:
            # clean paint covers the grime too, also the dark spots inside a plate
            # (not the neutral grey between the texture's islands, which would bleed into the seams)
            sat0 = hsv(rgb)[..., 1] / 255
            grime = (sat0 > 0.1) | (rgb.mean(-1) < 90)
            mask = np.maximum(raw_mask, close_mask(raw_mask, 15) * grime)
            if tidy:
                # a hard decision with soft edges: half-painted trim squares would turn grey otherwise; on the
                # level 4 helmet also its two curved pads, which the paint encloses
                share = 0.03 if target in RUST_PAINT and "helmet" in name else 0.003
                if clean and "helmet" in name:
                    # the dark dirt patches on the level 5 helmet plates stayed as black blocks (Military, 2026-10-25)
                    share = max(share, 0.02)
                mask = fill_islands((mask > 0.25).astype(np.float64), max_share=share)
                if clean:
                    mask = drop_specks(mask)
                mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)),
                                  dtype=np.float64) / 255
            mask = mask[..., None]
        else:
            mask = np.maximum(raw_mask, close_mask(raw_mask) * (rgb.mean(-1) > 35))[..., None]
        luma = rgb @ np.array([0.299, 0.587, 0.114])
        # brightness quantile of the original paint -> the same quantile of the style's paint
        blur = np.asarray(Image.fromarray(luma.astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)),
                          dtype=np.float64)
        detail = np.clip(luma / np.maximum(blur, 1), 0.6, 1.5)[..., None]
        if tidy:
            # the grime smoothed away, the brightness kept close to the style's typical paint (a coloured style
            # keeps a little more of the original's shading)
            smooth = np.asarray(Image.fromarray(luma.astype(np.uint8)).filter(ImageFilter.MedianFilter(7)),
                                dtype=np.float64)
            if clean:
                # only local relief survives: a dark trim square or grime block inside a plate no longer shows
                wide = np.asarray(Image.fromarray(smooth.astype(np.uint8)).filter(ImageFilter.GaussianBlur(12)),
                                  dtype=np.float64)
                target_luma = style_q[60] + np.clip((smooth - wide) * 0.15, -12, 12)
                keep = 0.06
            else:
                target_luma = np.interp(smooth, own_q, style_q)
                target_luma = np.maximum(style_q[60] + (target_luma - style_q[60]) * 0.4, style_q[40])
                keep = 0.12
            painted = curve[np.clip(target_luma, 0, 255).astype(int)] * (1 - keep + keep * detail)
            if style in PLATE_BRIGHTNESS:
                # plates lighter than the suit, as the original's are under its lettering
                painted = painted * (PLATE_BRIGHTNESS[style] / max(style_q[60], 1))
            painted = np.minimum(painted, 236)
        else:
            target_luma = np.interp(luma, own_q, style_q)
            painted = curve[np.clip(target_luma, 0, 255).astype(int)]
            # keep the original's fine detail: its brightness relative to a blurred copy
            painted = painted * (0.5 + 0.5 * detail)
        # a coloured style's hue and saturation (deep crimson for the Scorpion), the brightness kept
        if paint_sat > 0.3 * 255:
            ph = hsv(painted)
            ph[..., 0] = paint_hue
            ph[..., 1] = np.maximum(ph[..., 1], paint_sat)
            painted = np.asarray(Image.fromarray(ph.astype(np.uint8), "HSV").convert("RGB"), dtype=np.float64)
        elif paint_sat < 8:
            # an uncoloured style stays uncoloured: the dark end of the learned curve carried the green steps of
            # the console maps' compression, and the Obsidian's gloss showed it green (2026-10-30)
            painted = np.repeat((painted @ np.array([0.299, 0.587, 0.114]))[..., None], 3, -1)
        normal = own.get(name[:-2] + "_n")
        if wear_colour is not None:
            # worn gold at the plate borders, broken up by noise
            band = plate_edges(raw_mask)[..., None]
            broken = np.clip((noise(rgb.shape[:2], sum(name.encode())) - 0.35) * 4, 0, 1)[..., None]
            gold = band * broken * (0.35 if tidy else 0.7)   # level 4 has many small plates: less gold
            painted = painted * (1 - gold) + wear_colour * (0.75 + 0.25 * detail) * gold
        if normal and wear_colour is not None and not tidy:
            wear = edge_wear(image(normal), src.size, rgb)[..., None] * mask
            wear = np.where(wear > 0.35, wear, 0) * 0.7
            painted = painted * (1 - wear) + wear_colour * wear
        # the cyan visor of the original takes the style's visor colour
        out = rgb * (1 - mask) + painted * mask
        if clean:
            # everything outside the paint (cloth, leather, rust, metal) turns the dark grey of the style's suit,
            # its brightness range narrowed; the cyan lights keep their colour
            weight = (1 - mask[..., 0]) * ~cyan_mask(rgb)
            grey = (30 + luma * 0.4)[..., None] * (0.85 + 0.15 * detail)
            out = out * (1 - weight[..., None]) + grey * weight[..., None]
        decals = 0
        if style in DECAL_STYLES:
            decals = apply_decals(style, out, mask[..., 0], name, rgb.shape[1])
        lens = cyan_mask(rgb)
        if style in CLEAN_STYLES and "helmet" not in name:
            # the cyan status lights on belt and pouches turn grey, they read as stray spots on a clean suit
            lights = cyan_mask(rgb)
            if lights.any():
                from scipy import ndimage
                lights = ndimage.binary_dilation(lights, iterations=1) & (hsv(rgb)[..., 1] > 40)
                grey = (rgb[lights] @ np.array([0.299, 0.587, 0.114]))[:, None] * 0.55
                out[lights] = grey
            lens[:] = False
        elif style in CLEAN_STYLES and lens.any():
            # the soft edge pixels of the visor glass too, or they glow cyan inside the visor
            from scipy import ndimage
            lens = ndimage.binary_dilation(lens, iterations=1) & (hsv(rgb)[..., 1] > 40)
        if target in WHITE_PAINT and "helmet" in name:
            lens |= green_lens_mask(rgb)
        if visor is not None and lens.any():
            if style == "scorpion" and target == "unilvl3":
                out[lens] = visor   # the approved first version: flat
            else:
                # shaded by the original's brightness, so a large visor glass keeps its detail
                val = hsv(rgb)[..., 2]
                shade = np.clip(val / max(np.percentile(val[lens], 90), 1), 0.35, 1.15)
                if lens.mean() > 0.02:
                    # a whole visor glass: its scratches and highlights are colourless and would stay white
                    from scipy import ndimage
                    glass = ndimage.binary_fill_holes(ndimage.binary_closing(lens, iterations=4)) | lens
                    shade[glass & ~lens] = np.median(shade[lens])
                    lens = glass
                # a whole visor glass (levels 1 to 3) shines as bright as the console suit's glow map; tinted to
                # 55 % it read as switched off next to level 4 (2026-10-30)
                # never past 255 in the visor's brightest channel: the Military blue went cyan-white there
                lift = np.minimum(shade[lens], 255 / max(float(np.max(visor)), 1))
                out[lens] = np.clip(np.asarray(visor, dtype=np.float64) * lift[:, None], 0, 255)
                from scipy import ndimage
                ring = ndimage.binary_dilation(lens, iterations=3) & ~lens
                if ring.any() and target in WHITE_PAINT:
                    around = np.median(out[ring], axis=0)
                    if np.abs(around - np.median(out[lens], axis=0)).max() < 70:
                        # the glow is the colour of the paint around it (Unitology's white on the white level 6
                        # panels, 2026-10-30): a dark rim and full brightness make it a lit slot in the plate
                        inner = ndimage.binary_dilation(lens, iterations=1) & ~lens
                        out[ring] = out[ring] * 0.45
                        out[inner] = out[inner] * 0.6
                        peak = np.asarray(visor, dtype=np.float64)
                        out[lens] = np.clip(peak / max(peak.max(), 1) * 255 * np.clip(shade[lens], 0.85, 1.0)[:, None],
                                            0, 255)
        result = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGBA")
        result.putalpha(src.getchannel("A"))
        result.save(out_dir / (name + ".png"))
        results[name] = result
        # the specular map: the style's shine on its paint, a neutral one on the greyed rest
        spec_name = name[:-2] + "_s"
        if spec_name in own and spec is not None:
            try:
                spec_src = image(own[spec_name])
            except ValueError:
                spec_src = None
            if spec_src is not None:
                s_rgb = np.asarray(spec_src.convert("RGB"), dtype=np.float64)
                size = (s_rgb.shape[1], s_rgb.shape[0])
                m = np.asarray(Image.fromarray((mask[..., 0] * 255).astype(np.uint8)).resize(size, Image.BILINEAR),
                               dtype=np.float64)[..., None] / 255
                s_luma = s_rgb @ np.array([0.299, 0.587, 0.114])
                ref = max(np.median(s_luma[m[..., 0] > 0.5]) if (m > 0.5).any() else 1, 1)
                variation = np.clip(s_luma / ref, 0.6, 1.4)[..., None]
                shine = spec * (0.92 + 0.08 * variation if clean else 0.75 + 0.25 * variation)
                s_out = s_rgb * (1 - m) + shine * m
                if clean:
                    s_out = s_out * m + np.repeat(s_luma[..., None], 3, -1) * (1 - m)
                s_img = Image.fromarray(np.clip(s_out, 0, 255).astype(np.uint8)).convert("RGBA")
                s_img.putalpha(spec_src.getchannel("A"))
                s_img.save(out_dir / (spec_name + ".png"))
                results[spec_name] = s_img
        print(name, src.size, "paint %.0f%%" % (mask.mean() * 100) + (", %d decals" % decals if decals else ""))
    return results


if __name__ == "__main__":
    stylize(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
