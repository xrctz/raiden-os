"""@DISTRO_SHORT_NAME@ Appearance: choose the desktop layout, style and effects."""
import math
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from . import characters as C  # noqa: E402
from . import layouts as L  # noqa: E402

APP_ID = "org.raidenos.Appearance"

CSS = """
.layout-card { padding: 10px; border-radius: 16px; }
.layout-card:checked { background-color: alpha(@accent_bg_color, 0.18);
                       box-shadow: inset 0 0 0 2px @accent_bg_color; }
.layout-title { font-weight: 700; font-size: 1.05em; }
.layout-sub { font-size: 0.85em; opacity: 0.7; }
.swatch { min-width: 34px; min-height: 34px; border-radius: 999px; padding: 0; }
.swatch:checked { box-shadow: 0 0 0 3px @window_bg_color, 0 0 0 5px @accent_bg_color; }
.wall-card { padding: 6px; border-radius: 14px; }
.wall-card:checked { box-shadow: inset 0 0 0 3px @accent_bg_color; }
.hero-title { font-size: 1.6em; font-weight: 800; }
"""


def _rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_layout_preview(area, cr, width, height, layout):
    """Small illustration of a desktop layout (drawn, so it is always crisp)."""
    pad = 4
    w, h = width - 2 * pad, height - 2 * pad
    x0, y0 = pad, pad
    # wallpaper
    _rounded(cr, x0, y0, w, h, 10)
    cr.save()
    cr.clip()
    import cairo
    grad = cairo.LinearGradient(x0, y0, x0 + w, y0 + h)
    grad.add_color_stop_rgb(0, 0.04, 0.07, 0.18)
    grad.add_color_stop_rgb(0.55, 0.16, 0.25, 0.75)
    grad.add_color_stop_rgb(1, 0.45, 0.25, 0.85)
    cr.set_source(grad)
    cr.paint()
    # a window
    win_x, win_y, win_w, win_h = x0 + w * 0.22, y0 + h * 0.2, w * 0.56, h * 0.5
    if layout == "ubuntu":
        win_x += w * 0.06
    cr.set_source_rgba(0.95, 0.96, 1.0, 0.92)
    _rounded(cr, win_x, win_y, win_w, win_h, 5)
    cr.fill()
    cr.set_source_rgba(0.82, 0.85, 0.95, 1)
    _rounded(cr, win_x, win_y, win_w, h * 0.07, 5)
    cr.fill()
    # window buttons
    btn_y = win_y + h * 0.035
    if layout == "macos":
        for i, col in enumerate(((1, .37, .34), (1, .74, .18), (.16, .78, .25))):
            cr.set_source_rgb(*col)
            cr.arc(win_x + 8 + i * 8, btn_y, 2.6, 0, 2 * math.pi)
            cr.fill()
    else:
        cr.set_source_rgba(0.3, 0.33, 0.45, 1)
        for i in range(3):
            cr.arc(win_x + win_w - 8 - i * 8, btn_y, 2.2, 0, 2 * math.pi)
            cr.fill()
    accent = (0.24, 0.42, 0.97)
    icon_cols = [(0.94, 0.45, 0.2), (0.2, 0.6, 0.95), (0.3, 0.8, 0.5), (0.75, 0.4, 0.95)]
    if layout in ("windows", "modern"):
        bar_h = h * 0.12
        cr.set_source_rgba(0.05, 0.07, 0.14, 0.82)
        cr.rectangle(x0, y0 + h - bar_h, w, bar_h)
        cr.fill()
        n = 5
        s = bar_h * 0.56
        gap = s * 0.45
        total = n * s + (n - 1) * gap
        start = x0 + (w - total) / 2 if layout == "modern" else x0 + 8
        cy = y0 + h - bar_h / 2
        for i in range(n):
            col = accent if i == 0 else icon_cols[(i - 1) % 4]
            cr.set_source_rgb(*col)
            _rounded(cr, start + i * (s + gap), cy - s / 2, s, s, 3)
            cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.75)
        cr.rectangle(x0 + w - 32, cy - 2, 22, 4)
        cr.fill()
    else:
        # top bar
        top_h = h * 0.07
        cr.set_source_rgba(0.03, 0.04, 0.08, 0.9)
        cr.rectangle(x0, y0, w, top_h)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.rectangle(x0 + w / 2 - 12, y0 + top_h / 2 - 1.5, 24, 3)
        cr.fill()
        if layout == "gnome":
            cr.set_source_rgba(1, 1, 1, 0.85)
            _rounded(cr, x0 + 6, y0 + top_h / 2 - 2.5, 14, 5, 2.5)
            cr.fill()
        if layout == "macos":
            n, s = 6, h * 0.075
            gap = s * 0.35
            dock_w = n * s + (n + 1) * gap
            dx, dy = x0 + (w - dock_w) / 2, y0 + h - s - gap * 3
            cr.set_source_rgba(1, 1, 1, 0.28)
            _rounded(cr, dx, dy, dock_w, s + 2 * gap, 6)
            cr.fill()
            for i in range(n):
                cr.set_source_rgb(*icon_cols[i % 4])
                _rounded(cr, dx + gap + i * (s + gap), dy + gap, s, s, 3)
                cr.fill()
        if layout == "ubuntu":
            dock_w = w * 0.09
            cr.set_source_rgba(0.05, 0.07, 0.14, 0.82)
            cr.rectangle(x0, y0 + top_h, dock_w, h - top_h)
            cr.fill()
            s = dock_w * 0.62
            for i in range(5):
                cr.set_source_rgb(*icon_cols[i % 4])
                _rounded(cr, x0 + (dock_w - s) / 2, y0 + top_h + 6 + i * (s + 5), s, s, 3)
                cr.fill()
    cr.restore()


