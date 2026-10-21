#!/usr/bin/env python3
"""Raiden OS character themes: wallpapers, preview, avatar and effects per
character.

    make-characters.py SRC_DIR OUTDIR

Character art is usually copyrighted and always personal, so nothing about
the characters is in git: each one is a folder SRC_DIR/personal/characters/<id>/
on the build PC with the picture, art.<png|jpg|jpeg|webp>, and theme.json:

    {"order": 1, "name": "First Last", "lines": ["First", "Last"],
     "series": "Where they are from", "style": "card", "accent": "yellow",
     "desktop_text": "light",
     "colors": {"top": "#FFF3CC", "bottom": "#E3A43D", "sub": "#E9DAFF",
                "line": "#EBC56C", "glow": "#F2C66B"},
     "avatar": [155, 50, 180], "art_crop": null,
     "effects": {"open": {"effect": "hexagon", ...}, "close": {...}}}

avatar and art_crop are x, y, size squares of the art (the profile picture,
and what goes into the frame; null: all of it); "full" pictures may give
"face": [x, y] as fractions of the art for the login screen version; effects
are Burn My Windows effects with their settings. With no characters nothing
is written and Raiden OS simply ships without character themes.

Styles:
  card      the art in a glowing card, in front of the Blender scene's magic
            circle (artwork/blender/wallpaper_scenes.py "arcane")
  portrait  the art in a round frame inside the scene's lightning ring ("storm")
  full      the art already is a complete wallpaper and is used as it is
"card" and "portrait" sit over artwork/renders/characters/<scene>-bg[-ultrawide].png
with the name on the left. Every wallpaper comes twice: <id>.jpg (16:10) and
<id>-ultrawide.jpg (3440x1440, laid out so a 16:9 crop of it still shows the
name and the picture); display-setup picks the one that fits the main monitor.
Each character also gets <id>-preview.jpg (480x300), <id>-avatar.png
(256x256) and <id>.json (with its window effects), "full" ones also
<id>-login[-ultrawide].jpg (login screen versions, see login_image()); GNOME's
background chooser gets raiden-os-characters.xml.

Needs rsvg-convert, ImageMagick 7 (magick) and the Inter fonts.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WALLPAPER_DIR = "/usr/share/backgrounds/raiden-os/characters"
DATA_DIR = "/usr/share/raiden-os/characters"


class Canvas:
    """A wallpaper size. Sizes were designed on the 1600 px tall 16:10 canvas
    and scale with the height; the picture sits right of the login screen's
    centred user list, the name on the left."""

    def __init__(self, suffix, w, h, cx, name_x):
        self.suffix, self.W, self.H = suffix, w, h
        self.k = h / 1600
        self.CX, self.CY = cx, h // 2
        self.name_x = name_x

    def s(self, v):
        return round(v * self.k)


CANVASES = [
    Canvas("", 2560, 1600, 1930, 220),
    # 21:9; the centre 16:9 (x 440..3000) shows on 16:9 screens too
    Canvas("-ultrawide", 3440, 1440, 2408, 560),
]
# The Blender scenes frame their hero at (CX/W, 0.5) with a 26 degree
# vertical view: the storm ring (1.35 m at 15 m) is 0.195 H in radius.
STORM_RING = 0.195
# the scene rendered behind each style (artwork/blender/render_all_scenes.py)
BACKGROUNDS = {"card": "arcane", "portrait": "storm"}


def load_characters(src_dir):
    """The characters in SRC_DIR/personal/characters/*/theme.json, in order."""
    found = []
    for theme in sorted((src_dir / "personal" / "characters").glob("*/theme.json")):
        c = json.loads(theme.read_text(encoding="utf-8"))
        c["id"] = theme.parent.name
        found.append(c)
    return sorted(found, key=lambda c: (c.get("order", 999), c["id"]))




def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def find_art(src_dir, cid):
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = src_dir / "personal" / "characters" / cid / f"art.{ext}"
        if p.is_file():
            return p
    return None


def image_size(path):
    out = subprocess.run(["magick", "identify", "-format", "%w %h", f"{path}[0]"],
                         check=True, capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1])


