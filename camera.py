# camera.py — camera backend dispatcher
#
# Selects between the two camera backends based on the persisted
# "CameraBackend" setting in camera_settings.json ("picamera2" [default] or
# "arducam_usb3"), then re-exports that backend's full public interface so
# every other module can keep calling camera.get_frame(), camera.save_image(),
# etc. unchanged regardless of which physical camera is active.
#
# IMPORTANT: only the selected backend module is ever imported. Each backend
# opens/claims its physical camera device at import time (Picamera2() /
# cv2.VideoCapture()), so importing both unconditionally would try to open
# hardware that may not even be present.
#
# Changing the backend (via Camera Config -> General -> Camera Backend, or by
# hand-editing "CameraBackend" in camera_settings.json) requires restarting
# the application — the backend is fixed for the lifetime of the process.

import json
from pathlib import Path

_SETTINGS_PATH = Path("camera_settings.json")
_VALID_BACKENDS = ("picamera2", "arducam_usb3")


def get_camera_backend() -> str:
    """Read the currently configured backend name without importing either backend module."""
    try:
        if _SETTINGS_PATH.exists():
            data = json.loads(_SETTINGS_PATH.read_text())
            name = data.get("CameraBackend", "picamera2")
            if name in _VALID_BACKENDS:
                return name
    except Exception:
        pass
    return "picamera2"


def set_camera_backend(name: str) -> bool:
    """
    Persist a new backend selection. Does NOT switch the running process —
    the change only takes effect after restarting the application.
    """
    if name not in _VALID_BACKENDS:
        raise ValueError(f"Unknown camera backend {name!r}; must be one of {_VALID_BACKENDS}")
    try:
        data = {}
        if _SETTINGS_PATH.exists():
            data = json.loads(_SETTINGS_PATH.read_text())
        data["CameraBackend"] = name
        _SETTINGS_PATH.write_text(json.dumps(data, indent=2))
        return True
    except Exception as e:
        print(f"[camera] set_camera_backend error: {e}", flush=True)
        return False


def get_camera_backend_active_this_process() -> str:
    """
    Which backend this already-running process actually loaded — may differ
    from get_camera_backend() (the currently *saved* setting) if the setting
    was changed after the app started, since switching backends requires a
    restart. Used by camera_config.py to show a restart-required notice.
    """
    return _ACTIVE_BACKEND


_ACTIVE_BACKEND = get_camera_backend()

if _ACTIVE_BACKEND == "arducam_usb3":
    from camera_arducam_usb3 import (
        DEFAULTS, SETTINGS_PATH,
        load_settings, save_settings,
        apply_ir_quant_preset, apply_ir_transmission_preset,
        set_manual_exposure_gain,
        enable_liveview_boost_for_ir, disable_liveview_boost,
        start_camera, stop_camera,
        apply_settings, get_current_settings,
        set_auto_exposure, set_manual_focus, set_af_mode, trigger_autofocus,
        get_frame, save_image, get_metadata, get_last_saved_shape,
        print_diagnostics,
    )
else:
    from camera_picamera2 import (
        DEFAULTS, SETTINGS_PATH,
        load_settings, save_settings,
        apply_ir_quant_preset, apply_ir_transmission_preset,
        set_manual_exposure_gain,
        enable_liveview_boost_for_ir, disable_liveview_boost,
        start_camera, stop_camera,
        apply_settings, get_current_settings,
        set_auto_exposure, set_manual_focus, set_af_mode, trigger_autofocus,
        get_frame, save_image, get_metadata, get_last_saved_shape,
    )

print(f"[camera] Active backend: {_ACTIVE_BACKEND}", flush=True)
