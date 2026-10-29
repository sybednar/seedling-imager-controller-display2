import cv2
import cv2.aruco as aruco
import numpy as np
import os
import pathlib
import sys
import scipy.ndimage

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from singlePlantAnalysis.analysis.qr import aruco_detect_full

# Open folder_path and return every image as a list
def get_input_folder(folder_path):
    folder_path = pathlib.Path(folder_path)
    extensions = {".png",".tif",".tiff"}
    
    matching_files = sorted(
        p for p in folder_path.glob("*") 
        if p.is_file() and p.suffix.lower() in extensions
    )
    
    return matching_files

# Detect every marker in one frame. Returns (corners, ids), or (None, None) if nothing was found
def detect_frame(image_path):
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return None, None
    corners, ids, _ = aruco_detect_full(gray)
    if ids is None or len(ids) == 0:
        return None, None
    return corners, ids

def _perimeter(marker):
    pts = marker.reshape(4, 2)
    return float(np.linalg.norm(pts - np.roll(pts, 1, axis=0), axis=1).sum())

# The reference marker is the largest one in the first frame. The printed marker is far
# bigger than the false positives the detector sometimes reports elsewhere in the scene.
def pick_reference_id(corners, ids):
    largest = max(range(len(corners)), key=lambda k: _perimeter(corners[k]))
    return int(ids.flatten()[largest])

# Index (into corners/ids) of the marker with this ID, or None. If the ID shows up twice, the larger one wins.
def select_marker_index(corners, ids, marker_id):
    if corners is None or marker_id is None:
        return None
    matches = [k for k, i in enumerate(ids.flatten()) if int(i) == marker_id]
    if not matches:
        return None
    return max(matches, key=lambda k: _perimeter(corners[k]))

# The (4,2) corner array of the marker with this ID, or None
def select_marker(corners, ids, marker_id):
    k = select_marker_index(corners, ids, marker_id)
    return None if k is None else corners[k].reshape(4, 2)

# Detect the reference marker in each image and return its corners as a list of (4,2) arrays (None where missing)
def detect_marker_corners(image_paths):
    marker_corners = []
    ref_id = None
    for n, image in enumerate(image_paths):
        corners, ids = detect_frame(image)
        if n == 0 and corners is not None:
            ref_id = pick_reference_id(corners, ids)
        marker = select_marker(corners, ids, ref_id)

        if marker is None:
            print(f"Warning: reference marker not detected in {image.name}")
        marker_corners.append(marker)

    return marker_corners

# Aligns images to the aruco marker in the first frame. marker_corners is a list of one (4,2) array per frame, None where missing
def compute_transforms(marker_corners):
    if marker_corners[0] is None:
        raise ValueError("No ArUco marker detected in the first frame — cannot establish reference.")

    # The first image is used as the reference point
    reference = marker_corners[0].astype(np.float32)
    transforms = [] # Array of transformation that needs to be applied to each image

    for i, corners in enumerate(marker_corners):
        if corners is None:
            transforms.append(None)
        else:
            current = corners.astype(np.float32)
            ref_centroid = np.mean(reference, axis=0)
            cur_centroid = np.mean(current, axis=0)
            tx = ref_centroid[0] - cur_centroid[0]
            ty = 0
            M = np.float32([[1, 0, tx], [0, 1, ty]])
            transforms.append(M)
    
    return transforms

# def compute_transforms(marker_corners):
#       if marker_corners[0] is None:
#           raise ValueError("No ArUco marker detected in the first frame — cannot establish reference.")

#       # Collect all centroids
#       centroids = []
#       for corners in marker_corners:
#           if corners is None:
#               centroids.append(None)
#           else:
#               pts = corners[0][0].astype(np.float32)
#               centroids.append(np.mean(pts, axis=0))

#       # Fill None gaps with nearest valid centroid for smoothing
#       filled = _fill_none(centroids)

#       # Smooth tx/ty series with a Gaussian filter
#       xs = scipy.ndimage.gaussian_filter1d([c[0] for c in filled], sigma=5)
#       ys = scipy.ndimage.gaussian_filter1d([c[1] for c in filled], sigma=5)
  
#       ref_x, ref_y = xs[0], ys[0]
  
#       transforms = []
#       for i, corners in enumerate(marker_corners):
#           if corners is None:
#               transforms.append(None)
#           else:
#               M = np.float32([[1, 0, ref_x - xs[i]],
#                               [0, 1, ref_y - ys[i]]])
#               transforms.append(M)

#       return transforms


# def _fill_none(centroids):
#     filled = list(centroids)
#     # Forward fill
#     last = None
#     for i, c in enumerate(filled):
#         if c is not None:
#             last = c
#         elif last is not None:
#             filled[i] = last
#     # Backward fill for leading Nones
#     last = None
#     for i in range(len(filled) - 1, -1, -1):
#         if filled[i] is not None:
#             last = filled[i]
#         elif last is not None:
#             filled[i] = last
#     return filled
            
def apply_transforms(image_paths,transform_matrices):
    # Create the output directory
    output_folder = pathlib.Path(image_paths[0]).parent / "aligned"
    output_folder.mkdir(exist_ok=True)
    
    for i in range(0,len(image_paths)):
        file_name = os.path.basename(image_paths[i])
        name, extension = os.path.splitext(file_name)
        file_name = name + "_aligned" + extension
        
        
        image = cv2.imread(str(image_paths[i]))
        h, w = image.shape[:2]
        
        if transform_matrices[i] is None:
          print(f"Warning: no transform for {os.path.basename(image_paths[i])}, copying unmodified")
          transformed_image = image
        else:
            transformed_image = cv2.warpAffine(image, transform_matrices[i], (w, h))

        full_path = os.path.join(output_folder, file_name)
        cv2.imwrite(full_path, transformed_image)
        
# Only used for testing
if __name__ == "__main__":
    folder_path = "/Users/calvinyong/Desktop/UW Madison/Research Materials/Dataset/Experiment  20260528_124038/plate2"
    matching_files = get_input_folder(folder_path)
    marker_corners = detect_marker_corners(matching_files)
    transforms = compute_transforms(marker_corners)
    apply_transforms(matching_files, transforms)