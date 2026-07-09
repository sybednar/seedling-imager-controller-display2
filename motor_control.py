# motor_control.py — dynamic bracket midpoint centering, all 6 plates
#
# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
#  Microstepping : 1/32  →  BTT TMC2209: MS2=GND, MS1=VCC_IO (3.3 V)
#  Drive ratio   : 3:1 belt  (NEMA 17 → carousel)
#  Steps per 60° : 200 full-steps × 32 microsteps × 3 (belt) / 6 plates = 3200
#  Optical stripe: 5 mm wide white PETG insert; expected W ≈ 192 µsteps
#  Hall sensor   : between plate positions 4 and 5 (active LOW, SWITCH_PIN=26)
#
# ═══════════════════════════════════════════════════════════════════════════════
# ⚠  IMPORTANT — BEFORE FIRST RUN AFTER HARDWARE CHANGE
# ═══════════════════════════════════════════════════════════════════════════════
#  Delete  motion_cal.json  if upgrading from a different microstepping setting.
#  Saved hall_to_leading / W values scale with step resolution; old values will
#  cause incorrect positioning at the new resolution.
# ═══════════════════════════════════════════════════════════════════════════════
#
# Flow:
#   1) Seek Hall sensor (pre-index, fast CW rotation)
#   2) CW to optical LOW (leading edge of Plate 1 stripe) → measure steps_to_leading
#   3) CW to optical HIGH (trailing edge) → measure initial W
#   4) Dynamic bracket (backlash-robust):
#        CW→HIGH (escape stripe if needed), CCW→LOW (trailing), CCW→HIGH (past
#        leading, measure W fresh), CW→LOW (re-validate leading), CW +round(W/2)
#   5) Persist W, hall→centre to motion_cal.json
#   6) Each advance (plates 2-6): bracket-centre on arriving stripe (fresh W)
#   7) Plate 1 wrap: same bracket with separate log prefix for clarity
#
# Public API (unchanged from v1.0):
#   driver_enable(), driver_disable(), step_motor(), home(), advance(),
#   goto_plate(), get_current_plate(), get_calibration(),
#   rehome_quick_via_hall(), rehome_full_from_hall()

import time
import json
from pathlib import Path
import gpiod
from gpiod.line import Direction, Value, Bias

# ─────────────────────────────────────────────────────────────────────────────
# GPIO pin assignments
# ─────────────────────────────────────────────────────────────────────────────
CHIP        = "/dev/gpiochip0"
EN_PIN      = 21
STEP_PIN    = 20
DIR_PIN     = 16
SWITCH_PIN  = 26   # Hall sensor     (active LOW)
OPTICAL_PIN = 19   # Reflective opt. (active LOW when stripe is under sensor)

# ─────────────────────────────────────────────────────────────────────────────
# Motion constants  —  1/32 microstepping
# ─────────────────────────────────────────────────────────────────────────────
# 200 full-steps/rev × 32 µsteps × 3:1 belt / 6 positions = 3200 µsteps per 60°
steps_per_60_deg = 3200

# Step pulse half-period (seconds).
# SLOW_DELAY = 1.0 ms  →  500 steps/s  →  ~6.4 s per 60° advance.
# FAST_DELAY = 0.5 ms  →  1000 steps/s  →  used for Hall seek & rapid moves.
SLOW_DELAY = 0.0010
FAST_DELAY = 0.0005

# Hall seek batch size — number of steps per polling iteration.
# 40 steps × 1 ms/step = 40 ms/batch.  At 19 200 steps/rev this gives ~19 s
# worst-case seek (Hall just behind current position), comfortably within the
# 20 s timeout below.  Scale this if FAST_DELAY is changed.
HALL_STEP_BATCH = 40

# ─────────────────────────────────────────────────────────────────────────────
# Centering options
# ─────────────────────────────────────────────────────────────────────────────
DIR_INVERT = True   # True for belt drive;  False for gear/direct drive

# Dynamic bracket backoff fraction.
# 0.0 = land exactly at geometric centre of stripe (recommended).
# Small positive value (e.g. 0.05) shifts landing slightly CCW of centre.
CENTER_BACKOFF_FRAC = 0.0

# Optional CW trim after backoff.  Keep 0 — avoids double-applying CW after
# the backoff step.  Increase only if you observe a consistent CW bias.
FINE_CENTER_TRIM = 0

