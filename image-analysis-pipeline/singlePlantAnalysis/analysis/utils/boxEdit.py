"""Pure box-editing helpers for the plate ROI confirm screen (no GUI code).

Boxes are [y_min, y_max, x_min, x_max] in image pixels.
"""

MIN_SIZE = 20


def hit_test(boxes, x, y, handle=8):
    """Return (index, part) for the topmost box under (x, y), else None.

    part is 'l', 'r', 't', 'b' when within ``handle`` px of that edge,
    otherwise 'body'. Later boxes are drawn on top, so they win on overlap.
    """
    for i in range(len(boxes) - 1, -1, -1):
        y0, y1, x0, x1 = boxes[i]
        if not (x0 - handle <= x <= x1 + handle and y0 - handle <= y <= y1 + handle):
            continue
        dists = []
        if y0 <= y <= y1 or abs(y - y0) <= handle or abs(y - y1) <= handle:
            dists += [(abs(x - x0), 'l'), (abs(x - x1), 'r')]
        if x0 <= x <= x1 or abs(x - x0) <= handle or abs(x - x1) <= handle:
            dists += [(abs(y - y0), 't'), (abs(y - y1), 'b')]
        near = [d for d in dists if d[0] <= handle]
        if near:
            return i, min(near, key=lambda d: d[0])[1]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return i, 'body'
    return None


def move_box(box, dx, dy, image_shape):
    """Translate a box, keeping its size and staying inside the image."""
    h, w = int(image_shape[0]), int(image_shape[1])
    y0, y1, x0, x1 = box
    dy = max(-y0, min(h - y1, dy))
    dx = max(-x0, min(w - x1, dx))
    return [int(y0 + dy), int(y1 + dy), int(x0 + dx), int(x1 + dx)]


def resize_box(box, part, dx, dy, image_shape, min_size=MIN_SIZE):
    """Drag one edge ('l','r','t','b'); clamp to the image, keep >= min_size."""
    h, w = int(image_shape[0]), int(image_shape[1])
    y0, y1, x0, x1 = box
    if part == 'l':
        x0 = max(0, min(x0 + dx, x1 - min_size))
    elif part == 'r':
        x1 = min(w, max(x1 + dx, x0 + min_size))
    elif part == 't':
        y0 = max(0, min(y0 + dy, y1 - min_size))
    elif part == 'b':
        y1 = min(h, max(y1 + dy, y0 + min_size))
    return [int(y0), int(y1), int(x0), int(x1)]


def renumber(boxes):
    """Sort boxes left to right by x_min (plant 1 is leftmost)."""
    return [list(b) for b in sorted(boxes, key=lambda b: b[2])]
