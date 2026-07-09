#!/usr/bin/env bash
# install_dependencies.sh
#
# One-shot dependency installer for the Seedling Imager Controller.
# Run this ONCE, from inside the cloned repository folder
# (seedling_imager_controller/), right after `git clone`.
#
#   cd ~/Seedling_Imager/seedling_imager_controller
#   chmod +x install_dependencies.sh
#   ./install_dependencies.sh
#
# What it does:
#   1. Installs system (apt) packages: picamera2, PySide6, numpy, opencv —
#      these need to be apt packages on Raspberry Pi OS so they are built
#      against the system libcamera/Qt6/GPU libraries.
#   2. Creates a Python virtual environment (venv/) INSIDE this folder with
#      --system-site-packages, so it can see the apt packages above.
#   3. Installs the remaining pure-Python packages (tifffile, gpiod) from
#      requirements.txt into that venv with pip.
#   4. Verifies gpiod imports with the modern (v2.x) API the code needs.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================================="
echo " Seedling Imager Controller — dependency installer"
echo " Project folder: $PROJECT_DIR"
echo "=================================================================="

echo
echo "--> [1/4] Installing system (apt) packages..."
sudo apt update
sudo apt install -y \
    python3-picamera2 \
    python3-pyside6 \
    python3-numpy \
    python3-opencv \
    python3-venv \
    python3-full \
    git

echo
echo "--> [2/4] Creating virtual environment at: $PROJECT_DIR/venv"
if [ -d "$PROJECT_DIR/venv" ]; then
    echo "    venv already exists — skipping creation (delete it first if you want a clean rebuild)."
else
    python3 -m venv --system-site-packages "$PROJECT_DIR/venv"
fi

echo
echo "--> [3/4] Installing pip requirements into the venv..."
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo
echo "--> [4/4] Verifying installation..."
"$PROJECT_DIR/venv/bin/python3" -c "
import gpiod
from gpiod.line import Direction, Value, Bias
print('  gpiod OK — version', getattr(gpiod, '__version__', 'unknown'))

import tifffile
print('  tifffile OK — version', tifffile.__version__)

from picamera2 import Picamera2
print('  picamera2 OK (imported via --system-site-packages)')

from PySide6.QtWidgets import QApplication
print('  PySide6 OK (imported via --system-site-packages)')

import cv2
print('  opencv (cv2) OK — version', cv2.__version__)

import numpy
print('  numpy OK — version', numpy.__version__)
"

echo
echo "=================================================================="
echo " All dependencies installed successfully."
echo " Activate the environment with:"
echo "     source \"$PROJECT_DIR/venv/bin/activate\""
echo "=================================================================="