# ─────────────────────────────────────────────────────────────────────────────
# Optical window (W) validity bounds  —  5 mm stripe @ 1/32 µstepping
# ─────────────────────────────────────────────────────────────────────────────
# Geometry:  R_trigger ≈ 80 mm, circumference ≈ 502 mm
#            steps/mm @ 1/32 = 19 200 steps/rev / 502 mm = 38.2 steps/mm
#            5 mm stripe → W ≈ 5 × 38.2 = 191 ≈ 192 steps
#
# W_MIN_VALID  : below this → stripe too narrow / sensor misaligned / wrong pin
# W_MAX_VALID  : above this → spurious read (two stripes merged, wrong pin, etc.)
# W_FALLBACK   : substituted only when measurement falls outside valid range
#                (triggers a logged warning; investigate before relying on it)
W_MIN_VALID =  80
W_MAX_VALID = 350
W_FALLBACK  = 192

# ─────────────────────────────────────────────────────────────────────────────
# Seek distance limits (µsteps)  —  all scaled ×4 vs 1/8 microstepping
# ─────────────────────────────────────────────────────────────────────────────
# _FULL_SPAN   : default limit for inter-plate seeks (CW/CCW to stripe edge).
#                2 × 60° = 120° of carousel travel — safely finds any edge
#                within one plate-spacing even if the advance overshot.
_FULL_SPAN  = steps_per_60_deg * 2   # 6400 µsteps

# _HALL_LEAD   : maximum steps from Hall trigger to Plate 1 leading edge.
#                Set equal to _FULL_SPAN (120°) which is generous.
_HALL_LEAD  = steps_per_60_deg * 2   # 6400 µsteps

# _W_SEEK_LIM  : limit for the CCW→HIGH seek that measures stripe width (W).
#                Must be > W_MAX_VALID.  800 >> 350, giving 2× headroom.
_W_SEEK_LIM = 800                    # µsteps

# ─────────────────────────────────────────────────────────────────────────────
# Calibration persistence
# ─────────────────────────────────────────────────────────────────────────────
CAL_PATH = Path("motion_cal.json")
_cal = {
    "opt_window_width":        None,   # W  (µsteps) — last measured stripe width
    "opt_center_from_leading": None,   # C = W // 2  (geometric midpoint offset)
    "hall_to_leading":         None,   # µsteps: Hall trigger → Plate 1 leading edge
    "hall_to_center":          None,   # µsteps: Hall trigger → Plate 1 centre
}

current_plate = 0   # 0 = unknown / not yet homed

# ─────────────────────────────────────────────────────────────────────────────
# GPIO line request
# ─────────────────────────────────────────────────────────────────────────────
request = gpiod.request_lines(
    CHIP,
    consumer="seedling_imager",
    config={
        EN_PIN:      gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        DIR_PIN:     gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
        STEP_PIN:    gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        SWITCH_PIN:  gpiod.LineSettings(direction=Direction.INPUT,  bias=Bias.PULL_UP),
        OPTICAL_PIN: gpiod.LineSettings(direction=Direction.INPUT,  bias=Bias.PULL_UP),
    }
)

# ═══════════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════════
DEBUG_VERBOSE = True

def _log(msg: str):
    if DEBUG_VERBOSE:
        print(f"[motor] {msg}", flush=True)


def _set_dir_cw(is_cw: bool = True):
    """Set motor direction, honouring DIR_INVERT for belt/gear drives."""
    logical = is_cw if not DIR_INVERT else (not is_cw)
    request.set_value(DIR_PIN, Value.ACTIVE if logical else Value.INACTIVE)


def _debounced_read(pin, samples: int = 5, dt: float = 0.0004) -> Value:
    """
    Majority-vote debounce over `samples` reads spaced `dt` seconds apart.
    Returns Value.ACTIVE if >= ceil(samples/2) reads are ACTIVE, else INACTIVE.
    """
    ones = 0
    for _ in range(samples):
        if request.get_value(pin) == Value.ACTIVE:
            ones += 1
        time.sleep(dt)
    return Value.ACTIVE if ones >= (samples - ones) else Value.INACTIVE


def _is_low(pin) -> bool:
    """Return True when pin reads LOW (sensor active / stripe under sensor)."""
    return _debounced_read(pin) == Value.INACTIVE


