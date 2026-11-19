"""Pure box-editing helpers for the plate ROI confirm screen (no GUI code).

Boxes are [y_min, y_max, x_min, x_max] in image pixels.
"""

MIN_SIZE = 20
# A new plate row starts when y_min jumps by more than this fraction of the
# median box height.
ROW_GAP_FRACTION = 0.25


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


def plant_order(boxes):
    """Indices of ``boxes`` in plant-number order (plant 1 first).

    Rows come first: boxes are sorted by y_min and a new row starts when y_min
    exceeds the previous box's y_min by more than ROW_GAP_FRACTION of the median
    box height. The bottom row of the plate (largest y) gets the lowest numbers;
    within a row plants run left to right by x_min.
    """
    if not boxes:
        return []
    by_y = sorted(range(len(boxes)), key=lambda i: boxes[i][0])
    heights = sorted(b[1] - b[0] for b in boxes)
    m = len(heights)
    median = heights[m // 2] if m % 2 else (heights[m // 2 - 1] + heights[m // 2]) / 2.0
    gap = ROW_GAP_FRACTION * median
    rows = [[by_y[0]]]
    for prev, cur in zip(by_y, by_y[1:]):
        if boxes[cur][0] - boxes[prev][0] > gap:
            rows.append([])
        rows[-1].append(cur)
    order = []
    for row in reversed(rows):
        order += sorted(row, key=lambda i: boxes[i][2])
    return order


def renumber(boxes):
    """Return copies of ``boxes`` in plant-number order (see plant_order)."""
    return [list(boxes[i]) for i in plant_order(boxes)]


def press_action(boxes, x, y, handle, adding):
    """Decide what a left-button press means on the confirm screen.

    Returns ('draw',) to start a new box (add mode, or empty space), or
    ('drag', index, part) when the press lands on an existing box.
    """
    if adding:
        return ('draw',)
    hit = hit_test(boxes, x, y, handle)
    if hit is None:
        return ('draw',)
    return ('drag', hit[0], hit[1])


def is_click(p0, p1, tol):
    """True if press and release points are within ``tol`` px on both axes,
    i.e. a plain click rather than a drag."""
    return abs(p1[0] - p0[0]) <= tol and abs(p1[1] - p0[1]) <= tol


def legend_lines(adding, n_boxes, has_seg=False):
    """On-screen instruction lines for the confirm screen (top line first)."""
    lines = []
    if adding:
        lines.append("ADD MODE: drag a new box (A or Esc: leave add mode)")
    if n_boxes == 0:
        lines.append("No boxes: drag on the plate to draw a box around each plant")
    lines += [
        "Drag on empty space to draw a plant box   Drag box: move   Drag edge: resize",
        "D: delete selected   ENTER: confirm   Q/Esc: cancel",
    ]
    if has_seg:
        lines.append("S: toggle segmentation")
    return lines


def key_action(key, adding):
    """Map a key code to a confirm-screen action, given whether add mode is on.

    Returns 'cancel', 'confirm', 'delete', 'enter_add', 'exit_add', 'toggle_seg'
    or None.
    In add mode Esc and A leave add mode instead of cancelling the screen;
    Q still cancels.
    """
    if key in (ord('q'), ord('Q')):
        return 'cancel'
    if key == 27:
        return 'exit_add' if adding else 'cancel'
    if key in (13, 10):
        return 'confirm'
    if key in (ord('d'), ord('D')):
        return 'delete'
    if key in (ord('s'), ord('S')):
        return 'toggle_seg'
    if key in (ord('a'), ord('A')):
        return 'exit_add' if adding else 'enter_add'
    return None
