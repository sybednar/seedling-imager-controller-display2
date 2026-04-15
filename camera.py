
# camera.py
from picamera2 import Picamera2
from PySide6.QtGui import QImage
import numpy as np
import cv2
from pathlib import Path
import json
import threading

# Try to import tifffile for TIFF saving (optional but recommended)
try:
    import tifffile as tiff
except ImportError:
    tiff = None  # save_image() will fall back to OpenCV for non-TIFF paths

# =============================================================================
# Settings persistence (camera_settings.json)
# =============================================================================
DEFAULTS = {
    "AeEnable": True,          # Auto Exposure on/off
    "ExposureTime": 20000,     # microseconds (used only when AE is False)
    "AnalogueGain": 1.0,       # sensor analogue gain (ISO-like)
    "AwbEnable": True,         # Auto White Balance on/off
    "Contrast": 1.0,
    "Brightness": 0.0,         # typically -1.0 .. +1.0
    "Saturation": 1.0,
    "Sharpness": 1.0,
    "NoiseReductionMode": 0,   # 0=off (preferred for scientific imaging)
    "HdrEnable": False,        # keep HDR off for full-res work
    "ManualFocusEnable":   False,   # ADDED 041426
    "ManualFocusPosition": 7.589,   # ADDED — diopters measured 14 April 2026
    
        # --- NEW: Front IR (reflectance) overrides ---
    "FrontIR_Saturation":  0.0,
    "FrontIR_AwbEnable":   False,
    "FrontIR_Contrast":    1.10,
    "FrontIR_Sharpness":   1.15,
    "FrontIR_Brightness":  0.0,
    "FrontIR_AeEnable":    True,
    "FrontIR_ExposureTime": 20000,
    "FrontIR_Gain":        1.0,

    # --- NEW: Rear IR (transmission) overrides ---
    "RearIR_Saturation":   0.0,
    "RearIR_AwbEnable":    False,
    "RearIR_Contrast":     1.5,
    "RearIR_Sharpness":    1.4,
    "RearIR_Brightness":  -0.05,
    "RearIR_AeEnable":     False,
    "RearIR_ExposureTime": 9000,
    "RearIR_Gain":         1.0,
    
    
}
SETTINGS_PATH = Path("camera_settings.json")

def load_settings() -> dict:
    """Load camera settings from JSON; fall back to DEFAULTS on error."""
    if SETTINGS_PATH.exists():
        try:
            return {**DEFAULTS, **json.loads(SETTINGS_PATH.read_text())}
        except Exception:
            pass
    return DEFAULTS.copy()

def save_settings(settings: dict) -> bool:
    """Persist camera settings to JSON."""
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
        return True
    except Exception:
        return False

def apply_ir_quant_preset(base: dict | None) -> dict:
    """
    Build Front IR (reflectance) runtime settings by merging FrontIR_* overrides
    from persisted settings onto the base dict.
    Does NOT write camera_settings.json.
    """
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Saturation"]  = 0.0    # always 0 for IR — no useful chroma information
    s["AwbEnable"]   = False  # always off — prevents channel drift on 940 nm source
    s["NoiseReductionMode"] = 0
    s["Contrast"]    = float(saved.get("FrontIR_Contrast",   1.10))
    s["Sharpness"]   = float(saved.get("FrontIR_Sharpness",  1.15))
    s["Brightness"]  = float(saved.get("FrontIR_Brightness", 0.0))
    s["AeEnable"]    = bool(saved.get("FrontIR_AeEnable",    True))
    if not s["AeEnable"]:
        s["ExposureTime"]  = int(saved.get("FrontIR_ExposureTime", 20000))
        s["AnalogueGain"]  = float(saved.get("FrontIR_Gain",       1.0))
    return s


def apply_ir_transmission_preset(base: dict | None) -> dict:
    """
    Build Rear IR (transmission) runtime settings by merging RearIR_* overrides
    from persisted settings onto the base dict.
    Does NOT write camera_settings.json.
    """
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Saturation"]  = 0.0    # always 0 for IR
    s["AwbEnable"]   = False  # always off
    s["NoiseReductionMode"] = 0
    s["Contrast"]    = float(saved.get("RearIR_Contrast",    1.5))
    s["Sharpness"]   = float(saved.get("RearIR_Sharpness",   1.4))
    s["Brightness"]  = float(saved.get("RearIR_Brightness", -0.05))
    s["AeEnable"]    = bool(saved.get("RearIR_AeEnable",     False))
    if not s["AeEnable"]:
        s["ExposureTime"]  = int(saved.get("RearIR_ExposureTime", 9000))
        s["AnalogueGain"]  = float(saved.get("RearIR_Gain",        1.0))
    return s

