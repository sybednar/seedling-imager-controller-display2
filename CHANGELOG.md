<
# Changelog

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
