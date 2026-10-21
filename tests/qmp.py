#!/usr/bin/env python3
"""Tiny QMP client to drive a QEMU test VM: screenshots, mouse and keyboard.

    qmp.py SOCK shot out.png
    qmp.py SOCK click X Y [--screen WxH] [--button left|right] [--double]
    qmp.py SOCK move X Y [--screen WxH]
    qmp.py SOCK key ctrl-alt-t            (QEMU qcode names joined by '-')
    qmp.py SOCK type "some text"
    qmp.py SOCK scroll X Y AMOUNT         (negative = up)
    qmp.py SOCK cmd '{"execute": "query-status"}'

Pointer coordinates are in screen pixels; they are converted to the absolute
0..32767 range of the usb-tablet device. The screen size is taken from the
last screenshot (saved next to the socket) unless --screen is given.
"""
import json
import os
import socket
import struct
import sys
import time
import zlib

KEYMAP = {
    " ": "spc", "\n": "ret", "\t": "tab", "-": "minus", "=": "equal", "[": "bracket_left",
    "]": "bracket_right", ";": "semicolon", "'": "apostrophe", "`": "grave_accent", "\\": "backslash",
    ",": "comma", ".": "dot", "/": "slash",
}
SHIFTED = {
    "_": "minus", "+": "equal", "{": "bracket_left", "}": "bracket_right", ":": "semicolon",
    '"': "apostrophe", "~": "grave_accent", "|": "backslash", "<": "comma", ">": "dot", "?": "slash",
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
}


class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.buf = b""
        self._read()  # greeting
        self.cmd("qmp_capabilities")

    def _read(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("QMP socket closed")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def cmd(self, name, **args):
        msg = {"execute": name}
        if args:
            msg["arguments"] = args
        self.sock.sendall(json.dumps(msg).encode() + b"\n")
        while True:
            reply = self._read()
            if "return" in reply:
                return reply["return"]
            if "error" in reply:
                raise RuntimeError(reply["error"])
            # asynchronous events are ignored


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def screen_size(sock_path, args):
    if "--screen" in args:
        w, h = args[args.index("--screen") + 1].lower().split("x")
        return int(w), int(h)
    marker = sock_path + ".lastshot"
    if os.path.exists(marker):
        with open(marker) as f:
            w, h = f.read().split()
            return int(w), int(h)
    return 1920, 1080


def abs_event(x, y, size):
    w, h = size
    return [
        {"type": "abs", "data": {"axis": "x", "value": int(x * 32767 / max(w - 1, 1))}},
        {"type": "abs", "data": {"axis": "y", "value": int(y * 32767 / max(h - 1, 1))}},
    ]


def btn(button, down):
    return {"type": "btn", "data": {"button": button, "down": down}}


def main():
    sock_path, action, *rest = sys.argv[1:]
    q = QMP(sock_path)
    if action == "shot":
        out = os.path.abspath(rest[0])
        tmp = out + ".ppm"
        try:
            q.cmd("screendump", filename=out, format="png")
        except RuntimeError:
            q.cmd("screendump", filename=tmp)
            os.replace(tmp, out)
        for _ in range(50):
            if os.path.exists(out) and os.path.getsize(out) > 0:
                break
            time.sleep(0.1)
        if out.endswith(".png"):
            w, h = png_size(out)
            with open(sock_path + ".lastshot", "w") as f:
                f.write(f"{w} {h}")
            print(f"{out} {w}x{h}")
    elif action in ("click", "move"):
        x, y = float(rest[0]), float(rest[1])
        size = screen_size(sock_path, rest)
        q.cmd("input-send-event", events=abs_event(x, y, size))
        if action == "click":
            button = rest[rest.index("--button") + 1] if "--button" in rest else "left"
            clicks = 2 if "--double" in rest else 1
            for _ in range(clicks):
                time.sleep(0.08)
                q.cmd("input-send-event", events=[btn(button, True)])
                time.sleep(0.06)
                q.cmd("input-send-event", events=[btn(button, False)])
    elif action == "scroll":
        x, y, amount = float(rest[0]), float(rest[1]), int(rest[2])
        q.cmd("input-send-event", events=abs_event(x, y, screen_size(sock_path, rest)))
        b = "wheel-up" if amount < 0 else "wheel-down"
        for _ in range(abs(amount)):
            q.cmd("input-send-event", events=[btn(b, True)])
            q.cmd("input-send-event", events=[btn(b, False)])
            time.sleep(0.03)
    elif action == "key":
        keys = [{"type": "qcode", "data": k} for k in rest[0].split("-")]
        q.cmd("send-key", keys=keys, **{"hold-time": 80})
    elif action in ("type", "typefile"):
        text = rest[0]
        if action == "typefile":
            with open(rest[0], encoding="utf-8") as f:
                text = f.read().rstrip("\n")
        for ch in text:
            if ch.isalpha() and ch.isupper():
                keys = ["shift", ch.lower()]
            elif ch.isalnum():
                keys = [ch]
            elif ch in KEYMAP:
                keys = [KEYMAP[ch]]
            elif ch in SHIFTED:
                keys = ["shift", SHIFTED[ch]]
            else:
                raise SystemExit(f"cannot type {ch!r}")
            # send-key returns before the key is released; wait well past the
            # hold time or the guest merges/drops keystrokes
            q.cmd("send-key", keys=[{"type": "qcode", "data": k} for k in keys], **{"hold-time": 25})
            time.sleep(0.07)
    elif action == "cmd":
        msg = json.loads(rest[0])
        print(json.dumps(q.cmd(msg["execute"], **msg.get("arguments", {})), indent=1))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