def fit(src, w, h, out):
    """Scale (Lanczos, lightly sharpened) and centre-crop SRC to exactly WxH."""
    run("magick", src, "-filter", "Lanczos", "-resize", f"{w}x{h}^", "-gravity", "center",
        "-extent", f"{w}x{h}", "+repage", "-unsharp", "0x0.8+0.6+0.02", out)


# ----------------------------------------------------------------------- SVG
def defs(cv, colors):
    s = cv.s
    return f'''<defs>
  <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#040208" stop-opacity="0.75"/>
    <stop offset="0.38" stop-color="#040208" stop-opacity="0.35"/>
    <stop offset="0.6" stop-color="#040208" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="nameFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{colors['top']}"/>
    <stop offset="1" stop-color="{colors['bottom']}"/>
  </linearGradient>
  <filter id="wide" x="-30%" y="-30%" width="160%" height="160%">
    <feGaussianBlur stdDeviation="{s(16)}"/>
  </filter>
  <filter id="textGlow" x="-10%" y="-40%" width="120%" height="180%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="{s(18)}" result="b"/>
    <feFlood flood-color="{colors['glow']}" flood-opacity="0.35"/>
    <feComposite in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="shadow" x="-30%" y="-30%" width="160%" height="170%">
    <feDropShadow dx="0" dy="{s(26)}" stdDeviation="{s(32)}" flood-color="#000000" flood-opacity="0.7"/>
  </filter>
</defs>'''


def name_block(cv, c):
    s, col = cv.s, c["colors"]
    first, last = c["lines"]
    x, y = cv.name_x, s(690)
    return f'''<g font-family="Inter Display" font-weight="700" font-size="{s(150)}" letter-spacing="{-s(3)}"
   fill="url(#nameFill)" filter="url(#textGlow)">
  <text x="{x}" y="{y}">{first}</text>
  <text x="{x}" y="{y + s(165)}">{last}</text>
</g>
<rect x="{x + s(6)}" y="{y + s(218)}" width="{s(150)}" height="{s(6)}" rx="{s(3)}" fill="{col['line']}"/>
<text x="{x + s(4)}" y="{y + s(300)}" font-family="Inter Display" font-weight="500" font-size="{s(48)}"
   letter-spacing="{s(5)}" fill="{col['sub']}">{c['series']}</text>'''


def svg_open(cv, col):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{cv.W}" height="{cv.H}" viewBox="0 0 {cv.W} {cv.H}">
{defs(cv, col)}
<image href="bg.png" x="0" y="0" width="{cv.W}" height="{cv.H}" preserveAspectRatio="none"/>
<rect width="{cv.W}" height="{cv.H}" fill="url(#shade)"/>'''


def card_size(cv):
    ch = round(0.541 * cv.H)
    return round(ch * 0.8776), ch


def svg_card(cv, c):
    col, s = c["colors"], cv.s
    cw, ch = card_size(cv)
    x0, y0, r = cv.CX - cw // 2, cv.CY - ch // 2, s(36)
    return f'''{svg_open(cv, col)}
<clipPath id="frame"><rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" rx="{r}"/></clipPath>
<rect x="{x0 - s(8)}" y="{y0 - s(8)}" width="{cw + s(16)}" height="{ch + s(16)}" rx="{r + s(8)}" fill="none"
   stroke="{col['glow']}" stroke-width="{s(14)}" opacity="0.8" filter="url(#wide)"/>
<rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" rx="{r}" fill="#000000" filter="url(#shadow)"/>
<image href="art.png" x="{x0}" y="{y0}" width="{cw}" height="{ch}" clip-path="url(#frame)"/>
<rect x="{x0}" y="{y0}" width="{cw}" height="{ch}" rx="{r}" fill="none" stroke="{col['line']}" stroke-width="{s(4)}"/>
{name_block(cv, c)}
</svg>'''


def portrait_radius(cv):
    return round(STORM_RING * cv.H * 0.86)


def svg_portrait(cv, c):
    col, s = c["colors"], cv.s
    r = portrait_radius(cv)
    return f'''{svg_open(cv, col)}
