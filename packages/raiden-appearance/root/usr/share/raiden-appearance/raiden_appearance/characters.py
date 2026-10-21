"""Character themes: wallpaper, accent colour, login screen and profile picture.

Themes are described by /usr/share/raiden-os/characters/<id>.json (written
by artwork/make-characters.py at build time). Wallpaper and accent are per
user (GSettings); the login screen background is system-wide and goes through
a polkit-protected helper; the profile picture goes through AccountsService.
"""
import glob
import json
import os

from gi.repository import Gio, GLib

from . import layouts as L

DATA_DIR = "/usr/share/raiden-os/characters"
LOGIN_HELPER = "/usr/libexec/raiden-appearance/set-login-background"
LOGIN_CONF = "/etc/gdm3/raiden-login-background"
PREFS = os.path.join(GLib.get_user_config_dir(), "raiden-appearance", "characters.json")

AURORA = {
    # the built-in look, so you can always switch back
    "id": "aurora", "name": "@DISTRO_SHORT_NAME@", "series": "Aurora", "accent": "blue",
    "wallpaper": os.path.join(L.WALLPAPER_DIR, "aurora-dark.jpg"),
    "preview": os.path.join(L.WALLPAPER_DIR, "aurora-dark.jpg"),
    "avatar": None, "desktop_text": None,
}


def available():
    """Installed character themes, in their intended order."""
    themes = []
    for path in glob.glob(os.path.join(DATA_DIR, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                theme = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(theme, dict) and os.path.isfile(theme.get("wallpaper", "")):
            themes.append(theme)
    themes.sort(key=lambda t: (t.get("order", 99), t.get("name", "")))
    return themes


def base_picture(path):
    """PATH without the "-ultrawide" variant suffix (display-setup picks the
    variant that fits the main monitor)."""
    root, ext = os.path.splitext(path)
    return (root[:-len("-ultrawide")] if root.endswith("-ultrawide") else root) + ext


def primary_is_ultrawide():
    """True if the main monitor is 21:9 or wider (asks the compositor)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        _serial, monitors, logical, _props = bus.call_sync(
            "org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig", "GetCurrentState", None, None,
            Gio.DBusCallFlags.NONE, -1, None).unpack()
    except GLib.Error:
        return False
    for _x, _y, _scale, transform, primary, specs, _p in logical:
        if not (primary and specs):
            continue
        for spec, modes, _mp in monitors:
            if spec[0] != specs[0][0]:
                continue
            for mode in modes:
                if mode[6].get("is-current"):
                    w, h = (mode[2], mode[1]) if transform % 2 else (mode[1], mode[2])
                    return w / h >= 2.1
    return False


def current(themes):
    """id of the theme whose wallpaper is set, "raiden" for Aurora, or None."""
    uri = base_picture(L.get_key(L.BACKGROUND, "picture-uri-dark", "") or "")
    for theme in themes:
        if uri == "file://" + theme["wallpaper"]:
            return theme["id"]
    if uri.startswith(f"file://{L.WALLPAPER_DIR}/aurora"):
        return "raiden"
    return None


def apply(theme):
    """Wallpaper (desktop + lock screen), accent colour and desktop icon labels."""
    if theme["id"] == "raiden":
        L.set_wallpaper("aurora")
        L.set_accent("blue")
        L.set_key(L.DING, "dark-text-in-labels", not L.is_dark())
        return
    uri = "file://" + theme["wallpaper"]
    L.set_key(L.BACKGROUND, "picture-uri", uri)
    L.set_key(L.BACKGROUND, "picture-uri-dark", uri)
    L.set_key(L.BACKGROUND, "picture-options", "zoom")
    L.set_key(L.SCREENSAVER, "picture-uri", uri)
    L.set_accent(theme.get("accent") or "blue")
    # light pictures (e.g. a white background) need dark desktop icon labels
    L.set_key(L.DING, "dark-text-in-labels", theme.get("desktop_text") == "dark")


# ------------------------------------------------------------ preferences
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


# ----------------------------------------------------------- login screen
def login_picture(theme):
    """The theme's login screen version of its wallpaper (falls back to the
    wallpaper), in its ultrawide version on an ultrawide main monitor."""
    login = theme.get("login")
    picture = login if login and os.path.isfile(login) else theme["wallpaper"]
    root, ext = os.path.splitext(picture)
    wide = f"{root}-ultrawide{ext}"
    return wide if os.path.isfile(wide) and primary_is_ultrawide() else picture


def login_background():
    """The picture currently on the login screen, or None."""
    try:
        with open(LOGIN_CONF, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("background-picture-uri="):
                    uri = line.split("=", 1)[1].strip().strip("'")
                    return uri[len("file://"):] if uri.startswith("file://") else None
    except OSError:
        pass
    return None


def set_login_background(path, callback):
    """Put PATH (a system wallpaper) on the login screen; None = plain background.
    Asks for an administrator password (polkit). callback(ok: bool)."""
    argv = ["pkexec", LOGIN_HELPER, path or "--default"]
    try:
        proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDERR_SILENCE)
    except GLib.Error:
        callback(False)
        return

    def done(p, result):
        try:
            ok = p.wait_check_finish(result)
        except GLib.Error:
            ok = False
        callback(ok)
    proc.wait_check_async(None, done)


# --------------------------------------------------------- profile picture
def set_avatar(path, callback):
    """Use PATH as your profile picture (AccountsService; no password needed
    for your own account). callback(ok: bool)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        user = bus.call_sync("org.freedesktop.Accounts", "/org/freedesktop/Accounts",
                             "org.freedesktop.Accounts", "FindUserById",
                             GLib.Variant("(x)", (os.getuid(),)), GLib.VariantType("(o)"),
                             Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
    except GLib.Error:
        callback(False)
        return

    def done(b, result):
        try:
            b.call_finish(result)
            ok = True
        except GLib.Error:
            ok = False
        callback(ok)
    bus.call("org.freedesktop.Accounts", user, "org.freedesktop.Accounts.User", "SetIconFile",
             GLib.Variant("(s)", (path,)), None, Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION,
             -1, None, done)
