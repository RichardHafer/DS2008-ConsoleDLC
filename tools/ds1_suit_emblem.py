"""Pack emblems on the custom suits: the scorpion of the retail Scorpion helmet on every Scorpion level.

The emblem is cut from the retail colour map and located on the level 5 helmet it was painted for (the retail suit
reuses the level 5 meshes and UVs), which gives its size and its turn against the model's up axis. Each level's
helmet then gets it where it sits cleanly: on paint, away from hard edges, seams and holes, with nothing of the
helmet in front of it and on a gently curved spot, as large as the room allows up to the retail size, upright, and
on the same side and half of the helmet as the retail one where possible.
"""
import struct
import zlib

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree


# style: (retail colour map, level 5 map with the same UVs, emblem box in the retail map's pixels)
EMBLEMS = {"scorpion": ("isaacscorpionhelmet_c", "isaaclevel5helmet_c", (28, 18, 104, 110))}
BASE_TARGET = "unilvl5"
UP = np.array([0.0, 1.0, 0.0])   # the suit models stand along +y
MIN_SCALE = 0.45                 # smaller than this against the retail emblem and it turns to mush
MAX_TURN = np.radians(28)        # surface normals under the emblem stay within this of its own
_cache = {}


def read_mesh(data):
    """A PC skinned Mesh as write_mesh lays it out (Isaac's retail meshes too): per sub-mesh the material crc,
    positions, normals, UVs, triangles and [(bone row, weight)] per vertex, plus the bone rows (name, skeleton index) and
    their inverse bind matrices."""
    u = lambda o: struct.unpack_from("<I", data, o)[0]
    rows, inv = [], []
    for i in range(u(0x38)):
        at = u(0x60) + 16 * i
        rows.append((data[u(at):data.index(b"\0", u(at))].decode(), u(at + 12)))
        inv.append(np.array(struct.unpack_from("<16f", data, u(0x64) + 64 * i), np.float64).reshape(4, 4))
    uv_at = u(u(0x68) + 0x1C)
    subs = []
    for k in range(u(0x34)):
        s = u(0x50) + 0xA0 * k
        influences, palette_n = data[s + 6], data[s + 0x29]
        n_idx, _, first_v, n_v = struct.unpack_from("<IIHH", data, u(s + 0x30))
        pal = [data[u(s + 0x48) + 2 * j] for j in range(palette_n)]
        vtx = np.frombuffer(data, np.uint8, 32 * n_v, u(s + 0x38)).reshape(n_v, 32)
        pos = vtx[:, :12].copy().view("<f4").astype(np.float64)
        idx, w = vtx[:, 20:24], vtx[:, 24:32].copy().view("<u2")
        packed = vtx[:, 12:16].copy().view("<u4")[:, 0].astype(np.int64)
        normal = np.stack([((packed >> k) & 0x3FF) for k in (0, 10, 20)], 1)
        normal = np.where(normal >= 512, normal - 1024, normal) / 511.0
        weights = [[(pal[0], 1.0)] if influences == 0 else
                   [(pal[idx[v, j]], w[v, j] / 65535.0) for j in range(4) if w[v, j]] for v in range(n_v)]
        uv = np.array(struct.unpack_from("<%df" % (2 * n_v), data, uv_at + 8 * first_v)).reshape(-1, 2)
        tris = np.array(struct.unpack_from("<%dH" % n_idx, data, u(s + 0x40)), np.int64).reshape(-1, 3) - first_v
        subs.append(dict(crc=u(s + 0xC), pos=pos, normal=normal, uv=uv, tris=tris, weights=weights))
    return dict(subs=subs, rows=rows, inv=inv)


_TEXT_UP = np.array([0.0, 0.0, 1.0])
_TEXT_BACK = np.array([0.0, 1.0, 0.0])
_surface_cache = {}


