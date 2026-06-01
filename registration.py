# registration.py — per-plate phase cross-correlation registration
#
# Usage:
#   from registration import PlateRegistrationCorrector
#   reg = PlateRegistrationCorrector()
#   dy, dx = reg.register(plate_id, img_path)   # (0.0, 0.0) on first call per plate
#   reg.reset()                                  # clear all references (new run)
#
# Algorithm:
#   • Load image as float32 grayscale (tifffile preferred, cv2 fallback)
#   • Extract 1024×1024 centre crop
#   • Normalised phase cross-correlation (FFT-based)
#   • Sub-pixel peak via parabolic refinement
#   • Positive dy = image shifted DOWN relative to reference
#   • Positive dx = image shifted RIGHT relative to reference

import numpy as np
from pathlib import Path


def _load_crop(img_path: str, half: int = 512) -> "np.ndarray | None":
    """Load grayscale image and return a (2*half) × (2*half) float32 centre crop."""
    img = None

    # Try tifffile first (lossless, preserves 16-bit)
    try:
        import tifffile
        raw = tifffile.imread(img_path)
        if raw.ndim == 3:
            # RGB or RGBA — convert to grayscale via luminance weights
            raw = (0.2989 * raw[..., 0] +
                   0.5870 * raw[..., 1] +
                   0.1140 * raw[..., 2]).astype(np.float32)
        else:
            img = raw.astype(np.float32)
    except Exception:
        pass

    # Fallback: OpenCV
    if img is None:
        try:
            import cv2
            raw = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if raw is not None:
                img = raw.astype(np.float32)
        except Exception:
            pass

    if img is None:
        return None

    cy, cx = img.shape[0] // 2, img.shape[1] // 2
    crop = img[cy - half: cy + half, cx - half: cx + half]
    if crop.shape != (2 * half, 2 * half):
        return None
    return crop


def _xcorr(ref: "np.ndarray", cur: "np.ndarray") -> "tuple[float, float]":
    """
    Normalised phase cross-correlation between two same-shape float32 arrays.
    Returns (dy, dx) shift of cur relative to ref, with sub-pixel parabolic refinement.
    """
    R = np.fft.fft2(ref)
    C = np.fft.fft2(cur)
    P = R * np.conj(C)
    norm = np.abs(P)
    norm[norm == 0] = 1.0
    P /= norm
    r = np.real(np.fft.ifft2(P))
    r = np.fft.fftshift(r)

    h, w = r.shape
    cy, cx = h // 2, w // 2
    py, px = np.unravel_index(np.argmax(r), r.shape)

    def _parabolic(arr, i):
        """Sub-pixel peak refinement along a 1-D slice."""
        if 0 < i < len(arr) - 1:
            denom = arr[i - 1] - 2.0 * arr[i] + arr[i + 1]
            if denom != 0.0:
                return i - 0.5 * (arr[i + 1] - arr[i - 1]) / denom
        return float(i)

    sy = _parabolic(r[:, px], py) - cy
    sx = _parabolic(r[py, :], px) - cx
    return float(sy), float(sx)


class PlateRegistrationCorrector:
    """
    Tracks per-plate image registration across cycles.

    First call for a given plate_id stores the reference image and returns (0.0, 0.0).
    Subsequent calls return (dy, dx) shift in pixels relative to that reference.
    Call reset() at the start of each new experiment run.
    """

    def __init__(self, crop_half: int = 512):
        self.crop_half = crop_half
        self._refs: dict[int, np.ndarray] = {}

    def reset(self) -> None:
        """Clear all stored reference images."""
        self._refs.clear()

    def register(self, plate_id: int, img_path: str) -> "tuple[float, float]":
        """
        Compute shift of the image at img_path relative to the stored reference
        for plate_id.  Stores the image as the reference if none exists yet.

        Returns:
            (dy, dx) in pixels — rounded to 3 decimal places.
            (0.0, 0.0) if the image cannot be loaded or on the first call.
        """
        crop = _load_crop(img_path, half=self.crop_half)
        if crop is None:
            return (0.0, 0.0)

        if plate_id not in self._refs:
            self._refs[plate_id] = crop
            return (0.0, 0.0)

        dy, dx = _xcorr(self._refs[plate_id], crop)
        return (round(dy, 3), round(dx, 3))