def driver_enable():
    """Enable TMC2209 outputs (EN pin LOW)."""
    request.set_value(EN_PIN, Value.INACTIVE)


def driver_disable():
    """Disable TMC2209 outputs (EN pin HIGH) — motor coasts, holding torque lost."""
    request.set_value(EN_PIN, Value.ACTIVE)


def step_motor(steps: int, delay: float = SLOW_DELAY, should_abort=None) -> bool:
    """
    Send `steps` step pulses at the given half-period `delay`.
    Total time = steps x 2 x delay.
    Returns False immediately if should_abort() returns True; otherwise True.
    """
    for _ in range(steps):
        if callable(should_abort) and should_abort():
            return False
        request.set_value(STEP_PIN, Value.ACTIVE)
        time.sleep(delay)
        request.set_value(STEP_PIN, Value.INACTIVE)
        time.sleep(delay)
    return True


def _load_cal():
    try:
        if CAL_PATH.exists():
            _cal.update(json.loads(CAL_PATH.read_text()))
    except Exception:
        pass


def _save_cal():
    try:
        CAL_PATH.write_text(json.dumps(_cal, indent=2))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Low-level edge seekers
# ═══════════════════════════════════════════════════════════════════════════════

def _seek_transition(expect_low: bool, dir_cw: bool,
                     delay: float = SLOW_DELAY,
                     limit: int   = _FULL_SPAN,
                     should_abort = None):
    """
    Move in direction `dir_cw` until the optical sensor reaches the target state.

      expect_low=True  -> seek LOW  (stripe leading edge enters sensor field)
      expect_low=False -> seek HIGH (stripe trailing edge leaves sensor field)

    Returns the number of µsteps taken to reach the transition (>= 0),
    or None if the limit was reached or the move was aborted.

    Two consecutive matching reads are required to confirm the transition
    (simple noise filter).
    """
    _set_dir_cw(dir_cw)
    want        = Value.INACTIVE if expect_low else Value.ACTIVE
    steps       = 0
    consecutive = 0

    while steps <= limit:
        if callable(should_abort) and should_abort():
            return None
        if _debounced_read(OPTICAL_PIN) == want:
            consecutive += 1
            if consecutive >= 2:
                return steps
        else:
            consecutive = 0
        if not step_motor(1, delay=delay, should_abort=should_abort):
            return None
        steps += 1

    return None   # limit reached without finding transition


# Convenience wrappers ─────────────────────────────────────────────────────────

def _seek_cw_low(delay=SLOW_DELAY, limit=_FULL_SPAN, should_abort=None):
    """CW until optical goes LOW  (leading edge)."""
    return _seek_transition(True,  True,  delay, limit, should_abort)

def _seek_cw_high(delay=SLOW_DELAY, limit=_FULL_SPAN, should_abort=None):
    """CW until optical goes HIGH  (trailing edge)."""
    return _seek_transition(False, True,  delay, limit, should_abort)

def _seek_ccw_low(delay=SLOW_DELAY, limit=_FULL_SPAN, should_abort=None):
    """CCW until optical goes LOW  (trailing edge approached from CCW)."""
    return _seek_transition(True,  False, delay, limit, should_abort)

def _seek_ccw_high(delay=SLOW_DELAY, limit=_FULL_SPAN, should_abort=None):
    """CCW until optical goes HIGH  (past leading edge, CCW overshoot)."""
    return _seek_transition(False, False, delay, limit, should_abort)


# ─────────────────────────────────────────────────────────────────────────────
# Hall seeker
# ─────────────────────────────────────────────────────────────────────────────

def _seek_hall(timeout_s: float = 20.0, should_abort=None) -> bool:
    """
    Rotate CW quickly in batches of HALL_STEP_BATCH steps until the Hall sensor
    (SWITCH_PIN) goes LOW.

    Timeout is set to 20 s to allow a full carousel revolution at 1/32
    microstepping (worst case ~19 s when Hall is just behind current position).
    Returns True if Hall was found, False on timeout or abort.
    """
    t0 = time.time()
    _set_dir_cw(True)
    while _debounced_read(SWITCH_PIN) == Value.ACTIVE:
        if not step_motor(HALL_STEP_BATCH, delay=FAST_DELAY, should_abort=should_abort):
            return False
        if callable(should_abort) and should_abort():
            return False
        if time.time() - t0 > timeout_s:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Re-home helpers  (called between imaging cycles)
