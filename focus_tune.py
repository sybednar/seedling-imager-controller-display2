#!/usr/bin/env python3
"""
focus_tune.py — quantitative live focus assistant for the Arducam AR2020
mono USB3 camera (stock lens or ACHF080402320MP M12 lens).

By-eye focus is inherently subjective. This script gives you a repeatable,
numeric sharpness score computed from the live image, plus (when run from a
terminal on the Pi's own desktop) an actual live preview window — so you can
first get visually close to focus by watching the Siemens star sharpen up on
screen, then fine-tune to the true maximum using the printed number.

METHOD: "variance of the Laplacian" — a standard, widely-used focus metric.
The Laplacian highlights edges/detail in the image; a blurry image has weak,
smeared edges (low variance), a sharp image has strong, well-defined edges
(high variance). The number has no absolute meaning by itself — it's only
useful as a RELATIVE score to maximize on the SAME scene while you turn the
focus ring. Comparing scores between different scenes/lighting is not
meaningful.

HOW TO USE (see MODES below for which command/illumination to use):
  1. Place the Siemens star (or anything with fine, high-contrast detail —
     printed text, a ruler, seed/tray markings) at your real working
     distance, under whichever illumination matches the mode you're running.
     A blank/uniform surface gives a near-zero, uninformative score
     regardless of focus.
  2. Run this script (see command below). A live preview window opens
     (title "Siemens Star Focus") showing the camera feed with the scored
     region boxed in red and the current/peak sharpness overlaid — watch
     this window and turn the focus ring slowly, using the image itself to
     get roughly close to sharp first.
  3. Once it looks close by eye, switch to watching the printed score in the
     terminal (or the on-image overlay) to nail the true peak: the score
     will rise, peak, and then fall as you sweep through best focus.
     Overshoot past the peak on purpose, then sweep back — the "peak so
     far" value tracks the best you've seen. Bracket it in smaller and
     smaller steps until you're confident you're at the true maximum, not a
     local wobble.
  4. Once you've found the peak, tighten the lock ring (or set screw, on the
     Arducam stock lens) at that exact position. Grip ONLY the lock
     ring/collar while tightening — if the lens itself rotates even
     slightly while you tighten, you'll lose the focus point you just
     found. Recheck the score after tightening in case it shifted, and
     readjust if needed.
  5. Press 'q' or Esc in the preview window, or Ctrl+C in the terminal, to
     stop.

RUN IT (same pattern as camera_arducam_usb3.print_diagnostics()):

    cd ~/Seedling_Imager/seedling_imager_controller
    source venv/bin/activate
    python3 focus_tune.py                 # default: Rear IR (940nm), manual exposure
    python3 focus_tune.py front_visible    # ordinary room light recommended, manual exposure
    python3 focus_tune.py white_front      # front panel White LED strip (GPIO23), manual exposure

NOTE: Fully close the main seedling imager GUI application before running
this (not just "stop Live View" — the GUI holds the GPIO/LED lines and the
camera device open for its entire lifetime, so both need to be free).

NOTE on the live preview window: it needs a real display to draw to, so run
this from a terminal opened on the Pi's own touchscreen/desktop session —
not a plain SSH session with no X forwarding. If no display is available,
the script detects this, prints a warning, and falls back automatically to
writing focus_debug_snapshot.jpg once a second (the original behavior) —
everything else (scoring, LED control) still works the same either way.

MODES:
  rear_ir (default) — drives GPIO27 (Rear IR 940nm panel, same pin gui.py
      uses) and forces the same manual exposure/gain used for real imaging,
      via apply_ir_transmission_preset(). This matches real imaging
      conditions but ONLY makes sense with that illumination — the manual
      exposure/gain values are tuned for that panel's brightness and will
      be wrong (usually far too dark) under any other light source.
  front_visible — for testing with the lens's IR bandpass filter removed
      under ordinary front lighting (to isolate whether a printed target's
      poor contrast is IR-specific). Drives GPIO24 (gui.py's LED_GREEN_PIN)
      as a convenience, but that LED is a deliberately dim service light —
      ordinary room/desk light is a better illuminant for this test. This
      camera's driver rejects true auto-exposure outright, so this mode
      forces manual exposure/gain via the FRONT_VISIBLE_EXPOSURE_US /
      FRONT_VISIBLE_GAIN constants below (edit them if the startup frame
      check shows the image is too dark or too bright).
  white_front — drives GPIO23 (the front panel's White LED strip, same pin
      camera_config.py's "White LED Front" button uses) — a bright, even
      illuminant purpose-built for lighting a Siemens star target during
      manual focus calibration of either camera backend. This is the mode
      to use for the current Arducam stock-lens focus work at ~9.5-10cm
      working distance. Forces manual exposure/gain via the
      WHITE_FRONT_EXPOSURE_US / WHITE_FRONT_GAIN constants below (edit them
      if the startup frame check shows the image is too dark or too
      bright — the white LED is much brighter than front_visible's green
      service light, so these default to a shorter exposure/lower gain).
"""
import sys
import time
import numpy as np
import cv2
import camera_arducam_usb3 as cam

