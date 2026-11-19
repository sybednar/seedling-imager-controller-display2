"""Propose per-plant ROI boxes from seed-class segmentation masks.

Pure numpy/cv2 (no GUI imports). Boxes are [y_min, y_max, x_min, x_max].
Segmentation class values: 1=main root, 2=lateral root, 3=seed.
"""
import cv2
import numpy as np

SEED_CLASS = 3
ROOT_CLASSES = (1, 2)


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


def propose_boxes(centroids, seg_paths, image_shape, margin=20):
    """One [y_min, y_max, x_min, x_max] per centroid, in centroid order."""
    h, w = int(image_shape[0]), int(image_shape[1])
    if not centroids:
        return []
    xs = [c[0] for c in centroids]
    bounds = []
    for left, right in _x_edges(xs, w):
        x0 = int(np.clip(np.floor(left + 0.5), 0, w - 1))
        x1 = int(np.clip(np.floor(right + 0.5), x0 + 1, w))
        bounds.append((x0, x1))

    lowest = [-1] * len(bounds)
    for path in seg_paths:
        mask = _read_mask(path)
        if mask is None:
            continue
        root = np.isin(mask, ROOT_CLASSES)
        for i, (x0, x1) in enumerate(bounds):
            rows = np.flatnonzero(root[:, x0:x1].any(axis=1))
            if rows.size:
                lowest[i] = max(lowest[i], int(rows[-1]))

    boxes = []
    for (cx, cy), (x0, x1), low in zip(centroids, bounds, lowest):
        y0 = max(0, int(cy) - margin)
        y1 = h if low < 0 else min(h, low + margin)
        y1 = max(y1, min(h, y0 + 1))
        boxes.append([y0, y1, x0, x1])
    return boxes
