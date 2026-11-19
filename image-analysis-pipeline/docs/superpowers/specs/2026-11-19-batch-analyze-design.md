# Batch Analyze: auto-proposed plant ROIs with manual root origin

Branch: `feature/batch-analyze`

## Intent
Today each plant on a plate needs its own run: drag an ROI, click the root
origin, repeat per Plant Number. For a plate of N plants that is N ROI drags and
N separate GUI runs. Batch Analyze proposes every plant's ROI automatically from
the segmentation, lets the user confirm/fix them on one screen, then has them
click the root origin in each confirmed ROI (kept manual so segmentation errors
cannot skew `fixed_seed_position` and hence the measurements).

## Goals
- New **Batch Analyze** button in Tab 1, next to the existing **Analyze Plant**
  (which is unchanged).
- Propose one ROI per plant for the whole plate; user can move/resize, delete
  and add boxes before confirming.
- Root origin is always a manual click per confirmed ROI, using the existing
  `selectSeed()` UI.
- After confirmation, analyse each plant in turn with the same code path as a
  single-plant run (`plantAnalysis`), so outputs are identical in layout.

## Non-goals / anti-goals
- No automatic root origin. Auto-proposing the origin is the failure mode this
  design exists to avoid.
- No change to single-plant `analysis()` behaviour, `plantAnalysis()` internals
  or the saved `metadata.json` format.
- Not parallel processing; plants run sequentially.
- Not a fix for segmentation misses: a plant with no detected seed is added by
  hand on the confirm screen.

## Constraints
- `plantAnalysis()` is one plant per run and reads `conf['bounding box']` /
  `conf['seed']` on the replicate path; Batch Analyze reuses that rather than
  changing it.
- OpenCV windows are launched from a subprocess (as `1_analysis.py` does today),
  not inside the Qt GUI process.
- Plate-level checks (video folder, segmentation present, calibration fields,
  ArUco guard) run once, before anything opens. The ArUco guard applies to batch
  because every plant on the plate shares the same scale.
- `bounding box` is `[y_min, y_max, x_min, x_max]`; seed is `[x, y]` in full-image
  coordinates (confirm in implementation: `selectSeed` returns crop-relative `pos`).
- Tab 1 uses absolute geometry (810x680 fixed); the new button must not sit
  under a divider line (see CLAUDE.md Qt stacking note).

## Approaches considered
1. Replace the manual drag in `getROIandSeed()` with proposed boxes, one run per
   plant. Smallest, but repeats detection/confirmation per plant.
2. **Chosen (user picked):** a plate-level step. Detect seeds, one confirm screen
   for all boxes, origin click per box, then analyse each plant.
3. Option 2 plus automatic batch run. The user's button name ("Batch Analyze")
   implies running the analyses, so the run-after-confirm part of 3 is included.

## Design
**Detection** (`analysis/utils/proposeROIs.py`, pure numpy/cv2, no GUI):
- Take the seed class (value 3) from the first frame that has any; if none, the
  first 10 frames combined. Connected components, drop blobs under a minimum
  area, centroid per blob, sort by x. Index + 1 = proposed Plant Number.
- Box per plant: x range from the midpoint to each neighbouring seed (outermost
  boxes use half the typical spacing, clipped to the image); y from the topmost
  hypocotyl/leaf/petiole pixel (classes 4-6) in that x band across all frames,
  minus a margin, to the lowest root-class pixel in that band plus a margin
  (capped at the image bottom). The top is never lower than seed y minus the
  margin (also the fallback when no shoot pixels exist), because the hypocotyl
  grows up from the seed and a crop that starts at the seed would cut it off. Midpoint limits stop a neighbour's
  hypocotyl being pulled in (the earlier `extract_hypocotyl_length` bug).

**Confirm screen** (`selectPlantROIs(image, proposals)` in `getROIandSeed.py`):
- Last frame with numbered boxes. Click a box to select, drag handles to resize or
  drag the body to move, `D` delete, `A` then drag to add, `Enter` confirm,
  `Q` cancel. Boxes are renumbered left to right on confirm.

**Origin click:** for each confirmed box, call the existing `selectSeed()`.
Cancelling aborts the batch before any analysis starts; nothing is saved.

**Orchestration:** new `batch_setup.py` (CLI, run as a subprocess by the GUI)
writes `batch_plants.json` (`[{plant, bounding box, seed}]`) and then runs
`plantAnalysis(conf, replicate=True)` for each entry with `conf['plant']` set,
like `1_analysis.py` does after its config setup. Config prep currently inline in
`1_analysis.py` (sequenceLabel, pixel_size, etc.) is moved into a shared helper so
both scripts use one copy.

**GUI** (`run.py`): `batchAnalysisButton` + `batch_analysis()`. Validation from
`analysis()` is factored into a shared method so both buttons check identically.

## Testing
`test_batch_rois.py` (unittest, headless like `test_aruco_guard.py`):
synthetic seed masks give the right count/order, tiny blobs are ignored, boxes
split at midpoints and stay inside the image, merged/missing seeds degrade
without crashing. The GUI guard test pattern is reused to check that the button
runs the same validation and does not launch on failure.

## Left to the builder
Minimum blob area, margins, handle size and key bindings; exact button position.

## Calls I made (not discussed)
- Run the analyses automatically after confirmation (name implies it).
- Seeds detected from early frames, box length from all frames.
- Plant numbers are 1..N left to right, overwriting the Plant Number field.
