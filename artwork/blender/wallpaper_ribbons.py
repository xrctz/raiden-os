"""Raiden OS wallpapers: frosted-glass ribbons over a luminous aurora glow.

Run inside Blender (any scene; it is rebuilt from scratch):
    ns = {"__file__": ".../wallpaper_ribbons.py"}
    exec(open(ns["__file__"], encoding="utf-8").read(), ns)
    ns["render_wallpaper"]("aurora-dark", "C:/out/aurora-dark.png")
"""
import math
import os

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    os.getcwd()
exec(open(os.path.join(HERE, "rl_common.py"), encoding="utf-8").read())


# --------------------------------------------------------------------------- geometry
def ribbon_mesh(name, length=70.0, width=2.6, n_len=700, n_w=28, amp=(3.2, 1.1), freq=(0.85, 2.3),
                phase=(0.0, 0.0), twist=(1.1, 0.55, 0.0), depth=0.0, height=0.0, slope=0.18, wobble=0.6,
                thickness=0.08):
    """A ribbon whose centreline flows left -> right while it slowly twists."""
    t = np.linspace(0.0, 1.0, n_len)
    x = (t - 0.5) * length
    z = (height + slope * x
         + amp[0] * np.sin(2 * np.pi * freq[0] * t + phase[0])
         + amp[1] * np.sin(2 * np.pi * freq[1] * t + phase[1]))
    y = depth + wobble * np.sin(2 * np.pi * 0.6 * t + phase[0] * 0.7)
    C = np.stack([x, y, z], axis=1)
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    toward_camera = np.array([0.0, -1.0, 0.0])
    N0 = toward_camera - (T @ toward_camera)[:, None] * T
    N0 /= np.linalg.norm(N0, axis=1, keepdims=True)
    B = np.cross(T, N0)
    theta = twist[0] * np.sin(2 * np.pi * twist[1] * t + twist[2])
    W = np.cos(theta)[:, None] * B + np.sin(theta)[:, None] * N0
    s = np.linspace(-0.5, 0.5, n_w)
    taper = np.clip(np.minimum(t, 1 - t) * 9.0, 0.0, 1.0) ** 0.5
    verts = (C[:, None, :] + (s[None, :, None] * width * taper[:, None, None]) * W[:, None, :]).reshape(-1, 3)
    faces = [(i * n_w + j, i * n_w + j + 1, (i + 1) * n_w + j + 1, (i + 1) * n_w + j)
             for i in range(n_len - 1) for j in range(n_w - 1)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts.tolist(), [], faces)
    uv = mesh.uv_layers.new(name="UVMap")
    uvs = np.zeros((len(faces) * 4, 2), dtype=np.float32)
    k = 0
    for i in range(n_len - 1):
        for j in range(n_w - 1):
            for (ii, jj) in ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)):
                uvs[k] = (t[ii], s[jj] + 0.5)
                k += 1
    uv.data.foreach_set("uv", uvs.ravel())
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    sol = ob.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = 0.0
    sub = ob.modifiers.new("Subsurf", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    return ob


# --------------------------------------------------------------------------- materials
def glass_ribbon_material(name, stops, roughness=0.14, coat=0.8, emission=0.1, thin_film=420.0):
    """Frosted tinted glass; the tint follows a ramp along the ribbon (UV.x)."""
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(uvn.outputs["UV"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], ramp.inputs[0])
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, hx) in zip(els, stops):
        el.position = pos
        el.color = hex_rgba(hx)
    ramp.color_ramp.interpolation = "EASE"
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = 1.45
    _set_input(bsdf, ("Transmission Weight", "Transmission"), 1.0)
    _set_input(bsdf, ("Coat Weight", "Coat"), coat)
    _set_input(bsdf, ("Coat Roughness",), 0.04)
    if thin_film:
        _set_input(bsdf, ("Thin Film Thickness",), thin_film)
        _set_input(bsdf, ("Thin Film IOR",), 1.38)
    nt.links.new(ramp.outputs["Color"], _get_input(bsdf, ("Emission Color", "Emission")))
    _set_input(bsdf, ("Emission Strength",), emission)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def glow_plane(name, colors, strength, location=(7.0, 18.0, 4.0), size=(150.0, 90.0), center=(0.6, 0.53),
               radius=0.36):
    """Large emissive backdrop with a soft radial glow (the 'aurora' behind the glass)."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=(math.radians(90), 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0], size[1], 1.0)
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (center[0], center[1], 0.0)
    scl = nt.nodes.new("ShaderNodeVectorMath")
    scl.operation = "MULTIPLY"
    scl.inputs[1].default_value = (1.0, size[1] / size[0], 1.0)
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = 0.0
    mapr.inputs["From Max"].default_value = radius
    mapr.inputs["To Min"].default_value = 1.0
    mapr.inputs["To Max"].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for el, (pos, hx) in zip(els, colors):
        el.position = pos
        el.color = hex_rgba(hx)
    ramp.color_ramp.interpolation = "EASE"
    nt.links.new(tc.outputs["UV"], sub.inputs[0])
    nt.links.new(sub.outputs[0], scl.inputs[0])
    nt.links.new(scl.outputs[0], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], mapr.inputs["Value"])
    nt.links.new(mapr.outputs["Result"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


# --------------------------------------------------------------------------- scenes
# Ribbon layout shared by every variant: (depth, height, phase, amp, freq, twist, width)
LAYOUT = [
    (3.5, 2.2, (1.4, 0.6), (3.4, 1.0), (0.62, 1.9), (1.1, 0.5, 2.2), 4.6),
    (0.0, -1.0, (0.0, 1.0), (4.0, 1.2), (0.58, 1.7), (1.4, 0.45, 0.3), 6.2),
    (7.0, 4.8, (2.9, 0.2), (3.0, 0.8), (0.66, 2.1), (1.0, 0.55, 4.1), 3.2),
    (-4.2, -3.6, (2.5, 1.9), (3.0, 0.8), (0.7, 2.2), (0.9, 0.55, 1.0), 1.6),
]

SCENES = {
    "aurora-dark": dict(
        world=("#070B1C", "#020308"), ambient=("#0B1230", 0.08),
        bands=[(0.6, 0.04, "#DDE8FF"), (0.75, 0.025, "#BFEFFF"), (0.88, 0.03, "#F0D8FF")], band_strength=5.0,
        glow=([(0.0, "#000000"), (0.3, "#060A2A"), (0.55, "#1A1F8A"), (0.72, "#4E2FD0"), (0.86, "#3D7BF7"),
               (0.95, "#2BD9F0"), (1.0, "#C8F7FF")], 2.2, (0.6, 0.53), 0.36),
        palettes=[[(0, "#16207A"), (0.4, "#3D6BF7"), (0.72, "#7B3AED"), (1, "#E040FB")],
                  [(0, "#0D3A9C"), (0.3, "#2BD9F0"), (0.6, "#3D6BF7"), (1, "#7B3AED")],
                  [(0, "#1B2A8F"), (0.5, "#5B3FE0"), (1, "#2BD9F0")],
                  [(0, "#1E9BE0"), (0.45, "#2BD9F0"), (0.75, "#3D6BF7"), (1, "#7B3AED")]],
        key=900.0, look="Punchy", exposure=0.0,
    ),
    "aurora-light": dict(
        world=("#FFFFFF", "#EDF1FF"), ambient=("#F2F5FF", 0.9),
        bands=[(0.6, 0.05, "#FFFFFF"), (0.76, 0.03, "#FFFFFF"), (0.88, 0.04, "#FFFFFF")], band_strength=2.0,
        glow=([(0.0, "#F3F6FF"), (0.5, "#E9ECFF"), (0.72, "#D9D2FF"), (0.86, "#C7E3FF"), (0.95, "#D8FAFF"),
               (1.0, "#FFFFFF")], 1.0, (0.6, 0.53), 0.5),
        palettes=[[(0, "#5B7CFF"), (0.4, "#6C8CFF"), (0.72, "#A37BFF"), (1, "#EE8BFF")],
                  [(0, "#4F86FF"), (0.3, "#38D3EA"), (0.6, "#5F84FF"), (1, "#9B74FF")],
                  [(0, "#8296FF"), (0.5, "#A78BFF"), (1, "#5FDCF0")],
                  [(0, "#3FB8F0"), (0.45, "#4FDCEB"), (0.75, "#6F8CFF"), (1, "#A07BFF")]],
        key=1200.0, view="Standard", look=None, exposure=0.0,
    ),
    "nebula-dark": dict(
        world=("#0C0718", "#030207"), ambient=("#1A0E33", 0.08),
        bands=[(0.6, 0.04, "#F2DDFF"), (0.75, 0.025, "#FFD6F5"), (0.88, 0.03, "#D8E4FF")], band_strength=5.0,
        glow=([(0.0, "#000000"), (0.3, "#12061F"), (0.55, "#3A1477"), (0.72, "#8A2FD9"), (0.86, "#D946EF"),
               (0.95, "#FF8AD8"), (1.0, "#FFE3F6")], 2.0, (0.58, 0.55), 0.36),
        palettes=[[(0, "#2A0F6E"), (0.4, "#7B3AED"), (0.72, "#C13BE8"), (1, "#FF6AD5")],
                  [(0, "#3A1A9C"), (0.3, "#B05CFF"), (0.6, "#7B3AED"), (1, "#3D6BF7")],
                  [(0, "#2B1A8F"), (0.5, "#9D4BFF"), (1, "#FF8AD8")],
                  [(0, "#7B3AED"), (0.45, "#E040FB"), (0.75, "#B05CFF"), (1, "#3D6BF7")]],
        key=900.0, look="Punchy", exposure=0.0,
    ),
    "lagoon-dark": dict(
        world=("#04121A", "#010508"), ambient=("#06222B", 0.08),
        bands=[(0.6, 0.04, "#D8FFF8"), (0.75, 0.025, "#BFF6FF"), (0.88, 0.03, "#E0F0FF")], band_strength=5.0,
        glow=([(0.0, "#000000"), (0.3, "#03161C"), (0.55, "#064E5E"), (0.72, "#0E8FA3"), (0.86, "#22D3EE"),
               (0.95, "#7DF9E8"), (1.0, "#E6FFFB")], 2.0, (0.6, 0.5), 0.36),
        palettes=[[(0, "#0A3D5C"), (0.4, "#0EA5B7"), (0.72, "#22D3EE"), (1, "#3D6BF7")],
                  [(0, "#064E5E"), (0.3, "#2DD4BF"), (0.6, "#22D3EE"), (1, "#3D6BF7")],
                  [(0, "#0B3A66"), (0.5, "#1E9BE0"), (1, "#5EEAD4")],
                  [(0, "#14B8A6"), (0.45, "#5EEAD4"), (0.75, "#22D3EE"), (1, "#3D6BF7")]],
        key=900.0, look="Punchy", exposure=0.0,
    ),
}


def build_wallpaper(scene_name, tilt_deg=-16.0):
    cfg = SCENES[scene_name]
    reset_scene()
    for idx, ((depth, height, phase, amp, freq, twist, width), palette) in enumerate(zip(LAYOUT, cfg["palettes"])):
        ob = ribbon_mesh(f"Ribbon{idx}", width=width, depth=depth, height=height, phase=phase, amp=amp,
                         freq=freq, twist=twist)
        ob.rotation_euler = (0.0, math.radians(tilt_deg), 0.0)
        ob.data.materials.append(glass_ribbon_material(f"Ribbon{idx}-{scene_name}", palette))
    set_world_studio(cfg["world"][0], cfg["world"][1], bands=cfg["bands"], band_strength=cfg["band_strength"],
                     ambient_hex=cfg["ambient"][0], ambient_strength=cfg["ambient"][1])
    colors, strength, center, radius = cfg["glow"]
    glow_plane("Glow", colors, strength, center=center, radius=radius)
    add_area_light((-6, -30, 18), (0, 0, 0), cfg["key"], "#E6EEFF", size=24, name="Key")
    add_camera((1.5, -30.0, 2.0), (1.5, 0.0, 1.0), lens=38.0, dof_distance=29.0, fstop=4.0)
    return cfg


def render_wallpaper(scene_name, path, width=3840, height=2160, samples=256):
    cfg = build_wallpaper(scene_name)
    setup_render(width, height, samples=samples, view=cfg.get("view", "AgX"), look=cfg["look"],
                 exposure=cfg["exposure"])
    return render_to(path)
