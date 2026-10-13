#!/usr/bin/env python3
"""
analyze_run.py — quick image-quality check of a finished experiment folder.

Usage (from the project folder, venv active):
    python3 analyze_run.py ~/Seedling_Imager/images/experiment_YYYYMMDD_HHMMSS

For every plateN_*_rear_gray.tif found under the folder it measures:
  bg      median brightness of the lit (agar) area, grey levels
  max     brightest pixel
  clip    fraction of pixels at >= 250 (saturation check)
  sharp   brightness-normalised Laplacian variance of the central region,
          after 4x block-averaging (same idea as focus_tune.py; compare only
          within a run — it depends on exposure, noise and image content)
  dx, dy  sub-pixel shift of this image vs. that plate's first image
          (phase correlation, in full-resolution pixels)

Writes analysis.csv into the experiment folder and prints a per-plate
summary. Read-only with respect to the images.
"""
import csv
import re
import sys
from pathlib import Path

import cv2
import numpy as np

try:
    import tifffile
except ImportError:  # OpenCV can read these 8-bit TIFFs too
    tifffile = None

DS = 4


def _read(path):
    if tifffile is not None:
        return tifffile.imread(str(path))
    return cv2.imread(str(path), cv2.IMREAD_UNCHANGED)


def measure(path):
    g = _read(path).astype(np.float32)
    if g.ndim == 3:
        g = g[..., 0]
    h, w = g.shape
    lit = g[g > g.max() * 0.4]
    bg = float(np.median(lit)) if lit.size else float(g.mean())
    roi = g[int(h * 0.13):int(h * 0.86), int(w * 0.25):int(w * 0.82)] / max(bg, 1.0)
    small = cv2.resize(roi, (roi.shape[1] // DS, roi.shape[0] // DS), interpolation=cv2.INTER_AREA)
    sharp = float(cv2.Laplacian(small, cv2.CV_32F).var())
    thumb = cv2.resize(g / max(bg, 1.0), (w // DS, h // DS), interpolation=cv2.INTER_AREA)
    return {
        "bg": bg, "max": float(g.max()), "clip": float((g >= 250).mean()),
        "sharp": sharp, "thumb": thumb,
    }


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    root = Path(sys.argv[1]).expanduser()
    files = sorted(root.rglob("plate*_rear_gray.tif"))
    if not files:
        print(f"No plate*_rear_gray.tif files under {root}")
        sys.exit(1)

    plates = {}
    for f in files:
        m = re.match(r"plate(\d+)_(\d{8})_(\d{6})_", f.name)
        if m:
            plates.setdefault(int(m.group(1)), []).append((m.group(2) + m.group(3), f))

    rows = []
    for p in sorted(plates):
        ref = None
        win = cv2.createHanningWindow
        for stamp, f in sorted(plates[p]):
            try:
                r = measure(f)
            except Exception as e:  # unreadable/truncated file
                print(f"plate{p} {f.name}: READ ERROR {e}")
                rows.append({"plate": p, "time": stamp, "file": f.name, "error": str(e)})
                continue
            if ref is None:
                ref = r["thumb"]
                dx = dy = 0.0
            else:
                (sx, sy), _ = cv2.phaseCorrelate(ref.astype(np.float32), r["thumb"].astype(np.float32),
                                                 win(ref.shape[::-1], cv2.CV_32F))
                dx, dy = sx * DS, sy * DS
            rows.append({"plate": p, "time": stamp, "file": f.name, "bg": round(r["bg"], 1),
                         "max": r["max"], "clip": round(r["clip"], 5),
                         "sharp": round(r["sharp"], 6), "dx": round(dx, 3), "dy": round(dy, 3)})

    out = root / "analysis.csv"
    cols = ["plate", "time", "file", "bg", "max", "clip", "sharp", "dx", "dy", "error"]
    with open(out, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)

    print(f"\n{len(files)} images, written to {out}\n")
    print("plate  n   bg first->last (min..max)    sharp mean (CV%)  worst clip   max |dx|,|dy| px")
    for p in sorted(plates):
        r = [x for x in rows if x["plate"] == p and "bg" in x]
        if not r:
            continue
        bg = [x["bg"] for x in r]
        sh = np.array([x["sharp"] for x in r])
        cl = max(x["clip"] for x in r)
        mdx = max(abs(x["dx"]) for x in r)
        mdy = max(abs(x["dy"]) for x in r)
        print(f"{p:>5} {len(r):>3}   {bg[0]:6.1f} -> {bg[-1]:6.1f} ({min(bg):.0f}..{max(bg):.0f})"
              f"   {sh.mean():.5f} ({100*sh.std()/sh.mean():4.1f}%)   {cl:.4f}    {mdx:.2f}, {mdy:.2f}")
    print("\nNote: the first image of each plate is the registration reference (dx=dy=0).")


if __name__ == "__main__":
    main()
