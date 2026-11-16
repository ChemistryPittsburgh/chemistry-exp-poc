"""Shared helpers for the sphere build scripts (Blender 5.2, run headless).

Conventions
- Blender is Z-up; the glTF exporter converts to Y-up. Blender -Y becomes glTF +Z,
  which is the side that faces the Three.js camera, so -Y is "front" here.
- Equirect UVs: u = 0.5 + lon / 2pi (lon = 0 at front, + toward +X),
  v = 0.5 + lat / pi. The texture seam sits at the back.
"""

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "models")
TEX_DIR = os.path.join(ROOT, "blender", "_textures")  # bake scratch, gitignored


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def obj_from_bm(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


# ---------------------------------------------------------------------------
# Spherical coordinates
# ---------------------------------------------------------------------------

def dir_from_lonlat(lon, lat):
    """Unit vector; lon=0, lat=0 points at the front (-Y)."""
    return Vector((math.sin(lon) * math.cos(lat), -math.cos(lon) * math.cos(lat), math.sin(lat)))


def lonlat(v):
    v = v.normalized()
    return math.atan2(v.x, -v.y), math.asin(max(-1.0, min(1.0, v.z)))


def lonlat_grid(w, h):
    """Per-texel lon/lat arrays for an equirect image (row 0 = bottom, like Blender)."""
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    lon = (u - 0.5) * 2 * math.pi
    lat = (v - 0.5) * math.pi
    return np.meshgrid(lon, lat)


def dirs_from_grid(lon, lat):
    return np.stack(
        [np.sin(lon) * np.cos(lat), -np.cos(lon) * np.cos(lat), np.sin(lat)], axis=-1
    )


def uv_sphere(name, radius=1.0, segments=64, rings=32, displace=None):
    """UV sphere with equirect UVs. `displace(dir) -> radius` reshapes it."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    if displace:
        for vert in bm.verts:
            d = vert.co.normalized()
            vert.co = d * displace(d)
    set_equirect_uvs(bm)
    return obj_from_bm(name, bm)


def set_equirect_uvs(bm):
    uv = bm.loops.layers.uv.verify()
    for face in bm.faces:
        coords = []
        for loop in face.loops:
            lon, lat = lonlat(loop.vert.co)
            coords.append([0.5 + lon / (2 * math.pi), 0.5 + lat / math.pi, abs(lat) > 1.5707])
        # Fix wrap at the back seam.
        us = [c[0] for c in coords if not c[2]]
        if us and max(us) - min(us) > 0.5:
            for c in coords:
                if c[0] < 0.5:
                    c[0] += 1.0
        # Poles take the mean u of their face.
        if us:
            mean_u = sum(c[0] for c in coords if not c[2]) / len(us)
            for c in coords:
                if c[2]:
                    c[0] = mean_u
        for loop, c in zip(face.loops, coords):
            loop[uv].uv = (c[0], c[1])


# ---------------------------------------------------------------------------
# Mesh utilities
# ---------------------------------------------------------------------------

def lathe(name, profile, steps=128, merge_axis=True):
    """Spin a profile of (r, z) points around Z. Profile order sets normal direction."""
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(
        bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
        angle=math.tau, steps=steps, use_duplicate=False,
    )
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm)


def apply_modifiers(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)
    return obj


def apply_transform(obj):
    obj.data.transform(obj.matrix_world)
    obj.matrix_world.identity()


def smooth(obj, angle_deg=35.0):
    """Smooth shading with sharp edges above `angle_deg` (exported as split normals)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    limit = math.radians(angle_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if e.is_manifold:
            e.smooth = e.calc_face_angle(0.0) < limit
        else:
            e.smooth = True
    bm.to_mesh(obj.data)
    bm.free()


def boolean(obj, cutter, op="DIFFERENCE"):
    mod = obj.modifiers.new("bool", "BOOLEAN")
    mod.object = cutter
    mod.operation = op
    mod.solver = "EXACT"
    apply_modifiers(obj)
    cutter.hide_render = True
    bpy.data.objects.remove(cutter, do_unlink=True)


def bevel(obj, width=0.01, segments=3, angle_deg=30):
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle_deg)
    mod.harden_normals = False
    apply_modifiers(obj)


def text_mesh(name, body, size=0.2, depth=0.01, font="C:/Windows/Fonts/arialbd.ttf", align="CENTER", spacing=1.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = depth
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_line = spacing
    cu.resolution_u = 4
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    ob = link(bpy.data.objects.new(name + "_curve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    out = link(bpy.data.objects.new(name, me))
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return out


def orient_to(obj, direction, distance=0.0, spin=0.0):
    """Point the object's local +Z along `direction`, placed at `distance` from origin."""
    d = Vector(direction).normalized()
    q = Vector((0, 0, 1)).rotation_difference(d)
    obj.rotation_mode = "QUATERNION"
    from mathutils import Quaternion
    obj.rotation_quaternion = q @ Quaternion((0, 0, 1), spin)
    obj.location = d * distance


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def tri_count(objs):
    n = 0
    for o in objs:
        if o.type == "MESH":
            n += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return n


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def principled(name, color=(1, 1, 1), rough=0.5, metal=0.0, coat=0.0, coat_rough=0.03,
               sheen=0.0, sheen_tint=(1, 1, 1), sheen_rough=0.5, emission=None, strength=0.0,
               alpha=1.0, ior=1.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = coat_rough
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Tint"].default_value = (*sheen_tint, 1)
    bsdf.inputs["Sheen Roughness"].default_value = sheen_rough
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = "BLENDED"
    return mat


def srgb(hex_str):
    """'#rrggbb' -> linear RGB tuple (Blender colour sockets are linear)."""
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def tex_node(mat, image, non_color=False, location=(-400, 0)):
    nt = mat.node_tree
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = image
    n.location = location
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    return n


def use_base_color(mat, image):
    nt = mat.node_tree
    n = tex_node(mat, image, location=(-500, 300))
    nt.links.new(n.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])


def use_normal_map(mat, image, strength=1.0):
    nt = mat.node_tree
    n = tex_node(mat, image, non_color=True, location=(-700, -300))
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = strength
    nm.location = (-300, -300)
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])


def use_occlusion(mat, image):
    """glTF exporter picks up AO from a 'glTF Material Output' group's Occlusion input."""
    nt = mat.node_tree
    group = bpy.data.node_groups.get("glTF Material Output")
    if group is None:
        group = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        group.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        group.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = group
    g.location = (200, -400)
    n = tex_node(mat, image, non_color=True, location=(-200, -600))
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (0, -600)
    nt.links.new(n.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Red"], g.inputs["Occlusion"])


# ---------------------------------------------------------------------------
# Images & baking
# ---------------------------------------------------------------------------

def image_from_array(name, rgba, non_color=False):
    """rgba: float array (h, w, 4) in 0..1, row 0 = bottom. Saved as PNG for export."""
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(np.ascontiguousarray(rgba, dtype=np.float32).ravel())
    return save_image(img)


def save_image(img):
    path = os.path.join(TEX_DIR, img.name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def setup_cycles(samples=64):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("CUDA",):  # OptiX kernels fail on this driver
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                break
        except TypeError:
            continue
    for d in prefs.devices:
        d.use = d.type != "CPU"
    sc.cycles.device = "GPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False


def bake(target, image, kind, sources=(), extrusion=0.04, margin=16, samples=64):
    """Bake `kind` ('NORMAL', 'AO', ...) into `image` on `target`'s active UV map."""
    setup_cycles(samples)
    temp = []
    for mat in target.data.materials:
        n = mat.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = image
        mat.node_tree.nodes.active = n
        temp.append((mat, n))
    bpy.ops.object.select_all(action="DESELECT")
    for s in sources:
        s.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    rb = bpy.context.scene.render.bake
    rb.use_selected_to_active = bool(sources)
    rb.cage_extrusion = extrusion
    rb.margin = margin
    rb.normal_space = "TANGENT"
    bpy.ops.object.bake(type=kind)
    for mat, n in temp:
        mat.node_tree.nodes.remove(n)
    return save_image(image)


def smart_uv(obj, margin=0.01):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_ao(obj, size=1024, samples=128, distance=0.3):
    """Ambient occlusion from the whole scene, wired into obj's materials."""
    bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world.light_settings.distance = distance
    img = bpy.data.images.new(obj.name + "_ao", size, size, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    bake(obj, img, "AO", samples=samples)
    for mat in obj.data.materials:
        use_occlusion(mat, img)
    return img


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_glb(name, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    path = os.path.join(OUT_DIR, name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        export_image_format="WEBP",
        export_image_quality=88,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=7,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )
    print(f"EXPORTED {path} tris={tri_count(objects)} size={os.path.getsize(path) // 1024}KB")
    return path


# ---------------------------------------------------------------------------
# Frames & primitives
# ---------------------------------------------------------------------------

def frame(n, roll=0.0):
    """4x4 matrix whose Z points along n, X to the viewer's right, Y up (viewer at -Y)."""
    from mathutils import Matrix
    n = Vector(n).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.95 else Vector((0, 1, 0))
    x = up.cross(n).normalized()
    y = n.cross(x).normalized()
    m = Matrix((x, y, n)).transposed()
    m = m @ Matrix.Rotation(roll, 3, "Z")
    return m.to_4x4()


def torus(name, major, minor, steps=128, ring=16, z=0.0):
    prof = [(major + minor * math.cos(a), z + minor * math.sin(a))
            for a in [i / ring * math.tau for i in range(ring + 1)]]
    return lathe(name, prof, steps=steps)


def rounded_rect(hw, hh, r_top, r_bottom, n=16):
    """Closed outline (x, y) of a rectangle with separate top/bottom corner radii."""
    pts = []
    corners = [(hw - r_top, hh - r_top, r_top, 0), (-hw + r_top, hh - r_top, r_top, 90),
               (-hw + r_bottom, -hh + r_bottom, r_bottom, 180), (hw - r_bottom, -hh + r_bottom, r_bottom, 270)]
    for cx, cy, r, start in corners:
        for i in range(n + 1):
            a = math.radians(start + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def prism(name, outline, y0, y1, center=(0, 0)):
    """Extrude an (x, z) outline along Y from y0 to y1 (closed solid)."""
    bm = bmesh.new()
    a = [bm.verts.new((x + center[0], y0, z + center[1])) for x, z in outline]
    b = [bm.verts.new((x + center[0], y1, z + center[1])) for x, z in outline]
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm)


def wrap_to_sphere(obj, n, radius, roll=0.0, subdivide=3):
    """Gnomonic-project a flat mesh (XY plane, Z = height) onto a sphere around direction n."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if subdivide:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=subdivide, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces)
    f = frame(n, roll)
    X, Y, N = f.col[0].xyz, f.col[1].xyz, f.col[2].xyz
    for v in bm.verts:
        lx, ly, lz = v.co
        v.co = (N + X * lx + Y * ly).normalized() * (radius + lz)
    bm.to_mesh(obj.data)
    bm.free()


def recessed_sphere(name, cap_angle, depth, rim_fillet=0.03, floor_fillet=0.02, rings=72, steps=128):
    """Sphere with a flat-bottomed circular recess at +Z (lathe, so the rim is clean)."""
    y0 = math.cos(cap_angle)
    rho = math.sin(cap_angle)
    floor = y0 - depth
    prof = []
    arc_end = cap_angle + rim_fillet
    for i in range(rings + 1):
        a = math.pi - (math.pi - arc_end) * i / rings
        prof.append((max(math.sin(a), 0.0), math.cos(a)))

    def quad(p0, p1, p2, n):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
                for t in [k / n for k in range(1, n + 1)]]

    prof += quad(prof[-1], (rho, y0), (rho, y0 - rim_fillet), 8)
    prof += [(rho, floor + floor_fillet)]
    prof += quad(prof[-1], (rho, floor), (rho - floor_fillet, floor), 6)
    prof += [(rho * 0.5, floor), (0.0, floor)]
    return lathe(name, prof, steps=steps), rho, y0, floor


def face_out(obj, ref=None):
    """Flip faces so normals point away from the origin (or along `ref` for flat parts)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    flip = [f for f in bm.faces
            if f.normal.dot(Vector(ref) if ref is not None else f.calc_center_median()) < 0]
    bmesh.ops.reverse_faces(bm, faces=flip)
    bm.to_mesh(obj.data)
    bm.free()
