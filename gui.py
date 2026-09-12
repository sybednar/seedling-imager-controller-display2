#gui.py fixing image rescaling issue during experimental run
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDialog, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEventLoop
from PySide6.QtGui import QPixmap, QGuiApplication
from datetime import datetime, timedelta
from styles import dark_style
from experiment_setup import (
    ExperimentSetupDialog, ILLUM_REAR_IR,
    GROWTH_MODE_DAYLIGHT, GROWTH_MODE_DARK, GERM_LED_PINS,
)
from experiment_runner import ExperimentRunner
from camera_config import CameraConfigDialog
from file_manager import FileManagerDialog
import motor_control
import camera

# --- Constants for LED colors/styles ---
SEA_FOAM_GREEN = "#26A69A"  # Green mode button color
DEEP_RED = "#B71C1C"        # Infrared mode button color

# LED GPIO setup block
try:
    import gpiod
    from gpiod.line import Value, Direction

    # Imaging illumination — Rear IR (transmission) is now the ONLY imaging
    # illumination source. The old Front IR panel (GPIO17) did not work
    # well for reflectance imaging and has been removed; GPIO17 is now
    # free/unused.
    LED_REAR_IR_PIN  = 27    # rear IR panel (transmission imaging illumination)

    # Green LED (GPIO24) — low-photomorphogenic-impact light for setting up
    # dark-grown experiments (loading plates, checking alignment, etc.)
    # without triggering light-dependent germination responses.
    LED_GREEN_PIN = 24

    # Germination/photomorphogenesis LED strip — independent of imaging
    # illumination. Pin map is shared with experiment_setup.py /
    # experiment_runner.py via GERM_LED_PINS so there's a single source of
    # truth.
    LED_GERM_BLUE_PIN   = GERM_LED_PINS["Blue"]     # 450 nm
    LED_GERM_RED_PIN    = GERM_LED_PINS["Red"]      # 660 nm
    LED_GERM_FARRED_PIN = GERM_LED_PINS["FarRed"]   # 730 nm

    chip = "/dev/gpiochip0"
    led_request = gpiod.request_lines(
        chip,
        consumer="seedling_leds",
        config={
            LED_REAR_IR_PIN:      gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
            LED_GREEN_PIN:        gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
            LED_GERM_BLUE_PIN:    gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
            LED_GERM_RED_PIN:     gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
            LED_GERM_FARRED_PIN:  gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        }
    )
except Exception as e:
    print(f"LED init failed: {e}", flush=True)
    led_request = None


