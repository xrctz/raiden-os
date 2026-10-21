#!/bin/bash
# Boot Raiden OS in a QEMU/KVM test VM (run inside the build WSL distro).
#
#   qemu-run.sh start uefi|bios [options]   start the VM in the background
#   qemu-run.sh stop                        power it off
#
# Options:
#   --iso FILE         ISO to attach (default: newest out/*.iso)
#   --usb              attach the ISO as a USB stick (default: DVD drive)
#   --no-iso           boot without installation media
#   --fresh-disk       create a new empty 40 GB NVMe disk (and reset UEFI vars)
#   --fresh-vars       reset the UEFI variables only (no boot entries, like
#                      plugging a drive into a different PC)
#   --no-disk          no hard disk
#   --ext FILE         also attach FILE (raw image) as an external USB drive
#   --smbios SPEC      extra QEMU -smbios entry, e.g. type=2,product=FA617NT
#                      to pose as a given laptop board
#   --mem MB / --cpus N / --res WxH
#
# UEFI mode uses OVMF with Secure Boot ENFORCED and Microsoft's keys enrolled,
# like a typical Windows 11 PC. Drive the VM with tests/qmp.py and the socket
# /var/tmp/raiden-test/qmp.sock.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
T=/var/tmp/raiden-test
mkdir -p "$T"

stop_vm() {
  local pid
  # QEMU deletes its pidfile on exit, so keep the pid in a variable
  if [ -f "$T/qemu.pid" ] && pid="$(cat "$T/qemu.pid")" && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    for _ in $(seq 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.2; done
  fi
  rm -f "$T/qemu.pid" "$T/qmp.sock"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  stop) stop_vm; echo "VM stopped"; exit 0 ;;
  start) ;;
  *) sed -n '2,22p' "$0"; exit 2 ;;
esac

fw="${1:?uefi or bios}"; shift
ISO=""; USB=0; NOISO=0; FRESH=0; FRESHVARS=0; NODISK=0; EXT=""; SMBIOS=(); MEM=8192; CPUS=8; RES=1920x1080
while [ $# -gt 0 ]; do
  case "$1" in
    --iso) ISO="$2"; shift ;;
    --usb) USB=1 ;;
    --no-iso) NOISO=1 ;;
    --fresh-disk) FRESH=1 ;;
    --fresh-vars) FRESHVARS=1 ;;
    --no-disk) NODISK=1 ;;
    --ext) EXT="$2"; shift ;;
    --smbios) SMBIOS+=(-smbios "$2"); shift ;;
    --mem) MEM="$2"; shift ;;
    --cpus) CPUS="$2"; shift ;;
    --res) RES="$2"; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
[ -n "$ISO" ] || ISO="$(ls -t "$SRC_DIR"/out/*.iso /var/tmp/raiden-build/*.iso 2>/dev/null | head -n1 || true)"
DISK="$T/disk-$fw.qcow2"

stop_vm
# The test agent (tests/vm-agent.py) is offered to the guest through fw_cfg;
# start it inside the VM with:
#   sudo setsid python3 /sys/firmware/qemu_fw_cfg/by_name/opt/raiden/agent/raw &
args=(-name raiden-test -cpu host -smp "$CPUS" -m "$MEM"
      -device "virtio-vga,xres=${RES%x*},yres=${RES#*x}"
      -device qemu-xhci -device usb-tablet -device usb-kbd
      -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:2222-:2222" -device virtio-net-pci,netdev=n0
      -fw_cfg "name=opt/raiden/agent,file=$SRC_DIR/tests/vm-agent.py"
      -display none -qmp "unix:$T/qmp.sock,server,nowait"
      -serial "file:$T/serial-$fw.log" -daemonize -pidfile "$T/qemu.pid")

if [ "$fw" = uefi ]; then
  CODE=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd
  VARS_SRC=/usr/share/OVMF/OVMF_VARS_4M.ms.fd
  [ -f "$T/vars-uefi.fd" ] && [ "$FRESH" = 0 ] && [ "$FRESHVARS" = 0 ] ||
    cp "$VARS_SRC" "$T/vars-uefi.fd"
  args+=(-machine q35,smm=on,accel=kvm
         -global driver=cfi.pflash01,property=secure,value=on
         -drive "if=pflash,format=raw,unit=0,file=$CODE,readonly=on"
         -drive "if=pflash,format=raw,unit=1,file=$T/vars-uefi.fd")
else
  args+=(-machine q35,accel=kvm)
fi

if [ "$NODISK" = 0 ]; then
  if [ "$FRESH" = 1 ] || [ ! -f "$DISK" ]; then
    rm -f "$DISK"; qemu-img create -q -f qcow2 "$DISK" 40G
  fi
  args+=(-drive "file=$DISK,if=none,id=hd0,format=qcow2")
  if [ "$fw" = uefi ]; then
    args+=(-device "nvme,drive=hd0,serial=raidennvme,bootindex=2")
  else
    # SeaBIOS cannot boot from NVMe (neither can most BIOS-only PCs): SATA
    args+=(-device "ide-hd,drive=hd0,bus=ide.0,serial=raidensata,bootindex=2")
  fi
fi
if [ -n "$EXT" ]; then
  [ -f "$EXT" ] || { echo "external disk image $EXT not found"; exit 1; }
  args+=(-drive "file=$EXT,if=none,id=ext0,format=raw"
         -device "usb-storage,drive=ext0,serial=raidenext,bootindex=3")
fi
if [ "$NOISO" = 0 ]; then
  [ -f "$ISO" ] || { echo "ISO not found"; exit 1; }
  if [ "$USB" = 1 ]; then
    args+=(-drive "file=$ISO,if=none,id=usbstick,format=raw,readonly=on"
           -device "usb-storage,drive=usbstick,bootindex=1")
  else
    args+=(-drive "file=$ISO,if=none,id=cd0,format=raw,readonly=on,media=cdrom"
           -device "ide-cd,drive=cd0,bootindex=1")
  fi
fi

args+=("${SMBIOS[@]}")
qemu-system-x86_64 "${args[@]}"
[ "$NOISO" = 0 ] || ISO=""
echo "VM started ($fw, iso=${ISO:-none}, usb=$USB). QMP: $T/qmp.sock"
