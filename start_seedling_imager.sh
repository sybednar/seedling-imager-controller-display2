#!/usr/bin/env bash
# start_seedling_imager.sh
#
# Launch wrapper for the Seedling Imager Controller. This is the ONE script
# that both the systemd service and the XDG autostart fallback call — so
# the environment variables below (XDG_RUNTIME_DIR, QT_QPA_PLATFORM) are
# guaranteed to be set correctly no matter which trigger mechanism starts it.
#
# It can also be run by hand from a terminal for a manual test:
#     ./start_seedling_imager.sh
#
set -euo pipefail

PROJECT_DIR="/home/sybednar/Seedling_Imager/seedling_imager_controller"
LOG_FILE="$PROJECT_DIR/autostart.log"

# Send all stdout/stderr to a log file so autostart failures are debuggable
# (view with: tail -f "$LOG_FILE")
exec >> "$LOG_FILE" 2>&1
echo "=== $(date) Seedling Imager launch begin ==="

# Let the desktop session finish settling before we grab the display
sleep 3

export XDG_RUNTIME_DIR="/run/user/$(id -u)"

# Raspberry Pi OS Bookworm/Trixie use Wayland (labwc) by default on Pi 5.
# If the touchscreen shows a black screen or the app fails to open a window,
# comment the Wayland line and uncomment the xcb (X11) line instead, then
# re-run this script by hand to confirm which one works before re-enabling
# autostart.
export QT_QPA_PLATFORM=wayland
# export QT_QPA_PLATFORM=xcb

source "$PROJECT_DIR/venv/bin/activate"

python3 "$PROJECT_DIR/main.py"

echo "=== $(date) Seedling Imager launch end ==="
