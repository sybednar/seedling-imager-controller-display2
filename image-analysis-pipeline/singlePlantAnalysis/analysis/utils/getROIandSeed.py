""" 
ChronoRoot: High-throughput phenotyping by deep learning reveals novel temporal parameters of plant root system architecture
Copyright (C) 2020 Nicolás Gaggion

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import time

import cv2
import numpy as np

from analysis.utils import boxEdit, componentROIs, segOverlay

# State for custom ROI selector
_roi_state = {
    'start': None,
    'end': None,
    'drawing': False,
    'done': False,
}

def _roi_mouse_callback(event, x, y, flags, param):
    s = _roi_state
    if event == cv2.EVENT_LBUTTONDOWN:
        s['start'] = (x, y)
        s['end'] = (x, y)
        s['drawing'] = True
        s['done'] = False
    elif event == cv2.EVENT_MOUSEMOVE and s['drawing']:
        s['end'] = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        s['end'] = (x, y)
        s['drawing'] = False
        s['done'] = True

def selectROI(image):
        window_name = "Select Plant ROI"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        DISPLAY_SIZE = 1000
        h_orig, w_orig = image.shape[:2]
        scale = DISPLAY_SIZE / max(h_orig, w_orig)
        display_w = int(w_orig * scale)
        display_h = int(h_orig * scale)
        cv2.resizeWindow(window_name, display_w, display_h)

        img_small = cv2.resize(image, (display_w, display_h), interpolation=cv2.INTER_AREA)

        # Reset state
        for k in _roi_state:
            _roi_state[k] = None if k != 'drawing' and k != 'done' else False
        cv2.setMouseCallback(window_name, _roi_mouse_callback)

        font = cv2.FONT_HERSHEY_SIMPLEX

        while True:
            img_copy = img_small.copy()

            # Draw live rectangle while dragging or after release
            s = _roi_state
            if s['start'] is not None and s['end'] is not None:
                cv2.rectangle(img_copy, s['start'], s['end'], (0, 255, 0), 2)

            # Instructions
            if s['done']:
                lines = [
                    "Selection made.",
                    "ENTER: confirm   R: redo   Q: quit",
                ]
            else:
                lines = [
                    "Select Plant ROI",
                    "Click and drag to select region",
                    "ENTER: confirm   R: redo   Q: quit",
                ]

            y0 = 25
            for idx, line in enumerate(lines):
                cv2.putText(img_copy, line, (10, y0 + idx * 28), font, 0.8, (255, 255, 255), 2)

            cv2.imshow(window_name, img_copy)
            key = cv2.waitKey(16) & 0xFF  # ~60 fps

            if key == ord('q'):
                cv2.destroyWindow(window_name)
                return None
            elif key == ord('r'):
                for k in _roi_state:
                    _roi_state[k] = None if k != 'drawing' and k != 'done' else False
            elif key in [13, 10]:  # Enter
                if not s['done']:
                    continue
                x0, y0_ = s['start']
                x1, y1 = s['end']
                rx, ry = min(x0, x1), min(y0_, y1)
                rw, rh = abs(x1 - x0), abs(y1 - y0_)
                if rw == 0 or rh == 0:
                    print("Invalid selection, please try again")
                    continue
                roi = (
                    int(rx / scale),
                    int(ry / scale),
                    int(rw / scale),
                    int(rh / scale),
                )
                cv2.destroyWindow(window_name)
                return roi

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                return None
            
pos = None

def mouse_callback(event, x, y, flags, param):
    global pos
    if event == cv2.EVENT_LBUTTONDOWN:
        pos = [x, y]
        
def selectSeed(images, segFiles, bbox, conf):
    n = min(len(images), len(segFiles))
    images, segFiles = images[:n], segFiles[:n]

    # Time calculations
    timeStep = conf['timeStep']
    time_mins = np.arange(0, n * timeStep, timeStep)
    minutes = (time_mins % 60).astype('int')
    hours = ((time_mins / 60) % 24).astype('int')
    days = (time_mins // 1440).astype('int')

    global pos
    window_name = 'Select Root Origin'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 900)
    cv2.setMouseCallback(window_name, mouse_callback)
    cv2.createTrackbar('Overlap segmentation with "s"', window_name, 0, n - 1, lambda x: None)

    useSeg = False
    cached_i = -1
    cached_img = None
    cached_seg = None

    while True:
        i = cv2.getTrackbarPos('Overlap segmentation with "s"', window_name)

        if i != cached_i:
            cached_img = cv2.imread(images[i])[bbox[0]:bbox[1], bbox[2]:bbox[3]]
            cached_seg = cv2.imread(segFiles[i], 0)[bbox[0]:bbox[1], bbox[2]:bbox[3]]
            cached_i = i

        img = cached_img.copy()
        h, w = img.shape[:2]

        if useSeg:
            seg = cached_seg
            colors = {1: (0, 0, 255), 2: (0, 255, 0), 3: (255, 0, 0), 4: (0, 255, 255)}
            for val, color in colors.items():
                img[seg == val] = color
            img[seg >= 5] = (255, 0, 255)

        # Top Overlay: Large Day and Time

        if pos is not None:
            # Precision marker and divider
            cv2.drawMarker(img, tuple(pos), (0, 255, 0), cv2.MARKER_CROSS, 25, 5)
            cv2.line(img, (0, pos[1]), (w, pos[1]), (0, 255, 255), 5)
            cv2.putText(img, "Root Start", (w-250, pos[1]+35), 0, 1.0, (255, 255, 0), 3)

        # Bottom Overlay: Large Instructions in Rows
        row1 = "ENTER: CONFIRM"
        row2 = "S: TOGGLE SEGMENTATION"
        row3 = "ESC/C/Q: CANCEL"

        cv2.putText(img, "Day: %2d" % days[i], (10, h-230), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 5)
        cv2.putText(img, "Time: %2d:%2d" % (hours[i], minutes[i]), (10, h-175), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 5)
        cv2.putText(img, row1, (10, h-130), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        cv2.putText(img, row2, (10, h-85), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        cv2.putText(img, row3, (10, h-40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        cv2.imshow(window_name, img)
        key = cv2.waitKey(1) & 0xFF

        # Return None on cancel keys
        if key in [ord('c'), ord('q'), 27]:
            cv2.destroyAllWindows()
            return None
        
        # Return position on Enter
        elif key in [13, 10]:
            if pos is not None:
                break
        
        elif key == ord('s'):
            useSeg = not useSeg
        
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            return None

    cv2.destroyAllWindows()
    return pos

def getROIandSeed(conf, images, segFiles):
    last_image = cv2.imread(images[-1])
    try:
        r = selectROI(last_image)
    except:
        return None, None
    
    if r is None:
        return None, None
    elif r[0] == 0 and r[1] == 0 and r[2] == 0 and r[3] == 0:
        return None, None

    bbox = [int(r[1]),int(r[1]+r[3]), int(r[0]),int(r[0]+r[2])]    
    
    try:
        seed = selectSeed(images, segFiles, bbox, conf)
    except:
        return None, None
    
    if seed is None:
        return None, None
    
    return bbox, seed


def _clamp_new_box(p0, p1, image_shape):
    """Box [y0, y1, x0, x1] from two drag corners (image px), clamped; None if too small."""
    h, w = image_shape[:2]
    x0, x1 = sorted((int(p0[0]), int(p1[0])))
    y0, y1 = sorted((int(p0[1]), int(p1[1])))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 - x0 < boxEdit.MIN_SIZE or y1 - y0 < boxEdit.MIN_SIZE:
        return None
    return [y0, y1, x0, x1]


def selectPlantROIs(image, boxes, notice=None, seg=None):
    """Interactive confirm screen for per-plant boxes on the plate image.

    Boxes may be pre-filled (auto-proposed) and stay fully editable. Drag on empty
    space to draw a box (A add mode still works but is not needed),
    drag a box body to move it, drag an edge to resize, D deletes the selected box,
    Enter confirms, Q/Esc/window close cancels. ``boxes`` are the starting boxes
    (empty for manual drawing). Returns boxes in plant order, or None if cancelled.
    ``notice`` is an optional text shown for the first few seconds. ``seg`` is
    the optional grayscale mask of the same frame; S toggles its colour overlay.
    Box logic lives in boxEdit; this function only wires up the window.
    """
    window_name = "Confirm Plant ROIs"
    DISPLAY_SIZE = 1000
    h_orig, w_orig = image.shape[:2]
    scale = DISPLAY_SIZE / max(h_orig, w_orig)
    display_w, display_h = int(w_orig * scale), int(h_orig * scale)
    img_small = cv2.resize(image, (display_w, display_h), interpolation=cv2.INTER_AREA)
    seg_small = None
    if seg is not None:
        seg_small = segOverlay.colorize_segmentation(
            img_small, cv2.resize(seg, (display_w, display_h), interpolation=cv2.INTER_NEAREST))
    handle = max(1, int(round(8 / scale)))  # 8 display px, in image px
    click_tol = max(1, int(round(4 / scale)))  # 4 display px: click, not drag

    state = {
        'boxes': boxEdit.renumber(boxes),
        'selected': None,
        'drag': None,      # (index, part, last_x, last_y) in image px
        'adding': False,
        'show_seg': False,
        'add_start': None,
        'add_end': None,
        'notice_until': time.time() + 8.0,
        'message': None,   # (text, expires_at) short on-screen notice
    }

    def to_img(x, y):
        return int(x / scale), int(y / scale)

    def on_mouse(event, x, y, flags, param):
        ix, iy = to_img(x, y)
        st = state
        if event == cv2.EVENT_LBUTTONDOWN:
            act = boxEdit.press_action(st['boxes'], ix, iy, handle, st['adding'])
            if act[0] == 'draw':
                st['selected'] = None
                st['add_start'] = st['add_end'] = (ix, iy)
                st['message'] = None
            else:
                st['selected'] = act[1]
                st['drag'] = (act[1], act[2], ix, iy)
        elif event == cv2.EVENT_MOUSEMOVE:
            if st['add_start'] is not None:
                st['add_end'] = (ix, iy)
            elif st['drag'] is not None:
                i, part, lx, ly = st['drag']
                dx, dy = ix - lx, iy - ly
                if part == 'body':
                    st['boxes'][i] = boxEdit.move_box(st['boxes'][i], dx, dy, image.shape)
                else:
                    st['boxes'][i] = boxEdit.resize_box(st['boxes'][i], part, dx, dy, image.shape)
                st['drag'] = (i, part, ix, iy)
        elif event == cv2.EVENT_LBUTTONUP:
            if st['add_start'] is not None:
                start = st['add_start']
                new = _clamp_new_box(start, (ix, iy), image.shape)
                st['add_start'] = st['add_end'] = None
                if boxEdit.is_click(start, (ix, iy), click_tol):
                    pass  # plain click on empty space: just deselects
                elif new is not None:
                    st['boxes'].append(new)
                    st['selected'] = len(st['boxes']) - 1
                else:
                    st['message'] = ("Box too small (min %d px): add cancelled" % boxEdit.MIN_SIZE,
                                     time.time() + 3.0)
                # Leave add mode either way so a stray drag can't keep it armed.
                st['adding'] = False
            st['drag'] = None

    font = cv2.FONT_HERSHEY_SIMPLEX
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, display_w, display_h)
        cv2.setMouseCallback(window_name, on_mouse)

        while True:
            frame = (seg_small if state['show_seg'] and seg_small is not None else img_small).copy()
            # Number plants with the same rule as the final renumber (bottom row
            # first, then left to right) without reordering the list mid-drag.
            order = boxEdit.plant_order(state['boxes'])
            for rank, k in enumerate(order, start=1):
                y0, y1, x0, x1 = state['boxes'][k]
                color = (0, 255, 255) if k == state['selected'] else (0, 255, 0)
                p0 = (int(x0 * scale), int(y0 * scale))
                p1 = (int(x1 * scale), int(y1 * scale))
                cv2.rectangle(frame, p0, p1, color, 2)
                cv2.putText(frame, str(rank), (p0[0] + 6, p0[1] + 28), font, 0.9, color, 2)
            if state['add_start'] is not None:
                a, b = state['add_start'], state['add_end']
                cv2.rectangle(frame, (int(a[0] * scale), int(a[1] * scale)),
                              (int(b[0] * scale), int(b[1] * scale)), (255, 0, 255), 2)

            legend = boxEdit.legend_lines(state['adding'], len(state['boxes']), seg_small is not None)
            notice_lines = notice.split("\n") if notice and time.time() < state['notice_until'] else []
            for n, line in enumerate(notice_lines):
                cv2.putText(frame, line, (10, 28 + 26 * n), font, 0.7, (0, 255, 255), 2)
            msg = state['message']
            if msg is not None and time.time() < msg[1]:
                cv2.putText(frame, msg[0], (10, 28 + 26 * len(notice_lines)), font, 0.7, (0, 0, 255), 2)
            for n, line in enumerate(legend):
                cv2.putText(frame, line, (10, display_h - 12 - 26 * (len(legend) - 1 - n)),
                            font, 0.6, (255, 255, 255), 2)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(16) & 0xFF

            action = boxEdit.key_action(key, state['adding'])
            if action == 'cancel':
                return None
            elif action == 'confirm':
                return boxEdit.renumber(state['boxes'])
            elif action == 'delete':
                if state['selected'] is not None:
                    del state['boxes'][state['selected']]
                    state['selected'] = None
                    state['drag'] = None
            elif action == 'toggle_seg':
                if seg_small is not None:
                    state['show_seg'] = not state['show_seg']
            elif action == 'enter_add':
                state['adding'] = True
                state['selected'] = None
            elif action == 'exit_add':
                state['adding'] = False
                state['add_start'] = state['add_end'] = None

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                return None
    finally:
        cv2.destroyAllWindows()


def getPlateROIsAndSeeds(conf, images, segFiles):
    """Auto-propose a box per plant from the last frame's segmentation, let the
    user edit/confirm them, then collect a manual root origin per box. Returns
    [{'plant', 'bounding box', 'seed'}] with seeds relative to each box, or None
    if cancelled or no boxes confirmed. If the proposal fails, boxes are drawn by hand."""
    global pos
    last_image = cv2.imread(images[-1])
    if last_image is None:
        return None

    seg = cv2.imread(segFiles[-1], 0)   # None if unreadable: no overlay, no crash
    proposed, notice = [], None
    try:
        detail = componentROIs.propose_component_boxes_detail(segFiles[-1])
        proposed = detail['boxes']
        notice = componentROIs.proposal_notice(detail)
    except Exception as e:
        print("Box proposal failed (%s); draw boxes by hand" % e)
        proposed, notice = [], None

    try:
        boxes = selectPlantROIs(last_image, proposed, notice=notice, seg=seg)
    except Exception as e:
        print("ROI selection failed: %s" % e)
        return None
    if not boxes:
        return None

    plants = []
    for n, bbox in enumerate(boxEdit.renumber(boxes), start=1):
        # selectSeed keeps the last click in module-global ``pos``; clear it so
        # each plant starts with no origin placed.
        pos = None
        seed = selectSeed(images, segFiles, bbox, conf)
        if seed is None:
            return None
        plants.append({'plant': n, 'bounding box': list(bbox), 'seed': list(seed)})
    return plants
