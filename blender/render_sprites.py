"""Render 360-degree turntable frames of each sphere GLB with Cycles.

    blender -b --factory-startup -P blender/render_sprites.py -- [frames] [size] [ids...]

Defaults: 72 frames (5-degree steps), 640 px, all four spheres.
Frames land in blender/_renders/<id>/0000.png; tools/pack_sprites.py builds the sheets.
The tennis ball gets real particle hair here instead of the runtime shell fur.
"""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402

# Same hero poses as src/models.js, converted from three.js (Y-up) to Blender (Z-up).
POSES = {
    "puffer": (0.05, 0.0, 0.0),
    "tennis": (0.0, 0.0, 0.0),
    "eightball": (0.0, 0.0, 0.0),
    "robot": (0.04, 0.0, -0.55),
}

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FRAMES = int(args[0]) if args else 72
SIZE = int(args[1]) if len(args) > 1 else 640
IDS = args[2:] or ["puffer", "tennis", "eightball", "robot"]
RENDER_DIR = os.path.join(c.ROOT, "blender", "_renders")


def scene_setup():
    sc = bpy.context.scene
    c.setup_cycles(samples=32)
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 16
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Khronos PBR Neutral"

    world = bpy.data.worlds.new("Studio")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    hdr = os.path.join(bpy.utils.system_resource("DATAFILES"), "studiolights", "world", "studio.exr")
    env.image = bpy.data.images.load(hdr)
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 0.7
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])

    # Key (upper left, front) and rim (upper right, behind), like the realtime stage.
    for name, loc, power, size in (("Key", (-3, -4, 4), 420, 3.0), ("Rim", (3.5, 3, 2), 320, 2.5)):
        light = bpy.data.lights.new(name, "AREA")
        light.energy = power
        light.size = size
        ob = c.link(bpy.data.objects.new(name, light))
        ob.location = loc
        direction = -ob.location.normalized()
        ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.angle = math.radians(30)
    cam = c.link(bpy.data.objects.new("Cam", cam_data))
    cam.location = (0, -5.4, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam


def add_tennis_fur(objects):
    core = next((o for o in objects if o.name.startswith("TennisCore")), None)
    shell = next((o for o in objects if o.name.startswith("FurShell")), None)
    if shell:
        shell.hide_render = True
    if core is None:
        return
    # Density from the seam mask so no felt grows on the rubber seam.
    mask = bpy.data.images.load(os.path.join(c.OUT_DIR, "tennis-fur-mask.webp"))
    mw, mh = mask.size
    px = list(mask.pixels)
    vg = core.vertex_groups.new(name="fur")
    uv = core.data.uv_layers.active.data
    weights = {}
    for loop in core.data.loops:
        u, v = uv[loop.index].uv
        x = min(int(u % 1 * mw), mw - 1)
        y = min(int(v % 1 * mh), mh - 1)
        weights[loop.vertex_index] = px[(y * mw + x) * 4]
    for vi, w in weights.items():
        vg.add([vi], w, "REPLACE")

    mod = core.modifiers.new("Fur", "PARTICLE_SYSTEM")
    ps = mod.particle_system
    ps.vertex_group_density = "fur"
    st = ps.settings
    st.type = "HAIR"
    st.count = 70000
    st.hair_length = 0.03
    st.use_advanced_hair = True
    st.child_type = "INTERPOLATED"
    st.rendered_child_count = 12
    st.child_radius = 0.02
    st.roughness_1 = 0.006
    st.roughness_2 = 0.006
    st.roughness_endpoint = 0.004
    st.root_radius = 1.0
    st.tip_radius = 0.0
    st.radius_scale = 0.0011
    st.render_step = 3
    st.hair_step = 3
    st.use_hair_bspline = True

    base = core.active_material
    tex = next(n for n in base.node_tree.nodes if n.type == "TEX_IMAGE")
    hair = bpy.data.materials.new("Felt Hair")
    hair.use_nodes = True
    nt = hair.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Sheen Weight"].default_value = 0.6
    uvnode = nt.nodes.new("ShaderNodeUVMap")
    uvnode.from_instancer = True
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = tex.image
    nt.links.new(uvnode.outputs["UV"], img.inputs["Vector"])
    lift = nt.nodes.new("ShaderNodeHueSaturation")
    lift.inputs["Value"].default_value = 1.9
    lift.inputs["Hue"].default_value = 0.475  # nudge green toward tennis-ball yellow
    lift.inputs["Saturation"].default_value = 0.92
    nt.links.new(img.outputs["Color"], lift.inputs["Color"])
    nt.links.new(lift.outputs["Color"], bsdf.inputs["Base Color"])
    core.data.materials.append(hair)
    # Lift the felt under the hair too, so gaps between strands don't read as dark.
    bnt = base.node_tree
    core_lift = bnt.nodes.new("ShaderNodeHueSaturation")
    core_lift.inputs["Value"].default_value = 1.45
    core_lift.inputs["Hue"].default_value = 0.475
    link = next(l for l in bnt.links if l.from_node == tex)
    bnt.links.new(tex.outputs["Color"], core_lift.inputs["Color"])
    bnt.links.new(core_lift.outputs["Color"], link.to_socket)
    st.material_slot = hair.name


def render_model(model_id):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene_setup()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(c.OUT_DIR, f"{model_id}.glb"))
    imported = [o for o in bpy.data.objects if o not in before]

    turntable = c.link(bpy.data.objects.new("Turntable", None))
    pose = c.link(bpy.data.objects.new("Pose", None))
    pose.parent = turntable
    pose.rotation_euler = POSES.get(model_id, (0, 0, 0))
    for o in imported:
        if o.parent is None:
            o.parent = pose
    if model_id == "tennis":
        add_tennis_fur(imported)

    out = os.path.join(RENDER_DIR, model_id)
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    for i in range(FRAMES):
        turntable.rotation_euler = (0, 0, -math.tau * i / FRAMES)
        sc.render.filepath = os.path.join(out, f"{i:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {model_id} {i + 1}/{FRAMES}", flush=True)


for mid in IDS:
    render_model(mid)
