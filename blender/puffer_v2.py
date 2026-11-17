"""Puffer jacket ball, realism pass (exports models/puffer-v2.glb).

What changes from puffer.py, and why it reads less like plastic:
- Surface detail is computed analytically into a 4096x2048 normal map instead of baked
  from a 300k-face mesh, so it can go much finer: crinkled nylon creases everywhere,
  compression wrinkles radiating from every seam, a stitch groove with stitch holes.
- Down fill is uneven: baffles loft by different amounts, so no two puffs match.
- A roughness map breaks up the sheen (creases and seams are duller than the puffs).
- Garment cues: hanging zipper pull, storm-flap edges, elastic hem binding, chest patch.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import common as c
from puffer import add_box, collar_profile, resample

THETA_TOP = 0.2 * math.pi
THETA_BOTTOM = 0.94 * math.pi
BANDS = 8
BAND_H = (THETA_BOTTOM - THETA_TOP) / BANDS
PANELS = 4
POCKETS = [((0.38, -0.62), (0.62, -0.47)), ((-0.38, -0.62), (-0.62, -0.47))]  # (lon, lat)
PATCH = (0.36, 0.32)  # (lon, lat) of the chest patch, wearer's left
W, H = 4096, 2048


# ---------------------------------------------------------------------------
# Vectorised gradient noise (numpy), so textures can be computed per texel
# ---------------------------------------------------------------------------

class Perlin:
    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        p = rng.permutation(256)
        self.p = np.concatenate([p, p]).astype(np.int64)
        g = rng.normal(size=(256, 3))
        self.g = g / np.linalg.norm(g, axis=1, keepdims=True)

    def __call__(self, P):
        P = np.asarray(P, dtype=np.float64)
        i0 = np.floor(P).astype(np.int64)
        f = P - i0
        i0 &= 255
        u = f * f * f * (f * (f * 6 - 15) + 10)
        p, g = self.p, self.g
        out = 0.0
        vals = {}
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    h = p[p[p[i0[:, 0] + dx] + i0[:, 1] + dy] + i0[:, 2] + dz]
                    off = f - np.array([dx, dy, dz])
                    vals[dx, dy, dz] = np.einsum("ij,ij->i", g[h], off)
        lerp = lambda a, b, t: a + (b - a) * t
        x00 = lerp(vals[0, 0, 0], vals[1, 0, 0], u[:, 0])
        x10 = lerp(vals[0, 1, 0], vals[1, 1, 0], u[:, 0])
        x01 = lerp(vals[0, 0, 1], vals[1, 0, 1], u[:, 0])
        x11 = lerp(vals[0, 1, 1], vals[1, 1, 1], u[:, 0])
        y0 = lerp(x00, x10, u[:, 1])
        y1 = lerp(x01, x11, u[:, 1])
        out = lerp(y0, y1, u[:, 2])
        return out


N_LUMP = Perlin(11)
N_WARP = Perlin(12)
N_SEAMW = Perlin(13)
N_CRINK = Perlin(14)
N_ROUGH = Perlin(15)


def fbm(noise, P, octaves, lac=2.03, gain=0.5):
    total, amp, norm = 0.0, 1.0, 0.0
    for _ in range(octaves):
        total = total + amp * noise(P)
        norm += amp
        P = P * lac + 17.1
        amp *= gain
    return total / norm


def polar(d):
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    theta = np.arccos(np.clip(z, -1, 1))
    lon = np.arctan2(x, -y)
    return theta, lon


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

def fields(d):
    """Quilting fields for directions d (N, 3)."""
    theta, lon = polar(d)
    # Seams dip a little toward the zip, like a real chevron quilt.
    theta_e = theta + 0.045 * np.cos(lon) - 0.02
    t = (theta_e - THETA_TOP) / BAND_H
    local = t - np.floor(t)
    band = np.where(t < 0, 0.0, np.sin(np.pi * local) ** 0.38)
    s = ((lon / math.tau) * PANELS) % 1.0
    panel = np.sin(np.pi * s) ** 0.3
    # Arc distance (radians) to the nearest horizontal / vertical seam.
    d_band = np.minimum(local, 1 - local) * BAND_H
    d_band = np.where(t < 0, -t * BAND_H, d_band)
    d_panel = np.minimum(s, 1 - s) * (math.tau / PANELS) * np.maximum(np.sin(theta), 0.05)
    return dict(theta=theta, lon=lon, t=t, band=band, panel=panel, d_band=d_band, d_panel=d_panel)


def radius(d):
    """Low-frequency silhouette (goes in the mesh)."""
    f = fields(d)
    lump = 1 + 0.32 * fbm(N_LUMP, d * 2.2, 2)  # uneven down fill
    puff = f["band"] * (0.45 + 0.55 * f["panel"]) * lump
    x = np.clip((np.abs(f["lon"]) - 0.07) / 0.09, 0, 1)
    puff *= 0.25 + 0.75 * x * x * (3 - 2 * x)  # flatter placket either side of the zip
    return 0.945 + 0.056 * puff


def radius1(v):
    return float(radius(np.array([[v.x, v.y, v.z]]))[0])


def detail_height(d):
    """Fine surface detail (normal map only), in the same units as the radius."""
    f = fields(d)
    theta, lon = f["theta"], f["lon"]
    db, dp = f["d_band"], f["d_panel"]
    h = np.zeros(len(d))

    # Compression wrinkles: fabric gathered by the stitching forms short ridges that run
    # away from each seam. Noise sampled on a stretched cylinder: fast across the seam
    # direction, slow along the wrinkle.
    warp = 0.6 * N_WARP(d * 5.0)
    cyl_b = np.stack([np.cos(lon) * 9.0, np.sin(lon) * 9.0, theta * 2.2 + warp], axis=1)
    rib_b = np.abs(fbm(N_SEAMW, cyl_b, 2))
    fall_b = np.exp(-db / 0.06)
    h -= 0.007 * fall_b * rib_b

    cyl_p = np.stack([np.cos(lon) * 1.2 + warp, np.sin(lon) * 1.2, theta * 30.0], axis=1)
    rib_p = np.abs(fbm(N_SEAMW, cyl_p + 40.0, 2))
    fall_p = np.exp(-dp / 0.045) * (theta > THETA_TOP)
    h -= 0.005 * fall_p * rib_p

    # Nylon crinkle: sharp creases (|noise| valleys) all over, finer on the tight areas.
    crink = np.abs(fbm(N_CRINK, d * 22.0 + warp[:, None] * 0.3, 3))
    micro = np.abs(N_CRINK(d * 70.0 + 5.0))
    h += 0.003 * crink + 0.0007 * micro

    # Stitch line: a narrow pinched groove with stitch holes every ~5 mm.
    seam = np.minimum(db, np.where(theta > THETA_TOP, dp, 9.0))
    along = np.where(db < dp, lon * np.sin(theta), theta)
    groove = np.exp(-(seam / 0.004) ** 2)
    holes = 0.5 + 0.5 * np.cos(along * (math.tau / 0.016))
    h -= 0.0035 * groove * (0.6 + 0.4 * holes)

    # Pocket welts: a sunken slit with a raised lip.
    lat = math.pi / 2 - theta
    for (a0, b0), (a1, b1) in POCKETS:
        ax, ay, bx, by = a0, b0, a1, b1
        dx, dy = bx - ax, by - ay
        tt = np.clip(((lon - ax) * dx + (lat - ay) * dy) / (dx * dx + dy * dy), 0, 1)
        dist = np.hypot(lon - ax - tt * dx, lat - ay - tt * dy)
        h -= 0.01 * np.exp(-(dist / 0.007) ** 2)
        h += 0.003 * np.exp(-((dist - 0.018) / 0.008) ** 2)
    return h, f


def chunked(fn, d, n=400_000):
    outs = [fn(d[i:i + n]) for i in range(0, len(d), n)]
    return outs


def build_maps():
    lon, lat = c.lonlat_grid(W, H)
    dirs = c.dirs_from_grid(lon, lat).reshape(-1, 3)
    heights, rough = [], []
    for i in range(0, len(dirs), 400_000):
        d = dirs[i:i + 400_000]
        h, f = detail_height(d)
        heights.append(h)
        # Roughness: puffs are glossier where the fabric is taut; creases, seams and
        # gathered areas scatter more light.
        seam = np.exp(-np.minimum(f["d_band"], f["d_panel"]) / 0.03)
        r = 0.3 + 0.12 * seam + 0.05 * fbm(N_ROUGH, d * 6.0, 2) + 0.06 * (1 - f["band"])
        rough.append(np.clip(r, 0.18, 0.6))
        print(f"maps {i * 100 // len(dirs)}%", flush=True)
    height = np.concatenate(heights).reshape(H, W)
    rough = np.concatenate(rough).reshape(H, W)

    dlon = 2 * math.pi / W
    dlat = math.pi / H
    coslat = np.maximum(np.cos(lat), 0.05)
    dh_east = np.gradient(height, axis=1) / (dlon * coslat)
    dh_north = np.gradient(height, axis=0) / dlat
    n = np.stack([-dh_east, -dh_north, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    nrgba = np.concatenate([n * 0.5 + 0.5, np.ones((H, W, 1))], axis=-1)
    normal_img = c.image_from_array("puffer2_normal", nrgba, non_color=True)

    # glTF metallicRoughness: G = roughness, B = metallic (0). Half res is plenty.
    r2 = rough[::2, ::2]
    mr = np.stack([np.ones_like(r2), r2, np.zeros_like(r2), np.ones_like(r2)], axis=-1)
    rough_img = c.image_from_array("puffer2_rough", mr, non_color=True)
    return normal_img, rough_img


def use_roughness(mat, image):
    nt = mat.node_tree
    n = c.tex_node(mat, image, non_color=True, location=(-700, 0))
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-400, 0)
    nt.links.new(n.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], nt.nodes["Principled BSDF"].inputs["Roughness"])


# ---------------------------------------------------------------------------
# Hardware and trims
# ---------------------------------------------------------------------------

def zipper_path():
    prof = collar_profile()
    path = []
    top = max(range(len(prof)), key=lambda i: prof[i][1])
    for r, z in prof[top:]:
        if z < 0.76:
            break
        path.append((Vector((0, -(r + 0.006), z)), Vector((0, -1, 0.15)).normalized()))
    steps = 260
    for i in range(steps + 1):
        theta = THETA_TOP + 0.05 + (THETA_BOTTOM + 0.02 - THETA_TOP) * i / steps
        d = Vector((0, -math.sin(theta), math.cos(theta)))
        path.append((d * (radius1(d) + 0.004), d))
    return path


def build_zipper():
    pts = resample(zipper_path(), 0.0105)
    teeth, tape, flap = bmesh.new(), bmesh.new(), bmesh.new()
    left, right, fl, fr = [], [], [], []
    for i, (p, n) in enumerate(pts):
        nxt = pts[min(i + 1, len(pts) - 1)][0]
        prv = pts[max(i - 1, 0)][0]
        t = (nxt - prv).normalized()
        side = t.cross(n).normalized()
        n = side.cross(t).normalized()
        offset = 0.009 if i % 2 else -0.009
        add_box(teeth, p + side * offset + n * 0.005, side, t, n, 0.014, 0.0038, 0.0052)
        for sign, row, frow in ((-1, left, fl), (1, right, fr)):
            q = p + side * (0.03 * sign)
            e = p + side * (0.05 * sign) + n * 0.006
            if q.z < 0.74:
                d = q.normalized()
                q = d * (radius1(d) + 0.002)
                d = e.normalized()
                e = d * (radius1(d) + 0.006)
            row.append(tape.verts.new(q))
            frow.append((q, e))
    for i in range(len(pts) - 1):
        tape.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    # Storm-flap edges: a folded nylon lip either side of the zip.
    for frow in (fl, fr):
        vs = [(flap.verts.new(a), flap.verts.new(b)) for a, b in frow]
        for i in range(len(vs) - 1):
            flap.faces.new((vs[i][0], vs[i][1], vs[i + 1][1], vs[i + 1][0]))
    bmesh.ops.recalc_face_normals(teeth, faces=teeth.faces)
    teeth_obj = c.obj_from_bm("ZipperTeeth", teeth)
    tape_obj = c.obj_from_bm("ZipperTape", tape)
    flap_obj = c.obj_from_bm("StormFlap", flap)
    sol = flap_obj.modifiers.new("Thick", "SOLIDIFY")
    sol.thickness = 0.006
    sol.offset = 0
    c.apply_modifiers(flap_obj)

    # Slider at the collar, pull tab hanging down over the chest.
    p, n = pts[3]
    t = (pts[4][0] - pts[2][0]).normalized()
    side = t.cross(n).normalized()
    n = side.cross(t).normalized()
    slider = bmesh.new()
    add_box(slider, p + n * 0.014, side, t, n, 0.022, 0.03, 0.01)
    bmesh.ops.recalc_face_normals(slider, faces=slider.faces)
    slider_obj = c.obj_from_bm("ZipSlider", slider)
    c.bevel(slider_obj, width=0.006, segments=3)

    outline = c.rounded_rect(0.028, 0.085, 0.012, 0.026, n=10)
    hole = c.rounded_rect(0.008, 0.016, 0.006, 0.006, n=6)
    tab = c.prism("ZipPull", outline, -0.004, 0.004)
    cut = c.prism("ZipPullHole", [(x, z + 0.05) for x, z in hole], -0.02, 0.02)
    c.boolean(tab, cut)
    from mathutils import Matrix
    c.bevel(tab, width=0.002, segments=2)
    # Tab built in XZ with Y thickness: face the viewer, hang from the slider and lean out
    # to follow the collar's flare.
    anchor = Vector((0.0, -0.5, 0.965))
    tab.data.transform(Matrix.Translation((0, 0, -0.082)))
    tab.matrix_world = Matrix.Translation(anchor) @ Matrix.Rotation(-0.42, 4, "X")
    c.apply_transform(tab)
    return teeth_obj, tape_obj, flap_obj, slider_obj, tab


def build_patch():
    """Small rubberised patch on the chest, curved to sit on the puff."""
    from mathutils import Matrix
    outline = c.rounded_rect(0.07, 0.032, 0.01, 0.01, n=8)
    patch = c.prism("ChestPatch", outline, -0.004, 0.004)
    bm = bmesh.new()
    bm.from_mesh(patch.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=6, use_grid_fill=True)
    bm.to_mesh(patch.data)
    bm.free()
    lon, lat = PATCH
    dctr = c.dir_from_lonlat(lon, lat)
    f = c.frame(dctr)
    X, Y, N = f.col[0].xyz, f.col[1].xyz, f.col[2].xyz
    for v in patch.data.vertices:
        x, depth, z = v.co
        d = (N + X * x + Y * z).normalized()
        v.co = d * (radius1(d) + 0.0025 - depth * 0.5)
    c.bevel(patch, width=0.0015, segments=2, angle_deg=40)
    return patch


def build_collar():
    """Stand collar: nylon outer wall with a rolled top edge, dark lining inside, a
    topstitch line under the fold and a bead seam where it joins the body. The outer wall
    gets a little fabric irregularity so it stops reading as a turned bowl."""
    prof = collar_profile()
    top = max(range(len(prof)), key=lambda i: prof[i][1])
    outer = c.lathe("Collar", prof[top:], steps=192, merge_axis=False)
    inner = c.lathe("CollarLining", prof[:top + 1], steps=192, merge_axis=False)
    me = outer.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    radial = co.copy()
    radial[:, 2] = 0
    rn = radial / np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-6)
    wob = 0.006 * fbm(N_LUMP, co * 5.0 + 3.0, 2) + 0.0025 * np.abs(N_SEAMW(np.stack(
        [co[:, 0] * 3.0, co[:, 1] * 3.0, co[:, 2] * 26.0], axis=1)))
    fade = np.clip((co[:, 2] - 0.72) / 0.06, 0, 1) * np.clip((1.0 - co[:, 2]) / 0.03, 0, 1)
    co += rn * (wob * fade)[:, None]
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    c.smooth(outer, 180)
    c.smooth(inner, 180)

    def outer_r(z):
        pts = prof[top:]
        for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
            if z1 <= z <= z0:
                return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
        return pts[-1][0]

    stitch = c.torus("CollarStitch", outer_r(0.93) + 0.004, 0.0022, steps=192, ring=8, z=0.93)
    bead = c.torus("CollarBead", outer_r(0.735) + 0.004, 0.011, steps=192, ring=12, z=0.735)
    trim = c.join([stitch, bead], "CollarTrim")
    c.smooth(trim, 180)
    return outer, inner, trim


def build_hem():
    """Elastic binding round the bottom opening, plus a dark inner lining."""
    theta0 = THETA_BOTTOM + 0.005
    r0 = math.sin(theta0) * radius1(Vector((0, -math.sin(theta0), math.cos(theta0))))
    z0 = math.cos(theta0)
    prof = []
    for i in range(13):
        a = math.pi * i / 12
        prof.append((r0 + 0.016 * math.sin(a) - 0.006, z0 - 0.02 + 0.04 * (i / 12) + 0.004 * math.cos(a)))
    hem = c.lathe("HemBinding", prof, steps=176, merge_axis=False)
    c.smooth(hem, 180)
    lining = c.lathe("HemLining", [(0.0, z0 + 0.03), (r0 - 0.004, z0 + 0.01)], steps=96)
    return hem, lining


def build():
    c.reset()
    normal_img, rough_img = build_maps()

    nylon = dict(color=c.srgb("#1b28b8"), rough=0.3, sheen=0.35, sheen_tint=c.srgb("#9fb0ff"), sheen_rough=0.3)

    # Shell: inflated with the cloth solver (see puffer_cloth.py), then every trim that sits
    # on the body looks up the simulated surface instead of the radius formula.
    global radius1
    import puffer_cloth
    body = puffer_cloth.simulate(segments=224, rings=128, pressure=25.0, shrink=-0.02, frames=40)
    radius1 = puffer_cloth.surface_lookup(body)
    c.smooth(body, 180)
    body_mat = c.principled("Nylon", **nylon)
    c.use_normal_map(body_mat, normal_img, strength=1.0)
    use_roughness(body_mat, rough_img)
    c.assign(body, body_mat)

    collar, collar_in, collar_trim = build_collar()
    c.assign(collar, c.principled("NylonCollar", **nylon))
    lining = c.principled("Lining", color=c.srgb("#0b0d26"), rough=0.85, sheen=0.3, sheen_tint=c.srgb("#3a4590"))
    c.assign(collar_in, lining)
    c.assign(collar_trim, c.principled("NylonSeam", **dict(nylon, rough=0.45)))

    neck = c.lathe("NeckHole", [(0.0, 0.955), (0.392, 0.955)], steps=64)  # covers the body cap
    c.assign(neck, c.principled("NeckDark", color=c.srgb("#05061a"), rough=0.95))

    teeth, tape, flap, slider, tab = build_zipper()
    c.assign(teeth, c.principled("ZipTeeth", color=c.srgb("#141416"), rough=0.35, metal=0.0, coat=0.5))
    c.assign(tape, c.principled("ZipTape", color=c.srgb("#0b0b10"), rough=0.75))
    c.assign(flap, c.principled("NylonFlap", **nylon))
    c.smooth(flap, 40)
    metal = c.principled("ZipMetal", color=c.srgb("#3a3a40"), rough=0.28, metal=1.0)
    c.assign(slider, metal)
    c.assign(tab, c.principled("ZipPullRubber", color=c.srgb("#111114"), rough=0.55))
    c.smooth(teeth, 30)

    hem, lining = build_hem()
    c.assign(hem, c.principled("Elastic", color=c.srgb("#121640"), rough=0.8, sheen=0.5, sheen_tint=c.srgb("#6070c0")))
    c.assign(lining, c.principled("Lining2", color=c.srgb("#0a0b1e"), rough=0.9))

    patch = build_patch()
    c.assign(patch, c.principled("Patch", color=c.srgb("#0e0f14"), rough=0.6))

    snaps = []
    for (a, b) in POCKETS:
        lon, lat = b
        dv = c.dir_from_lonlat(lon, lat)
        s = c.lathe("Snap", [(0.0, 0.01), (0.014, 0.008), (0.019, 0.0), (0.019, -0.01)], steps=32)
        c.orient_to(s, dv, radius1(dv) - 0.003)
        c.apply_transform(s)
        c.assign(s, metal)
        snaps.append(s)

    ao = c.bpy.data.images.new("puffer2_ao", 1024, 512, alpha=False)
    ao.colorspace_settings.name = "Non-Color"
    c.bpy.context.scene.world = c.bpy.data.worlds.new("World")
    c.bpy.context.scene.world.light_settings.distance = 0.3
    c.bake(body, ao, "AO", samples=128)
    c.use_occlusion(body_mat, ao)

    c.export_glb("puffer-v2", [body, collar, collar_in, collar_trim, neck, teeth, tape, flap, slider, tab, hem, lining, patch, *snaps])


if __name__ == "__main__":
    build()
