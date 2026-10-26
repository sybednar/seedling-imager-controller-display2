<
# Changelog

## Unreleased — 2026-10-26 (camera stall handling, new System 1 hardware)
- **Live View no longer freezes the GUI if the camera stalls.** Frames are now fetched on a background thread (`_LiveFrameWorker` in `gui.py`); previously a stalled Arducam blocked the screen for 10 s per frame and queued-up taps (e.g. on Home) were replayed as start/stop pairs.
- **Automatic camera reconnect** (`recover_camera()` in `camera_arducam_usb3.py`, re-exported by `camera.py`): reads time out after 4 s, and after 2 consecutive failed reads the stream is released, the device re-detected and reopened (at most once per 30 s). Status line shows "Camera not responding … reconnecting" / "Camera reconnected".
- **GUI**: removed the light border around the message log on newer OS images; all left-column button rows are now exactly the same width.
- **Installer**: makes the system journal persistent (Raspberry Pi OS defaults it to memory-only).

## Unreleased — 2026-10-19 (System 1 freeze diagnostics)
- **Experiment runner**: `metadata.csv` rows are now flushed and fsync'd to disk as each image is saved (previously buffered until the run ended, so a system freeze left the file empty). Every runner status message is also appended to `run_log.txt` in the experiment folder.
- **Launcher**: `start_seedling_imager.sh` now holds a single-instance lock; a second launch exits cleanly instead of failing with `gpiod ... Device or resource busy` (System 1 had two launchers active, which caused a restart loop at boot).
- **Diagnostics** (new `diagnostics/` folder): `seedling-health-usb` logger writes a health line every minute (including an uncached NVMe read probe) plus all kernel messages to a USB flash drive, so evidence survives an NVMe/storage hang. Install with `sudo bash diagnostics/install_health_monitor.sh`, which also removes the duplicate labwc launcher and disables the old systemd --user unit.

## v1.3.2 — 2026-10-04
- **Hardware**: renamed the IR filter holder component to "850 nm long-pass filter holder" (Fusion archive and STEP files); clarified camera-mount contents in `hardware/README.md`; updated BOM.
- Updated root README, CHANGELOG and citation. Software unchanged from v1.3.0. Archived on Zenodo: 10.5281/zenodo.23144486.

## v1.3.1 — 2026-10-04
- **Hardware**
  - Added complete hardware design files under `hardware/`: full-assembly STEP (zipped), individual part STEP files by subsystem, KiCad 10 files for board 1, board 2 and the hall sensor board, bill of materials, and assembly render.
  - Hardware licensed under CERN-OHL-S v2 (`hardware/LICENSE-CERN-OHL-S-v2.txt`, `hardware/NOTICE.txt`).
  - Fusion archive (`.f3z`) and full-assembly STEP are distributed as GitHub Release assets (over the 100 MB repository file limit).
- **Licensing**: added root `LICENSE` (MIT) for the software.
- Software unchanged from v1.3.0. Archived on Zenodo: 10.5281/zenodo.23143807.


## v0.06 — 2026-01-08
- **Camera & Imaging**
  - Dual-stream Picamera2 config: full-res TIFF (4608×2592) + lores preview (640×360).
  - Lossless TIFF saving via `tifffile` (zlib compression).
  - AF helpers: Continuous AF in Live View; single AF trigger during settle.
  - AE lock/unlock: AE enabled during settle; disabled before capture for consistency.
- **Experiment Runner**
  - Per-plate sequence: LED ON → AF → 10 s settle → capture → LED OFF → advance.
  - Post-cycle wait after Plate 6, then start next cycle at Plate 1.
  - **CSV metadata logging** (`metadata.csv`): timestamp, cycle, plate, illumination, path, dimensions, size, AE, exposure, gain, AWB.
- **GUI**
  - **Camera Config dialog** with persisted settings (`camera_settings.json`).
  - **File Manager**: toolbar actions, thumbnails with robust TIFF fallback, per-plate filter, CSV tab & Open CSV.
  - **Experiment Setup**: storage estimate + free-space warning.
  - Live View stability and LED control restored; last-saved-image preview after capture.
- **Autostart & Launcher**
  - Systemd user service (`seedling-imager.service`) and desktop autostart entry.
  - Desktop launcher icon (`Seedling-Imager.desktop`).

---



## v0.05 — 2025-12-30
- **New:** `experiment_runner.py` to schedule time-lapse imaging cycles.
  - Per-plate sequence: illumination ON → 10 s settle → capture (if selected) → illumination OFF → advance.
  - Wait begins immediately after Plate 6, then next cycle starts at Plate 1.
  - Signals:
    - `image_saved_signal(path)` → GUI shows last captured image.
    - `settling_started(plate_idx)`/`settling_finished(plate_idx)` → optional live preview during settle.
- **GUI:**
  - Shows *last saved image* after each capture (helps remote users).
  - Optional live preview during settle period.
  - Homing terminology and dual illumination toggle (Green @ GPIO12, IR @ GPIO13).
  - “End Experiment” button aborts the thread gracefully.
- **Motor control:**
  - `advance()` now always reports drift correction when wrapping to Plate #1 (including “0 extra steps”).
- **Experiment Setup:**
  - Two-row plate selection; visible checkbox outlines; illumination selector with color (teal = Green, deep red = IR).
- **Camera:**
  - `save_image(path)` helper saves PNG/JPEG with correct color ordering.

## v0.04 — 2025-12-30
- Homing rename; dual-LED support; initial experiment loop scaffolding.

## v0.03 — 2025-12-30
- UI refinements; illumination selector; plate layout and sizing fixes; basic homing and drift code paths.

``
 >