<clipPath id="frame"><circle cx="{cv.CX}" cy="{cv.CY}" r="{r}"/></clipPath>
<circle cx="{cv.CX}" cy="{cv.CY}" r="{r + s(8)}" fill="none" stroke="{col['glow']}" stroke-width="{s(16)}"
   opacity="0.8" filter="url(#wide)"/>
<circle cx="{cv.CX}" cy="{cv.CY}" r="{r}" fill="#000000" filter="url(#shadow)"/>
<image href="art.png" x="{cv.CX - r}" y="{cv.CY - r}" width="{2 * r}" height="{2 * r}" clip-path="url(#frame)"/>
<circle cx="{cv.CX}" cy="{cv.CY}" r="{r}" fill="none" stroke="#F4EEFF" stroke-width="{s(5)}"/>
{name_block(cv, c)}
</svg>'''


def render_svg(cv, svg, tmp, out_jpg):
    (tmp / "w.svg").write_text(svg, encoding="utf-8")
    run("rsvg-convert", "-w", cv.W, "-h", cv.H, tmp / "w.svg", "-o", tmp / "w.png")
    run("magick", tmp / "w.png", "-quality", "92", "-sampling-factor", "4:4:4", out_jpg)


def login_image(cv, art, face, tmp, out_jpg, zoom=1.2, target=(0.30, 0.42)):
    """Login screen version of a full-picture wallpaper. The login screen puts
    the user list in the middle, so the picture is zoomed and moved until the
    face (FACE, fractions of the art) sits left of it, and dark bands at the top
    and bottom keep the clock, the status icons and the logo readable."""
    W, H = cv.W, cv.H
    w0, h0 = image_size(art)
    s = max(W / w0, H / h0) * zoom
    sw, sh = round(w0 * s), round(h0 * s)
    ox = min(0, max(W - sw, round(target[0] * W - face[0] * sw)))
    oy = min(0, max(H - sh, round(target[1] * H - face[1] * sh)))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="top" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#000000" stop-opacity="0.6"/>
    <stop offset="1" stop-color="#000000" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="bottom" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#000000" stop-opacity="0"/>
    <stop offset="1" stop-color="#000000" stop-opacity="0.62"/>
  </linearGradient>
</defs>
<image href="big.png" x="{ox}" y="{oy}" width="{sw}" height="{sh}" preserveAspectRatio="none"/>
<rect x="0" y="0" width="{W}" height="{cv.s(190)}" fill="url(#top)"/>
<rect x="0" y="{H - cv.s(300)}" width="{W}" height="{cv.s(300)}" fill="url(#bottom)"/>
</svg>'''
    run("magick", art, "-filter", "Lanczos", "-resize", f"{sw}x{sh}!", tmp / "big.png")
    render_svg(cv, svg, tmp, out_jpg)


def full_ultrawide(cv, art, tmp, out_jpg):
    """A 16:9 picture on a 21:9 screen: the whole picture in the middle (exactly
    what a 16:9 screen shows of it), the sides filled with a blurred, darker
    copy that melts into it."""
    W, H = cv.W, cv.H
    w0, h0 = image_size(art)
    fw = round(w0 * H / h0)                       # picture width at full height
    feather = cv.s(260)
    # (darken with a plain multiply: -modulate works in HSL, where near-white
    # pixels have random hues that turn into coloured contour lines)
    run("magick", art, "-filter", "Lanczos", "-resize", f"{W}x{H}^", "-gravity", "center",
        "-extent", f"{W}x{H}", "-blur", "0x60", "-channel", "RGB", "-evaluate", "multiply",
        "0.9", "+channel", tmp / "fill.png")
    run("magick", art, "-filter", "Lanczos", "-resize", f"{fw}x{H}!", "-unsharp", "0x0.8+0.5+0.02",
        tmp / "mid.png")
    # alpha: opaque, fading out over FEATHER pixels at the left and right edges
    run("magick", "-size", f"{fw}x{H}", "gradient:white-white",
        "(", "-size", f"{H}x{feather}", "gradient:black-white", "-rotate", "-90", ")",
        "-gravity", "west", "-composite",
        "(", "-size", f"{H}x{feather}", "gradient:black-white", "-rotate", "90", ")",
        "-gravity", "east", "-composite", tmp / "mask.png")
    run("magick", tmp / "mid.png", tmp / "mask.png", "-alpha", "off", "-compose", "copy_opacity",
        "-composite", tmp / "mid-a.png")
    run("magick", tmp / "fill.png", tmp / "mid-a.png", "-gravity", "center", "-compose", "over",
        "-composite", "-quality", "92", "-sampling-factor", "4:4:4", out_jpg)


