# experiment_setup.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QGridLayout, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt
from styles import dark_style
import shutil
from pathlib import Path
import camera   # needed only to read which backend is active, for the storage estimate

# Rear IR (transmission, GPIO27) is now the SOLE imaging illumination
# source. Front IR (GPIO17) and Combined IR have been removed from the
# hardware/GUI — front-panel reflectance imaging did not work well enough
# to keep. Kept as a named constant (rather than a bare string) so the
# rest of the codebase (gui.py, experiment_runner.py, metadata) still has
# one canonical label to reference.
ILLUM_REAR_IR = "Rear IR"

# Growth-mode constants for the new DAYLIGHT / DARK experiment setup.
GROWTH_MODE_DAYLIGHT = "DAYLIGHT"
GROWTH_MODE_DARK = "DARK"

# Germination/photomorphogenesis LED GPIO map — single source of truth,
# shared by gui.py (manual buttons) and experiment_runner.py (automated
# DAYLIGHT/DARK control during a run).
GERM_LED_PINS = {"FarRed": 19, "Red": 13, "Blue": 12}

# DARK-mode shared timer bounds (hours). Default of 36h matches the
# spontaneous dark-opening kinetics discussed for etiolated hook-opening
# (fast phase ~48-72h; see Burachik et al. 2025 bioRxiv doi:10.1101/2025.02.18.638861).
# Dark-grown seedling protocol phases. Stratification (3-4 days at 4C) is
# done externally in a cold room before plates reach the imager; these
# phases model the timeline from that point forward: warm re-equilibration
# -> brief red germination pulse -> etiolation dark growth -> hook-opening
# induction.
PREEQ_DEFAULT_HOURS = 0     # Warm re-equilibration (dark, 20-22C)
PREEQ_STEP_HOURS    = 4
PREEQ_MIN_HOURS     = 0
PREEQ_MAX_HOURS     = 24

PULSE_DEFAULT_MINUTES = 30   # Germination pulse -- Red (660nm) only, per protocol
PULSE_STEP_MINUTES    = 30
PULSE_MIN_MINUTES     = 0
PULSE_MAX_MINUTES     = 240

ETIOLATION_DEFAULT_HOURS = 60  # Dark growth after the pulse
ETIOLATION_STEP_HOURS    = 1
ETIOLATION_MIN_HOURS     = 0
ETIOLATION_MAX_HOURS     = 96

IMAGES_ROOT = Path("/home/sybednar/Seedling_Imager/images")  # for disk-usage estimate

# Storage estimates (all IR grayscale now, Rear IR only).
#
# On-disk (zlib-compressed TIFF) size depends heavily on which camera
# backend is active — NOT just resolution. Confirmed on real hardware
# (Sept 2026): the Picamera2 backend's well-exposed Rear IR grayscale
# captures compress to roughly 6-7 MB, while the Arducam 20MP backend's
# well-exposed full-resolution (5120x3840) captures — at exposure/gain
# settings that produce comparable real image detail with no
# clipping — run closer to 13-14 MB, because more real, non-uniform
# image content (fine root/shoot detail across a much larger sensor)
# compresses less than the smaller Picamera2 frame. A single shared
# constant would misestimate storage badly for whichever backend it
# wasn't tuned against, so this is now backend-specific; see
# update_storage_estimate() below, which picks the right one from
# camera.get_camera_backend_active_this_process() (the backend that will
# actually be used once an experiment starts — this is fixed for the
# life of the running process regardless of what's saved in the Camera
# Configuration dialog until the app is restarted).
AVG_IMAGE_MB_IR_GRAY_PICAMERA2 = 10.0
AVG_IMAGE_MB_IR_GRAY_ARDUCAM   = 13.5


