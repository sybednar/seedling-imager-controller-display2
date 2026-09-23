# Seedling Imager Controller

## Overview
Inspired by the SPIRO (Smart Plate Imaging Robot; Ohlsson et al The Plant Journal doi: 10.1111/tpj.16587) project, the **Seedling Imager** is a Raspberry Pi 5-based imaging system designed to monitor Arabidopsis seedling growth using a 6-position hexagonal carousel. It provides automated imaging, LED control, and experiment scheduling through a touch-friendly GUI.

# Seedling Imager Controller — Universal

**v1.2.1** · Raspberry Pi 5 · PySide6 · picamera2 (or Arducam USB3) · GT2 belt carousel

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
| Power (Pi 5) | SZZCNOX 5V/5A PD step-down module | SZZCNOX 5V/5A PD step-down module |

GUI layout, font sizes, button heights, and dialog dimensions all auto-scale via `s = screen_width / 800`. No separate display-specific files are needed.

> **Power supply note:** both systems use the same SZZCNOX 5V/5A USB-PD step-down board. A different-brand step-down module was tried on System 2 during a hardware upgrade and measured **5.42 V** on the Pi 5's 5V rail (GPIO pins 2/4) instead of 5.0 V — that ~0.2 V overvoltage is the confirmed cause of an intermittent shutdown/reboot hang (`plymouth-poweroff`/`plymouth-reboot` stuck for 1–2 minutes, or indefinitely). Swapping back to the SZZCNOX module resolved it completely. **Measure your 5V rail voltage before troubleshooting any shutdown/reboot instability in software** — it will look exactly like an OS or application bug otherwise. See Troubleshooting below.

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

### Camera Backend (Picamera2 / Arducam USB3)
- Selectable in Camera Config → General tab: **Raspberry Pi Camera Module 3 (Picamera2)** [default] or **Arducam 20MP AR2020 Mono USB3**
- Persisted as `CameraBackend` in `camera_settings.json`; **switching requires an application restart** — the backend is fixed for the lifetime of the running process (`camera.py` only imports the selected backend module, since each one claims its physical camera device at import time)
- `camera.py` is a thin dispatcher: every other module calls `camera.get_frame()`, `camera.save_image()`, etc. unchanged regardless of which backend is active
- Arducam backend validated on physical hardware (Sept 2026): full-resolution reopen/discard/retry sequence confirmed reliable across extended multi-cycle experiments, including a `mock_capture()` path that exercises the same reopen sequence for unselected plates so every plate position gets a fresh, reliable on-screen preview whether or not it is actually captured that cycle. Before relying on it for a new unit:
  1. `sudo apt install v4l-utils` (already included in `install_dependencies.sh`)
  2. Connect the camera, then run `python3 -c "import camera_arducam_usb3 as c; c.print_diagnostics()"` — reports the detected `/dev/videoN` device, every resolution/format the driver advertises, and every V4L2 control it exposes
  3. Compare against the assumptions documented at the top of `camera_arducam_usb3.py` (control names, resolutions, mode-switch timing) and adjust the constants there if they don't match
- The Arducam is a **fixed physical manual-focus lens** (twist the M12 ring by hand) — there is no AF motor, so `set_manual_focus()`/AF-related calls are safe no-ops on this backend; the Focus tab in Camera Config has no effect when Arducam is selected
- UVC cameras generally stream one resolution at a time, unlike Picamera2's simultaneous main+lores streams — the Arducam backend runs live preview at a lower resolution continuously and briefly reconfigures to full resolution for each saved image (or each mock capture), so expect a short pause per cycle that the Picamera2 backend does not have

### Germination / Photomorphogenesis LEDs
- Independent on/off toggle buttons for **Blue (450 nm)**, **Red (660 nm)**, and **FarRed (730 nm)** — driven low-side via 3× IRLZ44N MOSFETs on the auxiliary MOSFET board
- Not coupled to the IR imaging illumination cycle — hold any combination on (e.g. Red+FarRed for a red:far-red ratio treatment) while IR imaging continues independently
- State is not persisted between sessions — all three channels default OFF at startup

