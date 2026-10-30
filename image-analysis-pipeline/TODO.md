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
