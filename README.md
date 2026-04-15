# Seedling Imager Controller

## Overview

Inspired by the [SPIRO](https://doi.org/10.1111/tpj.16587) (Smart Plate Imaging Robot; Ohlsson et al., *The Plant Journal*) project, the **Seedling Imager** is a Raspberry Pi 5-based time-lapse imaging system for monitoring *Arabidopsis thaliana* and other small seedlings growing on vertical MS agar plates. It uses a 6-position hexagonal carousel driven by a GT2 belt and stepper motor, a Raspberry Pi Camera Module 3 fitted with a 940 nm bandpass filter, and dual IR LED panels (front reflectance + rear transmission) controlled through a touch-friendly PySide6 GUI optimised for the Raspberry Pi Touch Display 2.

---

## Features (v0.07)

### Illumination — dual IR panels (replaces earlier green + IR design)

Three illumination modes are available and selectable from the main screen:

| Mode | GPIO | Description |
|---|---|---|
| **Front IR** | GPIO 13 | Front panel on only — IR reflectance off the plate surface |
| **Rear IR** | GPIO 12 | Rear panel on only — IR transmission through a translucent backing |
| **Combined IR** | GPIO 12 + 13 | Both panels on simultaneously |

The illumination toggle button changes colour (red / blue / purple) to show the active mode at a glance. Green illumination has been removed; all imaging is now performed in the 940 nm IR band, which does not activate plant photoreceptors and is invisible to the unaided eye.

### Camera — Raspberry Pi Camera Module 3 with 940 nm bandpass filter

- **Manual focus required**: Phase-detect autofocus (PDAF) does not function through the 940 nm bandpass filter. A manual lens position of **7.589 diopters (≈ 13 cm)** is set at startup and locked throughout every experiment.
- **Per-mode presets**: Separate camera parameter sets are stored for Front IR (reflectance) and Rear IR (transmission) capture and applied automatically at the start of each plate acquisition.
- **AE disabled for transmission**: Rear IR and Combined IR captures use pinned exposure and gain (`AeEnable = False`) to prevent exposure drift as seedlings grow and block increasing amounts of transmitted light over the course of a multi-day experiment.
- **AE stability gate**: Before each capture the runner polls `AnalogueGain` and waits until it stabilises (< 5 % relative change over 5 consecutive reads) before pinning and saving.

### Camera Config dialog — tabbed layout for Touch Display 2

The Camera Configuration dialog is now split into four tabs so it fits on the 720 px-tall Touch Display 2 landscape screen without scrolling:

| Tab | Contents |
|---|---|
| **General** | AE, Exposure, Gain, AWB, Contrast, Brightness, Saturation, Sharpness, NR, HDR |
| **Focus** | Manual focus enable/position, "Read from Camera" button |
| **Front IR** | Per-mode overrides for reflectance imaging |
| **Rear IR** | Per-mode overrides for transmission imaging |

All per-mode settings are persisted to `camera_settings.json` under `FrontIR_*` / `RearIR_*` keys and loaded automatically at experiment start.

### Motor control — GT2 belt drive with dynamic bracket homing

- Hall sensor (GPIO 26) triggers the initial coarse home.
- Optical sensor (GPIO 19) measures the optical window width `W` (typically 20–21 µsteps) and re-centres using a dynamic bracket algorithm with `CENTER_BACKOFF = 5` µsteps, placing the carousel at the mid-point of the optical slot.
- Full re-homing is performed at every cycle boundary (configurable via `REHOME_EVERY_N`) to maintain sub-5 px inter-cycle registration.
- Verified registration: ≤ 4 px lateral shift across repeated cycles on a 4608 px wide sensor (0.09 % of frame width).

### Experiment runner

- Plates 1–6 are imaged in order each cycle; unselected plates are skipped.
- Per-plate sequence: LED on → AE settle (10 s + optional 3 s first-plate warm-up) → AE stability gate → pin exposure/gain → **GUI preview snapshot** → capture TIFF → LED off → advance.
- The GUI preview snapshot fires **after** AE is pinned (not at LED-on), so the preview always matches the saved image.
- Images are saved as 16-bit grayscale TIFF with a mode tag in the filename (`front_gray`, `rear_gray`, or `combined_gray`).
- Per-experiment `metadata.json` and per-image `metadata.csv` are written alongside the images.
- Re-home at cycle boundary uses `motor_control.rehome_full_from_hall()` to re-measure `W` and re-centre without a full GUI homing sequence.

### GUI

- Full-screen PySide6 dark mode interface, scales to any display geometry.
- Focus mode indicator below the Camera Config button: yellow **MF: 7.589 D (13 cm)** when manual focus is active, grey **Focus: Auto** otherwise.
- Home button doubles as **STOP** during homing (cuts motor driver power immediately).
- Homing-with-preview before experiment start: Live View stays on during the initial home so alignment can be confirmed visually before imaging begins.
- File Manager dialog for browsing, previewing, and deleting experiment image trees.

---

## Hardware

| Component | Description |
|---|---|
| **Compute** | Raspberry Pi 5 |
| **Display** | Raspberry Pi Touch Display 2 (landscape, 1280 × 720) |
| **Camera** | Raspberry Pi Camera Module 3 (IMX708, 12 MP) |
| **Filter** | 940 nm bandpass filter (mounted in front of lens) |
| **Motor driver** | TMC2209 (UART + STEP/DIR mode) |
| **Motor** | NEMA 17 stepper, GT2 belt drive |
| **Homing sensors** | Hall effect (GPIO 26), optical ITR20001 (GPIO 19) |
| **IR front panel** | 940 nm LED array, GPIO 13 |
| **IR rear panel** | 940 nm LED array, GPIO 12 |

### GPIO pin map

| Function | GPIO |
|---|---|
| STEP | 20 |
| DIR | 16 |
| EN | 21 |
| Hall sensor | 26 |
| Optical sensor | 19 |
| Front IR LED | 13 |
| Rear IR LED | 12 |

---

## Software requirements

- Python 3.11+
- PySide6
- picamera2
- gpiod
- OpenCV (optional, used for image utilities)

---

## Installation

```bash
# Clone the repository onto the Raspberry Pi
cd ~/projects
git clone https://github.com/sybednar/seedling-imager-controller-display2.git seedling_imager
cd seedling_imager

# Install dependencies (system Python, no venv required on Pi OS Bookworm)
pip install PySide6 picamera2 gpiod --break-system-packages
```

### Autostart (optional)

A desktop launcher and `autostart.log`-based startup script are included. To launch manually:

```bash
cd /home/sybednar/projects/seedling_imager
python3 main.py
```

---

## Image output structure

```
/home/sybednar/Seedling_Imager/images/
└── experiment_YYYYMMDD_HHMMSS/
    ├── metadata.json          ← experiment-level settings
    ├── metadata.csv           ← per-image exposure/focus metadata
    ├── plate1/
    │   └── plate1_YYYYMMDD_HHMMSS_rear_gray.tif
    ├── plate2/
    │   └── plate2_YYYYMMDD_HHMMSS_combined_gray.tif
    └── ...
```

---

## Updating the repository

A helper script `git_update.sh` is included for committing and pushing changes:

```bash
cd /home/sybednar/projects/seedling_imager

# Basic commit and push
./git_update.sh -m "Your commit message"

# Commit, push, and tag a new version
./git_update.sh -m "v0.07: dual IR illumination, tabbed Camera Config, fixed preview timing" -v v0.07
```

---

## Version history

| Version | Summary |
|---|---|
| v0.07 | Dual IR illumination (front reflectance + rear transmission); 940 nm bandpass filter with manual focus; tabbed Camera Config dialog for Touch Display 2; AE stability gate; fixed experiment preview snapshot timing; GT2 belt drive with dynamic bracket homing; per-mode camera presets in `camera_settings.json` |
| v0.05 | Dual-stream camera (still + lores), TIFF output, autofocus settle, File Manager with thumbnails, CSV metadata, Camera Config dialog, autostart |

---

## Reference

Ohlsson et al. (2023). SPIRO: a low-cost, open-source platform for time-lapse imaging of plant growth. *The Plant Journal*. [doi: 10.1111/tpj.16587](https://doi.org/10.1111/tpj.16587)