### Camera Config Dialog
- Tabbed interface: General settings (incl. Camera Backend selector) + Focus + IR-specific presets
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
    ├── camera.py                         # Camera BACKEND DISPATCHER — selects picamera2 vs arducam_usb3
    ├── camera_picamera2.py               # Picamera2 backend; manual focus; TIFF save; AE gate
    ├── camera_arducam_usb3.py            # Arducam 20MP AR2020 mono USB3 backend (OpenCV/V4L2)
    ├── camera_config.py                  # Camera Config dialog; Camera Backend selector; _FocusReader QThread
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
    ├── start_seedling_imager.sh          # Launch wrapper used by both autostart methods below
    ├── restart_seedling_imager.sh        # Manual stop/relaunch (used by desktop icon)
    ├── seedling-imager-autostart.desktop # XDG autostart template — RECOMMENDED (see Setup Step 8)
    ├── seedling-imager.service           # systemd --user service template — optional/alternative (see Setup Step 8)
    ├── Seedling_Imager.desktop           # Desktop icon template — start/restart the controller (see Setup Step 9)
    ├── git_update.sh                     # Convenience script for commit + tag + push
    ├── hardware/                         # 3D print files / hardware documentation
    ├── logs/                             # Experiment run logs
    └── README.md
```

---

## GPIO Pin Map (as of v1.2.0)

All pins below are on the auxiliary MOSFET board or the motor driver, addressed via `gpiod` against `/dev/gpiochip0`.

| GPIO | Function | Module |
|---|---|---|
| 12 | Germination LED — Blue 450 nm | `gui.py` |
| 13 | Germination LED — Red 660 nm | `gui.py` |
| 16 | Motor DIR | `motor_control.py` |
| 17 | Front IR imaging panel (reflectance) | `gui.py` |
| 19 | Germination LED — FarRed 730 nm | `gui.py` |
| 20 | Motor STEP | `motor_control.py` |
| 21 | Motor driver EN | `motor_control.py` |
| 22 | Optical sensor (reflective stripe) | `motor_control.py` |
| 23 | *Reserved* — rear IR940 intensity PWM (AO4805 mosfet, not yet implemented) | — |
| 24 | *Reserved* — rear IR940 intensity PWM (AO4805 mosfet, not yet implemented) | — |
| 26 | Hall sensor (motor pre-index) | `motor_control.py` |
| 27 | Rear IR imaging panel (transmission) | `gui.py` |

**v1.2.0 pin reshuffle:** `OPTICAL_PIN` moved 19→22 and the front/rear IR imaging panels moved 13→17 and 12→27, freeing GPIO12/13/19 for the three germination LED channels above. If you're carrying forward calibration or wiring notes from before v1.2.0, update them against this table, not the older pin numbers referenced in earlier Version History entries.

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
v4l-utils           (provides v4l2-ctl — only needed if using the Arducam USB3 camera backend)
libxcb-cursor0      (required by Qt >= 6.5's xcb platform plugin; usually already present, but
                     confirmed missing on at least one fresh Raspberry Pi OS Trixie image — see
                     Troubleshooting)
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

These instructions assume you have already flashed Raspberry Pi OS (Bookworm or Trixie) onto the NVMe/SD card, booted to the desktop, confirmed **Desktop Autologin** is enabled for your user (`sudo raspi-config` → System Options → Boot / Autologin → Desktop Autologin), and connected to Wi-Fi/Ethernet. All commands are run in a terminal on the Raspberry Pi itself (or over SSH — except where noted in Step 8/9, where a few things must be checked from a terminal running *inside* the desktop session itself).

### Step 0 — Confirm your Linux username

The code hardcodes the path `/home/sybednar/Seedling_Imager/...` in two places (`experiment_setup.py`'s `IMAGES_ROOT`, and the autostart scripts). Open a terminal and run:

```bash
whoami
```

- If it prints `sybednar`, continue to Step 1 as written.
- If it prints anything else, either (a) create a `sybednar` user on this Pi, or (b) do a project-wide find-and-replace of `/home/sybednar/` with `/home/<your-username>/` in `experiment_setup.py`, `start_seedling_imager.sh`, `restart_seedling_imager.sh`, `seedling-imager.service`, and `seedling-imager-autostart.desktop` before proceeding.

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

(HTTPS clone requires no GitHub account or SSH key setup — fine for read-only cloning of this public repo. If you need the Arducam USB3 branch specifically, add `-b arducam-integration` to the clone command.)

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

Always test manually first — it's much easier to read errors in a live terminal than in a log file. Run this from a terminal opened **on the Pi's own desktop** (not a bare SSH session), since the app needs the desktop's live display/session environment:

```bash
source venv/bin/activate
python3 main.py
```

The app should open fullscreen. Use Alt+F4 (or the on-screen Exit control, if present) to close it and return to the terminal. If it fails to start, see Troubleshooting below before continuing.

### Step 6 — Calibrate manual focus for this camera unit

Manual focus is **per-camera-unit** and must be re-measured on every new Pi/camera pairing — do not reuse another unit's value. Follow the steps in the repository's `Setting manual camera focus instructions` file, then update the `ManualFocusPosition` value(s) in `camera_settings.json`.

### Step 7 — Confirm the motor calibration file is fresh

If this SSD/OS image was ever used with a different microstepping setting or a different physical unit, delete the stale calibration before the first homing run:

```bash
rm -f /home/sybednar/Seedling_Imager/seedling_imager_controller/motion_cal.json
```

It will be recreated automatically the first time `home()` runs successfully from the GUI.

### Step 8 — Enable autostart (XDG autostart, recommended)

Two mechanisms exist for autostarting the controller GUI when the desktop session starts: a **systemd `--user` service** and an **XDG autostart `.desktop` entry**. Real-world testing across two different Pi 5 units (and, on one of them, two different OS images) consistently found the systemd method **unreliable for this application**: it works fine when started by hand in an already-running session (`systemctl --user enable --now ...`), but on a genuine cold `sudo reboot` it either fails with a Qt platform-plugin error or exits silently a few seconds after launch, with no window ever appearing. The confirmed root cause is that the systemd user manager on these Pi 5 / labwc images does not reliably import `XAUTHORITY`/`WLR_XWAYLAND` into its environment the way an interactive desktop session does — `DISPLAY` and `WAYLAND_DISPLAY` are present, but the xcb/XWayland platform plugin still can't authenticate without those two extra variables. `start_seedling_imager.sh` already sets explicit fallback defaults for both (see the script), which helps but has not made systemd fully reliable across every image tested. The **XDG autostart** method sidesteps the problem entirely, since the compositor launches it directly inside the already-fully-initialized session — it has been 100% reliable across every reboot/shutdown test performed. **Use it as the primary method:**

```bash
mkdir -p ~/.config/autostart
cp seedling-imager-autostart.desktop ~/.config/autostart/seedling-imager.desktop
```

**Reboot the Pi with `sudo reboot` (a real reboot — not `systemctl --user start`) and confirm the controller launches automatically to the fullscreen GUI.** Also test a full `sudo shutdown now` to confirm the Pi actually powers off cleanly. Testing only with a live-session start can look successful and still fail on a real cold boot — always validate with an actual reboot and an actual shutdown before considering autostart done.

If the GUI doesn't appear, check the log first:

```bash
tail -80 /home/sybednar/Seedling_Imager/seedling_imager_controller/autostart.log
```

<details>
<summary>Optional: systemd <code>--user</code> service (alternative method — click to expand)</summary>

If you'd prefer process supervision (automatic restart on crash) and are willing to validate it carefully, the systemd unit is still provided:

```bash
mkdir -p ~/.config/systemd/user
cp seedling-imager.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now seedling-imager.service
```

Check it's running:

```bash
systemctl --user status seedling-imager.service --no-pager -l
```

**Do not stop here** — this only confirms it works when started inside your current live session, which is exactly the false-positive result seen on both test units before a real reboot exposed the failure. Reboot and re-check status/log before trusting it:

```bash
sudo reboot
# after it comes back up:
systemctl --user status seedling-imager.service --no-pager -l
tail -80 /home/sybednar/Seedling_Imager/seedling_imager_controller/autostart.log
```

If it fails (Qt platform-plugin error, or the log shows the script exiting cleanly within a few seconds of launch with no other error), fall back to the XDG method above:

```bash
systemctl --user disable --now seedling-imager.service
mkdir -p ~/.config/autostart
cp seedling-imager-autostart.desktop ~/.config/autostart/seedling-imager.desktop
sudo reboot
```

</details>

### Step 9 — Add the "Seedling Imager" desktop icon

This lets you start (or stop-and-relaunch) the controller from the touchscreen — e.g. after using "Exit to Desktop" to review files — without rebooting the Pi.

```bash
cp Seedling_Imager.desktop ~/Desktop/
chmod +x ~/Desktop/Seedling_Imager.desktop
```

**Two one-time desktop settings, or the icon won't work smoothly:**

1. On first double-click, the file manager may show an "Untrusted application launcher" warning — right-click the icon and choose **Allow Launching** (or **Trust**), then it will run normally from then on.
2. By default, clicking an executable `.desktop`/script icon pops up an "Execute / Execute in Terminal / Display / Cancel" dialog every time instead of just running it. To disable this: open the **File Manager**, go to **Edit → Preferences** (or right-click the desktop → **Desktop Preferences**, depending on OS version), find the **General** tab, and check **"Don't ask options on launch executable file."** Without this, every click on the icon interrupts the user with an extra dialog.

The icon uses `seedlings.png` (already in this repo) and calls `restart_seedling_imager.sh`, which kills any already-running instance of the GUI and relaunches `start_seedling_imager.sh` fresh — safe to click whether or not the controller is currently running.

### Step 10 — Run a short registration test

Run a short multi-cycle experiment (a few plates, a few cycles) and inspect results with `registration.py` to confirm the 1/32-microstepping `motor_control.py` gives the same registration improvement seen on System 1 before starting a long unattended run.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `pip install` fails with "externally-managed-environment" | You're not inside the venv, or the venv was created without `--system-site-packages`. Re-run `source venv/bin/activate` first, or rebuild the venv per Step 3. |
| `ModuleNotFoundError: No module named 'picamera2'` inside the venv | The venv wasn't created with `--system-site-packages`, or the apt package `python3-picamera2` isn't installed. Rebuild: `rm -rf venv && python3 -m venv --system-site-packages venv`, then re-run `install_dependencies.sh`. |
| `ImportError: cannot import name 'Direction' from 'gpiod.line'` | An old `gpiod` (1.x) is shadowing the pip-installed 2.x version. Confirm with `venv/bin/pip show gpiod` (should be ≥2.0) and re-run `venv/bin/pip install --upgrade gpiod`. |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb" ... xcb-cursor0 or libxcb-cursor0 is needed` | Missing system library required by Qt ≥ 6.5. Fix: `sudo apt-get install -y libxcb-cursor0`. Seen on a fresh Raspberry Pi OS Trixie image where it wasn't pulled in automatically. |
| `qt.qpa.xcb: could not connect to display` when testing manually | You're running the command over plain SSH (no `DISPLAY`), not in a terminal inside the desktop session. Either open a terminal locally on the Pi's touchscreen, or (for a quick manual check only) `export DISPLAY=:0` in the SSH shell first. |
| GUI never appears at boot, but manual `python3 main.py` (run inside the desktop session) works fine | This is the systemd `XAUTHORITY`/`WLR_XWAYLAND` gap described in Setup Step 8. Switch to the XDG autostart method — don't spend time tuning `QT_QPA_PLATFORM` or startup delay first, since neither addresses the actual cause. |
| systemd service shows `enabled`, `autostart.log` shows the script reach `Seedling Imager launch end` a few seconds after launch, but no window ever appeared | The app started and exited cleanly on its own under systemd — a different, not-fully-understood failure mode from the Qt platform-plugin error above, also resolved by switching to XDG autostart. Confirmed independent of camera backend and hardware revision. |
| systemd service works when started by hand (`enable --now`) but not after a real `sudo reboot` | Expected — see Setup Step 8. Validate autostart only with a genuine reboot, never with a live-session start. |
| `sudo shutdown`/`sudo reboot` hangs for 1–2 minutes (or indefinitely) at a `plymouth-poweroff`/`plymouth-reboot` message | Check your Pi 5's 5V rail voltage (GPIO pins 2/4) before assuming it's a software issue — a step-down power module running even slightly over 5.0 V (5.4 V confirmed to cause this) can produce exactly this symptom. See the Power Supply note near the top of this README. Also run `sudo rpi-eeprom-update` and apply any pending bootloader update (`sudo rpi-eeprom-update -a && sudo reboot`) as a secondary check, especially on units with an NVMe HAT. A momentary pushbutton wired to the J2 GPIO shutdown pins will reliably force a clean power-down while you diagnose this. |
| Clicking the desktop icon pops up an Execute/Terminal/Cancel dialog every time | See Setup Step 9 — enable "Don't ask options on launch executable file" in the File Manager's preferences. |
| Homing/centering seems off after this update | Delete `motion_cal.json` and re-home — old calibration values from a different microstepping setting do not carry over (see Motor / Carousel notes above). |

