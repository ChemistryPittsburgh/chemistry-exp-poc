"""Puffer-jacket ball: quilted baffles, zipper with real teeth, stand collar, welt pockets.

High-res displaced sphere is baked (normal + AO) onto a lighter mesh for realtime.
"""

import math

import bmesh
from mathutils import Vector, noise

import common as c

THETA_TOP = 0.2 * math.pi
THETA_BOTTOM = 0.97 * math.pi
BANDS = 8
BAND_H = (THETA_BOTTOM - THETA_TOP) / BANDS
PANELS = 4
POCKETS = [((0.38, -0.66), (0.62, -0.5)), ((-0.38, -0.66), (-0.62, -0.5))]  # (lon, lat) segments


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def radius(d, detail=True):
    theta = math.acos(max(-1.0, min(1.0, d.z)))
    lon = math.atan2(d.x, -d.y)
    t = (theta - THETA_TOP) / BAND_H
    local = t - math.floor(t)
    band = 0.0 if t < 0 else math.sin(math.pi * local) ** 0.38
    s = ((lon / math.tau) * PANELS) % 1.0
    panel = math.sin(math.pi * s) ** 0.3
    puff = band * (0.45 + 0.55 * panel)
    # Flatter placket either side of the zipper so the zip area reads wider.
    x = max(0.0, min(1.0, (abs(lon) - 0.07) / 0.09))
    puff *= 0.25 + 0.75 * x * x * (3 - 2 * x)
    r = 0.95 + 0.05 * puff
    if detail:
        pinch = (1 - band) ** 2
        # Fabric gathers into wrinkles that radiate from each stitch line.
        r += 0.005 * pinch * math.sin(lon * 70 + theta * 7 + 2 * noise.noise(d * 6))
        r += 0.0025 * noise.noise(d * 9) * band
        lat = math.pi / 2 - theta
        for a, b in POCKETS:
            dist = seg_dist((lon, lat), a, b)
            if dist < 0.02:
                r -= 0.012 * (1 - dist / 0.02) ** 2
    return r


def collar_profile():
    pts = [(0.38, 0.74), (0.37, 0.9), (0.39, 0.98), (0.44, 1.0), (0.49, 0.95), (0.54, 0.8), (0.555, 0.72)]
    # Catmull-Rom through the points for a soft, padded edge.
    out = []
    for i in range(len(pts) - 1):
        p0 = Vector(pts[max(i - 1, 0)])
        p1 = Vector(pts[i])
        p2 = Vector(pts[i + 1])
        p3 = Vector(pts[min(i + 2, len(pts) - 1)])
        for k in range(12):
            t = k / 12
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((v.x, v.y))
    out.append(pts[-1])
    return out


def zipper_path():
    """Points (Vector) from the collar top down the front seam, with outward normals."""
    prof = collar_profile()
    path = []
    top = max(range(len(prof)), key=lambda i: prof[i][1])
    for r, z in prof[top:]:
        if z < 0.76:
            break
        path.append((Vector((0, -(r + 0.006), z)), Vector((0, -1, 0.15)).normalized()))
    steps = 240
    for i in range(steps + 1):
        theta = THETA_TOP + 0.05 + (THETA_BOTTOM - 0.07 - THETA_TOP) * i / steps
        d = Vector((0, -math.sin(theta), math.cos(theta)))
        path.append((d * (radius(d, detail=False) + 0.004), d))
    return path


def resample(path, spacing):
    out = [path[0]]
    acc = 0.0
    for (p0, n0), (p1, n1) in zip(path, path[1:]):
        seg = (p1 - p0).length
        while acc + seg >= spacing:
            t = (spacing - acc) / seg
            p0 = p0.lerp(p1, t)
            n0 = n0.lerp(n1, t).normalized()
            seg = (p1 - p0).length
            acc = 0.0
            out.append((p0.copy(), n0.copy()))
        acc += seg
    return out


def add_box(bm, center, x, y, z, sx, sy, sz):
    corners = []
    for dx in (-1, 1):
        for dy in (-1, 1):
            for dz in (-1, 1):
                corners.append(bm.verts.new(center + x * (dx * sx) + y * (dy * sy) + z * (dz * sz)))
    idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for f in idx:
        bm.faces.new([corners[i] for i in f])


