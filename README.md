# Seedling Imager Controller

## Overview
Inspired by the SPIRO (Smart Plate Imaging Robot; Ohlsson et al The Plant Journal doi: 10.1111/tpj.16587) project, the **Seedling Imager** is a Raspberry Pi 5-based imaging system designed to monitor Arabidopsis seedling growth using a 6-position hexagonal carousel. It provides automated imaging, LED control, and experiment scheduling through a touch-friendly GUI.

# Seedling Imager Controller — Universal

**v1.1.0** · Raspberry Pi 5 · PySide6 · picamera2 · GT2 belt carousel

A touchscreen controller for automated timelapse imaging of seedling plates using near-infrared (940 nm) transmission and front illumination. A single codebase runs on both supported display configurations without any code changes.

Repository: **https://github.com/sybednar/seedling-imager-controller-display2**

---

## Supported Hardware

| Component | System 1 (original) | System 2 |
|---|---|---|
| Display | Original 800×480 DSI touchscreen | Raspberry Pi Touch Display 2 (1280×720) |
| Scale factor `s` | 1.0 | 1.6 |
| Camera | Raspberry Pi HQ Camera | Raspberry Pi HQ Camera |
| Compute | Raspberry Pi 5 | Raspberry Pi 5 |
| Motor | Stepper + GT2 belt carousel | Stepper + GT2 belt carousel |
| Illumination | Dual 940 nm IR LEDs (front + rear) | Dual 940 nm IR LEDs (front + rear) |
| Optical sensor | Photointerrupter (hall + flag) | Photointerrupter (hall + flag) |

GUI layout, font sizes, button heights, and dialog dimensions all auto-scale via `s = screen_width / 800`. No separate display-specific files are needed.

---

## Key Features (v1.1.0)

### GUI & Display
- Auto-scaling dark theme UI: `s = screen_width / 800` (1.0 at 800 px, 1.6 at 1280 px)
- Fullscreen kiosk mode; all widget dimensions computed as `int(X * s)`
- `dark_style(s)` parameterized stylesheet — font, padding, and border-radius all scale

### Imaging
- Dual 940 nm IR illumination modes: **Front IR**, **Rear IR (transmission)**, **Combined**
- Per-mode camera presets stored in `camera_settings.json` (`FrontIR_*` / `RearIR_*` keys)
- Manual focus locked via `set_manual_focus()` at camera start (measured per unit — see Calibration Notes)
  - PDAF non-functional through 940 nm bandpass filter; manual focus required
- 16-bit grayscale TIFF output (`tifffile`; OpenCV fallback for non-TIFF formats)
- AE stability gate: polls `AnalogueGain` until < 5% relative change over 5 consecutive reads before pinning exposure
- `settling_started` signal emitted **after** AE is pinned and 0.20 s settle — GUI preview snapshot matches saved image exposure
- Live-view IR boost (mode-specific gain/exposure floor) enabled during preview, disabled before capture

### Motor / Carousel
- GT2 belt drive with dynamic bracket homing:
  1. CCW to LOW (leading edge of optical flag)
  2. CCW to HIGH (past leading edge)
  3. CW to LOW (re-validate leading edge)
  4. CW + `mid` µsteps to geometric center
- **Microstepping: 1/32** (BTT TMC2209: MS2=GND, MS1=VCC_IO). `steps_per_60_deg = 3200`.
  - This replaces the earlier 1/8-microstepping configuration (`steps_per_60_deg = 800`). 1/32 microstepping gives substantially finer positioning resolution and improved plate-to-plate registration — see Version History below.
  - **If you are upgrading an existing unit from a lower microstepping setting, delete `motion_cal.json` before the first run** — the saved calibration values do not scale automatically.
- Optical window `W` measured physically each homing run by counting µsteps CW across the sensor aperture (expected W ≈ 192 µsteps at 1/32 microstepping for the 5 mm stripe)
  - W is **not** a configurable parameter — it is measured live every homing cycle
