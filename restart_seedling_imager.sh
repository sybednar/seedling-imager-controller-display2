#!/usr/bin/env bash
# restart_seedling_imager.sh
#
# Stops and relaunches the Seedling Imager Controller. Triggered from the
# "Seedling Imager" desktop icon, but can also be run by hand from a
# terminal.
#
# Uses XDG autostart (~/.config/autostart/) rather than a systemd --user
# unit (see README — Setup Step 8 for why), so this just kills any running
# GUI process and relaunches start_seedling_imager.sh directly, instead of
# going through systemctl. Safe to run whether or not the controller is
# currently running.
set -uo pipefail

echo "Stopping any running Seedling Imager Controller..."
pkill -f "python3 .*main.py" 2>/dev/null || true
sleep 2

echo "Relaunching..."
nohup /home/sybednar/Seedling_Imager/seedling_imager_controller/start_seedling_imager.sh >/dev/null 2>&1 &
disown

echo "Restart triggered. Check ~/Seedling_Imager/seedling_imager_controller/autostart.log if the window doesn't appear."
