#!/bin/bash
# Downloads the few third-party pieces that are not in the Ubuntu archive.
# Every file is pinned to an exact version and verified against vendor/SHA256SUMS,
# so a build is reproducible and cannot silently pick up a changed upstream file.
#
#   fetch-vendor.sh            download missing files and verify all checksums
#   fetch-vendor.sh --record   (maintainers) re-download and rewrite SHA256SUMS
set -Eeuo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$SRC_DIR/vendor"
SUMS="$VENDOR/SHA256SUMS"
RECORD=0
[ "${1:-}" = "--record" ] && RECORD=1

# name|url
FILES=(
  "extensions/dash-to-panel@jderose9.github.com.zip|https://extensions.gnome.org/download-extension/dash-to-panel@jderose9.github.com.shell-extension.zip?version_tag=75054"
  "extensions/arcmenu@arcmenu.com.zip|https://extensions.gnome.org/download-extension/arcmenu@arcmenu.com.shell-extension.zip?version_tag=75483"
  "extensions/blur-my-shell@aunetx.zip|https://extensions.gnome.org/download-extension/blur-my-shell@aunetx.shell-extension.zip?version_tag=76770"
  "extensions/compiz-alike-magic-lamp-effect@hermes83.github.com.zip|https://extensions.gnome.org/download-extension/compiz-alike-magic-lamp-effect@hermes83.github.com.shell-extension.zip?version_tag=76122"
  "extensions/desktop-cube@schneegans.github.com.zip|https://extensions.gnome.org/download-extension/desktop-cube@schneegans.github.com.shell-extension.zip?version_tag=76156"
  "extensions/caffeine@patapon.info.zip|https://extensions.gnome.org/download-extension/caffeine@patapon.info.shell-extension.zip?version_tag=76057"
  "extensions/burn-my-windows@schneegans.github.com.zip|https://extensions.gnome.org/download-extension/burn-my-windows@schneegans.github.com.shell-extension.zip?version_tag=75536"
  "extensions/compiz-windows-effect@hermes83.github.com.zip|https://extensions.gnome.org/download-extension/compiz-windows-effect@hermes83.github.com.shell-extension.zip?version_tag=76121"
  "themes/adw-gtk3v6.5.tar.xz|https://github.com/lassekongo83/adw-gtk3/releases/download/v6.5/adw-gtk3v6.5.tar.xz"
  "keys/packages.mozilla.org.asc|https://packages.mozilla.org/apt/repo-signing-key.gpg"
  "keys/google-linux-signing-key.asc|https://dl.google.com/linux/linux_signing_key.pub"
  "keys/claude-desktop.asc|https://downloads.claude.ai/claude-desktop/key.asc"
  "flatpak/flathub.flatpakrepo|https://dl.flathub.org/repo/flathub.flatpakrepo"
  # Apps without an apt repository (vendor/apps/ is not in git: too big)
  "apps/antigravity-2.24.0-5780333019398144-linux-x64.tar.gz|https://storage.googleapis.com/antigravity-public/antigravity-hub/2.24.0-5780333019398144/linux-x64/Antigravity.tar.gz"
  "apps/antigravity-ide-2.5.5-4923483625488384-linux-x64.tar.gz|https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.5.5-4923483625488384/linux-x64/Antigravity%20IDE.tar.gz"
  "apps/heroic_2.22.4_amd64.deb|https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/releases/download/v2.22.4/Heroic-2.22.4-linux-amd64.deb"
  "apps/protonplus-0.6.8-x86_64.AppImage|https://github.com/Vysp3r/ProtonPlus/releases/download/v0.6.8/ProtonPlus-0.6.8-anylinux-x86_64.AppImage"
)

# APT signing keys must be the ones their publishers document, whatever the
# checksums say: file|primary key fingerprint|publisher
KEYS=(
  "keys/packages.mozilla.org.asc|35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3|Mozilla"
  "keys/google-linux-signing-key.asc|EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796|Google"
  "keys/claude-desktop.asc|31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE|Anthropic"
)

mkdir -p "$VENDOR"
for entry in "${FILES[@]}"; do
  case "$entry" in "#"*) continue ;; esac
  name="${entry%%|*}"; url="${entry#*|}"
  dest="$VENDOR/$name"
  mkdir -p "$(dirname "$dest")"
  if [ ! -s "$dest" ] || [ "$RECORD" = 1 ]; then
    echo "  downloading $name"
    curl -fsSL --retry 3 -o "$dest.part" "$url"
    mv "$dest.part" "$dest"
  fi
done

for entry in "${KEYS[@]}"; do
  IFS='|' read -r name want who <<< "$entry"
  fpr=$(gpg --batch --show-keys --with-colons "$VENDOR/$name" 2>/dev/null | awk -F: '/^fpr:/{print $10; exit}')
  if [ "$fpr" != "$want" ]; then
    echo "ERROR: $who APT key fingerprint mismatch ($fpr)" >&2; exit 1
  fi
done

cd "$VENDOR"
if [ "$RECORD" = 1 ] || [ ! -f "$SUMS" ]; then
  : > "$SUMS"
  for entry in "${FILES[@]}"; do
    case "$entry" in "#"*) continue ;; esac
    sha256sum "${entry%%|*}" >> "$SUMS"
  done
  echo "  recorded checksums in vendor/SHA256SUMS"
fi
sha256sum --quiet -c "$SUMS"
echo "  vendor files verified"
