# Changes — 2026-10-14

## `analysis/qr.py`

### 1. ArUco corner refinement changed from SUBPIX to APRILTAG

**Symptom:** On `plate1` the detected side length of the (rigid, fixed-camera)
marker varied from 401 to 427 px (std 4.1 px) across 42 frames; centroid y
jumped by up to 17 px. `plate2` was milder (std 1.2 px).

**Cause:** `CORNER_REFINE_SUBPIX` with the default 5 px window gave no better
corner accuracy than no refinement at all on these images.

**Fix:** `aruco_detect_full()` (new; `aruco_detect()` now wraps it with an
unchanged return value) uses `CORNER_REFINE_APRILTAG`. Side-length std drops to
0.2 px on both plates. Per-frame x-shift used by the aligner changes by at most
0.6 px (mean ~0.25 px), so the main gain is for corner-based quantities such as
`aruco_get_pixel_size` (mm per pixel), not alignment.

**Tradeoff:** detection is ~12x slower (0.87 s vs 0.07 s per 4608x2592 frame).
Pixel sizes computed after this change will differ slightly from earlier runs.

## `imageAligner/process.py`, `imageAligner/run.py`

### 2. Aligner now tracks the reference marker by ID instead of taking index 0

**Cause:** `compute_transforms` used `corners[0]`, the first marker in each
frame's detections, with no ID check, and OpenCV does not guarantee order. On
`plate2` frame 28 the detector also reports a spurious 35 px marker (ID 17)
next to the real 413 px marker (ID 2); the real one happened to come first.
If the order flipped, that frame would shift by ~130 px.

**Fix:** the reference is the largest marker in frame 0 (`pick_reference_id`);
every frame is matched to that ID (`select_marker`, larger wins if the ID
appears twice). A frame without the reference ID is left unaligned, same as a
frame with no marker. `compute_transforms` now takes one `(4,2)` array (or
`None`) per frame. Results on `plate1`/`plate2` are unchanged, since each has
one real marker.

# Changes — 2026-09-03

## `analysis/imageUtils/seg.py`

### 1. Added a hard horizontal-distance gate to hypocotyl component selection

**Symptom:** When two plants' hypocotyls both fall inside one plant's ROI
(rectangular ROI forced wide by e.g. a diagonally-growing root), the neighbor's
hypocotyl could get tracked as this plant's own — specifically when the
neighbor's hypocotyl becomes a valid, trackable blob *before* this plant's own
hypocotyl does. At that point the only candidate component in the ROI belongs
to the neighbor.

**Cause:** `extract_hypocotyl_length()`'s anchor selection (added in an earlier
session to fix largest-blob-wins picking the wrong plant) always picked
whichever component was *closest* to `fixed_seed_position`, with no rejection
threshold — unlike the sibling root-selection code in
`extract_root_segmentation()`, which already had one (`distance_to_root_base <
100`, falling back to `found_root=False` otherwise). So if this plant had no
hypocotyl blob yet, the neighbor's blob — the only one present — was accepted
regardless of how far away it actually was.