def surface(target, name, shape):
    """Per texel of one texture, from the suit meshes that use it (sub-mesh crc = crc32 of the texture stem): the
    outward normal, the 3D position and the texture-pixel vectors pointing right and up on the suit as seen from
    outside (their length is pixels per world unit). Texels shared by parts that disagree, such as mirrored left and
    right pieces on the same UVs, come back unusable."""
    key = (target, name, shape)
    if key in _surface_cache:
        return _surface_cache[key]
    import zlib
    import ds1_dlc_build as b
    members = b.read_archive(b.WORK / "pc" / target)
    # the sub-mesh crc is the material's short name, which mostly equals the texture stem (not on level 5:
    # isaacl5helmet for isaaclevel5helmet_c)
    crcs = {zlib.crc32(name[:-2].encode()) & 0xFFFFFFFF}
    for m in members:
        if m.attrs["type_name"] == "Material" and name in b.material_samplers(m.data()).values():
            crcs.add(b.crc_lower(b.short_name(m.data())))
    h, w = shape
    # normal 3, position 3, right 2, up 2, right dir 2, up dir 2, count 1, shading normal 3
    acc = np.zeros((h, w, 18), dtype=np.float32)
    for m in members:
        if m.attrs["type_name"] != "Mesh" or "hit" in m.attrs["base_name"]:
            continue
        for sub in read_mesh(m.data())["subs"]:
            if sub["crc"] not in crcs:
                continue
            pos = np.asarray(sub["pos"], dtype=np.float64)
            nrm = np.asarray(sub["normal"], dtype=np.float64)
            uv = np.asarray(sub["uv"], dtype=np.float64)
            for t in sub["tris"]:
                t = [int(i) for i in t]
                # the legs sit in a tile next to the texture (u -1..0, v 1..2), the sampler wraps
                p, q = pos[t], (uv[t] - np.floor(uv[t].mean(0))) * (w, h)
                E = np.stack([p[1] - p[0], p[2] - p[0]], 1)
                Q = np.stack([q[1] - q[0], q[2] - q[0]], 1)
                if abs(np.linalg.det(Q)) < 1e-4:
                    continue
                n = np.cross(E[:, 0], E[:, 1])
                if np.linalg.norm(n) < 1e-12:
                    continue
                n /= np.linalg.norm(n)
                if n @ nrm[t].sum(0) < 0:
                    n = -n
                up = _TEXT_UP - (_TEXT_UP @ n) * n
                if np.linalg.norm(up) < 0.5:
                    up = _TEXT_BACK - (_TEXT_BACK @ n) * n
                up /= np.linalg.norm(up)
                right = np.cross(up, n)
                to_px = Q @ np.linalg.pinv(E)
                r, u = to_px @ right, to_px @ up
                x0, y0 = np.maximum(np.floor(q.min(0)).astype(int), 0)
                x1, y1 = np.minimum(np.ceil(q.max(0)).astype(int), (w, h))
                if x1 <= x0 or y1 <= y0:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5 - q[0, 0], np.arange(y0, y1) + 0.5 - q[0, 1])
                inv = np.linalg.inv(Q)
                l1 = inv[0, 0] * gx + inv[0, 1] * gy
                l2 = inv[1, 0] * gx + inv[1, 1] * gy
                inside = (l1 >= -0.02) & (l2 >= -0.02) & (l1 + l2 <= 1.02)
                if not inside.any():
                    continue
                ys, xs = np.nonzero(inside)
                P = p[0] + l1[inside][:, None] * E[:, 0] + l2[inside][:, None] * E[:, 1]
                rest = np.concatenate([r, u, r / np.linalg.norm(r), u / np.linalg.norm(u), [1.0]])
                vn = nrm[t]
                S = vn[0] + l1[inside][:, None] * (vn[1] - vn[0]) + l2[inside][:, None] * (vn[2] - vn[0])
                S /= np.maximum(np.linalg.norm(S, axis=1, keepdims=True), 1e-9)
                vals = np.concatenate([np.broadcast_to(n, (len(ys), 3)), P, np.broadcast_to(rest, (len(ys), 9)), S], 1)
                acc[ys + y0, xs + x0] += vals.astype(np.float32)
    cnt = acc[..., 14]
    c = np.maximum(cnt, 1)[..., None]
    N = acc[..., 0:3] / c
    agree = (np.linalg.norm(N, axis=-1) > 0.97) & (np.linalg.norm(acc[..., 10:12] / c, axis=-1) > 0.95) & \
        (np.linalg.norm(acc[..., 12:14] / c, axis=-1) > 0.95)
    N = N / np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-9)
    S = acc[..., 15:18]
    S = S / np.maximum(np.linalg.norm(S, axis=-1, keepdims=True), 1e-9)
    res = dict(ok=(cnt > 0) & agree, covered=cnt > 0, N=N, S=S, P=acc[..., 3:6] / c, R=acc[..., 6:8] / c,
               U=acc[..., 8:10] / c)
    _surface_cache[key] = res
    return res


def cut(rgb, box):
    """(colour, alpha) of the gold emblem in the box; stray scratches away from it are dropped."""
    x0, y0, x1, y1 = box
    crop = rgb[y0:y1, x0:x1].astype(np.float64)
    r, g = crop[..., 0], crop[..., 1]
    gold = np.clip((g / np.maximum(r, 1) - 0.45) * 5, 0, 1) * np.clip((r - 110) / 60, 0, 1)
    lab, count = ndimage.label(ndimage.binary_dilation(gold > 0.5, iterations=2))
    if count:
        gold *= lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1
    return crop, gold


