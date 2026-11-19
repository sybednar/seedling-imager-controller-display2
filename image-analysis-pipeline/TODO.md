# TODO

## `singlePlantAnalysis` — early-frame measurements zeroed despite visible growth

Investigated 2026-07-23. `Results_raw.csv` reports `MainRootLength = 0` and
`HypocotylLength = 0` for early frames where the segmentation mask visibly shows
growth. Confirmed via direct testing against real masks
(`experiment_20260707_092606_Output/Analysis/1/cam_1/plant_2/Results_0/`).

Root cause is in `analysis/plantAnalysis.py`'s Phase 1 loop
("Find first frame with valid root structure", ~lines 105-186), which searches
for the first frame where a full root graph can be built before tracking starts.
Zeroing `MainRootLength`/`LateralRootsLength` during this search is intentional
and correct — tracking can't begin before a root structure exists. Two
side effects of that phase are bugs, not intentional filtering:

### 1. `HypocotylLength` gets discarded even when it was computed correctly

`analysis/plantAnalysis.py` lines 131-152: `hypocotyl_length` is computed
independently at line 124 (separate class-4-mask routine, unrelated to root
graph success), but every early-return path in the loop hardcodes
`saveProps(frame_name, frame_idx, False, csv_writer, 0, 0)` instead of passing
the real value through. `analysis/graphUtils/save.py` `saveProps()` (~lines
100-105) reinforces this by writing a literal zero row whenever `graph=False`,
ignoring whatever hypocotyl value was passed in.

Verified empirically: frames 11-18 have real, growing hypocotyl lengths
(1px → 22px) computed correctly by the pipeline, but recorded as `0` in
`Results_raw.csv` because the *root* wasn't found yet — an unrelated failure.

**Fix:** pass `hypocotyl_length` (and lateral count, where applicable) through
in the three early-return branches (lines 133, 143, 149) instead of hardcoding
`0`, and update `saveProps()` to accept and write those values even when
`graph=False`.

### 2. Fixed-depth skeleton pruning destroys short, newly-emerged root sprouts

`analysis/imageUtils/seg.py`, `extract_skeleton()` line 282:
`skeleton_crop = prune(skeleton_crop, 5)` — a fixed 5-iteration erosion with no
length-awareness. For a root skeleton only ~8-13px long (frames 17-18 in the
test data), 5 erosion passes consume the entire structure before endpoint
detection runs, collapsing it to a single orphan pixel with 0 endpoints. This
fails the `len(end_points) >= 2` validity check (line 310), so a real, visible
root sprout is discarded.

Verified empirically:
```
frame 17: raw skeleton (pre-prune) = 8px, 2 endpoints  -> after prune(5): 1px, 0 endpoints
frame 18: raw skeleton (pre-prune) = 13px, 2 endpoints -> after prune(5): 1px, 0 endpoints
frame 19: raw skeleton = 20px, 2 endpoints             -> after prune(5): 14px, 2 endpoints (survives)
```

**Fix:** guard the pruning depth against skeleton length (e.g. skip/soften
pruning when raw skeleton length is below ~2x `num_it`), or detect orphan-pixel
collapse and fall back to the pre-prune skeleton.

### Not a bug (for reference)

Frames 0-10 in the test dataset genuinely have no root or hypocotyl pixels in
the mask — only a stationary seed blob and a shoot region above it. Zeros there
are correct and don't need fixing.

## `singlePlantAnalysis/analysis/dataWork.py` — remaining known issue

See `CHANGES.md` — `PostProcess_Hour.csv` still has `NaN` in 2 of every 3 hourly
rows when the capture interval doesn't divide 60 minutes evenly (e.g. 180 min).
`plot_individual_plant` (`analysis/report.py`) plots without markers, so
isolated non-`NaN` points don't render as visible line segments. Proposed fix
(not yet applied): interpolate the hourly gaps right after the resample step.

## Installers (`installer_conda_{linux,wsl,mac}.sh`)

Open items found while moving the pipeline into the monorepo (not applied):

