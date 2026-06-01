# motor_control.py — dynamic bracket midpoint centering, all 6 plates (6-optical sensor trigger strategy)
# Flow:
#   1) Seek hall (pre-index)
#   2) Measure optical window once (CW: LOW -> HIGH) => W
#   3) Dynamic bracket (robust to backlash):
#        CCW -> LOW, CCW -> HIGH (past leading), CW -> LOW (re-validate leading),
#        CW + round(W/2 * (1 - CENTER_BACKOFF_FRAC)) to land at geometric midpoint
#   4) Persist W, hall->leading, hall->center; display values
#   5) On each advance (plates 2-6): bracket-center on arriving plate's optical stripe
#   6) On wrap to Plate 1: re-center with Hall-assisted dynamic bracket + backoff
#
# Hardware: 1 fixed ITR20001 sensor (OPTICAL_PIN=19) on machine frame;
#           6 reflective stripes (2.5 mm, nail polish) on carousel — one per plate face.
#           1 Hall sensor (SWITCH_PIN=26) between plate positions 4 and 5 (pre-index).
#
# Public API preserved:
#   driver_enable(), driver_disable(), step_motor(), home(), advance(),
#   goto_plate(), get_current_plate(), get_calibration()
 
import time
import json
from pathlib import Path
import gpiod
from gpiod.line import Direction, Value, Bias
 
# ---------------- GPIO pins ----------------
CHIP = "/dev/gpiochip0"
EN_PIN = 21
STEP_PIN = 20
DIR_PIN = 16
SWITCH_PIN = 26   # Hall sensor (active LOW)
OPTICAL_PIN = 19  # Optical sensor (active LOW)
 
# ---------------- motion / timing ----------------
steps_per_60_deg = 800
SLOW_DELAY = 0.0025
FAST_DELAY  = 0.0010
 
# ---------------- options ----------------
DIR_INVERT = True        # set to false for gear drive/True for belt drive
DEBUG_VERBOSE = True
 
# Dynamic centering: the carousel lands at W//2 * (1 - CENTER_BACKOFF_FRAC) µsteps from the
# re-validated leading edge.  0.0 = geometric centre of the optical window (recommended).
# Increase slightly (e.g. 0.1) only if you want a small CCW-of-centre margin.
# This replaces the old fixed CENTER_BACKOFF = 5 which was tuned for W≈20 and broke for W≈12.
CENTER_BACKOFF_FRAC = 0.0
 
# Keep trim at 0 so we do NOT re-add CW after backoff (avoid double-application).
FINE_CENTER_TRIM = 0      # leave 0 unless you intentionally want an extra CW nudge
 
# ---------------- persistence ----------------
CAL_PATH = Path("motion_cal.json")
_cal = {
    "opt_window_width": None,        # W (µsteps)
    "opt_center_from_leading": None, # C = W//2 (raw geometric midpoint)
    "hall_to_leading": None,         # µsteps hall -> first LOW
    "hall_to_center": None           # µsteps hall -> C (raw midpoint)
}
 
current_plate = 0  # 0 = unknown/not homed
 
# ---------------- gpiod request ----------------
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
 
# ================================================================
# Utils
# ================================================================
def _log(msg: str):
    if DEBUG_VERBOSE:
        print(f"[motor] {msg}", flush=True)
 
def _set_dir_cw(is_cw: bool = True):
    logical = is_cw if not DIR_INVERT else (not is_cw)
    request.set_value(DIR_PIN, Value.ACTIVE if logical else Value.INACTIVE)
 
def _debounced_read(pin, samples=5, dt=0.0004):
    ones = 0
    for _ in range(samples):
        if request.get_value(pin) == Value.ACTIVE:
            ones += 1
        time.sleep(dt)
    return Value.ACTIVE if ones >= (samples - ones) else Value.INACTIVE
 
def _is_low(pin):
    return _debounced_read(pin) == Value.INACTIVE  # active-LOW
 
def driver_enable():
    request.set_value(EN_PIN, Value.INACTIVE)
 
def driver_disable():
    request.set_value(EN_PIN, Value.ACTIVE)
 
