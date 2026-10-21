"""Shared helpers for the Raiden OS Blender scenes.

Every scene script imports this module (it is exec'd into the scene script's
namespace) so render settings, colours and materials stay consistent.
Tested with Blender 5.2 (Cycles + OptiX).
"""
import math
import bpy

# Brand palette (sRGB hex)
PALETTE = {
    "cyan":   "#2BD9F0",
    "blue":   "#3D6BF7",
    "violet": "#7B3AED",
    "pink":   "#E040FB",
    "navy":   "#0B1020",
    "night":  "#060912",
    "mist":   "#EEF3FF",
}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(h, alpha=1.0, linear=True):
    h = h.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    if linear:
        rgb = [srgb_to_linear(c) for c in rgb]
    return (*rgb, alpha)


def reset_scene():
    """Start from an empty scene (keeps the file's preferences)."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                 bpy.data.curves, bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    return scene


def setup_render(width, height, samples=256, transparent=False, view="AgX", look=None, exposure=0.0):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"
        prefs.refresh_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        scene.cycles.device = "GPU"
    except Exception:
        scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.005
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPTIX"
    except Exception:
        pass
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 12
    scene.cycles.glossy_bounces = 8
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = view
    if look:
        for candidate in (look, f"{view} - {look}"):
            try:
                scene.view_settings.look = candidate
                break
            except Exception:
                continue
    scene.view_settings.exposure = exposure
    scene.view_settings.gamma = 1.0
    return scene


def node_tree_of(idblock):
    if hasattr(idblock, "use_nodes"):
        try:
            idblock.use_nodes = True
        except Exception:
            pass
    return idblock.node_tree


def set_world_color(hex_color, strength=1.0):
    world = bpy.context.scene.world
    nt = node_tree_of(world)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs["Color"].default_value = hex_rgba(hex_color)
    bg.inputs["Strength"].default_value = strength


def set_world_gradient(top_hex, bottom_hex, strength=1.0, light_strength=None):
    """Vertical gradient background (camera-facing), optional separate lighting strength."""
    world = bpy.context.scene.world
    nt = node_tree_of(world)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(tex.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs[0])
    ramp.color_ramp.elements[0].color = hex_rgba(bottom_hex)
    ramp.color_ramp.elements[1].color = hex_rgba(top_hex)
    nt.links.new(ramp.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    if light_strength is None:
        nt.links.new(bg.outputs[0], out.inputs[0])
        return
    # Camera rays see the gradient, everything else sees a dimmer version
    lp = nt.nodes.new("ShaderNodeLightPath")
    bg2 = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(ramp.outputs[0], bg2.inputs["Color"])
    bg2.inputs["Strength"].default_value = light_strength
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg2.outputs[0], mix.inputs[1])
    nt.links.new(bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])


def set_world_studio(top_hex, bottom_hex, bands, band_strength=3.0, ambient_hex="#0B1020", ambient_strength=0.05,
                     front_only=True):
    """Camera sees a vertical gradient; glossy rays see soft 'softbox' bands; diffuse rays see dim ambient.

    bands: list of (position 0..1 in elevation, half-width, hex colour).
    """
    world = bpy.context.scene.world
    nt = node_tree_of(world)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    # camera gradient
    tex = nt.nodes.new("ShaderNodeTexCoord")
    sep_w = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Window"], sep_w.inputs[0])
    cam_ramp = nt.nodes.new("ShaderNodeValToRGB")
    cam_ramp.color_ramp.elements[0].color = hex_rgba(bottom_hex)
    cam_ramp.color_ramp.elements[1].color = hex_rgba(top_hex)
    nt.links.new(sep_w.outputs["Y"], cam_ramp.inputs[0])
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(cam_ramp.outputs[0], bg_cam.inputs["Color"])
    # reflection bands from direction elevation
    sep_d = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Generated"], sep_d.inputs[0])
    elev = nt.nodes.new("ShaderNodeMapRange")          # z in [-1, 1] -> [0, 1]
    elev.inputs["From Min"].default_value = -1.0
    elev.inputs["From Max"].default_value = 1.0
    nt.links.new(sep_d.outputs["Z"], elev.inputs["Value"])
    band_ramp = nt.nodes.new("ShaderNodeValToRGB")
    band_ramp.color_ramp.interpolation = "EASE"
    els = band_ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (0, 0, 0, 1)
    els[1].position = 1.0
    els[1].color = (0, 0, 0, 1)
    for pos, half, hx in bands:
        for p, c in ((pos - half, (0, 0, 0, 1)), (pos, hex_rgba(hx)), (pos + half, (0, 0, 0, 1))):
            e = els.new(min(max(p, 0.001), 0.999))
            e.color = c
    nt.links.new(elev.outputs["Result"], band_ramp.inputs[0])
    bg_band = nt.nodes.new("ShaderNodeBackground")
    bg_band.inputs["Strength"].default_value = band_strength
    if front_only:
        # only the hemisphere behind the camera (negative Y) holds softboxes
        front = nt.nodes.new("ShaderNodeMapRange")
        front.inputs["From Min"].default_value = 0.2
        front.inputs["From Max"].default_value = -0.6
        nt.links.new(sep_d.outputs["Y"], front.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(band_ramp.outputs[0], mul.inputs[6])
        nt.links.new(front.outputs["Result"], mul.inputs[7])
        nt.links.new(mul.outputs[2], bg_band.inputs["Color"])
    else:
        nt.links.new(band_ramp.outputs[0], bg_band.inputs["Color"])
    bg_amb = nt.nodes.new("ShaderNodeBackground")
    bg_amb.inputs["Color"].default_value = hex_rgba(ambient_hex)
    bg_amb.inputs["Strength"].default_value = ambient_strength
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix_g = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Glossy Ray"], mix_g.inputs[0])
    nt.links.new(bg_amb.outputs[0], mix_g.inputs[1])
    nt.links.new(bg_band.outputs[0], mix_g.inputs[2])
    mix_c = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix_c.inputs[0])
    nt.links.new(mix_g.outputs[0], mix_c.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix_c.inputs[2])
    nt.links.new(mix_c.outputs[0], out.inputs[0])


def add_camera(location, target, lens=50.0, dof_distance=None, fstop=4.0, name="Camera"):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    look_at(cam, target)
    if dof_distance:
        cam_data.dof.use_dof = True
        cam_data.dof.focus_distance = dof_distance
        cam_data.dof.aperture_fstop = fstop
    bpy.context.scene.camera = cam
    return cam


def look_at(obj, target):
    from mathutils import Vector
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(location, target, energy, color_hex="#FFFFFF", size=4.0, shape="DISK", name="Area"):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = hex_rgba(color_hex)[:3]
    ld.shape = shape
    ld.size = size
    if shape in ("RECTANGLE", "ELLIPSE"):
        ld.size_y = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = location
    look_at(ob, target)
    return ob


def gradient_material(name, stops, axis="X", lo=-10.0, hi=10.0, roughness=0.3, metallic=0.0,
                      coat=0.0, sheen=0.0, emission=0.0, transmission=0.0, ior=1.45):
    """Principled material whose colour follows a ramp along an object-space axis."""
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mapr = nt.nodes.new("ShaderNodeMapRange")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(coord.outputs["Object"], sep.inputs[0])
    nt.links.new(sep.outputs[axis], mapr.inputs["Value"])
    mapr.inputs["From Min"].default_value = lo
    mapr.inputs["From Max"].default_value = hi
    nt.links.new(mapr.outputs["Result"], ramp.inputs[0])
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, hx) in zip(els, stops):
        el.position = pos
        el.color = hex_rgba(hx)
    ramp.color_ramp.interpolation = "B_SPLINE"
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    _set_input(bsdf, ("Coat Weight", "Coat"), coat)
    _set_input(bsdf, ("Sheen Weight", "Sheen"), sheen)
    _set_input(bsdf, ("Transmission Weight", "Transmission"), transmission)
    bsdf.inputs["IOR"].default_value = ior
    if emission > 0:
        nt.links.new(ramp.outputs["Color"], _get_input(bsdf, ("Emission Color", "Emission")))
        _set_input(bsdf, ("Emission Strength",), emission)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def emission_material(name, hex_color, strength):
    mat = bpy.data.materials.new(name)
    nt = node_tree_of(mat)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(hex_color)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _get_input(node, names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None


def _set_input(node, names, value):
    sock = _get_input(node, names)
    if sock is not None:
        sock.default_value = value


def grid_surface(name, size_x, size_y, nx, ny, height_fn, smooth=True, subsurf=1):
    """Create a grid mesh and displace its vertices with height_fn(x, y) -> z."""
    import numpy as np
    mesh = bpy.data.meshes.new(name)
    xs = np.linspace(-size_x / 2, size_x / 2, nx)
    ys = np.linspace(-size_y / 2, size_y / 2, ny)
    X, Y = np.meshgrid(xs, ys)
    Z = height_fn(X, Y)
    verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    faces = []
    for j in range(ny - 1):
        row = j * nx
        for i in range(nx - 1):
            a = row + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    mesh.from_pydata(verts.tolist(), [], faces)
    mesh.update()
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    if subsurf:
        mod = ob.modifiers.new("Subsurf", "SUBSURF")
        mod.levels = subsurf
        mod.render_levels = subsurf
    return ob


def render_to(path):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