def build_zipper():
    pts = resample(zipper_path(), 0.0105)
    teeth = bmesh.new()
    tape = bmesh.new()
    left, right = [], []
    for i, (p, n) in enumerate(pts):
        nxt = pts[min(i + 1, len(pts) - 1)][0]
        prv = pts[max(i - 1, 0)][0]
        t = (nxt - prv).normalized()
        side = t.cross(n).normalized()
        n = side.cross(t).normalized()
        offset = 0.009 if i % 2 else -0.009
        add_box(teeth, p + side * offset + n * 0.005, side, t, n, 0.014, 0.0038, 0.0052)
        for sign, row in ((-1, left), (1, right)):
            q = p + side * (0.058 * sign)
            if q.z < 0.74:  # on the body: hug the quilted surface
                d = q.normalized()
                q = d * (radius(d, detail=False) + 0.004)
            row.append(tape.verts.new(q))
    for i in range(len(pts) - 1):
        tape.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    bmesh.ops.recalc_face_normals(teeth, faces=teeth.faces)
    teeth_obj = c.obj_from_bm("ZipperTeeth", teeth)
    tape_obj = c.obj_from_bm("ZipperTape", tape)

    # Slider + pull tab at the collar.
    hw = bmesh.new()
    p, n = pts[2]
    t = (pts[3][0] - pts[1][0]).normalized()
    side = t.cross(n).normalized()
    n = side.cross(t).normalized()
    add_box(hw, p + n * 0.016, side, t, n, 0.028, 0.035, 0.012)
    add_box(hw, p + n * 0.03 + t * 0.075, side, t, n, 0.016, 0.055, 0.005)
    bmesh.ops.recalc_face_normals(hw, faces=hw.faces)
    hw_obj = c.obj_from_bm("ZipperPull", hw)
    c.bevel(hw_obj, width=0.004, segments=2)
    return teeth_obj, tape_obj, hw_obj


def build():
    c.reset()
    nylon = dict(color=c.srgb("#1d2ab8"), rough=0.5, coat=0.3, coat_rough=0.38,
                 sheen=0.25, sheen_tint=c.srgb("#9fb0ff"), sheen_rough=0.35)

    high = c.uv_sphere("PufferHigh", segments=768, rings=384, displace=lambda d: radius(d, True))
    low = c.uv_sphere("Puffer", segments=176, rings=96, displace=lambda d: radius(d, False))
    c.smooth(high, 180)
    c.smooth(low, 180)
    body_mat = c.principled("Nylon", **nylon)
    c.assign(low, body_mat)
    c.assign(high, c.principled("NylonHigh", **nylon))

    collar = c.lathe("Collar", collar_profile() + [(0.38, 0.74)], steps=176)
    c.smooth(collar, 50)
    c.assign(collar, c.principled("NylonCollar", **nylon))

    neck = c.lathe("NeckHole", [(0.0, 0.86), (0.39, 0.86)], steps=64)
    c.assign(neck, c.principled("NeckDark", color=c.srgb("#05061a"), rough=1.0))

    teeth, tape, pull = build_zipper()
    c.assign(teeth, c.principled("ZipTeeth", color=c.srgb("#18181b"), rough=0.3, metal=0.8))
    c.assign(tape, c.principled("ZipTape", color=c.srgb("#0b0b10"), rough=0.6))
    c.assign(pull, c.principled("ZipPull", color=c.srgb("#1b1b1f"), rough=0.22, metal=0.9))
    c.smooth(teeth, 30)

    snaps = []
    for (a, b) in POCKETS:
        lon, lat = b
        d = c.dir_from_lonlat(lon, lat)
        s = c.lathe("Snap", [(0.0, 0.012), (0.018, 0.01), (0.024, 0.0), (0.024, -0.01)], steps=32)
        c.orient_to(s, d, radius(d, False) - 0.004)
        c.apply_transform(s)
        c.assign(s, c.principled("Snap", color=c.srgb("#2a2a30"), rough=0.25, metal=0.9))
        snaps.append(s)

    # Bake fine detail (stitch lines, wrinkles, pocket welts) and AO onto the realtime body.
    normal = c.bpy.data.images.new("puffer_normal", 2048, 1024, alpha=False)
    normal.colorspace_settings.name = "Non-Color"
    c.bake(low, normal, "NORMAL", sources=[high], extrusion=0.03, samples=8)
    c.use_normal_map(body_mat, normal)
    c.bpy.data.objects.remove(high, do_unlink=True)

    ao = c.bpy.data.images.new("puffer_ao", 1024, 512, alpha=False)
    ao.colorspace_settings.name = "Non-Color"
    c.bpy.context.scene.world = c.bpy.data.worlds.new("World")
    c.bpy.context.scene.world.light_settings.distance = 0.25
    c.bake(low, ao, "AO", samples=96)
    c.use_occlusion(body_mat, ao)

    c.export_glb("puffer", [low, collar, neck, teeth, tape, pull, *snaps])


if __name__ == "__main__":
    build()
