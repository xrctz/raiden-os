"""Raiden OS wallpaper "Aurora": flowing silk sheet in the brand gradient.

Run inside Blender:  exec(open(<this file>).read()); build_aurora("dark")
"""
import math
import os

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    os.getcwd()
exec(open(os.path.join(HERE, "rl_common.py"), encoding="utf-8").read())


def aurora_height(X, Y):
    fold = 1.25 * np.sin(0.30 * X + 0.95 * np.sin(0.16 * Y + 0.4))
    swell = 0.62 * np.sin(0.52 * X - 0.33 * Y + 1.2)
    ripple = 0.30 * np.sin(1.05 * X + 0.65 * Y + 0.3) * np.exp(-((Y + 1.5) / 7.0) ** 2)
    tilt = 0.10 * Y
    return fold + swell + ripple + tilt


def diagonal_gradient_material(name, stops, roughness, sheen, coat, emission=0.0, dx=1.0, dy=0.45,
                               lo=-16.0, hi=16.0):
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (dx, dy, 0.0)
    mapr = nt.nodes.new("ShaderNodeMapRange")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(coord.outputs["Object"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], mapr.inputs["Value"])
    mapr.inputs["From Min"].default_value = lo
    mapr.inputs["From Max"].default_value = hi
    nt.links.new(mapr.outputs["Result"], ramp.inputs[0])
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, hx) in zip(els, stops):
        el.position = pos
        el.color = hex_rgba(hx)
    ramp.color_ramp.interpolation = "EASE"
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    _set_input(bsdf, ("Sheen Weight", "Sheen"), sheen)
    _set_input(bsdf, ("Sheen Tint",), (1.0, 1.0, 1.0, 1.0))
    _set_input(bsdf, ("Coat Weight", "Coat"), coat)
    _set_input(bsdf, ("Coat Roughness",), 0.08)
    if emission:
        nt.links.new(ramp.outputs["Color"], _get_input(bsdf, ("Emission Color", "Emission")))
        _set_input(bsdf, ("Emission Strength",), emission)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


VARIANTS = {
    "dark": dict(
        world_top="#070B18", world_bottom="#0B1124", world_strength=1.0,
        stops=[(0.0, "#0E2A6B"), (0.28, "#2BD9F0"), (0.52, "#3D6BF7"), (0.78, "#7B3AED"), (1.0, "#C13BE8")],
        roughness=0.32, sheen=0.55, coat=0.35, emission=0.0,
        key=("#DCE6FF", 2600.0), rim=("#2BD9F0", 3200.0), fill=("#B24BFF", 1800.0),
        exposure=0.0, look="Punchy",
    ),
    "light": dict(
        world_top="#F4F7FF", world_bottom="#DCE5FF", world_strength=1.0,
        stops=[(0.0, "#BFD3FF"), (0.28, "#7FE7F5"), (0.52, "#7FA0FF"), (0.78, "#B08CFF"), (1.0, "#F2A6FF")],
        roughness=0.38, sheen=0.6, coat=0.25, emission=0.0,
        key=("#FFFFFF", 2400.0), rim=("#9FF3FF", 1600.0), fill=("#E3B6FF", 1300.0),
        exposure=0.35, look="Base Contrast",
    ),
}


def build_aurora(variant="dark"):
    v = VARIANTS[variant]
    reset_scene()
    sheet = grid_surface("AuroraSheet", 44.0, 26.0, 440, 260, aurora_height, subsurf=1)
    sheet.rotation_euler = (math.radians(-8.0), 0.0, math.radians(-6.0))
    mat = diagonal_gradient_material(f"Aurora-{variant}", v["stops"], v["roughness"], v["sheen"], v["coat"],
                                     v["emission"])
    sheet.data.materials.append(mat)

    set_world_gradient(v["world_top"], v["world_bottom"], strength=v["world_strength"], light_strength=0.35)
    add_area_light((-10.0, -8.0, 12.0), (0.0, 0.0, 0.0), v["key"][1], v["key"][0], size=10.0, name="Key")
    add_area_light((4.0, 14.0, 7.0), (0.0, 0.0, 0.0), v["rim"][1], v["rim"][0], size=8.0, name="Rim")
    add_area_light((16.0, -4.0, 5.0), (2.0, 0.0, 0.0), v["fill"][1], v["fill"][0], size=7.0, name="Fill")
    add_camera((0.0, -19.0, 8.5), (0.6, 0.0, 0.2), lens=42.0, dof_distance=19.5, fstop=3.2)
    return v


def render_aurora(variant, path, width=3840, height=2160, samples=256):
    v = build_aurora(variant)
    setup_render(width, height, samples=samples, view="AgX", look=v["look"], exposure=v["exposure"])
    return render_to(path)
