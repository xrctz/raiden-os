#!/bin/bash
# Generates every derived asset of Raiden OS from the sources in artwork/
# (SVG logo/icons + the Blender renders in artwork/renders).
#
#   make-assets.sh OUTDIR
#
# Needs: rsvg-convert, ImageMagick (convert), grub-mkfont, python3 and the
# Inter font (all installed by the "host" stage of scripts/build.sh).
set -Eeuo pipefail

ART="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
SRC_DIR="$(dirname "$ART")"
. "$SRC_DIR/build.conf"
OUT="${1:?usage: make-assets.sh OUTDIR}"
R="$ART/renders"
ID="$DISTRO_ID"
INTER=/usr/share/fonts/opentype/inter

for tool in rsvg-convert convert grub-mkfont python3; do
  command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 1; }
done
[ -f "$INTER/Inter-Regular.otf" ] || { echo "Inter font missing (apt install fonts-inter)" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Text in SVGs is converted to outlines, so installed SVGs never depend on fonts.
outline_svg() { rsvg-convert -f svg "$1" -o "$2"; }

# --------------------------------------------------------------------- icons
ICONS="$OUT/icons/hicolor"
for name in raiden-os-logo raiden-appearance raiden-welcome raiden-os-installer; do
  src="$ART/icons/$name.svg"
  [ -f "$src" ] || src="$ART/logo/$name.svg"
  install -Dm644 "$src" "$ICONS/scalable/apps/$name.svg"
  for s in 16 22 24 32 48 64 96 128 256 512; do
    mkdir -p "$ICONS/${s}x${s}/apps"
    rsvg-convert -w "$s" -h "$s" "$src" -o "$ICONS/${s}x${s}/apps/$name.png"
  done
done
install -Dm644 "$ART/logo/raiden-os-logo-symbolic.svg" "$ICONS/symbolic/apps/raiden-os-logo-symbolic.svg"

# ------------------------------------------------------------------ wordmarks
wordmark() { # text-colour output.svg
  sed -e "s/@TEXT@/$1/" -e "s/@NAME@/$DISTRO_NAME/" "$ART/wordmark.svg.in" > "$TMP/wm.svg"
  outline_svg "$TMP/wm.svg" "$2"
}
wordmark "#1B1F3B" "$TMP/wordmark-dark-text.svg"     # for light backgrounds
wordmark "#FFFFFF" "$TMP/wordmark-light-text.svg"    # for dark backgrounds
# GNOME Settings > About shows LOGO from os-release, preferring the "-text" variants
install -Dm644 "$TMP/wordmark-dark-text.svg"  "$ICONS/scalable/apps/raiden-os-logo-text.svg"
install -Dm644 "$TMP/wordmark-light-text.svg" "$ICONS/scalable/apps/raiden-os-logo-text-dark.svg"
mkdir -p "$OUT/pixmaps"
# GNOME 50 shows the login-screen logo at its natural size: keep it modest
rsvg-convert -h 56 "$TMP/wordmark-light-text.svg" -o "$OUT/pixmaps/$ID-gdm-logo.png"
rsvg-convert -w 256 -h 256 "$ART/logo/raiden-os-logo.svg" -o "$OUT/pixmaps/$ID-logo.png"
convert "$R/logo/raiden-os-emblem-3d.png" -trim +repage -resize 512x512 "$OUT/pixmaps/$ID-emblem-3d.png"

# -------------------------------------------------------------- backgrounds
B="$OUT/backgrounds/$ID"
mkdir -p "$B" "$OUT/gnome-background-properties"
# every render, with its "-ultrawide" (3440x1440) version where there is one;
# display-setup swaps that in on ultrawide monitors
for png in "$R"/wallpapers/*.png; do
  w="$(basename "$png" .png)"
  convert "$png" -sampling-factor 4:4:4 -quality 92 "$B/$w.jpg"
done
cat > "$OUT/gnome-background-properties/$ID-backgrounds.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE wallpapers SYSTEM "gnome-wp-list.dtd">
<wallpapers>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Aurora</name>
    <filename>/usr/share/backgrounds/$ID/aurora-light.jpg</filename>
    <filename-dark>/usr/share/backgrounds/$ID/aurora-dark.jpg</filename-dark>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#0b1020</pcolor>
    <scolor>#0b1020</scolor>
  </wallpaper>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Aurora Night</name>
    <filename>/usr/share/backgrounds/$ID/aurora-dark.jpg</filename>
    <filename-dark>/usr/share/backgrounds/$ID/aurora-dark.jpg</filename-dark>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#05070f</pcolor>
    <scolor>#05070f</scolor>
  </wallpaper>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Nebula</name>
    <filename>/usr/share/backgrounds/$ID/nebula-dark.jpg</filename>
    <filename-dark>/usr/share/backgrounds/$ID/nebula-dark.jpg</filename-dark>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#0c0718</pcolor>
    <scolor>#0c0718</scolor>
  </wallpaper>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Lagoon</name>
    <filename>/usr/share/backgrounds/$ID/lagoon-dark.jpg</filename>
    <filename-dark>/usr/share/backgrounds/$ID/lagoon-dark.jpg</filename-dark>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#04121a</pcolor>
    <scolor>#04121a</scolor>
  </wallpaper>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Arcane</name>
    <filename>/usr/share/backgrounds/$ID/arcane.jpg</filename>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#07040c</pcolor>
    <scolor>#07040c</scolor>
  </wallpaper>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Storm</name>
    <filename>/usr/share/backgrounds/$ID/storm.jpg</filename>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#05040f</pcolor>
    <scolor>#05040f</scolor>
  </wallpaper>
  <wallpaper deleted="false">
    <name>$DISTRO_NAME Crimson King</name>
    <filename>/usr/share/backgrounds/$ID/crimson.jpg</filename>
    <options>zoom</options>
    <shade_type>solid</shade_type>
    <pcolor>#0a0103</pcolor>
    <scolor>#0a0103</scolor>
  </wallpaper>
</wallpapers>
EOF

# ---------------------------------------------------------------- plymouth
P="$OUT/plymouth/$ID"
mkdir -p "$P"
cp "$R/plymouth/"throbber-*.png "$P/"
cp "$SRC_DIR/vendor/plymouth-dialog/"*.png "$P/"
cat > "$TMP/watermark.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="110" viewBox="0 0 600 110">
  <text x="300" y="78" text-anchor="middle" font-family="Inter" font-weight="500" font-size="64"
        letter-spacing="1" fill="#E6EAFF">$DISTRO_NAME</text>
</svg>
EOF
rsvg-convert -w 300 "$TMP/watermark.svg" -o "$P/watermark.png"
cat > "$P/$ID.plymouth" <<EOF
[Plymouth Theme]
Name=$DISTRO_NAME
Description=$DISTRO_NAME boot splash: glossy emblem with a rotating light ring
ModuleName=two-step

[two-step]
Font=Ubuntu 12
TitleFont=Ubuntu Light 30
ImageDir=/usr/share/plymouth/themes/$ID
DialogHorizontalAlignment=.5
DialogVerticalAlignment=.382
TitleHorizontalAlignment=.5
TitleVerticalAlignment=.382
HorizontalAlignment=.5
VerticalAlignment=.5
WatermarkHorizontalAlignment=.5
WatermarkVerticalAlignment=.9
Transition=none
TransitionDuration=0.0
BackgroundStartColor=0x000000
BackgroundEndColor=0x000000
ProgressBarBackgroundColor=0x262b45
ProgressBarForegroundColor=0x6f95ff
MessageBelowAnimation=true

[boot-up]
UseEndAnimation=false

[shutdown]
UseEndAnimation=false

[reboot]
UseEndAnimation=false

[updates]
SuppressMessages=true
ProgressBarShowPercentComplete=true
UseProgressBar=true
Title=Installing Updates...
SubTitle=Do not turn off your computer

[system-upgrade]
SuppressMessages=true
ProgressBarShowPercentComplete=true
UseProgressBar=true
Title=Upgrading System...
SubTitle=Do not turn off your computer

[firmware-upgrade]
SuppressMessages=true
ProgressBarShowPercentComplete=true
UseProgressBar=true
Title=Upgrading Firmware...
SubTitle=Do not turn off your computer

[system-reset]
SuppressMessages=true
ProgressBarShowPercentComplete=true
UseProgressBar=true
Title=Resetting System...
SubTitle=Do not turn off your computer
EOF

# -------------------------------------------------------------- GRUB theme
G="$OUT/grub/$ID"
mkdir -p "$G"
rsvg-convert -w 460 "$TMP/wordmark-light-text.svg" -o "$TMP/grub-wordmark.png"
convert "$R/wallpapers/aurora-dark.png" -resize 1920x1080^ -gravity center -extent 1920x1080 \
  \( -size 1920x1080 xc:'#04060E' -alpha set -channel A -evaluate set 58% +channel \) -composite \
  -blur 0x5 \
  "$TMP/grub-wordmark.png" -gravity north -geometry +0+190 -composite \
  -depth 8 "PNG24:$G/background.png"
# Rounded selection highlight, cut into the 9 slices GRUB stretches. GRUB draws
# the border slices OUTSIDE the item box, so they are kept small (8 px) and the
# menu spacing below leaves room for them.
convert -size 32x32 xc:none -fill 'rgba(120,150,255,0.22)' -stroke 'rgba(170,195,255,0.6)' \
  -strokewidth 1.5 -draw 'roundrectangle 1,1 30,30 7,7' "$TMP/sel.png"
slice() { convert "$TMP/sel.png" -crop "$2" +repage "PNG32:$G/select_$1.png"; }
slice nw 8x8+0+0;  slice n 16x8+8+0;  slice ne 8x8+24+0
slice w  8x16+0+8; slice c 16x16+8+8; slice e  8x16+24+8
slice sw 8x8+0+24; slice s 16x8+8+24; slice se 8x8+24+24
RANGES="0x20-0x24F,0x370-0x3FF,0x400-0x4FF,0x2000-0x206F,0x2190-0x21FF,0x25A0-0x25FF"
# Inter's static weights all report the style "Regular", so give the semibold
# face its own family name (-n sets the family; GRUB appends style and size).
grub-mkfont -s 16 -r "$RANGES" -n "Inter" -o "$G/inter-regular-16.pf2" "$INTER/Inter-Regular.otf" 2>/dev/null
grub-mkfont -s 20 -r "$RANGES" -n "Inter" -o "$G/inter-regular-20.pf2" "$INTER/Inter-Regular.otf" 2>/dev/null
grub-mkfont -s 20 -r "$RANGES" -n "Inter SemiBold" -o "$G/inter-semibold-20.pf2" "$INTER/Inter-SemiBold.otf" 2>/dev/null
pf2name() {
  python3 - "$1" <<'PY'
import struct, sys
data = open(sys.argv[1], "rb").read()
i = data.index(b"NAME")
n = struct.unpack(">I", data[i + 4:i + 8])[0]
print(data[i + 8:i + 8 + n].rstrip(b"\0").decode())
PY
}
F16="$(pf2name "$G/inter-regular-16.pf2")"
F20="$(pf2name "$G/inter-regular-20.pf2")"
F20B="$(pf2name "$G/inter-semibold-20.pf2")"
cat > "$G/theme.txt" <<EOF
# $DISTRO_NAME GRUB theme
title-text: ""
desktop-image: "background.png"
desktop-image-scale-method: "crop"
desktop-color: "#05070F"
terminal-left: "8%"
terminal-top: "10%"
terminal-width: "84%"
terminal-height: "80%"
terminal-border: "0"

+ boot_menu {
    left = 28%
    top = 44%
    width = 44%
    height = 38%
    item_font = "$F20"
    item_color = "#C7D0F2"
    selected_item_font = "$F20B"
    selected_item_color = "#FFFFFF"
    item_height = 40
    item_padding = 14
    item_spacing = 22
    icon_width = 0
    icon_height = 0
    item_icon_space = 0
    selected_item_pixmap_style = "select_*.png"
    scrollbar = false
}

+ label {
    id = "__timeout__"
    left = 0
    top = 86%
    width = 100%
    align = "center"
    color = "#8E9CCB"
    font = "$F16"
    text = "Starting automatically in %d seconds"
}

+ label {
    left = 0
    top = 91%
    width = 100%
    align = "center"
    color = "#6874A6"
    font = "$F16"
    text = "↑ ↓  choose     •     Enter  start     •     E  edit     •     C  command line"
}
EOF

# -------------------------------------------------------- Calamares branding
C="$OUT/calamares/$ID"
mkdir -p "$C"
rsvg-convert -w 256 -h 256 "$ART/logo/raiden-os-logo.svg" -o "$C/logo.png"
rsvg-convert -w 128 -h 128 "$ART/logo/raiden-os-logo.svg" -o "$C/icon.png"
# Calamares runs as root with the (dark) system default style
rsvg-convert -w 560 "$TMP/wordmark-light-text.svg" -o "$C/welcome.png"
i=0
for spec in "aurora-dark:+0+0" "nebula-dark:+700+200" "lagoon-dark:+300+500" \
            "aurora-dark:+1500+900" "nebula-dark:+0+800" "lagoon-dark:+1600+100"; do
  i=$((i + 1))
  w="${spec%%:*}"; off="${spec#*:}"
  convert "$R/wallpapers/$w.png" -crop "2400x1350$off" +repage -resize 1000x562^ \
    -gravity center -extent 1000x562 \
    \( -size 1000x562 gradient:'rgba(5,7,15,0.15)-rgba(5,7,15,0.78)' -rotate 90 -resize 1000x562! \) \
    -compose over -composite -quality 90 "$C/slide$i.jpg"
done

# ---------------------------------------------------------------- fastfetch
# The real logo as true-colour half-block art (2 pixels per terminal cell).
mkdir -p "$OUT/fastfetch"
rsvg-convert -w 30 -h 30 "$ART/logo/raiden-os-logo.svg" -o "$TMP/ff.png"
convert "$TMP/ff.png" -depth 8 txt:- | python3 -c '
import re, sys
W = H = 30
px = {}
for line in sys.stdin:
    m = re.match(r"(\d+),(\d+): \(\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", line)
    if m:
        x, y = int(m.group(1)), int(m.group(2))
        r, g, b, a = (float(v) for v in m.groups()[2:])
        px[(x, y)] = (int(r), int(g), int(b), a if a <= 1 else a / 255)
out = []
for y in range(0, H, 2):
    row = ""
    for x in range(W):
        t, bt = px[(x, y)], px[(x, y + 1)]
        top, bot = t[3] > 0.5, bt[3] > 0.5
        if top and bot:
            row += "\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀" % (t[:3] + bt[:3])
        elif top:
            row += "\x1b[49m\x1b[38;2;%d;%d;%dm▀" % t[:3]
        elif bot:
            row += "\x1b[49m\x1b[38;2;%d;%d;%dm▄" % bt[:3]
        else:
            row += "\x1b[0m "
    out.append(row + "\x1b[0m")
sys.stdout.write("\n".join(out) + "\n")
' > "$OUT/fastfetch/logo.ansi"

# --------------------------------------------------------- character themes
# Built only from personal art on this PC (personal/characters/, not in git),
# and never for the public edition
if [ "$EDITION" != public ]; then
  python3 "$ART/make-characters.py" "$SRC_DIR" "$OUT/characters"
fi

echo "assets written to $OUT"