---

## Migrating an Existing Unit to This Layout

If a unit's folder/autostart layout predates this document, bringing it in line is usually a small job, not a rebuild:

1. **Confirm the folder structure first before assuming anything needs to move.** Check `ls -la /home/<user>/Seedling_Imager/` and `ls -la /home/<user>/Seedling_Imager/seedling_imager_controller/venv/bin/python3` — many units already have the correct layout (repo cloned into `Seedling_Imager/seedling_imager_controller/`, venv nested inside it) even if that wasn't true at some earlier point in the unit's history. Don't move files that are already in the right place.
2. **The autostart mechanism is the part most likely to need changing.** If the unit currently relies on the systemd `--user` service, convert it to the XDG autostart method per Setup Step 8 — do this even if the systemd version currently "seems to work," since a live-session start can pass while a real cold reboot fails (see Troubleshooting). Validate with an actual `sudo reboot` and `sudo shutdown`, not just `systemctl --user enable --now`.
3. Update the desktop icon to the current `Seedling_Imager.desktop` template and confirm the File Manager preference from Setup Step 9 is set.
4. Back up (rename, don't delete) any old/stale project folders before removing them, and only delete the backups once the converted unit has been confirmed working across a real reboot and shutdown.
5. **Do not touch a unit while it is running an experiment.** Do this migration between experimental runs.

---

## Calibration Notes

### Manual Focus
- Manual focus is per-camera-unit. Measure and set `ManualFocusPosition` in `camera_settings.json` for each new system — do not copy another system's value.
- PDAF is non-functional through the 940 nm bandpass filter on both systems.

### Optical Window W
W is measured automatically on every homing cycle — no manual configuration needed. Expect W ≈ 192 µsteps at 1/32 microstepping for the 5 mm stripe.

### CENTER_BACKOFF_FRAC
At the top of `motor_control.py`. Default `0.0` places the carousel at exact geometric window center. Only increase if consistent leading-edge drift is observed in registration analysis.

---

## Version History

### v1.2.1 — 2026-09 — Autostart reliability fix + setup documentation overhaul

**Autostart**
- Root-caused systemd `--user` autostart unreliability to `XAUTHORITY`/`WLR_XWAYLAND` not being reliably imported into the systemd user manager's environment on Pi 5/labwc images, even though `DISPLAY`/`WAYLAND_DISPLAY` are present. `start_seedling_imager.sh` now sets explicit fallback defaults for both.
- XDG autostart (`~/.config/autostart/`) promoted to the **recommended** primary method after passing repeated real cold-reboot and full-shutdown testing on two separate physical units; systemd retained as a documented, secondary/optional method.
- Desktop icon renamed/consolidated to a single `Seedling_Imager.desktop` template (start-or-restart), replacing the earlier restart-only icon naming.

**Hardware**
- Documented a confirmed root cause for intermittent `plymouth-poweroff`/`plymouth-reboot` shutdown hangs: a non-matching 5V step-down power module running at 5.42 V instead of 5.0 V. Resolved by standardizing on the SZZCNOX 5V/5A module on both systems.
- Added `sudo rpi-eeprom-update` as a secondary shutdown-instability check, particularly for units with an NVMe HAT.

**Camera**
- Arducam USB3 backend validated against physical hardware across extended multi-cycle runs; added `mock_capture()` so every plate position gets a fresh, reliable on-screen preview regardless of whether that plate is actually captured that cycle.

**Dependencies**
- Added `libxcb-cursor0` as a documented apt dependency (Qt ≥ 6.5 requirement, found missing on a fresh Raspberry Pi OS Trixie image).

### v1.2.0 — 2026-08 — Selectable camera backend, germination LEDs, GPIO reshuffle

**Camera**
- `camera.py` split into a backend dispatcher plus two implementations: `camera_picamera2.py` (existing Picamera2/libcamera code, behavior unchanged) and new `camera_arducam_usb3.py` (OpenCV/V4L2 backend for the Arducam 20MP AR2020 monochrome USB3 camera)
- Backend selectable in Camera Config → General (`CameraBackend` in `camera_settings.json`); requires an app restart to take effect

**Hardware / GPIO**
- Added a 3-channel germination/photomorphogenesis LED strip (Blue 450 nm, Red 660 nm, FarRed 730 nm) with independent GUI on/off toggles, driven low-side via IRLZ44N MOSFETs on a new auxiliary MOSFET board
- Reshuffled GPIO pins to make room: `motor_control.py`'s `OPTICAL_PIN` moved 19→22; `gui.py`'s front/rear IR imaging panel pins moved 13→17 and 12→27. See the GPIO Pin Map above for the full current assignment, including GPIO23/24 reserved for a planned rear-IR940 PWM intensity control (AO4805 mosfet, not yet implemented in software)

**Dependencies**
- Added `v4l-utils` (apt) for the Arducam backend's `v4l2-ctl`-based exposure/gain control

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
