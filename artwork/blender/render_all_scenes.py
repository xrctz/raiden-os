"""Render every 3D scene wallpaper and the ultrawide versions of the ribbon
wallpapers, headless:

    blender -b --factory-startup --python artwork/blender/render_all_scenes.py [-- NAME...]

NAMEs pick jobs by output file name (e.g. "storm-bg arcane"); none renders all.
"""
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
RENDERS = os.path.join(os.path.dirname(HERE), "renders")
CHAR, WALL = os.path.join(RENDERS, "characters"), os.path.join(RENDERS, "wallpapers")

# (scene, output, width, height, horizontal position of the hero)
SCENE_JOBS = [
    # character backgrounds: the hero frames the character's picture
    ("arcane", os.path.join(CHAR, "arcane-bg.png"), 2560, 1600, 1930 / 2560),
    ("arcane", os.path.join(CHAR, "arcane-bg-ultrawide.png"), 3440, 1440, 2408 / 3440),
    ("storm", os.path.join(CHAR, "storm-bg.png"), 2560, 1600, 1930 / 2560),
    ("storm", os.path.join(CHAR, "storm-bg-ultrawide.png"), 3440, 1440, 2408 / 3440),
    # wallpapers
    ("arcane", os.path.join(WALL, "arcane.png"), 3840, 2160, 0.5),
    ("arcane", os.path.join(WALL, "arcane-ultrawide.png"), 3440, 1440, 0.5),
    ("storm", os.path.join(WALL, "storm.png"), 3840, 2160, 0.5),
    ("storm", os.path.join(WALL, "storm-ultrawide.png"), 3440, 1440, 0.5),
    ("crimson", os.path.join(WALL, "crimson.png"), 3840, 2160, 0.5),
    ("crimson", os.path.join(WALL, "crimson-ultrawide.png"), 3440, 1440, 0.5),
]
RIBBON_JOBS = ["aurora-dark", "aurora-light", "nebula-dark", "lagoon-dark"]


def wanted(path):
    names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return not names or os.path.splitext(os.path.basename(path))[0] in names


def main():
    ns = {"__file__": os.path.join(HERE, "wallpaper_scenes.py")}
    exec(open(ns["__file__"], encoding="utf-8").read(), ns)
    for scene, path, w, h, fx in SCENE_JOBS:
        if wanted(path):
            t = time.time()
            ns["render_scene"](scene, path, w, h, focus=(fx, 0.5), samples=256)
            print(f"rendered {os.path.basename(path)} in {time.time() - t:.0f} s", flush=True)

    # ribbons: same look as the 4K versions; the camera keeps their vertical
    # view, so 21:9 shows more of the sides instead of less of the top
    rs = {"__file__": os.path.join(HERE, "wallpaper_ribbons.py")}
    exec(open(rs["__file__"], encoding="utf-8").read(), rs)
    for name in RIBBON_JOBS:
        path = os.path.join(WALL, f"{name}-ultrawide.png")
        if not wanted(path):
            continue
        t = time.time()
        bpy.context.scene.compositing_node_group = None
        cfg = rs["build_wallpaper"](name)
        cam = bpy.context.scene.camera.data
        cam.sensor_fit, cam.sensor_height, cam.lens = "VERTICAL", 24.0, 45.0
        rs["setup_render"](3440, 1440, samples=256, view=cfg.get("view", "AgX"), look=cfg["look"],
                           exposure=cfg["exposure"])
        rs["render_to"](path)
        print(f"rendered {os.path.basename(path)} in {time.time() - t:.0f} s", flush=True)


main()
