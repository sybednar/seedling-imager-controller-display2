#!/usr/bin/env bash
# restart_seedling_imager.sh
#
# Stops any running instance of the Seedling Imager Controller and relaunches
# it — no reboot required. Intended to be triggered from the
# "Restart Seedling Imager" desktop icon, but can also be run by hand from a
# terminal.
#
set -euo pipefail

PROJECT_DIR="/home/sybednar/Seedling_Imager/seedling_imager_controller"

echo "Stopping any running Seedling Imager Controller instance..."
# Matches on the full main.py path set by start_seedling_imager.sh, so this
# does not accidentally kill unrelated python3 processes on the system.
pkill -f "python3 $PROJECT_DIR/main.py" 2>/dev/null || true
sleep 2

echo "Relaunching Seedling Imager Controller..."
nohup "$PROJECT_DIR/start_seedling_imager.sh" >/dev/null 2>&1 &
disown

echo "Restart triggered. Check $PROJECT_DIR/autostart.log if the window doesn't appear."