class DaylightSettingsDialog(QDialog):
    """
    Static FarRed/Red/Blue germination LED settings for DAYLIGHT-mode
    experiments. Each channel is independently ON/OFF for the ENTIRE
    experiment duration (no timer) — e.g. to hold a fixed red:far-red
    ratio while imaging continues under Rear IR.
    """
    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        try:
            from PySide6.QtGui import QGuiApplication
            _scr = QGuiApplication.primaryScreen()
            _geom = _scr.availableGeometry() if _scr else None
            s = (_geom.width() / 800.0) if _geom else 1.0
        except Exception:
            s = 1.0
        s = max(1.0, s)
        self.setWindowTitle("DAYLIGHT Settings")
        self.setStyleSheet(dark_style(s))
        self.result_settings = dict(current)

        layout = QVBoxLayout()
        info = QLabel("Select germination LEDs to hold ON for the entire experiment:")
        info.setWordWrap(True)
        info.setStyleSheet(f"font-size: {max(12, int(11 * s))}px; color: white;")
        layout.addWidget(info)

        self.checks = {}
        for name in ("FarRed", "Red", "Blue"):
            cb = QCheckBox(name)
            cb.setChecked(bool(current.get(name, False)))
            cb.setStyleSheet(
                f"QCheckBox {{ color: white; font-size: {max(12, int(11 * s))}px; }} "
                f"QCheckBox::indicator {{ width: {max(14, int(14*s))}px; height: {max(14, int(14*s))}px; }} "
                "QCheckBox::indicator:unchecked { border: 2px solid #BBBBBB; background: #222222; } "
                "QCheckBox::indicator:checked { border: 2px solid #1E88E5; background: #1E88E5; } "
            )
            self.checks[name] = cb
            layout.addWidget(cb)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background-color: #43A047; color: white; font-weight: bold; padding: {max(5,int(6*s))}px; font-size: {max(12,int(11.25*s))}px;"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def accept(self):
        for name, cb in self.checks.items():
            self.result_settings[name] = cb.isChecked()
        super().accept()


