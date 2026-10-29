---
layout: default
title: Architecture Notes
---

# Architecture Notes

Things worth knowing before changing the analysis pipeline.

## `fixed_seed_position` vs. `current_root_base`

Both start as copies of the same manually-configured seed position.

- **`fixed_seed_position`** never changes for the rest of analysis.
- **`current_root_base`** gets reassigned every successfully-tracked frame,
  so it can drift over time.

Root component selection anchors on `current_root_base` (it should track
legitimate drift). Hypocotyl selection anchors on `fixed_seed_position`, so
it stays independent of any root-tracking mistakes and consistent
frame-to-frame.

## Main / Lateral Classification Is Topology-Based, Not Per-Pixel

`graphInit()` marks the longest weighted path from the seed as `root_type=10`
(main); everything else defaults to lateral. The skeleton is built from a
merged binary mask (classes 1+2 combined) before any per-pixel class
matters, so per-pixel main/lateral mislabeling in the segmentation mask
does **not** corrupt `MainRootLength` / `LateralRootsLength`. It only affects
the `SegMulti` visualization coloring used for human QC.

## `SegMulti` Images Are Visualizations, Not Raw Masks

BGR color key:

| Class | Color (BGR) | Grayscale value |
|---|---|---|
| Main root | `(0,0,255)` red | 76 |
| Lateral root | `(0,255,0)` green | 150 |
| Hypocotyl | `(0,255,255)` yellow | 179 |
| FTip marker | `(255,255,0)` cyan | 226 |

The real multi-class mask (pixel values 0&ndash;7) lives at the path in each
plant's `metadata.json` under the `SegPath` key, e.g.
`<video>/Segmentation/Ensemble/`.

## Class Labels (`dataset.json`)

```
0 = background
1 = main root
2 = lateral root
3 = seed
4 = hypocotyl   (spelled "hypocotil": typo, preserved for compatibility)
5 = leaf
6 = petiole
7 = ignore
```

## Case Naming

The live dataset and `corrected_to_nnunet_cases.py` /
`CreateArabidopsisDataset.ipynb` use `image_N`, not `CaseN`. If you see
`CaseN` anywhere, it's stale; reconcile it.

## What's Different from Upstream ChronoRoot2

- `chronoRootApp` (upstream name) was renamed to `singlePlantAnalysis` here.
- `imageAligner` exists only in this fork, not upstream.
- Upstream has a `chronoRootScreeningApp`; this fork does not.
