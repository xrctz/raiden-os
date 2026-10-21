#!/bin/bash
# Raiden OS ISO builder.
#
# Runs as root inside an Ubuntu 26.04 environment (the "RaidenOS-Build" WSL
# distro created by build.ps1, or any Ubuntu 26.04 machine/VM).
#
#   build.sh                 run every stage that has not completed yet
#   build.sh --redo STAGE    re-run STAGE and every stage after it
#   build.sh --only STAGE    run just one stage (for debugging)
#   build.sh --clean         delete the work directory and start from scratch
#
# Stages: host bootstrap aptsetup base desktop configure squashfs iso
set -Eeuo pipefail

SRC_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
. "$SRC_DIR/build.conf"
. "$SRC_DIR/scripts/lib.sh"

WORK="${WORK:-/var/tmp/raiden-build}"
CHROOT="$WORK/chroot"
ISO_ROOT="$WORK/iso"
DEBS="$WORK/debs"
OUT_DIR="${OUT_DIR:-$SRC_DIR/out}"
STAGES=(host bootstrap aptsetup base desktop configure squashfs iso)

[ "$(id -u)" -eq 0 ] || die "run as root"
. /etc/os-release
[ "${VERSION_CODENAME:-}" = "$UBUNTU_SUITE" ] || warn "build host is ${VERSION_CODENAME:-unknown}, expected $UBUNTU_SUITE"

trap 'rc=$?; umount_chroot; exit $rc' EXIT
trap 'die "build failed at line $LINENO (stage: ${CURRENT_STAGE:-?})"' ERR

# --------------------------------------------------------------------------
stage_host() {
  log "Installing build tools on the host"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    debootstrap squashfs-tools xorriso mtools dosfstools rsync zstd curl gnupg ca-certificates \
    python3 python3-gi gir1.2-glib-2.0 unzip xz-utils imagemagick librsvg2-bin \
    qemu-system-x86 qemu-utils ovmf >/dev/null
  bash "$SRC_DIR/scripts/fetch-vendor.sh"
}

# --------------------------------------------------------------------------
stage_bootstrap() {
  log "Bootstrapping Ubuntu $UBUNTU_VERSION ($UBUNTU_SUITE) into $CHROOT"
  umount_chroot
  rm -rf "$CHROOT"
  mkdir -p "$CHROOT"
  debootstrap --arch="$ARCH" --variant=minbase \
    --components=main,restricted,universe,multiverse \
    --include=ca-certificates,apt-utils,locales,gpg \
    "$UBUNTU_SUITE" "$CHROOT" "$MIRROR"
}

# --------------------------------------------------------------------------
stage_aptsetup() {
  log "Configuring APT, locale and build-time safety nets"
  local settings="$SRC_DIR/packages/raiden-os-settings/root"

  # Ubuntu archive (deb822 format, like a stock Ubuntu 26.04 install)
  rm -f "$CHROOT/etc/apt/sources.list"
  cat > "$CHROOT/etc/apt/sources.list.d/ubuntu.sources" <<EOF
Types: deb
URIs: $MIRROR
Suites: $UBUNTU_SUITE $UBUNTU_SUITE-updates $UBUNTU_SUITE-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: $SECURITY_MIRROR
Suites: $UBUNTU_SUITE-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

  # Mozilla's repository + package policy (the same files the settings package
  # ships, so placeholders filled in the same way): the Firefox Mozilla
  # publishes instead of Ubuntu's Snap wrapper
  local pref
  pref="$(<"$settings/etc/apt/preferences.d/raiden-os.pref")"
  mkdir -p "$CHROOT/etc/apt/preferences.d"
  printf '%s\n' "${pref//@DISTRO_NAME@/$DISTRO_NAME}" > "$CHROOT/etc/apt/preferences.d/raiden-os.pref"
  install -Dm644 "$settings/etc/apt/sources.list.d/mozilla.sources" "$CHROOT/etc/apt/sources.list.d/mozilla.sources"
  install -Dm644 "$SRC_DIR/vendor/keys/packages.mozilla.org.asc" "$CHROOT/usr/share/keyrings/packages.mozilla.org.asc"

  # Never start services inside the build chroot
  printf '#!/bin/sh\nexit 101\n' > "$CHROOT/usr/sbin/policy-rc.d"
  chmod 755 "$CHROOT/usr/sbin/policy-rc.d"

  # Networking for the chroot (restored to the systemd-resolved symlink later)
  rm -f "$CHROOT/etc/resolv.conf"
  cp -L /etc/resolv.conf "$CHROOT/etc/resolv.conf"
  echo "$LIVE_HOSTNAME" > "$CHROOT/etc/hostname"
  printf '127.0.0.1\tlocalhost\n127.0.1.1\t%s\n\n::1\tlocalhost ip6-localhost ip6-loopback\nff02::1\tip6-allnodes\nff02::2\tip6-allrouters\n' \
    "$LIVE_HOSTNAME" > "$CHROOT/etc/hosts"
  # Temporary machine id for package scripts; emptied before the squashfs is made
  tr -d '-' < /proc/sys/kernel/random/uuid > "$CHROOT/etc/machine-id"

  mount_chroot
  # Debconf answers so nothing ever waits for input
  in_chroot debconf-set-selections <<'EOF'
keyboard-configuration keyboard-configuration/layoutcode string us
keyboard-configuration keyboard-configuration/modelcode string pc105
tzdata tzdata/Areas select Etc
tzdata tzdata/Zones/Etc select UTC
grub-pc grub-pc/install_devices multiselect
grub-pc grub-pc/install_devices_empty boolean true
grub-efi-amd64-signed grub2/update_nvram boolean false
EOF
  in_chroot locale-gen en_US.UTF-8 >/dev/null
  in_chroot update-locale LANG=en_US.UTF-8
  apt_in_chroot update
}