def step_motor(steps, delay=SLOW_DELAY, should_abort=None):
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
 
# ================================================================
# Edge seekers (CW and CCW)
# ================================================================
def _seek_transition(expect_low: bool, dir_cw: bool, delay=SLOW_DELAY, limit=2000, should_abort=None):
    """
    Seek optical transition in a chosen direction:
      expect_low=True  -> seek LOW  (leading)
      expect_low=False -> seek HIGH (trailing)
    Returns µsteps moved to hit the target state, or None on limit/abort.
    """
    _set_dir_cw(dir_cw)
    want = Value.INACTIVE if expect_low else Value.ACTIVE
    steps = 0
    consecutive = 0
    while steps <= limit:
        if callable(should_abort) and should_abort():
            return None
        state = _debounced_read(OPTICAL_PIN)
        if state == want:
            consecutive += 1
            if consecutive >= 2:
                return steps
        else:
            consecutive = 0
        if not step_motor(1, delay=delay, should_abort=should_abort):
            return None
        steps += 1
    return None
 
def _seek_cw_low(delay=SLOW_DELAY, limit=2000, should_abort=None):   return _seek_transition(True,  True,  delay, limit, should_abort)
def _seek_cw_high(delay=SLOW_DELAY, limit=2000, should_abort=None):  return _seek_transition(False, True,  delay, limit, should_abort)
def _seek_ccw_low(delay=SLOW_DELAY, limit=2000, should_abort=None):  return _seek_transition(True,  False, delay, limit, should_abort)
def _seek_ccw_high(delay=SLOW_DELAY, limit=2000, should_abort=None): return _seek_transition(False, False, delay, limit, should_abort)
 
# ---------- Hall seeker (fast) ----------
def _seek_hall(timeout_s=5.0, should_abort=None):
    """Rotate CW quickly until Hall (SWITCH_PIN) goes LOW. Return True if found."""
    t0 = time.time()
    _set_dir_cw(True)
    while _debounced_read(SWITCH_PIN) == Value.ACTIVE:
        if not step_motor(10, delay=FAST_DELAY, should_abort=should_abort):
            return False
        if callable(should_abort) and should_abort():
            return False
        if time.time() - t0 > timeout_s:
            return False
    return True
 
# ---------- Quick re-sync via Hall using stored calibration ----------
def rehome_quick_via_hall(status_callback=None, should_abort=None):
    """
    Fast re-sync at end of each 360° cycle:
      - CW fast to Hall
      - CW to saved Hall->Leading (coarse)
      - Dynamic bracket + round(W/2 * (1 - CENTER_BACKOFF_FRAC)) to lock exact center (fine)
    Uses stored W and Hall->Leading; falls back to full home if missing.
    """
    _load_cal()
    W = _cal.get("opt_window_width")
    hall_to_leading = _cal.get("hall_to_leading")
 
    if W is None or hall_to_leading is None:
        # no calibration => do a normal home()
        if status_callback: status_callback("Re-home: no calibration; performing full homing...")
        return home(status_callback=status_callback, should_abort=should_abort) is not None
 
    if status_callback: status_callback("Re-home: seeking Hall (fast)...")
    if not _seek_hall(timeout_s=6.0, should_abort=should_abort):
        if status_callback: status_callback("Re-home: Hall not found (timeout).")
        return False
 
    # Coarse move from Hall to the neighborhood of the window
    if status_callback: status_callback(f"Re-home: stepping CW {hall_to_leading} µsteps to leading vicinity...")
    if not step_motor(int(hall_to_leading), delay=SLOW_DELAY, should_abort=should_abort):
        return False
 
    # Now apply the same dynamic bracket you use in 'home' to re-validate leading and center
    if status_callback: status_callback("Re-home: dynamic bracket to center...")
    ok = _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=should_abort)
    if not ok:
        if status_callback: status_callback("Re-home: bracket centering failed.")
        return False
 
    # Done
    global current_plate
    current_plate = 1
    if status_callback: status_callback("Re-home complete: Plate #1 centered (quick).")
    return True
 
