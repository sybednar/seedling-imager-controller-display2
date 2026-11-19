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


def propose_component_boxes_info(seg_path, min_seed_area=30, margin=20):
    """Return (boxes, n_seeds): boxes ordered like boxEdit.renumber, and the
    number of qualifying seeds found (n_seeds > len(boxes) means plants merged)."""
    mask = cv2.imread(seg_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return [], 0
    h, w = mask.shape[:2]
    plant = np.isin(mask, PLANT_CLASSES).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(plant, connectivity=8)

    seeds = (mask == SEED_CLASS).astype(np.uint8)
    n, seed_labels, seed_stats, _ = cv2.connectedComponentsWithStats(seeds, connectivity=8)
    comps = []
    n_seeds = 0
    for i in range(1, n):
        if seed_stats[i, cv2.CC_STAT_AREA] < min_seed_area:
            continue
        n_seeds += 1
        ys, xs = np.nonzero(seed_labels == i)
        lab = int(labels[ys[0], xs[0]])
        if lab not in comps:
            comps.append(lab)

    boxes = []
    for lab in comps:
        x = int(stats[lab, cv2.CC_STAT_LEFT])
        y = int(stats[lab, cv2.CC_STAT_TOP])
        bw = int(stats[lab, cv2.CC_STAT_WIDTH])
        bh = int(stats[lab, cv2.CC_STAT_HEIGHT])
        boxes.append([max(0, y - margin), min(h, y + bh + margin),
                      max(0, x - margin), min(w, x + bw + margin)])
    return boxEdit.renumber(boxes), n_seeds


def propose_component_boxes(seg_path, min_seed_area=30, margin=20):
    """Boxes only; see propose_component_boxes_info."""
    return propose_component_boxes_info(seg_path, min_seed_area, margin)[0]
