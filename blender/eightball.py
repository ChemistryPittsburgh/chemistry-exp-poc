"""Magic 8-ball: lacquered shell, deep liquid-filled window, floating answer die, "8" circle.

All glyphs are real geometry so they stay crisp at any size; no transmission needed.
The die is its own node ("Die", with the "Message" text parented to it) resting just under
the glass, so the runtime can sink it into the murk and float it back up like a real 8-ball.
"""

import math

import bmesh
from mathutils import Vector

import common as c

WINDOW_DIR = Vector((0.42, -0.8, 0.42)).normalized()  # up-right-front (Blender coords)
EIGHT_DIR = Vector((-0.66, -0.6, -0.45)).normalized()  # lower-left
CAP = 0.5
DEPTH = 0.3  # deep well: the die rises from the murk at the bottom
REST = 0.1  # die rests this far below the window opening
LABEL_ANGLE = 0.456  # number circle radius ~0.44 R, like a real pool ball


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

    # --- "8" circle: pool-ball proportions, flush on the lacquer ----------------
    r = math.tan(LABEL_ANGLE)
    label = c.lathe("Label", [(r * i / 16, 0.0) for i in range(17)], steps=128)
    c.wrap_to_sphere(label, EIGHT_DIR, 1.0015, subdivide=1)
    c.face_out(label)
    c.assign(label, c.principled("LabelWhite", color=c.srgb("#f1efe8"), rough=0.2, coat=1.0, coat_rough=0.03))

    eight = c.text_mesh("Eight", "8", size=0.8, depth=0.0)
    c.wrap_to_sphere(eight, EIGHT_DIR, 1.0032, roll=-0.3, subdivide=3)
    c.face_out(eight)
    c.assign(eight, c.principled("Ink", color=c.srgb("#0a0a0a"), rough=0.25, coat=1.0, coat_rough=0.03))

    # --- Window internals (built along +Z, then aligned) ---------------------
    win = c.frame(WINDOW_DIR)

    liquid = c.lathe("Liquid", [(0.0, floor + 0.004), (rho * 0.97, floor + 0.004)], steps=96)
    liquid.data.transform(win)
    c.face_out(liquid, WINDOW_DIR)
    c.assign(liquid, c.principled("Liquid", color=c.srgb("#02030c"), rough=0.35,
                                  emission=c.srgb("#0b1c7a"), strength=0.12))

    # Murky layer just under the resting die: anything below it reads as deep in the liquid.
    murk = c.lathe("Murk", [(0.0, y0 - REST - 0.016), (rho * 0.995, y0 - REST - 0.016)], steps=96)
    murk.data.transform(win)
    c.face_out(murk, WINDOW_DIR)
    c.assign(murk, c.principled("Murk", color=c.srgb("#01030b"), rough=0.3, alpha=0.88,
                                emission=c.srgb("#0a1866"), strength=0.08))

    die = die_mesh()
    die.data.transform(_translate((0, 0.02, 0)))
    die.matrix_world = win @ _translate((0, 0, y0 - REST))
    c.assign(die, c.principled("Die", color=c.srgb("#0a1a8a"), rough=0.45,
                               emission=c.srgb("#1e3cff"), strength=1.2))

    msg = c.text_mesh("Message", "Data\nRitual\nComplete", size=0.066, depth=0.0, spacing=0.9)
    msg.data.transform(_translate((0, 0.075, 0.038)))
    c.face_out(msg, (0, 0, 1))
    msg.parent = die
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

    c.export_glb("eightball", [body, label, eight, liquid, murk, die, msg, bezel, lens])


def _translate(v):
    from mathutils import Matrix
    return Matrix.Translation(Vector(v))


if __name__ == "__main__":
    build()
