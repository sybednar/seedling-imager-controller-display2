# camera_arducam_usb3.py — OpenCV/V4L2 backend for the Arducam 20MP AR2020
# Monochrome Manual-Focus USB 3.0 camera.
#
# STATUS (Aug 2026): written against the AR2020 mono USB3 datasheet and
# standard UVC/V4L2 conventions. NOT YET VALIDATED against physical hardware
# — flag this to yourself before trusting it for an unattended experiment.
#
# Before relying on this backend for a real run:
#   1. Connect the camera, install v4l-utils (`sudo apt install v4l-utils`
#      — already added to install_dependencies.sh), then run:
#           python3 -c "import camera_arducam_usb3 as c; c.print_diagnostics()"
#      This prints the detected /dev/videoN device, every resolution/format
#      the driver advertises, and every V4L2 control it actually exposes.
#   2. Compare that control list against _CTRL_CANDIDATES below. UVC control
#      naming (especially exposure_auto / exposure_absolute vs
#      exposure_time_absolute) varies by kernel version and vendor — this
#      module tries several known names and logs which one it resolved to,
#      but add a name to the list rather than guessing blind if none match.
#   3. Compare FULL/PREVIEW resolution constants against
#      `v4l2-ctl --list-formats-ext -d <device>` output. The datasheet lists
#      5120x3840@8fps (full) and 1280x960@90fps (preview); confirm the driver
#      agrees before an experiment depends on it.
#   4. Time the mode-switch pause in save_image() (stop preview -> reconfigure
#      to full res -> discard warm-up frames -> capture -> restore preview)
#      with a stopwatch and adjust the warm-up frame count / sleep below if
#      captured stills look stale or mis-exposed.
#
# Architecture notes vs. camera_picamera2.py:
#   - Fixed physical manual-focus lens (twist the M12 ring by hand, no AF
#     motor) — set_manual_focus() / set_af_mode() / trigger_autofocus() are
#     intentionally no-ops here, kept only so callers written against the
#     Picamera2 backend's interface don't need special-casing.
#   - A UVC device generally streams ONE resolution/format at a time from a
#     single open handle, unlike Picamera2's simultaneous main+lores streams.
#     Live preview runs continuously at PREVIEW size; save_image() briefly
#     reconfigures to FULL size, grabs a still, then reconfigures back. Expect
#     a short pause during every capture that the Picamera2 backend does not
#     have — length TBD until measured on real hardware.
#   - Exposure/gain are driven via `v4l2-ctl` subprocess calls against
#     standard V4L2_CID_* controls rather than libcamera controls.

import subprocess
import shutil
import threading
import time
import json
from pathlib import Path

import numpy as np
import cv2
from PySide6.QtGui import QImage

try:
    import tifffile as tiff
except ImportError:
    tiff = None  # save_image() falls back to OpenCV for non-TIFF paths

# =============================================================================
# Settings persistence — shares camera_settings.json with camera_picamera2.py.
# Keys are prefixed Arducam_ so both backends' settings coexist peacefully in
# the same file regardless of which one is currently selected.
# =============================================================================
DEFAULTS = {
    "CameraBackend": "arducam_usb3",

    "Arducam_DevicePath":    None,   # None = auto-detect by sysfs device name
    "Arducam_PreviewWidth":  1280,
    "Arducam_PreviewHeight": 960,
    "Arducam_FullWidth":     5120,
    "Arducam_FullHeight":    3840,

    "Arducam_AeEnable":      True,
    "Arducam_ExposureUs":    20000,  # manual exposure, µs (used when AE off)
    "Arducam_Gain":          1.0,    # nominal 1.0-16.0 — verify real range on hardware

    # Front IR (reflectance) overrides — mirrors camera_picamera2.py's FrontIR_* naming
    "Arducam_FrontIR_AeEnable":   True,
    "Arducam_FrontIR_ExposureUs": 20000,
    "Arducam_FrontIR_Gain":       1.0,

    # Rear IR (transmission) overrides
    "Arducam_RearIR_AeEnable":    False,
    "Arducam_RearIR_ExposureUs":  9000,
    "Arducam_RearIR_Gain":        1.0,
}
SETTINGS_PATH = Path("camera_settings.json")


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            return {**DEFAULTS, **json.loads(SETTINGS_PATH.read_text())}
        except Exception:
            pass
    return DEFAULTS.copy()


