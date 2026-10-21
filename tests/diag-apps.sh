# Checks of the preinstalled apps, drivers and game tuning on an installed
# system; run as root in the test VM:  vmexec.py "$(cat tests/diag-apps.sh)"
U=$(id -nu 1000)
as_user() { runuser -u "$U" -- env XDG_RUNTIME_DIR=/run/user/1000 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "$@"; }

echo "== apps (package version status)"
for p in google-chrome-stable claude-desktop steam-installer steam-libs-i386:i386 heroic lutris \
         mangohud goverlay gamescope gamemode libgamemode0:i386 xournalpp foliate \
         fonts-crosextra-carlito libreoffice-draw raiden-apps raiden-gaming firefox; do
  dpkg-query -W -f='${binary:Package} ${Version} ${db:Status-Status}\n' "$p" 2>/dev/null | head -n1 ||
    echo "$p not-installed"
done
echo "== apps in /opt"; /usr/libexec/raiden-os/apps-update status; ls -l /opt
echo "== launchers"
for d in google-chrome com.anthropic.Claude steam heroic net.lutris.Lutris com.vysp3r.ProtonPlus \
         antigravity antigravity-ide org.raidenos.Outlook org.raidenos.Microsoft365 \
         com.github.xournalpp.xournalpp com.github.johnfactotum.Foliate io.github.benjamimgois.goverlay; do
  f=/usr/share/applications/$d.desktop
  [ -f "$f" ] && echo "ok  $d" || echo "MISSING $d"
done
echo "== default browser"; as_user xdg-settings get default-web-browser
echo "== https handler"; as_user gio mime x-scheme-handler/https | head -n1
echo "== NVIDIA packages left (none expected without an NVIDIA card)"
dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' 'nvidia*' 'libnvidia*' 'linux-modules-nvidia*' 2>/dev/null |
  awk '$2 == "installed"' | head -20
echo "== raiden-os state"; ls -la /var/lib/raiden-os/
echo "== 32-bit"; dpkg --print-foreign-architectures
echo "   i386 packages: $(dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' | grep -c ':i386 installed')"
echo "   32-bit Vulkan drivers: $(ls /usr/share/vulkan/icd.d/ | tr '\n' ' ')"
echo "== game tuning"
sysctl kernel.split_lock_mitigate vm.max_map_count 2>&1
lsmod | grep -w ntsync || echo "ntsync not loaded"; ls -l /dev/ntsync 2>&1
getent group gamemode kvm; id "$U"
as_user systemctl --user show-environment | grep -E 'SHADER|MESA'
echo "== GameMode self-test"; as_user timeout 60 gamemoded -t 2>&1 | tail -n 12
echo "== VM support (Claude Cowork)"; ls -l /dev/kvm /dev/vhost-vsock 2>&1
echo "== updater"; systemctl list-timers raiden-apps-update.timer --all --no-pager | head -n 3
systemctl is-enabled raiden-apps-update.timer
echo "== apt sources"; ls /etc/apt/sources.list.d/; cat /etc/apt/sources.list.d/google-chrome.sources
apt-cache policy google-chrome-stable claude-desktop | grep -E '^[a-z]|Installed|Candidate'
echo "== unattended-upgrades origins"; apt-config dump | grep -i 'Origins-Pattern::'
echo "== installer log"; grep -E '^\[postinstall\]' /var/log/installer/raiden-postinstall.log | head -20
