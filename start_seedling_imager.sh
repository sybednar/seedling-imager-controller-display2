#!/usr/bin/env bash
# start_seedling_imager.sh
#
# Launch wrapper for the Seedling Imager Controller. This is the ONE script
# that both autostart methods call (XDG autostart — recommended — and the
# systemd --user service) — so the environment variables below are
# guaranteed to be set correctly no matter which trigger mechanism starts it.
#
# It can also be run by hand from a terminal for a manual test:
#     ./start_seedling_imager.sh
#
set -euo pipefail

PROJECT_DIR="/home/sybednar/Seedling_Imager/seedling_imager_controller"
LOG_FILE="$PROJECT_DIR/autostart.log"

# Ensure relative paths (camera_settings.json, motion_cal.json, etc.)
# resolve the same way here as they do during manual terminal testing
# (cd + python3 main.py). Without this, the working directory under XDG
# autostart defaults to $HOME, not the project folder -- see the matching
# Sept 2026 fix in camera_config.py/camera_picamera2.py/
# camera_arducam_usb3.py/camera.py for the full story.
cd "$PROJECT_DIR" || { echo "FATAL: could not cd to $PROJECT_DIR" >&2; exit 1; }

# Send all stdout/stderr to a log file so autostart failures are debuggable
# (view with: tail -f "$LOG_FILE")
exec >> "$LOG_FILE" 2>&1
echo "=== $(date) Seedling Imager launch begin ==="

{ echo "--- NVMe/PCIe state at launch ---"; dmesg | tail -30; } >> "$LOG_FILE" 2>&1

# Let the desktop session finish settling before we grab the display
sleep 10

export XDG_RUNTIME_DIR="/run/user/$(id -u)"
# systemd --user services don't inherit WAYLAND_DISPLAY the way an
# interactive terminal does. Only fall back to a default here if it isn't
# already set, so manual/interactive runs (which already have the correct
# value) are left untouched.
: "${WAYLAND_DISPLAY:=wayland-0}"
export WAYLAND_DISPLAY

# systemd --user services also don't reliably inherit XAUTHORITY/WLR_XWAYLAND
# the way an interactive session does, on at least some Pi 5/labwc images —
# this breaks the xcb (X11/XWayland) platform plugin's ability to
# authenticate even when DISPLAY is set correctly. Set explicit defaults
# here (harmless if already set correctly). This is the confirmed root
# cause of systemd-autostart failures documented in the README; the XDG
# autostart method sidesteps the issue entirely by not depending on
# systemd's environment import at all, and is the recommended method.
: "${XAUTHORITY:=/home/sybednar/.Xauthority}"
export XAUTHORITY
: "${WLR_XWAYLAND:=/usr/bin/xwayland-xauth}"
export WLR_XWAYLAND

# Raspberry Pi OS Bookworm/Trixie use Wayland (labwc) by default on Pi 5.
# If the touchscreen shows a black screen or the app fails to open a window,
# comment the Wayland line and uncomment the xcb (X11) line instead, then
# re-run this script by hand to confirm which one works before re-enabling
# autostart. Note: in practice this has NOT been the cause of autostart
# failures seen so far (those were the XAUTHORITY/WLR_XWAYLAND gap above) —
# only change this if you have a specific, confirmed reason to.
#export QT_QPA_PLATFORM=wayland
export QT_QPA_PLATFORM=xcb

source "$PROJECT_DIR/venv/bin/activate"

python3 "$PROJECT_DIR/main.py"

echo "=== $(date) Seedling Imager launch end ==="