def set_manual_exposure_gain(exposure_us: int, gain: float) -> None:
    """
    Explicitly pin exposure and gain (use after AE settling for repeatability).
    """
    try:
        picam.set_controls({
            "AeEnable": False,
            "ExposureTime": int(exposure_us),
            "AnalogueGain": float(gain),
        })
    except Exception as e:
        print(f"set_manual_exposure_gain error: {e}", flush=True)


# --- Live-view boost state (module-level) ---
_liveview_boost_active = False
_liveview_saved_controls = None

def enable_liveview_boost_for_ir(
    target_gain: float = 8.0,
    target_exposure_us: int = 20000,
    mode: str = "Front IR"
) -> None:
    """
    Temporarily brighten the IR live view by pushing AnalogueGain and ExposureTime.
    Should only be called during Live View; must be cleared with disable_liveview_boost()
    before starting an experiment.

    mode: one of "Front IR" (reflectance), "Rear IR" (transmission), "Combined IR".
      - Rear IR and Combined IR illuminate the sensor with far more photons than front
        reflectance, so the gain and exposure ceilings are lowered automatically to
        avoid saturation of the agar background.
      - Front IR (reflectance) uses the full target_gain / target_exposure_us as passed.
    """
    global _liveview_boost_active, _liveview_saved_controls

    if _liveview_boost_active:
        return  # already active; caller must disable before re-calling with new mode

    # --- Adjust boost parameters for transmission geometries ---
    # Rear and combined panels produce a bright-field signal that is typically
    # 5–20× stronger than front reflectance.  Cap gain and exposure to prevent
    # the agar background from clipping while still giving a usable preview.
    if mode in ("Rear IR", "Combined IR"):
        target_gain        = min(target_gain, 1.0)    # was 2.0
        target_exposure_us = min(target_exposure_us, 500)  # ~8 ms ceiling change from 8000
    # Front IR: use the caller-supplied values unchanged (default 8.0 gain / 20 ms)

    try:
        # Snapshot current controls so disable_liveview_boost() can restore them exactly
        md = get_metadata() or {}
        _liveview_saved_controls = {
            "AeEnable":    md.get("AeEnable",    True),
            "ExposureTime": md.get("ExposureTime", None),
            "AnalogueGain": md.get("AnalogueGain", None),
            "AwbEnable":   md.get("AwbEnable",   True),
        }

        # Let AE settle briefly before we apply the floor — helps the sensor
        # start from a reasonable operating point rather than from cold defaults
        try:
            set_auto_exposure(True)
        except Exception:
            pass

        controls = {
            # Keep AE active during preview so it can hunt around the floor;
            # set AeEnable=False here if you prefer a hard-locked preview instead.
            "AeEnable":     True,
            # Floor the gain so preview stays bright even if AE wants to go lower
            "AnalogueGain": float(target_gain),
            # Provide an exposure starting point; AE will adjust from here
            "ExposureTime": int(target_exposure_us),
            # AWB has no useful effect on a near-monochromatic 940 nm signal and
            # can cause channel-gain oscillation — keep it off for all IR modes
            "AwbEnable":    False,
        }
        picam.set_controls(controls)
        _liveview_boost_active = True
        print(
            f"[camera] Live-view IR boost enabled: mode={mode}, "
            f"gain_floor={target_gain}, exposure_floor={target_exposure_us}µs",
            flush=True
        )

    except Exception as e:
        print(f"[camera] liveview boost error: {e}", flush=True)

def disable_liveview_boost() -> None:
    """
    Restore controls saved by enable_liveview_boost_for_ir(). Safe to call multiple times.
    """
    global _liveview_boost_active, _liveview_saved_controls
    if not _liveview_boost_active:
        return
    try:
        if isinstance(_liveview_saved_controls, dict):
            # Restore previous state (best-effort)
            picam.set_controls({
                "AeEnable": bool(_liveview_saved_controls.get("AeEnable", True)),
                "AwbEnable": bool(_liveview_saved_controls.get("AwbEnable", True)),
            })
            # If previous capture was manual, restore exact exposure/gain
            prev_exp = _liveview_saved_controls.get("ExposureTime", None)
            prev_gain = _liveview_saved_controls.get("AnalogueGain", None)
            if prev_exp is not None and prev_gain is not None and not _liveview_saved_controls.get("AeEnable", True):
                picam.set_controls({"ExposureTime": int(prev_exp), "AnalogueGain": float(prev_gain)})
        _liveview_boost_active = False
        _liveview_saved_controls = None
        print("[camera] Live-view IR boost disabled (restored controls)", flush=True)
    except Exception as e:
        print(f"[camera] liveview boost restore error: {e}", flush=True)

