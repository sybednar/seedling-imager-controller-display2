#!/usr/bin/env bash
set -euo pipefail

# Log file location (can be anywhere you prefer)
LOGDIR="/home/sybednar/Seedling_Imager/seedling_imager_controller"
mkdir -p "$LOGDIR"
exec >> "$LOGDIR/autostart.log" 2>&1

echo "=== $(date) Seedling Imager autostart begin ==="
echo "User: $(id -un) UID: $(id -u)"

# For GUI apps, runtime dir matters
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

# Wait briefly for a usable user session bus (more reliable than DISPLAY checks alone)
for i in {1..60}; do
  if command -v busctl >/dev/null 2>&1 && busctl --user status >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Try to infer display variables if systemd didn't pass them
if [[ -z "${WAYLAND_DISPLAY:-}" && -S "$XDG_RUNTIME_DIR/wayland-0" ]]; then
  export WAYLAND_DISPLAY="wayland-0"
fi
if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
  export DISPLAY=":0"
fi

# Choose Qt platform plugin
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=wayland
elif [[ -n "${DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
fi

echo "DISPLAY=${DISPLAY:-}"
echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
echo "QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-<unset>}"

# Activate venv located in /home/sybednar/Seedling_Imager (your setup)
source /home/sybednar/Seedling_Imager/bin/activate

# Run from repo directory where main.py lives (your setup)
cd /home/sybednar/projects/seedling_imager

# Run the GUI
exec python3 -u main.py
