# Diagnostics for the live session (run through tests/vmexec.py as root).
U=$(getent passwd 1000 | cut -d: -f1)
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
asuser() { runuser -u "$U" -- env XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS "$@"; }
echo "== secure boot";      mokutil --sb-state 2>&1
echo "== live user";        echo "$U"; grep -E 'Automatic' /etc/gdm3/custom.conf
echo "== session";          loginctl list-sessions --no-legend; asuser printenv XDG_SESSION_TYPE 2>/dev/null
echo "== live setup unit";  systemctl is-active raiden-live-setup.service; systemctl status raiden-live-setup.service --no-pager 2>&1 | tail -3
echo "== autostart files";  ls /etc/xdg/autostart/ | grep -i raiden
echo "== prompt/theme-sync procs"; pgrep -af 'live-prompt|theme-sync|raiden-welcome' || echo none
echo "== journal (raiden/prompt/python errors)"
journalctl -b --no-pager -o cat 2>/dev/null | grep -iE 'live-prompt|theme-sync|raiden-welcome|raiden_|Traceback|SyntaxError|ModuleNotFound|gi.repository' | tail -25
echo "== extensions";       asuser gnome-extensions list --enabled 2>&1
echo "== extension errors"; journalctl -b --no-pager -o cat | grep -iE 'Extension .* (had|error)|JS ERROR|JS WARNING' | sort | uniq -c | sort -rn | head -15
echo "== zram/swap";        swapon --show; cat /proc/sys/vm/swappiness
echo "== udev nvidia mask"; ls -la /run/udev/rules.d/ 2>&1
echo "== plymouth";         readlink -f /usr/share/plymouth/themes/default.plymouth
echo "== gpu";              lspci -k | grep -A3 -E 'VGA|Display'
echo "== renderer";         asuser bash -c 'cat /proc/$(pgrep -u '"$U"' -x gnome-shell)/maps 2>/dev/null | grep -oE "(swrast|llvmpipe|virtio|zink|iris|radeonsi)[^ ]*" | sort -u | head'
echo "== failed units";     systemctl --failed --no-legend
