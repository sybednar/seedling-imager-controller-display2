# camera_arducam_usb3.py — OpenCV/V4L2 backend for the Arducam 20MP AR2020
# Monochrome Manual-Focus USB 3.0 camera.
#
# STATUS (Sept 2026): validated against physical hardware. Rear IR is locked
# to fixed manual exposure/gain — see apply_ir_transmission_preset() below —
# because this sensor's onboard auto-exposure was confirmed to converge
# poorly/inconsistently against the bright, uniform Rear IR transmission
# scene (one capture had 54% of pixels clipped to white; the very next
# capture at identical logged settings had 0% clipped).
#
# Before relying on this backend for a real run:
#   1. Connect the camera, install v4l2-utils (`sudo apt install v4l2-utils`
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
#      `v4l2-ctl --list-formats-ext -d <device>` output. Confirmed on
#      hardware: 5120x3840 @ 8/5 fps (full) and 1280x960 up to 90 fps
#      (preview), plus 3840x2160, 2560x1920, and 1920x1080 intermediate
#      modes. If the full 5120x3840 mode is missing from that listing, the
#      USB3 cable/port is not delivering full SuperSpeed bandwidth.
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
#     have.
#   - Exposure/gain are driven via `v4l2-ctl` subprocess calls against
#     standard V4L2_CID_* controls rather than libcamera controls.
#   - This sensor's real V4L2 "gain" control range is 100-2200 (integer),
#     confirmed via print_diagnostics() on real hardware — NOT the ~1.0-16.0
#     float scale used by camera_picamera2.py. Front IR is unused in the
#     current hardware (Front IR illumination was removed from the system),
#     but its gain default is kept on the same 100-2200 scale for
#     consistency in case it's ever reintroduced.

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
# the same file regardless of which one is currently selected. EXCEPTION:
# Rear IR exposure time uses the plain 'RearIR_ExposureTime' key shared with
# camera_picamera2.py (microseconds mean the same thing on any sensor, and
# it's set from the same Camera Config dialog field for both backends). Gain
# is never shared — see the note above about the 100-2200 vs 1.0-16.0 scale
# mismatch.
# =============================================================================
DEFAULTS = {
    "CameraBackend": "arducam_usb3",

    "Arducam_DevicePath":    None,   # None = auto-detect by sysfs device name
    "Arducam_PreviewWidth":  1280,
    "Arducam_PreviewHeight": 960,
    "Arducam_FullWidth":     5120,
    "Arducam_FullHeight":    3840,

    "Arducam_AeEnable":      False,  # CONFIRMED on real hardware (Sept 2026): this
                                     # sensor's onboard AE converges poorly/
                                     # inconsistently on the bright, uniform Rear IR
                                     # scene, and Rear IR is permanently locked to
                                     # fixed manual exposure/gain regardless of this
                                     # flag anyway (see _rear_ir_lock_manual). Leaving
                                     # this True caused apply_settings()/start_camera()
                                     # to repeatedly try (and always fail — wrong enum
                                     # value for this device) to re-enable AE, logged
                                     # as harmless but noisy "v4l2_set(exposure_auto=3)
                                     # ... exit status 255" errors on every Live View
                                     # start and every capture restore.
    "Arducam_ExposureUs":    20000,  # manual exposure, µs (used when AE off)
    "Arducam_Gain":          100,    # CONFIRMED on real hardware (Sept 2026): this
                                     # sensor's V4L2 "gain" control range is 100-2200
                                     # (integer), NOT the ~1.0-16.0 float scale used by
                                     # camera_picamera2.py. 100 = the device's declared
                                     # minimum (no additional gain).

    # Front IR (reflectance) overrides — mirrors camera_picamera2.py's FrontIR_* naming.
    # Unused in the current hardware (Front IR illumination was removed), kept for
    # interface parity in case it's reintroduced.
    "Arducam_FrontIR_AeEnable":   True,
    "Arducam_FrontIR_ExposureUs": 20000,
    "Arducam_FrontIR_Gain":       100,

    # Rear IR (transmission) — always manual (see apply_ir_transmission_preset
    # below). Exposure time is shared with camera_picamera2.py via the plain
    # 'RearIR_ExposureTime' key (microseconds mean the same thing on any
    # sensor, so one Camera Config dialog field drives both backends). Gain
    # is NOT shared — this sensor's real range (100-2200) has nothing to do
    # with Picamera2's ~1.0-16.0 scale — so it gets its own key here, with
    # its own dialog field shown only when this backend is selected.
    "Arducam_RearIR_Gain":        100,

    # LIVE VIEW-only Rear IR exposure/gain — kept separate from the capture
    # values above. Confirmed on real hardware (Sept 2026): the 1280x960
    # preview stream and the 5120x3840 full-resolution capture are NOT
    # equally sensitive at identical exposure/gain register values — the
    # lower-resolution preview reads out effectively brighter (most likely
    # sensor pixel binning at the lower resolution) than a full 1:1 readout
    # at full resolution. A single shared manual value can't look right in
    # both places: exposure/gain tuned so the full-res CAPTURE looks
    # correct makes Live View look considerably brighter, potentially blown
    # out. See apply_ir_transmission_preset_liveview() below.
    "Arducam_RearIR_LiveView_ExposureUs": 4000,
    "Arducam_RearIR_LiveView_Gain":       100,
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
    global _rear_ir_lock_manual
    _rear_ir_lock_manual = False  # only Rear IR is locked to manual; Front IR is unaffected
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Arducam_AeEnable"] = bool(saved.get("Arducam_FrontIR_AeEnable", True))
    if not s["Arducam_AeEnable"]:
        s["Arducam_ExposureUs"] = int(saved.get("Arducam_FrontIR_ExposureUs", 20000))
        s["Arducam_Gain"] = float(saved.get("Arducam_FrontIR_Gain", 100))
    return s


def apply_ir_transmission_preset(base: dict | None) -> dict:
    """
    Rear IR (transmission) runtime settings — mirrors the Picamera2 backend's helper.

    Always forced to manual exposure/gain, regardless of any saved AE flag.
    Confirmed on real hardware: this sensor's onboard auto-exposure converges
    poorly/inconsistently against the bright, uniform Rear IR transmission
    scene (one capture had 54% of pixels clipped white, the very next
    capture at identical logged settings had 0% clipped).

    Exposure time (µs) is shared with camera_picamera2.py via the same
    'RearIR_ExposureTime' key in camera_settings.json, set from the Camera
    Config dialog's Rear IR tab — µs means the same physical thing on any
    sensor. Gain is NOT shared (this sensor's 100-2200 range has nothing to
    do with Picamera2's ~1.0-16.0 scale) — it uses its own
    'Arducam_RearIR_Gain' key, shown as its own dialog field only when this
    backend is selected.
    """
    global _rear_ir_lock_manual
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Arducam_AeEnable"] = False
    s["Arducam_ExposureUs"] = int(saved.get("RearIR_ExposureTime", 9000))
    s["Arducam_Gain"] = float(saved.get("Arducam_RearIR_Gain", 100))
    # Lock out any later set_auto_exposure(True) calls for the life of this
    # Rear IR session — experiment_runner.py's shared per-plate settle logic
    # unconditionally re-enables AE every cycle (needed for Picamera2), so
    # without this lock Rear IR would silently drift back to auto exposure
    # on the very next plate.
    _rear_ir_lock_manual = True
    return s


def apply_ir_transmission_preset_liveview(base: dict | None) -> dict:
    """
    Rear IR (transmission) LIVE VIEW runtime settings — deliberately
    SEPARATE from apply_ir_transmission_preset() above, which drives the
    actual saved full-resolution capture.

    Confirmed on real hardware (Sept 2026): with identical exposure_auto/
    exposure/gain register values, the 1280x960 preview stream comes out
    visibly brighter than the 5120x3840 full-resolution capture — most
    likely because the lower-resolution readout mode bins/combines multiple
    photosites per output pixel, effectively increasing sensitivity versus
    a full 1:1 readout. Practical consequence: exposure/gain tuned so the
    real full-res CAPTURE looks correctly exposed will generally make Live
    View look considerably brighter — possibly blown out — at those same
    values, and a Live View that looks right will typically mean the real
    capture is under-exposed. One shared manual value cannot serve both
    purposes at once, so this uses its own 'Arducam_RearIR_LiveView_*' keys
    (own dialog fields in Camera Config's Rear IR tab, shown only when this
    backend is selected) rather than the capture-only 'RearIR_ExposureTime'
    / 'Arducam_RearIR_Gain' keys used by apply_ir_transmission_preset().

    gui.py's apply_liveview_camera_profile() calls this (not the capture
    preset) whenever Live View is (re)started, and camera_config.py's
    on_apply() pushes it immediately so tuning it is visible in Live View
    right away. experiment_runner.py continues to use only the capture
    preset — this function has no effect on what's actually saved.
    """
    global _rear_ir_lock_manual
    s = dict(base) if base else load_settings()
    saved = load_settings()
    s["Arducam_AeEnable"] = False
    s["Arducam_ExposureUs"] = int(saved.get("Arducam_RearIR_LiveView_ExposureUs", 4000))
    s["Arducam_Gain"] = float(saved.get("Arducam_RearIR_LiveView_Gain", 100))
    _rear_ir_lock_manual = True
    return s


def set_manual_exposure_gain(exposure_us: int, gain: float) -> None:
    """
    Explicitly pin exposure and gain (use after AE settling for repeatability).
    """
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

# True while Rear IR is configured for manual exposure/gain (the normal,
# recommended state — see apply_ir_transmission_preset()). While True,
# set_auto_exposure(True) and enable_liveview_boost_for_ir() both become
# no-ops, so nothing can silently re-enable auto-exposure out from under
# Rear IR's fixed manual settings.
_rear_ir_lock_manual = False


def enable_liveview_boost_for_ir(
    target_gain: float = 8.0,
    target_exposure_us: int = 20000,
    mode: str = "Front IR",
) -> None:
    global _liveview_boost_active, _liveview_saved
    if _liveview_boost_active:
        return
    if mode in ("Rear IR", "Combined IR") and _rear_ir_lock_manual:
        # Rear IR is locked to fixed manual exposure/gain — the caller
        # (gui.py's apply_liveview_camera_profile()) already applied those
        # exact values via apply_settings() moments before this runs. Skip
        # the generic boost rather than flooring gain/exposure with values
        # scaled for Picamera2's ~1-16 gain range, which is what made Rear
        # IR Live View blow out completely on this camera.
        print("[arducam] Live-view IR boost skipped — Rear IR locked to manual exposure/gain.", flush=True)
        return
    if mode in ("Rear IR", "Combined IR"):
        target_gain = min(target_gain, 4.0)
        target_exposure_us = min(target_exposure_us, 5000)
    try:
        _liveview_saved = dict(get_metadata())
        _set_auto_exposure(True)
        _v4l2_set("gain", int(target_gain))
        _v4l2_set("exposure", _us_to_v4l2_exposure(target_exposure_us))
        _liveview_boost_active = True
        print(
            f"[arducam] Live-view IR boost enabled: mode={mode}, "
            f"gain_floor={target_gain}, exposure_floor={target_exposure_us}µs",
            flush=True,
        )
    except Exception as e:
        print(f"[arducam] liveview boost error: {e}", flush=True)


def disable_liveview_boost() -> None:
    """
    Restore controls saved by enable_liveview_boost_for_ir(). Safe to call multiple times.
    """
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
    UVC devices are ever connected (confirmed: this camera enumerated as
    /dev/video0 on one boot and /dev/video4 on another) — this auto-detect
    already handles that correctly by matching on device name rather than a
    fixed path. Prefer setting 'Arducam_DevicePath' to a
    /dev/v4l/by-id/... symlink instead if you want to pin it explicitly.
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
# V4L2 control access (via v4l2-ctl subprocess)
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
        print("[arducam] v4l2-ctl not found — install the 'v4l2-utils' apt package.", flush=True)
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
        # Typical output line for a plain integer control: "exposure_absolute: 1000"
        # But menu/enum-type controls (e.g. exposure_auto) print the numeric
        # value FOLLOWED by its label: "exposure_auto: 1 (Manual Mode)" — the
        # plain int(...) below crashed on that whole "1 (Manual Mode)" string
        # every single time this was called for exposure_auto, silently
        # returning None from the except block. That in turn meant the
        # pinned_ae re-application added to save_image() never actually ran
        # (its "if pinned_ae is not None" guard was always False), so the
        # exposure_auto mode itself was never re-pinned to manual after the
        # full-resolution reopen — only exposure/gain were, which the driver
        # may ignore while it isn't in manual mode. Confirmed on real
        # hardware: exposure/gain still drifted wildly plate-to-plate even
        # after that first fix. Fix: take only the leading whitespace-
        # separated token (the numeric value) before parsing, which works
        # for both plain-integer and menu/enum-type control output.
        value_str = out.strip().split(":")[-1].strip().split()[0]
        return int(value_str)
    except Exception as e:
        print(f"[arducam] v4l2_get({key}) error: {e}", flush=True)
        return None


def _us_to_v4l2_exposure(exposure_us: int) -> int:
    """UVC exposure_absolute is conventionally in 100µs units — verified on real hardware
    (a 9000µs manual exposure round-trips through get_metadata() as 9000µs)."""
    return max(1, int(round(exposure_us / 100)))


def _v4l2_exposure_to_us(value):
    if value is None:
        return None
    return int(value) * 100


def _set_auto_exposure(enabled: bool):
    name = _resolve_ctrl("exposure_auto")
    if not name:
        return
    # UVC menu convention: 3 = Aperture Priority (auto), 1 = Manual Mode.
    # Some drivers instead use a plain 0/1 boolean for this control —
    # print_diagnostics() will show the menu values actually reported.
    value = 3 if enabled else 1
    _v4l2_set("exposure_auto", value)


def set_auto_exposure(enabled: bool) -> None:
    if enabled and _rear_ir_lock_manual:
        # Rear IR is locked to fixed manual exposure/gain (see
        # apply_ir_transmission_preset) — ignore requests to re-enable AE.
        return
    _set_auto_exposure(bool(enabled))


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
            return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        else:
            return arr[:, :, :3].copy()
    return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)


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
        _v4l2_set("gain", int(settings.get("Arducam_Gain", 100)))


