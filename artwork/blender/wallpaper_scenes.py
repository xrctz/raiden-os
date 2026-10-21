"""Raiden OS 3D scenes for the character themes, also used as wallpapers.

  arcane   a golden heptagram magic circle standing over a dark glossy floor,
           with drifting sparks
  storm    a glowing ring in violet storm clouds, lightning breaking out of it
  crimson  a crimson glass chess king on a dark chessboard, embers rising

Each scene has a hero (the circle, the ring, the king) that the camera puts
at a chosen point of the frame, so character wallpapers can frame the
character's picture in it. The camera keeps the vertical field of view, so a
21:9 render shows more of the sides, not less of the top and bottom.

Run inside Blender 5.2:
    ns = {"__file__": ".../wallpaper_scenes.py"}
    exec(open(ns["__file__"], encoding="utf-8").read(), ns)
    ns["render_scene"]("arcane", "C:/out/arcane.png", 3440, 1440, focus=(0.70, 0.5))
"""
import math
import os
import random

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    os.getcwd()
exec(open(os.path.join(HERE, "rl_common.py"), encoding="utf-8").read())


# ------------------------------------------------------------------ helpers
def clear_compositor():
    bpy.context.scene.compositing_node_group = None


def add_bloom(strength=0.7, size=0.7, threshold=0.8):
    """Glow around bright things (compositor Glare node, Bloom)."""
    scene = bpy.context.scene
    ng = bpy.data.node_groups.new("Raiden-Bloom", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    glare = ng.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = threshold
    glare.inputs["Strength"].default_value = strength
    glare.inputs["Size"].default_value = size
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
    ng.links.new(glare.outputs["Image"], out.inputs[0])
    scene.compositing_node_group = ng
    scene.render.use_compositing = True


def link_mesh(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def ring_object(name, center, radius, thickness, material, axis="Y", segments=256, sides=8):
    """A torus of RADIUS around AXIS (Y: standing up, facing the camera)."""
    bm = bmesh.new()
    circle = bmesh.ops.create_circle(bm, cap_ends=False, radius=thickness, segments=sides)
    for v in circle["verts"]:            # cross-section in the XZ plane
        v.co = Vector((radius + v.co.x, 0.0, v.co.y))
    bmesh.ops.spin(bm, geom=bm.verts[:] + bm.edges[:], cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=segments, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    ob = link_mesh(name, bm, material)
    if axis == "Y":
        ob.rotation_euler = (math.pi / 2, 0, 0)
    ob.location = center
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def bm_rod(bm, a, b, radius, sides=8):
    a, b = Vector(a), Vector(b)
    d = b - a
    length = d.length
    m = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=sides,
                          radius1=radius, radius2=radius, depth=length, matrix=m)


def bm_box(bm, center, size, rot_matrix=None):
    m = Matrix.Translation(center)
    if rot_matrix is not None:
        m = m @ rot_matrix
    m = m @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def sparks(name, count, box, radius, colors, strength, seed=3):
    """Little glowing spheres (out of focus they become bokeh)."""
    rnd = random.Random(seed)
    obs = []
    for idx, hx in enumerate(colors):
        bm = bmesh.new()
        for _ in range(count // len(colors)):
            c = Vector([rnd.uniform(lo, hi) for lo, hi in box])
            r = rnd.uniform(*radius)
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r,
                                       matrix=Matrix.Translation(c))
        mat = emission_material(f"{name}-{idx}", hx, strength)
        obs.append(link_mesh(f"{name}-{idx}", bm, mat))
    for ob in obs:
        ob.visible_shadow = False
    return obs


def noise_backdrop(name, colors, strength, location, size, scale=1.6, dark_left=True):
    """Huge emissive plane far behind: soft coloured haze."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=(math.pi / 2, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0], size[1], 1.0)
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for el, (pos, hx) in zip(els, colors):
        el.position = pos
        el.color = hex_rgba(hx)
    nt.links.new(tc.outputs["Generated"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    color = ramp.outputs["Color"]
    if dark_left:
        # fade to black towards the left, where the name goes
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        fade = nt.nodes.new("ShaderNodeMapRange")
        fade.inputs["From Min"].default_value = 0.30
        fade.inputs["From Max"].default_value = 0.62
        nt.links.new(sep.outputs["X"], fade.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(color, mul.inputs[6])
        nt.links.new(fade.outputs["Result"], mul.inputs[7])
        color = mul.outputs[2]
    nt.links.new(color, em.inputs["Color"])
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


def scene_camera(location, target, vertical_fov_deg, focus, dof_distance=None, fstop=5.6):
    """Camera with a fixed vertical field of view that shows TARGET at FOCUS
    (fractions of the frame from the top left)."""
    cam = add_camera(location, target, lens=50.0, dof_distance=dof_distance, fstop=fstop)
    cam.data.sensor_fit = "VERTICAL"
    cam.data.sensor_height = 24.0
    cam.data.lens = 12.0 / math.tan(math.radians(vertical_fov_deg) / 2)
    scene = bpy.context.scene
    target = Vector(target)

    def project():
        bpy.context.view_layer.update()
        co = world_to_camera_view(scene, cam, target)
        return co.x, 1.0 - co.y

    # projection is linear in the lens shift: measure, then solve
    for axis, want in (("shift_x", focus[0]), ("shift_y", focus[1])):
        setattr(cam.data, axis, 0.0)
        p0 = project()[0 if axis == "shift_x" else 1]
        setattr(cam.data, axis, 0.1)
        p1 = project()[0 if axis == "shift_x" else 1]
        setattr(cam.data, axis, 0.1 * (want - p0) / (p1 - p0))
    return cam


# ------------------------------------------------------------------- arcane
def build_arcane(focus):
    reset_scene()
    clear_compositor()
    R, H = 3.0, 3.25                  # circle radius and height of its centre
    C = Vector((0.0, 0.0, H))
    set_world_gradient("#140829", "#030106", strength=1.0, light_strength=0.15)

    gold = emission_material("Arcane-Gold", "#F6C768", 9.0)
    gold_soft = emission_material("Arcane-GoldSoft", "#F2B85A", 3.5)
    violet = emission_material("Arcane-Violet", "#A065FF", 5.0)

    # rings (vertical, facing the camera)
    for name, r, t, mat in (("Ring-Outer", R, 0.028, gold), ("Ring-Outer2", R * 0.955, 0.012, gold_soft),
                            ("Ring-Star", R * 0.80, 0.020, gold), ("Ring-Inner", R * 0.42, 0.016, gold),
                            ("Ring-Core", R * 0.36, 0.008, violet), ("Ring-Halo", R * 1.10, 0.006, violet)):
        ring_object(name, C, r, t, mat)

    # tick marks between the outer rings, 7 x 12
    bm = bmesh.new()
    for i in range(84):
        a = 2 * math.pi * i / 84
        long = i % 12 == 0
        r0, r1 = (R * 0.955, R * 0.995) if long else (R * 0.962, R * 0.985)
        mid = (r0 + r1) / 2
        center = C + Vector((mid * math.sin(a), 0.0, mid * math.cos(a)))
        rot = Matrix.Rotation(a, 4, "Y")
        bm_box(bm, center, (0.018 if long else 0.010, 0.02, r1 - r0), rot)
    link_mesh("Ticks", bm, gold)

    # diamonds on the band between the outer and the star ring
    bm = bmesh.new()
    for i in range(14):
        a = 2 * math.pi * (i + 0.5) / 14
        r = R * 0.885
        center = C + Vector((r * math.sin(a), 0.0, r * math.cos(a)))
        rot = Matrix.Rotation(a + math.pi / 4, 4, "Y")
        bm_box(bm, center, (0.07, 0.02, 0.07), rot)
    link_mesh("Diamonds", bm, gold_soft)

    # glyph band: short arcs of varying length, like runes
    rnd = random.Random(7)
    bm = bmesh.new()
    a = 0.0
    while a < 2 * math.pi - 0.05:
        span = rnd.uniform(0.04, 0.16)
        r = R * 0.60
        pts = [C + Vector((r * math.sin(a + span * k / 6), 0.0, r * math.cos(a + span * k / 6)))
               for k in range(7)]
        for p, q in zip(pts, pts[1:]):
            bm_rod(bm, p, q, 0.009, sides=6)
        a += span + rnd.uniform(0.03, 0.09)
    link_mesh("Glyphs", bm, gold_soft)

    # heptagram {7/3} with a small circle on every point
    pts = [C + Vector((R * 0.80 * math.sin(2 * math.pi * k / 7), 0.0,
                       R * 0.80 * math.cos(2 * math.pi * k / 7))) for k in range(7)]
    bm = bmesh.new()
    for k in range(7):
        bm_rod(bm, pts[(3 * k) % 7], pts[(3 * (k + 1)) % 7], 0.020)
    link_mesh("Heptagram", bm, gold)
    for k, p in enumerate(pts):
        ring_object(f"Point-{k}", p, 0.13, 0.016, gold, segments=64)

    # inner seal: a small hexagram and a glowing core
    inner = [C + Vector((R * 0.36 * math.sin(math.pi / 3 * k), 0.0,
                         R * 0.36 * math.cos(math.pi / 3 * k))) for k in range(6)]
    bm = bmesh.new()
    for k in range(6):
        bm_rod(bm, inner[k], inner[(k + 2) % 6], 0.010, sides=6)
    link_mesh("Seal", bm, violet)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=C)
    core = bpy.context.active_object
    core.data.materials.append(emission_material("Arcane-Core", "#FFE7B0", 14.0))

    # a second, faint circle lying on the floor under it, like a summoning ground
    floor_gold = emission_material("Arcane-FloorGold", "#E8B04F", 0.9)
    base = Vector((0.0, 0.0, 0.012))
    for name, r, t in (("Floor-Ring1", 4.6, 0.025), ("Floor-Ring2", 4.3, 0.012),
                       ("Floor-Ring3", 3.0, 0.016)):
        ring_object(name, base, r, t, floor_gold, axis="Z")
    fpts = [base + Vector((4.3 * math.sin(2 * math.pi * k / 7), 4.3 * math.cos(2 * math.pi * k / 7), 0))
            for k in range(7)]
    bm = bmesh.new()
    for k in range(7):
        bm_rod(bm, fpts[(3 * k) % 7], fpts[(3 * (k + 1)) % 7], 0.02)
    link_mesh("Floor-Star", bm, floor_gold)

    # glossy dark floor, slightly uneven like polished stone
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    floor = bpy.context.active_object
    mat = bpy.data.materials.new("Arcane-Floor")
    nt = node_tree_of(mat)
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_rgba("#07040C")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.35
    noise.inputs["Detail"].default_value = 6.0
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.05
    rough.inputs["To Max"].default_value = 0.30
    nt.links.new(noise.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    floor.data.materials.append(mat)

    # light from the circle onto the floor, violet rim from behind
    pl = bpy.data.lights.new("CircleGlow", "POINT")
    pl.energy = 900
    pl.color = hex_rgba("#F6C768")[:3]
    pl.shadow_soft_size = 2.0
    plo = bpy.data.objects.new("CircleGlow", pl)
    bpy.context.scene.collection.objects.link(plo)
    plo.location = C + Vector((0, 0.6, -0.6))
    add_area_light((-6, 14, 9), (0, 0, 1), 2500, "#7A3FE0", size=10, name="RimViolet")
    add_area_light((9, 10, 6), (0, 0, 1), 1200, "#C24BD9", size=8, name="RimMagenta")

    name_side = focus[0] > 0.6          # a character's name goes on the left
    noise_backdrop("Arcane-Haze", [(0.0, "#000000"), (0.3, "#0B0418"), (0.5, "#2A0E52"),
                                   (0.68, "#5B2A8F"), (0.85, "#9A5CC0"), (1.0, "#E0A848")],
                   1.1, (0, 60, 18), (260, 110), dark_left=name_side)
    xmin = -4 if name_side else -14
    sparks("Arcane-Sparks", 120, ((xmin, 14), (-5, 6), (0.3, 8)), (0.012, 0.045),
           ["#FFD98A", "#F6C768", "#B98BFF"], 10.0)
    sparks("Arcane-Bokeh", 24, ((xmin + 1, 9), (-11, -8), (0.5, 6)), (0.03, 0.07),
           ["#FFD98A", "#C9A2FF"], 6.0, seed=21)
    add_bloom(strength=0.75, size=0.75, threshold=0.7)
    scene_camera((0.0, -17.5, 2.3), tuple(C), vertical_fov_deg=26.0, focus=focus,
                 dof_distance=17.6, fstop=2.2)
    return dict(view="AgX", look="Punchy", exposure=-0.2)


# -------------------------------------------------------------------- storm
def lightning_path(rnd, a, b, rough=0.22, depth=6, jitter_y=0.6):
    pts = [Vector(a), Vector(b)]
    disp = (Vector(b) - Vector(a)).length * rough
    for _ in range(depth):
        new = [pts[0]]
        for p, q in zip(pts, pts[1:]):
            d = q - p
            side = Vector((-d.z, 0.0, d.x)).normalized() if d.length else Vector((1, 0, 0))
            mid = (p + q) / 2 + side * rnd.uniform(-disp, disp) + \
                Vector((0, rnd.uniform(-disp, disp) * jitter_y, 0))
            new += [mid, q]
        pts = new
        disp *= 0.52
    return pts


def curve_from_paths(name, paths, bevel, material):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    for pts, scale in paths:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            # taper towards the end of every bolt
            sp.points[i].co = (p.x, p.y, p.z, 1.0)
            sp.points[i].radius = scale * (1.0 - 0.75 * i / max(1, len(pts) - 1))
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    ob.visible_shadow = False
    return ob


def build_storm(focus):
    reset_scene()
    clear_compositor()
    R, C = 1.35, Vector((0.0, 0.0, 0.0))
    set_world_gradient("#0E0A2E", "#03020C", strength=1.0, light_strength=0.2)

    ring_object("Ring", C, R, 0.045, emission_material("Storm-Ring", "#E4D6FF", 8.0))
    ring_object("Ring-2", C, R * 1.12, 0.012, emission_material("Storm-Ring2", "#B79BFF", 4.0))
    ring_object("Ring-3", C, R * 1.26, 0.006, emission_material("Storm-Ring3", "#8E6BFF", 2.5))

    # lightning breaking out of the ring, with branches
    rnd = random.Random(11)
    paths = []
    for ang, length in ((32, 7.5), (70, 5.0), (112, 6.5), (158, 4.2), (205, 3.6), (250, 3.4),
                        (298, 4.8), (338, 6.8)):
        a = math.radians(ang)
        start = C + Vector((R * 1.02 * math.sin(a), 0.0, R * 1.02 * math.cos(a)))
        end = C + Vector(((R + length) * math.sin(a), rnd.uniform(-1.5, 1.5),
                          (R + length) * math.cos(a)))
        main = lightning_path(rnd, start, end)
        paths.append((main, 1.0))
        for _ in range(3):
            i = rnd.randrange(len(main) // 5, 4 * len(main) // 5)
            b = a + math.radians(rnd.choice((-1, 1)) * rnd.uniform(20, 50))
            bl = length * rnd.uniform(0.2, 0.45)
            s = main[i]
            e = s + Vector((bl * math.sin(b), rnd.uniform(-0.8, 0.8), bl * math.cos(b)))
            paths.append((lightning_path(rnd, s, e, depth=5), 0.55))
    curve_from_paths("Bolts", paths, 0.022, emission_material("Storm-Bolt", "#F4EEFF", 45.0))

    # far bolts inside the clouds
    far = []
    for x in (8, 13, 19):
        top = Vector((x + rnd.uniform(-2, 2), 14.0, 9.0))
        far.append((lightning_path(rnd, top, top + Vector((rnd.uniform(-4, 4), 0, -10))), 1.0))
    curve_from_paths("FarBolts", far, 0.05, emission_material("Storm-FarBolt", "#C9B2FF", 12.0))

    # storm clouds: a volume of noise, lit by the bolts
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 12, 2))
    clouds = bpy.context.active_object
    clouds.scale = (90, 14, 34)
    mat = bpy.data.materials.new("Storm-Clouds")
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = hex_rgba("#5E46B8")
    vol.inputs["Anisotropy"].default_value = 0.35
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.11
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.62
    dens = nt.nodes.new("ShaderNodeMapRange")
    dens.inputs["From Min"].default_value = 0.5
    dens.inputs["From Max"].default_value = 0.82
    dens.inputs["To Max"].default_value = 0.3
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], dens.inputs["Value"])
    nt.links.new(dens.outputs["Result"], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    clouds.data.materials.append(mat)

    # lit mostly on the right; the left stays dark for the name
    for loc, energy in (((11, 9, 6), 22000), ((17, 10, -3), 18000), ((3, 8, 3), 12000),
                        ((7, 11, -7), 10000), ((-9, 10, 6), 2500)):
        pl = bpy.data.lights.new("CloudLight", "POINT")
        pl.energy = energy
        pl.color = hex_rgba("#B9A2FF")[:3]
        pl.shadow_soft_size = 3.0
        plo = bpy.data.objects.new("CloudLight", pl)
        bpy.context.scene.collection.objects.link(plo)
        plo.location = loc

    sparks("Storm-Motes", 120, ((-16, 16), (-6, 4), (-8, 8)), (0.01, 0.035),
           ["#E4D6FF", "#9C7BFF"], 8.0, seed=5)
    add_bloom(strength=0.8, size=0.8, threshold=0.75)
    scene_camera((0.0, -15.0, 0.0), tuple(C), vertical_fov_deg=26.0, focus=focus,
                 dof_distance=15.0, fstop=4.0)
    return dict(view="AgX", look="Punchy", exposure=-0.5)


# ------------------------------------------------------------------ crimson
def chess_piece(name, profile, material, location, scale=1.0, tilt=None):
    """Lathe a (radius, height) profile into a chess piece."""
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((a, b)) for a, b in zip(verts, verts[1:])]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=96, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = link_mesh(name, bm, material)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.location = location
    ob.scale = (scale, scale, scale)
    if tilt:
        ob.rotation_euler = tilt
    mod = ob.modifiers.new("Subsurf", "SUBSURF")
    mod.levels = mod.render_levels = 1
    return ob


KING = [(0.0, 0.0), (0.95, 0.0), (0.95, 0.12), (0.82, 0.2), (0.86, 0.3), (0.62, 0.42),
        (0.5, 0.62), (0.4, 1.4), (0.36, 1.85), (0.58, 1.95), (0.6, 2.05), (0.38, 2.12),
        (0.42, 2.25), (0.5, 2.62), (0.44, 2.7), (0.0, 2.72)]
PAWN = [(0.0, 0.0), (0.75, 0.0), (0.75, 0.1), (0.62, 0.18), (0.5, 0.3), (0.32, 0.7),
        (0.26, 0.95), (0.44, 1.02), (0.44, 1.08), (0.24, 1.12), (0.36, 1.3), (0.38, 1.45),
        (0.3, 1.62), (0.14, 1.7), (0.0, 1.72)]


def build_crimson(focus):
    reset_scene()
    clear_compositor()
    set_world_gradient("#1A0207", "#020001", strength=1.0, light_strength=0.1)

    # chessboard of polished black and deep crimson stone
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    floor = bpy.context.active_object
    mat = bpy.data.materials.new("Crimson-Board")
    nt = node_tree_of(mat)
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.5, 0.5, 0.5)       # 2 m squares
    checker = nt.nodes.new("ShaderNodeTexChecker")
    checker.inputs["Scale"].default_value = 1.0
    checker.inputs["Color1"].default_value = hex_rgba("#5C0B1C")
    checker.inputs["Color2"].default_value = hex_rgba("#050304")
    nt.links.new(tc.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], checker.inputs["Vector"])
    nt.links.new(checker.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.16
    _set_input(bsdf, ("Coat Weight", "Coat"), 0.35)
    floor.data.materials.append(mat)

    glass = bpy.data.materials.new("Crimson-Glass")
    nt = node_tree_of(glass)
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_rgba("#FF2238")
    bsdf.inputs["Roughness"].default_value = 0.04
    bsdf.inputs["IOR"].default_value = 1.52
    _set_input(bsdf, ("Transmission Weight", "Transmission"), 1.0)
    _set_input(bsdf, ("Emission Color", "Emission"), hex_rgba("#FF1030"))
    _set_input(bsdf, ("Emission Strength",), 0.25)
    obsidian = bpy.data.materials.new("Crimson-Obsidian")
    nt = node_tree_of(obsidian)
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_rgba("#060405")
    bsdf.inputs["Roughness"].default_value = 0.12
    _set_input(bsdf, ("Coat Weight", "Coat"), 1.0)

    king = chess_piece("King", KING, glass, (0, 0, 0), scale=1.25)
    # the cross on the crown
    bm = bmesh.new()
    bm_box(bm, Vector((0, 0, 2.98)), (0.16, 0.16, 0.56))
    bm_box(bm, Vector((0, 0, 3.06)), (0.46, 0.16, 0.15))
    cross = link_mesh("Cross", bm, glass)
    cross.scale = (1.25, 1.25, 1.25)
    # a light inside the glass king
    pl = bpy.data.lights.new("KingHeart", "POINT")
    pl.energy = 140
    pl.color = hex_rgba("#FF2A3C")[:3]
    pl.shadow_soft_size = 0.3
    plo = bpy.data.objects.new("KingHeart", pl)
    bpy.context.scene.collection.objects.link(plo)
    plo.location = (0, 0, 1.6)
    plo.visible_transmission = False     # lights the board, no hot spot in the glass

    chess_piece("Pawn-1", PAWN, obsidian, (-4.2, 3.0, 0), scale=1.1)
    chess_piece("Pawn-2", PAWN, obsidian, (4.6, 4.5, 0), scale=1.1)
    chess_piece("Pawn-3", PAWN, obsidian, (2.6, -1.8, 0.62), scale=1.1,
                tilt=(math.radians(90), 0, math.radians(35)))
    chess_piece("Pawn-4", PAWN, glass, (-7.5, 8.0, 0), scale=1.1)

    add_area_light((-6, -8, 9), (0, 0, 1.8), 900, "#FFE8EC", size=6, name="Key")
    add_area_light((0, 10, 6), (0, 0, 1.5), 2200, "#FF1E3C", size=6, name="RimCrimson")
    add_area_light((10, 6, 7), (0, 0, 1.5), 700, "#FF4D6D", size=4, name="RimRose")

    noise_backdrop("Crimson-Haze", [(0.0, "#000000"), (0.5, "#140006"), (0.7, "#4A0613"),
                                    (0.9, "#A3122B"), (1.0, "#FF6B7F")],
                   0.28, (0, 70, 16), (300, 120))
    sparks("Crimson-Embers", 200, ((-14, 14), (-6, 8), (0.2, 9)), (0.012, 0.045),
           ["#FF3B4E", "#FF8A5C", "#FFC4CC"], 12.0, seed=9)
    add_bloom(strength=0.7, size=0.75, threshold=0.75)
    scene_camera((0.0, -13.0, 1.4), (0.0, 0.0, 1.9), vertical_fov_deg=26.0, focus=focus,
                 dof_distance=13.1, fstop=3.2)
    return dict(view="AgX", look="Punchy", exposure=-0.5)


SCENES = {"arcane": build_arcane, "storm": build_storm, "crimson": build_crimson}


def render_scene(name, path, width, height, focus=(0.5, 0.5), samples=256):
    # the camera aims its hero using the frame's aspect, so size the frame first
    render = bpy.context.scene.render
    render.resolution_x, render.resolution_y, render.resolution_percentage = width, height, 100
    cfg = SCENES[name](focus)
    setup_render(width, height, samples=samples, view=cfg["view"], look=cfg["look"],
                 exposure=cfg["exposure"])
    return render_to(path)