**Fix:** Replaced the Euclidean `cv2.pointPolygonTest` distance used for
anchor scoring with a horizontal-only distance (candidate bounding-rect vs.
`root_origin`'s x-coordinate), and added a hard cutoff
`max_horizontal_distance=80` (a new keyword arg on `extract_hypocotyl_length`,
default `80`). If the closest candidate is farther than that, the function now
returns `(zeros, 0)` — no hypocotyl detected — instead of forcing a pick.

Horizontal-only distance was chosen over Euclidean because plants are plated
in a row (measured minimum seed spacing ~170px) and a hypocotyl grows
vertically from its own seed: neighboring plants separate cleanly on the
x-axis, while a real hypocotyl can legitimately sit far away in y once it's
tall. `80` = half of the ~170px minimum spacing, minus a small margin for
blob width.

**Known residual risk (not fixed):** the stitching step just below the anchor
check (`GAP_THRESHOLD = 100` in the same function) that grows the accepted
mask outward from the anchor is still a full 2D gap check, not horizontally
scoped. If a real hypocotyl is accepted as anchor near the 80px edge, and a
neighbor's blob sits within a 100px 2D gap of it, stitching could still pull
in a sliver of the neighbor's hypocotyl. Narrower/less likely than the bug
this fix addresses; left alone rather than tightened blind. Revisit only if
seen in production data.

**How to revert if this proves error-prone in testing:** in
`extract_hypocotyl_length()`, restore the previous signature (drop the
`max_horizontal_distance=80` parameter) and replace the anchor-selection block
with:

```python
origin_pt = (int(root_origin[0]), int(root_origin[1]))
anchor_index = 0
best_distance = None
for i, (area, comp, rect) in enumerate(components_data):
    contains_origin = cv2.pointPolygonTest(comp, origin_pt, False) > 0
    distance = 0 if contains_origin else abs(cv2.pointPolygonTest(comp, origin_pt, True))
    if best_distance is None or distance < best_distance:
        best_distance = distance
        anchor_index = i

if anchor_index != 0:
    components_data.insert(0, components_data.pop(anchor_index))
```

This restores "always pick nearest available, no rejection" behavior (still
proximity-anchored, just without the horizontal-only metric or the hard
cutoff). Alternatively, `git log -- singlePlantAnalysis/analysis/imageUtils/seg.py`
and revert this specific commit.

# Changes — 2026-08-24

## `environment.yml` / `environment_no_nnunet.yml`, `singlePlantAnalysis/3_generateReport.py`

### Fixed report generation crashing entirely on fresh installs due to an unpinned `multimethod` regression

**Symptom:** A user on a freshly-installed WSL environment ran `3_generateReport.py`
and it crashed immediately at import time, before doing anything:

```
TypeError: metaclass conflict: the metaclass of a derived class must be a
(non-strict) subclass of the metaclasses of all its bases
```

with the traceback rooted in `skfda`'s `Identity` operator registering
`gram_matrix_optimization` via `multimethod`.

**Cause:** `environment.yml` pins `scikit-fda=0.10.1` (released April 2025) but
never pins its transitive dependency `multimethod`. `scikit-fda`'s own metadata
only excludes `multimethod==1.11`/`1.11.1` (an older, unrelated bug fixed in
Feb 2024) — it has no upper bound. `multimethod==2.0.2` (Nov 2025) shipped a
change ("Nested `subtype` allowed") that breaks `skfda`'s `Identity` operator
registration with exactly this metaclass-conflict error. Any environment
solved before Nov 2025 still resolves to an older, working `multimethod` and
never sees this; any environment solved fresh today resolves to the latest
release (`2.1` as of this writing) and crashes immediately.

Compounding the impact: `3_generateReport.py` imported `performFPCA` from
`analysis.fpca_analysis` unconditionally at the top of the file, even though
FPCA only actually runs behind `if conf['doFPCA']:`. So the broken import took
down report generation entirely — the temporal plots, convex hull analysis,
Fourier plots, and lateral angle plots never ran either, even for configs with
`doFPCA` disabled.

**Fix:**
- `environment.yml` / `environment_no_nnunet.yml`: added `multimethod<2.0.2` to
  pin the solver to the last known-good release.
- `3_generateReport.py`: moved `from analysis.fpca_analysis import performFPCA`
  out of the top-level imports and into the `if conf['doFPCA']:` block, wrapped
  in a `try/except` that logs and skips FPCA on failure instead of crashing —
  so a broken/incompatible FPCA dependency can no longer take down the rest of
  the report.



## `analysis/dataWork.py`

### 1. Fixed `expected_hour_count` hardcoded to a 15-minute capture interval

**Symptom:** Growth chart came out empty (or badly truncated) whenever the capture
interval was set to anything other than 15 minutes — worst at 180 minutes, where
only the first ~24 hours of a multi-day experiment survived.

**Cause:** After resampling the per-frame data to hourly bins, the code reconciled
the resulting row count against the expected frame count (`N_exp`) using a formula
that assumed a fixed 4 frames/hour (15-min interval):

```python
expected_hour_count = (N_exp + 3) // 4
```

This silently ignored `conf['timeStep']` (the actual configured capture interval),
so at 180 minutes it computed a duration ~12x too short and truncated the
hourly dataframe down to just the first day.

**Fix:** Generalized the formula to use the real capture interval, accounting for
the fencepost relationship between frame count and elapsed time (`N_exp` frames
span `N_exp - 1` intervals, since the first frame defines t=0):

```python
expected_hour_count = (N_exp - 1) * timeStep // 60 + 1
```

### 2. Fixed `medfilt` zero-padding artifact flattening the last few data points

**Symptom:** The last `kernel_size // 2` (4, for kernel=9) measurements of
`MainRootLength`, `LateralRootsLength`, `NumberOfLateralRoots`, and
`HypocotylLength` were identical, even though the raw segmentation data kept
increasing right up to the last frame.

**Cause:** `scipy.signal.medfilt(x, 9)` implicitly zero-pads past the array
boundary. Near the end of a short series, the window's zero-padding pulled the
median down, and the "values never decrease" clamp locked all subsequent points
to that same value — producing an artificial flat plateau at the end of every
plant's curve.

**Fix:** Replaced `signal.medfilt(x, 9)` with a centered rolling median that
shrinks its window near the edges instead of padding with fabricated data:

```python
pd.Series(x).rolling(window=9, center=True, min_periods=1).median().to_numpy()
```

This keeps full 9-point smoothing wherever a full window is available, and uses
only real neighboring points (no padding) near the start/end of the sequence.

Applied to `mainRoot`, `lateralRoots`, `numlateralRoots`, and `hypocotylLength`
(lines ~175-178). The `medfilt(..., 5)` calls used for `MainOverTotal`,
`LateralDensity`, and `DiscreteLateralDensity` were left unchanged.

## `analysis/plantAnalysis.py` / `analysis/graphUtils/save.py` — 2026-08-19

### 3. Fixed `HypocotylLength` being discarded whenever the root graph wasn't valid yet

**Symptom:** `Results_raw.csv` reported `HypocotylLength = 0` on early frames
where the segmentation mask visibly showed hypocotyl growth, whenever the main
root hadn't been detected/tracked yet. Confirmed empirically against real masks
(`experiment_20260707_092606_Output/.../plant_2/Results_0/`) — frames 11-18 had
real, growing hypocotyl lengths (1px → 22px) computed correctly by the
pipeline, but recorded as `0`.

**Cause:** `plantAnalysis.py`'s Phase 1 loop ("Find first frame with valid root
structure") computes `hypocotyl_length` independently each frame (a separate
class-4-mask routine, unrelated to root graph success), but every early-return
path in the loop — `not found_root`, `not is_valid_skeleton`, the
`extract_root_segmentation` exception handler, and the `graphInit`/`createTree`
exception handler — hardcoded `saveProps(..., 0, 0)`, discarding the
already-computed value. `graphUtils/save.py`'s `saveProps()` reinforced this by
writing a literal all-zero row whenever `graph=False`, ignoring whatever
hypocotyl value was passed in. Zeroing `MainRootLength`/`LateralRootsLength`
during this search is intentional and correct (tracking can't begin before a
root structure exists) — only the hypocotyl discard was a bug.

