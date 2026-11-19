"""Propose per-plant ROI boxes from seed-class segmentation masks.

Pure numpy/cv2 (no GUI imports). Boxes are [y_min, y_max, x_min, x_max].
Segmentation class values: 1=main root, 2=lateral root, 3=seed.
"""
import cv2
import numpy as np

from analysis.utils.boxEdit import MIN_SIZE

SEED_CLASS = 3
ROOT_CLASSES = (1, 2)
# Hypocotyl, leaf, petiole: shoot structures that grow up from the seed.
SHOOT_CLASSES = (4, 5, 6)


def _read_mask(path):
    return cv2.imread(path, cv2.IMREAD_GRAYSCALE)


def detect_seed_centroids(seg_paths, min_area=30, max_frames=10):
    """Return (x, y) seed centroids sorted by x.

    Scans only the first ``max_frames`` frames and uses the first one that has
    at least one class-3 blob of area >= ``min_area``; returns [] if none does.
    """
    for path in list(seg_paths)[:max_frames]:
        mask = _read_mask(path)
        if mask is None:
            continue
        binary = (mask == SEED_CLASS).astype(np.uint8)
        n, _, stats, cents = cv2.connectedComponentsWithStats(binary, connectivity=8)
        found = [(float(cents[i][0]), float(cents[i][1]))
                 for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area]
        if found:
            return sorted(found, key=lambda c: c[0])
    return []


def _x_edges(xs, width):
    """Left/right x edge per centroid: midpoints between neighbours, half the
    median spacing (width // 4 for a single seed) on the outside."""
    n = len(xs)
    half = width // 4 if n == 1 else float(np.median(np.diff(xs))) / 2.0
    edges = []
    for i, x in enumerate(xs):
        left = x - half if i == 0 else (xs[i - 1] + x) / 2.0
        right = x + half if i == n - 1 else (x + xs[i + 1]) / 2.0
        edges.append((left, right))
    return edges


def _merge_close(centroids, min_gap=MIN_SIZE):
    """Collapse centroids (sorted by x) closer than ``min_gap`` px in x into
    one at their mean, so a split seed never yields a degenerate box."""
    groups = []
    for c in sorted(centroids, key=lambda c: c[0]):
        if groups and c[0] - groups[-1][-1][0] < min_gap:
            groups[-1].append(c)
        else:
            groups.append([c])
    return [(float(np.mean([g[0] for g in grp])), float(np.mean([g[1] for g in grp])))
            for grp in groups]


def _span(lo, hi, limit, min_size=MIN_SIZE):
    """Widen [lo, hi) to at least min_size inside [0, limit]."""
    if hi - lo < min_size:
        hi = min(limit, lo + min_size)
        lo = max(0, hi - min_size)
    return lo, hi


def propose_boxes(centroids, seg_paths, image_shape, margin=20):
    """One [y_min, y_max, x_min, x_max] per (merged) centroid, left to right.

    Centroids closer than boxEdit.MIN_SIZE in x are merged, and every box is
    at least MIN_SIZE wide and tall.
    """
    h, w = int(image_shape[0]), int(image_shape[1])
    if not centroids:
        return []
    centroids = _merge_close(centroids)
    xs = [c[0] for c in centroids]
    bounds = []
    for left, right in _x_edges(xs, w):
        x0 = int(np.clip(np.floor(left + 0.5), 0, w - 1))
        x1 = int(np.clip(np.floor(right + 0.5), x0 + 1, w))
        bounds.append(_span(x0, x1, w))

    lowest = [-1] * len(bounds)
    topmost = [h] * len(bounds)
    for path in seg_paths:
        mask = _read_mask(path)
        if mask is None:
            continue
        root = np.isin(mask, ROOT_CLASSES)
        for i, (x0, x1) in enumerate(bounds):
            rows = np.flatnonzero(root[:, x0:x1].any(axis=1))
            if rows.size:
                lowest[i] = max(lowest[i], int(rows[-1]))
        shoot = np.isin(mask, SHOOT_CLASSES)
        for i, (x0, x1) in enumerate(bounds):
            rows = np.flatnonzero(shoot[:, x0:x1].any(axis=1))
            if rows.size:
                topmost[i] = min(topmost[i], int(rows[0]))

    boxes = []
    for (cx, cy), (x0, x1), low, top in zip(centroids, bounds, lowest, topmost):
        # The hypocotyl grows up from the seed, so start above its topmost
        # pixel; never start lower than the seed margin.
        y0 = max(0, min(top, int(cy)) - margin)
        # Root pixels at or above the seed row mean no root below the seed yet.
        y1 = h if low <= cy else min(h, low + margin)
        y0, y1 = _span(y0, y1, h)
        boxes.append([y0, y1, x0, x1])
    return boxes
