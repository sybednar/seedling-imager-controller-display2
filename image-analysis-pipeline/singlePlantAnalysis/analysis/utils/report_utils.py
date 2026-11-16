import re
import pathlib
import os
import json
import numpy as np

def natural_key(string_text):
    """
    Sorts strings containing numbers in a human-friendly way 
    (e.g., 'File 2' comes before 'File 10').
    See http://www.codinghorror.com/blog/archives/001018.html
    """
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_text)]

_IMAGE_EXTS = ("*.png", "*.tif", "*.tiff")

def load_image_files(search_path):
    """Load all image files (PNG/TIF/TIFF) from a directory, sorted naturally."""
    data_root = pathlib.Path(search_path)
    all_files = []
    for ext in _IMAGE_EXTS:
        all_files.extend(data_root.glob(ext))
    all_files = [str(p) for p in all_files]
    all_files.sort(key=natural_key)
    return all_files

def load_paths(search_path, ext='*.*'):
    """
    Glob patterns for files and sorts them naturally.
    """
    data_root = pathlib.Path(search_path)
    # The glob pattern needs to be consistent with pathlib usage
    # If ext contains wildcards like *.*, we use it directly
    all_files = list(data_root.glob(ext))
    all_files = [str(path) for path in all_files]
    all_files.sort(key=natural_key)
    return all_files

def ensure_directory(path):
    """Safely creates a directory if it doesn't exist."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass

def unit_vector(vector):
    """Returns the unit vector of the vector."""
    norm = np.linalg.norm(vector)
    if norm == 0: 
        return vector
    return vector / norm

def angle_between(v1, v2):
    """
    Returns the angle in radians between vectors 'v1' and 'v2'.
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    # Clip to handle floating point errors outside [-1, 1]
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))


def experiment_display_name(exp_dir):
    """
    Human-readable experiment name for an Analysis/<experiment> folder: the
    "Experiment" value in the first metadata.json found, else the folder name
    with the path-safe encoding undone.
    """
    from .fileUtilities import convertFromPathSafe
    name = convertFromPathSafe(os.path.basename(os.path.normpath(exp_dir)))
    for meta_path in load_paths(exp_dir, '*/*/*/metadata.json')[:1]:
        try:
            with open(meta_path, 'r') as f:
                name = json.load(f).get('Experiment', name)
        except (OSError, ValueError):
            pass
    return name


def experiment_has_data(exp_dir):
    """
    True if at least one <cam>/<plant> under the experiment has a PostProcess_Hour.csv
    in its latest Results_* folder (the file the report reads for each plant).
    """
    for plant in load_paths(exp_dir, '*/*'):
        results = load_paths(plant, '*')
        if results and os.path.exists(os.path.join(results[-1], 'PostProcess_Hour.csv')):
            return True
    return False


def filter_experiments(experiments, conf, verbose=False):
    """
    Keep only the experiment folders listed in conf['selectedExperiments']
    (matched on display name or folder name). A missing/None key keeps all, so
    configs saved before this option existed behave as before.

    Selected experiments with no valid data (see experiment_has_data) are
    skipped; with verbose=True each skip is reported.
    """
    selected = conf.get('selectedExperiments')
    if selected is not None:
        selected = set(selected)
        experiments = [e for e in experiments
                       if experiment_display_name(e) in selected
                       or os.path.basename(os.path.normpath(e)) in selected]
    kept = []
    for e in experiments:
        if experiment_has_data(e):
            kept.append(e)
        elif verbose:
            print(f"Skipping experiment '{experiment_display_name(e)}': "
                  "no PostProcess_Hour.csv found in any plant's latest Results folder.")
    return kept
