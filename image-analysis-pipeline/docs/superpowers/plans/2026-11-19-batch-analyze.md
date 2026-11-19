> **Superseded:** Task 1 (automatic box proposal, `proposeROIs.py`) was replaced by a manual ROI screen and later by the component-based proposal (`componentROIs.py`), with row-aware plant indexing (top row first, then bottom row, each left to right). See `../specs/2026-11-19-batch-analyze-design.md`. The rest of this plan is unchanged.

# Batch Analyze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Batch Analyze button that proposes every plant's ROI on a plate, lets the user confirm/edit them, collects a manual root origin per ROI, then analyses each plant.

**Architecture:** A pure detection module proposes boxes from the segmentation seed class. A cv2 confirm screen edits them, and the existing `selectSeed()` collects each origin. A new `batch_setup.py` subprocess saves `(bounding box, seed)` per plant and calls `plantAnalysis(conf, replicate=True)` once per plant. The GUI button reuses single-plant validation and the ArUco guard.

**Tech Stack:** Python, OpenCV (cv2), numpy, PyQt5, `unittest` (no pytest in the ChronoRoot env).

**Spec:** `image-analysis-pipeline/docs/superpowers/specs/2026-11-19-batch-analyze-design.md`

## Global Constraints

- Run everything from `singlePlantAnalysis/` in the `ChronoRoot` conda env; tests are `python -m unittest <module> -v`.
- `bounding box` is `[y_min, y_max, x_min, x_max]` in full-image pixels; `seed` is `[x, y]` **relative to the cropped ROI** (this is what `selectSeed()` returns and what `extract_root_segmentation` indexes with). Verified in code.
- Segmentation class values: `1` main root, `2` lateral root, `3` seed, `4` hypocotyl. Seed class is `3`.
- Single-plant `analysis()`, `1_analysis.py` behaviour, `plantAnalysis()` internals and the `metadata.json` format must not change.
- OpenCV windows run in a subprocess, never inside the Qt process.
- ArUco guard runs once per batch (`check_aruco_marker`).
- No linter exists; `sed -i` on macOS needs `''`, so use Edit for scripted edits.
- **Commits:** one logical change each. Do **not** add a Claude co-author line (user's global CLAUDE.md overrides the default attribution reminder). The working tree already has uncommitted user edits in `../APP_USAGE_GUIDE.md`, `../CHANGES.md`, `../TODO.md`, `frontend/.../single-plant-analysis.mdx`; stage only files/hunks this plan changes (`git add -p` for those) and never `git add -A`.
- Work on branch `feature/batch-analyze` (already created).

## Review Focus

- A plate with **zero** detected seeds: confirm screen opens empty so the user can add boxes by hand; confirming with zero boxes aborts cleanly (no analysis, no files).
- **Exactly one** detected seed: box width has no neighbour to split with; must not divide by zero or yield a zero-width box.
- Two seeds **merged into one blob**: yields one box; user can add/resize (covered by edit helpers), no crash.
- Seeds very close together or near the image edge: boxes clipped to the image and never inverted/overlapping.
- User **cancels** (`Q`/`Esc`/window close) at the confirm screen or in any origin click: nothing saved, no analysis launched.
- A plant's analysis **raises**: remaining plants still run and the failure is reported at the end.

---

### Task 1: Seed detection and box proposal

**Files:**
- Create: `singlePlantAnalysis/analysis/utils/proposeROIs.py`
- Test: `singlePlantAnalysis/test_batch_rois.py`

**Interfaces:**
- Produces:
  - `detect_seed_centroids(seg_paths: list[str], min_area: int = 30, max_frames: int = 10) -> list[tuple[float, float]]` returns `(x, y)` centroids sorted by x. Uses the first frame containing any class-3 pixels; if none of the first `max_frames` frames qualifies on its own, ORs class-3 pixels from those frames. Blobs under `min_area` px are dropped.
  - `propose_boxes(centroids, seg_paths, image_shape: tuple[int, int], margin: int = 20) -> list[list[int]]` returns one `[y_min, y_max, x_min, x_max]` per centroid, in centroid order.

- [ ] **Step 1: Write failing tests** in `test_batch_rois.py` (plain `unittest`, synthetic masks written with `cv2.imwrite` into a `tempfile.mkdtemp`). Test names and assertions:
  - `test_three_seeds_sorted_left_to_right`: three 8x8 class-3 squares at x=50,150,250 written in shuffled order → centroids x-sorted, length 3.
  - `test_tiny_blob_ignored`: a 2x2 class-3 blob with `min_area=30` → not returned.
  - `test_no_seeds_returns_empty`: all-zero mask → `[]`.
  - `test_seed_found_in_later_frame`: frame 0 empty, frame 1 has a seed → returned.
  - `test_boxes_split_at_midpoints`: seeds at x=100 and x=300 → box 0 `x_max` and box 1 `x_min` both `200`.
  - `test_single_seed_box_nonzero_width_inside_image`: one seed, image 400 wide → `0 <= x_min < x_max <= 400`.
  - `test_boxes_clipped_to_image_and_ordered`: seed at x=5 → `x_min >= 0`; every box has `y_min < y_max`, `x_min < x_max`, and all values inside `image_shape`.
  - `test_box_extends_to_lowest_root_pixel`: class-1 pixels down to y=300 inside seed's band in frame 1 only → `y_max >= 300`, capped at image height.
  - `test_root_of_neighbour_does_not_extend_box`: class-1 pixels at y=380 in the *other* seed's band → this box's `y_max` is unaffected.
  - `test_merged_seeds_give_one_box`: two touching 8x8 squares → one centroid, one box.

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest test_batch_rois -v`
Expected: ImportError / FAIL (module missing).

- [ ] **Step 3: Implement both functions in `proposeROIs.py`.** Pure numpy/cv2, no GUI imports. Use `cv2.connectedComponentsWithStats` for blobs. Box rules: x edges at midpoints between adjacent centroids; outermost edges use half the median spacing (or `image_width // 4` when only one seed), clipped to the image; `y_min = max(0, seed_y - margin)`; `y_max = min(image_h, lowest class-1/2 row within the x band over all `seg_paths` + margin)`, falling back to `image_h` when no root pixels exist.

- [ ] **Step 4: Run tests, expect all PASS**

Run: `python -m unittest test_batch_rois -v`

- [ ] **Step 5: Commit**

```bash
git add singlePlantAnalysis/analysis/utils/proposeROIs.py singlePlantAnalysis/test_batch_rois.py
git commit -m "Propose per-plant ROI boxes from seed-class segmentation"
```

---

### Task 2: Confirm screen and origin collection

**Files:**
- Modify: `singlePlantAnalysis/analysis/utils/getROIandSeed.py` (add after `selectSeed`; do not alter existing functions)
- Create: `singlePlantAnalysis/analysis/utils/boxEdit.py` (pure box-editing helpers, so they are testable without a window)
- Test: `singlePlantAnalysis/test_batch_rois.py`

**Interfaces:**
- Consumes: `propose_boxes` / `detect_seed_centroids` from Task 1; existing `selectSeed(images, segFiles, bbox, conf) -> [x, y] | None`.
- Produces:
  - `boxEdit.hit_test(boxes, x, y, handle: int = 8) -> tuple[int, str] | None` returning `(index, part)` where part is `'body'` or one of `'l','r','t','b'`; topmost/last box wins on overlap.
  - `boxEdit.move_box(box, dx, dy, image_shape) -> list[int]` and `boxEdit.resize_box(box, part, dx, dy, image_shape) -> list[int]`: clamp to the image, enforce min size 20 px, never invert.
  - `boxEdit.renumber(boxes) -> list[list[int]]`: sort by `x_min`.
  - `selectPlantROIs(image, boxes) -> list[list[int]] | None` (None = cancelled): the interactive screen. Keys: click/drag body to move, drag edge to resize, `D` delete selected, `A` then drag to add, `Enter` confirm, `Q`/`Esc`/window close cancel. Shows each box number (left to right) and a key legend. Uses the same scaled-display approach as `selectROI`.
  - `getPlateROIsAndSeeds(conf, images, segFiles) -> list[dict] | None` where each dict is `{'plant': int, 'bounding box': [y0,y1,x0,x1], 'seed': [x, y]}`. Detects, calls `selectPlantROIs` on the last frame, then `selectSeed` for each confirmed box (in order). Returns `None` if the user cancels anywhere or confirms zero boxes.

- [ ] **Step 1: Write failing tests** for `boxEdit` in `test_batch_rois.py`:
  - `test_hit_test_prefers_edge_over_body`, `test_hit_test_none_outside`, `test_hit_test_overlap_picks_last`.
  - `test_move_box_clamped_to_image`, `test_resize_box_enforces_min_size`, `test_resize_box_cannot_invert`.
  - `test_renumber_sorts_by_x`.
  - `test_getPlateROIsAndSeeds_cancel_returns_none` and `test_getPlateROIsAndSeeds_zero_boxes_returns_none`, with `selectPlantROIs` and `selectSeed` patched via `unittest.mock`.
  - `test_getPlateROIsAndSeeds_numbers_plants_left_to_right`: patched `selectPlantROIs` returns two boxes, patched `selectSeed` returns known points → result plants `[1, 2]` with matching boxes/seeds.
  - `test_getPlateROIsAndSeeds_cancel_during_origin_click_returns_none`: second `selectSeed` returns `None`.

- [ ] **Step 2: Run to verify failure** (`python -m unittest test_batch_rois -v`; expect ImportError).

- [ ] **Step 3: Implement `boxEdit.py`** with the signatures above (pure functions, no cv2 window code).

- [ ] **Step 4: Implement `selectPlantROIs` and `getPlateROIsAndSeeds`** in `getROIandSeed.py`. `getPlateROIsAndSeeds` reads the first frame of `segFiles` shape for `image_shape`. Wrap window code in try/finally calling `cv2.destroyAllWindows()`.

- [ ] **Step 5: Run tests, expect PASS.** Then **manual check** on real data: run a throwaway snippet from `singlePlantAnalysis/` calling `getPlateROIsAndSeeds` on a plate that has `Segmentation/Ensemble`; confirm boxes appear, can be moved/resized/deleted/added, origins can be clicked, and the returned seed `y` is relative to the box (a click at a box's top edge gives `y≈0`).

- [ ] **Step 6: Commit**

```bash
git add singlePlantAnalysis/analysis/utils/boxEdit.py singlePlantAnalysis/analysis/utils/getROIandSeed.py singlePlantAnalysis/test_batch_rois.py
git commit -m "Add plate-level ROI confirm screen with manual root origin per plant"
```

---

### Task 3: Shared config prep and `batch_setup.py`

**Files:**
- Create: `singlePlantAnalysis/analysis/utils/configPrep.py`
- Create: `singlePlantAnalysis/batch_setup.py`
- Modify: `singlePlantAnalysis/1_analysis.py` (replace its inline config-prep lines with a call to the helper; behaviour unchanged)
- Test: `singlePlantAnalysis/test_batch_rois.py`

**Interfaces:**
- Produces:
  - `configPrep.prepare_conf(conf: dict) -> dict`: performs exactly what `1_analysis.py` does between `conf = json.load(...)` and the ArUco debug block: `fileKey`/`Experiment` fallback to `identifierField`, `sequenceLabel`, `Plant = 'Arabidopsis thaliana'`, `pixel_size` for manual calibration. Mutates and returns `conf`.
  - `batch_setup.py --config <project_config.json>`: loads conf, `prepare_conf`, `getImages`, `getPlateROIsAndSeeds`; exits 0 without analysing on `None`. Otherwise writes `batch_plants.json` (list of `{'plant','bounding box','seed'}`) into `conf['MainFolder']`, then for each entry runs `plantAnalysis(dict(conf, plant=str(p['plant']), **{'bounding box': ..., 'seed': ...}), True)` inside try/except, collects failures and prints a summary (`Batch finished: N succeeded, M failed (plants ...)`). Expose the loop as `run_batch(conf, plants, analyse=plantAnalysis) -> list[int]` returning failed plant numbers (testable with a stub `analyse`).

- [ ] **Step 1: Write failing tests:**
  - `test_prepare_conf_manual_calibration_sets_pixel_size` (`knownDistance=15`, `pixelDistance=300` → `0.05`).
  - `test_prepare_conf_sequence_label` (`Experiment='E'`, `Images='/x'`, `plant=2` → `'E_/x_2'`).
  - `test_prepare_conf_identifier_fallback` (no `Experiment` → uses `identifierField`).
  - `test_run_batch_runs_every_plant_with_its_own_box_and_seed` (stub records `conf['plant']`, `['bounding box']`, `['seed']`, and `replicate is True`).
  - `test_run_batch_continues_after_failure` (stub raises for plant 2; plants 1 and 3 still called; returns `[2]`).
  - `test_run_batch_does_not_mutate_shared_conf` (second plant doesn't see first's `bounding box`).

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `configPrep.py`, then edit `1_analysis.py`** to call `prepare_conf(conf)` in place of the inline block, keeping the `--restart`/`--rerun` logic and ArUco debug printing as they are.

- [ ] **Step 4: Implement `batch_setup.py`** per the interface above.

- [ ] **Step 5: Run tests, expect PASS.** Also run `python 1_analysis.py --help` to confirm the edited script still imports.

- [ ] **Step 6: Commit** (two commits, one per logical change):

```bash
git add singlePlantAnalysis/analysis/utils/configPrep.py singlePlantAnalysis/1_analysis.py singlePlantAnalysis/test_batch_rois.py
git commit -m "Move analysis config prep into a shared helper"
git add singlePlantAnalysis/batch_setup.py singlePlantAnalysis/test_batch_rois.py
git commit -m "Add batch_setup: confirm plate ROIs, then analyse each plant"
```
(Split the test file hunks with `git add -p` so each commit contains only its own tests.)

---

### Task 4: GUI button and shared validation

**Files:**
- Modify: `singlePlantAnalysis/run.py` (`analysis()` at ~673, button block at ~1134, translations at ~1818 and tooltip at ~1868)
- Test: `singlePlantAnalysis/test_aruco_guard.py` (extend, following its headless-Qt pattern) or `test_batch_rois.py`

**Interfaces:**
- Produces:
  - `run.py` method `validate_analysis_inputs(self) -> list[str] | None`: all checks currently in `analysis()` (video folder, images, segmentation files, manual calibration, ArUco guard); shows the same message boxes; returns the image list on success or `None` on failure.
  - `analysis()` becomes: `images = self.validate_analysis_inputs()`; return if `None`; then `saveFieldsIntoJson()` and launch as before (behaviour identical).
  - `batch_analysis(self)`: same validation, `saveFieldsIntoJson()`, then `subprocess.Popen([sys.executable, "batch_setup.py", "--config", <project_config.json>])`.
  - `self.batchAnalysisButton` (`QPushButton`, objectName `batchAnalysisButton`, label "Batch Analyze", tooltip says it proposes ROIs for all plants and still asks for each root origin).

- [ ] **Step 1: Write failing tests** (offscreen Qt, `HOME` temp, patch `run.GLOBAL_CONFIG_FILE`, `subprocess.Popen` mocked):
  - `test_batch_button_exists_and_is_visible_clickable` (inside Tab 1 geometry, not overlapping another button's rect).
  - `test_batch_blocked_without_video_folder`: Popen not called.
  - `test_batch_blocked_when_aruco_check_fails`: patch `check_aruco_marker` → False; Popen not called.
  - `test_batch_launches_batch_setup_when_valid`: Popen called once with `batch_setup.py` and the project config path.
  - `test_analyze_plant_still_launches_1_analysis`: regression for the refactor.
  - Existing `test_aruco_guard` tests must still pass.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Refactor `analysis()`** into `validate_analysis_inputs()` + launch without changing messages or order. **Add the button** in the Tab 1 block; the right column (x=660) currently holds buttons at y=0,100,200,300,400… so choose a free slot (check the window is 810x680 and nothing sits under divider `QFrame`s; `raise_()` the button if needed) and add the label/tooltip next to the existing `analysisButton` translation/tooltip lines.

- [ ] **Step 4: Run all tests**

Run: `python -m unittest test_aruco_guard test_batch_rois -v`
Expected: PASS.

- [ ] **Step 5: Visual check:** launch `python run.py` and confirm the button is visible, clickable (not covered by a divider), and that clicking it with no video folder shows the error box.

- [ ] **Step 6: Commit** (refactor first, then feature):

```bash
git add singlePlantAnalysis/run.py singlePlantAnalysis/test_aruco_guard.py
git commit -m "Factor input validation out of analysis() so batch can share it"
git add singlePlantAnalysis/run.py singlePlantAnalysis/test_batch_rois.py
git commit -m "Add Batch Analyze button"
```
(Use `git add -p` to separate the refactor hunks from the button hunks.)

---

### Task 5: End-to-end check and docs

**Files:**
- Modify: `CHANGES.md` (repo `image-analysis-pipeline/`), `APP_USAGE_GUIDE.md`, `frontend/src/content/docs/docs/single-plant-analysis.mdx`, `CLAUDE.md` (architecture note + test commands)
- These files have **pre-existing uncommitted user edits** (all but `CLAUDE.md`): add only your own hunks with `git add -p`.

- [ ] **Step 1: End-to-end run on a real plate** with ≥2 plants (e.g. one under `experiment_*/plate*`): click Batch Analyze, confirm/edit boxes, click origins, and verify each plant produces `Results_raw.csv` in its result folder and `batch_plants.json` exists in the project folder. Compare one plant's `Results_raw.csv` to a single-plant "Analyze Plant" run with the same box/origin (should match).

- [ ] **Step 2: Run the whole test set**

Run: `python -m unittest test_aruco_guard test_batch_rois -v`
Expected: all PASS. Also run `python -m unittest test_report_filter` equivalent is pytest-style: skip unless pytest is available.

- [ ] **Step 3: Docs.** Add a dated `CHANGES.md` entry (feature, not a bug fix, but note which files). Document the button, the confirm-screen keys and the "origin is always manual" rule in `APP_USAGE_GUIDE.md` and the site's `single-plant-analysis.mdx` (the site summarises the root docs, update both). In `CLAUDE.md` add a short Architecture bullet for `batch_setup.py` / `proposeROIs.py` and the `test_batch_rois` command.

- [ ] **Step 4: Commit**

```bash
git add -p CHANGES.md APP_USAGE_GUIDE.md frontend/src/content/docs/docs/single-plant-analysis.mdx
git add CLAUDE.md
git commit -m "Document Batch Analyze"
```

---

## Self-review

- **Spec coverage:** detection (T1), midpoint/lowest-root boxes (T1), confirm screen with move/resize/delete/add (T2), manual origin per box (T2), `batch_setup.py` + `batch_plants.json` + sequential replicate runs (T3), shared config helper (T3), button + shared validation + ArUco guard once (T4), tests (T1–T4), docs (T5). Seed-coordinate question in the spec is resolved: crop-relative.
- **Types:** `getPlateROIsAndSeeds` returns dicts consumed unchanged by `run_batch` (`plant`, `bounding box`, `seed`); `propose_boxes` returns `[y_min, y_max, x_min, x_max]` matching `bbox` use in `selectSeed`.
- **Proportion:** steps give signatures, names and spec values; bodies left to the implementer.