# ═══════════════════════════════════════════════════════════════════════════════

def rehome_quick_via_hall(status_callback=None, should_abort=None) -> bool:
    """
    Fast per-cycle re-sync using stored calibration:
      1. CW fast -> Hall
      2. CW slow -> stored Hall->Leading offset  (coarse)
      3. Dynamic bracket -> exact centre  (fine, re-measures W live)

    Falls back to full home() if calibration is absent or corrupt.

    NOTE: Stored calibration is only valid for the microstepping resolution and
    stripe width it was measured at.  Delete motion_cal.json when changing
    hardware.
    """
    _load_cal()
    W               = _cal.get("opt_window_width")
    hall_to_leading = _cal.get("hall_to_leading")

    if W is None or hall_to_leading is None:
        if status_callback:
            status_callback("Re-home: no calibration found — performing full homing...")
        return home(status_callback=status_callback, should_abort=should_abort) is not None

    if status_callback:
        status_callback("Re-home (quick): seeking Hall...")
    if not _seek_hall(timeout_s=20.0, should_abort=should_abort):
        if status_callback:
            status_callback("Re-home (quick): Hall not found — timeout.")
        return False

    if status_callback:
        status_callback(f"Re-home (quick): coarse move CW {hall_to_leading} µsteps to stripe vicinity...")
    if not step_motor(int(hall_to_leading), delay=SLOW_DELAY, should_abort=should_abort):
        return False

    if status_callback:
        status_callback("Re-home (quick): dynamic bracket to centre...")
    if not _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=should_abort):
        if status_callback:
            status_callback("Re-home (quick): bracket centering failed.")
        return False

    global current_plate
    current_plate = 1
    if status_callback:
        status_callback("Re-home (quick) complete: Plate #1 centred.")
    return True


def rehome_full_from_hall(status_callback=None, should_abort=None) -> bool:
    """
    Full per-cycle re-home: re-measures W each time (slower, more robust).
      1. CW fast -> Hall
      2. CW slow -> optical LOW (leading edge)  -> measure steps_to_leading
      3. CW slow -> optical HIGH (trailing edge) -> measure W
      4. Dynamic bracket -> exact centre
      5. Persist refreshed calibration

    Use this when W may drift between cycles (e.g. temperature effects on
    belt tension) or as a diagnostic.
    """
    if status_callback:
        status_callback("Re-home (full): seeking Hall...")
    if not _seek_hall(timeout_s=20.0, should_abort=should_abort):
        if status_callback:
            status_callback("Re-home (full): Hall not found — timeout.")
        return False

    # CW -> leading edge (LOW)
    steps_to_leading = _seek_cw_low(delay=SLOW_DELAY, limit=_HALL_LEAD,
                                    should_abort=should_abort)
    if steps_to_leading is None:
        if status_callback:
            status_callback("Re-home (full): optical LOW not found after Hall.")
        return False

    # CW -> trailing edge (HIGH) -> W
    W = _seek_cw_high(delay=SLOW_DELAY, limit=_W_SEEK_LIM * 2,
                      should_abort=should_abort)
    if W is None or W < W_MIN_VALID or W > W_MAX_VALID:
        _log(f"Re-home (full): W={W} outside [{W_MIN_VALID},{W_MAX_VALID}]; "
             f"using fallback W={W_FALLBACK}")
        W = W_FALLBACK
    C = W // 2

    if status_callback:
        status_callback(
            f"Re-home (full): W={W} µsteps; "
            f"leading={steps_to_leading} µsteps from Hall; "
            f"centre={steps_to_leading + C} µsteps from Hall"
        )

    # Dynamic bracket -> exact centre
    if not _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=should_abort):
        if status_callback:
            status_callback("Re-home (full): bracket centering failed.")
        return False

    # Persist refreshed calibration
    _cal["opt_window_width"]        = int(W)
    _cal["opt_center_from_leading"] = int(C)
    _cal["hall_to_leading"]         = int(steps_to_leading)
    _cal["hall_to_center"]          = int(steps_to_leading + C)
    _save_cal()

    global current_plate
    current_plate = 1
    if status_callback:
        status_callback("Re-home (full) complete: Plate #1 centred.")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Dynamic bracket centering  (core positioning algorithm)