# --------------------------------------------------------------------------
stage_base() {
  log "Installing the Ubuntu base system, kernel and firmware"
  mount_chroot
  apt_in_chroot full-upgrade
  # shellcheck disable=SC2046
  apt_in_chroot install $(read_list "$SRC_DIR/config/packages/base.list")
  in_chroot dpkg -s initramfs-tools >/dev/null || die "initramfs-tools missing"
  if in_chroot dpkg -s dracut >/dev/null 2>&1; then die "dracut got installed; casper needs initramfs-tools"; fi
}

# --------------------------------------------------------------------------
stage_desktop() {
  log "Building Raiden OS packages ($EDITION edition)"
  bash "$SRC_DIR/scripts/build-packages.sh" "$DEBS"

  log "Installing the desktop, apps, live system, drivers and Raiden OS packages"
  mount_chroot
  # 32-bit libraries: Steam and 32-bit games (Windows games through Proton too)
  in_chroot dpkg --add-architecture i386
  # raiden-desktop recommends Chrome and Claude: the personal edition installs
  # them from their repositories. The public edition must not pass them on, so
  # it adds the repositories only at the end, for the first-start install.
  if [ "$EDITION" != public ]; then add_app_repos; fi
  rm -rf "$CHROOT/tmp/raiden-debs"
  mkdir -p "$CHROOT/tmp/raiden-debs"
  cp "$DEBS"/*.deb "$CHROOT/tmp/raiden-debs/"     # ours, and Heroic's
  apt_in_chroot update
  # Updates published since the base layer was built (security fixes etc.)
  apt_in_chroot full-upgrade
  # shellcheck disable=SC2046
  apt_in_chroot install $(cd "$CHROOT" && ls tmp/raiden-debs/*.deb | sed 's|^|/|')
  if [ "$EDITION" = public ]; then
    # Mozilla's Firefox is the browser until Chrome arrives on first start
    apt_in_chroot install firefox
  elif in_chroot dpkg-query -W -f='${db:Status-Status}' firefox 2>/dev/null | grep -qx installed; then
    # Google Chrome replaced Firefox; a work directory from before still has it
    apt_in_chroot purge firefox
  fi
  # Heroic's package adds its AppArmor profile (which lets its sandbox work
  # under Ubuntu's user namespace rules) only where AppArmor is running, and
  # it does not run in the build chroot
  if [ -f "$CHROOT/opt/Heroic/resources/apparmor-profile" ]; then
    install -m644 "$CHROOT/opt/Heroic/resources/apparmor-profile" "$CHROOT/etc/apparmor.d/heroic"
  fi

  log "Installing NVIDIA $NVIDIA_BRANCH driver (open kernel modules, prebuilt + signed)"
  apt_in_chroot install "nvidia-driver-${NVIDIA_BRANCH}-open" \
    "linux-modules-nvidia-${NVIDIA_BRANCH}-open-${KERNEL_FLAVOUR}" "libnvidia-gl-${NVIDIA_BRANCH}:i386"

  log "Installing 32-bit graphics and game libraries"
  apt_in_chroot install mesa-vulkan-drivers:i386 libgl1-mesa-dri:i386 \
    libgamemode0:i386 libgamemodeauto0:i386

  # ProtonPlus is free software; Antigravity goes onto personal ISOs only
  log "Installing apps without an apt repository into /opt"
  rm -rf "$CHROOT/tmp/raiden-apps"
  mkdir -p "$CHROOT/tmp/raiden-apps"
  cp "$SRC_DIR"/vendor/apps/protonplus-*.AppImage "$CHROOT/tmp/raiden-apps/"
  if [ "$EDITION" != public ]; then
    cp "$SRC_DIR"/vendor/apps/antigravity-*-linux-x64.tar.gz "$CHROOT/tmp/raiden-apps/"
  fi
  # shellcheck disable=SC2046
  in_chroot /usr/libexec/raiden-os/apps-update install $(cd "$CHROOT" && ls tmp/raiden-apps/* | sed 's|^|/|')
  rm -rf "$CHROOT/tmp/raiden-apps"

  # A kernel update leaves the previous kernel installed; ship only the newest
  local kver k
  kver=$(in_chroot linux-version list | sort -V | tail -1)
  for k in $(in_chroot linux-version list); do
    [ "$k" = "$kver" ] && continue
    info "removing old kernel $k"
    apt_in_chroot purge "linux-image-$k" "linux-modules-$k"
  done
  [ "$(in_chroot linux-version list | wc -l)" -eq 1 ] || die "more than one kernel left in the image"

  # Safety checks: nothing may need DKMS (it would break Secure Boot installs)
  if in_chroot dpkg-query -W -f='${Package} ${Status}\n' 'nvidia-dkms-*' 'dkms' 2>/dev/null | grep -q ' installed$'; then
    die "a DKMS NVIDIA package was installed; prebuilt signed modules expected"
  fi
  in_chroot modinfo -k "$kver" nvidia >/dev/null || die "no prebuilt nvidia module for kernel $kver"
  info "kernel $kver with prebuilt NVIDIA $NVIDIA_BRANCH module"
  local present=(steam-installer heroic raiden-apps raiden-gaming) absent=() files=(/opt/protonplus/AppRun)
  if [ "$EDITION" = public ]; then
    present+=(firefox)
    absent+=(google-chrome-stable claude-desktop)
  else
    present+=(google-chrome-stable claude-desktop)
    files+=(/opt/antigravity/antigravity /opt/antigravity-ide/antigravity-ide)
  fi
  for k in "${present[@]}"; do
    in_chroot dpkg-query -W -f='${Status}' "$k" 2>/dev/null | grep -q 'ok installed' || die "$k is not installed"
  done
  for k in "${absent[@]}"; do
    if in_chroot dpkg-query -W -f='${Status}' "$k" 2>/dev/null | grep -q 'ok installed'; then
      die "$k must not be on the public edition"
    fi
  done
  for k in "${files[@]}"; do
    [ -x "$CHROOT$k" ] || die "missing in image: $k"
  done
  if [ "$EDITION" = public ]; then
    for k in /opt/antigravity /opt/antigravity-ide /usr/share/raiden-os/characters \
             "/usr/share/backgrounds/$DISTRO_ID/characters"; do
      [ ! -e "$CHROOT$k" ] || die "$k must not be on the public edition"
    done
    add_app_repos
  fi

  add_nvidia_legacy_pool
  rm -rf "$CHROOT/tmp/raiden-debs"
}

# Third-party apt repositories: Google Chrome and Claude. Each app's package
# rewrites its own repository file when it is installed or updated, so the
# files are created here exactly as those packages write them: apt never sees
# a repository twice, and the apps keep their entries current.
add_app_repos() {
  local keys="$CHROOT/usr/share/keyrings" lists="$CHROOT/etc/apt/sources.list.d"
  gpg --dearmor < "$SRC_DIR/vendor/keys/google-linux-signing-key.asc" > "$keys/google-chrome.gpg"
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
  install -m644 "$SRC_DIR/vendor/keys/claude-desktop.asc" "$keys/claude-desktop-archive-keyring.asc"
  cat > "$lists/claude-desktop.list" <<'EOF'
### Managed by the claude-desktop package.
### Set CLAUDE_DESKTOP_ADD_REPO="true"|"false" in /etc/default/claude-desktop
### to force this entry on or off; remove this file too when opting out.
deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/claude-desktop-archive-keyring.asc] https://downloads.claude.ai/claude-desktop/apt/stable stable main
EOF
  chmod 644 "$keys/google-chrome.gpg" "$lists/google-chrome.sources" "$lists/claude-desktop.list"
}

# The legacy NVIDIA driver for GPUs the open kernel modules do not support
# (Maxwell, Pascal, Volta: GTX 750 to GTX 10xx, Titan V), kept on the image
# so the installer can switch such computers to it without internet. The
# installed system then keeps it current through normal updates.
modalias_ids() { # package -> the NVIDIA PCI device IDs it supports
  # (no "head" here: with pipefail, closing the pipe early counts as a failure)
  in_chroot apt-cache show --no-all-versions "$1" | sed -n 's/^Modaliases: //p' |
    grep -o 'd0000[0-9A-F]\{4\}' | cut -c6- | LC_ALL=C sort -u
}

add_nvidia_legacy_pool() {
  local b="$NVIDIA_LEGACY_BRANCH" pool="$CHROOT/var/lib/raiden-os/nvidia-legacy"
  log "Adding the legacy NVIDIA $b driver for older GPUs (installed offline where needed)"
  rm -rf "$pool"
  mkdir -p "$pool"
  apt_in_chroot clean
  apt_in_chroot install --download-only "nvidia-driver-$b" \
    "linux-modules-nvidia-$b-$KERNEL_FLAVOUR" "libnvidia-gl-$b:i386" >/dev/null
  mv "$CHROOT"/var/cache/apt/archives/*.deb "$pool/"
  echo "nvidia-driver-$b linux-modules-nvidia-$b-$KERNEL_FLAVOUR libnvidia-gl-$b:i386" > "$pool/packages"
  # the GPUs it is for: supported by it, but not by the preinstalled driver
  LC_ALL=C comm -23 <(modalias_ids "nvidia-driver-$b") <(modalias_ids "nvidia-driver-${NVIDIA_BRANCH}-open") \
    > "$pool/pci-ids"
  grep -qx 1B80 "$pool/pci-ids" || die "legacy NVIDIA GPU list looks wrong (no GTX 1080)"
  if grep -qx 2782 "$pool/pci-ids"; then die "legacy NVIDIA GPU list looks wrong (has RTX 4070 Ti)"; fi
  info "NVIDIA $b: $(ls "$pool"/*.deb | wc -l) packages, $(du -sh "$pool" | cut -f1), $(wc -l < "$pool/pci-ids") GPUs"
}

remove_stray_initrds() {
  local f v
  for f in "$CHROOT"/boot/initrd.img-*; do
    [ -e "$f" ] || continue
    v="${f##*/initrd.img-}"
    if [ ! -e "$CHROOT/boot/vmlinuz-$v" ]; then
      info "removing stray initrd for kernel $v"
      rm -f "$f"
      rm -f "$CHROOT/var/lib/initramfs-tools/$v"
    fi
  done
}

