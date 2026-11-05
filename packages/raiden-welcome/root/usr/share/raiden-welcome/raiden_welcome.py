"""@DISTRO_NAME@ Welcome: first steps after installation."""
import glob
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = "org.raidenos.Welcome"
DISTRO = "@DISTRO_NAME@"
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "raiden-welcome")
SEEN_FLAG = os.path.join(CONFIG_DIR, "first-run-done")
ALWAYS_FLAG = os.path.join(CONFIG_DIR, "show-at-login")
# Left by the installer: the NVIDIA card is older than any NVIDIA driver
NVIDIA_TOO_OLD_FLAG = "/var/lib/raiden-os/nvidia-too-old"
# Apps the public edition gets on the first start with internet (raiden-apps
# keeps a file per app it has installed in APPS_STATE)
APPS_STATE = "/var/lib/raiden-apps"
APPS_STATUS = "/run/raiden-apps/status"   # what raiden-apps is doing right now
ARRIVING = (("Google Chrome", "google-chrome", "google-chrome.desktop"),
            ("Claude", "claude", "com.anthropic.Claude.desktop"),
            ("Antigravity", "antigravity", "antigravity.desktop"))
HERO = "/usr/share/pixmaps/raiden-os-emblem-3d.png"
STEAM_LAUNCH_OPTIONS = "gamemoderun mangohud %command%"

CSS = """
.hero-title { font-size: 2.1em; font-weight: 800; }
.hero-sub { font-size: 1.1em; opacity: 0.8; }
.card-title { font-weight: 700; }
.welcome-card { padding: 16px; border-radius: 16px; }
.status-ok { color: @success_color; }
.status-warn { color: @warning_color; }
"""

VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}


