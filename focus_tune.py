#!/usr/bin/env python3
"""
focus_tune.py — quantitative live focus assistant for the Arducam AR2020 +
ACHF080402320MP lens.

By-eye focus is inherently subjective. This script gives you a repeatable,
numeric sharpness score computed from the live image, so you can adjust the
manual focus ring while watching a number instead of trusting your eyes.

METHOD: "variance of the Laplacian" — a standard, widely-used focus metric.
The Laplacian highlights edges/detail in the image; a blurry image has weak,
smeared edges (low variance), a sharp image has strong, well-defined edges
(high variance). The number has no absolute meaning by itself — it's only
useful as a RELATIVE score to maximize on the SAME scene while you turn the
focus ring. Comparing scores between different scenes/lighting is not
meaningful.

HOW TO USE:
  1. Place a plate (or anything with fine, high-contrast detail — printed
     text, a ruler, seed/tray markings) at your real working distance, under
     your real Rear IR illumination. A blank/uniform surface gives a
     near-zero, uninformative score regardless of focus.
  2. Run this script (see command below), then SLOWLY turn the focus ring
     in one direction while watching the printed score.
  3. The score will rise, peak, and then fall as you sweep through best
     focus. Overshoot past the peak on purpose, then sweep back — the "peak
     so far" value on screen tracks the best you've seen. Bracket it in
     smaller and smaller steps until you're confident you're at the true
     maximum, not a local wobble.
  4. Once you've found the peak, tighten the lock ring at that exact
     position. Grip ONLY the lock ring while tightening — if the lens
     itself rotates even slightly while you tighten, you'll lose the focus
     point you just found. Recheck the score after tightening in case it
     shifted, and readjust if needed.
  5. Ctrl+C to stop.

RUN IT (same pattern as camera_arducam_usb3.print_diagnostics()):

    cd ~/Seedling_Imager/seedling_imager_controller
    source venv/bin/activate
    python3 focus_tune.py

NOTE: Close the main seedling imager GUI (or at least stop Live View) before
running this — only one process can hold the camera device open at a time.
"""
import time
import numpy as np
import cv2
import camera_arducam_usb3 as cam


def sharpness_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian — higher means sharper. Relative score
    only; meaningful for comparing frames of the SAME scene."""
    lap = cv2.Laplacian(gray, cv2.CV_64F)
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

    # Lock exposure/gain to your saved Rear IR values so brightness changes
    # don't masquerade as focus changes while you're turning the ring.
    live = cam.apply_ir_transmission_preset(None)
    cam.apply_settings(live)

    print(f"Streaming at {fw}x{fh}. Point the camera at a high-contrast "
          f"target (text, ruler, seed markings) at your real working "
          f"distance, then turn the focus ring slowly. Ctrl+C to stop.\n")

    best = 0.0
    best_time = time.time()
    try:
        while True:
            frame = cam._read_raw_frame()
            if frame is None:
                print("no frame — retrying...                              ",
                      end="\r", flush=True)
                time.sleep(0.2)
                continue
            gray = cam._to_gray(frame)
            # Center crop (middle third x middle third) so frame-edge
            # softness/vignetting doesn't bias the score — focus on what's
            # in the middle of the plate, which is what matters most.
            h, w = gray.shape[:2]
            roi = gray[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
            score = sharpness_score(roi)
            if score > best:
                best = score
                best_time = time.time()
            since_peak = time.time() - best_time
            bar_len = 50
            filled = min(bar_len, int((score / best) * bar_len)) if best > 0 else 0
            bar = "#" * filled + "-" * (bar_len - filled)
            print(f"sharpness: {score:9.1f}  |  peak: {best:9.1f} "
                  f"({since_peak:4.1f}s ago)  |  {bar}",
                  end="\r", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n\nStopped. Best sharpness seen this session: {best:.1f}")
        print("If that peak was more than a few seconds before you stopped, "
              "turn back to that ring position before locking it down.")
    finally:
        cam.stop_camera()


if __name__ == "__main__":
    main()