def basis(normal):
    """In-plane axes of a decal: e2 the model's up laid onto the plane, e1 across."""
    e2 = UP - (UP @ normal) * normal
    if np.linalg.norm(e2) < 0.2:
        e2 = np.array([0.0, 0.0, 1.0]) - normal[2] * normal
    e2 /= np.linalg.norm(e2)
    return np.cross(e2, normal), e2


def density_of(surf):
    return np.median((np.linalg.norm(surf["R"], axis=-1) + np.linalg.norm(surf["U"], axis=-1))[surf["covered"]] / 2)


def decal(style, retail_rgb):
    """The emblem on the level 5 model: centre, normal, a search tree over its texels in upright plane coordinates
    with their colours and alphas, its radius and the texel spacing there."""
    if style in _cache:
        return _cache[style]
    _, base_name, box = EMBLEMS[style]
    colour, alpha = cut(retail_rgb, box)
    surf = surface(BASE_TARGET, base_name, retail_rgb.shape[:2])
    x0, y0, x1, y1 = box
    covered = surf["covered"][y0:y1, x0:x1]
    P, N = surf["P"][y0:y1, x0:x1][covered], surf["N"][y0:y1, x0:x1][covered]
    a, c = alpha[covered], colour[covered]
    weight = a[:, None] + 1e-6
    centre = (P * weight).sum(0) / weight.sum()
    normal = (N * weight).sum(0)
    normal /= np.linalg.norm(normal)
    e1, e2 = basis(normal)
    flat = np.stack([(P - centre) @ e1, (P - centre) @ e2], 1)
    radius = np.linalg.norm(flat[a > 0.3], axis=1).max() if (a > 0.3).any() else 0.0
    _cache[style] = dict(centre=centre, normal=normal, tree=cKDTree(flat), colour=c, alpha=a,
                         spacing=1.0 / density_of(surf), radius=radius)
    return _cache[style]


def helmet_points(target, name):
    """Sample points on every part of the meshes that use this texture (bars and frames included), for the test
    whether something sits in front of a spot."""
    import ds1_dlc_build as b
    members = b.read_archive(b.WORK / "pc" / target)
    crcs = {zlib.crc32(name[:-2].encode()) & 0xFFFFFFFF}
    for m in members:
        if m.attrs["type_name"] == "Material" and name in b.material_samplers(m.data()).values():
            crcs.add(b.crc_lower(b.short_name(m.data())))
    weights = np.array([(i, j, 6 - i - j) for i in range(7) for j in range(7 - i)], dtype=np.float64) / 6
    points = []
    for m in members:
        if m.attrs["type_name"] != "Mesh" or "hit" in m.attrs["base_name"]:
            continue
        subs = read_mesh(m.data())["subs"]
        if not any(s["crc"] in crcs for s in subs):
            continue
        for s in subs:
            pos = np.asarray(s["pos"], dtype=np.float64)
            tris = np.asarray(s["tris"], dtype=np.int64)
            if len(tris):
                points.append(np.einsum("tvk,sv->tsk", pos[tris], weights).reshape(-1, 3))
    return np.concatenate(points) if points else np.zeros((0, 3))


def clean_texels(surf, paint):
    """Texels an emblem may cover: paint on one unmirrored part, away from seams where the model jumps. Folds are
    left to the curvature test in place(): the helmets' smooth plates are split by shading seams that do not show."""
    P = surf["P"]
    density = (np.linalg.norm(surf["R"], axis=-1) + np.linalg.norm(surf["U"], axis=-1)) / 2
    good = surf["ok"] & (paint > 0.5)
    cut = np.zeros_like(good)
    for axis in (0, 1):
        a, b = [slice(None)] * 2, [slice(None)] * 2
        a[axis], b[axis] = slice(None, -1), slice(1, None)
        a, b = tuple(a), tuple(b)
        bad = np.linalg.norm(P[a] - P[b], axis=-1) * np.maximum(density[a], density[b]) > 3
        cut[a] |= bad
        cut[b] |= bad
    good &= ~cut
    # paint specks and scratch lines would make every spot look crowded
    good = ndimage.binary_opening(ndimage.binary_closing(good, iterations=2), iterations=1) & surf["ok"]
    return good