def draw_style_preview(area, cr, width, height, dark):
    bg = (0.13, 0.13, 0.16) if dark else (0.96, 0.96, 0.98)
    card = (0.2, 0.2, 0.24) if dark else (1, 1, 1)
    fg = (0.92, 0.92, 0.95) if dark else (0.2, 0.2, 0.25)
    _rounded(cr, 4, 4, width - 8, height - 8, 10)
    cr.set_source_rgb(*bg)
    cr.fill()
    _rounded(cr, 14, 16, width - 28, height - 32, 8)
    cr.set_source_rgb(*card)
    cr.fill()
    cr.set_source_rgb(*fg)
    for i, frac in enumerate((0.6, 0.45, 0.7)):
        _rounded(cr, 26, 30 + i * 14, (width - 60) * frac, 6, 3)
        cr.fill()
    cr.set_source_rgb(0.24, 0.42, 0.97)
    _rounded(cr, width - 64, height - 40, 38, 14, 7)
    cr.fill()


class AppearanceWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Appearance")
        self.set_default_size(980, 760)
        self.set_size_request(380, 400)
        self._updating = False

        stack = Adw.ViewStack()
        stack.add_titled_with_icon(self._layout_page(), "layout", "Layout", "view-grid-symbolic")
        stack.add_titled_with_icon(self._style_page(), "style", "Style", "applications-graphics-symbolic")
        self._themes = C.available()
        if self._themes:
            stack.add_titled_with_icon(self._characters_page(), "characters", "Characters",
                                       "emblem-favorite-symbolic")
        stack.add_titled_with_icon(self._desktop_page(), "desktop", "Desktop", "user-desktop-symbolic")
        stack.add_titled_with_icon(self._effects_page(), "effects", "Effects", "starred-symbolic")

        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        menu = Gio.Menu()
        menu.append("Reset to Defaults", "app.reset")
        menu.append("About Appearance", "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text="Main Menu"))
        bottom = Adw.ViewSwitcherBar(stack=stack)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(stack)
        view.add_bottom_bar(bottom)
        self.toasts = Adw.ToastOverlay(child=view)
        self.set_content(self.toasts)

        # narrow windows: switcher moves to the bottom
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 620sp"))
        bp.add_setter(bottom, "reveal", True)
        bp.add_setter(header, "show-title", False)
        self.add_breakpoint(bp)

    # ------------------------------------------------------------ helpers
    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=2))

    @staticmethod
    def _page(title, description=None):
        page = Adw.PreferencesPage()
        if title:
            group = Adw.PreferencesGroup()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lbl = Gtk.Label(label=title, xalign=0)
            lbl.add_css_class("hero-title")
            box.append(lbl)
            if description:
                d = Gtk.Label(label=description, xalign=0, wrap=True)
                d.add_css_class("dim-label")
                box.append(d)
            group.add(box)
            page.add(group)
        return page

    def _switch_row(self, title, subtitle, active, on_change):
        row = Adw.SwitchRow(title=title, subtitle=subtitle or "")
        row.set_active(bool(active))
        row.connect("notify::active", lambda r, _p: None if self._updating else on_change(r.get_active()))
        return row

    # ------------------------------------------------------------- layout
    def _layout_page(self):
        page = self._page("Desktop Layout",
                          "Pick the layout you feel at home with. You can switch any time.")
        group = Adw.PreferencesGroup()
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=3, min_children_per_line=1,
                           column_spacing=12, row_spacing=12)
        current = L.current_layout()
        first = None
        self.layout_buttons = {}
        for name in L.LAYOUT_ORDER:
            info = L.LAYOUTS[name]
            btn = Gtk.ToggleButton()
            btn.add_css_class("layout-card")
            btn.add_css_class("flat")
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            area = Gtk.DrawingArea(content_width=240, content_height=150)
            area.set_draw_func(draw_layout_preview, name)
            box.append(area)
            t = Gtk.Label(label=info["title"], xalign=0)
            t.add_css_class("layout-title")
            s = Gtk.Label(label=info["subtitle"], xalign=0, wrap=True, max_width_chars=28)
            s.add_css_class("layout-sub")
            box.append(t)
            box.append(s)
            btn.set_child(box)
            btn.set_active(name == current)
            btn.connect("toggled", self._on_layout_toggled, name)
            self.layout_buttons[name] = btn
            flow.append(btn)
        group.add(flow)
        page.add(group)

        tip = Adw.PreferencesGroup()
        tip.add(Adw.ActionRow(title="Tip",
                              subtitle="Press the Super (Windows) key to open the start menu "
                                       "or the Activities overview."))
        page.add(tip)
        return page

    def _on_layout_toggled(self, btn, name):
        if self._updating or not btn.get_active():
            return
        try:
            L.apply_layout(name)
            self.toast(f"{L.LAYOUTS[name]['title']} layout applied")
        except Exception as exc:  # never crash the app on a settings error
            self.toast(f"Could not apply layout: {exc}")
        self._sync_taskbar_group()

    # -------------------------------------------------------------- style
    def _style_page(self):
        page = self._page("Style", "Light or dark, accent colour and taskbar look.")
        group = Adw.PreferencesGroup(title="Appearance")
        row = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6)
        light = Gtk.ToggleButton()
        dark = Gtk.ToggleButton(group=light)
        for btn, is_dark, label in ((light, False, "Light"), (dark, True, "Dark")):
            btn.add_css_class("layout-card")
            btn.add_css_class("flat")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            area = Gtk.DrawingArea(content_width=180, content_height=112)
            area.set_draw_func(draw_style_preview, is_dark)
            box.append(area)
            box.append(Gtk.Label(label=label))
            btn.set_child(box)
            row.append(btn)
        (dark if L.is_dark() else light).set_active(True)
        dark.connect("toggled", lambda b: None if self._updating else L.set_dark(b.get_active()))
        group.add(row)
        page.add(group)

        accent_group = Adw.PreferencesGroup(title="Accent Colour")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=9,
                           min_children_per_line=5, column_spacing=10, row_spacing=10,
                           halign=Gtk.Align.START)
        provider = Gtk.CssProvider()
        provider.load_from_string("".join(
            f".swatch-{v} {{ background: {hx}; }}" for v, _l, hx in L.ACCENT_COLORS))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        current = L.current_accent()
        first = None
        for value, label, _hx in L.ACCENT_COLORS:
            b = Gtk.ToggleButton(tooltip_text=label)
            b.add_css_class("swatch")
            b.add_css_class(f"swatch-{value}")
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.set_active(value == current)
            b.connect("toggled", lambda btn, v=value: btn.get_active() and not self._updating
                      and L.set_accent(v))
            flow.append(b)
        accent_group.add(flow)
        page.add(accent_group)

        icons = Adw.PreferencesGroup(title="Icons")
        combo = Adw.ComboRow(title="Icon style",
                             model=Gtk.StringList.new(["Papirus (colourful)", "Adwaita (GNOME)"]))
        theme = L.get_key(L.IFACE, "icon-theme", "Papirus-Dark")
        combo.set_selected(0 if theme.startswith("Papirus") else 1)

        def on_icons(c, _p):
            if self._updating:
                return
            if c.get_selected() == 0:
                L.set_key(L.IFACE, "icon-theme", "Papirus-Dark" if L.is_dark() else "Papirus")
            else:
                L.set_key(L.IFACE, "icon-theme", "Adwaita")
        combo.connect("notify::selected", on_icons)
        icons.add(combo)
        page.add(icons)

        self.taskbar_group = Adw.PreferencesGroup(
            title="Taskbar", description="Used by the @DISTRO_SHORT_NAME@ and Modern layouts.")
        size = Adw.SpinRow.new_with_range(32, 72, 2)
        size.set_title("Taskbar height")
        size.set_value(L.get_key(L.DTP, "panel-size", 48) or 48)
        size.connect("notify::value", lambda r, _p: None if self._updating else
                     L.set_key(L.DTP, "panel-size", int(r.get_value())))
        self.taskbar_group.add(size)
        opacity = Adw.SpinRow.new_with_range(0, 100, 5)
        opacity.set_title("Taskbar opacity")
        opacity.set_subtitle("Lower values show more of the wallpaper (percent)")
        opacity.set_value(round((L.get_key(L.DTP, "trans-panel-opacity", 0.55) or 0.55) * 100))

        def on_opacity(r, _p):
            if self._updating:
                return
            L.set_key(L.DTP, "trans-use-custom-opacity", True)
            L.set_key(L.DTP, "trans-panel-opacity", r.get_value() / 100.0)
        opacity.connect("notify::value", on_opacity)
        self.taskbar_group.add(opacity)
        floating = self._switch_row(
            "Floating taskbar", "Rounded taskbar with a small gap around it",
            (L.get_key(L.DTP, "panel-side-margins", 0) or 0) > 0, self._set_floating)
        self.taskbar_group.add(floating)
        page.add(self.taskbar_group)
        self._sync_taskbar_group()
        return page

    @staticmethod
    def _set_floating(on):
        L.set_floating(on)

    def _sync_taskbar_group(self):
        # the Dock layout uses Dash to Panel too, but with its own shape
        if hasattr(self, "taskbar_group"):
            self.taskbar_group.set_sensitive(L.current_layout() in ("windows", "modern"))

    # ------------------------------------------------------------ desktop
    def _desktop_page(self):
        page = self._page("Desktop", "Wallpaper, desktop icons and windows.")
        walls = Adw.PreferencesGroup(title="Wallpaper",
                                     description="Aurora switches between a light and a dark "
                                                 "version together with the style.")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=4, min_children_per_line=2,
                           column_spacing=10, row_spacing=10)
        current = L.current_wallpaper()
        first = None
        for wid, label, light, dark in L.WALLPAPERS:
            b = Gtk.ToggleButton(tooltip_text=label)
            b.add_css_class("wall-card")
            b.add_css_class("flat")
            if first is None:
                first = b
            else:
                b.set_group(first)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            pic = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.COVER)
            pic.set_size_request(192, 108)
            path = os.path.join(L.WALLPAPER_DIR, dark if L.is_dark() else light)
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 384, 216, True)
                pic.set_paintable(Gdk.Texture.new_for_pixbuf(pb))
            except GLib.Error:
                pass
            box.append(pic)
            box.append(Gtk.Label(label=label))
            b.set_child(box)
            b.set_active(wid == current)
            b.connect("toggled", lambda btn, w=wid: btn.get_active() and not self._updating
                      and L.set_wallpaper(w))
            flow.append(b)
        walls.add(flow)
        more = Adw.ActionRow(title="More wallpapers", subtitle="Pick any picture in Settings",
                             activatable=True)
        more.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        more.connect("activated", lambda *_: _spawn(["gnome-control-center", "background"]))
        walls.add(more)
        page.add(walls)

        icons = Adw.PreferencesGroup(title="Desktop Icons")
        icons.add(self._switch_row("Show icons on the desktop", None,
                                   L.extension_enabled(L.DESKTOP_ICONS),
                                   lambda on: L.set_extension(L.DESKTOP_ICONS, on)))
        icons.add(self._switch_row("Home folder", None, L.get_key(L.DING, "show-home", True),
                                   lambda on: L.set_key(L.DING, "show-home", on)))
        icons.add(self._switch_row("Trash", None, L.get_key(L.DING, "show-trash", True),
                                   lambda on: L.set_key(L.DING, "show-trash", on)))
        page.add(icons)

        windows = Adw.PreferencesGroup(title="Windows and Top Bar")
        left = (L.get_key(L.WM, "button-layout", "") or "").startswith("close")
        windows.add(self._switch_row(
            "Window buttons on the left", "Close, minimise and maximise like on a Mac", left,
            lambda on: L.set_key(L.WM, "button-layout",
                                 "close,minimize,maximize:appmenu" if on
                                 else "appmenu:minimize,maximize,close")))
        windows.add(self._switch_row("Battery percentage", "Show the exact charge next to the icon",
                                     L.get_key(L.IFACE, "show-battery-percentage", True),
                                     lambda on: L.set_key(L.IFACE, "show-battery-percentage", on)))
        windows.add(self._switch_row("Hot corner", "Open the overview by pushing the pointer "
                                                   "into the top-left corner",
                                     L.get_key(L.IFACE, "enable-hot-corners", False),
                                     lambda on: L.set_key(L.IFACE, "enable-hot-corners", on)))
        page.add(windows)
        return page

    # --------------------------------------------------------- characters
    def _characters_page(self):
        page = self._page("Characters", "Your favourite characters as the wallpaper, accent colour, "
                                        "login screen and profile picture.")
        group = Adw.PreferencesGroup()
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=3, min_children_per_line=1,
                           column_spacing=12, row_spacing=12)
        current = C.current(self._themes)
        first = None
        for theme in self._themes + [C.AURORA]:
            b = Gtk.ToggleButton(tooltip_text=theme["name"])
            b.add_css_class("wall-card")
            b.add_css_class("flat")
            if first is None:
                first = b
            else:
                b.set_group(first)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            pic = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.COVER)
            pic.set_size_request(240, 150)
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(theme["preview"], 480, 300, True)
                pic.set_paintable(Gdk.Texture.new_for_pixbuf(pb))
            except GLib.Error:
                pass
            box.append(pic)
            title = Gtk.Label(label=theme["name"])
            title.add_css_class("layout-title")
            sub = Gtk.Label(label=theme["series"])
            sub.add_css_class("layout-sub")
            box.append(title)
            box.append(sub)
            b.set_child(box)
            b.set_active(theme["id"] == current)
            b.connect("toggled", self._on_character_toggled, theme)
            flow.append(b)
        group.add(flow)
        page.add(group)

        also = Adw.PreferencesGroup(title="Also use the character for")
        self._login_row = Adw.SwitchRow(title="Login screen",
                                        subtitle="Background of the login screen (asks for your password)")
        self._login_row.set_active(C.login_background() is not None)
        self._login_row.connect("notify::active", self._on_login_toggled)
        self._avatar_row = Adw.SwitchRow(title="Profile picture",
                                         subtitle="Shown on the login screen and in the system menu")
        self._avatar_row.set_active(bool(C.load_prefs().get("avatar", False)))
        self._avatar_row.connect("notify::active", self._on_avatar_toggled)
        also.add(self._login_row)
        also.add(self._avatar_row)
        page.add(also)
        return page

    def _selected_theme(self):
        cur = C.current(self._themes)
        return next((t for t in self._themes + [C.AURORA] if t["id"] == cur), None)

    def _on_character_toggled(self, btn, theme):
        if self._updating or not btn.get_active():
            return
        C.apply(theme)
        self.toast(f"{theme['name']} applied")
        if self._login_row.get_active():
            C.set_login_background(C.login_picture(theme), self._login_done)
        if self._avatar_row.get_active() and theme.get("avatar"):
            C.set_avatar(theme["avatar"], self._avatar_done)

    def _login_done(self, ok):
        if not ok:
            self.toast("The login screen was not changed")
        self._updating = True
        self._login_row.set_active(C.login_background() is not None)
        self._updating = False

    def _avatar_done(self, ok):
        self.toast("Profile picture updated" if ok else "Could not change the profile picture")

    def _on_login_toggled(self, row, _p):
        if self._updating:
            return
        theme = self._selected_theme() or C.AURORA
        C.set_login_background(C.login_picture(theme) if row.get_active() else None, self._login_done)

    def _on_avatar_toggled(self, row, _p):
        if self._updating:
            return
        prefs = C.load_prefs()
        prefs["avatar"] = row.get_active()
        C.save_prefs(prefs)
        theme = self._selected_theme()
        if row.get_active() and theme and theme.get("avatar"):
            C.set_avatar(theme["avatar"], self._avatar_done)

    # ------------------------------------------------------------ effects
    def _effects_page(self):
        page = self._page("Effects", "Make the desktop as calm or as lively as you like.")
        icons = Adw.PreferencesGroup(title="Taskbar and Dock")
        labels = [label for _kind, label in L.ICON_ANIMATIONS]
        anim = Adw.ComboRow(title="Icon animation",
                            subtitle="What icons do when the pointer moves over them",
                            model=Gtk.StringList.new(labels))
        kinds = [kind for kind, _label in L.ICON_ANIMATIONS]
        current = L.current_icon_animation()
        anim.set_selected(kinds.index(current) if current in kinds else 0)
        anim.connect("notify::selected", lambda c, _p: None if self._updating else
                     L.set_icon_animation(kinds[c.get_selected()]))
        icons.add(anim)
        page.add(icons)

        group = Adw.PreferencesGroup(title="Windows")
        group.add(self._switch_row("Window effects", "Windows open and close with an effect that "
                                                     "matches your character theme",
                                   L.extension_enabled(L.WINDOW_EFFECTS),
                                   lambda on: L.set_extension(L.WINDOW_EFFECTS, on)))
        group.add(self._switch_row("Wobbly windows", "Windows wobble like jelly while you "
                                                     "move them",
                                   L.extension_enabled(L.WOBBLY),
                                   lambda on: L.set_extension(L.WOBBLY, on)))
        group.add(self._switch_row("Magic Lamp", "Windows minimise like a genie into the taskbar",
                                   L.extension_enabled(L.MAGIC_LAMP),
                                   lambda on: L.set_extension(L.MAGIC_LAMP, on)))
        page.add(group)

        group = Adw.PreferencesGroup(title="Desktop")
        group.add(self._switch_row("Glass effects", "Blur behind the taskbar, dock and overview",
                                   L.extension_enabled(L.BLUR),
                                   lambda on: L.set_extension(L.BLUR, on)))
        group.add(self._switch_row("Animations", "Smooth window and menu animations",
                                   L.get_key(L.IFACE, "enable-animations", True),
                                   lambda on: L.set_key(L.IFACE, "enable-animations", on)))
        group.add(self._switch_row("Desktop Cube", "Switch workspaces on a rotating 3D cube",
                                   L.extension_enabled(L.DESKTOP_CUBE),
                                   lambda on: L.set_extension(L.DESKTOP_CUBE, on)))
        group.add(self._switch_row("Keep Awake button", "Quick setting that stops the screen "
                                                        "from sleeping (Caffeine)",
                                   L.extension_enabled(L.CAFFEINE),
                                   lambda on: L.set_extension(L.CAFFEINE, on)))
        page.add(group)
        more = Adw.PreferencesGroup()
        row = Adw.ActionRow(title="More extensions",
                            subtitle="Browse and install GNOME extensions", activatable=True)
        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        row.connect("activated", lambda *_: _spawn(["extension-manager"]))
        more.add(row)
        page.add(more)
        return page