def is_live_session():
    try:
        with open("/proc/cmdline") as f:
            return "boot=casper" in f.read().split()
    except OSError:
        return False


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def gpus():
    """List display controllers: (slot, vendor, model, driver)."""
    names = {}
    try:
        out = subprocess.run(["lspci", "-mm"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            parts = [p.strip('"') for p in _split_quoted(line)]
            if len(parts) >= 4:
                names[parts[0]] = f"{parts[2]} {parts[3]}"
    except (OSError, subprocess.SubprocessError):
        pass
    found = []
    for dev in sorted(glob.glob("/sys/bus/pci/devices/*")):
        if not read(os.path.join(dev, "class")).startswith("0x03"):
            continue
        slot = os.path.basename(dev)
        vendor = VENDORS.get(read(os.path.join(dev, "vendor")), "Other")
        driver_link = os.path.join(dev, "driver")
        driver = os.path.basename(os.readlink(driver_link)) if os.path.islink(driver_link) else ""
        short = slot.split(":", 1)[1] if slot.count(":") == 2 else slot
        found.append((slot, vendor, names.get(short, vendor + " graphics"), driver))
    return found


def _split_quoted(line):
    out, cur, quoted = [], "", False
    for ch in line:
        if ch == '"':
            quoted = not quoted
            continue
        if ch == " " and not quoted:
            if cur:
                out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur:
        out.append(cur)
    return out


def launch(argv=None, desktop_id=None):
    try:
        if desktop_id:
            info = Gio.DesktopAppInfo.new(desktop_id)
            if info is not None:
                info.launch([], None)
                return True
        if argv:
            Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
            return True
    except (GLib.Error, TypeError):
        pass
    return False


def app_info(*desktop_ids):
    """The first of these apps that is installed, or None."""
    for desktop_id in desktop_ids:
        try:
            info = Gio.DesktopAppInfo.new(desktop_id)
        except TypeError:
            info = None
        if info is not None:
            return info
    return None


def arriving_apps():
    """Names of the apps raiden-apps is still to install: missing, and never
    installed before (one the user removed stays removed)."""
    if not os.path.exists("/usr/libexec/raiden-os/apps-update"):
        return []
    return [name for name, key, desktop_id in ARRIVING
            if app_info(desktop_id) is None and not os.path.exists(os.path.join(APPS_STATE, key))]


class WelcomeWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=f"Welcome to {DISTRO}")
        self.set_default_size(900, 760)
        self.set_size_request(380, 420)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Welcome"))
        view = Adw.ToolbarView()
        view.add_top_bar(header)

        page = Adw.PreferencesPage()
        page.add(self._hero())
        arriving = arriving_apps()
        if arriving:
            page.add(self._arriving_group(arriving))
        page.add(self._drivers_group())
        page.add(self._setup_group())
        page.add(self._games_group())
        page.add(self._school_group())
        page.add(self._ai_group())
        page.add(self._more_group())
        page.add(self._footer())
        self.toasts = Adw.ToastOverlay(child=page)
        view.set_content(self.toasts)
        self.set_content(view)

    # ---------------------------------------------------------------- hero
    def _hero(self):
        group = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24, margin_top=12,
                      margin_bottom=12, halign=Gtk.Align.CENTER)
        if os.path.exists(HERO):
            pic = Gtk.Image.new_from_file(HERO)
            pic.set_pixel_size(144)
            box.append(pic)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        title = Gtk.Label(label=f"Welcome to {DISTRO}", xalign=0, wrap=True)
        title.add_css_class("hero-title")
        sub = Gtk.Label(label="Fast, beautiful and yours. Here are a few things to get you started.",
                        xalign=0, wrap=True, max_width_chars=44)
        sub.add_css_class("hero-sub")
        text.append(title)
        text.append(sub)
        box.append(text)
        group.add(box)
        return group

    @staticmethod
    def _action_row(title, subtitle, icon, button_label, callback, suggested=False):
        """ICON: an icon name, or an app's own icon (Gio.Icon)."""
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        image = Gtk.Image(icon_name=icon) if isinstance(icon, str) else Gtk.Image(gicon=icon)
        image.set_pixel_size(32)
        row.add_prefix(image)
        btn = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.connect("clicked", lambda *_: callback())
        row.add_suffix(btn)
        row.set_activatable_widget(btn)
        return row

    def _app_row(self, title, subtitle, desktop_ids, flathub_id=None):
        """Opens an installed app; one that was removed is offered in Software."""
        info = app_info(*desktop_ids)
        if info is not None:
            return self._action_row(title, subtitle, info.get_icon() or "application-x-executable",
                                    "Open", lambda: launch(desktop_id=info.get_id()))
        if flathub_id:
            return self._action_row(title, subtitle, "system-software-install-symbolic", "Get",
                                    lambda: launch(["gnome-software", f"--details={flathub_id}"]))
        return None

    def _arriving_group(self, names):
        group = Adw.PreferencesGroup()
        row = Adw.ActionRow(title="On their way: " + ", ".join(names))
        row.add_prefix(Gtk.Image(icon_name="folder-download-symbolic", pixel_size=32))
        spinner = Adw.Spinner(valign=Gtk.Align.CENTER)
        row.add_suffix(spinner)
        btn = Gtk.Button(label="Try now", valign=Gtk.Align.CENTER)
        btn.set_tooltip_text("Start installing them now (asks for your password)")
        btn.connect("clicked", lambda *_: launch(
            ["systemctl", "start", "--no-block", "raiden-apps-update.service"]))
        row.add_suffix(btn)
        group.add(row)

        def refresh():
            left = arriving_apps()
            if not left:
                row.set_title("Your apps are ready")
                row.set_subtitle("Find them in the start menu.")
                spinner.set_visible(False)
                btn.set_visible(False)
                return GLib.SOURCE_REMOVE
            row.set_title("On their way: " + ", ".join(left))
            status = read(APPS_STATUS)
            if status:
                subtitle = status + "…"
            else:
                subtitle = ("They install by themselves as soon as this computer is online, "
                            "no restart needed.")
            if "Google Chrome" in left:
                subtitle += " Until then, Firefox is your browser."
            row.set_subtitle(subtitle)
            spinner.set_visible(bool(status))
            btn.set_visible(not status)
            return GLib.SOURCE_CONTINUE

        refresh()
        GLib.timeout_add_seconds(3, refresh)
        return group

    # ------------------------------------------------------------- drivers
    def _drivers_group(self):
        group = Adw.PreferencesGroup(title="Graphics",
                                     description="Drivers for your graphics card(s)")
        cards = gpus()
        too_old = os.path.exists(NVIDIA_TOO_OLD_FLAG)
        if not cards:
            group.add(Adw.ActionRow(title="No graphics card information available"))
        for _slot, vendor, model, driver in cards:
            if vendor == "NVIDIA":
                if driver == "nvidia":
                    ver = read("/sys/module/nvidia/version")
                    status = f"NVIDIA driver {ver} is active" if ver else "NVIDIA driver is active"
                    good = True
                elif driver == "nouveau" and too_old:
                    status = ("Open-source driver (nouveau). NVIDIA no longer makes drivers "
                              "for this card, so it is too old for most new games")
                    good = True
                else:
                    status = ("Needs an NVIDIA driver; install the recommended one"
                              if driver != "nouveau" else
                              "Using the basic open-source driver; the NVIDIA driver is faster")
                    good = False
            elif vendor == "AMD" and driver == "radeon":
                good = True
                status = ("Built-in open-source driver (radeon). This card is too old for "
                          "Vulkan, which most new games need")
            elif vendor in ("AMD", "Intel"):
                good = bool(driver)
                status = (f"Built-in open-source driver ({driver}) with Vulkan and video "
                          "acceleration" if good else "No driver loaded")
            else:
                good = bool(driver)
                status = f"Driver: {driver or 'none'}"
            row = Adw.ActionRow(title=model, subtitle=status)
            icon = Gtk.Image(icon_name="emblem-ok-symbolic" if good else "dialog-warning-symbolic")
            icon.add_css_class("status-ok" if good else "status-warn")
            row.add_prefix(Gtk.Image(icon_name="video-display-symbolic", pixel_size=32))
            row.add_suffix(icon)
            group.add(row)
        needs = any(v == "NVIDIA" and d != "nvidia" for _s, v, _m, d in cards)
        if needs and not too_old:
            group.add(self._action_row(
                "Install the NVIDIA driver",
                "Connect to the internet, then pick the recommended driver in Additional Drivers.",
                "software-update-available-symbolic", "Open",
                lambda: launch(["software-properties-gtk", "--open-tab=4"]), suggested=True))
        else:
            group.add(self._action_row(
                "Additional drivers", "See or change the drivers used by this computer.",
                "preferences-system-symbolic", "Open",
                lambda: launch(["software-properties-gtk", "--open-tab=4"])))
        return group

    # ---------------------------------------------------------------- setup
    def _setup_group(self):
        group = Adw.PreferencesGroup(title="Make it yours")
        group.add(self._action_row("Choose your desktop layout",
                                   "Windows-like, Windows 11-like, macOS-like or GNOME.",
                                   "raiden-appearance", "Appearance",
                                   lambda: launch(["raiden-appearance"]), suggested=True))
        group.add(self._action_row("Check for updates",
                                   "Install the latest security fixes, kernel and drivers.",
                                   "software-update-available-symbolic", "Update",
                                   lambda: launch(["update-manager"])))
        group.add(self._action_row("Battery and power",
                                   "Power modes, battery health and automatic power saving.",
                                   "battery-full-charged-symbolic", "Power",
                                   lambda: launch(["gnome-control-center", "power"])))
        group.add(self._action_row("Connect your phone",
                                   "Share files, notifications and the clipboard with your phone.",
                                   "phone-symbolic", "Set up",
                                   lambda: launch(desktop_id="org.gnome.Shell.Extensions.GSConnect.Preferences.desktop")))
        group.add(self._action_row("Get more apps",
                                   "Thousands of apps from Flathub and Ubuntu in Software.",
                                   "org.gnome.Software", "Software",
                                   lambda: launch(["gnome-software"])))
        return group

    # ----------------------------------------------------------------- apps
    def _add_rows(self, group, rows):
        for row in rows:
            if row is not None:
                group.add(row)

    def _games_group(self):
        group = Adw.PreferencesGroup(
            title="Games",
            description="Windows games run through Proton. GameMode, MangoHud and the "
                        "system's game tuning are already set up.")
        self._add_rows(group, [
            self._app_row("Steam", "Thousands of Windows and Linux games.",
                          ["steam.desktop", "com.valvesoftware.Steam.desktop"],
                          "com.valvesoftware.Steam"),
            self._app_row("Heroic Games Launcher", "Your Epic Games, GOG and Amazon games.",
                          ["heroic.desktop", "com.heroicgameslauncher.hgl.desktop"],
                          "com.heroicgameslauncher.hgl"),
            self._app_row("Lutris", "Games from other stores, emulators and Windows installers.",
                          ["net.lutris.Lutris.desktop"], "net.lutris.Lutris"),
            self._app_row("ProtonPlus", "Add Proton-GE and other tools that some games need.",
                          ["com.vysp3r.ProtonPlus.desktop"], "com.vysp3r.ProtonPlus"),
            self._app_row("FPS overlay", "Choose what MangoHud shows in games: FPS, "
                          "temperatures, frame times (GOverlay).",
                          ["io.github.benjamimgois.goverlay.desktop", "goverlay.desktop"]),
        ])
        tip = self._action_row(
            "Boost a Steam game",
            f"In the game's Properties, set the launch options to: {STEAM_LAUNCH_OPTIONS}",
            "applications-games-symbolic", "Copy", self._copy_launch_options)
        group.add(tip)
        return group

    def _copy_launch_options(self):
        Gdk.Display.get_default().get_clipboard().set(STEAM_LAUNCH_OPTIONS)
        self.toasts.add_toast(Adw.Toast(title="Copied. Paste it into the launch options in Steam."))

    def _school_group(self):
        group = Adw.PreferencesGroup(title="School and work")
        self._add_rows(group, [
            self._app_row("Outlook", "Mail and calendar for your school or work account.",
                          ["org.raidenos.Outlook.desktop"]),
            self._app_row("Microsoft 365", "Word, Excel, PowerPoint, OneDrive and Teams.",
                          ["org.raidenos.Microsoft365.desktop"]),
            self._app_row("LibreOffice Writer", "Write documents; opens and saves Word files.",
                          ["libreoffice-writer.desktop"], "org.libreoffice.LibreOffice"),
            self._app_row("Xournal++", "Handwritten notes, and notes and highlights on PDFs.",
                          ["com.github.xournalpp.xournalpp.desktop"], "com.github.xournalpp.xournalpp"),
            self._app_row("Foliate", "Read e-books (EPUB, MOBI) and pick up where you left off.",
                          ["com.github.johnfactotum.Foliate.desktop"], "com.github.johnfactotum.Foliate"),
            self._app_row("Zotero", "Collect sources and create citations and bibliographies.",
                          ["org.zotero.Zotero.desktop", "zotero.desktop"], "org.zotero.Zotero"),
        ])
        return group

    def _ai_group(self):
        group = Adw.PreferencesGroup(title="AI assistants")
        self._add_rows(group, [
            self._app_row("Claude", "Anthropic's AI assistant, with Claude Code and Cowork.",
                          ["com.anthropic.Claude.desktop"]),
            self._app_row("Antigravity", "Google's AI agent app.", ["antigravity.desktop"]),
            self._app_row("Antigravity IDE", "Google's AI code editor.", ["antigravity-ide.desktop"]),
        ])
        return group

    def _more_group(self):
        group = Adw.PreferencesGroup(title="Stay safe")
        group.add(self._action_row("System snapshots",
                                   "Roll the system back if an update ever goes wrong (Timeshift).",
                                   "timeshift", "Timeshift", lambda: launch(["timeshift-launcher"])))
        group.add(self._action_row("Back up your files",
                                   "Automatic backups of your personal files.",
                                   "org.gnome.DejaDup", "Backups", lambda: launch(["deja-dup"])))
        group.add(self._action_row("Firewall",
                                   "Block unwanted incoming connections.",
                                   "security-high-symbolic", "Firewall",
                                   lambda: launch(["gufw"])))
        return group

    def _footer(self):
        group = Adw.PreferencesGroup()
        row = Adw.SwitchRow(title="Show Welcome at every login")
        row.set_active(os.path.exists(ALWAYS_FLAG))

        def toggled(r, _p):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if r.get_active():
                open(ALWAYS_FLAG, "w").close()
            elif os.path.exists(ALWAYS_FLAG):
                os.remove(ALWAYS_FLAG)
        row.connect("notify::active", toggled)
        group.add(row)
        return group


class WelcomeApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.win = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if self.win is None:
            self.win = WelcomeWindow(self)
        self.win.present()
        os.makedirs(CONFIG_DIR, exist_ok=True)
        open(SEEN_FLAG, "w").close()


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--autostart" in argv:
        if is_live_session():
            return 0
        if os.path.exists(SEEN_FLAG) and not os.path.exists(ALWAYS_FLAG):
            return 0
    return WelcomeApp().run([argv[0]])
