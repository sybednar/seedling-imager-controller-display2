---
layout: default
title: Changelog
---

# Changelog

Dated log of fixes applied to the analysis pipeline
(`singlePlantAnalysis/analysis/`). This page mirrors `CHANGES.md`. Keep
them in sync, or replace this content with an `include` of the real file.

## 2026-09-03: `analysis/imageUtils/seg.py`

**Hypocotyl component selection no longer borrows a neighbor's blob.**
Added a hard horizontal-distance gate (`max_horizontal_distance=80`) to
hypocotyl anchor selection. Previously, if a plant had no hypocotyl blob yet,
the nearest *available* component (even a distant neighbor's) was accepted
regardless of distance. Horizontal-only distance was chosen over Euclidean
because plants are plated in a row and a hypocotyl grows vertically: `80` is
half the ~170px minimum seed spacing, minus a margin for blob width.

## 2026-08-24: Environment Pinning, `3_generateReport.py`

**Report generation no longer crashes on fresh installs.** An unpinned
transitive dependency (`multimethod`) shipped a change that broke
`scikit-fda`'s operator registration with a metaclass-conflict error at
import time, taking down report generation entirely, even for configs with
FPCA disabled. Fixed by pinning `multimethod<2.0.2` and making the FPCA
import lazy and failure-tolerant.

## 2026-08-19: `analysis/dataWork.py`

**Growth charts respect the real capture interval.** The hourly
reconciliation formula assumed a fixed 15-minute interval; generalized to
`(N_exp - 1) * timeStep // 60 + 1`.

**Fixed a `medfilt` zero-padding artifact.** `scipy.signal.medfilt` implicitly
zero-pads past the array boundary, flattening the last few points of every
growth curve. Replaced with a centered rolling median that shrinks its
window near the edges instead of padding with fabricated data.

## 2026-08-19: `analysis/plantAnalysis.py`, `analysis/graphUtils/save.py`

**`HypocotylLength` no longer zeroed before root detection.** Hypocotyl
length is computed independently of root graph success, but every
early-return path in the "find first valid root structure" loop hardcoded
`saveProps(..., 0, 0)`, discarding the already-computed value. The real value
now survives all four early-return paths.

## 2026-08-19: `analysis/imageUtils/seg.py`

**Hypocotyl selection anchored on seed position instead of largest blob.**
Component selection previously picked whichever class-4 blob had the largest
pixel area, with no awareness of which plant it belonged to: a diagonally
grown root could widen the ROI enough to catch a neighbor's larger hypocotyl.
Selection now scores candidates by proximity to `fixed_seed_position`,
mirroring the pattern already used for root component selection.

## 2026-06-12: Path Structure Across `fileUtilities.py`, `run.py`, `2_postprocess.py`, `3_generateReport.py`

**Dropped a hardcoded multi-Raspberry-Pi path segment** that didn't match
the pipeline's actual single-rig capture setup. Output paths are now
`Analysis/{experiment}/{cam}/{plant}/...` instead of carrying an extra `rpi`
level.

**Missing ArUco marker on a plate's reference frame no longer blocks the
whole plate.** Alignment failure on the reference frame now falls back to
copying raw images through unaligned, so segmentation can still proceed;
the segmentation queue UI gained `Not Aligned` / `Partially Aligned` states.

## 2026-05-19: Image Discovery

**`.tif` / `.tiff` experiments are no longer silently dropped.** Image
discovery was hardcoded to `*.png` only. Added `loadImageFiles()`, which
globs `.png`, `.tif`, and `.tiff` together.

## 2026-04-16: `singlePlantAnalysis/run.py`

**Blank plate/camera/plant/experiment fields no longer corrupt output
paths.** Fields default to `"1"` when blank, with `editingFinished` handlers
so a blank field self-corrects as soon as focus leaves it.

---

## Still Open

- `prune()`'s skeleton erosion has no length-awareness: a structure shorter
  than roughly `2 x num_it` can be fully consumed before it regrows.
- The "remove spurious lateral roots at the beginning" logic in
  `dataWork.py` isn't actually scoped to the beginning; it runs across the
  entire sequence.
- `PostProcess_Hour.csv` has `NaN` in 2 of every 3 hourly rows whenever the
  capture interval doesn't divide 60 minutes evenly.
