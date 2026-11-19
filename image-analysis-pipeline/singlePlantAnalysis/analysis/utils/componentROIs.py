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


def propose_component_boxes_detail(seg_path, min_seed_area=30, margin=20):
    """Propose boxes and report how they were formed.

    Returns a dict: ``boxes`` (ordered like boxEdit.renumber), ``n_seed_blobs``
    (qualifying class-3 blobs), ``n_components_with_seed`` (plant components that
    contain a seed, fragments included), ``n_merged_components`` (components with
    more than one seed blob: touching plants or one split seed) and
    ``n_skipped_fragments`` (seed components whose bounding box, before the
    margin, is under boxEdit.MIN_SIZE in both dimensions, i.e. a seed piece cut
    off from its plant; they get no box).
    """
    out = {'boxes': [], 'n_seed_blobs': 0, 'n_components_with_seed': 0,
           'n_merged_components': 0, 'n_skipped_fragments': 0}
    mask = cv2.imread(seg_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return out
    h, w = mask.shape[:2]
    plant = np.isin(mask, PLANT_CLASSES).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(plant, connectivity=8)

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

    out['n_components_with_seed'] = len(blobs_per_comp)
    out['n_merged_components'] = sum(1 for c in blobs_per_comp.values() if c > 1)
    boxes = []
    for lab in blobs_per_comp:
        x = int(stats[lab, cv2.CC_STAT_LEFT])
        y = int(stats[lab, cv2.CC_STAT_TOP])
        bw = int(stats[lab, cv2.CC_STAT_WIDTH])
        bh = int(stats[lab, cv2.CC_STAT_HEIGHT])
        if bw < boxEdit.MIN_SIZE and bh < boxEdit.MIN_SIZE:
            out['n_skipped_fragments'] += 1
            continue
        boxes.append([max(0, y - margin), min(h, y + bh + margin),
                      max(0, x - margin), min(w, x + bw + margin)])
    out['boxes'] = boxEdit.renumber(boxes)
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
    a proposal; None when no boxes were proposed. Merging is only mentioned when
    some box holds several seed blobs, which may be touching plants or one split seed."""
    n = len(detail['boxes'])
    if n == 0:
        return None
    lines = ["Auto-proposed %d box%s" % (n, "" if n == 1 else "es")]
    if detail['n_merged_components'] > 0:
        lines.append("Several seed blobs share a box (%d): touching plants" % detail['n_merged_components'])
        lines.append("or a split seed - check them")
    k = detail['n_skipped_fragments']
    if k > 0:
        lines.append("%d seed fragment%s skipped (no plant attached)" % (k, "" if k == 1 else "s"))
    return "\n".join(lines)