def _spawn(argv):
    try:
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
    except GLib.Error:
        pass


RESET_KEYS = [
    (L.IFACE, "color-scheme"), (L.IFACE, "accent-color"), (L.IFACE, "gtk-theme"),
    (L.IFACE, "icon-theme"), (L.IFACE, "enable-animations"), (L.IFACE, "enable-hot-corners"),
    (L.IFACE, "show-battery-percentage"), (L.WM, "button-layout"),
    (L.BACKGROUND, "picture-uri"), (L.BACKGROUND, "picture-uri-dark"),
    (L.SCREENSAVER, "picture-uri"), (L.SHELL, "enabled-extensions"),
    (L.SHELL, "disabled-extensions"), (L.DTP, "panel-element-positions"), (L.DTP, "panel-size"),
    (L.DTP, "trans-panel-opacity"), (L.DTP, "panel-side-margins"),
    (L.DTP, "panel-top-bottom-margins"), (L.DTP, "global-border-radius"),
    (L.DTP, "stockgs-keep-top-panel"), (L.DTP, "panel-positions"), (L.DTP, "panel-lengths"),
    (L.DTP, "panel-anchors"), (L.DTP, "panel-sizes"), (L.DTP, "intellihide"),
    (L.DTP, "panel-side-padding"), (L.DTP, "show-apps-icon-side-padding"),
    (L.DTP, "intellihide-hide-from-windows"), (L.DTP, "dot-style-focused"),
    (L.DTP, "dot-style-unfocused"), (L.DTP, "animate-appicon-hover"),
    (L.DTP, "animate-appicon-hover-animation-type"),
    (L.ARC, "menu-layout"), (L.DOCK, "dock-position"), (L.DOCK, "extend-height"),
    (L.DOCK, "dock-fixed"), (L.DOCK, "intellihide"), (L.DOCK, "dash-max-icon-size"),
    (L.DING, "show-home"), (L.DING, "show-trash"), (L.DING, "dark-text-in-labels"),
    (L.BACKGROUND, "picture-options"),
]


class AppearanceApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.win = None
        for name, cb in (("reset", self._on_reset), ("about", self._on_about)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if self.win is None:
            self.win = AppearanceWindow(self)
        self.win.present()

    def _on_reset(self, *_):
        dialog = Adw.AlertDialog(heading="Reset appearance?",
                                 body="Layout, style, wallpaper and effects go back to the "
                                      "@DISTRO_NAME@ defaults.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)

        def done(d, result):
            if d.choose_finish(result) == "reset":
                for schema, key in RESET_KEYS:
                    L.reset_key(schema, key)
                self.win.close()
                self.win = AppearanceWindow(self)
                self.win.present()
        dialog.choose(self.win, None, done)

    def _on_about(self, *_):
        about = Adw.AboutDialog(application_name="Appearance", application_icon="raiden-appearance",
                                developer_name="@DISTRO_NAME@", version="1.0",
                                comments="Choose your desktop layout, style and effects.",
                                license_type=Gtk.License.GPL_3_0)
        about.present(self.win)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--layout" in argv:
        i = argv.index("--layout")
        if i + 1 >= len(argv):
            print("usage: raiden-appearance --layout {" + ",".join(L.LAYOUT_ORDER) + "}")
            return 2
        try:
            L.apply_layout(argv[i + 1])
        except ValueError as exc:
            print(exc)
            return 2
        Gio.Settings.sync()
        return 0
    if "--current-layout" in argv:
        print(L.current_layout())
        return 0
    if "--character" in argv:
        i = argv.index("--character")
        themes = C.available() + [C.AURORA]
        ids = [t["id"] for t in themes]
        if i + 1 >= len(argv) or argv[i + 1] not in ids:
            print("usage: raiden-appearance --character {" + ",".join(ids) + "}")
            return 2
        C.apply(next(t for t in themes if t["id"] == argv[i + 1]))
        Gio.Settings.sync()
        return 0
    return AppearanceApp().run([argv[0]])
