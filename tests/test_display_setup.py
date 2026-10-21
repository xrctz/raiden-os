#!/usr/bin/env python3
"""Unit test for display-setup's refresh-rate and wallpaper choices.

The monitors are typical of a gaming desktop (modes as their EDIDs list
them): a 3440x1440 ultrawide (60/100/120 Hz) and a 1920x1080 screen
(60/144/165/180 Hz), both started by GNOME at 60 Hz.

    python3 tests/test_display_setup.py
"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "packages", "raiden-os-settings", "root",
                      "usr", "libexec", "raiden-os", "display-setup")
loader = importlib.machinery.SourceFileLoader("display_setup", SCRIPT)
spec = importlib.util.spec_from_loader("display_setup", loader)
ds = importlib.util.module_from_spec(spec)
loader.exec_module(ds)


def mode(w, h, hz, current=False, vrr=False, scales=(1.0, 1.25, 1.5, 2.0)):
    props = {}
    if current:
        props["is-current"] = True
    if vrr:
        props["refresh-rate-mode"] = "variable"
    return (f"{w}x{h}@{hz:.3f}" + ("+vrr" if vrr else ""), w, h, hz, 1.0, list(scales), props)


ULTRAWIDE = ds.Monitor(("DP-1", "UWD", "UW34 120", "0000000001"),
                  [mode(3440, 1440, 120.0), mode(3440, 1440, 120.0, vrr=True),
                   mode(3440, 1440, 100.0), mode(3440, 1440, 60.0, current=True),
                   mode(2560, 1080, 60.0)], {"display-name": "Ultrawide 34\""})
FAST = ds.Monitor(("HDMI-1", "FHD", "FHD24 180", "0000000002"),
                  [mode(1920, 1080, 180.003), mode(1920, 1080, 165.0), mode(1920, 1080, 144.0),
                   mode(1920, 1080, 60.0, current=True), mode(1280, 720, 60.0)],
                  {"display-name": "Gaming 24\""})
LOGICAL = [(1920, 0, 1.0, 0, True, [ULTRAWIDE.spec], {}),
           (0, 106, 1.0, 0, False, [FAST.spec], {})]


def test_fastest_modes():
    config, changes = ds.plan_max_refresh([ULTRAWIDE, FAST], LOGICAL)
    picked = {e[0]: e[1] for lm in config for e in lm[5]}
    assert picked == {"DP-1": "3440x1440@120.000", "HDMI-1": "1920x1080@180.003"}, picked
    assert [lm[:5] for lm in config] == [(1920, 0, 1.0, 0, True), (0, 106, 1.0, 0, False)]
    assert changes == ["DP-1 60 -> 120 Hz", "HDMI-1 60 -> 180 Hz"], changes


def test_nothing_to_do_at_max():
    fast = ds.Monitor(ULTRAWIDE.spec, [mode(3440, 1440, 120.0, current=True),
                                  mode(3440, 1440, 60.0)], {})
    assert ds.plan_max_refresh([fast], [LOGICAL[0][:5] + ([fast.spec], {})]) is None


def test_scale_must_be_supported():
    odd = ds.Monitor(FAST.spec, [mode(1920, 1080, 60.0, current=True),
                                 mode(1920, 1080, 144.0, scales=(1.0,))], {})
    lm = [(0, 0, 1.25, 0, True, [odd.spec], {})]
    assert ds.plan_max_refresh([odd], lm) is None


def test_configured_sets_and_key():
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "monitors.xml"), "w") as f:
            f.write("""<monitors version="2"><configuration><logicalmonitor>
              <monitor><monitorspec><connector>DP-1</connector><vendor>UWD</vendor>
              <product>UW34 120</product><serial>0000000001</serial></monitorspec>
              </monitor></logicalmonitor><logicalmonitor><monitor><monitorspec>
              <connector>HDMI-1</connector><vendor>FHD</vendor><product>FHD24 180</product>
              <serial>0000000002</serial></monitorspec></monitor></logicalmonitor>
              </configuration></monitors>""")
        ds.monitors_xml = lambda: os.path.join(tmp, "monitors.xml")
        sets = ds.configured_sets()
    assert ds.set_key([ULTRAWIDE, FAST]) in sets, sets
    assert ds.set_key([ULTRAWIDE]) not in sets


def test_save_configuration():
    config, _changes = ds.plan_max_refresh([ULTRAWIDE, FAST], LOGICAL)
    with tempfile.TemporaryDirectory() as tmp:
        ds.monitors_xml = lambda: os.path.join(tmp, "monitors.xml")
        # an existing configuration for another monitor set must survive
        with open(os.path.join(tmp, "monitors.xml"), "w") as f:
            f.write('<monitors version="2"><configuration><logicalmonitor><x>0</x><y>0</y>'
                    '<scale>1</scale><primary>yes</primary><monitor><monitorspec>'
                    '<connector>eDP-1</connector><vendor>BOE</vendor><product>0x0a1c</product>'
                    '<serial>0x0</serial></monitorspec><mode><width>2560</width>'
                    '<height>1600</height><rate>165.000</rate></mode></monitor>'
                    '</logicalmonitor></configuration></monitors>')
        ds.save_configuration([ULTRAWIDE, FAST], config, 1)
        xml = open(os.path.join(tmp, "monitors.xml")).read()
        sets = ds.configured_sets()
    assert ds.set_key([ULTRAWIDE, FAST]) in sets and len(sets) == 2, sets
    for needle in ("<layoutmode>logical</layoutmode>", "<rate>120.000</rate>",
                   "<rate>180.003</rate>", "<x>1920</x>", "<y>106</y>", "<primary>yes</primary>",
                   "<product>UW34 120</product>", "<rate>165.000</rate>"):
        assert needle in xml, needle


def test_ultrawide_and_variants():
    assert ds.primary_is_ultrawide([ULTRAWIDE, FAST], LOGICAL) is True
    swapped = [(0, 0, 1.0, 0, True, [FAST.spec], {})]
    assert ds.primary_is_ultrawide([ULTRAWIDE, FAST], swapped) is False
    with tempfile.TemporaryDirectory() as tmp:
        ds.WALLPAPER_DIR = tmp + "/"
        for name in ("aurora-dark.jpg", "aurora-dark-ultrawide.jpg", "plain.jpg"):
            open(os.path.join(tmp, name), "w").close()
        base, wide = f"file://{tmp}/aurora-dark.jpg", f"file://{tmp}/aurora-dark-ultrawide.jpg"
        assert ds.wallpaper_variant(base, True) == wide
        assert ds.wallpaper_variant(wide, False) == base
        assert ds.wallpaper_variant(f"file://{tmp}/plain.jpg", True) == f"file://{tmp}/plain.jpg"
        assert ds.wallpaper_variant("file:///home/u/me.png", True) == "file:///home/u/me.png"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    sys.exit(0)
