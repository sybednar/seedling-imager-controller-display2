"""Colour a segmentation mask over an image (same colours as selectSeed)."""
import cv2

# BGR, as in getROIandSeed.selectSeed's "S" toggle; classes >= 5 are magenta.
CLASS_COLORS = {1: (0, 0, 255), 2: (0, 255, 0), 3: (255, 0, 0), 4: (0, 255, 255)}
OTHER_COLOR = (255, 0, 255)


def colorize_segmentation(image_bgr, seg):
    """Return a copy of ``image_bgr`` with class pixels coloured; class 0 is
    untouched. A mask of a different size is resized with nearest neighbour."""
    out = image_bgr.copy()
    h, w = out.shape[:2]
    if seg.shape[:2] != (h, w):
        seg = cv2.resize(seg, (w, h), interpolation=cv2.INTER_NEAREST)
    for val, color in CLASS_COLORS.items():
        out[seg == val] = color
    out[seg >= 5] = OTHER_COLOR
    return out