MODE = sys.argv[1] if len(sys.argv) > 1 else "rear_ir"
if MODE not in ("rear_ir", "front_visible", "white_front"):
    print(f"Unknown mode '{MODE}' — use 'rear_ir', 'front_visible', or 'white_front'.")
    sys.exit(1)

# GPIO pins/chip match gui.py's LED_REAR_IR_PIN (27) / LED_GREEN_PIN (24),
# and camera_config.py's WHITE_LED_FRONT_PIN (23) exactly — focus_tune.py is
# standalone, so it must drive the LED itself; nothing else will turn it on.
LED_PIN = {"rear_ir": 27, "front_visible": 24, "white_front": 23}[MODE]
_gpio_chip = "/dev/gpiochip0"
_led_request = None
try:
    import gpiod
    from gpiod.line import Value, Direction
except Exception as e:
    gpiod = None
    print(f"[focus_tune] gpiod import failed ({e}) — LED will NOT be turned "
          f"on; sharpness will read ~0.0 the whole time.", flush=True)


def led_on(on: bool):
    global _led_request
    if gpiod is None:
        return
    if _led_request is None:
        _led_request = gpiod.request_lines(
            _gpio_chip,
            consumer="focus_tune",
            config={LED_PIN: gpiod.LineSettings(
                direction=Direction.OUTPUT, output_value=Value.INACTIVE)},
        )
    _led_request.set_value(LED_PIN, Value.ACTIVE if on else Value.INACTIVE)


# Starting manual exposure/gain for front_visible mode. This camera's
# driver rejects auto_exposure=3 ("aperture priority" / full auto) outright
# — v4l2-ctl returns a hard error, not a soft fallback — so we can't rely on
# AE at all here and must pick manual values instead. These are just a
# starting guess for ordinary room/desk lighting; EDIT THEM if the startup
# frame check below still shows a very dark (or blown-out) frame.
FRONT_VISIBLE_EXPOSURE_US = 30000
FRONT_VISIBLE_GAIN = 300  # Arducam scale, 100-2200

# Starting manual exposure/gain for white_front mode. The front panel White
# LED strip is a much brighter, more direct illuminant than front_visible's
# green service LED, so it needs a shorter exposure / lower gain starting
# point rather than reusing FRONT_VISIBLE_EXPOSURE_US/GAIN above. EDIT THESE
# if the startup frame check below shows the image is too dark (raise
# exposure/gain) or blown out / all-white (lower them).
WHITE_FRONT_EXPOSURE_US = 8000
WHITE_FRONT_GAIN = 150  # Arducam scale, 100-2200

WINDOW_NAME = "Siemens Star Focus"


