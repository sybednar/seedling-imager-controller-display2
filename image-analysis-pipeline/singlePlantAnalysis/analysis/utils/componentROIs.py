"""Propose per-plant ROI boxes from the last frame's segmentation mask.

Pure numpy/cv2 (no GUI imports). Boxes are [y_min, y_max, x_min, x_max].
Segmentation classes: 1=main root, 2=lateral root, 3=seed, 4=hypocotyl,
5=leaf, 6=petiole; 0=background and 7=ignore are not part of a plant.

Each seed (class-3 blob) is a starting point: the box is the bounding box
(leftmost, rightmost, topmost, bottommost pixel) of the plant-mask connected
component containing it, plus a margin. Touching plants form one component
and therefore get one box.
"""
import cv2
import numpy as np

from analysis.utils import boxEdit

SEED_CLASS = 3
PLANT_CLASSES = (1, 2, 3, 4, 5, 6)


def propose_component_boxes_detail(seg, min_seed_area=30, margin=20,
                                   min_attach_area=200, max_attach_distance=300):
    """Propose boxes and report how they were formed.

    Seeds are often tiny blobs detached from their roots, so non-seeded plant
    components of area >= ``min_attach_area`` are attached to the nearest seeded
    component (smallest pixel-to-pixel gap, ties to the lower label) when that
    gap is <= ``max_attach_distance`` px. A seeded component's box is the bounding
    box of itself plus everything attached, plus ``margin``, clipped.

    Returns a dict: ``boxes`` (ordered like boxEdit.renumber), ``n_seed_blobs``
    (qualifying class-3 blobs), ``n_components_with_seed``, ``n_merged_components``
    (components holding more than one seed blob: touching plants or a split seed),
    ``n_attached`` (components attached to a seeded one), ``n_unattached`` (large
    components farther than ``max_attach_distance`` from every seed) and
    ``n_specks_ignored`` (components under ``min_attach_area``).

    ``seg`` is a path or an already-read grayscale mask array.
    """
    out = {'boxes': [], 'n_seed_blobs': 0, 'n_components_with_seed': 0,
           'n_merged_components': 0, 'n_attached': 0, 'n_unattached': 0,
           'n_specks_ignored': 0}
    mask = cv2.imread(seg, cv2.IMREAD_GRAYSCALE) if isinstance(seg, str) else seg
    if mask is None:
        return out
    h, w = mask.shape[:2]
    plant = np.isin(mask, PLANT_CLASSES).astype(np.uint8)
    n_lab, labels, stats, _ = cv2.connectedComponentsWithStats(plant, connectivity=8)

    seeds = (mask == SEED_CLASS).astype(np.uint8)
    n, seed_labels, seed_stats, _ = cv2.connectedComponentsWithStats(seeds, connectivity=8)
    blobs_per_comp = {}
    for i in range(1, n):
        if seed_stats[i, cv2.CC_STAT_AREA] < min_seed_area:
            continue
        out['n_seed_blobs'] += 1
        ys, xs = np.nonzero(seed_labels == i)
        lab = int(labels[ys[0], xs[0]])
        blobs_per_comp[lab] = blobs_per_comp.get(lab, 0) + 1
    seeded = sorted(blobs_per_comp)
    out['n_components_with_seed'] = len(seeded)
    out['n_merged_components'] = sum(1 for c in blobs_per_comp.values() if c > 1)

    def bbox(lab):
        x = int(stats[lab, cv2.CC_STAT_LEFT]); y = int(stats[lab, cv2.CC_STAT_TOP])
        return [y, y + int(stats[lab, cv2.CC_STAT_HEIGHT]),
                x, x + int(stats[lab, cv2.CC_STAT_WIDTH])]

    extent = {lab: bbox(lab) for lab in seeded}
    candidates = [c for c in range(1, n_lab) if c not in blobs_per_comp]
    big = [c for c in candidates if stats[c, cv2.CC_STAT_AREA] >= min_attach_area]
    out['n_specks_ignored'] = len(candidates) - len(big)

    best = {c: (None, None) for c in big}      # candidate -> (gap, seeded label)
    d = int(np.ceil(max_attach_distance)) + 1
    for lab in seeded:
        y0, y1, x0, x1 = extent[lab]
        cy0, cy1 = max(0, y0 - d), min(h, y1 + d)
        cx0, cx1 = max(0, x0 - d), min(w, x1 + d)
        crop = labels[cy0:cy1, cx0:cx1]
        # Distance of every crop pixel to this seeded component. Pixels outside
        # the crop are farther than max_attach_distance, so nothing is missed.
        dist = cv2.distanceTransform((crop != lab).astype(np.uint8), cv2.DIST_L2,
                                     cv2.DIST_MASK_PRECISE)
        for c in big:
            cy, cy2, cx, cx2 = bbox(c)
            if cy2 <= cy0 or cy >= cy1 or cx2 <= cx0 or cx >= cx1:
                continue
            # Only look inside the candidate's bbox (clipped to the crop).
            ry0, ry1 = max(cy, cy0) - cy0, min(cy2, cy1) - cy0
            rx0, rx1 = max(cx, cx0) - cx0, min(cx2, cx1) - cx0
            sel = crop[ry0:ry1, rx0:rx1] == c
            if not sel.any():
                continue
            gap = float(dist[ry0:ry1, rx0:rx1][sel].min())
            if gap > max_attach_distance:
                continue
            if best[c][0] is None or gap < best[c][0]:     # strict: ties keep lower label
                best[c] = (gap, lab)
    for c in big:
        gap, lab = best[c]
        if lab is None:
            out['n_unattached'] += 1
            continue
        out['n_attached'] += 1
        e, b = extent[lab], bbox(c)
        extent[lab] = [min(e[0], b[0]), max(e[1], b[1]), min(e[2], b[2]), max(e[3], b[3])]

    boxes = [[max(0, e[0] - margin), min(h, e[1] + margin),
              max(0, e[2] - margin), min(w, e[3] + margin)] for e in extent.values()]
    out['boxes'] = boxEdit.renumber(boxes, h)
    return out


def propose_component_boxes_info(seg_path, min_seed_area=30, margin=20):
    """Return (boxes, n_seeds) where n_seeds counts seed blobs (not plants)."""
    d = propose_component_boxes_detail(seg_path, min_seed_area, margin)
    return d['boxes'], d['n_seed_blobs']


def propose_component_boxes(seg_path, min_seed_area=30, margin=20):
    """Boxes only; see propose_component_boxes_detail."""
    return propose_component_boxes_detail(seg_path, min_seed_area, margin)['boxes']


def proposal_notice(detail):
    """Short on-screen text (lines of <= 60 chars joined by newlines) describing
    a proposal; None when no boxes were proposed. Warnings appear only when they
    apply: boxes holding several seed blobs (touching plants or one split seed),
    roots/shoots attached to seeds, and pieces left out for size or distance."""
    n = len(detail['boxes'])
    if n == 0:
        return None
    lines = ["Auto-proposed %d box%s" % (n, "" if n == 1 else "es")]
    if detail['n_attached'] > 0:
        lines.append("%d roots/shoots attached to seeds" % detail['n_attached'])
    if detail['n_merged_components'] > 0:
        lines.append("Several seed blobs share a box (%d): touching plants" % detail['n_merged_components'])
        lines.append("or a split seed - check them")
    k = detail['n_unattached']
    if k > 0:
        lines.append("%d roots/shoots too far from any seed were left out" % k)
    return "\n".join(lines)