# ---------------------------------------------------------------------- main
def build(c, art, src_dir, out):
    cid = c["id"]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        framed = art                    # what goes into the frame (avatar crops use the original)
        if c.get("art_crop"):
            x, y, size = c["art_crop"]
            framed = tmp / "crop.png"
            run("magick", art, "-crop", f"{size}x{size}+{x}+{y}", "+repage", framed)
        login = None
        for cv in CANVASES:
            wallpaper = out / f"{cid}{cv.suffix}.jpg"
            if c["style"] == "full":
                if cv.suffix:
                    full_ultrawide(cv, art, tmp, wallpaper)
                else:
                    run("magick", art, "-quality", "95", "-sampling-factor", "4:4:4", wallpaper)
                zoom = 1.2 if not cv.suffix else 1.0
                login_image(cv, art, c.get("face", (0.5, 0.35)), tmp,
                            out / f"{cid}-login{cv.suffix}.jpg", zoom=zoom)
                login = f"{WALLPAPER_DIR}/{cid}-login.jpg"
                continue
            scene = c.get("background", BACKGROUNDS[c["style"]])
            bg = src_dir / "artwork" / "renders" / "characters" / f"{scene}-bg{cv.suffix}.png"
            shutil.copy(bg, tmp / "bg.png")
            if c["style"] == "card":
                fit(framed, *card_size(cv), tmp / "art.png")
                svg = svg_card(cv, c)
            else:
                d = 2 * portrait_radius(cv)
                fit(framed, d, d, tmp / "art.png")
                svg = svg_portrait(cv, c)
            render_svg(cv, svg, tmp, wallpaper)
    run("magick", out / f"{cid}.jpg", "-resize", "480x300^", "-gravity", "center", "-extent",
        "480x300", "-quality", "90", out / f"{cid}-preview.jpg")
    if c.get("avatar"):
        x, y, s = c["avatar"]
        run("magick", art, "-crop", f"{s}x{s}+{x}+{y}", "+repage", "-filter", "Lanczos",
            "-resize", "256x256", out / f"{cid}-avatar.png")
    else:
        fit(art, 256, 256, out / f"{cid}-avatar.png")
    meta = {k: c[k] for k in ("id", "name", "series", "accent", "desktop_text", "effects")}
    meta.update(wallpaper=f"{WALLPAPER_DIR}/{cid}.jpg", login=login or f"{WALLPAPER_DIR}/{cid}.jpg",
                preview=f"{DATA_DIR}/{cid}-preview.jpg", avatar=f"{DATA_DIR}/{cid}-avatar.png")
    return meta


def main():
    src_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    built = []
    for order, c in enumerate(load_characters(src_dir), 1):
        art = find_art(src_dir, c["id"])
        if not art:
            continue
        out.mkdir(parents=True, exist_ok=True)
        meta = build(c, art, src_dir, out)
        meta["order"] = order
        (out / f"{c['id']}.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        built.append(meta)
        print(f"character theme: {c['id']}")
    if built:
        items = "".join(f'''  <wallpaper deleted="false">
    <name>{m['name']}</name>
    <filename>{m['wallpaper']}</filename>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#000000</pcolor>
    <scolor>#000000</scolor>
  </wallpaper>
''' for m in built)
        (out / "raiden-os-characters.xml").write_text(
            '<?xml version="1.0"?>\n<!DOCTYPE wallpapers SYSTEM "gnome-wp-list.dtd">\n'
            f"<wallpapers>\n{items}</wallpapers>\n", encoding="utf-8")


if __name__ == "__main__":
    main()