def get_current_settings() -> dict:
    return load_settings()


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

    # Capture whatever exposure/gain is CURRENTLY pinned on the hardware
    # right now (e.g. experiment_runner.py's per-plate AE-pin, set directly
    # via set_manual_exposure_gain() and never written to camera_settings.json)
    # — NOT the same thing as `settings` above, which only reflects the last
    # saved JSON. Confirmed on real hardware: _open_capture() below fully
    # releases and reopens the V4L2 device for the full-resolution still,
    # and reopening can silently reset exposure/gain to the driver's default
    # — which behaves like a brief, uncontrolled auto-exposure moment right
    # as the frame is grabbed. This is why the Live View/settling preview
    # (which never reopens the device) stayed correctly exposed while actual
    # saved captures came out wildly over/under-exposed plate to plate.
    pinned_ae   = _v4l2_get("exposure_auto")
    pinned_exp  = _v4l2_get("exposure")
    pinned_gain = _v4l2_get("gain")

    # Confirmed on real hardware (Sept 2026): re-reading frames from an
    # already-open full-res session does NOT recover a bad capture — a
    # degenerate flat frame (mean=255.00, std=0.01) came back byte-identical
    # on all 6 retries within the same _open_capture() session, while a
    # LATER, completely separate _open_capture() call (the next plate/cycle)
    # produced a real image with zero retries needed. So this isn't a
    # transient dropped USB packet that clears on a re-read — it's the
    # device getting stuck delivering a static placeholder for as long as
    # that particular full-res session stays open. The exposure_auto/
    # exposure/gain CONTROLS read back correctly every time regardless (see
    # the verify prints below) — this is not an exposure problem. Since only
    # a fresh close+reopen has any chance of clearing it, retry by fully
    # closing and reopening the device from scratch, not just re-reading.
    _DISCARD_FRAMES = 5
    _FRAME_PERIOD_S = 0.15
    max_reopen_attempts = 3

    def _frame_looks_valid(g) -> bool:
        # A real Rear IR transmission image (even a poorly-exposed one)
        # always has SOME structure — the darkest real captures we've seen
        # still had std >= ~10. A stuck/placeholder frame reads as
        # near-perfectly flat (std ~0).
        return float(g.std()) > 2.0

    gray = None
    try:
        for reopen_attempt in range(1, max_reopen_attempts + 1):
            # Force a REAL reopen — _open_capture() no-ops if _cap is
            # already open at this exact size, so an already-open full-res
            # session (from a previous failed attempt) must be explicitly
            # closed first or this would just keep reading the same stuck
            # stream instead of getting a fresh one.
            stop_camera()
            _open_capture(fw, fh)

            # Re-apply whatever was pinned immediately before the reopen,
            # rather than trusting the driver to have preserved it.
            if pinned_ae is not None:
                _v4l2_set("exposure_auto", pinned_ae)
            if pinned_exp is not None:
                _v4l2_set("exposure", pinned_exp)
            if pinned_gain is not None:
                _v4l2_set("gain", pinned_gain)

            verify_ae   = _v4l2_get("exposure_auto")
            verify_exp  = _v4l2_get("exposure")
            verify_gain = _v4l2_get("gain")
            print(
                f"[arducam] save_image: reopen attempt {reopen_attempt}/{max_reopen_attempts} "
                f"— requested ae={pinned_ae} exp={pinned_exp} gain={pinned_gain}; "
                f"verified ae={verify_ae} exp={verify_exp} gain={verify_gain}",
                flush=True,
            )

            # Discard a modest run-up of frames after the mode switch.
            for _ in range(_DISCARD_FRAMES):
                _read_raw_frame()
                time.sleep(_FRAME_PERIOD_S)

            frame = _read_raw_frame()
            if frame is None:
                print(
                    f"[arducam] save_image: reopen attempt {reopen_attempt} — "
                    f"no frame returned at full resolution.",
                    flush=True,
                )
                continue

            g_check = _to_gray(frame)
            g_mean, g_std = float(g_check.mean()), float(g_check.std())
            if _frame_looks_valid(g_check):
                if reopen_attempt > 1:
                    print(
                        f"[arducam] save_image: got a valid frame after "
                        f"{reopen_attempt} full-reopen attempt(s) "
                        f"(mean={g_mean:.2f}, std={g_std:.2f}).",
                        flush=True,
                    )
                gray = g_check
                break

            print(
                f"[arducam] save_image: reopen attempt {reopen_attempt} produced a "
                f"suspect blank/flat frame (mean={g_mean:.2f}, std={g_std:.2f}) — "
                f"forcing a full close+reopen and trying again.",
                flush=True,
            )
            gray = g_check  # keep the last one in case every attempt fails

        if gray is None:
            print("[arducam] save_image: no frame returned at full resolution", flush=True)
            return False
        if not _frame_looks_valid(gray):
            print(
                "[arducam] save_image: still blank/flat after all reopen attempts; "
                "saving it anyway so the failure is visible rather than lost.",
                flush=True,
            )

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
        # Always try to restore the preview STREAM RESOLUTION, even if the
        # capture above failed — but deliberately do NOT touch the manual
        # exposure/gain controls here.
        #
        # A previous version of this function explicitly re-applied the
        # Live View preset here (to fix an overexposed "experiment
        # snapshot" preview in gui.py). Confirmed on real hardware (Sept
        # 2026) that this was wrong and caused a worse, genuine data-quality
        # regression: experiment_runner.py's AE-stability-gate
        # (_ae_stability_gate) blindly treats whatever exposure/gain is
        # CURRENTLY on the hardware as the correct value to pin for the
        # NEXT plate's capture — necessary because this backend's Rear IR
        # is always locked to fixed manual exposure/gain (see
        # _rear_ir_lock_manual) rather than genuinely running AE. Pushing
        # the Live View preset here meant every plate's capture AFTER the
        # first one in an experiment got silently pinned to the Live View
        # exposure/gain instead of the intended Rear IR capture profile —
        # confirmed via metadata CSV showing SettledExposureTime_us/
        # SettledAnalogueGain alternating away from the correct capture
        # values, with matching under-exposed ~7MB files instead of the
        # correct ~13-14MB ones.
        #
        # Leaving exposure/gain untouched here means the hardware simply
        # keeps whatever was pinned for the capture that just happened —
        # which is exactly right, since nothing between plates should be
        # changing it. The (separate, real, cosmetic) overexposed-preview
        # problem this was trying to fix is instead solved in gui.py's
        # show_experiment_snapshot(), which temporarily borrows the Live
        # View preset for exactly one displayed frame and then explicitly
        # restores the exact exposure/gain that was pinned beforehand —
        # confining the change so it can never leak into the next plate's
        # real capture.
        _open_capture(pw, ph)