class DarkSettingsDialog(QDialog):
    """
    Models the standard dark-grown seedling protocol (stratification is
    done externally, in a cold room, before plates reach the imager):

      1) Warm re-equilibration -- dark, 20-22C ("Pre-pulse dark" below)
      2) Germination pulse -- brief 660nm Red exposure only. Protocol note:
         an 8h pulse is long enough to act as a structural light treatment
         and can suppress proper apical hook formation -- keep this brief
         (15-30 min up to ~2h is typical).
      3) Etiolation -- extended dark growth; hooks reach maximum curvature
         ~60-72h after the pulse, then begin opening on their own if held
         longer.
      4) Hook-opening induction -- the channel(s) selected below (Red,
         Blue, and/or Far-Red) switch ON and stay ON continuously for the
         rest of the experiment (a sustained exposure, not a brief pulse,
         is required for the far-red High Irradiance Response -- see
         Liscum & Hangarter, Plant Physiol 1993, doi:10.1104/pp.101.2.567).

    The induction start time is computed automatically as the sum of
    phases 1-3 (shown live below) rather than set independently, so the
    whole timeline stays internally consistent.
    """
    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        try:
            from PySide6.QtGui import QGuiApplication
            _scr = QGuiApplication.primaryScreen()
            _geom = _scr.availableGeometry() if _scr else None
            s = (_geom.width() / 800.0) if _geom else 1.0
        except Exception:
            s = 1.0
        s = max(1.0, s)
        self.setWindowTitle("DARK Settings")
        self.setStyleSheet(dark_style(s))
        self.result_settings = dict(current)
        _fs = max(12, int(11 * s))

        layout = QVBoxLayout()

        def _spin_row(label_text, initial, step, lo, hi):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-size: {_fs}px; color: white;")
            value = QLineEdit(str(int(initial)))
            value.setAlignment(Qt.AlignCenter)
            value.setFixedSize(int(69 * s), int(38 * s))
            value.setStyleSheet(f"background-color: white; color: black; font-size: {max(12, int(14 * s))}px;")
            up = QPushButton("\u25b2"); down = QPushButton("\u25bc")
            for btn in (up, down):
                btn.setFixedSize(int(36 * s), int(38 * s))
                btn.setStyleSheet(f"background-color: #ccc; font-size: {max(12, int(15 * s))}px; font-weight: bold;")

            def _adjust(delta):
                try:
                    cur = float(value.text())
                except ValueError:
                    cur = initial
                new_val = max(lo, min(hi, cur + delta))
                value.setText(str(int(new_val)))
                self._refresh_induction_estimate()

            up.clicked.connect(lambda: _adjust(step))
            down.clicked.connect(lambda: _adjust(-step))
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(down)
            row.addWidget(value)
            row.addWidget(up)
            layout.addLayout(row)
            return value

        # --- Phase 1: pre-pulse (warm re-equilibration) ---
        self.preeq_value = _spin_row(
            "Pre-pulse dark, re-equilibration (h):",
            current.get("preequilibration_hours", PREEQ_DEFAULT_HOURS),
            PREEQ_STEP_HOURS, PREEQ_MIN_HOURS, PREEQ_MAX_HOURS,
        )

        # --- Phase 2: germination pulse (Red 660nm only) ---
        self.pulse_enable_chk = QCheckBox("Enable germination pulse (Red 660nm)")
        self.pulse_enable_chk.setChecked(bool(current.get("pulse_enabled", True)))
        self.pulse_enable_chk.setStyleSheet(
            f"QCheckBox {{ color: white; font-size: {_fs}px; }} "
            f"QCheckBox::indicator {{ width: {max(14, int(14*s))}px; height: {max(14, int(14*s))}px; }} "
            "QCheckBox::indicator:unchecked { border: 2px solid #BBBBBB; background: #222222; } "
            "QCheckBox::indicator:checked { border: 2px solid #E53935; background: #E53935; } "
        )
        self.pulse_enable_chk.toggled.connect(self._update_pulse_enabled)
        layout.addWidget(self.pulse_enable_chk)

        self.pulse_value = _spin_row(
            "Pulse duration (min):",
            current.get("pulse_minutes", PULSE_DEFAULT_MINUTES),
            PULSE_STEP_MINUTES, PULSE_MIN_MINUTES, PULSE_MAX_MINUTES,
        )

        # --- Phase 3: etiolation (dark growth) ---
        self.etiolation_value = _spin_row(
            "Etiolation, dark growth (h):",
            current.get("etiolation_hours", ETIOLATION_DEFAULT_HOURS),
            ETIOLATION_STEP_HOURS, ETIOLATION_MIN_HOURS, ETIOLATION_MAX_HOURS,
        )

        # --- Computed induction start estimate ---
        self.induction_estimate_label = QLabel("")
        self.induction_estimate_label.setStyleSheet(f"font-size: {_fs}px; color: #90CAF9; font-weight: bold;")
        layout.addWidget(self.induction_estimate_label)

        # --- Phase 4: induction channels ---
        induction_hdr = QLabel("Hook-opening induction -- channel(s) to switch on and hold:")
        induction_hdr.setWordWrap(True)
        induction_hdr.setStyleSheet(f"font-size: {_fs}px; color: white;")
        layout.addWidget(induction_hdr)

        self.checks = {}
        # Colors match the germination LED buttons on the main GUI page
        # (self.germ_blue_btn / germ_red_btn / germ_farred_btn in gui.py).
        _channel_labels = {"FarRed": "FarRed 730nm", "Red": "Red 660nm", "Blue": "Blue 450nm"}
        _channel_colors = {"FarRed": "#FF5722", "Red": "#D32F2F", "Blue": "#3D5AFE"}
        for name in ("FarRed", "Red", "Blue"):
            cb = QCheckBox(_channel_labels[name])
            cb.setChecked(bool(current.get(name, False)))
            _color = _channel_colors[name]
            cb.setStyleSheet(
                f"QCheckBox {{ color: white; font-size: {_fs}px; }} "
                f"QCheckBox::indicator {{ width: {max(14, int(14*s))}px; height: {max(14, int(14*s))}px; }} "
                "QCheckBox::indicator:unchecked { border: 2px solid #BBBBBB; background: #222222; } "
                f"QCheckBox::indicator:checked {{ border: 2px solid {_color}; background: {_color}; }} "
            )
            self.checks[name] = cb
            layout.addWidget(cb)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background-color: #43A047; color: white; font-weight: bold; padding: {max(5,int(6*s))}px; font-size: {max(12,int(11.25*s))}px;"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        self._update_pulse_enabled()
        self._refresh_induction_estimate()

    def _update_pulse_enabled(self, *_):
        if not hasattr(self, "pulse_value"):
            return
        self.pulse_value.setEnabled(self.pulse_enable_chk.isChecked())
        self._refresh_induction_estimate()

    def _refresh_induction_estimate(self):
        if not hasattr(self, "induction_estimate_label"):
            return
        try:
            preeq_h = float(self.preeq_value.text())
        except ValueError:
            preeq_h = PREEQ_DEFAULT_HOURS
        try:
            pulse_min = float(self.pulse_value.text())
        except ValueError:
            pulse_min = PULSE_DEFAULT_MINUTES
        pulse_h = (pulse_min / 60.0) if self.pulse_enable_chk.isChecked() else 0.0
        try:
            etiolation_h = float(self.etiolation_value.text())
        except ValueError:
            etiolation_h = ETIOLATION_DEFAULT_HOURS
        total_h = preeq_h + pulse_h + etiolation_h
        self.induction_estimate_label.setText(
            f"Induction will begin at approximately {total_h:.1f}h after experiment start."
        )

    def accept(self):
        for name, cb in self.checks.items():
            self.result_settings[name] = cb.isChecked()
        try:
            self.result_settings["preequilibration_hours"] = float(self.preeq_value.text())
        except ValueError:
            self.result_settings["preequilibration_hours"] = PREEQ_DEFAULT_HOURS
        self.result_settings["pulse_enabled"] = self.pulse_enable_chk.isChecked()
        try:
            self.result_settings["pulse_minutes"] = float(self.pulse_value.text())
        except ValueError:
            self.result_settings["pulse_minutes"] = PULSE_DEFAULT_MINUTES
        try:
            self.result_settings["etiolation_hours"] = float(self.etiolation_value.text())
        except ValueError:
            self.result_settings["etiolation_hours"] = ETIOLATION_DEFAULT_HOURS
        super().accept()


class ExperimentSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # --- Universal screen scaling ---
        try:
            from PySide6.QtGui import QGuiApplication
            _scr = QGuiApplication.primaryScreen()
            _geom = _scr.availableGeometry() if _scr else None
            s = (_geom.width() / 800.0) if _geom else 1.0
        except Exception:
            s = 1.0
        s = max(1.0, s)
        self.setWindowTitle("Experiment Setup")
        self.setMinimumWidth(int(544 * s))   # 870 px on Display2 (1.6×)
        self.setMinimumHeight(int(325 * s))  # 520 px on Display2
        self.setStyleSheet(dark_style(s))

        # Imaging illumination is now fixed (Rear IR is the only source).
        self.selected_illum = ILLUM_REAR_IR

        # Growth mode + per-mode germination LED settings.
        self.growth_mode = GROWTH_MODE_DAYLIGHT
        self.daylight_settings = {"FarRed": False, "Red": False, "Blue": False}
        self.dark_settings = {
            "FarRed": False, "Red": False, "Blue": False,
            "preequilibration_hours": PREEQ_DEFAULT_HOURS,
            "pulse_enabled": True,
            "pulse_minutes": PULSE_DEFAULT_MINUTES,
            "etiolation_hours": ETIOLATION_DEFAULT_HOURS,
        }

        main_layout = QVBoxLayout()

        # Growth Mode row (replaces the old Illumination toggle row)
        growth_row = QHBoxLayout()
        growth_label = QLabel("Growth Mode:")
        growth_label.setStyleSheet(f"font-size: {max(12, int(11.25 * s))}px; color: white;")
        self.daylight_btn = QPushButton("DAYLIGHT")
        self.daylight_btn.setFixedSize(int(100 * s), int(30 * s))
        self.daylight_btn.clicked.connect(self.open_daylight_dialog)
        self.dark_btn = QPushButton("DARK")
        self.dark_btn.setFixedSize(int(100 * s), int(30 * s))
        self.dark_btn.clicked.connect(self.open_dark_dialog)
        self._apply_growth_mode_styles()
        growth_row.addWidget(growth_label)
        growth_row.addStretch()
        growth_row.addWidget(self.daylight_btn)
        growth_row.addWidget(self.dark_btn)
        main_layout.addLayout(growth_row)

        # Duration (unchanged except signal to recompute estimate)
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Duration (days):")
        duration_label.setStyleSheet(f"font-size: {max(12, int(11.25 * s))}px; color: white;")
        self.duration_value = QLineEdit("1")
        self.duration_value.setAlignment(Qt.AlignCenter)
        self.duration_value.setFixedSize(int(69 * s), int(38 * s))
        self.duration_value.setStyleSheet(f"background-color: white; color: black; font-size: {max(12, int(14 * s))}px;")
        duration_up = QPushButton("▲"); duration_down = QPushButton("▼")
        for btn in (duration_up, duration_down):
            btn.setFixedSize(int(36 * s), int(38 * s))
            btn.setStyleSheet(f"background-color: #ccc; font-size: {max(12, int(15 * s))}px; font-weight: bold;")
        duration_up.clicked.connect(lambda: self.adjust_value(self.duration_value, 1, 1, 7))
        duration_down.clicked.connect(lambda: self.adjust_value(self.duration_value, -1, 1, 7))
        # Recompute when value is edited manually
        self.duration_value.textChanged.connect(self.update_storage_estimate)
        duration_layout.addWidget(duration_label)
        duration_layout.addStretch()
        duration_layout.addWidget(duration_up)
        duration_layout.addWidget(self.duration_value)
        duration_layout.addWidget(duration_down)
        main_layout.addLayout(duration_layout)

        # Frequency
        freq_layout = QHBoxLayout()
        freq_label = QLabel("Acquisition Frequency (minutes):")
        freq_label.setStyleSheet(f"font-size: {max(12, int(11.25 * s))}px; color: white;")
        self.freq_value = QLineEdit("30")   # 30 min default for experiments
        self.freq_value.setAlignment(Qt.AlignCenter)
        self.freq_value.setFixedSize(int(69 * s), int(38 * s))
        self.freq_value.setStyleSheet(f"background-color: white; color: black; font-size: {max(12, int(14 * s))}px;")
        freq_up = QPushButton("▲"); freq_down = QPushButton("▼")
        for btn in (freq_up, freq_down):
            btn.setFixedSize(int(36 * s), int(38 * s))
            btn.setStyleSheet(f"background-color: #ccc; font-size: {max(12, int(15 * s))}px; font-weight: bold;")
        freq_up.clicked.connect(lambda: self.adjust_value(self.freq_value, 30, 1, 360))
        freq_down.clicked.connect(lambda: self.adjust_value(self.freq_value, -30, 1, 360))
        # Recompute when value is edited manually
        self.freq_value.textChanged.connect(self.update_storage_estimate)
        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_up)
        freq_layout.addWidget(self.freq_value)
        freq_layout.addWidget(freq_down)
        main_layout.addLayout(freq_layout)

        # Instruction
        instruction_label = QLabel("Select plates for experiment:")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet(f"font-size: {max(12, int(11.25 * s))}px; color: white;")
        main_layout.addWidget(instruction_label)

        # Two-row plate grid (unchanged except connect signals)
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(20); grid_layout.setVerticalSpacing(10)
        self.plate_checkboxes = {}
        for row, names in enumerate([["Plate 1", "Plate 2", "Plate 3"], ["Plate 4", "Plate 5", "Plate 6"]]):
            h = QHBoxLayout(); h.setSpacing(24); h.setAlignment(Qt.AlignCenter)
            for name in names:
                cb = QCheckBox(name)
                _cbfs  = max(10, int(10 * s))
                _cbind = max(14, int(14 * s))
                cb.setStyleSheet(
                    f"QCheckBox {{ color: white; font-size: {_cbfs}px; }} "
                    f"QCheckBox::indicator {{ width: {_cbind}px; height: {_cbind}px; }} "
                    "QCheckBox::indicator:unchecked { border: 2px solid #BBBBBB; background: #222222; } "
                    "QCheckBox::indicator:checked { border: 2px solid #1E88E5; background: #1E88E5; } "
                )
                cb.toggled.connect(self.update_storage_estimate)  # <-- recompute when plate selection changes
                self.plate_checkboxes[name] = cb
                h.addWidget(cb)
            main_layout.addLayout(h)

        # ---- storage estimate label ----
        self.storage_label = QLabel("")
        self.storage_label.setAlignment(Qt.AlignCenter)
        self.storage_label.setWordWrap(True)
        self.storage_label.setStyleSheet(f"font-size: {max(9, int(9.4 * s))}px; color: #CCCCCC;")
        main_layout.addWidget(self.storage_label)

        # Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Experiment")
        self.exit_button = QPushButton("Exit")
        _bfs = max(12, int(11.25 * s))
        _bpad = max(5, int(6.25 * s))
        self.start_button.setStyleSheet(f"background-color: #43A047; color: white; font-weight: bold; padding: {_bpad}px; font-size: {_bfs}px;")
        self.exit_button.setStyleSheet(f"background-color: #E53935; color: white; font-weight: bold; padding: {_bpad}px; font-size: {_bfs}px;")
        self.start_button.clicked.connect(self.validate_and_start)
        self.exit_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.exit_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # Initial compute
        self.update_storage_estimate()

        # --- Growth mode dialogs ---
    def open_daylight_dialog(self):
        # Re-entrancy guard (Sept 2026): a double-click/double-tap -- easy to
        # trigger over a laggy remote session like Raspberry Pi Connect, where
        # the dialog's on-screen appearance can lag behind the actual click --
        # could otherwise queue a second invocation before the first dialog's
        # exec() call returns, leaving the UI looking frozen until Esc was
        # pressed. Disabling the button for the duration of exec() makes a
        # second click on it a no-op instead.
        self.daylight_btn.setEnabled(False)
        try:
            dlg = DaylightSettingsDialog(self.daylight_settings, self)
            if dlg.exec() == QDialog.Accepted:
                self.daylight_settings = dlg.result_settings
                self.growth_mode = GROWTH_MODE_DAYLIGHT
                self._apply_growth_mode_styles()
        finally:
            self.daylight_btn.setEnabled(True)

    def open_dark_dialog(self):
        # See open_daylight_dialog() above for why this guard exists.
        self.dark_btn.setEnabled(False)
        try:
            dlg = DarkSettingsDialog(self.dark_settings, self)
            if dlg.exec() == QDialog.Accepted:
                self.dark_settings = dlg.result_settings
                self.growth_mode = GROWTH_MODE_DARK
                self._apply_growth_mode_styles()
        finally:
            self.dark_btn.setEnabled(True)

    def _apply_growth_mode_styles(self):
        active_style = "background-color: #43A047; color: white; font-weight: bold; border-radius: 4px;"
        inactive_style = "background-color: #37474F; color: white; font-weight: bold; border-radius: 4px;"
        self.daylight_btn.setStyleSheet(active_style if self.growth_mode == GROWTH_MODE_DAYLIGHT else inactive_style)
        self.dark_btn.setStyleSheet(active_style if self.growth_mode == GROWTH_MODE_DARK else inactive_style)

    # --- helpers ---
    def adjust_value(self, line_edit, step, min_val, max_val):
        try:
            current = int(line_edit.text())
        except ValueError:
            current = min_val
        new_val = max(min_val, min(max_val, current + step))
        line_edit.setText(str(new_val))
        # recompute after button presses
        self.update_storage_estimate()

    # ---- storage estimate computation ----
    def update_storage_estimate(self):
            try:
                duration_days      = int(self.duration_value.text())
                frequency_minutes  = int(self.freq_value.text())
            except ValueError:
                duration_days, frequency_minutes = 1, 30

            selected = [name for name, cb in self.plate_checkboxes.items() if cb.isChecked()]
            n_plates = len(selected)

            cycles    = int((duration_days * 24 * 60) / max(1, frequency_minutes))
            images    = n_plates * cycles

            # All modes are IR grayscale, Rear IR only — but the per-image size
            # estimate is backend-specific (see the constants' comment above).
            try:
                active_backend = camera.get_camera_backend_active_this_process()
            except Exception:
                active_backend = "picamera2"
            avg_mb = (
                AVG_IMAGE_MB_IR_GRAY_ARDUCAM
                if active_backend == "arducam_usb3"
                else AVG_IMAGE_MB_IR_GRAY_PICAMERA2
            )
            est_gb    = (images * avg_mb) / 1024.0

            mode_label = "rear IR gray"

            try:
                total, used, free = shutil.disk_usage(IMAGES_ROOT)
                free_gb = free / (1024 ** 3)
            except Exception:
                free_gb = None

            if n_plates == 0:
                msg   = "No plates selected — storage estimate unavailable."
                style = "color: #CCCCCC;"
            else:
                msg = (
                    f"Estimated storage: ~{est_gb:.1f} GB "
                    f"({images} images over {cycles} cycles, {mode_label} ~{avg_mb:.0f} MB/img)"
                )
                if free_gb is not None:
                    msg += f"  |  Free: {free_gb:.1f} GB"
                    style = "color: #43A047;" if est_gb <= free_gb else "color: #E53935;"
                else:
                    style = "color: #CCCCCC;"

            self.storage_label.setText(msg)
            self.storage_label.setStyleSheet(style)

    def validate_and_start(self):
        selected = [name for name, cb in self.plate_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Validation Error", "Please select at least one plate before starting the experiment.")
            return
        self.selected_plates = selected
        self.duration_days = int(self.duration_value.text())
        self.frequency_minutes = int(self.freq_value.text())
        self.selected_illum = ILLUM_REAR_IR  # fixed — Rear IR is the sole imaging illumination now
        self.accept()
