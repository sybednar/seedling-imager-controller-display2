# camera_config.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QCheckBox, QDoubleSpinBox, QSpinBox, QFrame,
    QTabWidget, QWidget, QComboBox,
)
from PySide6.QtCore import Qt
import json
from pathlib import Path
import camera   # needed for "Read from Camera" button and backend get/set helpers
DEFAULTS = {
    "CameraBackend":       "picamera2",   # ADDED 081226 — "picamera2" or "arducam_usb3"
    "AeEnable":            True,
    "ExposureTime":        20000,
    "AnalogueGain":        1.0,
    "AwbEnable":           True,
    "Contrast":            1.0,
    "Brightness":          0.0,
    "Saturation":          1.0,
    "Sharpness":           1.0,
    "NoiseReductionMode":  0,
    "HdrEnable":           False,
    "ManualFocusEnable":   False,
    "ManualFocusPosition": 7.589,
    # Front IR (reflectance) overrides
    "FrontIR_Saturation":  0.0,
    "FrontIR_AwbEnable":   False,
    "FrontIR_Contrast":    1.10,
    "FrontIR_Sharpness":   1.15,
    "FrontIR_Brightness":  0.0,
    "FrontIR_AeEnable":    True,
    "FrontIR_ExposureTime": 20000,
    "FrontIR_Gain":        1.0,
    # Rear IR (transmission) overrides
    "RearIR_Saturation":   0.0,
    "RearIR_AwbEnable":    False,
    "RearIR_Contrast":     1.5,
    "RearIR_Sharpness":    1.4,
    "RearIR_Brightness":  -0.05,
    "RearIR_AeEnable":     False,
    "RearIR_ExposureTime": 9000,
    "RearIR_Gain":         1.0,
    # Arducam-only Rear IR gain — this camera's real V4L2 gain range is
    # 100-2200, unrelated to Picamera2's RearIR_Gain scale above, so it
    # can't share that key. See camera_arducam_usb3.py.
    "Arducam_RearIR_Gain": 100,
}
SETTINGS_PATH = Path("camera_settings.json")
def load_settings():
    if SETTINGS_PATH.exists():
        try:
            return {**DEFAULTS, **json.loads(SETTINGS_PATH.read_text())}
        except Exception:
            pass
    return DEFAULTS.copy()
def save_settings(settings: dict):
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
        return True
    except Exception:
        return False
# ---------------------------------------------------------------------------
# Helper: build a compact QFormLayout inside a plain QWidget (one tab page)
# ---------------------------------------------------------------------------
def _tab_page() -> tuple[QWidget, QFormLayout]:
    w = QWidget()
    fl = QFormLayout(w)
    fl.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    fl.setHorizontalSpacing(10)
    fl.setVerticalSpacing(6)
    fl.setContentsMargins(12, 10, 12, 10)
    return w, fl
