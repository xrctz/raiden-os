# Shared helpers for the Raiden OS build scripts (sourced, not executed).

log()  { printf '\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '\033[1;33mWARNING:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Read a package list: one package per line, '#' comments and blank lines ignored.
read_list() {
  sed -e 's/#.*//' -e 's/[[:space:]]\+$//' -e '/^[[:space:]]*$/d' "$1" | tr '\n' ' '
}

chroot_mounted() { mountpoint -q "$CHROOT/proc"; }

mount_chroot() {
  chroot_mounted && return 0
  mount --bind /dev "$CHROOT/dev"
  mount -t devpts devpts "$CHROOT/dev/pts" -o gid=5,mode=620,ptmxmode=666
  mount -t proc proc "$CHROOT/proc"
  mount -t sysfs sysfs "$CHROOT/sys"
  mount -t tmpfs tmpfs "$CHROOT/run" -o mode=755
  mkdir -p "$CHROOT/run/lock"
  # Once systemd-resolved is installed, /etc/resolv.conf is a symlink into /run;
  # give it the host's DNS settings so downloads keep working inside the chroot.
  mkdir -p "$CHROOT/run/systemd/resolve"
  cp -L /etc/resolv.conf "$CHROOT/run/systemd/resolve/stub-resolv.conf"
  cp -L /etc/resolv.conf "$CHROOT/run/systemd/resolve/resolv.conf"
}

umount_chroot() {
  local m
  for m in run sys proc dev/pts dev; do
    if mountpoint -q "$CHROOT/$m"; then
      umount "$CHROOT/$m" 2>/dev/null || umount -l "$CHROOT/$m"
    fi
  done
}

# Run a command inside the chroot with a clean, non-interactive environment.
in_chroot() {
  chroot "$CHROOT" /usr/bin/env -i \
    HOME=/root TERM="${TERM:-xterm}" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true \
    "$@"
}

APT_OPTS=(-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold -o APT::Acquire::Retries=5)

apt_in_chroot() { in_chroot apt-get "${APT_OPTS[@]}" "$@"; }

# Stage bookkeeping so a failed build can resume where it stopped.
stage_done() { [ -f "$WORK/stamps/$1" ]; }
mark_done()  { mkdir -p "$WORK/stamps"; touch "$WORK/stamps/$1"; }