# ---------- Full re-home starting from Hall ----------
def rehome_full_from_hall(status_callback=None, should_abort=None):
    """
    Slower but fully recalibrates W each cycle:
      - CW fast to Hall
      - Then re-run the same (LOW->HIGH) window measurement & dynamic bracket as 'home'
    """
    if status_callback: status_callback("Re-home (full): seeking Hall (fast)...")
    if not _seek_hall(timeout_s=6.0, should_abort=should_abort):
        if status_callback: status_callback("Re-home (full): Hall not found (timeout).")
        return False
 
    # From here, replicate the middle of 'home()' starting right after "Hall triggered"
    # 2) CW to leading (LOW)
    steps_to_leading = _seek_cw_low(delay=SLOW_DELAY, limit=1600, should_abort=should_abort)
    if steps_to_leading is None:
        if status_callback: status_callback("Re-home (full): optical LOW not found.")
        return False
 
    # 3) CW to trailing (HIGH) -> W
    W = _seek_cw_high(delay=SLOW_DELAY, limit=400, should_abort=should_abort)
    if W is None or W < 2 or W > 100:
        W = 10
    C = W // 2
 
    if status_callback: status_callback(f"Re-home (full): W={W} µsteps; leading={steps_to_leading}; center={steps_to_leading + C}")
 
    # 4) Dynamic bracket to midpoint with backoff
    ok = _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=should_abort)
    if not ok:
        if status_callback: status_callback("Re-home (full): bracket centering failed.")
        return False
 
    # 5) Persist the refreshed calibration
    _cal["opt_window_width"] = int(W)
    _cal["opt_center_from_leading"] = int(C)
    _cal["hall_to_leading"] = int(steps_to_leading)
    _cal["hall_to_center"]  = int(steps_to_leading + C)
    _save_cal()
 
    global current_plate
    current_plate = 1
    if status_callback: status_callback("Re-home (full) complete: Plate #1 centered.")
    return True
 
# ================================================================
# Dynamic bracket with midpoint backoff
# ================================================================
def _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=None):
    """
    Measures W dynamically during the bracket sequence — no external W parameter.
    Each call independently measures its own stripe width from the CCW crossing,
    eliminating cross-plate W contamination when adjacent stripes differ in width.

    Sequence:
      - If currently LOW, CW -> HIGH to start from HIGH side
      - CCW -> LOW  (trailing edge)
      - CCW -> HIGH (past leading) — step count here = this stripe's W
      - CW  -> LOW  (re-validate leading with CW approach)
      - CW  + round(W_measured/2 * (1 - CENTER_BACKOFF_FRAC)) to land at midpoint
    Returns True on success, False on failure.
    """
    max_span = max(steps_per_60_deg, 300)

    # Ensure starting on HIGH
    if _is_low(OPTICAL_PIN):
        _log("Bracket: we are LOW; CW -> HIGH first")
        if _seek_cw_high(delay=delay, limit=max_span, should_abort=should_abort) is None:
            _log("Bracket: failed CW->HIGH")
            return False

    _log("Bracket: CCW -> LOW")
    if _seek_ccw_low(delay=delay, limit=max_span, should_abort=should_abort) is None:
        _log("Bracket: failed CCW->LOW")
        return False

    _log("Bracket: CCW -> HIGH (past leading) — measuring W")
    W_measured = _seek_ccw_high(delay=delay, limit=200, should_abort=should_abort)
    if W_measured is None or W_measured < 2 or W_measured > 100:
        _log(f"Bracket: failed CCW->HIGH or invalid W={W_measured}")
        return False

    _log("Bracket: CW -> LOW (re-validate leading)")
    if _seek_cw_low(delay=delay, limit=max_span, should_abort=should_abort) is None:
        _log("Bracket: failed CW->LOW re-validation")
        return False

    # Midpoint using this stripe's own measured W
    mid = max(1, int(round(W_measured / 2.0 * (1.0 - CENTER_BACKOFF_FRAC))))
    _log(f"Bracket: CW +{mid} µsteps to midpoint (frac={CENTER_BACKOFF_FRAC}, W_measured={W_measured})")
    if not step_motor(mid, delay=delay, should_abort=should_abort):
        return False

    # Optional CW trim (keep 0 to avoid double-adding CW after backoff)
    if FINE_CENTER_TRIM > 0:
        _log(f"Bracket: fine CW trim +{FINE_CENTER_TRIM} µsteps")
        if not step_motor(int(FINE_CENTER_TRIM), delay=delay, should_abort=should_abort):
            return False

    return True
 