- `CENTER_BACKOFF_FRAC = 0.0`: places carousel at exact geometric center regardless of W
  - Formula: `mid = max(1, int(round(W / 2.0 * (1.0 - CENTER_BACKOFF_FRAC))))`
  - Increase slightly (e.g. 0.05) only if consistent leading-edge drift is observed
- Log output includes `frac=` and `W=` on every homing for traceability

### Camera Config Dialog
- Tabbed interface: General settings + IR-specific presets
- Non-blocking "Read Current Position from Camera" button — `_FocusReader(QThread)` worker prevents GUI freeze when Live View is off
- Button disabled during read, re-enabled on completion or error

### Experiment Setup
- Configurable plate selection, frequency (default 30 min), duration, illumination mode
- Disk usage estimate uses `IMAGES_ROOT = Path("/home/sybednar/Seedling_Imager/images")` — **this path is hardcoded in `experiment_setup.py`.** If you use a different Linux username or folder layout, you must edit this line (see Setup, Step 0).
- Storage label colour: green (sufficient free space) / red (insufficient)

### File Manager
- Thumbnail grid with per-image metadata overlay
- Scaled thumbnail size: `QSize(int(100 * s), int(100 * s))`

---

## Module Structure

```
Seedling_Imager/                          # top-level project folder (NOT the git repo)
├── images/                               # timelapse output — IMAGES_ROOT (hardcoded path)
└── seedling_imager_controller/           # git clone of this repository
    ├── venv/                             # Python virtual environment (created locally, not in git)
    ├── main.py                           # Entry point; launches QApplication fullscreen
    ├── gui.py                            # Main window; computes s = screen_width / 800
    ├── styles.py                         # dark_style(s) — parameterized stylesheet
    ├── camera.py                         # Picamera2 wrapper; manual focus; TIFF save; AE gate
    ├── camera_config.py                  # Camera Config dialog; _FocusReader QThread
    ├── motor_control.py                  # Stepper driver; dynamic bracket homing; 1/32 microstepping
    ├── experiment_runner.py              # Timelapse loop; AE settle; settling_started signal
    ├── experiment_setup.py               # Setup dialog; plate/frequency/mode/disk usage
    ├── file_manager.py                   # File browser with thumbnail grid
    ├── registration.py                   # Per-plate phase cross-correlation registration analysis
    ├── jog.py                            # Manual motor jog utility for bench testing
    ├── camera_settings.json              # Persisted camera presets (FrontIR_*, RearIR_* keys)
    ├── motion_cal.json                   # Persisted motor calibration (auto-created on first homing)
    ├── requirements.txt                  # pip dependencies (installed inside venv)
    ├── install_dependencies.sh           # One-shot apt + venv + pip installer
    ├── start_seedling_imager.sh          # Launch wrapper used by systemd/autostart
    ├── restart_seedling_imager.sh        # Manual restart (used by desktop icon)
    ├── seedling-imager.service           # systemd user service template
    ├── seedling-imager-autostart.desktop # XDG autostart fallback template
    ├── Restart-Seedling-Imager.desktop   # Desktop icon template for manual restart
    ├── git_update.sh                     # Convenience script for commit + tag + push
    ├── hardware/                         # 3D print files / hardware documentation
    ├── logs/                             # Experiment run logs
    └── README.md
```

---

## Dependencies

