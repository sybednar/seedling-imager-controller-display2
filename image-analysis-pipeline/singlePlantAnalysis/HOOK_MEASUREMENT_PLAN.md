# Apical Hook Angle: Measurement Plan

Status: **plan only, nothing implemented yet.**

Convention: 180° = closed hook, 0° = fully open. Geometric methods only, no model retraining.
Standard definition (confirm against the lab protocol): angle between the hypocotyl axis below the hook and the apex/cotyledon direction.

## Why the union mask

The class boundary between hypocotyl (4) and cotyledon (5/6) segmentations is sometimes wrong. Both methods therefore work on the **union of classes 4+5+6**, so a shifted boundary does not change the measurement.

## Shared preprocessing

1. Union mask = classes 4, 5, 6. Light close/open with a small kernel (a large close fuses the stem and folded cotyledons), drop blobs < 30 px².
2. Keep the component nearest the seed x-position and merge nearby parts. Reuse the logic in `extract_hypocotyl_length()` (`analysis/imageUtils/seg.py`).
3. Distance transform on the union. Define all windows as multiples of the median local width, so the method is scale-free (pixel size is only resolved later, in `2_postprocess.py`).
4. Invalid or failed frames return **NaN, never 0**, because 0° means fully open.

## Method 1: single-tube centerline (closed or partly open hook, no junction)

1. Base = mask pixel nearest the seed. Apex = geodesically farthest pixel.
2. Centerline = minimum-cost path base to apex (`skimage.graph.route_through_array`, cost ≈ 1 / distance transform). Resample to even arc length and smooth (spline or Savitzky-Golay). No `prune()`.
3. Apex direction = unit vector over the last window `w_a`, pointing toward the apex.
4. Reference direction = stem tangent over window `w_h`, taken at distance `L_hook` below the apex. This is a local tangent, so a curved hypocotyl does not matter.
5. θ = arccos(t_ref · t_apex), clipped to [0°, 180°] (`angle_between` in `analysis/utils/report_utils.py`). Optional sign from the 2D cross product.

Tunables: `L_hook` (hardest), `w_a`, `w_h`, smoothing strength.
Fails when: the two arms of a tight hook touch (path shortcut across the gap), or the hypocotyl is very short (first frames).

## Method 2: Y-junction (cotyledons open)

Method 1 breaks here: the farthest point is the tip of one cotyledon, and which one can flip between frames.

1. Skeletonize the union and build a graph (`skeleton_nodes` in `seg.py`; networkx pattern in `analysis/graphUtils/graphTrack.py`).
2. Drop short branches by a length threshold relative to local width. Do not use `prune()` (tip-erosion bug, see `TODO.md`).
3. Valid Y = a branch point with two arms above it, each longer than about 2 widths.
4. Reference direction = stem tangent over `w_h` just below the junction. The junction replaces `L_hook`.
5. Apex direction = unit vector from the junction to the midpoint of the two arm tips (or the mean of the two arms' initial directions over `w_a`).
6. θ as in Method 1.

Bonus metric: angle between the two arms (cotyledon opening angle).
Fails when: one cotyledon hides the other (side view), or an arm is mislabeled or truncated so the Y disappears.

## Mode switching and QC

- Use Method 2 when a valid Y exists, otherwise Method 1. When the arms first separate, their bisector is close to the tube's end tangent, so the transition should be roughly continuous.
- Hysteresis: require several consecutive frames before switching mode. Save the mode as a per-frame column.
- Reject frame-to-frame jumps larger than X° (tune on data). Then apply a rolling median in `dataWork.py`.
- In `dataWork.py` skip the monotonic non-decreasing step (lines ~194-196) and the `pixel_size` multiplication, since neither applies to an angle.
- Save centerline coordinates per frame so parameters can be retuned without rerunning segmentation.

## Integration points

- `analysis/imageUtils/seg.py`: new function near `extract_hypocotyl_length()` (~line 121), called before the mask is reduced to classes 1/2 (~line 127).
- `analysis/plantAnalysis.py` and `analysis/graphUtils/save.py`: thread the value like `hypocotyl_length` (header, normal row, failed-graph row, `saveProps`).
- `analysis/dataWork.py`: add the column if missing (backward compatibility, as for `HypocotylLength`).
- `analysis/imageUtils/plot.py`: draw both direction vectors for visual QC.
- `3_generateReport.py` (`temporal_parameters`), `analysis/report.py` (second axis, aggregation, `metrics`).
- Docs: `CHANGES.md`, `APP_USAGE_GUIDE.md`, `frontend/src/content/docs/docs/single-plant-analysis.mdx`.

## Validation

- Compare against manual angles on ~20 frames across hook stages.
- Use corrected-label cases (see `segmentationApp/TRAINING.md`) to compare angles from corrected labels, model predictions, and the union, to separate boundary error from geometry error.
- Check A vs B agreement where both apply, and that old Results CSVs without the new column still process.

## Open questions

- Etiolated (dark/IR) or light-grown imaging?
- Side view or angled view? Are both cotyledons usually visible?
- Exact angle definition in the lab's protocol.
- Do corrected-label cases cover several hook stages, or mostly late frames?