def _recenter_plate1_dynamic(delay=SLOW_DELAY, should_abort=None):
    """
    Re-center Plate 1 measuring W dynamically from this stripe — no external W parameter.
    Identical logic to _center_with_dynamic_bracket but kept separate so callers can
    distinguish plate-1 wrap re-centers from mid-run bracket centers in the log.
    """
    max_span = max(steps_per_60_deg, 300)

    if _is_low(OPTICAL_PIN):
        _log("Re-center: we are LOW; CW -> HIGH first")
        if _seek_cw_high(delay=delay, limit=max_span, should_abort=should_abort) is None:
            _log("Re-center: failed CW->HIGH")
            return False

    _log("Re-center: CCW -> LOW")
    if _seek_ccw_low(delay=delay, limit=max_span, should_abort=should_abort) is None:
        _log("Re-center: failed CCW->LOW")
        return False

    _log("Re-center: CCW -> HIGH (past leading) — measuring W")
    W_measured = _seek_ccw_high(delay=delay, limit=200, should_abort=should_abort)
    if W_measured is None or W_measured < 2 or W_measured > 100:
        _log(f"Re-center: failed CCW->HIGH or invalid W={W_measured}")
        return False

    _log("Re-center: CW -> LOW (re-validate leading)")
    if _seek_cw_low(delay=delay, limit=max_span, should_abort=should_abort) is None:
        _log("Re-center: failed CW->LOW re-validation")
        return False

    mid = max(1, int(round(W_measured / 2.0 * (1.0 - CENTER_BACKOFF_FRAC))))
    _log(f"Re-center: CW +{mid} µsteps to midpoint (frac={CENTER_BACKOFF_FRAC}, W_measured={W_measured})")
    if not step_motor(mid, delay=delay, should_abort=should_abort):
        return False

    if FINE_CENTER_TRIM > 0:
        _log(f"Re-center: fine CW trim +{FINE_CENTER_TRIM} µsteps")
        if not step_motor(int(FINE_CENTER_TRIM), delay=delay, should_abort=should_abort):
            return False

    return True
 
# ================================================================
# Public API
# ================================================================
def home(timeout=60, status_callback=None, should_abort=None):
    """
    Homing (dynamic bracket + backoff):
      1) Seek hall (pre-index)
      2) CW to LOW (leading)
      3) CW to HIGH (trailing) -> W
      4) Dynamic bracket to re-validate leading and land at round(W/2 * (1 - CENTER_BACKOFF_FRAC))
      5) Persist W, hall->leading, hall->center; report values
    Returns 1 on success; None on failure/abort.
    """
    global current_plate
    _load_cal()
 
    if status_callback: status_callback("Starting homing...")
    _log("Homing started (dynamic bracket + backoff)")
 
    # 1) Seek hall
    t0 = time.time()
    _set_dir_cw(True)
    while _debounced_read(SWITCH_PIN) == Value.ACTIVE:
        if not step_motor(10, delay=FAST_DELAY, should_abort=should_abort):
            if status_callback: status_callback("Homing aborted by user.")
            _log("Abort during hall search")
            return None
        if time.time() - t0 > timeout:
            if status_callback: status_callback("Homing timeout: hall not detected.")
            _log("Timeout seeking hall")
            return None
        if callable(should_abort) and should_abort():
            if status_callback: status_callback("Homing aborted by user.")
            _log("Abort flag during hall search")
            return None
 
    _log("Hall triggered. Measuring optical window...")
 
    # 2) CW to leading (LOW)
    steps_to_leading = _seek_cw_low(delay=SLOW_DELAY, limit=1600, should_abort=should_abort)
    if steps_to_leading is None:
        if status_callback: status_callback("Homing failed: optical LOW not found.")
        _log("Error: optical LOW not found")
        return None
    _log(f"Leading (LOW) at {steps_to_leading} µsteps from hall")
 
    # 3) CW to trailing (HIGH) -> W
    W = _seek_cw_high(delay=SLOW_DELAY, limit=400, should_abort=should_abort)
    if W is None or W < 2 or W > 100:
        _log(f"WARNING: measured W={W} invalid; fallback W=10")
        W = 10
    C = W // 2
    _log(f"Window width W={W}, center offset C={C}")
 
    # 4) Dynamic bracket to midpoint with backoff (W measured internally)
    if not _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=should_abort):
        if status_callback: status_callback("Homing failed during bracket centering.")
        _log("Homing failed during dynamic bracket")
        return None
 
    # 5) Persist & report
    _cal["opt_window_width"] = int(W)
    _cal["opt_center_from_leading"] = int(C)
    _cal["hall_to_leading"] = int(steps_to_leading)
    _cal["hall_to_center"]  = int(steps_to_leading + C)
    _save_cal()
 
    if status_callback:
        status_callback(
            f"Optical window W={W} µsteps; leading={steps_to_leading} µsteps after hall; "
            f"center={steps_to_leading + C} µsteps after hall"
        )
 
    current_plate = 1
    if status_callback:
        status_callback("Homing complete. Plate #1 centered.")
    _log("Homing complete. Plate #1 centered.")
    return current_plate
 