- **WSL1 is not detected.** If `$DISPLAY` is empty inside WSL, the distro is
  probably WSL1, which has no GUI/WSLg support. The installer's WSL check
  (`grep -qEi "(Microsoft|WSL)" /proc/version`) matches WSL1 and WSL2. Add an
  explicit WSL-version check to `installer_conda_wsl.sh` and a troubleshooting
  entry to `WSL_INSTALL.md` (fix: `wsl --set-version <Distro> 2` from
  PowerShell, then `wsl --shutdown`).
- **Full-repo clone.** Linux/WSL installers clone the whole monorepo (Pi code,
  CAD, hardware docs). A sparse checkout
  (`git sparse-checkout set image-analysis-pipeline`) would avoid that.
- **Website moved to the monorepo** (`.github/workflows/deploy-site.yml`,
  `frontend/astro.config.mjs`). Remaining: set repo Settings > Pages > Source to
  "GitHub Actions" after merging to `main`; the `frontend/design/*.html`
  mockups still carry the old URLs.

## Report experiment filter / ArUco calibration — open follow-ups

From the 2026-11-16 code review of the experiment filter, ArUco guard and precheck
(the Important items were fixed; these were left). None is a crash on current data.

- `analysis/qr.py` imports `pyzbar` at the top, so the ArUco guard fails with
  "ArUco detection failed" on a machine without libzbar even though ArUco-only use
  does not need it. Lazy-import `pyzbar` inside `qr_detect`.
- `report_utils.experiment_display_name` reads only the first `metadata.json`; metadata
  that is not a dict raises `AttributeError`, and `{"Experiment": null}` returns `None`
  (shows as "None" in the GUI and report). It also does not apply `convertFromPathSafe`
  to the metadata name the way `2_postprocess.py` does, so names containing `_dot_` can differ.
- `filter_experiments` matches display name *or* folder name, so two folders with the
  same display name are selected/deselected together. Matching and storing the folder
  basename only would avoid it.
- `plotLateralAnglesOnTop` now also applies the has-data check (skips experiments without
  `PostProcess_Hour.csv`) and runs the filter over every `os.listdir` entry, including plain files.
- Deselecting an experiment does not remove its old files in `Report/` (per-experiment
  images, `Individual plant plots/<exp>`); only `Temporal_Data.csv` is rebuilt
  (`FORCE_REPORT = True`).
- `check_aruco_marker` scans up to 20 large images on the GUI thread (UI freezes briefly);
  the wait cursor is restored manually instead of in a `try/finally`. The precheck dialog
  reads 16-bit images as 8-bit, so a dim image can look dark.
- The new `WARNING`s in `2_postprocess.py` (no marker / marker under 300 px) were only
  syntax-checked, not run end to end on a real project.
- `test_report_filter.py` does not cover metadata that is not a dict, a null `Experiment`,
  files mixed into `Analysis/`, or `plotLateralAnglesOnTop`.
- `analysis/qr.py::aruco_detect_full` lost its comment explaining why
  `CORNER_REFINE_APRILTAG` is used (rigid-marker side length stable to ~0.2 px vs SUBPIX
  1-4 px off); consider restoring it.


## Batch Analyze follow-ups

Parked items from the Batch Analyze work (`singlePlantAnalysis/batch_setup.py`,
`analysis/utils/getROIandSeed.py`):

- Confirm screen: a drag drifts after an edge clamp (the box stops at the image edge
  but the drag anchor keeps moving).
- `run_batch`: a plant whose `plantAnalysis` returns early (no root found) still counts
  as a success.
- The Batch Analyze button is cramped (141x28 at the bottom of Tab 1).
- User-reported "needs a double click to select/add a box" on the confirm screen;
  not reproduced (macOS Cocoa HighGUI window focus suspected).
- The box proposal merges touching plants into one box; splitting by nearest seed is
  a possible follow-up.
- `apply_processing_limit` / `setupPlantAnalysis` hardcode `* 24 * 4` (a 15-minute
  capture interval).
