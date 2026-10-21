"""Raiden OS 3D emblem: glossy gradient tile with a white 'R', plus a rotating light ring.

Used for the Plymouth boot animation (looping frames) and hero images.

    ns = {"__file__": ".../logo3d.py"}; exec(open(ns["__file__"], encoding="utf-8").read(), ns)
    ns["render_splash_frames"]("C:/out/plymouth", frames=60, size=256)
    ns["render_hero"]("C:/out/hero.png", size=1024)
"""
import math
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    os.getcwd()
exec(open(os.path.join(HERE, "rl_common.py"), encoding="utf-8").read())

KAPPA = 0.5522847498


def rounded_rect_curve(name, size=2.0, radius=0.533, depth=0.18, bevel=0.035):
    """Rounded square (same proportions as the 2D logo: rx 64/240) extruded along Z."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth / 2
    cu.bevel_depth = bevel
    cu.bevel_resolution = 6
    cu.resolution_u = 24
    sp = cu.splines.new("BEZIER")
    h = size / 2
    r = radius
    k = r * KAPPA
    # 8 points: two per side (where the straight edges meet the corner arcs)
    pts = [((h - r, -h), (-k, 0), (k, 0)), ((h, -h + r), (0, -k), (0, k)),
           ((h, h - r), (0, -k), (0, k)), ((h - r, h), (k, 0), (-k, 0)),
           ((-h + r, h), (k, 0), (-k, 0)), ((-h, h - r), (0, k), (0, -k)),
           ((-h, -h + r), (0, k), (0, -k)), ((-h + r, -h), (-k, 0), (k, 0))]
    sp.bezier_points.add(len(pts) - 1)
    for bp, ((x, y), hl, hr) in zip(sp.bezier_points, pts):
        bp.co = (x, y, 0)
        bp.handle_left = (x + hl[0], y + hl[1], 0)
        bp.handle_right = (x + hr[0], y + hr[1], 0)
        bp.handle_left_type = bp.handle_right_type = "FREE"
    # straight edges: make the handles between corners collinear
    sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def r_letter_curve(name, scale, stroke, z):
    """The 'R' strokes of the 2D logo (256px grid, centre 128,128) as a bevelled 3D curve."""
    def P(x, y):
        return ((x - 128) / 128 * scale, (128 - y) / 128 * scale, 0.0)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = stroke
    cu.bevel_resolution = 8
    cu.resolution_u = 32
    cu.use_fill_caps = True
    # stem + bowl: M92 188 V70 H136 A33 33 0 0 1 136 136 H92
    s1 = cu.splines.new("BEZIER")
    k = 33 * KAPPA
    pts = [(P(92, 188), None), (P(92, 70), None), (P(136, 70), None),
           (P(169, 103), "arc1"), (P(136, 136), "arc2"), (P(92, 136), None)]
    s1.bezier_points.add(len(pts) - 1)
    for bp, (co, kind) in zip(s1.bezier_points, pts):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "VECTOR"
    # turn the bowl into a smooth half circle (136,70) -> (169,103) -> (136,136)
    b2, b3, b4 = s1.bezier_points[2], s1.bezier_points[3], s1.bezier_points[4]
    for b in (b2, b3, b4):
        b.handle_left_type = b.handle_right_type = "FREE"
    b2.handle_right = P(136 + k, 70)
    b3.handle_left = P(169, 103 - k)
    b3.handle_right = P(169, 103 + k)
    b4.handle_left = P(136 + k, 136)
    b2.handle_left = P(136 - 5, 70)
    b4.handle_right = P(136 - 5, 136)
    # leg: M126 136 L168 186
    s2 = cu.splines.new("BEZIER")
    s2.bezier_points.add(1)
    s2.bezier_points[0].co = P(126, 136)
    s2.bezier_points[1].co = P(168, 186)
    for bp in s2.bezier_points:
        bp.handle_left_type = bp.handle_right_type = "VECTOR"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 0, z)
    ob.scale = (1, 1, 0.45)          # flatten the round tubes into soft extruded strokes
    return ob


def _arc(cx, cy, r, a0, a1, step_deg=2.0):
    """Points along a circular arc in SVG coordinates (y down), angles in degrees."""
    n = max(2, int(abs(a1 - a0) / step_deg) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]


def r_glyph_outlines():
    """Outline of the logo's stroked 'R' (stroke width 28, round caps/joins), SVG coordinates.

    Outer contour + the counter (hole) of the bowl. Derived from the SVG paths
    M92 188 V70 H136 A33 33 0 0 1 136 136 H92  and  M126 136 L168 186.
    """
    leg = (42.0, 50.0)
    ll = math.hypot(*leg)
    u = (leg[0] / ll, leg[1] / ll)
    n = (u[1], -u[0])                                    # normal pointing up-right
    right0 = (126 + 14 * n[0], 136 + 14 * n[1])
    right1 = (168 + 14 * n[0], 186 + 14 * n[1])
    left0 = (126 - 14 * n[0], 136 - 14 * n[1])
    # where the leg's right edge meets the bowl's outer circle (r=47 around 136,103)
    px, py = right0[0] - 136, right0[1] - 103
    b = 2 * (px * u[0] + py * u[1])
    c = px * px + py * py - 47 * 47
    s = (-b + math.sqrt(b * b - 4 * c)) / 2
    meet = (right0[0] + s * u[0], right0[1] + s * u[1])
    meet_angle = math.degrees(math.atan2(meet[1] - 103, meet[0] - 136))
    # where the leg's left edge meets the bottom of the bottom bar (y = 150)
    s2 = (150 - left0[1]) / u[1]
    left_meet = (left0[0] + s2 * u[0], 150.0)
    cap_start = math.degrees(math.atan2(n[1], n[0]))     # angle of right1 around (168,186)
    outer = []
    outer += _arc(92, 70, 14, 180, 270)                  # top-left round join
    outer += [(136, 56)]
    outer += _arc(136, 103, 47, -90, meet_angle)         # outer bowl
    outer += [right1]
    outer += _arc(168, 186, 14, cap_start, cap_start + 180)   # leg end cap
    outer += [left_meet, (106, 150), (106, 188)]
    outer += _arc(92, 188, 14, 0, 180)                   # stem bottom cap
    outer += [(78, 70)]
    inner = [(106, 84), (136, 84)] + _arc(136, 103, 19, -90, 90) + [(106, 122)]
    return outer, inner


def r_letter_mesh_curve(name, svg_unit, depth, bevel, z):
    """Filled, extruded and bevelled 'R' glyph (2D curve with a hole)."""
    outer, inner = r_glyph_outlines()
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth / 2
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    for pts, rev in ((outer, False), (inner, True)):
        sp = cu.splines.new("POLY")
        seq = list(reversed(pts)) if rev else pts
        # drop consecutive duplicates
        clean = [seq[0]] + [p for i, p in enumerate(seq[1:], 1) if math.dist(p, seq[i - 1]) > 1e-6]
        sp.points.add(len(clean) - 1)
        for pt, (x, y) in zip(sp.points, clean):
            pt.co = ((x - 128) * svg_unit, (128 - y) * svg_unit, 0.0, 1.0)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 0, z)
    return ob


def tile_material():
    mat = bpy.data.materials.new("TileGradient")
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (0.62, -0.78, 0.0)      # top-left -> bottom-right like the SVG
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = -1.25
    mapr.inputs["From Max"].default_value = 1.25
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, hex_rgba("#2BD9F0")
    els[1].position, els[1].color = 1.0, hex_rgba("#7B3AED")
    mid = els.new(0.45)
    mid.color = hex_rgba("#3D6BF7")
    nt.links.new(coord.outputs["Object"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], mapr.inputs["Value"])
    nt.links.new(mapr.outputs["Result"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.3
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def letter_material():
    mat = bpy.data.materials.new("LetterWhite")
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
    bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    bsdf.inputs["Emission Strength"].default_value = 0.55
    bsdf.inputs["Roughness"].default_value = 0.25
    bsdf.inputs["Coat Weight"].default_value = 0.6
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def ring_material(name, head_hex="#BFF6FF", tail_hex="#3D6BF7", strength=6.0):
    """Emissive comet ring: bright head fading to transparent along the angle."""
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    atan = nt.nodes.new("ShaderNodeMath")
    atan.operation = "ARCTAN2"
    norm = nt.nodes.new("ShaderNodeMapRange")       # angle -pi..pi -> 0..1
    norm.inputs["From Min"].default_value = -math.pi
    norm.inputs["From Max"].default_value = math.pi
    ramp_a = nt.nodes.new("ShaderNodeValToRGB")      # alpha/brightness along the ring
    ea = ramp_a.color_ramp.elements
    ea[0].position, ea[0].color = 0.0, (0, 0, 0, 1)
    ea[1].position, ea[1].color = 1.0, (1, 1, 1, 1)
    ramp_a.color_ramp.interpolation = "EASE"
    e_cut = ea.new(0.999)
    e_cut.color = (1, 1, 1, 1)
    ramp_c = nt.nodes.new("ShaderNodeValToRGB")      # colour along the ring
    ec = ramp_c.color_ramp.elements
    ec[0].position, ec[0].color = 0.0, hex_rgba("#7B3AED")
    ec[1].position, ec[1].color = 1.0, hex_rgba(head_hex)
    m = ec.new(0.6)
    m.color = hex_rgba(tail_hex)
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mulstr = nt.nodes.new("ShaderNodeMath")
    mulstr.operation = "MULTIPLY"
    mulstr.inputs[1].default_value = strength
    nt.links.new(coord.outputs["Object"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], atan.inputs[0])
    nt.links.new(sep.outputs["X"], atan.inputs[1])
    nt.links.new(atan.outputs[0], norm.inputs["Value"])
    nt.links.new(norm.outputs["Result"], ramp_a.inputs[0])
    nt.links.new(norm.outputs["Result"], ramp_c.inputs[0])
    nt.links.new(ramp_c.outputs["Color"], em.inputs["Color"])
    nt.links.new(ramp_a.outputs["Color"], mulstr.inputs[0])
    nt.links.new(mulstr.outputs[0], em.inputs["Strength"])
    nt.links.new(ramp_a.outputs["Color"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    return mat


def ring(name, radius, tube, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=tube, major_segments=192,
                                     minor_segments=16, location=(0, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


def build_emblem(with_ring=True, bg_hex="#000000"):
    reset_scene()
    tile = rounded_rect_curve("Tile", size=2.0, radius=0.533, depth=0.22, bevel=0.05)
    tile.data.materials.append(tile_material())
    # SVG tile spans 240 units -> 2.0 Blender units; stroke width 28 -> radius 14 units
    svg_unit = 2.0 / 240.0
    letter = r_letter_mesh_curve("Letter", svg_unit, depth=0.07, bevel=0.018, z=0.165)
    letter.data.materials.append(letter_material())
    rings = []
    if with_ring:
        rings.append(ring("Ring", 1.62, 0.028, ring_material("RingMat")))
        rings.append(ring("RingGlow", 1.62, 0.12, ring_material("RingGlowMat", strength=0.9)))
    set_world_color(bg_hex, 1.0)
    # soft studio light + a strip whose reflection sweeps over the coat
    key = add_area_light((-3.0, 3.5, 6.0), (0, 0, 0), 260.0, "#FFFFFF", size=4.0, name="Key")
    sweep = add_area_light((0.0, 0.0, 5.0), (0, 0, 0), 0.0, "#FFFFFF", size=0.4, shape="RECTANGLE", name="Sweep")
    sweep.data.size = 8.0
    sweep.data.size_y = 0.9
    sweep.visible_camera = False      # only its reflection should be seen
    key.visible_camera = False
    cam = add_camera((0.0, 0.0, 9.0), (0.0, 0.0, 0.0), lens=50.0)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 3.9
    return tile, letter, rings, sweep


def render_splash_frames(out_dir, frames=60, size=256, samples=96):
    """Looping boot animation: ring makes one full turn; a light sheen sweeps the tile once."""
    tile, letter, rings, sweep = build_emblem(with_ring=True, bg_hex="#000000")
    setup_render(size, size, samples=samples, view="Standard", look=None)
    os.makedirs(out_dir, exist_ok=True)
    for f in range(frames):
        phase = f / frames
        for r in rings:
            r.rotation_euler = (0.0, 0.0, -2 * math.pi * phase)
        # sheen: a narrow strip light gliding diagonally across, visible ~40% of the loop
        s = (phase * 2.5) - 0.75
        sweep.location = (s * 3.0, -s * 3.0, 5.0)
        sweep.rotation_euler = (0.0, 0.0, math.radians(45))
        # fade in/out so the sheen never pops
        fade = max(0.0, 1.0 - abs(s) / 0.9)
        sweep.data.energy = 45.0 * fade * fade
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"throbber-{f + 1:04d}.png")
        bpy.ops.render.render(write_still=True)
    return out_dir


def render_hero(path, size=1024, samples=192, transparent=True):
    build_emblem(with_ring=False)
    setup_render(size, size, samples=samples, transparent=transparent, view="Standard", look=None)
    return render_to(path)
