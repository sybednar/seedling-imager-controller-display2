#!/bin/bash
# install_health_monitor.sh  —  one-time setup on each imager (Oct 2026)
#
# Run from the project folder with:
#     sudo bash diagnostics/install_health_monitor.sh
#
# Does three things, and is safe to run more than once:
#   1. Installs the USB crash-diagnostic logger (seedling-health-usb.service).
#   2. Removes the duplicate app launcher from labwc's autostart, leaving XDG
#      autostart (~/.config/autostart/seedling-imager.desktop) as the only one.
#   3. Makes sure the old systemd --user unit is disabled.
# The existing per-minute cron health.log on the NVMe is left as it is.

set -u
if [[ $EUID -ne 0 ]]; then echo "Please run with sudo: sudo bash $0"; exit 1; fi

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_USER="${SUDO_USER:-sybednar}"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
APP_UID="$(id -u "$APP_USER")"

echo "== 1. USB crash-diagnostic logger"
install -m 755 "$HERE/seedling-health-usb.sh" /usr/local/bin/seedling-health-usb.sh
install -m 644 "$HERE/seedling-health-usb.service" /etc/systemd/system/seedling-health-usb.service
systemctl daemon-reload
systemctl enable seedling-health-usb.service >/dev/null 2>&1
systemctl restart seedling-health-usb.service
echo "   installed and started"

echo "== 2. Duplicate launcher in labwc autostart"
LABWC="$APP_HOME/.config/labwc/autostart"
if [[ -f $LABWC ]] && grep -q "seedling-imager.service" "$LABWC"; then
    cp -p "$LABWC" "$LABWC.bak-$(date +%Y%m%d-%H%M%S)"
    sed -i '/systemctl --user start seedling-imager.service/d' "$LABWC"
    echo "   removed 'systemctl --user start seedling-imager.service' (backup saved next to it)"
else
    echo "   nothing to remove"
fi

echo "== 3. Old systemd --user unit"
sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$APP_UID" \
    systemctl --user disable seedling-imager.service >/dev/null 2>&1 || true
echo "   seedling-imager.service (user): $(sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$APP_UID" systemctl --user is-enabled seedling-imager.service 2>/dev/null)"

echo
echo "== Launchers now active"
ls "$APP_HOME/.config/autostart/" 2>/dev/null | sed 's/^/   XDG: /'
grep -v '^\s*$' "$LABWC" 2>/dev/null | sed 's/^/   labwc: /'

echo
echo "== Logger status (give it ~70 s for the first line)"
sleep 8
cat /run/seedling-health/status 2>/dev/null || echo "   (no status yet)"
echo
echo "Check later with:  cat /run/seedling-health/status"
echo "        and:       tail -3 /media/*/*/seedling_health_*/health.log /mnt/healthusb/seedling_health_*/health.log 2>/dev/null"
