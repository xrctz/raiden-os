#!/bin/bash
# Brings a computer installed from an older Raiden OS ISO up to this build.
# The build puts this script next to the new packages; copy that whole folder
# to the installed computer, open a terminal in it and run:
#
#   sudo ./update-installed-system.sh
#
# It adds what the new apps need first (32-bit support for Steam, Google's
# and Anthropic's apt repositories for Chrome and Claude), then installs the
# packages; raiden-desktop brings in the new apps. Needs internet.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"

log() { printf '\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
lists=/etc/apt/sources.list.d

log "32-bit libraries (Steam and 32-bit games)"
dpkg --add-architecture i386

# The same files Chrome's and Claude's own packages write (they keep them
# current from then on); skipped when the repository is already set up.
if ! grep -qs 'dl.google.com/linux/chrome' "$lists"/*; then
  log "Google Chrome repository"
  gpg --dearmor < keys/google-linux-signing-key.asc > /usr/share/keyrings/google-chrome.gpg
  cat > "$lists/google-chrome.sources" <<'EOF'
### THIS FILE IS AUTOMATICALLY CONFIGURED ###
# Changes to this file will not be preserved.
# This file will not be recreated if removed.
X-Repolib-Name: Google Chrome
Types: deb
URIs: https://dl.google.com/linux/chrome-stable/deb/
Suites: stable
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/google-chrome.gpg
EOF
  chmod 644 /usr/share/keyrings/google-chrome.gpg "$lists/google-chrome.sources"
fi
if ! grep -qs 'downloads.claude.ai/claude-desktop' "$lists"/*; then
  log "Claude repository"
  install -m644 keys/claude-desktop.asc /usr/share/keyrings/claude-desktop-archive-keyring.asc
  cat > "$lists/claude-desktop.list" <<'EOF'
### Managed by the claude-desktop package.
### Set CLAUDE_DESKTOP_ADD_REPO="true"|"false" in /etc/default/claude-desktop
### to force this entry on or off; remove this file too when opting out.
deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/claude-desktop-archive-keyring.asc] https://downloads.claude.ai/claude-desktop/apt/stable stable main
EOF
  chmod 644 "$lists/claude-desktop.list"
fi

log "Updating package lists"
apt-get update

log "Installing the new Raiden OS packages and apps"
# raiden-live is only for the live USB session
mapfile -t debs < <(ls ./*.deb | grep -v '/raiden-live_')
apt-get install -y "${debs[@]}"

log "32-bit graphics drivers and game libraries"
extra=(mesa-vulkan-drivers:i386 libgl1-mesa-dri:i386 libgamemode0:i386 libgamemodeauto0:i386)
# the 32-bit half of the NVIDIA driver in use (595, 580, ...)
for gl in $(dpkg-query -W -f='${Package} ${Status}\n' 'libnvidia-gl-*' 2>/dev/null |
            awk '$NF == "installed" {print $1}'); do
  extra+=("$gl:i386")
done
apt-get install -y "${extra[@]}"

log "Done"
echo "Antigravity, Antigravity IDE and ProtonPlus download in the background in"
echo "the next minutes (see: systemctl status raiden-apps-update). Log out and"
echo "back in once so the new groups (games, virtual machines) take effect."
