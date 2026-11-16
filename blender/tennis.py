"""Tennis ball with a graffiti smiley, matched to the design render.

The face strokes and seam path are traced in the reference image's screen space
(reference/tennis.png, 332 px) and projected onto the sphere, so the front view
lines up with the original. The seam is a recessed channel: a normal-mapped groove
with cream rubber colour and no felt, rather than a raised tube.

Textures are computed with numpy straight onto the equirect UVs:
- base colour: mottled felt + ink face + cream groove
- normal map: the groove
- fur mask: 0 in the groove so fur (runtime shells / Cycles hair) doesn't fill it
A low-res "FurShell" mesh is exported for the runtime shell fur (see src/models.js).
"""

import math

import bpy
import numpy as np
from mathutils import Vector, kdtree, noise

import common as c

W, H = 2048, 1024
K = 0.27  # seam shape

# Reference image geometry (px): ball centre and radius.
CX, CY, R = 168.0, 169.0, 150.0

# Seam points read off the reference (visible parts of the two grooves).
REF_SEAM = [(100, 46), (150, 40), (200, 44), (250, 58), (290, 85),
            (38, 197), (90, 193), (140, 195), (185, 210), (215, 240), (235, 272)]

# Ink strokes traced from the reference: polylines of (x, y, half-width) in px.
# Per-point widths give the tapered, brushy look of the original.
STROKES = [
    [(114, 68, 4), (104, 84, 11), (115, 100, 9), (100, 116, 13), (113, 131, 10), (100, 146, 12), (106, 160, 5)],  # left eye
    [(172, 72, 4), (160, 88, 11), (175, 104, 10), (160, 120, 13), (176, 134, 10), (164, 148, 8), (170, 158, 4)],  # right eye
    [(62, 112, 3), (50, 128, 6), (41, 150, 8), (42, 170, 8), (55, 184, 7), (76, 191, 6), (92, 193, 4)],  # left hook
    [(92, 203, 4), (100, 222, 10), (110, 246, 14), (118, 264, 12), (130, 256, 9), (146, 243, 8)],  # drip
    [(146, 243, 8), (178, 240, 10), (208, 232, 11), (232, 214, 11), (248, 190, 10), (254, 168, 8),
     (248, 148, 6), (234, 132, 3)],  # grin
]


def screen_dir(x, y):
    """Reference pixel -> unit direction in Blender space (front = -Y, up = +Z)."""
    dx = (x - CX) / R
    dy = (CY - y) / R
    dz = math.sqrt(max(1 - dx * dx - dy * dy, 0.0))
    return np.array([dx, -dz, dy])


def base_seam(n=900):
    s = 2 * math.sqrt(K * (1 - K))
    t = np.linspace(0, math.tau, n, endpoint=False)
    x = (1 - K) * np.cos(t) + K * np.cos(3 * t)
    y = (1 - K) * np.sin(t) - K * np.sin(3 * t)
    z = s * np.sin(2 * t)
    return np.stack([x, y, z], axis=1)


def quat_to_mat(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def fit_seam():
    """Find the rotation that makes the parametric seam pass through REF_SEAM."""
    curve = base_seam()
    ref = np.array([screen_dir(x, y) for x, y in REF_SEAM])
    rng = np.random.default_rng(3)

    def score(q):
        pts = curve @ quat_to_mat(q).T
        d = np.linalg.norm(ref[:, None, :] - pts[None, :, :], axis=2).min(axis=1)
        return float(np.mean(d ** 2))

    best_q, best = None, 1e9
    for q in rng.normal(size=(6000, 4)):
        q /= np.linalg.norm(q)
        s = score(q)
        if s < best:
            best_q, best = q, s
    step = 0.15
    for i in range(4000):
        q = best_q + rng.normal(scale=step, size=4)
        q /= np.linalg.norm(q)
        s = score(q)
        if s < best:
            best_q, best = q, s
        if i % 500 == 499:
            step *= 0.6
    print(f"seam fit rms={math.sqrt(best):.4f}")
    return curve @ quat_to_mat(best_q).T


def stroke_points(points):
    """Densify a (x, y, half-width) polyline with a smooth Catmull-Rom pass."""
    pts = [np.array(p, dtype=float) for p in points]
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(i - 1, 0)], pts[i]
        p2, p3 = pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        n = max(2, int(np.hypot(*(p2 - p1)[:2])))
        for k in range(n):
            t = k / n
            v = 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            out.append(v)
    out.append(pts[-1])
    dirs = np.array([screen_dir(x, y) for x, y, _ in out])
    widths = np.array([w for _, _, w in out]) / R
    return dirs, widths


