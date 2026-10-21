#!/bin/bash
# Assembles the bootable Raiden OS ISO from the finished chroot and the
# squashfs created by build.sh. The result boots from DVD or USB stick on:
#   - UEFI firmware, with or without Secure Boot (Microsoft-signed shim ->
#     Canonical-signed GRUB -> Canonical-signed kernel)
#   - legacy BIOS (GRUB El Torito image + hybrid MBR for USB)
# Layout and xorriso options follow the official Ubuntu 26.04 desktop ISOs.
set -Eeuo pipefail

SRC_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
. "$SRC_DIR/build.conf"
. "$SRC_DIR/scripts/lib.sh"
: "${WORK:?}" "${CHROOT:?}" "${ISO_ROOT:?}" "${OUT_DIR:?}"

[ -f "$ISO_ROOT/casper/filesystem.squashfs" ] || die "squashfs missing; run the squashfs stage first"
inchroot() { chroot "$CHROOT" "$@"; }

# --------------------------------------------------------- kernel + initrd
kver="$(inchroot linux-version list | sort -V | tail -n1)"
[ -n "$kver" ] || die "no kernel found in the chroot"
install -m644 "$CHROOT/boot/vmlinuz-$kver" "$ISO_ROOT/casper/vmlinuz"
install -m644 "$CHROOT/boot/initrd.img-$kver" "$ISO_ROOT/casper/initrd"
inchroot lsinitramfs "/boot/initrd.img-$kver" | grep -q '^scripts/casper$' ||
  die "the live initrd does not contain casper"
info "kernel $kver"

# --------------------------------------------------------- disc metadata
BUILD_DATE="$(date -u +%Y%m%d)"
mkdir -p "$ISO_ROOT/.disk"
echo "$DISTRO_NAME $DISTRO_VERSION \"$DISTRO_NAME\" - Release $ARCH ($BUILD_DATE)" > "$ISO_ROOT/.disk/info"
echo "full_cd/single" > "$ISO_ROOT/.disk/cd_type"
: > "$ISO_ROOT/.disk/base_installable"

