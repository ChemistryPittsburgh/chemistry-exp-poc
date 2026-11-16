"""Tennis ball with a graffiti smiley.

Textures are computed with numpy straight onto the equirect UVs:
- base colour: mottled felt + ink face
- fur mask: 0 in the seam groove so runtime fur shells don't cover the rubber seam
A low-res "FurShell" mesh is exported for the runtime shell fur (see src/models.js).
"""

import math

import bpy
import numpy as np
from mathutils import Vector, kdtree, noise

import common as c

W, H = 2048, 1024
K = 0.27  # seam shape


def seam_points(n=900):
    pts = []
    s = 2 * math.sqrt(K * (1 - K))
    for i in range(n):
        t = i / n * math.tau
        x = (1 - K) * math.cos(t) + K * math.cos(3 * t)
        y = (1 - K) * math.sin(t) - K * math.sin(3 * t)
        z = s * math.sin(2 * t)
        pts.append(Vector((x, z, y)))  # lobes cross the face horizontally
    # Tilt so the seam swoops across the lower face like the reference.
    from mathutils import Euler
    rot = Euler((0.35, 0.0, 0.25)).to_matrix()
    return [rot @ p for p in pts]


def polyline(points, step=0.01):
    out = []
    for a, b in zip(points, points[1:]):
        a, b = c.dir_from_lonlat(*a), c.dir_from_lonlat(*b)
        n = max(2, int((a - b).length / step))
        for i in range(n):
            out.append(a.lerp(b, i / n).normalized())
    return out


STROKES = [
    # (points in (lon, lat), half-width)
    ([(-0.36, 0.66), (-0.33, 0.48), (-0.37, 0.34), (-0.32, 0.2)], 0.07),  # left eye
    ([(0.2, 0.62), (0.24, 0.45), (0.19, 0.3), (0.23, 0.16)], 0.07),  # right eye
    ([(-0.95, 0.38), (-1.0, 0.12), (-0.86, -0.12), (-0.62, -0.2), (-0.45, -0.16), (-0.38, -0.33),
      (-0.18, -0.4), (0.12, -0.37), (0.42, -0.3), (0.66, -0.17), (0.8, 0.02), (0.82, 0.3), (0.7, 0.47)], 0.042),
    ([(-0.36, 0.2), (-0.38, 0.08)], 0.025),  # drips
    ([(0.23, 0.16), (0.25, 0.02)], 0.022),
    ([(-0.42, -0.33), (-0.44, -0.5)], 0.035),  # tongue
]


def build_textures():
    lon, lat = c.lonlat_grid(W, H)
    dirs = c.dirs_from_grid(lon, lat).reshape(-1, 3)

    rng = np.random.default_rng(7)
    felt = np.array(c.srgb("#c9de2e"))
    base = np.tile(felt, (H * W, 1))
    # Low-frequency mottling (value noise via mathutils on a coarse grid, upsampled).
    cw, ch = 256, 128
    clon, clat = c.lonlat_grid(cw, ch)
    cd = c.dirs_from_grid(clon, clat).reshape(-1, 3)
    mott = np.array([noise.fractal(Vector(d * 4.0), 1.0, 2.0, 4) for d in cd]).reshape(ch, cw)
    mott = np.kron(mott, np.ones((H // ch, W // cw))).reshape(-1)
    base *= (1 + 0.16 * mott)[:, None]
    base *= (1 + 0.08 * (rng.random(H * W) - 0.5))[:, None]

    # Ink: distance to each stroke, with ragged spray-paint edges.
    face = (np.abs(lon) < 1.25).reshape(-1) & (np.abs(lat) < 0.95).reshape(-1)
    idx = np.nonzero(face)[0]
    fd = dirs[idx]
    rag = np.array([noise.noise(Vector(d * 18.0)) for d in fd])
    ink = np.zeros(len(idx))
    for pts, half in STROKES:
        line = np.array(polyline(pts))
        best = np.full(len(idx), 9.0)
        for p in line:
            dist = np.linalg.norm(fd - p, axis=1)
            np.minimum(best, dist, out=best)
        edge = half * (1 + 0.45 * rag)
        ink = np.maximum(ink, np.clip((edge - best) / 0.006, 0, 1))
    ink_col = np.array(c.srgb("#262622"))
    base[idx] = base[idx] * (1 - ink[:, None]) + ink_col * ink[:, None]

    # Seam groove distance (KD tree over the seam polyline).
    seam = seam_points()
    kd = kdtree.KDTree(len(seam))
    for i, p in enumerate(seam):
        kd.insert(p, i)
    kd.balance()
    sd = np.array([kd.find(Vector(d))[2] for d in dirs])
    groove = np.clip((sd - 0.026) / 0.02, 0, 1)
    base *= (0.55 + 0.45 * groove)[:, None]

    rgba = np.concatenate([np.clip(base, 0, 1), np.ones((H * W, 1))], axis=1).reshape(H, W, 4)
    base_img = c.image_from_array("tennis_base", rgba)

    mask = np.repeat(groove[:, None], 3, axis=1)
    mask = np.concatenate([mask, np.ones((H * W, 1))], axis=1).reshape(H, W, 4)
    mask_img = c.image_from_array("tennis_fur_mask", mask[::2, ::2].copy(), non_color=True)
    return base_img, mask_img, seam


def build():
    c.reset()
    base_img, mask_img, seam = build_textures()

    core = c.uv_sphere("TennisCore", segments=128, rings=64)
    c.smooth(core, 180)
    mat = c.principled("Felt", rough=1.0, sheen=1.0, sheen_tint=c.srgb("#efff8a"), sheen_rough=0.45)
    c.use_base_color(mat, base_img)
    c.assign(core, mat)

    shell = c.uv_sphere("FurShell", segments=64, rings=32)
    c.smooth(shell, 180)
    fur = c.principled("Fur", rough=1.0)
    c.use_base_color(fur, base_img)
    c.assign(shell, fur)

    cu = bpy.data.curves.new("Seam", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.021
    cu.bevel_resolution = 3
    sp = cu.splines.new("POLY")
    sp.points.add(len(seam) - 1)
    for p, v in zip(sp.points, seam):
        p.co = (*(v * 1.016), 1)
    sp.use_cyclic_u = True
    tmp = c.link(bpy.data.objects.new("SeamCurve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    seam_obj = c.link(bpy.data.objects.new("Seam", bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))))
    bpy.data.objects.remove(tmp, do_unlink=True)
    c.smooth(seam_obj, 180)
    c.assign(seam_obj, c.principled("SeamRubber", color=c.srgb("#ddd9bd"), rough=0.62))

    c.export_glb("tennis", [core, shell, seam_obj])

    mask_img.filepath_raw = c.os.path.join(c.OUT_DIR, "tennis-fur-mask.webp")
    mask_img.file_format = "WEBP"
    bpy.context.scene.render.image_settings.quality = 90
    mask_img.save()


if __name__ == "__main__":
    build()