# ═══════════════════════════════════════════════════════════════════════════════

def _center_with_dynamic_bracket(delay: float = SLOW_DELAY,
                                  should_abort=None) -> bool:
    """
    Centre the carousel on the stripe currently near the optical sensor.

    Each call measures the stripe width W INDEPENDENTLY from the CCW crossing,
    so adjacent stripes with slightly different widths do not contaminate each
    other's centering.

    Sequence
    --------
    0. If sensor is currently LOW (on stripe): CW -> HIGH  (escape the stripe)
    1. CCW -> LOW   (find trailing edge, approaching from CW direction)
    2. CCW -> HIGH  (cross past leading edge, counting steps = W_measured)
    3. CW  -> LOW   (re-validate leading edge with a clean CW approach)
    4. CW  + round(W_measured / 2 x (1 - CENTER_BACKOFF_FRAC))  -> midpoint

    The final move always arrives from the CW direction, eliminating backlash
    as a source of positioning error.

    Expected W for 5 mm stripe @ 1/32 µstepping ~= 192 steps.
    Returns True on success, False on any seek failure or out-of-range W.
    """
    max_span = steps_per_60_deg   # 3200 µsteps — full 60° inter-plate gap

    # -- Step 0: escape if we are already sitting on the stripe ----------------
    if _is_low(OPTICAL_PIN):
        _log("Bracket: sensor is LOW (on stripe) — CW -> HIGH to escape")
        if _seek_cw_high(delay=delay, limit=max_span,
                         should_abort=should_abort) is None:
            _log("Bracket: FAILED — could not escape stripe CW->HIGH")
            return False

    # -- Step 1: CCW -> LOW  (trailing edge) ------------------------------------
    _log("Bracket: CCW -> LOW  (trailing edge)")
    if _seek_ccw_low(delay=delay, limit=max_span,
                     should_abort=should_abort) is None:
        _log("Bracket: FAILED — CCW->LOW not found")
        return False

    # -- Step 2: CCW -> HIGH  (past leading edge; counts W) ---------------------
    _log("Bracket: CCW -> HIGH  (past leading edge — measuring W)")
    W_measured = _seek_ccw_high(delay=delay, limit=_W_SEEK_LIM,
                                should_abort=should_abort)
    if W_measured is None or W_measured < W_MIN_VALID or W_measured > W_MAX_VALID:
        _log(f"Bracket: FAILED — W_measured={W_measured} "
             f"outside valid range [{W_MIN_VALID},{W_MAX_VALID}]")
        return False

    # -- Step 3: CW -> LOW  (re-validate leading edge from CW direction) --------
    _log("Bracket: CW -> LOW  (re-validate leading edge)")
    if _seek_cw_low(delay=delay, limit=max_span,
                    should_abort=should_abort) is None:
        _log("Bracket: FAILED — CW->LOW re-validation failed")
        return False

    # -- Step 4: CW + mid  ->  geometric midpoint -------------------------------
    mid = max(1, int(round(W_measured / 2.0 * (1.0 - CENTER_BACKOFF_FRAC))))
    _log(f"Bracket: CW +{mid} µsteps to midpoint  "
         f"[W_measured={W_measured}, backoff_frac={CENTER_BACKOFF_FRAC}]")
    if not step_motor(mid, delay=delay, should_abort=should_abort):
        return False

    # Optional fine CW trim (keep FINE_CENTER_TRIM=0 to avoid double CW bias)
    if FINE_CENTER_TRIM > 0:
        _log(f"Bracket: fine CW trim +{FINE_CENTER_TRIM} µsteps")
        if not step_motor(int(FINE_CENTER_TRIM), delay=delay,
                          should_abort=should_abort):
            return False

    return True