**Fix:**
- `plantAnalysis.py`: initialize `hypocotyl_length = 0` at the top of each
  Phase 1 loop iteration (so a genuinely failed frame still defaults safely,
  without carrying over a stale value from a previous frame), and pass the
  real `hypocotyl_length` through at all four early-return `saveProps()` calls
  instead of hardcoding `0`.
- `graphUtils/save.py`: `saveProps()`'s no-graph branch now writes
  `[image_name, frame_number, 0, 0, number_lateral_roots, 0, hypocotyl_length]`
  instead of an all-zero row — root/lateral lengths correctly stay `0` (no
  graph to derive them from), but the independently-measured hypocotyl length
  and lateral count now survive.

**Effect:** frames can now correctly show `HypocotylLength > 0` while
`MainRootLength = 0`, reflecting that hypocotyl elongation and root emergence
are separate biological events that don't have to start at the same time.
Early-experiment growth curves will look different (hypocotyl growth appears
several frames earlier) than before this fix — this is a correction, not a
regression.

## Known remaining issue (not yet fixed)

`PostProcess_Hour.csv` still has `NaN` in 2 of every 3 hourly rows whenever the
capture interval doesn't divide 60 minutes evenly (e.g. 180 min). Since
`plot_individual_plant` (`analysis/report.py`) plots this hourly data without
markers, isolated non-`NaN` points don't render as visible line segments — the
chart can still look empty even though the data is correct.

Proposed fix (not applied): interpolate the hourly gaps right after the resample
in `dataWork.py`:

```python
hour_data = data.resample(f'60{FREQ_MIN}', origin=reference_timestamp).mean()
hour_data = hour_data.interpolate(method='linear').ffill().bfill()
```

---

*The entries below were backfilled on 2026-09-09 by auditing the full git
history for fixes that were never written up here. They predate the entries
above.*

# Changes — 2026-08-19

## `analysis/imageUtils/seg.py`

### Fixed hypocotyl component selection picking a neighboring plant's larger blob over this plant's own

**Symptom:** `extract_hypocotyl_length()` picked whichever class-4 connected
component had the largest pixel area in the ROI, with no awareness of which
plant it actually belonged to. Since ROI selection is forced rectangular, a
diagonally-growing root could force the ROI wide enough to include a
neighboring plant's hypocotyl — and if that neighbor's blob happened to be
larger, it got selected as this plant's hypocotyl instead.

**Cause:** component selection sorted candidates purely by
`cv2.contourArea` and always accepted index 0 (largest), with no check
against anything specific to this plant.

**Fix:** `extract_hypocotyl_length()` gained a second parameter,
`root_origin`, called with `fixed_seed_position` (not `current_root_base` —
the seed position never changes for the whole analysis, so it's a stable
per-plant anchor unaffected by any root-tracking drift/mistakes). Component
selection now scores every candidate by proximity to `root_origin`
(contains-point test first, else nearest-edge distance via
`cv2.pointPolygonTest`) and promotes whichever component is closest to the
seed to be the accepted anchor — mirroring the analogous pattern
`extract_root_segmentation()` already used for root component selection.