def build_textures(seam):
    lon, lat = c.lonlat_grid(W, H)
    dirs = c.dirs_from_grid(lon, lat).reshape(-1, 3)

    rng = np.random.default_rng(7)
    felt = np.array(c.srgb("#c9de2e"))
    base = np.tile(felt, (H * W, 1))
    cw, ch = 256, 128
    clon, clat = c.lonlat_grid(cw, ch)
    cd = c.dirs_from_grid(clon, clat).reshape(-1, 3)
    mott = np.array([noise.fractal(Vector(d * 4.0), 1.0, 2.0, 4) for d in cd]).reshape(ch, cw)
    mott = np.kron(mott, np.ones((H // ch, W // cw))).reshape(-1)
    base *= (1 + 0.16 * mott)[:, None]
    base *= (1 + 0.08 * (rng.random(H * W) - 0.5))[:, None]

    # Ink: only texels on the front hemisphere can be near a stroke.
    idx = np.nonzero(dirs[:, 1] < 0.2)[0]
    fd = dirs[idx]
    rag = np.array([noise.noise(Vector(d * 26.0)) for d in fd])
    ink = np.zeros(len(idx))
    for pts in STROKES:
        line, widths = stroke_points(pts)
        # Signed coverage: how far inside the nearest stamp of the brush each texel is.
        cover = np.full(len(idx), -9.0)
        for p, w in zip(line, widths):
            np.maximum(cover, w * (1 + 0.28 * rag) - np.linalg.norm(fd - p, axis=1), out=cover)
        ink = np.maximum(ink, np.clip(cover / 0.005, 0, 1))
    ink_col = np.array(c.srgb("#232320"))
    base[idx] = base[idx] * (1 - ink[:, None]) + ink_col * ink[:, None]

    # Seam groove: distance to the fitted seam curve.
    kd = kdtree.KDTree(len(seam))
    for i, p in enumerate(seam):
        kd.insert(Vector(p), i)
    kd.balance()
    sd = np.array([kd.find(Vector(d))[2] for d in dirs])

    HALF = 0.036
    cream = np.array(c.srgb("#e7e3c6"))
    core = 1 - np.clip((sd - 0.022) / 0.012, 0, 1)  # 1 in the channel
    lip = np.exp(-((sd - HALF) / 0.01) ** 2) * 0.25  # felt darkens where it folds into the groove
    base *= (1 - lip)[:, None]
    base = base * (1 - core[:, None]) + cream * core[:, None]
    rgba = np.concatenate([np.clip(base, 0, 1), np.ones((H * W, 1))], axis=1).reshape(H, W, 4)
    base_img = c.image_from_array("tennis_base", rgba)

    # Height field of a rounded U channel -> tangent-space normal map.
    depth = 0.022
    u = np.clip(sd / HALF, 0, 1)
    height = (-depth * (1 - u ** 2) ** 1.5).reshape(H, W)
    dlon = 2 * math.pi / W
    dlat = math.pi / H
    coslat = np.maximum(np.cos(lat), 0.08)
    dh_east = np.gradient(height, axis=1) / (dlon * coslat)
    dh_north = np.gradient(height, axis=0) / dlat
    n = np.stack([-dh_east, -dh_north, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    nrgba = np.concatenate([n * 0.5 + 0.5, np.ones((H, W, 1))], axis=-1)
    normal_img = c.image_from_array("tennis_normal", nrgba, non_color=True)

    groove = np.clip((sd - 0.03) / 0.012, 0, 1)
    mask = np.repeat(groove[:, None], 3, axis=1)
    mask = np.concatenate([mask, np.ones((H * W, 1))], axis=1).reshape(H, W, 4)
    mask_img = c.image_from_array("tennis_fur_mask", mask[::2, ::2].copy(), non_color=True)
    return base_img, normal_img, mask_img


def build():
    c.reset()
    seam = fit_seam()
    base_img, normal_img, mask_img = build_textures(seam)

    core = c.uv_sphere("TennisCore", segments=128, rings=64)
    c.smooth(core, 180)
    mat = c.principled("Felt", rough=1.0, sheen=1.0, sheen_tint=c.srgb("#efff8a"), sheen_rough=0.45)
    c.use_base_color(mat, base_img)
    c.use_normal_map(mat, normal_img, strength=1.0)
    c.assign(core, mat)

    shell = c.uv_sphere("FurShell", segments=64, rings=32)
    c.smooth(shell, 180)
    fur = c.principled("Fur", rough=1.0)
    c.use_base_color(fur, base_img)
    c.assign(shell, fur)

    c.export_glb("tennis", [core, shell])

    mask_img.filepath_raw = c.os.path.join(c.OUT_DIR, "tennis-fur-mask.webp")
    mask_img.file_format = "WEBP"
    bpy.context.scene.render.image_settings.quality = 90
    mask_img.save()


if __name__ == "__main__":
    build()