# =============================================================================
# Picamera2 dual-stream setup
# =============================================================================
picam = Picamera2()
_cam_lock = threading.Lock()

# Full-res still (main) + low-res preview (lores).
# Adjust 'main' size if your sensor reports a different maximum.
preview_and_still_cfg = picam.create_still_configuration(
    main={"size": (4608, 2592), "format": "RGB888"},   # full-resolution for saving
    lores={"size": (1280, 720), "format": "RGB888"}     # 16:9 preview for Live View
)
picam.configure(preview_and_still_cfg)

def apply_settings(settings: dict = None) -> None:
    """
    Apply camera settings to Picamera2. If 'settings' is None, load from JSON.
    Note: ExposureTime is only set when AE is disabled (AeEnable=False).
    """
    if settings is None:
        settings = load_settings()

    ctrl = {
        "AeEnable":          bool(settings.get("AeEnable", True)),
        "AwbEnable":         bool(settings.get("AwbEnable", True)),
        "AnalogueGain":      float(settings.get("AnalogueGain", 1.0)),
        "Contrast":          float(settings.get("Contrast", 1.0)),
        "Brightness":        float(settings.get("Brightness", 0.0)),
        "Saturation":        float(settings.get("Saturation", 1.0)),
        "Sharpness":         float(settings.get("Sharpness", 1.0)),
        "NoiseReductionMode":int(settings.get("NoiseReductionMode", 0))
        #"HdrEnable":         bool(settings.get("HdrEnable", False)),
    }
    # Apply manual exposure only if AE is off
    if not ctrl["AeEnable"]:
        ctrl["ExposureTime"] = int(settings.get("ExposureTime", 20000))

    try:
        picam.set_controls(ctrl)
    except Exception as e:
        print(f"apply_settings error: {e}", flush=True)

def get_current_settings() -> dict:
    """Return the last saved (or default) settings for UI convenience."""
    return load_settings()

# =============================================================================
# Start/stop camera
# =============================================================================
def start_camera() -> None:
    """Start Picamera2 pipeline (idempotent). Apply focus mode immediately."""
    try:
        picam.start()
    except Exception:
        pass  # ignore if already started

    settings = load_settings()
    if settings.get("ManualFocusEnable", False):
        set_manual_focus()              # lock to saved diopter value
    else:
        set_af_mode(2)                  # continuous AF for live preview

def stop_camera() -> None:
    """Stop Picamera2 pipeline."""
    try:
        picam.stop()
    except Exception:
        pass

# =============================================================================
# Exposure & autofocus helpers
# =============================================================================
def set_auto_exposure(enabled: bool) -> None:
    """Enable/disable auto exposure."""
    try:
        picam.set_controls({"AeEnable": bool(enabled)})
    except Exception as e:
        print(f"set_auto_exposure error: {e}", flush=True)

def set_manual_focus(position: float = None) -> None:
    """
    Lock the lens to a fixed diopter position.
    If position is None, reads ManualFocusPosition from the persisted settings file.
    Call this after every start_camera() when ManualFocusEnable is True —
    the lens does NOT hold its position across pipeline restarts.
    """
    if position is None:
        position = float(load_settings().get("ManualFocusPosition", 7.589))
    try:
        picam.set_controls({
            "AfMode":       0,                 # 0 = manual; disables PDAF/CDAF
            "LensPosition": float(position),
        })
        print(f"[camera] Manual focus locked: {position:.3f} diopters", flush=True)
    except Exception as e:
        print(f"[camera] set_manual_focus error: {e}", flush=True)

def set_af_mode(mode: int = 2) -> None:
    """
    Set autofocus mode:
      0 = Manual, 1 = Auto (single), 2 = Continuous.
    """
    try:
        picam.set_controls({"AfMode": int(mode)})
    except Exception as e:
        print(f"set_af_mode error: {e}", flush=True)