class _CameraCallWorker(QThread):
    """
    Generic one-shot worker: runs an arbitrary no-arg callable on a
    background thread. Paired with SeedlingImagerGUI._run_camera_call_guarded()
    below — see that method's docstring for why this exists.
    """
    finished_ok = Signal(bool, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self._fn()
            self.finished_ok.emit(True, "")
        except Exception as e:
            self.finished_ok.emit(False, str(e))


class SeedlingImagerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time_Lapse Seedling Imager")

        # Adapt to actual display geometry (handles portrait/landscape without hard-coding)
        screen = QGuiApplication.primaryScreen()
        geom = screen.availableGeometry() if screen else None
        if geom:
            self.setGeometry(geom)
        else:
            self.resize(800, 480)   # safe fallback (original display baseline; Display2 uses screen geom)

        # --- UI scaling based on screen size (relative to original 800px-wide design) ---
        s = (geom.width() / 800.0) if geom else 1.6
        s = max(1.0, s)
        self._s = s   # stored for use in _update_focus_mode_label and style helpers

        # Apply scaled stylesheet now that s is known
        self.setStyleSheet(dark_style(s))

        # Left column sizing
        button_width = int(250 * s)
        base_btn_h = 30
        height_scale  = 1.25
        button_height = int(base_btn_h * height_scale * s)  # ~1.5x taller touch targets
        # Screen dimensions used below to lock the camera preview to a fixed size
        _screen_w = geom.width() if geom else int(800 * s)
        _screen_h = geom.height() if geom else int(480 * s)

        self.threads = []
        self.experiment_thread = None
        self.homing_worker = None  # <-- abortable homing worker
        self._guarded_camera_workers = []  # see _run_camera_call_guarded()

        # Experiment progress info (elapsed time / next-cycle ETA) — populated
        # when an experiment starts, cleared when it ends. See
        # _update_experiment_info() and _on_cycle_wait_started().
        self._experiment_start_time = None
        self._next_cycle_eta = None

        main_layout = QHBoxLayout()

        # Left: buttons (EXACT-FILL balanced column)
        button_layout = QVBoxLayout()
        button_layout.setSpacing(0)
        button_layout.setContentsMargins(0, 0, 0, 0)
        # NOTE: do NOT set AlignTop when using stretches for exact fill.


        def style_and_size(btn, *, full_width=True):
            """Apply consistent sizing for touchscreen use."""
            if full_width:
                btn.setFixedWidth(button_width)
            btn.setFixedHeight(button_height)
            return btn

        # --- Buttons (same as before, but now height-controlled) ---

        # Live View toggle button (text reflects current state)
        self.live_view_btn = QPushButton("Turn Live View On")
        #self.live_view_btn.setFixedWidth(button_width)
        style_and_size(self.live_view_btn)
        self.live_view_btn.setStyleSheet(
            dark_style(s) + " QPushButton { background-color: #FFD600; color: black; font-weight: bold; }"
        )
        self.live_view_btn.clicked.connect(self.toggle_live_view)
        #button_layout.addWidget(self.live_view_btn)

        # Setup LEDs — Rear IR (GPIO27) and Green (GPIO24). These are
        # independent manual toggles for bench use (same pattern as the
        # germination LEDs below), e.g. to preview transmission lighting or
        # to work under Green light while setting up a dark-grown
        # experiment. Rear IR is ALSO driven automatically during Live View
        # and experiment capture (see _set_rear_ir / set_led) regardless of
        # this button's state, since it's now the sole imaging illumination
        # source.
        setup_led_layout = QHBoxLayout()
        setup_led_layout.setSpacing(max(4, int(6 * s)))
        setup_led_layout.setContentsMargins(0, 0, 0, 0)
        setup_btn_w = (button_width - setup_led_layout.spacing()) // 2

        self.rear_ir_btn = QPushButton("Rear IR")
        self.rear_ir_btn.setCheckable(True)
        self.rear_ir_btn.setFixedWidth(setup_btn_w)
        self.rear_ir_btn.setFixedHeight(button_height)
        self.rear_ir_btn.toggled.connect(self._on_rear_ir_button_toggled)

        self.green_btn = QPushButton("Green")
        self.green_btn.setCheckable(True)
        self.green_btn.setFixedWidth(setup_btn_w)
        self.green_btn.setFixedHeight(button_height)
        self.green_btn.toggled.connect(
            lambda checked: self._toggle_manual_led(LED_GREEN_PIN, checked, self.green_btn, "#4CAF50", "Green")
        )

        for _btn in (self.rear_ir_btn, self.green_btn):
            _btn.setStyleSheet(dark_style(s) + " QPushButton { background-color: #37474F; color: white; }")
            setup_led_layout.addWidget(_btn)

        # Germination/photomorphogenesis LED strip — independent on/off per
        # channel (Blue 450nm, Red 660nm, FarRed 730nm). Unlike Rear IR
        # above, these are NOT part of the imaging illumination cycle —
        # they run (or not) independently, e.g. to manipulate red:far-red
        # ratio for a photomorphogenesis experiment while imaging continues
        # under IR. During DAYLIGHT/DARK experiments these are also driven
        # automatically by ExperimentRunner (see set_germination_led_raw);
        # these buttons remain available for manual bench use.
        germ_layout = QHBoxLayout()
        germ_layout.setSpacing(max(4, int(6 * s)))
        germ_layout.setContentsMargins(0, 0, 0, 0)
        germ_btn_w = (button_width - 2 * germ_layout.spacing()) // 3

        self.germ_blue_btn = QPushButton("Blue")
        self.germ_blue_btn.setCheckable(True)
        self.germ_blue_btn.setFixedWidth(germ_btn_w)
        self.germ_blue_btn.setFixedHeight(button_height)
        self.germ_blue_btn.toggled.connect(
            lambda checked: self._toggle_manual_led(LED_GERM_BLUE_PIN, checked, self.germ_blue_btn, "#3D5AFE", "Blue")
        )

        self.germ_red_btn = QPushButton("Red")
        self.germ_red_btn.setCheckable(True)
        self.germ_red_btn.setFixedWidth(germ_btn_w)
        self.germ_red_btn.setFixedHeight(button_height)
        self.germ_red_btn.toggled.connect(
            lambda checked: self._toggle_manual_led(LED_GERM_RED_PIN, checked, self.germ_red_btn, "#D32F2F", "Red")
        )

        self.germ_farred_btn = QPushButton("FarRed")
        self.germ_farred_btn.setCheckable(True)
        self.germ_farred_btn.setFixedWidth(germ_btn_w)
        self.germ_farred_btn.setFixedHeight(button_height)
        self.germ_farred_btn.toggled.connect(
            lambda checked: self._toggle_manual_led(LED_GERM_FARRED_PIN, checked, self.germ_farred_btn, "#FF5722", "FarRed")
        )

        for _btn in (self.germ_blue_btn, self.germ_red_btn, self.germ_farred_btn):
            _btn.setStyleSheet(
                dark_style(s) + " QPushButton { background-color: #37474F; color: white; }"
            )
            germ_layout.addWidget(_btn)

        # Home + Advance row (layout preserved)
        ha_layout = QHBoxLayout()
        ha_layout.setSpacing(max(6,int(10 * s)))
        ha_layout.setContentsMargins(0, 0, 0, 0)

        self.home_btn = QPushButton("Home")
        self.home_btn.setObjectName("homeBtn")
        self.home_btn.setFixedWidth(button_width // 2 - 5)
        self.home_btn.setFixedHeight(button_height)
        self.home_btn.clicked.connect(self.on_home_clicked)

        self.advance_btn = QPushButton("Advance")
        self.advance_btn.setFixedWidth(button_width // 2 - 5)
        self.advance_btn.setFixedHeight(button_height)
        self.advance_btn.clicked.connect(lambda: self.run_motor_action("advance"))

        ha_layout.addWidget(self.home_btn)
        ha_layout.addWidget(self.advance_btn)

        self.experiment_btn = QPushButton("Experiment Setup")
        style_and_size(self.experiment_btn)
        self.experiment_btn.setStyleSheet(dark_style(s) + " QPushButton { background-color: #8E24AA; color: white; }")
        self.experiment_btn.clicked.connect(self.open_experiment_setup)

        self.end_experiment_btn = QPushButton("End Experiment")
        style_and_size(self.end_experiment_btn)
        self.end_experiment_btn.setStyleSheet(dark_style(s) + " QPushButton { background-color: #E53935; color: white; }")
        self.end_experiment_btn.clicked.connect(self.end_experiment)

        self.camera_config_btn = QPushButton("Camera Config")
        style_and_size(self.camera_config_btn)
        self.camera_config_btn.setStyleSheet(dark_style(s) + " QPushButton { background-color: #546E7A; color: white; }")
        self.camera_config_btn.clicked.connect(self.open_camera_config)

        # Focus mode indicator — updates on startup and after Camera Config Apply
        self.focus_mode_label = QLabel()
        self.focus_mode_label.setAlignment(Qt.AlignCenter)
        self.focus_mode_label.setFixedWidth(button_width)
        self.focus_mode_label.setStyleSheet(f"font-size: {max(9, int(8.75 * s))}px;")
        self._update_focus_mode_label()          # set text at startup

        self.file_manager_btn = QPushButton("File Manager")
        style_and_size(self.file_manager_btn)
        self.file_manager_btn.setStyleSheet(dark_style(s) + " QPushButton { background-color: #455A64; color: white; }")
        self.file_manager_btn.clicked.connect(self.open_file_manager)


        # Exit to Desktop (touch-friendly)
        self.exit_btn = QPushButton("Exit to Desktop")
        style_and_size(self.exit_btn)
        self.exit_btn.setStyleSheet(
            dark_style(s) + " QPushButton { background-color: #D32F2F; color: white; font-weight: bold; }"
        )
        self.exit_btn.clicked.connect(self.close)


        # Optional top stretch to center the whole stack vertically:
        button_layout.addStretch(2)

        # Group 1: View / Setup LEDs
        button_layout.addWidget(self.live_view_btn)
        button_layout.addSpacing(int(6 * s))

        setup_led_label = QLabel("Setup LEDs:")
        setup_led_label.setAlignment(Qt.AlignCenter)
        setup_led_label.setStyleSheet(f"color: #90A4AE; font-size: {max(9, int(8.75 * s))}px;")
        button_layout.addWidget(setup_led_label)
        button_layout.addSpacing(int(3 * s))
        button_layout.addLayout(setup_led_layout)

        button_layout.addStretch(1)

        # Group 1b: Germination/photomorphogenesis LEDs (independent of imaging illum)
        germ_label = QLabel("Germination LEDs:")
        germ_label.setAlignment(Qt.AlignCenter)
        germ_label.setStyleSheet(f"color: #90A4AE; font-size: {max(9, int(8.75 * s))}px;")
        button_layout.addWidget(germ_label)
        button_layout.addSpacing(int(3 * s))
        button_layout.addLayout(germ_layout)

        button_layout.addStretch(1)

        # Group 2: Motion
        button_layout.addLayout(ha_layout)

        button_layout.addStretch(1)

        # Group 3: Experiment
        button_layout.addWidget(self.experiment_btn)
        button_layout.addSpacing(int(6 * s))
        button_layout.addWidget(self.end_experiment_btn)

        button_layout.addStretch(1)

        # Group 4: Management
        button_layout.addWidget(self.camera_config_btn)
        button_layout.addWidget(self.focus_mode_label)
        button_layout.addSpacing(int(6 * s))
        button_layout.addWidget(self.file_manager_btn)
        button_layout.addSpacing(int(6 * s))
        button_layout.addWidget(self.exit_btn)


        # If Exit button exists:
        # button_layout.addSpacing(int(6 * s))
        # button_layout.addWidget(self.exit_btn)

        # Optional bottom stretch to balance the top stretch:
        button_layout.addStretch(1)

        # Add the left column to the main layout (keep your stretch setup)
        main_layout.addLayout(button_layout, stretch=0)

        # Right: status + camera + log
        right_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Ready"); self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        #right_layout.addWidget(self.status_label)

        # Experiment progress info — elapsed time + rough next-cycle ETA.
        # Only populated/visible while an experiment is running.
        self.experiment_info_label = QLabel("")
        self.experiment_info_label.setAlignment(Qt.AlignCenter)
        self.experiment_info_label.setWordWrap(True)
        self.experiment_info_label.setStyleSheet(f"font-size: {max(9, int(9 * s))}px; color: #90A4AE;")

        self.camera_label = QLabel("Camera Preview")
        self.camera_label.setAlignment(Qt.AlignCenter)

        # Lock the camera label to a fixed size so Qt's layout engine can never
        # change its dimensions between experiment snapshots.  Without this, the
        # label's sizeHint shifts when the log panel receives long save-path text,
        # causing the preview image to drift position and scale on System 1.
        _cam_w = int((_screen_w - button_width) * 0.95)
        _cam_h = int(_screen_h * 0.55)
        self.camera_label.setFixedSize(_cam_w, _cam_h)

        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)

        # Keep right-side stack but give preview more space than log
        right_layout.addWidget(self.status_label, stretch=0)
        right_layout.addWidget(self.experiment_info_label, stretch=0)
        right_layout.addWidget(self.camera_label, stretch=3)
        right_layout.addWidget(self.log_panel, stretch=2)

        main_layout.addLayout(right_layout, stretch=1)
        self.setLayout(main_layout)

        self.timer = QTimer(); self.timer.timeout.connect(self.update_camera_frame)
        self.live_view_active = False

        # Experiment progress info timer — deliberately coarse (1 min) per
        # design intent: this is a "rough" indicator, not a live countdown,
        # so it doesn't add meaningful overhead during long unattended runs.
        self.experiment_info_timer = QTimer()
        self.experiment_info_timer.timeout.connect(self._update_experiment_info)

        self.update_controls_for_experiment(False)

        # Apply persisted camera settings at startup. Run through the
        # guarded helper (background thread + bounded wait) rather than a
        # direct call — confirmed on real hardware (Sept 2026) that if the
        # Arducam USB3 device was left wedged from a previous session, a
        # direct call here could hang indefinitely inside v4l2-ctl before
        # this __init__() even finished, meaning the window never showed at
        # all and every subsequent autostart-triggered boot would hang the
        # exact same way, with no way to reach the GUI to fix it. See
        # _run_camera_call_guarded()'s docstring for the full explanation.
        self._run_camera_call_guarded(camera.apply_settings, timeout_ms=4000, what="startup apply_settings()")

        # Ensure the Live View button text/style matches the current state at startup
        self._update_live_view_button()
        QTimer.singleShot(200, lambda: self.set_live_view(True))


    # ---------- Imaging illumination (Rear IR — sole imaging source) ----------
    def _set_rear_ir(self, on: bool):
        """GPIO-only — safe to call from ExperimentRunner's background thread."""
        if not led_request:
            return
        led_request.set_value(LED_REAR_IR_PIN, Value.ACTIVE if on else Value.INACTIVE)

    def _sync_rear_ir_button(self, on: bool):
        """GUI-thread only: sync the manual button's look to actual GPIO state."""
        if not hasattr(self, "rear_ir_btn"):
            return
        s = self._s
        self.rear_ir_btn.blockSignals(True)
        self.rear_ir_btn.setChecked(on)
        if on:
            self.rear_ir_btn.setStyleSheet(
                dark_style(s) + " QPushButton { background-color: #C2185B; color: white; font-weight: bold; }"
            )
        else:
            self.rear_ir_btn.setStyleSheet(
                dark_style(s) + " QPushButton { background-color: #37474F; color: white; }"
            )
        self.rear_ir_btn.blockSignals(False)

    def _on_rear_ir_button_toggled(self, checked: bool):
        self._set_rear_ir(checked)
        self._sync_rear_ir_button(checked)
        self.update_status(f"Rear IR LED: {'ON' if checked else 'OFF'}")

    # ---------- Manual/independent LED toggles (setup + germination) ----------
    def _toggle_manual_led(self, pin: int, checked: bool, btn: "QPushButton", on_color: str, label: str):
        """
        Independent on/off for a single manually-toggled LED channel (Rear
        IR / Green setup LEDs, or the Blue/Red/FarRed germination strip).
        Each button just reflects and drives its own GPIO line directly —
        not coupled to Live View, experiment state, or to each other.
        """
        if led_request:
            try:
                led_request.set_value(pin, Value.ACTIVE if checked else Value.INACTIVE)
            except Exception as e:
                print(f"[manual LED] set_value error on pin {pin}: {e}", flush=True)
        else:
            print("[manual LED] led_request unavailable — GPIO not initialized.", flush=True)

        s = self._s
        if checked:
            btn.setStyleSheet(
                dark_style(s) + f" QPushButton {{ background-color: {on_color}; color: white; font-weight: bold; }}"
            )
        else:
            btn.setStyleSheet(
                dark_style(s) + " QPushButton { background-color: #37474F; color: white; }"
            )
        self.update_status(f"{label} LED: {'ON' if checked else 'OFF'}")

    # ---------- Germination LED control for automated DAYLIGHT/DARK runs ----------
    def set_germination_led_raw(self, pin: int, on: bool):
        """
        Direct GPIO control for a germination-strip channel, used by
        ExperimentRunner to apply DAYLIGHT (static) or DARK (timer-
        triggered) settings during an automated run. Does not update the
        manual Blue/Red/FarRed button state/style — those buttons reflect
        manual toggles only; a channel switched on by the experiment runner
        won't visually flip the corresponding button (cosmetic limitation,
        flagged for a future pass).
        """
        if not led_request:
            print("[germination LED raw] led_request unavailable — GPIO not initialized.", flush=True)
            return
        try:
            led_request.set_value(pin, Value.ACTIVE if on else Value.INACTIVE)
        except Exception as e:
            print(f"[germination LED raw] set_value error on pin {pin}: {e}", flush=True)

    # ---------- Home/Stop logic (manual use via Home button) ----------
    def on_home_clicked(self):
        """Toggle behavior: start homing or request stop."""
        if self.homing_worker is None or not self.homing_worker.isRunning():
            self.start_homing()
        else:
            self.stop_homing()

    def start_homing(self):
        # Ensure driver is enabled before motion (EN low = enabled per wiring)
        motor_control.driver_enable()  # enable driver  [1](https://uwprod-my.sharepoint.com/personal/sybednar_wisc_edu/Documents/Microsoft%20Copilot%20Chat%20Files/git_update.sh.txt)

        # Update UI to STOP state (direct, per-widget style to override app-wide blue)
        self.home_btn.setText("STOP")
        self.home_btn.setStyleSheet("background-color: #E53935; color: white; font-weight: bold;")
        # Disable potentially conflicting controls during homing (keep Home enabled for STOP)
        self.advance_btn.setEnabled(False)
        self.experiment_btn.setEnabled(False)
        self.camera_config_btn.setEnabled(False)

        # Launch worker
        self.homing_worker = HomingWorker()
        self.homing_worker.status_signal.connect(self.update_status)
        self.homing_worker.finished_with_result.connect(self.on_homing_finished)
        self.homing_worker.start()
        self.update_status("Homing started...")

    def stop_homing(self):
        # Immediate hardware e-stop: cut coil current now (EN high = disabled)
        motor_control.driver_disable()  # disable driver  [1](https://uwprod-my.sharepoint.com/personal/sybednar_wisc_edu/Documents/Microsoft%20Copilot%20Chat%20Files/git_update.sh.txt)
        if self.homing_worker and self.homing_worker.isRunning():
            self.homing_worker.request_stop()
            self.update_status("Emergency stop requested... (driver disabled)")

    def on_homing_finished(self, plate_or_none):
        # Restore UI to normal state
        self.home_btn.setText("Home")
        self.home_btn.setStyleSheet("")  # clear per-widget override; fallback to app-wide blue
        self.advance_btn.setEnabled(True)
        self.experiment_btn.setEnabled(True)
        self.camera_config_btn.setEnabled(True)

        self.homing_worker = None

        if plate_or_none is None:
            # Leave driver disabled after emergency stop for safety.
            self.update_status("Homing aborted or failed. Driver remains DISABLED.")
        else:
            # Keep driver enabled after normal completion (holding torque).
            self.update_status("Homing finished. Driver remains ENABLED.")

    # ---------- Homing-with-preview right before starting an experiment ----------
    def open_experiment_setup(self):
        if self.live_view_active:
            self.toggle_live_view()
        dialog = ExperimentSetupDialog(self)
        if dialog.exec() == QDialog.Accepted:
            growth_settings = (
                dialog.daylight_settings if dialog.growth_mode == GROWTH_MODE_DAYLIGHT
                else dialog.dark_settings
            )
            # Run homing with preview first, then launch the runner
            self.start_experiment_with_homing_preview(
                plates=dialog.selected_plates,
                days=dialog.duration_days,
                freq=dialog.frequency_minutes,
                growth_mode=dialog.growth_mode,
                growth_settings=growth_settings,
            )

    def start_experiment_with_homing_preview(self, plates, days, freq, growth_mode, growth_settings):
        """
        1) Turn on Live View so the user SEES homing (Rear IR — the sole
           imaging illumination — turns on automatically).
        2) Perform homing via HomingWorker (STOP/E-stop available through Home button).
        3) On success: stop Live View and start ExperimentRunner(skip homing).
        """
        # Turn on Live View (drives Rear IR automatically)
        if not self.live_view_active:
            self.toggle_live_view()
        self.update_status("Starting homing (with preview)... Press STOP to abort if needed.")

        # Ensure driver enabled, set Home button to STOP style, and disable other controls
        motor_control.driver_enable()  # enable driver  [1](https://uwprod-my.sharepoint.com/personal/sybednar_wisc_edu/Documents/Microsoft%20Copilot%20Chat%20Files/git_update.sh.txt)
        self.home_btn.setText("STOP")
        self.home_btn.setStyleSheet("background-color: #E53935; color: white; font-weight: bold;")
        self.advance_btn.setEnabled(False)
        self.experiment_btn.setEnabled(False)
        self.camera_config_btn.setEnabled(False)

        # Launch a dedicated homing worker
        self.homing_worker = HomingWorker()
        self.homing_worker.status_signal.connect(self.update_status)
        # When homing completes, continue to experiment or abort
        self.homing_worker.finished_with_result.connect(
            lambda plate_or_none: self._on_preview_homing_done(
                plate_or_none, plates, days, freq, growth_mode, growth_settings
            )
        )
        self.homing_worker.start()

    def _on_preview_homing_done(self, plate_or_none, plates, days, freq, growth_mode, growth_settings):
        # Restore Home button and re-enable the controls disabled for the preview-homing step
        self.home_btn.setText("Home")
        self.home_btn.setStyleSheet("")
        self.advance_btn.setEnabled(True)
        self.experiment_btn.setEnabled(True)
        self.camera_config_btn.setEnabled(True)

        self.homing_worker = None

        if plate_or_none is None:
            # Homing aborted/failed — stop preview and keep driver disabled (safety).
            if self.live_view_active:
                self.toggle_live_view()
            self.update_status("Experiment start aborted: homing failed or was stopped. Driver remains DISABLED.")
            return

        # Homing succeeded: stop preview before starting the experiment run
        if self.live_view_active:
            self.toggle_live_view()

        # Start the standard experiment loop, but SKIP homing (we just did it with preview)
        self.start_experiment(plates, days, freq, growth_mode, growth_settings, skip_initial_homing=True)

    # ---------- Experiment orchestration ----------
    def start_experiment(self, plates, days, freq, growth_mode, growth_settings, skip_initial_homing=False):
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.update_status("Experiment already running."); return
        # Ensure Live View is off during the experiment
        if self.live_view_active:
            self.toggle_live_view()

        # Create the runner, passing perform_homing flag inverse of skip_initial_homing
        self.experiment_thread = ExperimentRunner(
            plates, days, freq,
            illumination_mode=ILLUM_REAR_IR,
            led_control_fn=self.set_led,
            growth_mode=growth_mode,
            growth_settings=growth_settings,
            germ_led_control_fn=self.set_germination_led_raw,
            perform_homing=(not skip_initial_homing)
        )
        self.experiment_thread.status_signal.connect(self.update_status)
        self.experiment_thread.image_saved_signal.connect(lambda p: self.log_panel.append(f"Image saved: {p}"))
        self.experiment_thread.plate_signal.connect(lambda idx: self.status_label.setText(f"Plate #{idx}"))
        self.experiment_thread.settling_started.connect(self.show_experiment_snapshot)
        self.experiment_thread.cycle_wait_started.connect(self._on_cycle_wait_started)
        self.experiment_thread.finished_signal.connect(self.on_experiment_finished)
        self.update_controls_for_experiment(True)

        # Start tracking elapsed time / next-cycle ETA for the info label.
        self._experiment_start_time = datetime.now()
        self._next_cycle_eta = None
        self._update_experiment_info()
        self.experiment_info_timer.start(60000)  # refresh once a minute

        self.experiment_thread.start()

    def end_experiment(self):
        if self.experiment_thread and self.experiment_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Experiment in Progress",
                "Experiment in Progress: Do you really want to end experiment?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return  # "No" — leave the experiment running untouched

            # Do NOT call self.experiment_thread.wait() here — that blocks the
            # GUI thread's event loop until the background thread's run()
            # fully returns, which can take several seconds if ending is
            # confirmed while the motor is mid-move or the camera is
            # mid-capture. That block previously caused a full GUI freeze.
            # Instead, just signal abort and disable the button so it can't
            # be clicked again; the existing finished_signal ->
            # on_experiment_finished() connection already re-enables controls
            # and updates status once the thread exits on its own, non-blocking.
            self.experiment_thread.abort()
            self.end_experiment_btn.setEnabled(False)
            self.update_status("Ending experiment... waiting for current motor/camera operation to finish.")
        else:
            self.update_status("No experiment running.")
            self.update_controls_for_experiment(False)


    def on_experiment_finished(self):
        self.update_controls_for_experiment(False)
        self.update_status("Experiment finished.")
        self.experiment_info_timer.stop()
        self.experiment_info_label.setText("")
        self._experiment_start_time = None
        self._next_cycle_eta = None

    # ---------- Experiment progress info (elapsed time / next-cycle ETA) ----------
    def _on_cycle_wait_started(self, freq_minutes: int):
        """Called once per cycle, right as the inter-cycle wait begins."""
        self._next_cycle_eta = datetime.now() + timedelta(minutes=freq_minutes)
        self._update_experiment_info()

    def _update_experiment_info(self):
        if not self._experiment_start_time:
            self.experiment_info_label.setText("")
            return
        elapsed_h = (datetime.now() - self._experiment_start_time).total_seconds() / 3600.0
        if self._next_cycle_eta:
            remaining_s = (self._next_cycle_eta - datetime.now()).total_seconds()
            if remaining_s > 30:
                remaining_min = max(1, round(remaining_s / 60))
                next_txt = f"Next cycle in ~{remaining_min} min"
            else:
                next_txt = "Imaging in progress"
        else:
            next_txt = "Next cycle: calculating..."
        # Two lines instead of one combined "Elapsed | Next" line — on the
        # 800x480 display a single wide line can run past the label's box
        # and get clipped. Two short lines stay comfortably within width.
        self.experiment_info_label.setText(f"Elapsed: {elapsed_h:.1f} h\n{next_txt}")


    def update_controls_for_experiment(self, running: bool):
        """Enable/disable controls while an experiment is running."""
        # Live View and motion/Config controls should be disabled during a run
        self.live_view_btn.setEnabled(not running)
        self.home_btn.setEnabled(not running)
        self.advance_btn.setEnabled(not running)
        self.experiment_btn.setEnabled(not running)
        self.camera_config_btn.setEnabled(not running)
        # Only the "End Experiment" button is enabled during a run
        self.end_experiment_btn.setEnabled(running)

    # ---------- Camera / LEDs / File manager ----------
    def update_status(self, text):
        self.status_label.setText(text)
        self.log_panel.append(text)


    def _run_camera_call_guarded(self, fn, timeout_ms=4000, what=""):
        """
        Run fn() (a no-arg camera.* call) on a background thread, and wait
        for it via a local QEventLoop instead of calling it directly here.

        Why: for the Arducam backend, several camera.* calls (apply_settings,
        enable_liveview_boost_for_ir, disable_liveview_boost) go through
        camera_arducam_usb3.py's _v4l2_set()/_v4l2_get(), which shell out to
        `v4l2-ctl` via subprocess.run(..., timeout=5). That 5-second timeout
        assumes the child process CAN be killed if it's slow. Confirmed on
        real hardware (Sept 2026): if the USB3 device itself is wedged, the
        v4l2-ctl child can enter an uninterruptible kernel wait that not even
        SIGKILL clears — so subprocess.run()'s own timeout can end up
        blocking indefinitely too, waiting to reap a child that cannot die.

        These particular calls are NOT confined to the (occasional, manual)
        Camera Config dialog — set_live_view() calls them automatically on
        every app startup and every homing/plate-advance cycle during an
        unattended, possibly multi-day experiment. Running them directly on
        this thread previously meant a wedged device would freeze the whole
        GUI event loop (and, since this app runs fullscreen, the whole
        display) — either at startup (before the window even showed) or
        silently mid-experiment with nobody watching, requiring a hard power
        cycle to recover either way.

        Running fn() on a background QThread and waiting via a *local*
        QEventLoop (rather than QThread.wait(), a plain blocking call) means
        the real Qt event loop keeps pumping while we wait — the window
        stays repaintable/closeable — and the QTimer.singleShot(timeout_ms, ...)
        below imposes a hard ceiling on how long we wait. If fn() hasn't
        finished by timeout_ms, we stop waiting and return False, but the
        worker thread itself is left running in the background — if fn() is
        truly stuck on an unkillable kernel-level wait, there is no way to
        forcibly stop it, only to stop waiting on it. This does not fix or
        prevent a wedged USB device; it only prevents that failure mode from
        taking down the whole GUI/display with it.

        Returns True if fn() completed successfully within timeout_ms,
        False otherwise (it either raised, or didn't finish in time).
        """
        worker = _CameraCallWorker(fn)
        loop = QEventLoop()
        result = {"ok": False, "settled": False}

        def _on_done(ok, err):
            result["ok"] = ok
            result["settled"] = True
            if not ok and err:
                print(f"[gui] {what} error: {err}", flush=True)
            loop.quit()

        worker.finished_ok.connect(_on_done)
        self._guarded_camera_workers.append(worker)

        worker.start()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

        if not result["settled"]:
            print(
                f"[gui] {what} did not complete within {timeout_ms}ms — "
                f"proceeding without waiting further (possible wedged camera device).",
                flush=True,
            )
        else:
            try:
                self._guarded_camera_workers.remove(worker)
            except ValueError:
                pass
        return result["ok"] and result["settled"]

    def apply_liveview_camera_profile(self):
        # Rear IR (transmission) is the only imaging illumination now, so
        # the transmission preset always applies — no mode branching needed.
        # Uses the LIVE VIEW preset specifically, not the capture preset —
        # see apply_ir_transmission_preset_liveview() in the active camera
        # backend for why these are now separate (confirmed on real
        # hardware, Sept 2026: Live View and full-res capture are not
        # equally sensitive at the same settings on the Arducam backend).
        base = camera.get_current_settings()
        base = camera.apply_ir_transmission_preset_liveview(base)
        camera.apply_settings(base)


    def run_motor_action(self, action: str):
        """
        Start a motor action (currently only 'advance') in a background thread.
        Keeps a reference to the thread so it isn't garbage-collected.
        """
        # Don't allow advance during homing or experiment runs
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.update_status("Motor action blocked: experiment is running.")
            return
        if self.homing_worker and self.homing_worker.isRunning():
            self.update_status("Motor action blocked: homing is running.")
            return

        # Disable the advance button while the action runs to prevent double-clicks
        if action == "advance":
            self.advance_btn.setEnabled(False)

        worker = MotorWorker(action)
        worker.status_signal.connect(self.update_status)

        # Re-enable controls when done and drop the reference
        def _cleanup():
            if action == "advance":
                self.advance_btn.setEnabled(True)
            try:
                self.threads.remove(worker)
            except ValueError:
                pass

        worker.finished.connect(_cleanup)

        # Keep reference alive
        self.threads.append(worker)
        worker.start()


    def _update_live_view_button(self):
        """Update Live View button text + style to reflect current state."""
        s = self._s
        if self.live_view_active:
            self.live_view_btn.setText("Turn Live View Off")
            self.live_view_btn.setStyleSheet(
                dark_style(s) + " QPushButton { background-color: #43A047; color: white; font-weight: bold; }"
            )
        else:
            self.live_view_btn.setText("Turn Live View On")
            self.live_view_btn.setStyleSheet(
                dark_style(s) + " QPushButton { background-color: #FFD600; color: black; font-weight: bold; }"
            )

    def set_live_view(self, enable: bool):
        """
        Explicitly enable/disable Live View (idempotent).
        Rear IR is the sole imaging illumination now; the liveview boost
        is always applied and Rear IR is driven automatically via
        _set_rear_ir().
        """
        # No-op if already in desired state
        if enable and self.live_view_active:
            return
        if (not enable) and (not self.live_view_active):
            return

        if enable:
            camera.start_camera()

            # Apply the transmission (Rear IR) camera profile — guarded
            # (background thread + bounded wait); see
            # _run_camera_call_guarded()'s docstring. This runs on every
            # startup and homing/plate-advance cycle, not just from the
            # Camera Config dialog, so it must not be able to freeze the
            # whole GUI if the Arducam device is wedged.
            self._run_camera_call_guarded(
                self.apply_liveview_camera_profile, timeout_ms=4000,
                what="apply_liveview_camera_profile()",
            )

            # Always apply the live-view brightness boost for Rear IR — also guarded.
            self._run_camera_call_guarded(
                lambda: camera.enable_liveview_boost_for_ir(
                    target_gain=2.0, target_exposure_us=4000, mode=ILLUM_REAR_IR
                ),
                timeout_ms=4000, what="enable_liveview_boost_for_ir()",
            )

            camera.set_af_mode(2)  # Continuous AF for preview

            self.timer.start(100)
            self.live_view_active = True
            self._update_live_view_button()

            # Turn ON Rear IR
            self._set_rear_ir(True)
            self._sync_rear_ir_button(True)

            self.update_status("Live View started. Rear IR LED ON.")

        else:
            self.timer.stop()

            # Always clear any preview boost when leaving Live View — guarded, same reasoning as above.
            self._run_camera_call_guarded(
                camera.disable_liveview_boost, timeout_ms=4000, what="disable_liveview_boost()"
            )

            camera.stop_camera()
            self.live_view_active = False
            self._update_live_view_button()

            # Turn OFF Rear IR
            self._set_rear_ir(False)
            self._sync_rear_ir_button(False)

            self.update_status("Live View stopped.")

    def toggle_live_view(self):
        """UI button handler: toggle live view on/off."""
        self.set_live_view(not self.live_view_active)

    def _set_preview_pixmap(self, pixmap: QPixmap):
        """
        Scale pixmap to fit fully inside camera_label, preserving the source's
        true aspect ratio with no cropping. camera_label already has a fixed
        size via setFixedSize(), so the label's own footprint in the layout
        never changes regardless of the pixmap's size — Qt.KeepAspectRatio
        guarantees the scaled result never exceeds (lw, lh), so there's no
        risk of the layout-drift problem that motivated the old expand-and-
        crop approach. Any leftover space just appears as blank margin on
        the shorter axis, instead of silently cropping off real image
        content — which is what was happening: camera_label's box shape is
        derived from leftover screen space (sized for Picamera2's ~16:9
        preview), and cropping a 4:3 Arducam frame to fit that box was
        hiding roughly a quarter of the actual field of view in Live View,
        even though the saved full-resolution capture was never cropped.
        """
        lw = self.camera_label.width()
        lh = self.camera_label.height()
        if lw < 2 or lh < 2:
            return
        scaled = pixmap.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.camera_label.setPixmap(scaled)

    def show_experiment_snapshot(self, plate_idx: int):
        """
        During an experiment, show a single low-res snapshot (lores) at the start
        of each plate's settling window so users can see the carousel cycling.
        """
        # If live view is active, snapshots are redundant (and Live View is usually off during runs)
        if self.live_view_active:
            return

        frame = camera.get_frame()
        if frame.isNull():
            return

        pixmap = QPixmap.fromImage(frame)
        self._set_preview_pixmap(pixmap)

        # Optional: make it explicit what the user is seeing
        self.status_label.setText(f"Plate #{plate_idx} (snapshot)")

    def update_camera_frame(self):
        frame = camera.get_frame()
        if frame.isNull():
            return

        pixmap = QPixmap.fromImage(frame)
        self._set_preview_pixmap(pixmap)

    def open_camera_config(self):
        # Camera pipeline stays running while the dialog is open so that:
        #   (a) "Read Current Position from Camera" can query live metadata, and
        #   (b) pressing Apply immediately shows the effect in the Live View preview.
        # The _cam_lock in camera.py protects concurrent access between the
        # live-view timer and any set_controls() calls made by the dialog.

        dialog = CameraConfigDialog(current_settings=camera.get_current_settings(), parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.setCursor(Qt.WaitCursor)
            self.update_status("Applying camera settings...")
            worker = SettingsApplier(dialog.settings, preview_was_active=self.live_view_active)
            worker.done.connect(
                lambda ok, msg: self._on_settings_applied(ok, msg, self.live_view_active, worker)
            )
            if not hasattr(self, "_settings_workers"):
                self._settings_workers = []
            self._settings_workers.append(worker)
            worker.start()
        # No else branch needed — if the user cancels, camera state is unchanged.

    def _update_focus_mode_label(self):
        """Refresh the focus mode indicator from persisted settings."""
        from camera_config import load_settings as _load_cam_settings
        cs = _load_cam_settings()
        sc = self._s
        ffs = max(9, int(8.75 * sc))   # label font, scaled
        if cs.get("ManualFocusEnable", False):
            pos = float(cs.get("ManualFocusPosition", 0.0))
            dist_cm = (1.0 / pos * 100) if pos > 0 else 0
            self.focus_mode_label.setText(f"MF: {pos:.2f} D  ({dist_cm:.0f} cm)")
            self.focus_mode_label.setStyleSheet(f"font-size: {ffs}px; color: #FFD600;")  # yellow = manual
        else:
            self.focus_mode_label.setText("Focus: Auto")
            self.focus_mode_label.setStyleSheet(f"font-size: {ffs}px; color: #AAAAAA;")  # grey = auto

    def _on_settings_applied(self, ok: bool, msg: str, was_live: bool, worker: QThread):
        # Restore cursor
        self.unsetCursor()
        # Drop the worker reference
        try:
            self._settings_workers.remove(worker)
        except Exception:
            pass
        # Report to user
        self.update_status(msg)
        self._update_focus_mode_label()
        # If the preview was previously active, turn it back on so the user sees the effect
        if was_live and not self.live_view_active:
            self.toggle_live_view()

    def set_led(self, on: bool, mode: str = None):
        """led_control_fn passed to ExperimentRunner for imaging illumination.
        mode is accepted for backward compatibility but ignored — Rear IR
        is the sole imaging illumination source now."""
        self._set_rear_ir(on)

    def open_file_manager(self):
        # Stop Live View to avoid racing the camera while user manages files (optional)
        if self.live_view_active:
            self.toggle_live_view()
        dlg = FileManagerDialog(self)
        dlg.showMaximized()   # maximize for usability on Touch Display 2
        dlg.exec()



    def keyPressEvent(self, event):
        # Backdoor exit: ESC closes the app
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


    def closeEvent(self, event):
        # Graceful shutdown
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.experiment_thread.abort()
            self.experiment_thread.wait()
        if self.homing_worker and self.homing_worker.isRunning():
            self.stop_homing()
            self.homing_worker.wait()
        if self.live_view_active:
            self.toggle_live_view()
        event.accept()


# Abortable homing worker
class HomingWorker(QThread):
    status_signal = Signal(str)
    finished_with_result = Signal(object)  # plate index (int) on success, or None

    def __init__(self):
        super().__init__()
        self._abort = False

    def request_stop(self):
        self._abort = True

    def _should_abort(self):
        return self._abort

    def run(self):
        try:
            plate = motor_control.home(
                status_callback=self.status_signal.emit,
                should_abort=self._should_abort
            )
            if plate is not None:
                self.status_signal.emit(f"Homing finished. Plate #{plate}")
            else:
                self.status_signal.emit("Homing stopped.")
            self.finished_with_result.emit(plate)
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")
            self.finished_with_result.emit(None)


# MotorWorker class (kept for 'advance' only, with driver enable)
class MotorWorker(QThread):
    status_signal = Signal(str)

    def __init__(self, action):
        super().__init__()
        self.action = action

    def run(self):
        try:
            if self.action == "advance":
                self.status_signal.emit("Advancing to next plate...")
                motor_control.driver_enable()  # ensure enabled before motion
                motor_control.advance(status_callback=self.status_signal.emit)
            elif self.action == "home":
                # Not used anymore (replaced by HomingWorker), kept for compatibility
                motor_control.driver_enable()
                plate = motor_control.home(status_callback=self.status_signal.emit)
                if plate is not None:
                    self.status_signal.emit(f"Homing finished. Plate #{plate}")
                else:
                    self.status_signal.emit("Homing failed")
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")

# ---- SettingsApplier: apply camera settings off the GUI thread ----
class SettingsApplier(QThread):
    done = Signal(bool, str)  # (success, message)

    def __init__(self, settings: dict, preview_was_active: bool):
        super().__init__()
        self.settings = dict(settings) if settings else {}
        self.preview_was_active = bool(preview_was_active)

    def run(self):
        try:
            # Ensure a running pipeline before setting controls; many controls are safer then
            camera.start_camera()
            camera.apply_settings(self.settings)
            ok = True
            msg = "Camera settings applied."
        except Exception as e:
            ok = False
            msg = f"Camera settings error: {e}"
        finally:
            # If Live View was not previously active, stop again so we leave state as we found it
            if not self.preview_was_active:
                try:
                    camera.stop_camera()
                except Exception:
                    pass
        self.done.emit(ok, msg)
