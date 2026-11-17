"""Inflate the puffer shell with Blender's cloth solver instead of a radius formula.

A closed sphere is pinned along every stitch line (and the flat zip placket), given a few
percent of slack fabric, and pumped up with internal pressure. The free panels balloon
between the pins, so the baffles come out uneven and the slack gathers into real
tension wrinkles at the seams.

    blender -b --factory-startup -P blender/puffer_cloth.py -- preview [pressure] [shrink]

renders a quick clay preview to blender/_renders/cloth-preview.png for tuning.
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402
import puffer_v2 as p2  # noqa: E402

R0 = 0.945  # seam radius: pinned vertices stay here


def pin_weights(d):
    f = p2.fields(d)
    seam = np.minimum(f["d_band"], np.where(f["theta"] > p2.THETA_TOP, f["d_panel"], 9.0))
    w = (seam < 0.013).astype(float)
    w[np.abs(f["lon"]) < 0.075] = 1.0  # zip placket stays flat
    w[f["t"] < 0] = 1.0  # shoulders under the collar
    w[f["theta"] > p2.THETA_BOTTOM + 0.01] = 1.0  # hem
    return w


def simulate(segments=256, rings=144, pressure=100.0, shrink=-0.10, frames=40, stiffness=40.0, bending=0.3, preshape=True):
    obj = c.uv_sphere("Puffer", radius=R0, segments=segments, rings=rings)
    me = obj.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    d = co.reshape(-1, 3) / R0
    w = pin_weights(d)
    if preshape:
        # Start from the formula shape so the spare fabric runs across the baffles only.
        me.vertices.foreach_set("co", (d * p2.radius(d)[:, None]).ravel())
        me.update()
    vg = obj.vertex_groups.new(name="pin")
    for i, wi in enumerate(w):
        if wi > 0:
            vg.add([i], float(wi), "REPLACE")

    mod = obj.modifiers.new("Cloth", "CLOTH")
    s = mod.settings
    s.quality = 8
    s.mass = 0.15
    s.tension_stiffness = stiffness
    s.compression_stiffness = stiffness
    s.shear_stiffness = stiffness * 0.5
    s.bending_stiffness = bending  # higher = fewer, larger folds
    s.tension_damping = 5
    s.air_damping = 2.0
    s.shrink_min = shrink  # negative = extra fabric to gather
    print(f"shrink_min set {shrink} -> {s.shrink_min}", flush=True)
    s.vertex_group_mass = "pin"
    s.pin_stiffness = 1.0
    s.use_pressure = True
    s.uniform_pressure_force = pressure
    s.effector_weights.gravity = 0.0
    mod.collision_settings.use_collision = False
    mod.collision_settings.use_self_collision = False
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, frames
    for fr in range(1, frames + 1):
        scene.frame_set(fr)
        if fr % 10 == 0:
            print(f"cloth frame {fr}/{frames}", flush=True)

    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev)
    obj.modifiers.clear()
    old = obj.data
    obj.data = new
    bpy.data.meshes.remove(old)
    obj.vertex_groups.clear()
    return obj


def surface_lookup(obj):
    """radius1(v) replacement: distance from the centre to the simulated surface along v."""
    bvh = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())
    from mathutils import Vector

    def radius1(v):
        v = Vector(v).normalized()
        hit = bvh.ray_cast(v * 1.5, -v)
        return (hit[0].length if hit[0] is not None else R0)
    return radius1


def preview(pressure, shrink, out, stiffness=40.0, bending=0.3, preshape=True):
    c.reset()
    obj = simulate(segments=192, rings=108, pressure=pressure, shrink=shrink, frames=30, stiffness=stiffness, bending=bending, preshape=preshape)
    c.smooth(obj, 180)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = scene.render.resolution_y = 640
    cam = bpy.data.cameras.new("cam")
    cam.angle = math.radians(30)
    co = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(co)
    co.location = (0, -5.4, 0)
    co.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = co
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    vs = np.zeros(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", vs)
    r = np.linalg.norm(vs.reshape(-1, 3), axis=1)
    print(f"PREVIEW pressure={pressure} shrink={shrink} k={stiffness} r min={r.min():.3f} max={r.max():.3f} mean={r.mean():.3f}")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if args and args[0] == "preview":
        pr = float(args[1]) if len(args) > 1 else 6.0
        sh = float(args[2]) if len(args) > 2 else -0.05
        st = float(args[3]) if len(args) > 3 else 40.0
        bd = float(args[4]) if len(args) > 4 else 0.3
        tag = f"p{pr}_s{sh}_k{st}_b{bd}"
        preview(pr, sh, os.path.join(c.ROOT, "blender", "_renders", f"cloth-{tag}.png"), st, bd)
