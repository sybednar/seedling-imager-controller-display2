# experiment_setup.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QGridLayout, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt
from styles import dark_style
import shutil
from pathlib import Path

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
DARK_TIMER_DEFAULT_HOURS = 36
DARK_TIMER_STEP_HOURS = 12
DARK_TIMER_MIN_HOURS = 0
DARK_TIMER_MAX_HOURS = 168  # 1 week ceiling

IMAGES_ROOT = Path("/home/sybednar/Seedling_Imager/images")  # for disk-usage estimate

# Storage estimates (all IR grayscale now, Rear IR only)
AVG_IMAGE_MB_IR_GRAY = 10.0


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
    Independent ON/OFF for FarRed/Red/Blue germination LEDs during a
    DARK-mode (etiolation) experiment, plus ONE shared timer (hours) that
    applies to whichever channel(s) are turned ON. Once the configured
    elapsed time is reached, the selected channel(s) switch on and stay on
    continuously for the rest of the experiment (a sustained exposure, not
    a brief pulse, is required for the far-red High Irradiance Response —
    see Liscum & Hangarter, Plant Physiol 1993, doi:10.1104/pp.101.2.567).
    The timer field is only editable while at least one channel is ON.
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

        layout = QVBoxLayout()
        info = QLabel(
            "Select germination LEDs to trigger during this dark-grown experiment, "
            "and the elapsed time (from experiment start) at which they turn on. "
            "Once triggered, selected LEDs stay on for the rest of the experiment."
        )
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
            cb.toggled.connect(self._update_timer_enabled)
            self.checks[name] = cb
            layout.addWidget(cb)

        timer_layout = QHBoxLayout()
        timer_label = QLabel("Trigger at (hours):")
        timer_label.setStyleSheet(f"font-size: {max(12, int(11 * s))}px; color: white;")
        self.timer_value = QLineEdit(str(int(current.get("timer_hours", DARK_TIMER_DEFAULT_HOURS))))
        self.timer_value.setAlignment(Qt.AlignCenter)
        self.timer_value.setFixedSize(int(69 * s), int(38 * s))
        self.timer_value.setStyleSheet(f"background-color: white; color: black; font-size: {max(12, int(14 * s))}px;")
        timer_up = QPushButton("▲"); timer_down = QPushButton("▼")
        for btn in (timer_up, timer_down):
            btn.setFixedSize(int(36 * s), int(38 * s))
            btn.setStyleSheet(f"background-color: #ccc; font-size: {max(12, int(15 * s))}px; font-weight: bold;")
        timer_up.clicked.connect(lambda: self._adjust_timer(DARK_TIMER_STEP_HOURS))
        timer_down.clicked.connect(lambda: self._adjust_timer(-DARK_TIMER_STEP_HOURS))
        timer_layout.addWidget(timer_label)
        timer_layout.addStretch()
        timer_layout.addWidget(timer_down)
        timer_layout.addWidget(self.timer_value)
        timer_layout.addWidget(timer_up)
        layout.addLayout(timer_layout)
        self._timer_up_btn, self._timer_down_btn = timer_up, timer_down

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background-color: #43A047; color: white; font-weight: bold; padding: {max(5,int(6*s))}px; font-size: {max(12,int(11.25*s))}px;"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        self._update_timer_enabled()

    def _any_channel_on(self) -> bool:
        return any(cb.isChecked() for cb in self.checks.values())

    def _update_timer_enabled(self, *_):
        enabled = self._any_channel_on()
        self.timer_value.setEnabled(enabled)
        self._timer_up_btn.setEnabled(enabled)
        self._timer_down_btn.setEnabled(enabled)

    def _adjust_timer(self, step: int):
        try:
            current = int(self.timer_value.text())
        except ValueError:
            current = DARK_TIMER_DEFAULT_HOURS
        new_val = max(DARK_TIMER_MIN_HOURS, min(DARK_TIMER_MAX_HOURS, current + step))
        self.timer_value.setText(str(new_val))

    def accept(self):
        for name, cb in self.checks.items():
            self.result_settings[name] = cb.isChecked()
        try:
            self.result_settings["timer_hours"] = int(self.timer_value.text())
        except ValueError:
            self.result_settings["timer_hours"] = DARK_TIMER_DEFAULT_HOURS
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
        self.dark_settings = {"FarRed": False, "Red": False, "Blue": False, "timer_hours": DARK_TIMER_DEFAULT_HOURS}

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
        dlg = DaylightSettingsDialog(self.daylight_settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.daylight_settings = dlg.result_settings
            self.growth_mode = GROWTH_MODE_DAYLIGHT
            self._apply_growth_mode_styles()

    def open_dark_dialog(self):
        dlg = DarkSettingsDialog(self.dark_settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.dark_settings = dlg.result_settings
            self.growth_mode = GROWTH_MODE_DARK
            self._apply_growth_mode_styles()

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

            # All modes are IR grayscale, Rear IR only — single per-image size estimate
            avg_mb    = AVG_IMAGE_MB_IR_GRAY
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
