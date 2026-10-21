"""Desktop layouts and look-and-feel settings for @DISTRO_NAME@.

Everything here works through GSettings, so changes apply live in a running
GNOME session and are also usable from the command line:

    raiden-appearance --layout windows
"""
import json
import os

from gi.repository import Gio, GLib

# Extension UUIDs ------------------------------------------------------------
DASH_TO_PANEL = "dash-to-panel@jderose9.github.com"
ARCMENU = "arcmenu@arcmenu.com"
UBUNTU_DOCK = "ubuntu-dock@ubuntu.com"
BLUR = "blur-my-shell@aunetx"
DESKTOP_ICONS = "ding@rastersoft.com"
MAGIC_LAMP = "compiz-alike-magic-lamp-effect@hermes83.github.com"
DESKTOP_CUBE = "desktop-cube@schneegans.github.com"
CAFFEINE = "caffeine@patapon.info"
APPINDICATOR = "ubuntu-appindicators@ubuntu.com"
WINDOW_EFFECTS = "burn-my-windows@schneegans.github.com"
WOBBLY = "compiz-windows-effect@hermes83.github.com"

SHELL = "org.gnome.shell"
IFACE = "org.gnome.desktop.interface"
WM = "org.gnome.desktop.wm.preferences"
BACKGROUND = "org.gnome.desktop.background"
SCREENSAVER = "org.gnome.desktop.screensaver"
DTP = "org.gnome.shell.extensions.dash-to-panel"
ARC = "org.gnome.shell.extensions.arcmenu"
DOCK = "org.gnome.shell.extensions.dash-to-dock"
DING = "org.gnome.shell.extensions.ding"

WALLPAPER_DIR = "/usr/share/backgrounds/raiden-os"

ACCENT_COLORS = [
    # (gsettings value, label, hex used for the swatch)
    ("blue", "Blue", "#3584e4"),
    ("teal", "Teal", "#2190a4"),
    ("green", "Green", "#3a944a"),
    ("yellow", "Yellow", "#c88800"),
    ("orange", "Orange", "#ed5b00"),
    ("red", "Red", "#e62d42"),
    ("pink", "Pink", "#d56199"),
    ("purple", "Purple", "#9141ac"),
    ("slate", "Slate", "#6f8396"),
]

WALLPAPERS = [
    # (id, label, light file, dark file)
    ("aurora", "Aurora", "aurora-light.jpg", "aurora-dark.jpg"),
    ("aurora-night", "Aurora Night", "aurora-dark.jpg", "aurora-dark.jpg"),
    ("nebula", "Nebula", "nebula-dark.jpg", "nebula-dark.jpg"),
    ("lagoon", "Lagoon", "lagoon-dark.jpg", "lagoon-dark.jpg"),
    ("arcane", "Arcane", "arcane.jpg", "arcane.jpg"),
    ("storm", "Storm", "storm.jpg", "storm.jpg"),
    ("crimson", "Crimson King", "crimson.jpg", "crimson.jpg"),
]

ICON_ANIMATIONS = [
    # (Dash to Panel hover animation, label); None switches it off
    (None, "Off"),
    ("SIMPLE", "Lift"),
    ("RIPPLE", "Ripple"),
    ("PLANK", "Magnify"),
]

PREFS = os.path.join(GLib.get_user_config_dir(), "raiden-appearance", "appearance.json")


def load_prefs():
    try:
        with open(PREFS, encoding="utf-8") as f:
            prefs = json.load(f)
        return prefs if isinstance(prefs, dict) else {}
    except (OSError, ValueError):
        return {}