def sharpness_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian, computed directly on the raw grayscale
    ROI — higher means sharper. Exposure and gain are locked to fixed
    manual values before the sweep starts (apply_ir_transmission_preset()
    for rear_ir, or the forced manual exposure/gain for front_visible /
    white_front), so frame-to-frame brightness is already consistent under
    fixed illumination. No per-frame renormalization is needed to remove a
    brightness confound here, and — critically — doing one anyway actively
    breaks this metric under defocus.

    A previous version of this function stretched each frame's own
    min/max pixel range to a fixed 0-1 span before scoring, intending to
    stop a brighter/higher-contrast frame from outscoring a genuinely
    sharper one. But a Siemens star's black/white spokes blur together
    toward flat mid-gray as focus is lost, so the frame's true (max-min)
    range SHRINKS the further out of focus you go. Rescaling that shrunken
    range back up to a fixed span amplifies whatever is left in it — by
    that point mostly sensor read noise, not real edge detail — so the
    reported "sharpness" could climb even as the lens moved further from
    correct focus. That is the "score keeps increasing past 200 while the
    image is visibly more blurred" failure. Scoring the raw grayscale
    directly (no rescaling) removes that noise-amplification path; with
    exposure/gain already fixed, relative comparisons across the sweep
    remain valid.
    """
    lap = cv2.Laplacian(gray.astype(np.float64), cv2.CV_64F)
    return float(lap.var())


def main():
    # Open at FULL resolution rather than the downsampled preview stream.
    # Fine focus differences get smoothed away at preview (1280x960)
    # resolution, so the score is far more sensitive to small ring
    # adjustments when measured at the full 5120x3840 capture size.
    settings = cam.load_settings()
    fw = int(settings.get("Arducam_FullWidth", 5120))
    fh = int(settings.get("Arducam_FullHeight", 3840))
    cam._open_capture(fw, fh)

    if MODE == "rear_ir":
        # Lock exposure/gain to your saved Rear IR values so brightness
        # changes don't masquerade as focus changes while turning the ring.
        # Only valid under the actual Rear IR panel's brightness.
        live = cam.apply_ir_transmission_preset(None)
        cam.apply_settings(live)
    elif MODE == "front_visible":
        # front_visible: this camera's driver rejects true auto-exposure
        # (auto_exposure=3 fails outright — confirmed on real hardware), so
        # force manual mode (value=1, known to work) with a starting
        # exposure/gain for ordinary lighting instead of the Rear-IR-tuned
        # values, which are wrong for this much dimmer light source.
        cam._set_auto_exposure(False)
        cam._v4l2_set("exposure", cam._us_to_v4l2_exposure(FRONT_VISIBLE_EXPOSURE_US))
        cam._v4l2_set("gain", FRONT_VISIBLE_GAIN)
        print(f"Manual exposure/gain forced for front_visible mode: "
              f"{FRONT_VISIBLE_EXPOSURE_US}us / gain {FRONT_VISIBLE_GAIN} "
              f"— edit the FRONT_VISIBLE_EXPOSURE_US / FRONT_VISIBLE_GAIN "
              f"constants near the top of this script if the frame below "
              f"is still too dark or too bright.")
        print("NOTE: the green LED (GPIO24) is a deliberately dim service "
              "light, not a photographic illuminant — for this test, "
              "ordinary room/desk light is likely a better light source.")
    else:  # white_front
        # Same reasoning as front_visible: this camera has no usable
        # auto-exposure, so force manual mode with a starting point tuned
        # for the much brighter white LED strip.
        cam._set_auto_exposure(False)
        cam._v4l2_set("exposure", cam._us_to_v4l2_exposure(WHITE_FRONT_EXPOSURE_US))
        cam._v4l2_set("gain", WHITE_FRONT_GAIN)
        print(f"Manual exposure/gain forced for white_front mode: "
              f"{WHITE_FRONT_EXPOSURE_US}us / gain {WHITE_FRONT_GAIN} "
              f"— edit the WHITE_FRONT_EXPOSURE_US / WHITE_FRONT_GAIN "
              f"constants near the top of this script if the frame below "
              f"is still too dark or too bright.")

    # Turn the illumination ON — see led_on() above.
    led_on(True)
    time.sleep(0.3)

    # Sanity-check that we're actually getting a non-black frame before
    # relying on the sharpness score at all. A flat/near-zero mean here
    # means the LED isn't lit, the target isn't in the frame, or exposure
    # is too low — sharpness will read ~0.0 regardless of focus until this
    # is fixed, so check it first rather than sweeping the lens blind.
    frame = cam._read_raw_frame()
    if frame is not None:
        gray0 = cam._to_gray(frame)
        print(f"Startup frame check — mean: {gray0.mean():.1f}  "
              f"min: {gray0.min()}  max: {gray0.max()}  (8-bit, 0-255)")
        if gray0.max() < 10:
            print("WARNING: frame looks essentially all-black. Check that "
                  "the LED for this mode is actually lit, the target is in "
                  "frame, and exposure/gain aren't set too low.\n")
    else:
        print("WARNING: could not read a startup frame at all.\n")

    # Try to open a live preview window. This needs a real display — it
    # will fail (harmlessly) over a plain SSH session with no X forwarding,
    # in which case we fall back to the original once-a-second
    # focus_debug_snapshot.jpg behavior so the script still works headless.
    live_window = False
    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 900, 675)
        live_window = True
        print(f"Live preview window opened ('{WINDOW_NAME}') — watch it "
              f"while turning the focus ring. Click the window and press "
              f"'q' or Esc to stop (or Ctrl+C in this terminal).\n")
    except Exception as e:
        print(f"[focus_tune] Could not open a live preview window ({e}) — "
              f"falling back to focus_debug_snapshot.jpg only. Run this "
              f"from a terminal on the Pi's own desktop (not plain SSH) to "
              f"get the live window.\n")

    print(f"Streaming at {fw}x{fh}. Point the camera at the Siemens star "
          f"target at your real working distance, then turn the focus ring "
          f"slowly. Ctrl+C to stop.\n")
    if not live_window:
        print("Writing focus_debug_snapshot.jpg once a second — the full "
              "frame, downsized, with a box around the region actually "
              "being scored. Pull it off the Pi (or open it in a file "
              "manager) to confirm the target is really inside that box "
              "before trusting the numbers below — a low, noisy score "
              "usually means it isn't.\n")

    best = 0.0
    best_time = time.time()
    last_snapshot = 0.0
    try:
        while True:
            frame = cam._read_raw_frame()
            if frame is None:
                print("no frame — retrying...                              ",
                      end="\r", flush=True)
                time.sleep(0.2)
                continue
            gray = cam._to_gray(frame)
            # Center crop — deliberately large (70% of the frame) rather
            # than a tight crop on the star's exact center. A Siemens
            # star's spokes get infinitely thin approaching the center, so
            # there's always a small soft "convergence blur" right at the
            # middle even at perfect focus — that's geometry, not defocus.
            # A tight crop centered on that point was mostly measuring that
            # one always-soft spot rather than the genuinely sharp spokes
            # around it, which is why scores stayed small no matter what
            # changed. This wider crop captures far more of the crisp outer
            # detail, which now dominates the score instead.
            h, w = gray.shape[:2]
            y0, y1 = int(h * 0.15), int(h * 0.85)
            x0, x1 = int(w * 0.15), int(w * 0.85)
            roi = gray[y0:y1, x0:x1]
            score = sharpness_score(roi)
            if score > best:
                best = score
                best_time = time.time()
            since_peak = time.time() - best_time
            bar_len = 50
            filled = min(bar_len, int((score / best) * bar_len)) if best > 0 else 0
            bar = "#" * filled + "-" * (bar_len - filled)
            print(f"sharpness: {score:9.2f}  |  peak: {best:9.2f} "
                  f"({since_peak:4.1f}s ago)  |  {bar}",
                  end="\r", flush=True)

            now = time.time()
            # Build the annotated preview every frame if the live window is
            # open (so the video looks smooth), otherwise only once a
            # second for the snapshot-file fallback.
            build_preview = live_window or (now - last_snapshot > 1.0)
            if build_preview:
                preview = cv2.resize(gray, (w // 4, h // 4))
                pr0, pc0 = y0 // 4, x0 // 4
                pr1, pc1 = y1 // 4, x1 // 4
                preview_bgr = cv2.cvtColor(preview, cv2.COLOR_GRAY2BGR)
                cv2.rectangle(preview_bgr, (pc0, pr0), (pc1, pr1), (0, 0, 255), 2)
                cv2.putText(preview_bgr, f"score: {score:.2f}   peak: {best:.2f}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(preview_bgr, f"mode: {MODE}   ({since_peak:.1f}s since peak)",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                # Live bar graph across the bottom of the frame, filled
                # proportional to score/peak — gives an at-a-glance visual
                # cue in the window itself, not just in the terminal.
                ph, pw = preview_bgr.shape[:2]
                bar_y0, bar_y1 = ph - 20, ph - 8
                cv2.rectangle(preview_bgr, (10, bar_y0), (pw - 10, bar_y1), (80, 80, 80), 1)
                if best > 0:
                    fill_w = int((pw - 22) * min(1.0, score / best))
                    cv2.rectangle(preview_bgr, (11, bar_y0 + 1),
                                  (11 + fill_w, bar_y1 - 1), (0, 200, 0), -1)

                if live_window:
                    cv2.imshow(WINDOW_NAME, preview_bgr)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:  # 'q' or Esc
                        raise KeyboardInterrupt
                if now - last_snapshot > 1.0:
                    last_snapshot = now
                    cv2.imwrite("focus_debug_snapshot.jpg", preview_bgr)

            time.sleep(0.05 if live_window else 0.1)
    except KeyboardInterrupt:
        print(f"\n\nStopped. Best sharpness seen this session: {best:.2f}")
        print("If that peak was more than a few seconds before you stopped, "
              "turn back to that ring position before locking it down.")
    finally:
        led_on(False)
        if _led_request is not None:
            try:
                _led_request.release()
            except Exception:
                pass
        if live_window:
            try:
                cv2.destroyWindow(WINDOW_NAME)
            except Exception:
                pass
        cam.stop_camera()


if __name__ == "__main__":
    main()