Installed as **apt system packages** (compiled against Raspberry Pi OS's libcamera/Qt6/GPU libraries — do not pip-install these):
```
python3-picamera2
python3-pyside6.*    (no single "python3-pyside6" metapackage on current Raspberry Pi OS/Debian
                       Trixie — PySide6 is split per Qt module; the wildcard installs all of them:
                       sudo apt install 'python3-pyside6.*')
python3-numpy
python3-opencv      (cv2)
```

Installed as **pip packages inside the project virtual environment** (see `requirements.txt`):
```
tifffile   (16-bit TIFF read/write)
gpiod>=2.0 (stepper/LED GPIO — modern gpiod.line API; see https://pypi.org/project/gpiod/)
```

> **Note on GPIO library:** this project uses `gpiod` (the modern libgpiod v2.x Python bindings), **not** `RPi.GPIO` and **not** `gpiozero`. Both are absent from the codebase. `gpiod` is installed via pip (not apt) because the apt-packaged `python3-libgpiod` on current Raspberry Pi OS releases may ship an older 1.x API incompatible with `motor_control.py`'s `gpiod.line.Direction/Value/Bias` usage.

The `install_dependencies.sh` script (see Setup below) installs and verifies all of the above in one step.

---

## Setup — New Raspberry Pi 5 (Step by Step for Novices)

These instructions assume you have already flashed Raspberry Pi OS (Bookworm or Trixie) onto the NVMe/SD card, booted to the desktop, and connected to Wi-Fi/Ethernet. All commands are run in a terminal on the Raspberry Pi itself (or over SSH).

### Step 0 — Confirm your Linux username

The code hardcodes the path `/home/sybednar/Seedling_Imager/...` in two places (`experiment_setup.py`'s `IMAGES_ROOT`, and the autostart scripts). Open a terminal and run:

```bash
whoami
```

- If it prints `sybednar`, continue to Step 1 as written.
- If it prints anything else, either (a) create a `sybednar` user on this Pi, or (b) do a project-wide find-and-replace of `/home/sybednar/` with `/home/<your-username>/` in `experiment_setup.py`, `start_seedling_imager.sh`, `restart_seedling_imager.sh`, and `seedling-imager.service` before proceeding.

### Step 1 — Create the project folder

```bash
mkdir -p /home/sybednar/Seedling_Imager/images
cd /home/sybednar/Seedling_Imager
```

### Step 2 — Clone the repository

```bash
git clone https://github.com/sybednar/seedling-imager-controller-display2.git seedling_imager_controller
cd seedling_imager_controller
```

(HTTPS clone requires no GitHub account or SSH key setup — fine for read-only cloning of this public repo.)

### Step 3 — Install dependencies (one command)

```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

This installs the apt system packages, creates `venv/` with `--system-site-packages`, installs `requirements.txt` into it, and prints a verification check for every dependency (picamera2, PySide6, opencv, numpy, tifffile, gpiod). **Do not continue to Step 4 until this script finishes with no errors.**

### Step 4 — Make the launch/restart scripts executable

```bash
chmod +x start_seedling_imager.sh restart_seedling_imager.sh
```

### Step 5 — First manual run (before enabling autostart)

Always test manually first — it's much easier to read errors in a live terminal than in a log file.

```bash
source venv/bin/activate
python3 main.py
```

The app should open fullscreen. Use Alt+F4 (or the on-screen Exit control, if present) to close it and return to the terminal. If it fails to start, see Troubleshooting below before continuing.

### Step 6 — Calibrate manual focus for this camera unit

Manual focus is **per-camera-unit** and must be re-measured on every new Pi/camera pairing — do not reuse System 1's value. Follow the steps in the repository's `Setting manual camera focus instructions` file, then update the `ManualFocusPosition` value(s) in `camera_settings.json`.

### Step 7 — Confirm the motor calibration file is fresh

If this SSD/OS image was ever used with a different microstepping setting or a different physical unit, delete the stale calibration before the first homing run:

```bash
rm -f /home/sybednar/Seedling_Imager/seedling_imager_controller/motion_cal.json
```

It will be recreated automatically the first time `home()` runs successfully from the GUI.

### Step 8 — Enable autostart (systemd, recommended)

```bash
mkdir -p ~/.config/systemd/user
cp seedling-imager.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable seedling-imager.service
systemctl --user start seedling-imager.service
```

Check it's running:

```bash
systemctl --user status seedling-imager.service
```

Reboot the Pi and confirm the controller launches automatically to the fullscreen GUI.

**If the systemd service does not launch the GUI** (common cause: the graphical session doesn't export `WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR` to the systemd user session on some OS configurations), check the log first:

```bash
journalctl --user -u seedling-imager -e
tail -50 /home/sybednar/Seedling_Imager/seedling_imager_controller/autostart.log
```

Then fall back to the XDG autostart method instead:

```bash
systemctl --user disable seedling-imager.service
mkdir -p ~/.config/autostart
cp seedling-imager-autostart.desktop ~/.config/autostart/
```

Reboot again to confirm.

### Step 9 — Add the "Restart Seedling Imager" desktop icon

This lets you stop and relaunch the controller from the touchscreen (e.g. after exiting to review files) without rebooting the Pi.

```bash
cp Restart-Seedling-Imager.desktop ~/Desktop/
chmod +x ~/Desktop/Restart-Seedling-Imager.desktop
```

On first double-click, the desktop file manager may show an "Untrusted application launcher" warning — right-click the icon and choose **Allow Launching**, or **Trust**, then it will run normally from then on.

### Step 10 — Run a short registration test

Run a short multi-cycle experiment (a few plates, a few cycles) and inspect results with `registration.py` to confirm the 1/32-microstepping `motor_control.py` gives the same registration improvement seen on System 1 before starting a long unattended run.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `pip install` fails with "externally-managed-environment" | You're not inside the venv, or the venv was created without `--system-site-packages`. Re-run `source venv/bin/activate` first, or rebuild the venv per Step 3. |
| `ModuleNotFoundError: No module named 'picamera2'` inside the venv | The venv wasn't created with `--system-site-packages`, or the apt package `python3-picamera2` isn't installed. Rebuild: `rm -rf venv && python3 -m venv --system-site-packages venv`, then re-run `install_dependencies.sh`. |
| `ImportError: cannot import name 'Direction' from 'gpiod.line'` | An old `gpiod` (1.x) is shadowing the pip-installed 2.x version. Confirm with `venv/bin/pip show gpiod` (should be ≥2.0) and re-run `venv/bin/pip install --upgrade gpiod`. |
| Black screen / window never appears at boot, but manual `python3 main.py` works fine | Wayland vs X11 platform plugin mismatch. Edit `start_seedling_imager.sh`, comment `QT_QPA_PLATFORM=wayland`, uncomment the `xcb` line, and test manually before re-enabling autostart. |
| systemd service shows `enabled` but GUI never appears | The systemd user session didn't have graphical environment variables at start. Check `journalctl --user -u seedling-imager -e`, then fall back to the XDG autostart method (Step 8). |
| Homing/centering seems off after this update | Delete `motion_cal.json` and re-home — old calibration values from a different microstepping setting do not carry over (see Motor / Carousel notes above). |

---

## Migrating System 1 to this layout

System 1's current folder/autostart layout predates this document and differs from the structure above (its venv currently lives directly at `/home/sybednar/Seedling_Imager` and its code at a separate `/home/sybednar/projects/seedling_imager`). **Do not touch System 1 while it is running an experiment.** Once the current run finishes, migrating it to match this README is a bounded, low-risk job (recreate folders, move/re-clone code, point a new venv and systemd unit at the same paths as System 2) — worth doing once System 2 has validated this setup end-to-end, so both units and the README stay in sync for future users.

---

## Calibration Notes

### Manual Focus
- Manual focus is per-camera-unit. Measure and set `ManualFocusPosition` in `camera_settings.json` for each new system — do not copy System 1's value.
- PDAF is non-functional through the 940 nm bandpass filter on both systems.

### Optical Window W
W is measured automatically on every homing cycle — no manual configuration needed. Expect W ≈ 192 µsteps at 1/32 microstepping for the 5 mm stripe.

### CENTER_BACKOFF_FRAC
At the top of `motor_control.py`. Default `0.0` places the carousel at exact geometric window center. Only increase if consistent leading-edge drift is observed in registration analysis.

---

## Version History

### v1.1.0 — 2026-07 — 1/32 microstepping + documentation overhaul

**Motor**
- `motor_control.py` updated from 1/8 to 1/32 microstepping (`steps_per_60_deg`: 800 → 3200), same single-optical-sensor + 6-stripe dynamic-bracket strategy. Finer step resolution further improves plate-to-plate registration.
- Cleaned a leftover dead-code block in `_debounced_read()`.

**Documentation**
- Corrected GPIO dependency: `RPi.GPIO`/`gpiozero` (never used in code) replaced with `gpiod>=2.0` throughout.
- Replaced three conflicting clone/folder-structure instructions with a single canonical layout and step-by-step novice setup guide.
- Added `requirements.txt`, `install_dependencies.sh`, systemd service template, XDG autostart fallback template, and desktop restart-icon template — previously undocumented/uncommitted.
- Fixed repository URL (previous README referenced two nonexistent repo names).

### v1.0.0 — 2026-04-22 — Universal release

**Architecture**
- Single codebase runs on both 800×480 and 1280×720 displays without modification
- `s = screen_width / 800` computed once in `gui.py`; every pixel dimension expressed as `int(X * s)`
- `dark_style(s)` replaces fixed stylesheet string; font, padding, border-radius all scale with `s`

**Motor / centering fix**
- `CENTER_BACKOFF_FRAC = 0.0` replaces fixed `CENTER_BACKOFF = 5`
- Fixes System 1 centering error: with W=12 the old formula gave `mid=1` (leading edge) instead of `mid=6` (center)
- After pulley realignment: W=23–24, mid=12; registration RMS improved ~79% (6.7 px → 1.4 px mean)

**Imaging**
- AE stability gate: waits for AnalogueGain < 5% relative change × 5 consecutive reads before pinning exposure
- `settling_started` signal timing fixed: now emitted after AE pin + 0.20 s settle, not before — preview snapshot matches saved image exposure
- Non-blocking Read Focus button: `_FocusReader(QThread)` prevents GUI freeze when Live View is off

**Bug fixes**
- `IMAGES_ROOT` constant added to `experiment_setup.py` (was causing silent disk estimate failure)
- Experiment frequency default restored to 30 minutes
- `apply_main_illum_style` scope fix: `s = self._s` added inside method body
- `experiment_setup.py` line 235: orphaned `else` clause fixed (comment had been inserted between `if` body and `else`)
- `gui.py`: `setStyleSheet(dark_style(s))` moved to after `s` is computed (was causing `UnboundLocalError`)

**All v0.06 Display2 features carried forward**
- Dual 940 nm IR illumination (front + rear), per-mode camera presets
- Tabbed Camera Config dialog, File Manager with thumbnails, CSV metadata
- GT2 belt drive, autostart and desktop launcher

### v0.06 — Display2-specific release
Dual-stream camera, TIFF output, autofocus, File Manager with thumbnails, CSV metadata, Camera Config dialog, autostart and desktop launcher, GT2 belt drive initial implementation, per-mode IR presets.

---

## Registration Performance (System 1, v1.0.0, 1/8 microstepping baseline)

Rear IR transmission, 8 cycles, plates 1 and 2:

| Metric | v0.06 baseline | v1.0.0 |
|---|---|---|
| Mean RMS | 6.7 px | 1.4 px |
| Mean \|dx\| | 6.5 px | 1.3 px |
| dx bias | +6.5 px (systematic) | −0.4 px (eliminated) |
| Cycles at 0 px shift | 0 of 4 | 9 of 14 (64%) |
| Max \|dx\| | 10 px | 6 px |

Residual jitter (2–6 px) is intrinsic GT2 belt backlash and stepper microstepping nonlinearity. Software registration using ArUco or QR fiducial markers on plate backs can correct remaining shift to sub-pixel if required for quantitative analysis. **1/32-microstepping results from System 2 will be added here once validated (see Setup Step 10).**

---

## License

MIT — see `LICENSE` file.