class CameraConfigDialog(QDialog):
    def __init__(self, current_settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Configuration")
        self.setMinimumWidth(520)
        self.settings = load_settings() if current_settings is None else {**DEFAULTS, **current_settings}
        main = QVBoxLayout(self)
        main.setSpacing(6)
        main.setContentsMargins(8, 8, 8, 8)
        tabs = QTabWidget()
        main.addWidget(tabs, stretch=1)
        # ------------------------------------------------------------------ #
        # Tab 1 – General                                                      #
        # ------------------------------------------------------------------ #
        gen_w, gen = _tab_page()
        # --- Camera Backend selector (081226 addition) ---
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Raspberry Pi Camera Module 3 (Picamera2)", userData="picamera2")
        self.backend_combo.addItem("Arducam 20MP AR2020 Mono USB3", userData="arducam_usb3")
        _saved_backend = camera.get_camera_backend()
        _running_backend = camera.get_camera_backend_active_this_process()
        _idx = self.backend_combo.findData(_saved_backend)
        self.backend_combo.setCurrentIndex(_idx if _idx >= 0 else 0)
        gen.addRow(QLabel("Camera Backend:"), self.backend_combo)
        self.backend_status_lbl = QLabel(f"Active this session: {_running_backend}")
        self.backend_status_lbl.setStyleSheet("color: #90A4AE; font-size: 12px;")
        gen.addRow(QLabel(""), self.backend_status_lbl)
        backend_note = QLabel(
            "Changing this takes effect after restarting the application —\n"
            "the active backend is fixed for the lifetime of the running process."
        )
        backend_note.setStyleSheet("color: #90A4AE; font-size: 12px;")
        gen.addRow(QLabel(""), backend_note)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color: #455A64;")
        gen.addRow(sep)
        self.ae_chk = QCheckBox("Enable Auto Exposure")
        self.ae_chk.setChecked(bool(self.settings["AeEnable"]))
        gen.addRow(QLabel("Auto Exposure (AE):"), self.ae_chk)
        self.exp_spin = QSpinBox()
        self.exp_spin.setRange(100, 200000)
        self.exp_spin.setSingleStep(500)          # 500 µs per click
        self.exp_spin.setValue(int(self.settings["ExposureTime"]))
        gen.addRow(QLabel("Exposure Time (µs):"), self.exp_spin)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(1.0, 16.0); self.gain_spin.setSingleStep(0.1)
        self.gain_spin.setValue(float(self.settings["AnalogueGain"]))
        gen.addRow(QLabel("Analogue Gain:"), self.gain_spin)
        self.awb_chk = QCheckBox("Enable Auto White Balance")
        self.awb_chk.setChecked(bool(self.settings["AwbEnable"]))
        gen.addRow(QLabel("AWB:"), self.awb_chk)
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.5, 2.0); self.contrast_spin.setSingleStep(0.1)
        self.contrast_spin.setValue(float(self.settings["Contrast"]))
        gen.addRow(QLabel("Contrast:"), self.contrast_spin)
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setRange(-1.0, 1.0); self.brightness_spin.setSingleStep(0.1)
        self.brightness_spin.setValue(float(self.settings["Brightness"]))
        gen.addRow(QLabel("Brightness:"), self.brightness_spin)
        self.saturation_spin = QDoubleSpinBox()
        self.saturation_spin.setRange(0.0, 2.0); self.saturation_spin.setSingleStep(0.1)
        self.saturation_spin.setValue(float(self.settings["Saturation"]))
        gen.addRow(QLabel("Saturation:"), self.saturation_spin)
        self.sharpness_spin = QDoubleSpinBox()
        self.sharpness_spin.setRange(0.0, 2.0); self.sharpness_spin.setSingleStep(0.1)
        self.sharpness_spin.setValue(float(self.settings["Sharpness"]))
        gen.addRow(QLabel("Sharpness:"), self.sharpness_spin)
        self.nr_spin = QSpinBox()
        self.nr_spin.setRange(0, 3)
        self.nr_spin.setValue(int(self.settings["NoiseReductionMode"]))
        gen.addRow(QLabel("Noise Reduction Mode:"), self.nr_spin)
        self.hdr_chk = QCheckBox("Enable HDR (3MP only)")
        self.hdr_chk.setChecked(bool(self.settings["HdrEnable"]))
        gen.addRow(QLabel("HDR:"), self.hdr_chk)
        tabs.addTab(gen_w, "General")
        # ------------------------------------------------------------------ #
        # Tab 2 – Focus                                                        #
        # ------------------------------------------------------------------ #
        foc_w, foc = _tab_page()
        self.manual_focus_chk = QCheckBox(
            "Use manual focus  (required with 940 nm bandpass filter)"
        )
        self.manual_focus_chk.setChecked(bool(self.settings["ManualFocusEnable"]))
        foc.addRow(QLabel("Manual Focus:"), self.manual_focus_chk)
        self.focus_pos_spin = QDoubleSpinBox()
        self.focus_pos_spin.setRange(0.0, 20.0)
        self.focus_pos_spin.setSingleStep(0.1); self.focus_pos_spin.setDecimals(3)
        self.focus_pos_spin.setValue(float(self.settings["ManualFocusPosition"]))
        self.focus_pos_spin.setToolTip(
            "Lens position in diopters (1 / focus distance in metres).\n"
            "0.0 = infinity.  Typical petri plate at 13 cm ≈ 7.589 diopters.\n"
            "Use 'Read from Camera' after auto-focusing in Live View."
        )
        foc.addRow(QLabel("Lens Position (diopters):"), self.focus_pos_spin)
        self.focus_pos_spin.setEnabled(self.manual_focus_chk.isChecked())
        self.manual_focus_chk.toggled.connect(self.focus_pos_spin.setEnabled)
        self.read_focus_btn = QPushButton("Read Current Position from Camera")
        self.read_focus_btn.setToolTip(
            "Turn on Live View and let auto-focus settle on the petri plate,\n"
            "then press this button to capture the current LensPosition value.\n"
            "Works best with the bandpass filter temporarily removed."
        )
        self.read_focus_btn.clicked.connect(self.on_read_focus)
        foc.addRow(QLabel(""), self.read_focus_btn)
        self.focus_hint_lbl = QLabel(
            "LensPosition 7.589 D ≈ 13 cm  |  0.0 D = infinity\n"
            "PDAF does not work through the 940 nm bandpass filter;\n"
            "manual focus must be enabled for captured images to be sharp."
        )
        self.focus_hint_lbl.setStyleSheet("color: #90A4AE; font-size: 13px;")
        foc.addRow(QLabel(""), self.focus_hint_lbl)
        self.focus_status_lbl = QLabel("")
        self.focus_status_lbl.setStyleSheet("color: #FFD600; font-size: 13px;")
        foc.addRow(QLabel(""), self.focus_status_lbl)
        tabs.addTab(foc_w, "Focus")
        # ------------------------------------------------------------------ #
        # Tab 3 – Front IR (Reflectance)                                       #
        # ------------------------------------------------------------------ #
        fir_w, fir = _tab_page()
        self.fir_ae_chk = QCheckBox("AE on")
        self.fir_ae_chk.setChecked(bool(self.settings.get("FrontIR_AeEnable", True)))
        fir.addRow(QLabel("AE:"), self.fir_ae_chk)
        self.fir_exp = QSpinBox()
        self.fir_exp.setRange(100, 200000)
        self.fir_exp.setSingleStep(500)           # 500 µs per click
        self.fir_exp.setValue(int(self.settings.get("FrontIR_ExposureTime", 20000)))
        fir.addRow(QLabel("Exposure (µs):"), self.fir_exp)
        self.fir_contrast = QDoubleSpinBox()
        self.fir_contrast.setRange(0.5, 2.0); self.fir_contrast.setSingleStep(0.05)
        self.fir_contrast.setValue(float(self.settings.get("FrontIR_Contrast", 1.10)))
        fir.addRow(QLabel("Contrast:"), self.fir_contrast)
        self.fir_sharpness = QDoubleSpinBox()
        self.fir_sharpness.setRange(0.0, 2.0); self.fir_sharpness.setSingleStep(0.05)
        self.fir_sharpness.setValue(float(self.settings.get("FrontIR_Sharpness", 1.15)))
        fir.addRow(QLabel("Sharpness:"), self.fir_sharpness)
        self.fir_brightness = QDoubleSpinBox()
        self.fir_brightness.setRange(-1.0, 1.0); self.fir_brightness.setSingleStep(0.05)
        self.fir_brightness.setValue(float(self.settings.get("FrontIR_Brightness", 0.0)))
        fir.addRow(QLabel("Brightness:"), self.fir_brightness)
        note_fir = QLabel(
            "Applied automatically during Front IR (reflectance)\n"
            "image capture and live view."
        )
        note_fir.setStyleSheet("color: #90A4AE; font-size: 13px;")
        fir.addRow(QLabel(""), note_fir)
        tabs.addTab(fir_w, "Front IR")
        # ------------------------------------------------------------------ #
        # Tab 4 – Rear IR (Transmission)                                       #
        # ------------------------------------------------------------------ #
        rir_w, rir = _tab_page()
        self.rir_ae_chk = QCheckBox("AE on")
        self.rir_ae_chk.setChecked(bool(self.settings.get("RearIR_AeEnable", False)))
        rir.addRow(QLabel("AE:"), self.rir_ae_chk)
        self.rir_exp = QSpinBox()
        self.rir_exp.setRange(100, 200000)
        self.rir_exp.setSingleStep(500)           # 500 µs per click
        self.rir_exp.setValue(int(self.settings.get("RearIR_ExposureTime", 9000)))
        rir.addRow(QLabel("Exposure (µs):"), self.rir_exp)
        self.rir_gain_lbl = QLabel("Gain:")
        self.rir_gain = QDoubleSpinBox()
        self.rir_gain.setRange(1.0, 16.0); self.rir_gain.setSingleStep(0.1)
        self.rir_gain.setValue(float(self.settings.get("RearIR_Gain", 1.0)))
        rir.addRow(self.rir_gain_lbl, self.rir_gain)

        # Arducam-only gain field: this sensor's real V4L2 gain range is
        # 100-2200 (confirmed on hardware) — nothing like Picamera2's
        # 1.0-16.0 scale above — so it needs its own widget. Shown only
        # when the Arducam backend is selected; see
        # _update_backend_specific_fields() below.
        self.rir_arducam_gain_lbl = QLabel("Gain (Arducam, 100-2200):")
        self.rir_arducam_gain = QSpinBox()
        self.rir_arducam_gain.setRange(100, 2200); self.rir_arducam_gain.setSingleStep(10)
        self.rir_arducam_gain.setValue(int(self.settings.get("Arducam_RearIR_Gain", 100)))
        rir.addRow(self.rir_arducam_gain_lbl, self.rir_arducam_gain)

        self.rir_contrast = QDoubleSpinBox()
        self.rir_contrast.setRange(0.5, 2.0); self.rir_contrast.setSingleStep(0.05)
        self.rir_contrast.setValue(float(self.settings.get("RearIR_Contrast", 1.5)))
        rir.addRow(QLabel("Contrast:"), self.rir_contrast)
        self.rir_sharpness = QDoubleSpinBox()
        self.rir_sharpness.setRange(0.0, 2.0); self.rir_sharpness.setSingleStep(0.05)
        self.rir_sharpness.setValue(float(self.settings.get("RearIR_Sharpness", 1.4)))
        rir.addRow(QLabel("Sharpness:"), self.rir_sharpness)
        self.rir_brightness = QDoubleSpinBox()
        self.rir_brightness.setRange(-1.0, 1.0); self.rir_brightness.setSingleStep(0.05)
        self.rir_brightness.setValue(float(self.settings.get("RearIR_Brightness", -0.05)))
        rir.addRow(QLabel("Brightness:"), self.rir_brightness)
        note_rir = QLabel(
            "AE is off by default to prevent exposure drift\n"
            "as seedlings grow over the experiment.\n"
            "Applied during Rear IR and Combined IR captures."
        )
        note_rir.setStyleSheet("color: #90A4AE; font-size: 13px;")
        rir.addRow(QLabel(""), note_rir)
        tabs.addTab(rir_w, "Rear IR")

        # Show the correct Rear IR gain field (and lock the AE checkbox) for
        # whichever backend is currently selected, and keep it in sync as
        # the user changes the combo box.
        self.backend_combo.currentIndexChanged.connect(self._update_backend_specific_fields)
        self._update_backend_specific_fields()

        # ------------------------------------------------------------------ #
        # Apply / Close buttons (always visible below the tabs)               #
        # ------------------------------------------------------------------ #
        btns = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.apply_btn)
        btns.addStretch()
        btns.addWidget(self.close_btn)
        main.addLayout(btns)
        self.apply_btn.clicked.connect(self.on_apply)
        self.close_btn.clicked.connect(self.accept)
    # ---------------------------------------------------------------------- #
    # Show backend-appropriate Rear IR fields                                  #
    # ---------------------------------------------------------------------- #
    def _update_backend_specific_fields(self):
        """
        Show/hide the Picamera2 vs Arducam Rear IR gain fields, and lock the
        AE checkbox off when Arducam is selected — that backend always uses
        fixed manual exposure/gain for Rear IR (its onboard auto-exposure is
        unreliable on the bright, uniform transmission scene; see
        camera_arducam_usb3.apply_ir_transmission_preset()).
        """
        is_arducam = (self.backend_combo.currentData() == "arducam_usb3")

        self.rir_gain_lbl.setVisible(not is_arducam)
        self.rir_gain.setVisible(not is_arducam)

        self.rir_arducam_gain_lbl.setVisible(is_arducam)
        self.rir_arducam_gain.setVisible(is_arducam)

        self.rir_ae_chk.setEnabled(not is_arducam)
        if is_arducam:
            self.rir_ae_chk.setChecked(False)
            self.rir_ae_chk.setToolTip(
                "Always off for the Arducam backend — its auto-exposure is "
                "unreliable on the bright, uniform Rear IR scene, so Rear IR "
                "always uses fixed manual exposure/gain regardless of this box."
            )
        else:
            self.rir_ae_chk.setToolTip("")
    # ---------------------------------------------------------------------- #
    # Read current lens position from the running camera pipeline             #
    # ---------------------------------------------------------------------- #
    def on_read_focus(self):
        try:
            md = camera.get_metadata()
            pos = md.get("LensPosition", None)
            if pos is not None and float(pos) > 0.0:
                self.focus_pos_spin.setValue(float(pos))
                self.focus_status_lbl.setText(
                    f"Captured: {float(pos):.3f} D  "
                    f"(≈ {1.0 / float(pos) * 100:.0f} cm).  "
                    "Check 'Manual Focus' and press Apply."
                )
                self.focus_status_lbl.setStyleSheet("color: #43A047; font-size: 13px;")
            elif pos == 0.0:
                self.focus_status_lbl.setText(
                    "LensPosition is 0.0 — AF has not moved yet.  "
                    "Enable Live View and let AF settle first."
                )
                self.focus_status_lbl.setStyleSheet("color: #E53935; font-size: 13px;")
            else:
                self.focus_status_lbl.setText(
                    "No LensPosition data — is Live View running?"
                )
                self.focus_status_lbl.setStyleSheet("color: #E53935; font-size: 13px;")
        except Exception as e:
            self.focus_status_lbl.setText(f"Error reading metadata: {e}")
            self.focus_status_lbl.setStyleSheet("color: #E53935; font-size: 13px;")
    # ---------------------------------------------------------------------- #
    # Collect all widget values into a flat dict                              #
    # ---------------------------------------------------------------------- #
    def collect(self) -> dict:
        return {
            "CameraBackend":       self.backend_combo.currentData(),
            "AeEnable":            bool(self.ae_chk.isChecked()),
            "ExposureTime":        int(self.exp_spin.value()),
            "AnalogueGain":        float(self.gain_spin.value()),
            "AwbEnable":           bool(self.awb_chk.isChecked()),
            "Contrast":            float(self.contrast_spin.value()),
            "Brightness":          float(self.brightness_spin.value()),
            "Saturation":          float(self.saturation_spin.value()),
            "Sharpness":           float(self.sharpness_spin.value()),
            "NoiseReductionMode":  int(self.nr_spin.value()),
            "HdrEnable":           bool(self.hdr_chk.isChecked()),
            "ManualFocusEnable":   bool(self.manual_focus_chk.isChecked()),
            "ManualFocusPosition": float(self.focus_pos_spin.value()),
            # Front IR overrides
            "FrontIR_AeEnable":    bool(self.fir_ae_chk.isChecked()),
            "FrontIR_ExposureTime": int(self.fir_exp.value()),
            "FrontIR_Contrast":    float(self.fir_contrast.value()),
            "FrontIR_Sharpness":   float(self.fir_sharpness.value()),
            "FrontIR_Brightness":  float(self.fir_brightness.value()),
            # Rear IR overrides
            "RearIR_AeEnable":     bool(self.rir_ae_chk.isChecked()),
            "RearIR_ExposureTime": int(self.rir_exp.value()),
            "RearIR_Gain":         float(self.rir_gain.value()),
            "Arducam_RearIR_Gain": int(self.rir_arducam_gain.value()),
            "RearIR_Contrast":     float(self.rir_contrast.value()),
            "RearIR_Sharpness":    float(self.rir_sharpness.value()),
            "RearIR_Brightness":   float(self.rir_brightness.value()),
        }
    # ---------------------------------------------------------------------- #
    # Apply: save to disk, push to camera, apply manual focus if enabled      #
    # ---------------------------------------------------------------------- #
    def on_apply(self):
        self.settings = self.collect()
        save_settings(self.settings)
        chosen_backend = self.settings["CameraBackend"]
        running_backend = camera.get_camera_backend_active_this_process()
        if chosen_backend != running_backend:
            self.backend_status_lbl.setText(
                f"Saved '{chosen_backend}' — restart the application to switch "
                f"from the currently running '{running_backend}' backend."
            )
            self.backend_status_lbl.setStyleSheet("color: #FFD600; font-size: 12px; font-weight: bold;")
        else:
            self.backend_status_lbl.setText(f"Active this session: {running_backend}")
            self.backend_status_lbl.setStyleSheet("color: #90A4AE; font-size: 12px;")
        if self.settings["ManualFocusEnable"]:
            try:
                camera.set_manual_focus(self.settings["ManualFocusPosition"])
            except Exception:
                pass
        # Dialog stays open so the user can see the effect and fine-tune.
