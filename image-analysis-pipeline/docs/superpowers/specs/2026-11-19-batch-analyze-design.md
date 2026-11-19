# Batch Analyze: auto-proposed, editable plant ROIs with manual root origin

Branch: `feature/batch-analyze`

## Intent
Today each plant on a plate needs its own run: drag an ROI, click the root
origin, repeat per Plant Number. For a plate of N plants that is N ROI drags and
N separate GUI runs. Batch Analyze shows the plate once, lets the user draw every
plant's ROI on one screen (pre-filled from the last frame's segmentation, fully
editable), then has them click the root origin in each ROI (kept
manual so segmentation errors cannot skew `fixed_seed_position` and hence the
measurements). A first proposal (seed centroids with midpoint splits and
margins, `proposeROIs.py`) was dropped as not accurate; the current proposal is
the connected-component rule under Design.

## Goals
- New **Batch Analyze** button in Tab 1, next to the existing **Analyze Plant**
  (which is unchanged).
- Draw one ROI per plant for the whole plate on the last frame; user can move,
  resize, delete and add boxes before confirming. Boxes are proposed but never
  trusted: every one is checked by the user.
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
- The proposal never decides the root origin, and touching plants are not split
  automatically (they merge into one box; the user splits or redraws by hand).

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
1. Replace the manual drag in `getROIandSeed()` with one run per plant. Smallest,
   but repeats ROI selection per plant.
2. **Chosen (user picked):** a plate-level step. One confirm screen for all boxes,
   origin click per box, then analyse each plant.
3. Option 2 plus automatic batch run. The user's button name ("Batch Analyze")
   implies running the analyses, so the run-after-confirm part of 3 is included.
4. Rejected: propose boxes from seed centroids with midpoint splits
   (`proposeROIs.py`). Not accurate enough, so removed.
5. **Current:** propose boxes from connected components of the last frame's
   segmentation (below), editable on the confirm screen.

## Design
**Box proposal** (`analysis/utils/componentROIs.py`, pure numpy/cv2):
`propose_component_boxes_info(seg_path)` reads the LAST frame's mask (the last
entry of the processing-limited seg list). Plant mask = classes 1-6 (root, lateral,
seed, hypocotyl, leaf, petiole); background 0 and ignore 7 are not plant, so class 7
never bridges two plants. Label with 8-connectivity. Seeds are class-3 blobs of
area >= 30 px. Each seed maps to the plant-mask component containing it; the box is
that component's bounding box (leftmost, rightmost, topmost, bottommost pixel) plus
a 20 px margin, clipped to the image. One box per distinct component, so several
seeds in one component (touching plants) give one box; components without a seed
(noise) give none. It returns `(boxes, n_seeds)` and boxes are ordered with
`boxEdit.renumber`. Any failure or unreadable mask falls back to manual drawing.

**Confirm screen** (`selectPlantROIs(image, boxes, notice=None)` in
`getROIandSeed.py`; `getPlateROIsAndSeeds` passes the proposals and a notice such
as "Auto-proposed N boxes from M seeds" plus, when M > N, "(some plants touch and
were merged: split or redraw by hand)", shown for ~8 s):
- Drag on empty space draws a new box (no add mode needed; `A` add mode and
  `Esc` to leave it still work). Click a box to select, drag its body to move,
  drag an edge to resize, `D` delete, `Enter` confirm, `Q` cancel. A drag under
  the minimum size is rejected with an on-screen message. With no boxes a hint
  says to drag on the plate. Proposed boxes are edited exactly like drawn ones. Decisions (press meaning, legend text, numbering)
  live in pure helpers in `boxEdit.py` so the window code stays thin.
- Plant numbers are shown live on each box and come from the same function
  (`boxEdit.plant_order`) as the final numbers, so what you see is what is saved.

**Plant indexing** (`boxEdit.plant_order` / `renumber`, pure): by row first, then
left to right. Sort boxes by y_min; start a new row when a box's y_min exceeds the
previous box's y_min (in that order) by more than `ROW_GAP_FRACTION` (0.25) of the
median box height (y_max - y_min); within a row sort by x_min. Rows are numbered
bottom row first (largest y_min), so the bottom row of the plate gets the lowest
numbers: a plant clearly lower in the image is indexed lower even if its x is
higher. A single row is plain left to right.

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
`test_batch_rois.py` (unittest, headless like `test_aruco_guard.py`): pure box
helpers (hit test, move/resize, key and press actions, legend, row-aware numbering incl. jitter, three rows,
empty and single box);
`getPlateROIsAndSeeds` with patched `selectPlantROIs`/`selectSeed` (starts with no
boxes, numbers plants, cancel paths, `pos` reset). The cv2 window itself is not
unit-tested. The GUI guard test pattern is reused to check that the button runs the
same validation and does not launch on failure.

## Left to the builder
Handle size and key bindings; exact button position.

## Calls I made (not discussed)
- Run the analyses automatically after confirmation (name implies it).
- Plant numbers are 1..N bottom row first then left to right, overwriting the Plant Number field.