**Note:** this anchor selection had no rejection threshold — if this plant
had no hypocotyl blob yet, the nearest *available* component (even a distant
neighbor's) still got picked regardless of how far away it was. That gap is
what the horizontal-distance-gate fix in the 2026-09-03 entry above
addresses.

# Changes — 2026-06-12

## `analysis/utils/fileUtilities.py`, `run.py`, `2_postprocess.py`, `3_generateReport.py`

### Removed a hardcoded RPI-module path segment that didn't match the pipeline's actual capture setup

**Symptom:** `createSaveFolder()` always built a 4-level output structure —
`Analysis/{experiment}/{rpi}/{cam}/{plant}/Results_N/`, with an extra `rpi`
directory level between experiment and camera — regardless of whether the
capture setup actually used multiple Raspberry Pi units. The corresponding
path-parsing/lookup code in `run.py`, `2_postprocess.py`, and
`3_generateReport.py` all assumed and reconstructed this same 4-level
structure, so the fix had to be applied consistently across all of them.

**Cause:** the path structure carried a multi-RPi-rig assumption that didn't
match the pipeline's actual/current capture setup.

**Fix:** dropped the `rpi` path segment entirely — `cam_path` is now built
directly under the experiment's `id_path`
(`Analysis/{experiment}/{cam}/{plant}/...`). Matching updates were made to
every consumer of that path structure (`run.py`, `2_postprocess.py`,
`3_generateReport.py`) so parsing and folder construction stay in agreement.

**Note:** an earlier attempt at this same change (`a91ae07` "Removed RPI
Module...") was fully reverted (`57cd635`) before this commit re-did it
correctly and consistently — this is the version that stuck.

## `imageAligner/run.py`, `segmentationApp/run.py`

### Missing ArUco marker on the reference frame blocked the entire plate's alignment and segmentation

**Symptom:** if the first frame of a plate's timelapse had no detectable
ArUco marker, `AlignWorker` emitted a fatal `error` signal and stopped
immediately — no aligned output was produced for that plate at all. Because
segmentationApp's queue guard requires aligned output to exist before letting
segmentation start, this blocked the whole plate's segmentation too, not just
alignment.

**Cause:** marker-detection failure on the reference frame was treated as
unrecoverable, with no fallback path.

**Fix:** `imageAligner/run.py` now downgrades this to a `warning` signal and
falls back to copying the raw images through unaligned (identity transform)
into the `aligned` output folder, so the rest of the pipeline can still
proceed for that plate. `segmentationApp/run.py`'s queue-status logic gained
`Not Aligned` / `Partially Aligned` states (with matching UI coloring, a
blocking "Run Image Aligner first" prompt for the fully-unaligned case, and a
confirm-before-start prompt for the partial case) so users can see and act on
the alignment gap instead of the pipeline silently stalling.

# Changes — 2026-05-19

## `analysis/utils/fileUtilities.py` and callers, `segmentationApp/run.py`

### Image discovery hardcoded to `.png` silently dropped `.tif`/`.tiff` experiments

**Symptom:** `getImages()` globbed only `*.png`. Any experiment whose source
capture images were `.tif`/`.tiff` returned zero images from this call, so
the plant's raw images couldn't be located at all (falling through to a
metadata-fallback path). `segmentationApp/run.py`'s queue monitor used the
same `.png`-only glob for its image-count fallback and legacy
Fold_0/Ensemble progress counters, so it under-reported progress or showed
"No Images" for `.tif` experiments too.

**Cause:** the file extension was hardcoded at both call sites instead of
covering the actual set of capture formats in use.

**Fix:** `fileUtilities.py` added `loadImageFiles()`, which globs `*.png`,
`*.tif`, and `*.tiff` together (naturally sorted); `getImages()` and its
metadata-fallback branch switched to it. `segmentationApp/run.py`'s
image-count fallback and legacy progress counters were updated to sum all
three extensions instead of `.png` alone.

# Changes — 2026-04-16

## `singlePlantAnalysis/run.py` (then `GUI/run.py`)

### Blank plate/camera/plant/experiment-name fields corrupted output paths

**Symptom:** the RPI/camera/plant/experiment-name Qt text fields were read
directly into the config dict with no validation. A blank (or
whitespace-only) field produced an empty string that fed straight into
output-folder path construction (`createSaveFolder`) as a path
segment/identifier.

**Cause:** no default or sanitization was applied before these fields were
used to build filesystem paths.

**Fix:** each field now defaults to `"1"` when blank
(`field.text().strip() or "1"`), and `editingFinished` handlers were added so
a blank field self-corrects to `"1"` as soon as focus leaves it, not just at
submit time.
