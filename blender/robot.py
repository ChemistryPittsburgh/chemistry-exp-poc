"""Robot pod: warm-grey shell, solid glossy visor with gasket, ring eyes, glowing ear ring.

Mesh names Eye_L / Eye_R / EarRing are animated at runtime (blink, pulse).
"""

import math

import bmesh

from mathutils import Matrix, Vector

import common as c

EAR_DIR = Vector((1.0, -0.05, 0.02)).normalized()  # +X side
CAP = 0.62
DEPTH = 0.06


def visor_part(name, radius, hw, hh, r_top, r_bottom, thickness, z_center=0.05):
    shell = c.uv_sphere(name, radius=radius, segments=160, rings=96)
    cutter = c.prism(name + "Cut", c.rounded_rect(hw, hh, r_top, r_bottom, n=20), 0.2, -1.6,
                     center=(0, z_center))
    c.boolean(shell, cutter, op="INTERSECT")
    # Keep only the outer skin (faces on the sphere); drop the prism walls inside it.
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    inner = [f for f in bm.faces if any(abs(v.co.length - radius) > 1e-3 for v in f.verts)]
    bmesh.ops.delete(bm, geom=inner, context="FACES")
    bm.to_mesh(shell.data)
    bm.free()
    mod = shell.modifiers.new("solid", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = -1
    mod.use_even_offset = True
    c.apply_modifiers(shell)
    c.bevel(shell, width=thickness * 0.35, segments=3, angle_deg=40)
    c.smooth(shell, 40)
    return shell


def build():
    c.reset()
    grey = c.principled("Shell", color=c.srgb("#7d746e"), rough=0.46, metal=0.12, coat=0.3, coat_rough=0.35)

    body, rho, y0, floor = c.recessed_sphere("Robot", CAP, DEPTH, rim_fillet=0.04, floor_fillet=0.02)
    body.data.transform(c.frame(EAR_DIR))
    c.smooth(body, 60)
    c.assign(body, grey)

    ear = c.frame(EAR_DIR)
    dome = c.lathe("EarDome", [(rho * 0.8, floor), (rho * 0.79, floor + 0.03), (rho * 0.6, floor + 0.045),
                               (rho * 0.3, floor + 0.052), (0.0, floor + 0.054)], steps=128)
    dome.data.transform(ear)
    c.face_out(dome, EAR_DIR)
    c.smooth(dome, 50)
    c.assign(dome, c.principled("EarFace", color=c.srgb("#857c76"), rough=0.4, metal=0.15, coat=0.4))

    ring = c.torus("EarRing", rho * 0.86, 0.016, steps=160, ring=12, z=floor + 0.022)
    ring.data.transform(ear)
    c.smooth(ring, 180)
    c.assign(ring, c.principled("EarGlow", color=(1, 1, 1), rough=0.3,
                                emission=c.srgb("#d6f1ff"), strength=4.0))

    gasket = visor_part("Gasket", 1.012, 0.69, 0.5, 0.3, 0.37, 0.02)
    c.assign(gasket, c.principled("Gasket", color=c.srgb("#1e1c1b"), rough=0.55))
    visor = visor_part("Visor", 1.03, 0.66, 0.47, 0.27, 0.34, 0.03)
    c.assign(visor, c.principled("Visor", color=c.srgb("#040404"), rough=0.06, coat=1.0, coat_rough=0.02))

    eyes = []
    for side, lon in (("L", -0.2), ("R", 0.2)):
        d = c.dir_from_lonlat(lon, -0.02)
        eye = c.torus("Eye_" + side, 0.062, 0.011, steps=64, ring=10)
        eye.matrix_world = Matrix.Translation(d * 1.032) @ c.frame(d)  # kept as a node transform for blinking
        c.smooth(eye, 180)
        c.assign(eye, c.principled("EyeGlow_" + side, color=(1, 1, 1), rough=0.3,
                                   emission=c.srgb("#e4f4ff"), strength=5.0))
        eyes.append(eye)

    c.smart_uv(body)
    c.bake_ao(body, size=1024, samples=128, distance=0.3)

    c.export_glb("robot", [body, dome, ring, gasket, visor, *eyes])


if __name__ == "__main__":
    build()