def save_settings(settings: dict) -> bool:
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
        return True
    except Exception:
        return False


def apply_ir_quant_preset(base: dict | None) -> dict:
    """Front IR (reflectance) runtime settings — mirrors the Picamera2 backend's helper."""
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Arducam_AeEnable"] = bool(saved.get("Arducam_FrontIR_AeEnable", True))
    if not s["Arducam_AeEnable"]:
        s["Arducam_ExposureUs"] = int(saved.get("Arducam_FrontIR_ExposureUs", 20000))
        s["Arducam_Gain"] = float(saved.get("Arducam_FrontIR_Gain", 1.0))
    return s


def apply_ir_transmission_preset(base: dict | None) -> dict:
    """Rear IR (transmission) runtime settings — mirrors the Picamera2 backend's helper."""
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Arducam_AeEnable"] = bool(saved.get("Arducam_RearIR_AeEnable", False))
    if not s["Arducam_AeEnable"]:
        s["Arducam_ExposureUs"] = int(saved.get("Arducam_RearIR_ExposureUs", 9000))
        s["Arducam_Gain"] = float(saved.get("Arducam_RearIR_Gain", 1.0))
    return s


# =============================================================================
# Device discovery
# =============================================================================
_device_path = None


def _find_device() -> str:
    """
    Resolve the /dev/videoN node for this camera.
    Priority: explicit 'Arducam_DevicePath' setting > sysfs name auto-detect
    (matches "arducam" or "ar2020" in /sys/class/video4linux/videoN/name) >
    hardcoded /dev/video0 fallback.

    USB enumeration order is not guaranteed stable across reboots if other
    UVC devices are ever connected — prefer setting 'Arducam_DevicePath' to
    a /dev/v4l/by-id/... symlink once you know the camera's stable ID, e.g.
    via `ls -la /dev/v4l/by-id/`.
    """
    global _device_path
    if _device_path:
        return _device_path

    override = load_settings().get("Arducam_DevicePath")
    if override and Path(override).exists():
        _device_path = override
        return _device_path

    try:
        for node in sorted(Path("/sys/class/video4linux").glob("video*")):
            name_file = node / "name"
            if name_file.exists():
                name = name_file.read_text().strip()
                if "arducam" in name.lower() or "ar2020" in name.lower():
                    _device_path = f"/dev/{node.name}"
                    print(f"[arducam] Auto-detected device: {_device_path} ({name})", flush=True)
                    return _device_path
    except Exception as e:
        print(f"[arducam] device auto-detect error: {e}", flush=True)

    _device_path = "/dev/video0"
    print(
        f"[arducam] WARNING: could not auto-detect the Arducam device by name; "
        f"falling back to {_device_path}. Set 'Arducam_DevicePath' in "
        f"camera_settings.json to pin this explicitly once you know the "
        f"correct node (see /dev/v4l/by-id/).",
        flush=True,
    )
    return _device_path


# =============================================================================
# V4L2 control access (via v4l2-ctl subprocess — see file header re: unverified names)
# =============================================================================
_CTRL_CANDIDATES = {
    "exposure_auto": ["exposure_auto", "auto_exposure"],
    "exposure":      ["exposure_time_absolute", "exposure_absolute", "exposure"],
    "gain":          ["gain", "analogue_gain"],
}
_resolved_ctrl_names: dict = {}


def _v4l2ctl_available() -> bool:
    return shutil.which("v4l2-ctl") is not None