def _recenter_plate1_dynamic(delay: float = SLOW_DELAY,
                              should_abort=None) -> bool:
    """
    Re-centre Plate 1 after a full carousel wrap.
    Identical algorithm to _center_with_dynamic_bracket; kept separate so
    Plate 1 wrap events are clearly identifiable in the log output.
    """
    max_span = steps_per_60_deg   # 3200 µsteps

    if _is_low(OPTICAL_PIN):
        _log("Re-centre P1: sensor LOW — CW -> HIGH to escape stripe")
        if _seek_cw_high(delay=delay, limit=max_span,
                         should_abort=should_abort) is None:
            _log("Re-centre P1: FAILED — CW->HIGH escape")
            return False

    _log("Re-centre P1: CCW -> LOW  (trailing edge)")
    if _seek_ccw_low(delay=delay, limit=max_span,
                     should_abort=should_abort) is None:
        _log("Re-centre P1: FAILED — CCW->LOW")
        return False

    _log("Re-centre P1: CCW -> HIGH  (past leading edge — measuring W)")
    W_measured = _seek_ccw_high(delay=delay, limit=_W_SEEK_LIM,
                                should_abort=should_abort)
    if W_measured is None or W_measured < W_MIN_VALID or W_measured > W_MAX_VALID:
        _log(f"Re-centre P1: FAILED — W_measured={W_measured} "
             f"outside [{W_MIN_VALID},{W_MAX_VALID}]")
        return False

    _log("Re-centre P1: CW -> LOW  (re-validate leading edge)")
    if _seek_cw_low(delay=delay, limit=max_span,
                    should_abort=should_abort) is None:
        _log("Re-centre P1: FAILED — CW->LOW re-validation")
        return False

    mid = max(1, int(round(W_measured / 2.0 * (1.0 - CENTER_BACKOFF_FRAC))))
    _log(f"Re-centre P1: CW +{mid} µsteps to midpoint  "
         f"[W_measured={W_measured}, backoff_frac={CENTER_BACKOFF_FRAC}]")
    if not step_motor(mid, delay=delay, should_abort=should_abort):
        return False

    if FINE_CENTER_TRIM > 0:
        _log(f"Re-centre P1: fine CW trim +{FINE_CENTER_TRIM} µsteps")
        if not step_motor(int(FINE_CENTER_TRIM), delay=delay,
                          should_abort=should_abort):
            return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def home(timeout: float = 60.0, status_callback=None, should_abort=None):
    """
    Full homing sequence — always run at experiment start.

      1. CW fast -> Hall sensor
      2. CW slow -> optical LOW  (Plate 1 leading edge)
      3. CW slow -> optical HIGH (trailing edge) -> initial W measurement
      4. Dynamic bracket -> exact centre
      5. Persist calibration to motion_cal.json

    Returns plate number (1) on success; None on failure or abort.

    Delete motion_cal.json before calling home() if microstepping
    resolution or stripe width has changed since the last run.
    """
    global current_plate
    _load_cal()

    if status_callback:
        status_callback("Starting homing sequence (1/32 µstep)...")
    _log("Homing started — 1/32 µstep, 5 mm stripe, dynamic bracket")

    # -- 1. Seek Hall ------------------------------------------------------------
    t0 = time.time()
    _set_dir_cw(True)
    while _debounced_read(SWITCH_PIN) == Value.ACTIVE:
        if not step_motor(HALL_STEP_BATCH, delay=FAST_DELAY,
                          should_abort=should_abort):
            if status_callback:
                status_callback("Homing aborted during Hall search.")
            _log("Abort during Hall search")
            return None
        if callable(should_abort) and should_abort():
            if status_callback:
                status_callback("Homing aborted by user.")
            _log("Abort flag during Hall search")
            return None
        if time.time() - t0 > timeout:
            if status_callback:
                status_callback("Homing timeout: Hall sensor not detected.")
            _log("Timeout — Hall not found")
            return None

    _log("Hall triggered — measuring optical window...")

    # -- 2. CW -> leading edge (LOW) ----------------------------------------------
    steps_to_leading = _seek_cw_low(delay=SLOW_DELAY, limit=_HALL_LEAD,
                                    should_abort=should_abort)
    if steps_to_leading is None:
        if status_callback:
            status_callback("Homing failed: optical LOW not found after Hall.")
        _log("Error: optical LOW not found after Hall trigger")
        return None
    _log(f"Leading edge (LOW) at {steps_to_leading} µsteps from Hall")

    # -- 3. CW -> trailing edge (HIGH) -> initial W -------------------------------
    W = _seek_cw_high(delay=SLOW_DELAY, limit=_W_SEEK_LIM * 2,
                      should_abort=should_abort)
    if W is None or W < W_MIN_VALID or W > W_MAX_VALID:
        _log(f"WARNING: initial W={W} outside [{W_MIN_VALID},{W_MAX_VALID}]; "
             f"using fallback W={W_FALLBACK}. "
             "Check stripe width, sensor gap, and sensor alignment.")
        W = W_FALLBACK
    C = W // 2
    _log(f"Initial window measurement: W={W} µsteps,  C={C} µsteps")

    # -- 4. Dynamic bracket -> exact centre ---------------------------------------
    if not _center_with_dynamic_bracket(delay=SLOW_DELAY,
                                        should_abort=should_abort):
        if status_callback:
            status_callback("Homing failed during dynamic bracket centering.")
        _log("Homing failed — dynamic bracket")
        return None

    # -- 5. Persist calibration ----------------------------------------------------
    _cal["opt_window_width"]        = int(W)
    _cal["opt_center_from_leading"] = int(C)
    _cal["hall_to_leading"]         = int(steps_to_leading)
    _cal["hall_to_center"]          = int(steps_to_leading + C)
    _save_cal()

    if status_callback:
        status_callback(
            f"Homing OK — W={W} µsteps  |  "
            f"Hall->leading={steps_to_leading} µsteps  |  "
            f"Hall->centre={steps_to_leading + C} µsteps"
        )

    current_plate = 1
    if status_callback:
        status_callback("Homing complete.  Plate #1 centred.")
    _log("Homing complete.  Plate #1 centred.")
    return current_plate