def place(style, target, name, paint, retail_rgb, report):
    """(centre, normal, scale, region label map, region id) of the cleanest spot on this helmet, or None."""
    d = decal(style, retail_rgb)
    surf = surface(target, name, paint.shape)
    good = clean_texels(surf, paint)
    density = density_of(surf)
    room = ndimage.distance_transform_edt(good) / density          # world distance to the next unclean texel
    regions, _ = ndimage.label(good)
    want, smallest = d["radius"], d["radius"] * MIN_SCALE
    ys, xs = np.nonzero(room > smallest * 1.05)
    if not len(ys):
        report.append("%s %s: no clean spot for the emblem" % (target, name))
        return None
    S = surf["S"]
    # one candidate per few texels, the roomiest first
    order = np.argsort(-room[ys, xs])
    ys, xs = ys[order][::3][:600], xs[order][::3][:600]
    occluders = helmet_points(target, name)
    tree = cKDTree(surf["P"][good])
    good_normals = S[good]
    best = None
    for y, x in zip(ys, xs):
        c = surf["P"][y, x]
        near = tree.query_ball_point(c, want * 1.3)
        n = good_normals[near].sum(0)
        n /= np.linalg.norm(n)
        if n @ d["normal"] < -0.2:
            continue   # the far half of the helmet
        r = min(room[y, x], want)
        # something of the helmet in front of the spot (a bar, a frame)
        rel = occluders - c
        depth = rel @ n
        lateral = np.linalg.norm(rel - depth[:, None] * n, axis=1)
        front = (depth > 0.004) & (depth < 0.1)
        if front.any():
            r = min(r, lateral[front].min() - d["spacing"] * 2)
        # curvature: normals under the emblem stay close to its own
        pts = surf["P"][good][near]
        turned = good_normals[near] @ n < np.cos(MAX_TURN)
        if turned.any():
            off = pts[turned] - c
            r = min(r, np.linalg.norm(off - (off @ n)[:, None] * n, axis=1).min())
        if r < smallest:
            continue
        # bigger wins; among nearly equal sizes the spot nearer the retail one's side and direction
        score = r / want + 0.15 * (n @ d["normal"]) - 0.5 * np.linalg.norm(c - d["centre"])
        if best is None or score > best[0]:
            best = (score, c, n, r / want, regions[y, x])
    if best is None:
        report.append("%s %s: no clean spot for the emblem" % (target, name))
        return None
    _, c, n, scale, region = best
    report.append("%s %s: emblem at %s, normal %s, %.0f %% of the retail size"
                  % (target, name, np.round(c, 3).tolist(), np.round(n, 2).tolist(), scale * 100))
    return c, n, scale, regions, region


def paint(out, style, target, name, retail_rgb, where=None, report=None):
    """Paint the style's emblem onto `out` (H x W x 3 float), the colour map `name` of `target`, at the cleanest
    spot of the paint `where` (0..1). Returns the number of texels painted."""
    if target == BASE_TARGET:
        return 0   # the retail suit carries it already
    report = [] if report is None else report
    d = decal(style, retail_rgb)
    paint_mask = where if where is not None else np.ones(out.shape[:2])
    spot = place(style, target, name, paint_mask, retail_rgb, report)
    if spot is None or not d["radius"]:
        return 0
    c, n, scale, regions, region = spot
    surf = surface(target, name, out.shape[:2])
    e1, e2 = basis(n)
    ys, xs = np.nonzero(regions == region)
    rel = surf["P"][ys, xs] - c
    flat = np.stack([rel @ e1, rel @ e2], 1) / scale
    # the clean region may wrap round the helmet: only its side facing the decal
    inside = (np.linalg.norm(flat, axis=1) < d["radius"] * 1.2) & (np.abs(rel @ n) < d["radius"] * scale * 0.8)
    ys, xs, flat = ys[inside], xs[inside], flat[inside]
    dist, idx = d["tree"].query(flat, k=4)
    w = 1.0 / np.maximum(dist, 1e-9)
    w[dist > d["spacing"] * 2.5] = 0
    total = w.sum(1)
    keep = total > 0
    ys, xs, idx = ys[keep], xs[keep], idx[keep]
    w = w[keep] / total[keep, None]
    wa = d["alpha"][idx] * w
    a = wa.sum(1)
    # colour from the emblem's own texels only, so its edge does not pick up the red around it
    col = (d["colour"][idx] * wa[..., None]).sum(1) / np.maximum(a, 1e-9)[:, None]
    if where is not None:
        a = a * where[ys, xs]
    out[ys, xs] = out[ys, xs] * (1 - a[:, None]) + col * a[:, None]
    return int((a > 0.3).sum())
