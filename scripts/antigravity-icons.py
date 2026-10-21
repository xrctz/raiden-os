#!/usr/bin/env python3
"""Make desktop icons for Google Antigravity from the vendored release tarballs.

    antigravity-icons.py APP.tar.gz IDE.tar.gz OUTDIR

Writes OUTDIR/<size>/antigravity.png and antigravity-ide.png (hicolor sizes).
The app's icon (icon.png inside app.asar) is used as it is; the IDE's square
dark tile (resources/linux/code.png) gets rounded corners like other app icons.

Needs ImageMagick 7 (magick).
"""
import json
import os
import struct
import subprocess
import sys
import tarfile
import tempfile

SIZES = (512, 256, 128, 64, 48, 32)


def run(*cmd, data=None):
    return subprocess.run([str(c) for c in cmd], input=data, check=True,
                          capture_output=True).stdout


def asar_file(asar_bytes, want):
    """Read one file from an Electron app.asar archive."""
    _, header_size, _, json_len = struct.unpack("<4I", asar_bytes[:16])
    header = json.loads(asar_bytes[16:16 + json_len])
    node = header
    for part in want.split("/"):
        node = node["files"][part]
    start = 8 + header_size + int(node["offset"])
    return asar_bytes[start:start + node["size"]]


def member(tarball, suffix):
    with tarfile.open(tarball) as tar:
        for m in tar.getmembers():
            if m.name.endswith(suffix):
                return tar.extractfile(m).read()
    raise SystemExit(f"{suffix} not found in {tarball}")


def main():
    app_tar, ide_tar, out = sys.argv[1:4]
    with tempfile.TemporaryDirectory() as tmp:
        # app: Google's icon as it is (a white rounded tile on transparency)
        app = os.path.join(tmp, "antigravity.png")
        run("magick", "png:-", "-resize", "512x512", app,
            data=asar_file(member(app_tar, "/resources/app.asar"), "icon.png"))
        # IDE: its dark tile with rounded corners, a little inset
        tile = os.path.join(tmp, "tile.png")
        run("magick", "png:-", "-resize", "512x512", tile,
            data=member(ide_tar, "/resources/app/resources/linux/code.png"))
        mask = os.path.join(tmp, "mask.png")
        run("magick", "-size", "512x512", "xc:black", "-fill", "white",
            "-draw", "roundrectangle 0,0,511,511,112,112", mask)
        ide = os.path.join(tmp, "antigravity-ide.png")
        run("magick", tile, "(", mask, "-alpha", "copy", ")", "-compose", "DstIn", "-composite",
            "-compose", "Over", "-resize", "456x456", "-background", "none",
            "-gravity", "center", "-extent", "512x512", ide)
        for size in SIZES:
            d = os.path.join(out, f"{size}x{size}")
            os.makedirs(d, exist_ok=True)
            for src in (app, ide):
                run("magick", src, "-filter", "Lanczos", "-resize", f"{size}x{size}",
                    os.path.join(d, os.path.basename(src)))
    print(f"antigravity icons: {', '.join(str(s) for s in SIZES)} px")


if __name__ == "__main__":
    main()