# --------------------------------------------------------------------------
stage_configure() {
  log "Configuring the system image"
  mount_chroot

  # Flathub (system-wide), from the pinned .flatpakrepo file
  cp "$SRC_DIR/vendor/flatpak/flathub.flatpakrepo" "$CHROOT/tmp/flathub.flatpakrepo"
  in_chroot flatpak remote-add --system --if-not-exists flathub /tmp/flathub.flatpakrepo
  rm -f "$CHROOT/tmp/flathub.flatpakrepo"

  # Live session user (casper)
  cat > "$CHROOT/etc/casper.conf" <<EOF
# Live session settings for casper
export USERNAME="$LIVE_USER"
export USERFULLNAME="$LIVE_USER_FULLNAME"
export HOST="$LIVE_HOSTNAME"
export BUILD_SYSTEM="Ubuntu"
export FLAVOUR="$DISTRO_NAME"
EOF

  # Boot splash: our Plymouth theme as the default, then rebuild the initramfs.
  # Package scripts that ran "update-initramfs" without a version may have
  # built an initrd for the *build host's* kernel (uname -r inside WSL); drop
  # every initrd that has no matching kernel image before rebuilding.
  in_chroot update-alternatives --set default.plymouth \
    "/usr/share/plymouth/themes/$DISTRO_ID/$DISTRO_ID.plymouth"
  remove_stray_initrds
  local k
  for k in $(in_chroot linux-version list); do
    in_chroot update-initramfs -u -k "$k"
  done
  remove_stray_initrds

  # Restore the stock Ubuntu answer we overrode for the build chroot
  echo "grub-efi-amd64-signed grub2/update_nvram boolean true" | in_chroot debconf-set-selections

  # No Ubuntu Pro advertising in apt output and the terminal login message
  in_chroot pro config set apt_news=false >/dev/null 2>&1 || true
  in_chroot systemctl mask motd-news.timer >/dev/null 2>&1 || true

  # Ubuntu's Snap-only shell extensions (the dpkg path-exclude shipped in
  # raiden-os-settings keeps them out on future updates; files that were
  # unpacked before it existed are removed here)
  rm -rf "$CHROOT"/usr/share/gnome-shell/extensions/snapd-prompting@canonical.com \
         "$CHROOT"/usr/share/gnome-shell/extensions/snapd-search-provider@canonical.com

  # Sanity checks on the finished image
  [ -L "$CHROOT/etc/alternatives/default.plymouth" ] || die "plymouth theme alternative missing"
  in_chroot glib-compile-schemas --strict --dry-run /usr/share/glib-2.0/schemas ||
    die "GSettings defaults do not compile"
  for f in /usr/share/gnome-shell/extensions/dash-to-panel@jderose9.github.com \
           /usr/share/gnome-shell/extensions/arcmenu@arcmenu.com \
           /usr/share/plymouth/themes/$DISTRO_ID/$DISTRO_ID.plymouth \
           /boot/grub/themes/$DISTRO_ID/theme.txt /etc/calamares/settings.conf; do
    [ -e "$CHROOT$f" ] || die "missing in image: $f"
  done

  # Clean up everything that must not end up on the ISO
  log "Cleaning the image"
  apt_in_chroot autoremove --purge
  apt_in_chroot clean
  rm -rf "$CHROOT"/var/lib/apt/lists/* "$CHROOT"/var/cache/apt/*.bin
  rm -rf "$CHROOT"/tmp/* "$CHROOT"/var/tmp/* "$CHROOT"/root/.cache "$CHROOT"/root/.bash_history
  find "$CHROOT/var/log" -type f -exec truncate -s 0 {} +
  rm -f "$CHROOT"/var/lib/dbus/machine-id
  : > "$CHROOT/etc/machine-id"
  rm -f "$CHROOT/usr/sbin/policy-rc.d"
  rm -f "$CHROOT/etc/resolv.conf"
  ln -s ../run/systemd/resolve/stub-resolv.conf "$CHROOT/etc/resolv.conf"
}

# --------------------------------------------------------------------------
stage_squashfs() {
  log "Creating the live filesystem (squashfs, $SQUASHFS_COMP)"
  umount_chroot
  mkdir -p "$ISO_ROOT/casper"
  in_chroot_query() { chroot "$CHROOT" "$@"; }
  in_chroot_query dpkg-query -W --showformat='${Package}\t${Version}\n' > "$ISO_ROOT/casper/filesystem.manifest"
  du -sx --block-size=1 "$CHROOT" | cut -f1 > "$ISO_ROOT/casper/filesystem.size"
  rm -f "$ISO_ROOT/casper/filesystem.squashfs"
  # shellcheck disable=SC2086
  mksquashfs "$CHROOT" "$ISO_ROOT/casper/filesystem.squashfs" \
    -noappend -comp "$SQUASHFS_COMP" $SQUASHFS_COMP_OPTS -b 1M -processors "$(nproc)" \
    -wildcards -e 'proc/*' 'sys/*' 'dev/*' 'run/*' 'tmp/*' 'boot/efi/*' \
    -no-progress
  info "squashfs: $(du -h "$ISO_ROOT/casper/filesystem.squashfs" | cut -f1)"
}

# --------------------------------------------------------------------------
stage_iso() {
  log "Assembling the bootable ISO (BIOS + UEFI with Secure Boot)"
  bash "$SRC_DIR/scripts/make-iso.sh"
}

# --------------------------------------------------------------------------
run_stage() {
  CURRENT_STAGE="$1"
  "stage_$1"
  mark_done "$1"
  CURRENT_STAGE=""
}

main() {
  local mode="all" target=""
  case "${1:-}" in
    --clean) umount_chroot; rm -rf "$WORK"; log "removed $WORK"; exit 0 ;;
    --redo)  target="${2:?stage name required}"; mode="redo" ;;
    --only)  target="${2:?stage name required}"; mode="only" ;;
    "")      ;;
    *)       die "unknown argument: $1" ;;
  esac
  mkdir -p "$WORK"
  export SRC_DIR WORK CHROOT ISO_ROOT DEBS OUT_DIR

  if [ "$mode" = "only" ]; then run_stage "$target"; exit 0; fi
  if [ "$mode" = "redo" ]; then
    local hit=0 s
    for s in "${STAGES[@]}"; do
      [ "$s" = "$target" ] && hit=1
      [ "$hit" = 1 ] && rm -f "$WORK/stamps/$s"
    done
    [ "$hit" = 1 ] || die "unknown stage $target"
  fi
  local s
  for s in "${STAGES[@]}"; do
    if stage_done "$s"; then info "stage $s already done"; continue; fi
    run_stage "$s"
  done
  log "Build finished: $OUT_DIR/$ISO_FILENAME"
}

main "$@"
