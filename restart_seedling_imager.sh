#!/usr/bin/env bash
# restart_seedling_imager.sh
#
# Restarts the Seedling Imager Controller via its systemd --user service.
# Intended to be triggered from the "Restart Seedling Imager" desktop icon,
# but can also be run by hand from a terminal.
#
set -euo pipefail

echo "Restarting Seedling Imager Controller (systemd --user service)..."
systemctl --user restart seedling-imager.service

echo "Restart triggered. Check ~/Seedling_Imager/seedling_imager_controller/autostart.log if the window doesn't appear."
