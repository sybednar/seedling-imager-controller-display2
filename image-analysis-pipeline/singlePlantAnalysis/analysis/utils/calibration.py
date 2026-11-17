"""
Scale-calibration constants shared by the GUI guard (run.py), post-processing
(2_postprocess.py) and the ArUco detector. Kept free of cv2/pyzbar imports so the GUI
can import it cheaply.
"""

# Physical side length of the ArUco calibration marker (mm).
ARUCO_MARKER_MM = 15

# Narrowest detected ArUco marker (in pixels) that still gives a reliable scale.
# The Analyze button refuses to start below this; post-processing warns.
MIN_ARUCO_PIXEL_WIDTH = 300

# Pixel size (mm/px) 2_postprocess.py falls back to when a marker is expected but not found.
DEFAULT_PIXEL_SIZE = 0.04