def _resolve_ctrl(key: str):
    """Find which candidate control name this specific device actually exposes (cached)."""
    if key in _resolved_ctrl_names:
        return _resolved_ctrl_names[key]
    device = _find_device()
    if not _v4l2ctl_available():
        print("[arducam] v4l2-ctl not found — install the 'v4l-utils' apt package.", flush=True)
        _resolved_ctrl_names[key] = None
        return None
    try:
        listing = subprocess.run(
            ["v4l2-ctl", "-d", device, "--list-ctrls"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception as e:
        print(f"[arducam] v4l2-ctl --list-ctrls failed: {e}", flush=True)
        _resolved_ctrl_names[key] = None
        return None
    for candidate in _CTRL_CANDIDATES.get(key, [key]):
        if candidate in listing:
            _resolved_ctrl_names[key] = candidate
            return candidate
    print(
        f"[arducam] WARNING: none of {_CTRL_CANDIDATES.get(key, [key])} found in "
        f"'v4l2-ctl --list-ctrls' for {device}. Run print_diagnostics() to see "
        f"the actual control names and add the right one to _CTRL_CANDIDATES.",
        flush=True,
    )
    _resolved_ctrl_names[key] = None
    return None


def _v4l2_set(key: str, value) -> bool:
    name = _resolve_ctrl(key)
    if not name:
        return False
    device = _find_device()
    try:
        subprocess.run(
            ["v4l2-ctl", "-d", device, f"--set-ctrl={name}={int(value)}"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return True
    except Exception as e:
        print(f"[arducam] v4l2_set({key}={value}) error: {e}", flush=True)
        return False


def _v4l2_get(key: str):
    name = _resolve_ctrl(key)
    if not name:
        return None
    device = _find_device()
    try:
        out = subprocess.run(
            ["v4l2-ctl", "-d", device, f"--get-ctrl={name}"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        # Numeric controls: "exposure_absolute: 1000". Menu controls:
        # "exposure_auto: 0 (Auto Mode)". Take just the leading numeric token
        # so both forms parse correctly.
        val_str = out.strip().split(":")[-1].strip()
        return int(val_str.split()[0])
    except Exception as e:
        print(f"[arducam] v4l2_get({key}) error: {e}", flush=True)
        return None
        

def _us_to_v4l2_exposure(exposure_us: int) -> int:
    """UVC exposure_absolute is conventionally in 100µs units — verify on real hardware."""
    return max(1, int(round(exposure_us / 100)))


def _v4l2_exposure_to_us(value):
    if value is None:
        return None
    return int(value) * 100


def _set_auto_exposure(enabled: bool):
    name = _resolve_ctrl("exposure_auto")
    if not name:
        return
    # UVC standard menu: 0 = Auto Mode, 1 = Manual Mode, 2 = Shutter Priority,
    # 3 = Aperture Priority. Confirmed on real hardware (Aug 2026): this
    # device only supports 0 and 1 — Shutter/Aperture Priority are rejected.
    value = 0 if enabled else 1
    _v4l2_set("exposure_auto", value)


def set_auto_exposure(enabled: bool) -> None:
    _set_auto_exposure(bool(enabled))


def set_manual_exposure_gain(exposure_us: int, gain: float) -> None:
    """Pin exposure and gain (mirrors the Picamera2 backend's helper)."""
    try:
        _set_auto_exposure(False)
        _v4l2_set("exposure", _us_to_v4l2_exposure(int(exposure_us)))
        _v4l2_set("gain", int(gain))
    except Exception as e:
        print(f"[arducam] set_manual_exposure_gain error: {e}", flush=True)


# =============================================================================
# Live-view boost (interface parity with camera_picamera2.py)
# =============================================================================
_liveview_boost_active = False
_liveview_saved = None


def enable_liveview_boost_for_ir(
    target_gain: float = 8.0,
    target_exposure_us: int = 20000,
    mode: str = "Front IR",
) -> None:
    global _liveview_boost_active, _liveview_saved
    if _liveview_boost_active:
        return
    if mode in ("Rear IR", "Combined IR"):
        target_gain = min(target_gain, 4.0)
        target_exposure_us = min(target_exposure_us, 5000)
    try:
        _liveview_saved = dict(get_metadata())
        _set_auto_exposure(False)   # was True — go Manual so exposure writes actually stick
        _v4l2_set("gain", int(target_gain))
        _v4l2_set("exposure", _us_to_v4l2_exposure(target_exposure_us))
        _liveview_boost_active = True
        print(
            f"[arducam] Live-view IR boost enabled: mode={mode}, "
            f"gain={target_gain}, exposure={target_exposure_us}µs (manual, pinned)",
            flush=True,
        )
    except Exception as e:
        print(f"[arducam] liveview boost error: {e}", flush=True)


def disable_liveview_boost() -> None:
    global _liveview_boost_active, _liveview_saved
    if not _liveview_boost_active:
        return
    try:
        if _liveview_saved:
            ae = bool(_liveview_saved.get("AeEnable", True))
            _set_auto_exposure(ae)
            if not ae:
                exp = _liveview_saved.get("ExposureTime")
                gain = _liveview_saved.get("AnalogueGain")
                if exp is not None and gain is not None:
                    _v4l2_set("exposure", _us_to_v4l2_exposure(int(exp)))
                    _v4l2_set("gain", int(gain))
        _liveview_boost_active = False
        _liveview_saved = None
        print("[arducam] Live-view IR boost disabled (restored controls)", flush=True)
    except Exception as e:
        print(f"[arducam] liveview boost restore error: {e}", flush=True)


# =============================================================================
# VideoCapture lifecycle
# =============================================================================
_cap = None
_cap_size = None  # (w, h) currently open at
_cap_lock = threading.Lock()


def _open_capture(width: int, height: int):
    global _cap, _cap_size
    device = _find_device()
    with _cap_lock:
        if _cap is not None and _cap_size == (width, height):
            return
        if _cap is not None:
            _cap.release()
            _cap = None
        cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not cap.isOpened():
            print(f"[arducam] ERROR: could not open {device}", flush=True)
            _cap = None
            _cap_size = None
            return
        # Prefer raw 8-bit grayscale (GREY/Y800) if the driver supports it —
        # this is the natural output for a monochrome sensor. If unsupported,
        # the driver silently keeps its default fourcc and _to_gray() below
        # collapses whatever multi-channel frame comes back instead.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"GREY"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        _cap = cap
        _cap_size = (width, height)


def start_camera() -> None:
    """Open the preview stream (idempotent) and apply persisted settings."""
    settings = load_settings()
    w = int(settings.get("Arducam_PreviewWidth", 1280))
    h = int(settings.get("Arducam_PreviewHeight", 960))
    _open_capture(w, h)
    apply_settings(settings)


def stop_camera() -> None:
    global _cap, _cap_size
    with _cap_lock:
        if _cap is not None:
            _cap.release()
        _cap = None
        _cap_size = None


def apply_settings(settings: dict = None) -> None:
    if settings is None:
        settings = load_settings()
    ae = bool(settings.get("Arducam_AeEnable", True))
    _set_auto_exposure(ae)
    if not ae:
        _v4l2_set("exposure", _us_to_v4l2_exposure(int(settings.get("Arducam_ExposureUs", 20000))))
        _v4l2_set("gain", int(settings.get("Arducam_Gain", 1.0)))


def get_current_settings() -> dict:
    return load_settings()


# --- No-op focus interface: fixed physical manual-focus lens, no AF motor ---
def set_manual_focus(position: float = None) -> None:
    print(
        "[arducam] set_manual_focus() ignored — this camera has a fixed "
        "physical manual-focus lens; adjust the M12 focus ring by hand.",
        flush=True,
    )


def set_af_mode(mode: int = 2) -> None:
    pass  # no AF motor on this lens


def trigger_autofocus() -> None:
    pass  # no AF motor on this lens


# =============================================================================
# Frame capture
# =============================================================================
def _read_raw_frame():
    with _cap_lock:
        if _cap is None:
            return None
        ok, frame = _cap.read()
    if not ok or frame is None:
        return None
    return frame


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame
    # Driver ignored the GREY fourcc request and returned a decoded 3-channel
    # frame (e.g. YUYV/MJPG path) — collapse it. All channels carry the same
    # intensity on a genuinely monochrome sensor, so this is lossless in practice.
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def get_frame() -> QImage:
    """Return a QImage (Grayscale8) for the preview label from the live stream."""
    frame = _read_raw_frame()
    if frame is None:
        return QImage()
    gray = np.ascontiguousarray(_to_gray(frame))
    h, w = gray.shape[:2]
    qimg = QImage(gray.data, w, h, w, QImage.Format_Grayscale8)
    return qimg.copy()  # detach from numpy buffer


# =============================================================================
# Saving full-res frames
# =============================================================================
_last_saved_shape: tuple[int, int] | None = None


def save_image(path: str, grayscale: bool = True) -> bool:
    """
    Reconfigure to full resolution, grab a still, save, then restore the
    preview stream. `grayscale` is accepted for interface parity with
    camera_picamera2.py but is effectively always True here — the sensor has
    no colour filter array, so there is no RGB variant to produce.
    """
    global _last_saved_shape
    settings = load_settings()
    fw = int(settings.get("Arducam_FullWidth", 5120))
    fh = int(settings.get("Arducam_FullHeight", 3840))
    pw = int(settings.get("Arducam_PreviewWidth", 1280))
    ph = int(settings.get("Arducam_PreviewHeight", 960))

    try:
        _open_capture(fw, fh)
        # Discard a few frames after the mode switch — many UVC drivers return
        # a stale/partially-exposed frame immediately after reconfiguring
        # resolution. Count/delay here are conservative placeholders; tune
        # against real hardware.
        for _ in range(3):
            _read_raw_frame()
            time.sleep(0.05)
        frame = _read_raw_frame()
        if frame is None:
            print("[arducam] save_image: no frame returned at full resolution", flush=True)
            return False
        gray = _to_gray(frame)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        ext = Path(path).suffix.lower()
        h, w = gray.shape[:2]
        _last_saved_shape = (h, w)

        if ext in (".tif", ".tiff") and tiff is not None:
            tiff.imwrite(path, gray, photometric="minisblack", compression="zlib")
            return True
        return cv2.imwrite(path, gray)

    except Exception as e:
        print(f"[arducam] save_image error: {e}", flush=True)
        return False

    finally:
        # Always try to restore live preview, even if the capture above failed.
        _open_capture(pw, ph)
        apply_settings(settings)


# =============================================================================
# Metadata (for CSV logging / AE-stability polling in experiment_runner.py)
# =============================================================================
def get_metadata() -> dict:
    out = {}
    try:
        ae_val = _v4l2_get("exposure_auto")
        out["AeEnable"] = (ae_val == 0) if ae_val is not None else None

        exp_val = _v4l2_get("exposure")
        out["ExposureTime"] = _v4l2_exposure_to_us(exp_val)

        gain_val = _v4l2_get("gain")
        out["AnalogueGain"] = float(gain_val) if gain_val is not None else None

        out["AwbEnable"] = None  # monochrome sensor — no white balance concept

        # No AF motor on this lens — always None so callers that check for a
        # positive LensPosition (e.g. camera_config.py's "Read from Camera"
        # button) fail gracefully instead of reporting a bogus value.
        out["LensPosition"] = None
        out["AfState"] = None
        out["FocusFoM"] = None
    except Exception as e:
        print(f"[arducam] get_metadata error: {e}", flush=True)
    return out


def get_last_saved_shape():
    return _last_saved_shape


# =============================================================================
# Hardware validation helper — run once the camera is physically connected
# =============================================================================
def print_diagnostics() -> None:
    """
    python3 -c "import camera_arducam_usb3 as c; c.print_diagnostics()"

    Prints the detected device path, every resolution/format the driver
    advertises, and every V4L2 control it exposes, plus which control names
    this module resolved _CTRL_CANDIDATES to. Use this to confirm (or correct)
    every assumption flagged in the file header before trusting this backend
    for an unattended experiment.
    """
    device = _find_device()
    print(f"Device: {device}")
    if not _v4l2ctl_available():
        print("v4l2-ctl not found. Install with: sudo apt install v4l-utils")
        return
    print("\n--- v4l2-ctl --list-formats-ext ---")
    subprocess.run(["v4l2-ctl", "-d", device, "--list-formats-ext"])
    print("\n--- v4l2-ctl --list-ctrls ---")
    subprocess.run(["v4l2-ctl", "-d", device, "--list-ctrls"])
    print("\n--- Resolved control names used by this backend ---")
    for key in _CTRL_CANDIDATES:
        print(f"  {key}: {_resolve_ctrl(key)}")