# ------------------------------------------------------------- GRUB files
G="$ISO_ROOT/boot/grub"
rm -rf "$G"
mkdir -p "$G/fonts" "$G/themes" "$G/i386-pc" "$G/x86_64-efi"
cp "$CHROOT/usr/share/grub/unicode.pf2" "$G/fonts/"
cp -a "$CHROOT/boot/grub/themes/$DISTRO_ID" "$G/themes/"
cp "$CHROOT"/usr/lib/grub/i386-pc/*.mod "$CHROOT"/usr/lib/grub/i386-pc/*.lst "$G/i386-pc/"
cp "$CHROOT"/usr/lib/grub/x86_64-efi/*.mod "$CHROOT"/usr/lib/grub/x86_64-efi/*.lst "$G/x86_64-efi/"
MEMTEST=""
if [ -f "$CHROOT/boot/mt86+x64" ]; then          # memtest86+ 7.x/8.x
  install -m644 "$CHROOT/boot/mt86+x64" "$ISO_ROOT/boot/mt86+x64"
  MEMTEST=1
fi

# Extra kernel parameters for the live session. amdgpu.dcdebugmask=0x10 turns
# off Panel Self Refresh: on Radeon RX 7600S/7700S (Navi 33) laptops such as
# the ASUS TUF A16 it corrupts the top of the built-in screen and stutters.
# It only affects AMD laptop panels and costs nothing in a live session; the
# installer adds it to installed systems only on that hardware.
LIVE_ARGS="amdgpu.dcdebugmask=0x10"

FONTS=""
for f in "$G/themes/$DISTRO_ID"/*.pf2; do
  FONTS+="        loadfont /boot/grub/themes/$DISTRO_ID/$(basename "$f")"$'\n'
done

cat > "$G/grub.cfg" <<EOF
# $DISTRO_NAME $DISTRO_VERSION live/installer boot menu
set default=0
set timeout=10
set timeout_style=menu
# Colours for a plain text menu (only if no font can be loaded at all)
set menu_color_normal=light-gray/black
set menu_color_highlight=white/blue

# "unicode" by name: the Secure Boot signed GRUB loads it from its built-in
# memdisk. Font *files* are refused under Secure Boot (lockdown, a
# CVE-2022-2601 hardening), so there the theme falls back to that font.
if loadfont unicode ; then
    set gfxmode=1920x1080,1280x720,auto
    insmod all_video
    insmod gfxterm
    insmod png
    terminal_output gfxterm
    if [ "\$lockdown" != "y" ] ; then
${FONTS}    fi
    set theme=/boot/grub/themes/$DISTRO_ID/theme.txt
    export theme
fi

menuentry "Try or Install $DISTRO_NAME" --class raiden {
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper $LIVE_ARGS quiet splash ---
	initrd	/casper/initrd
}
menuentry "Try or Install $DISTRO_NAME (Safe Graphics)" --class raiden {
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper nomodeset quiet splash ---
	initrd	/casper/initrd
}
if [ "\$grub_platform" = "efi" ]; then
menuentry "Boot from next volume" --class next {
	exit 1
}
menuentry "UEFI Firmware Settings" --class settings {
	fwsetup
}
EOF
if [ -n "$MEMTEST" ]; then
  cat >> "$G/grub.cfg" <<'EOF'
else
menuentry "Test Memory" --class memtest {
	linux16 /boot/mt86+x64
}
EOF
fi
echo "fi" >> "$G/grub.cfg"

cat > "$G/loopback.cfg" <<EOF
menuentry "Try or Install $DISTRO_NAME" {
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper iso-scan/filename=\${iso_path} $LIVE_ARGS quiet splash ---
	initrd	/casper/initrd
}
menuentry "Try or Install $DISTRO_NAME (Safe Graphics)" {
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper iso-scan/filename=\${iso_path} nomodeset quiet splash ---
	initrd	/casper/initrd
}
EOF

# ------------------------------------------------- BIOS El Torito boot image
inchroot grub-mkimage -O i386-pc-eltorito -d /usr/lib/grub/i386-pc -p /boot/grub \
  -o /tmp/eltorito.img biosdisk iso9660 part_msdos part_gpt normal configfile search
mv "$CHROOT/tmp/eltorito.img" "$G/i386-pc/eltorito.img"
cp "$CHROOT/usr/lib/grub/i386-pc/boot_hybrid.img" "$WORK/boot_hybrid.img"

# --------------------------------------------- UEFI (Secure Boot) boot files
SHIM="$(inchroot readlink -f /usr/lib/shim/shimx64.efi.signed)"
mkdir -p "$ISO_ROOT/EFI/boot"
install -m644 "$CHROOT$SHIM" "$ISO_ROOT/EFI/boot/bootx64.efi"
install -m644 "$CHROOT/usr/lib/shim/mmx64.efi" "$ISO_ROOT/EFI/boot/mmx64.efi"
install -m644 "$CHROOT/usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed" "$ISO_ROOT/EFI/boot/grubx64.efi"

# FAT image with the same three files: the ESP of the ISO (appended partition)
EFIIMG="$WORK/efi.img"
rm -f "$EFIIMG"
mkfs.vfat -C -n "ESP" "$EFIIMG" 10240 >/dev/null
mmd -i "$EFIIMG" ::/EFI ::/EFI/boot
mcopy -i "$EFIIMG" "$ISO_ROOT/EFI/boot/bootx64.efi" "$ISO_ROOT/EFI/boot/mmx64.efi" \
  "$ISO_ROOT/EFI/boot/grubx64.efi" ::/EFI/boot/

# ------------------------------------------------------------- checksums
(cd "$ISO_ROOT" && find . -type f ! -name md5sum.txt ! -name boot.catalog ! -path './boot/grub/i386-pc/eltorito.img' \
   -print0 | sort -z | xargs -0 md5sum > md5sum.txt)

# ------------------------------------------------------------------ xorriso
mkdir -p "$OUT_DIR"
ISO="$WORK/$ISO_FILENAME"
rm -f "$ISO"
xorriso -as mkisofs \
  -V "$ISO_VOLUME_ID" \
  -o "$ISO" \
  -r -J -joliet-long -iso-level 3 \
  --modification-date="$(date -u +%Y%m%d%H%M%S00)" \
  --grub2-mbr "$WORK/boot_hybrid.img" \
  --protective-msdos-label \
  -partition_cyl_align off \
  -partition_offset 16 \
  --mbr-force-bootable \
  -append_partition 2 28732ac11ff8d211ba4b00a0c93ec93b "$EFIIMG" \
  -appended_part_as_gpt \
  -iso_mbr_part_type a2a0d0ebe5b9334487c068b6b72699c7 \
  -c /boot.catalog \
  -b /boot/grub/i386-pc/eltorito.img \
     -no-emul-boot -boot-load-size 4 -boot-info-table --grub2-boot-info \
  -eltorito-alt-boot \
  -e '--interval:appended_partition_2:all::' \
     -no-emul-boot \
  "$ISO_ROOT"

cp "$ISO" "$OUT_DIR/$ISO_FILENAME"
(cd "$OUT_DIR" && sha256sum "$ISO_FILENAME" > "$ISO_FILENAME.sha256")
info "ISO: $OUT_DIR/$ISO_FILENAME ($(du -h "$OUT_DIR/$ISO_FILENAME" | cut -f1))"