def advance(status_callback=None, should_abort=None):
    """
    Advance one plate (800 µsteps CW), then bracket-center on the arriving stripe.
    Each plate measures its own W independently during the bracket — no shared W state.

    - Plates 2-6: _center_with_dynamic_bracket() measures this stripe's W on the fly.
    - Plate 1 wrap: _recenter_plate1_dynamic() does the same with Hall-guard logging.
    """
    global current_plate
    _set_dir_cw(True)
    if not step_motor(steps_per_60_deg, delay=SLOW_DELAY, should_abort=should_abort):
        if status_callback: status_callback("Advance aborted.")
        _log("Advance aborted")
        return current_plate

    current_plate = (current_plate % 6) + 1
    if status_callback: status_callback(f"Moved to Plate #{current_plate}")
    _log(f"Moved to Plate #{current_plate}")

    if current_plate == 1:
        if status_callback:
            status_callback("Plate #1 wrap: re-centering (Hall + dynamic bracket)...")
        ok = _recenter_plate1_dynamic(delay=SLOW_DELAY, should_abort=should_abort)
        if ok:
            if status_callback:
                status_callback("Re-center complete: Plate #1 aligned.")
        else:
            if status_callback:
                status_callback("Re-center failed: Plate #1 edge not found within span.")
        _log(f"Plate #1 re-center: frac={CENTER_BACKOFF_FRAC}, ok={ok}")
    else:
        if status_callback:
            status_callback(f"Plate #{current_plate}: centering (dynamic bracket)...")
        ok = _center_with_dynamic_bracket(delay=SLOW_DELAY, should_abort=should_abort)
        if ok:
            if status_callback:
                status_callback(f"Plate #{current_plate} centered.")
        else:
            if status_callback:
                status_callback(f"Plate #{current_plate}: centering failed.")
        _log(f"Plate #{current_plate} bracket center: frac={CENTER_BACKOFF_FRAC}, ok={ok}")

    return current_plate
 
def goto_plate(target_plate, status_callback=None):
    """Move to target plate (1..6) with repeated advance()."""
    global current_plate
    target_plate = int(target_plate)
    if target_plate < 1 or target_plate > 6:
        if status_callback:
            status_callback(f"goto_plate: invalid target {target_plate}")
        return current_plate
    if status_callback:
        status_callback(f"Moving to Plate #{target_plate} from #{current_plate}")
    max_steps = 6
    while current_plate != target_plate and max_steps > 0:
        advance(status_callback=status_callback)
        max_steps -= 1
    return current_plate
 
def get_current_plate():
    return current_plate
 
def get_calibration():
    """Return last measured calibration dict (W, hall->leading, hall->center)."""
    _load_cal()
    return dict(_cal)