def save_prefs(prefs):
    os.makedirs(os.path.dirname(PREFS), exist_ok=True)
    with open(PREFS, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


# ---------------------------------------------------------------- GSettings
def _source():
    return Gio.SettingsSchemaSource.get_default()


def has_schema(schema_id):
    src = _source()
    return src is not None and src.lookup(schema_id, True) is not None


def settings(schema_id):
    """Gio.Settings for schema_id, or None when the schema is not installed."""
    if not has_schema(schema_id):
        return None
    return Gio.Settings.new(schema_id)


def set_key(schema_id, key, value):
    """Set a key only if schema and key exist; value is a GLib.Variant or python value."""
    s = settings(schema_id)
    if s is None or not s.props.settings_schema.has_key(key):
        return False
    from gi.repository import GLib
    if isinstance(value, GLib.Variant):
        return s.set_value(key, value)
    vtype = s.props.settings_schema.get_key(key).get_value_type().dup_string()
    return s.set_value(key, GLib.Variant(vtype, value))


def get_key(schema_id, key, default=None):
    s = settings(schema_id)
    if s is None or not s.props.settings_schema.has_key(key):
        return default
    return s.get_value(key).unpack()


def reset_key(schema_id, key):
    s = settings(schema_id)
    if s is not None and s.props.settings_schema.has_key(key):
        s.reset(key)


# --------------------------------------------------------------- extensions
def installed_extensions():
    import os
    found = set()
    for base in ("/usr/share/gnome-shell/extensions",
                 os.path.expanduser("~/.local/share/gnome-shell/extensions")):
        if os.path.isdir(base):
            found.update(os.listdir(base))
    return found


def extension_enabled(uuid):
    return uuid in (get_key(SHELL, "enabled-extensions", []) or [])


def set_extension(uuid, enabled):
    """Enable/disable an extension through the shell's GSettings (applies live)."""
    if enabled and uuid not in installed_extensions():
        return False
    en = list(get_key(SHELL, "enabled-extensions", []) or [])
    dis = list(get_key(SHELL, "disabled-extensions", []) or [])
    if enabled:
        if uuid not in en:
            en.append(uuid)
        dis = [u for u in dis if u != uuid]
    else:
        en = [u for u in en if u != uuid]
        if uuid not in dis:
            dis.append(uuid)
    set_key(SHELL, "disabled-extensions", dis)
    set_key(SHELL, "enabled-extensions", en)
    if enabled:
        set_key(SHELL, "disable-user-extensions", False)
    return True


# ------------------------------------------------------------------ layouts
def _per_monitor(value):
    # Indexes are Dash to Panel's fallback monitor ids, so this covers up to 4
    # screens; writing the whole value also drops ids left over from its prefs
    return json.dumps({str(i): value for i in range(4)}, separators=(",", ":"))


def _dtp_elements(centered):
    tl, br = "stackedTL", "stackedBR"
    middle = "centerMonitor" if centered else tl
    elements = [
        ("showAppsButton", False, tl),
        ("activitiesButton", False, tl),
        ("leftBox", True, middle),
        ("taskbar", True, middle),
        ("centerBox", True, br),
        ("rightBox", True, br),
        ("dateMenu", True, br),
        ("systemMenu", True, br),
        ("desktopButton", True, br),
    ]
    return _per_monitor([{"element": e, "visible": v, "position": p} for e, v, p in elements])


def _dtp_dock_elements():
    # the app grid button first (where macOS keeps Launchpad), then the app
    # icons; GNOME's own top bar keeps the clock and the system menu
    tl, br = "stackedTL", "stackedBR"
    elements = [("showAppsButton", True, tl), ("taskbar", True, tl)]
    elements += [(e, False, br) for e in ("activitiesButton", "leftBox", "centerBox",
                                          "rightBox", "dateMenu", "systemMenu",
                                          "desktopButton")]
    return _per_monitor([{"element": e, "visible": v, "position": p} for e, v, p in elements])


# Magnify moves the outer icons about a third of an icon outwards: room for
# that at both ends of the dock (pixels)
DOCK_END_ROOM = 22


LAYOUTS = {
    "windows": {
        "title": "@DISTRO_SHORT_NAME@",
        "subtitle": "Taskbar and start menu at the bottom, like Windows 10",
    },
    "modern": {
        "title": "Modern",
        "subtitle": "Centered taskbar and start menu, like Windows 11",
    },
    "macos": {
        "title": "Dock",
        "subtitle": "Top bar and a floating dock that magnifies its icons, like macOS",
    },
    "ubuntu": {
        "title": "Classic",
        "subtitle": "Top bar with a side dock, like Ubuntu",
    },
    "gnome": {
        "title": "GNOME",
        "subtitle": "The original GNOME desktop with the Activities overview",
    },
}
LAYOUT_ORDER = ["windows", "modern", "macos", "ubuntu", "gnome"]


def _layout_icon_animation(kind):
    """Switch the hover animation style, unless the user turned it off."""
    if get_key(DTP, "animate-appicon-hover", True):
        set_key(DTP, "animate-appicon-hover-animation-type", kind)


def apply_layout(name):
    if name not in LAYOUTS:
        raise ValueError(f"unknown layout {name!r}; choose from {', '.join(LAYOUT_ORDER)}")
    previous = current_layout()
    if previous in ("windows", "modern"):
        prefs = load_prefs()
        prefs["floating-taskbar"] = (get_key(DTP, "panel-side-margins", 0) or 0) > 0
        save_prefs(prefs)
    if name in ("windows", "modern", "macos"):
        set_extension(UBUNTU_DOCK, False)
        # Dash to Panel rebuilds its panels on every key change; switch it off
        # while it is reconfigured so it starts once, in the new shape
        set_extension(DASH_TO_PANEL, False)
        if name == "macos":
            set_extension(ARCMENU, False)
            set_key(DTP, "stockgs-keep-top-panel", True)
            set_key(DTP, "panel-element-positions", _dtp_dock_elements())
            set_key(DTP, "panel-positions", _per_monitor("BOTTOM"))
            set_key(DTP, "panel-lengths", _per_monitor(-1))       # as long as its icons
            set_key(DTP, "panel-anchors", _per_monitor("MIDDLE"))
            set_key(DTP, "panel-sizes", _per_monitor(64))
            set_key(DTP, "panel-side-margins", 0)
            set_key(DTP, "panel-top-bottom-margins", 8)
            set_key(DTP, "panel-side-padding", DOCK_END_ROOM)
            set_key(DTP, "show-apps-icon-side-padding", DOCK_END_ROOM)
            set_key(DTP, "global-border-radius", 5)
            set_key(DTP, "intellihide", True)
            set_key(DTP, "intellihide-hide-from-windows", True)
            set_key(DTP, "dot-style-focused", "DOTS")
            set_key(DTP, "dot-style-unfocused", "DOTS")
            _layout_icon_animation("PLANK")
            set_key(WM, "button-layout", "close,minimize,maximize:appmenu")
        else:
            set_key(DTP, "stockgs-keep-top-panel", False)
            set_key(DTP, "panel-element-positions", _dtp_elements(centered=(name == "modern")))
            set_key(DTP, "panel-position", "BOTTOM")
            for key in ("panel-positions", "panel-lengths", "panel-anchors", "panel-sizes"):
                set_key(DTP, key, "{}")
            for key in ("panel-side-padding", "show-apps-icon-side-padding"):
                reset_key(DTP, key)
            set_key(DTP, "intellihide", False)
            set_key(DTP, "dot-style-focused", "METRO")
            set_key(DTP, "dot-style-unfocused", "METRO")
            if previous not in ("windows", "modern"):
                set_floating(load_prefs().get("floating-taskbar", False))
            _layout_icon_animation("RIPPLE")
            set_key(ARC, "menu-layout", "11" if name == "modern" else "arcmenu")
            set_key(ARC, "position-in-panel", "Left")
            set_key(WM, "button-layout", "appmenu:minimize,maximize,close")
            set_extension(ARCMENU, True)
        set_extension(DASH_TO_PANEL, True)
    elif name == "ubuntu":
        set_extension(DASH_TO_PANEL, False)
        set_extension(ARCMENU, False)
        set_key(DOCK, "dock-position", "LEFT")
        set_key(DOCK, "extend-height", True)
        set_key(DOCK, "dock-fixed", True)
        set_key(DOCK, "intellihide", False)
        set_key(DOCK, "dash-max-icon-size", 44)
        set_key(WM, "button-layout", "appmenu:minimize,maximize,close")
        set_extension(UBUNTU_DOCK, True)
    else:  # gnome
        set_extension(DASH_TO_PANEL, False)
        set_extension(ARCMENU, False)
        set_extension(UBUNTU_DOCK, False)
        set_key(WM, "button-layout", "appmenu:minimize,maximize,close")
    return True


def current_layout():
    dtp, dock = extension_enabled(DASH_TO_PANEL), extension_enabled(UBUNTU_DOCK)
    if dtp:
        if get_key(DTP, "stockgs-keep-top-panel", False):
            return "macos"
        positions = get_key(DTP, "panel-element-positions", "") or ""
        return "modern" if "centerMonitor" in positions else "windows"
    if dock:
        # a bottom Ubuntu Dock is how older versions made the Dock layout
        return "ubuntu" if get_key(DOCK, "extend-height", False) else "macos"
    return "gnome"


def set_floating(on):
    """Rounded taskbar with a small gap around it (@DISTRO_SHORT_NAME@ and Modern layouts)."""
    set_key(DTP, "panel-side-margins", 12 if on else 0)
    set_key(DTP, "panel-top-bottom-margins", 8 if on else 0)
    set_key(DTP, "global-border-radius", 4 if on else 0)


# --------------------------------------------------------------- animations
def set_icon_animation(kind):
    """Hover animation of taskbar/dock icons: None, SIMPLE, RIPPLE or PLANK."""
    if kind is None:
        set_key(DTP, "animate-appicon-hover", False)
    else:
        set_key(DTP, "animate-appicon-hover-animation-type", kind)
        set_key(DTP, "animate-appicon-hover", True)


def current_icon_animation():
    if not get_key(DTP, "animate-appicon-hover", False):
        return None
    return get_key(DTP, "animate-appicon-hover-animation-type", "SIMPLE")


# ------------------------------------------------------------------- style
def set_dark(dark):
    set_key(IFACE, "color-scheme", "prefer-dark" if dark else "default")
    # GTK3 theme and icons follow automatically through theme-sync; set them
    # here too so the change is immediate even if that helper is not running.
    gtk = get_key(IFACE, "gtk-theme", "")
    if gtk in ("adw-gtk3", "adw-gtk3-dark"):
        set_key(IFACE, "gtk-theme", "adw-gtk3-dark" if dark else "adw-gtk3")
    icons = get_key(IFACE, "icon-theme", "")
    if icons in ("Papirus", "Papirus-Dark", "Papirus-Light"):
        set_key(IFACE, "icon-theme", "Papirus-Dark" if dark else "Papirus")
    # dark desktop-icon labels read better on the light wallpaper
    set_key(DING, "dark-text-in-labels", not dark)


def is_dark():
    return get_key(IFACE, "color-scheme", "default") == "prefer-dark"


def set_accent(color):
    set_key(IFACE, "accent-color", color)


def current_accent():
    return get_key(IFACE, "accent-color", "blue")


def set_wallpaper(wall_id):
    for wid, _label, light, dark in WALLPAPERS:
        if wid == wall_id:
            set_key(BACKGROUND, "picture-uri", f"file://{WALLPAPER_DIR}/{light}")
            set_key(BACKGROUND, "picture-uri-dark", f"file://{WALLPAPER_DIR}/{dark}")
            set_key(SCREENSAVER, "picture-uri", f"file://{WALLPAPER_DIR}/{dark}")
            return True
    return False


def current_wallpaper():
    # display-setup swaps in "<name>-ultrawide" variants on ultrawide screens
    uri = (get_key(BACKGROUND, "picture-uri-dark", "") or "").replace("-ultrawide.", ".")
    light = (get_key(BACKGROUND, "picture-uri", "") or "").replace("-ultrawide.", ".")
    for wid, _label, lf, df in WALLPAPERS:
        if uri.endswith("/" + df) and light.endswith("/" + lf):
            return wid
    return None