def trigger_autofocus() -> None:
    """
    Trigger a single autofocus cycle (useful during settle when AfMode=1).
    """
    try:
        picam.set_controls({"AfTrigger": 1})  # start AF cycle
    except Exception as e:
        print(f"trigger_autofocus error: {e}", flush=True)

# =============================================================================
# Internal conversion utilities
# =============================================================================
def _to_rgb(arr: np.ndarray) -> np.ndarray:
    """
    Normalize any returned frame to RGB (HxWx3, uint8).
    Although we requested RGB888, guard against BGRA/BGR inputs.
    """
    if arr.ndim == 3:
        h, w, c = arr.shape
        if c == 4:
            return cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)
        elif c == 3:
            # If already RGB this becomes a no-op; if BGR it flips channels.
            return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        else:
            return arr[:, :, :3].copy()
    # Grayscale to RGB
    return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)

# =============================================================================
# Live View (lores stream → QImage for GUI)
# =============================================================================
def get_frame() -> QImage:
    """
    Return a QImage (RGB888) for the preview label using the lores stream.
    """
    try:
        with _cam_lock:
            arr = picam.capture_array("lores")  # 640x360; fast preview
    except Exception as e:
        print(f"get_frame error: {e}", flush=True)
        return QImage()

    rgb = _to_rgb(arr)
    h, w = rgb.shape[:2]
    rgb_c = np.ascontiguousarray(rgb)
    bytes_per_line = w * 3
    qimg = QImage(rgb_c.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return qimg.copy()  # detach from numpy buffer

# =============================================================================
# Saving full-res frames (main stream)
# =============================================================================
_last_saved_shape: tuple[int, int] | None = None  # (height, width) of last saved image

def save_image(path: str, grayscale: bool = False) -> bool:
    """
    Capture the current full-resolution frame from 'main' and save to 'path'.

    - If grayscale=True: save single-channel grayscale (best for IR quant).
    - If '.tif' or '.tiff' and tifffile is installed → write TIFF (lossless zlib).
    - Otherwise → OpenCV (PNG/JPEG depending on extension).

    Records the last saved shape for downstream CSV logging.
    """
    try:
        global _last_saved_shape  # <-- declare ONCE, before any assignment

        with _cam_lock:
            arr = picam.capture_array("main")  # full-res
        rgb = _to_rgb(arr)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        ext = Path(path).suffix.lower()

        if grayscale:
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape[:2]
            _last_saved_shape = (h, w)

            if ext in (".tif", ".tiff") and tiff is not None:
                tiff.imwrite(path, gray, photometric="minisblack", compression="zlib")
                return True

            return cv2.imwrite(path, gray)

        # RGB save
        h, w = rgb.shape[:2]
        _last_saved_shape = (h, w)

        if ext in (".tif", ".tiff") and tiff is not None:
            tiff.imwrite(path, rgb, photometric="rgb", compression="zlib")
            return True

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return cv2.imwrite(path, bgr)

    except Exception as e:
        print(f"save_image error: {e}", flush=True)
        return False

# =============================================================================
# Capture metadata (for CSV logging)
# =============================================================================
def get_metadata() -> dict:
    """
    Return a dictionary of useful capture metadata from Picamera2.
    Keys may include (depending on pipeline):
      - 'AeEnable', 'ExposureTime' (µs), 'AnalogueGain', 'AwbEnable'
    """
    out = {}
    try:
        with _cam_lock:
            md = picam.capture_metadata()  # Picamera2 metadata dict
        # Normalize common fields (add more here if you need them)
        out["AeEnable"]      = md.get("AeEnable", None)
        out["ExposureTime"]  = md.get("ExposureTime", None)   # microseconds
        out["AnalogueGain"]  = md.get("AnalogueGain", None)
        out["AwbEnable"]     = md.get("AwbEnable", None)
        
        
        # NEW: focus / autofocus diagnostics (may be absent on some builds)
        out["LensPosition"] = md.get("LensPosition", None)
        out["AfState"] = md.get("AfState", None)
        out["FocusFoM"] = md.get("FocusFoM", None)

    except Exception as e:
        print(f"get_metadata error: {e}", flush=True)
    return out

def get_last_saved_shape() -> tuple[int, int] | None:
    """Return (height, width) of the last saved full-res image, or None."""
    return _last_saved_shape
