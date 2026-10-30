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

import cv2
import numpy as np

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