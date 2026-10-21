# Health check of an installed Raiden OS system (run as root via tests/vmexec.py)
U=$(getent passwd 1000 | cut -d: -f1)
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
asuser() { runuser -u "$U" -- env XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS "$@"; }
echo "== failed units";    systemctl --failed --no-legend; echo "(end)"
echo "== live leftovers";  dpkg -l casper calamares raiden-live 2>/dev/null | grep -E '^ii' || echo none
echo "== raiden pkgs";     dpkg -l 'raiden-*' | awk '/^ii/{print $2, $3}'
echo "== blocked pkgs";    dpkg -l snapd apport whoopsie ubuntu-report gnome-initial-setup dracut 2>/dev/null | grep -E '^ii' || echo none
echo "== nvidia pkgs";     dpkg -l | grep -cE '^ii +(nvidia|libnvidia)'
echo "== kernel";          uname -r; ls /boot/vmlinuz-* /boot/initrd.img-*
echo "== swap";            swapon --show
echo "== session";         loginctl show-session $(loginctl list-sessions --no-legend | awk -v u="$U" '$3==u{print $1; exit}') -p Type -p Desktop 2>/dev/null
echo "== extensions";      asuser gnome-extensions list --enabled
echo "== shell errors";    journalctl -b --no-pager -o cat | grep -E 'JS ERROR|Extension .* had error' | sort | uniq -c | head
echo "== apt update";      apt-get update -qq 2>&1 | tail -3; apt list --upgradable 2>/dev/null | grep -vc Listing
echo "== chrome origin";   apt-cache policy google-chrome-stable | sed -n 1,6p
echo "== flatpak";         flatpak remotes --system
echo "== release prompt";  python3 -c "import configparser,glob;c=configparser.ConfigParser();[c.read(f) for f in ['/etc/update-manager/release-upgrades']+sorted(glob.glob('/etc/update-manager/release-upgrades.d/*.cfg'))];print(c['DEFAULT']['Prompt'])"
echo "== unattended";      systemctl is-enabled unattended-upgrades apt-daily-upgrade.timer
echo "== theme";           asuser gsettings get org.gnome.desktop.interface gtk-theme; asuser gsettings get org.gnome.desktop.interface icon-theme; asuser gsettings get org.gnome.desktop.interface color-scheme
echo "== layout";          asuser raiden-appearance --current-layout
echo "== power";           systemctl is-active power-profiles-daemon; asuser powerprofilesctl get 2>/dev/null
echo "== fastfetch";       asuser fastfetch --pipe --logo none 2>&1 | head -6
echo "== installer logs";  ls /var/log/installer 2>&1
echo "== grub";            ls /etc/default/grub.d/; grep -c menuentry /boot/grub/grub.cfg
echo "== efi";             efibootmgr | grep -iE 'raiden|ubuntu'
