#!/bin/bash
# Development helper: clone the base chroot and trial-install the full package
# set, to validate package names/conflicts and inspect the real files.
set -Eeuo pipefail
SRC_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
. "$SRC_DIR/build.conf"
. "$SRC_DIR/scripts/lib.sh"
WORK=/var/tmp/raiden-build
CHROOT=$WORK/explore
trap 'umount_chroot' EXIT

if [ ! -d "$CHROOT" ]; then
  log "cloning base chroot"
  cp -a "$WORK/chroot" "$CHROOT"
fi
mount_chroot

pkgs() { read_list "$1" | sed 's/ *| *[^ ]*//g'; }   # take the first alternative
# shellcheck disable=SC2046
log "installing desktop + live package set"
apt_in_chroot update
apt_in_chroot install $(pkgs "$SRC_DIR/config/packages/desktop-depends.list") \
                      $(pkgs "$SRC_DIR/config/packages/desktop-recommends.list") \
                      $(pkgs "$SRC_DIR/config/packages/live-depends.list")
log "installing NVIDIA"
apt_in_chroot install "nvidia-driver-${NVIDIA_BRANCH}-open" "linux-modules-nvidia-${NVIDIA_BRANCH}-open-${KERNEL_FLAVOUR}"
log "EXPLORE INSTALL DONE"
in_chroot dpkg-query -W -f='${Package}\n' | wc -l