def advance(status_callback=None, should_abort=None) -> int:
    """
    Advance one plate position (steps_per_60_deg µsteps CW), then
    bracket-centre on the arriving stripe.

    Each plate independently measures its own W — no shared state between
    plates.  The final CW approach is always consistent, eliminating backlash.

    Returns the new current_plate number (1-6).
    """
    global current_plate

    _set_dir_cw(True)
    if not step_motor(steps_per_60_deg, delay=SLOW_DELAY,
                      should_abort=should_abort):
        if status_callback:
            status_callback("Advance aborted.")
        _log("Advance aborted during bulk move")
        return current_plate

    current_plate = (current_plate % 6) + 1
    if status_callback:
        status_callback(f"Moved to Plate #{current_plate}")
    _log(f"Bulk advance complete -> Plate #{current_plate}")

    if current_plate == 1:
        # Plate 1 wrap — use dedicated function for distinct log messages
        if status_callback:
            status_callback("Plate #1 wrap: dynamic bracket re-centre...")
        ok = _recenter_plate1_dynamic(delay=SLOW_DELAY, should_abort=should_abort)
        if ok:
            if status_callback:
                status_callback("Plate #1 re-centre complete.")
        else:
            if status_callback:
                status_callback("Plate #1 re-centre FAILED — edge not found.")
        _log(f"Plate #1 wrap re-centre: backoff={CENTER_BACKOFF_FRAC}, ok={ok}")
    else:
        if status_callback:
            status_callback(f"Plate #{current_plate}: dynamic bracket centering...")
        ok = _center_with_dynamic_bracket(delay=SLOW_DELAY,
                                          should_abort=should_abort)
        if ok:
            if status_callback:
                status_callback(f"Plate #{current_plate} centred.")
        else:
            if status_callback:
                status_callback(f"Plate #{current_plate}: centering FAILED.")
        _log(f"Plate #{current_plate} bracket centre: backoff={CENTER_BACKOFF_FRAC}, ok={ok}")

    return current_plate


def goto_plate(target_plate, status_callback=None) -> int:
    """
    Move to `target_plate` (1-6) by calling advance() repeatedly.
    Each intermediate position is bracket-centred before continuing.
    Returns the final current_plate.
    """
    global current_plate
    target_plate = int(target_plate)
    if not (1 <= target_plate <= 6):
        if status_callback:
            status_callback(f"goto_plate: invalid target {target_plate} (must be 1-6)")
        return current_plate
    if status_callback:
        status_callback(f"goto_plate: {current_plate} -> {target_plate}")
    steps_remaining = 6
    while current_plate != target_plate and steps_remaining > 0:
        advance(status_callback=status_callback)
        steps_remaining -= 1
    return current_plate


def get_current_plate() -> int:
    """Return the current plate number (0 = not homed)."""
    return current_plate


def get_calibration() -> dict:
    """Return the last persisted calibration dict (W, hall->leading, hall->centre)."""
    _load_cal()
    return dict(_cal)