# =============================================================================
# Metadata (for CSV logging / AE-stability polling in experiment_runner.py)
# =============================================================================
def get_metadata() -> dict:
    out = {}
    try:
        ae_val = _v4l2_get("exposure_auto")
        out["AeEnable"] = (ae_val == 3) if ae_val is not None else None

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
# Hardware validation helper
# =============================================================================
def print_diagnostics() -> None:
    """
    python3 -c "import camera_arducam_usb3 as c; c.print_diagnostics()"

    Prints the detected device path, every resolution/format the driver
    advertises, and every V4L2 control it exposes, plus which control names
    this module resolved _CTRL_CANDIDATES to. Also useful as a USB3 cable/
    bandwidth check: if 5120x3840 is missing from the resolution list, the
    cable/port is not delivering full USB3 SuperSpeed bandwidth (confirmed
    on real hardware — a marginal cable truncated the list to a single
    1280x960 @ 10fps mode; the camera's own cable showed the complete list
    up to 5120x3840 @ 8fps).
    """
    device = _find_device()
    print(f"Device: {device}")
    if not _v4l2ctl_available():
        print("v4l2-ctl not found. Install with: sudo apt install v4l2-utils")
        return
    print("\n--- v4l2-ctl --list-formats-ext ---")
    subprocess.run(["v4l2-ctl", "-d", device, "--list-formats-ext"])
    print("\n--- v4l2-ctl --list-ctrls ---")
    subprocess.run(["v4l2-ctl", "-d", device, "--list-ctrls"])
    print("\n--- Resolved control names used by this backend ---")
    for key in _CTRL_CANDIDATES:
        print(f"  {key}: {_resolve_ctrl(key)}")
