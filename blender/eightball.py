"""Magic 8-ball: lacquered shell, recessed window, glowing answer die, wrapped "8" label.

All glyphs are real geometry so they stay crisp at any size; no transmission needed.
"""

import math

import bmesh
from mathutils import Vector

import common as c

WINDOW_DIR = Vector((0.42, -0.8, 0.42)).normalized()  # up-right-front (Blender coords)
EIGHT_DIR = Vector((-0.66, -0.6, -0.45)).normalized()  # lower-left
CAP = 0.5
DEPTH = 0.16


def local(obj, n, roll=0.0):
    obj.data.transform(c.frame(n, roll))


def die_mesh(side=0.56, depth=0.035):
    h = side * math.sqrt(3) / 2
    tri = [(-side / 2, h / 3), (side / 2, h / 3), (0.0, -2 * h / 3)]  # apex down
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, 0.0)) for x, y in tri]
    top = [bm.verts.new((x, y, depth)) for x, y in tri]
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(3):
        j = (i + 1) % 3
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = c.obj_from_bm("Die", bm)
    c.bevel(ob, width=0.018, segments=3, angle_deg=20)
    c.smooth(ob, 35)
    return ob


def build():
    c.reset()

    body, rho, y0, floor = c.recessed_sphere("EightBall", CAP, DEPTH, rim_fillet=0.03)
    local(body, WINDOW_DIR)
    c.smooth(body, 60)
    lacquer = c.principled("Lacquer", color=c.srgb("#070707"), rough=0.18, coat=1.0, coat_rough=0.03)
    c.assign(body, lacquer)

    # --- "8" label ----------------------------------------------------------
    label = c.lathe("Label", [(0.0, 0.0), (0.205, 0.0)], steps=96)
    c.wrap_to_sphere(label, EIGHT_DIR, 1.0015, subdivide=6)
    c.face_out(label)
    c.assign(label, c.principled("LabelWhite", color=c.srgb("#efede6"), rough=0.2, coat=1.0, coat_rough=0.03))

    eight = c.text_mesh("Eight", "8", size=0.34, depth=0.0)
    c.wrap_to_sphere(eight, EIGHT_DIR, 1.0032, roll=-0.35, subdivide=3)
    c.face_out(eight)
    c.assign(eight, c.principled("Ink", color=c.srgb("#0a0a0a"), rough=0.25, coat=1.0, coat_rough=0.03))

    # --- Window internals (built along +Z, then aligned) ---------------------
    win = c.frame(WINDOW_DIR)

    liquid = c.lathe("Liquid", [(0.0, floor + 0.004), (rho * 0.97, floor + 0.004)], steps=96)
    liquid.data.transform(win)
    c.face_out(liquid, WINDOW_DIR)
    c.assign(liquid, c.principled("Liquid", color=c.srgb("#02030c"), rough=0.35,
                                  emission=c.srgb("#0b1c7a"), strength=0.6))

    die = die_mesh()
    die.data.transform(win @ _translate((0, 0.02, floor + 0.02)))
    c.assign(die, c.principled("Die", color=c.srgb("#0a1a8a"), rough=0.45,
                               emission=c.srgb("#1e3cff"), strength=1.2))

    msg = c.text_mesh("Message", "Data\nRitual\nComplete", size=0.066, depth=0.0, spacing=0.9)
    msg.data.transform(win @ _translate((0, 0.075, floor + 0.02 + 0.038)))
    c.face_out(msg, WINDOW_DIR)
    c.assign(msg, c.principled("MessageGlow", color=c.srgb("#dce8ff"), rough=0.5,
                               emission=c.srgb("#d6e4ff"), strength=5.0))

    bezel = c.torus("Bezel", rho, 0.014, steps=160, ring=12, z=y0 - 0.006)
    bezel.data.transform(win)
    c.smooth(bezel, 180)
    c.assign(bezel, c.principled("Bezel", color=c.srgb("#1a1a1c"), rough=0.22, metal=0.85))

    lens = c.lathe("Lens", [(math.sin(a), math.cos(a)) for a in [CAP * i / 12 for i in range(12, -1, -1)]], steps=96)
    lens.data.transform(win)
    c.face_out(lens)
    c.smooth(lens, 180)
    c.assign(lens, c.principled("Glass", color=(0.01, 0.012, 0.03), rough=0.02, alpha=0.3))

    c.smart_uv(body)
    c.bake_ao(body, size=1024, samples=128, distance=0.35)

    c.export_glb("eightball", [body, label, eight, liquid, die, msg, bezel, lens])


def _translate(v):
    from mathutils import Matrix
    return Matrix.Translation(Vector(v))


if __name__ == "__main__":
    build()
