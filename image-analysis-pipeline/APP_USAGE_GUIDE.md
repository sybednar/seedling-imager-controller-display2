# ArabidopsisAnalysisV2: Application Usage Guide

Source material for the "How to use each app" web pages. Everything below was taken from the code (`run.py` and helper scripts of each app), not from running the GUIs. Items marked **[VERIFY]** are inferred from code and should be checked in a real session. Items marked **[SCREENSHOT]** are the places where a real screenshot should go.

---

## 0. The big picture

Three desktop GUI apps (PyQt5), used in this order:

| # | App | Folder | Launch | Purpose |
|---|-----|--------|--------|---------|
| 1 (optional) | **Image Aligner** | `imageAligner/` | `cd imageAligner && python run.py` | Removes horizontal drift between timelapse frames using an ArUco marker |
| 2 | **Segmentation** (window title: "nnUNet Segmentation Monitor") | `segmentationApp/` | `cd segmentationApp && python run.py` | Runs the nnU-Net model on every frame, then temporally smooths the masks |
| 3 | **Single Plant Analysis** (window title: "ChronoRootAnalysis") | `singlePlantAnalysis/` | `cd singlePlantAnalysis && python run.py` | Tracks one plant's root over time, measures it, and builds statistical reports |

Always `conda activate ChronoRoot` first. On macOS the installer also creates `ChronoRoot Analysis.app`, `ChronoRoot Segmentation.app` and `ChronoRoot Image Aligner.app` launchers (first launch: right-click, Open). The Linux and WSL installers likewise create a "ChronoRoot Image Aligner" shortcut.

### Data flow

```
Raw timelapse images (PNG / TIF / TIFF, one folder per plate)
        │
        ▼  (optional)
[1] Image Aligner        →  <plate>/aligned/<name>_aligned.<ext>
        │
        ▼
[2] Segmentation         →  <folder>/Segmentation/Fold_0/        raw nnU-Net masks
                            <folder>/Segmentation/Ensemble/      temporally smoothed masks (used by analysis)
                            <folder>/Segmentation/segmentation_metadata.json
        │
        ▼
[3] Single Plant Analysis →  <Project>/Analysis/<experiment>/cam_<N>/plant_<M>/Results_<k>/
                             <Project>/Report/…                  figures, CSVs, statistics
```

### Folder conventions to explain on the page

- **Video folder / image folder**: a folder that directly contains the timelapse frames (`.png`, `.tif`, `.tiff`), sorted by filename. One folder = one plate/camera sequence.
- **Experiment folder** (Segmentation app): a parent folder whose immediate subfolders are each an image folder (e.g. `Experiment_X/plate1`, `plate2`, …).
- **Project folder** (Analysis app): an output folder you choose. The app creates `Analysis/`, `Report/`, `Removed/` and `project_config.json` inside it.

---

## 1. Image Aligner

**What it does:** Detects an ArUco marker in every frame and shifts each frame **horizontally** so the marker sits where it was in the first frame. Use it when the plate or camera shifted sideways during the timelapse.

**Window:** "Image Aligner", about 1000 × 500 px. Single screen, no tabs. **[SCREENSHOT: main window with 2–3 folders loaded, one Complete, one Aligning]**

### Requirements
- An ArUco marker from the **`DICT_4X4_1000`** dictionary visible in the images (same marker family the Analysis app uses for scale calibration).
- Images are `.png`, `.tif` or `.tiff`, directly inside each folder.
- **The marker must be detected in the first frame.** It is the reference. If it is not, the app warns "No ArUco marker detected in the first frame — images left unaligned." and writes unmodified copies.

### Step by step
1. **Load Folder** (green button, top left). A folder picker opens; you can multi-select. Pick the **parent** folder that holds your plate folders. Every **immediate subfolder** becomes one row in the table (the parent itself is not added). The log shows "Loaded N folder(s) from …".
2. For each row, click **Align**. The row becomes **Queued**, then **Aligning**. Folders are processed **one at a time**, in the order queued.
3. Watch the **Progress** column and the log at the bottom. Progress covers two phases: detecting markers (first half), then writing aligned images (second half). Frames with no marker are logged as "Warning: no marker detected in <file>".
4. When the row turns **Complete** (green), aligned images are in `<folder>/aligned/`, each renamed `<original name>_aligned.<ext>`.

### Interface reference

**Top bar**

| Control | What it does |
|---|---|
| Load Folder | Add the subfolders of one or more chosen folders as rows |
| `Queue: N \| Idle` label | Number of folders waiting, and which folder is processing |
| Clear Queue (red) | Removes all *pending* folders from the queue. Does not stop the one running |

**Table columns**: Folder · Images (count of png/tif/tiff) · Aligned (count in `aligned/`) · Progress (bar) · Status · Action · Remove

**Status values**

| Status | Meaning | Action button |
|---|---|---|
| Not Started | No `aligned/` folder yet | **Align** (green) |
| Queued | Waiting its turn | **Cancel** |
| Aligning | Currently running | **Kill Process** (red) |
| Incomplete | `aligned/` has fewer images than the source | **Re-align** (blue) |
| Complete | `aligned/` has at least as many images as the source | **Re-align** (blue) |
| Error | Worker raised an error (e.g. unreadable image) | **Retry** (orange) |
| No Images | Folder has no png/tif/tiff | none |

- **Remove** (per row): stops tracking the folder in the app. Files are not deleted.
- The table refreshes automatically (about every 1–3 s), so it picks up changes made on disk.
- Closing the window while a job runs asks "Force quit?"

### Behaviour users should know
- **Horizontal only.** The shift is computed from the marker centroid in x. There is no vertical correction, rotation or scale correction.
- **Frames with no marker detected** are copied unchanged (no shift) into `aligned/`.
- Source images are never modified; output goes to the `aligned/` subfolder.
- **Re-align** on a Complete folder overwrites files in `aligned/` that share the same names.

### Using the output downstream
The aligned images sit in an `aligned/` subfolder of each plate. The Segmentation app detects it automatically: when you load the experiment folder, each plate's `aligned` subfolder gets its own row (shown as `plate1/aligned`) next to the plate itself. Segment that row, then point the Analysis app's "Select Video Folder" at `<plate>/aligned`.

### Troubleshooting
| Symptom | Likely cause / fix |
|---|---|
| "No ArUco marker detected in the first frame" | Marker missing, occluded or out of focus in frame 1. Crop/re-shoot, or skip alignment |
| Many "no marker detected" warnings | Marker partly hidden, glare, or wrong dictionary (must be 4×4_1000) |
| Row says "No Images" | Folder holds images in a subfolder, or uses another extension |
| Row stuck at Error | Check the log for "Failed to read image: <file>"; fix or remove the file, then Retry |

---

## 2. Segmentation app

**What it does:** Classifies every pixel of every frame (background, main root, lateral root, seed, hypocotyl, leaf, petiole) with an nnU-Net model, then smooths the masks over time. It is a **monitor/queue UI**: the real work runs in a background process (`cli.py`) in the `ChronoRoot` conda environment.

**Window:** "nnUNet Segmentation Monitor", about 1400 × 600 px. Single screen. **[SCREENSHOT: full window with several experiments, mix of statuses]**

### Requirements
- Conda env **ChronoRoot** with PyTorch/nnU-Net installed. If PyTorch is missing the app shows "missing PyTorch … monitor mode only".
- Model weights in `segmentationApp/models/<Species>/` (run `./download_weights.sh`, or the installer does it). The **Model** dropdown lists whatever folders exist there (currently Arabidopsis, Tomato).
- Images directly inside each plate folder.
- GPU: the app requests CUDA; if unavailable it falls back to Apple MPS, then CPU. CPU is much slower.

### Step by step
1. **Choose the model** in the **Model** dropdown. Switching sets **Alpha** automatically: Arabidopsis → **0.85**, Tomato → **0.60**.
2. **Load Experiment**: pick one or more experiment folders (multi-select). The folder name becomes the experiment name; its immediate subfolders become the rows. If a plate folder contains an `aligned` subfolder (Image Aligner output), that appears as an additional row labelled `<plate>/aligned`. **[VERIFY]** wording: the header label says "Experiments: N" initially, but some internal text still says "Robots".
3. (Optional) adjust **Alpha**, **Fast Mode**, or **Conda** (see reference).
4. Click **Start Pipeline** on a row (green). It is queued; one folder runs at a time. The pipeline has two stages:
   - **Stage 1, Segmentation:** nnU-Net predicts each frame → `Segmentation/Fold_0/`
   - **Stage 2, Temporal postprocessing:** a weighted trailing average over frames (controlled by alpha) → `Segmentation/Ensemble/`
5. Watch **Segmentation %** and **Postprocessing %** bars and the log. When Status is **Complete**, the folder is ready for the Analysis app.

### Interface reference

**Top bar** (left to right)

| Control | What it does |
|---|---|
| Load Experiment (green) | Add experiment folders (multi-select) |
| Remove Experiment (grey) | Unloads the experiment currently chosen in the *Filter Experiment* dropdown (must pick one, not "All Experiments"). Asks to confirm. Files untouched |
| `Experiments: N` label | Count of loaded experiments |
| `Queue: N \| Processing: …` label | Queue length and current folder |
| Alpha: 0.85 (blue) | Opens a numeric dialog (0.00–1.00). Temporal smoothing weight used in postprocessing |
| Model: [dropdown] | Species model to use |
| Fast Mode (checkbox) | Disables test-time mirroring augmentation. Faster, slightly less accurate |
| Hide Empty Folders (checkbox) | Hides rows with status "No Images" (folders with no png/tif/tiff). Untick to show them again |
| Clear Queue (red) | Drops all pending items |
| Conda: ChronoRoot | Set the conda environment name used for the background process |

**Filter row**: *Filter Experiment* (dropdown) and *Filter Status* (All Status, Not Started, Queued, Segmenting, Stalled, Segmented, Postprocessing, Complete, Different Alpha, Different Model, Error).

**Table columns**: Experiment · Folder Name · Images · Segmentation % · Postprocessing % · Model - Alpha · Status · Actions · Remove View · Clear Results

**Status values and the action offered**

| Status | Meaning | Buttons |
|---|---|---|
| Not Started | No results | **Start Pipeline** |
| Queued | Waiting | **Cancel** |
| Segmenting | Stage 1 running | **Kill Process** (if started from this window), otherwise "Running…" |
| Postprocessing | Stage 2 running | **Kill Process** / "Running…" |
| Stalled | Marked "Started" but no progress update for more than 10 × the average time per image | **Resume** (continues from the processed files list) |
| Error (Seg) | Stage 1 failed | **Restart Pipeline** or **Resume** |
| Error (Post) | Stage 2 failed | **Rerun Postprocessing** |
| Segmented | Stage 1 done, Stage 2 not | **Rerun Postprocessing** |
| Complete | Both stages done with the current model and alpha | none |
| Different Alpha | Complete, but done with a different alpha than currently set | **Update Alpha** (reruns Stage 2 only; fast) |
| Different Model | Complete, but with another model | **Rerun Pipeline** (everything) or **Postproc Only** (keep masks) |
| Different Model and Alpha | Both differ | Same two buttons as above |
| Complete (Legacy), Segmented (Legacy), Incomplete (Legacy) | Folders made by older versions (detected from `Fold_0` / `Ensemble` contents) | Rerun Postprocessing where applicable |
| No Images | No png/tif/tiff found | none |

**Per-row buttons**
- **Remove**: stop monitoring this folder. Nothing deleted.
- **Clear Results** (red): **permanently deletes the folder `Segmentation/`** after a confirmation dialog. Source images untouched. Cannot be undone.

**Settings persistence**: conda env, alpha, model and fast mode are saved to `~/.config/chronoroot/segmentationInterfaceConfig.json` and restored next launch.

### What "alpha" means (plain-language)
Postprocessing blends each frame's prediction with a running accumulation of earlier frames: `accum = α · accum + (1 − α) · new`. Higher α trusts history more (smoother, slower to react to real growth). Defaults: **0.85 Arabidopsis, 0.60 Tomato**. Changing alpha later only needs Stage 2, which is why "Update Alpha" is quick.

### Output on disk
```
<folder>/Segmentation/
    Fold_0/                       raw per-frame predictions (PNG)
    Ensemble/                     smoothed masks. The Analysis app reads this folder
    segmentation_metadata.json    status, progress, model, alpha, timestamps, image list
```
Mask pixel values: 0 background · 1 main root · 2 lateral root · 3 seed · 4 hypocotyl · 5 leaf · 6 petiole · 7 ignore.

### Command-line alternative (headless)
```bash
cd segmentationApp
python cli.py /path/to/images --model Arabidopsis            # full pipeline
python cli.py /path/to/images --model Arabidopsis --resume   # continue an interrupted run
python cli.py /path/to/images --model Tomato --alpha 0.7 --postprocess-only
```
Flags: `--model/-m` (required), `--alpha/-a`, `--output/-o`, `--device {cuda,cpu}`, `--fast`, `--postprocess-only`, `--resume`.

### Troubleshooting
| Symptom | Fix |
|---|---|
| "missing PyTorch … monitor mode only" | The conda env named in the **Conda** button lacks PyTorch. Use the full install, or correct the env name |
| Model dropdown shows "No models found" | Run `./download_weights.sh` in `segmentationApp/` |
| Status **Stalled** | Process died or hung. Click **Resume** |
| Very slow | Running on CPU. Enable Fast Mode, or use a CUDA machine |
| Closing window kills the job | By design. A confirmation appears first, and the folder is marked "Error: Terminated" in metadata so you can Resume |
| Segmentation folder deleted by mistake | **Clear Results** is permanent; rerun the pipeline |

---

## 3. Single Plant Analysis app

**What it does:** For one plant at a time, you mark the region of interest and the root's starting point on a segmented timelapse. The app then tracks the root system frame by frame and measures main root length, lateral root length and count, total length and hypocotyl length. Once several plants are done it builds a statistical report.

**Window:** "ChronoRootAnalysis", fixed size 810 × 680 px, **six tabs**: Plant Analysis · Analysis Overview · Plant Overlay · Generate Report · Report · About. **[SCREENSHOT: one per tab]**

### End-to-end workflow (the page's main narrative)
1. **Plant Analysis tab**: choose project folder and video folder, fill in camera / plant / identifier, set scale calibration, press **Analyze Plant**.
2. In the pop-up OpenCV windows: drag the plant's **ROI**, then click the **root origin**.
3. Wait while tracking runs (progress prints in the terminal that launched the app). Repeat steps 1–3 for each plant (change *Plant Number*, and *Camera* if needed).
4. **Analysis Overview tab**: check every plant is Finished and review error rates. Inspect plants in **Plant Overlay**. Remove or redo bad ones.
5. Press **Process all plants** (post-processing: pixel-size conversion, hourly tables, per-plant plots, lateral-angle data).
6. **Generate Report tab**: pick statistics options, press **Generate report**.
7. **Report tab**: browse the generated figures; open the report folder.

### Prerequisites per video folder
- Frames (png/tif/tiff) in the folder.
- A completed segmentation: `<video folder>/Segmentation/Ensemble/` containing mask files. Without it, Analyze Plant stops with "Found N images but no segmentation files!".
- Tip: if the video folder has no images but has `Segmentation/segmentation_metadata.json`, the app reads the images from the `input_path` stored there (so images may live elsewhere as long as they haven't been moved).

---

### Tab 1: Plant Analysis

**[SCREENSHOT: Tab 1, filled in]**

Top: heading **"Individual plant root analysis"**.

| Control | Details |
|---|---|
| **Select Project Folder** + path field | Output location (holds `Analysis/`, `Report/`, `Removed/`, `project_config.json`). Mirrors the project field on the Generate Report tab |
| **Select Video Folder** + path field | Folder with the timelapse images and a `Segmentation/` subfolder |
| **Camera** | Plate/camera identifier, default `1`. Becomes folder `cam_<value>` |
| **Plant Number** | Number identifying the plant in the plate, **left to right**, default `1`. Becomes folder `plant_<value>` |
| **Identifier** | Experiment/genotype label, e.g. `WT`, `Col0`. Default `1`. Becomes the first folder level under `Analysis/` |

Empty Camera / Plant Number / Identifier fields revert to `1`.

Heading **"Analysis and postprocessing parameters"**

| Control | Default | Details |
|---|---|---|
| **Set processing limit** | 0 | Days of the timelapse to process. 0 = no limit |
| **Capture interval** | 15 | Minutes between frames. Affects time axes and hour binning |
| **Emergence distance** | 2 | mm. Distance from the main root at which a lateral root counts as emerged (used for lateral-root angle analysis) |
| **Save Cropped Images** (checkbox) | off | Saves per-plant crops. Required for making growth timelapse videos |

Capture interval, processing limit and project folder appear on both Tab 1 and Tab 4 and are kept in sync.

**Scale calibration**: how pixels become millimetres. Pick one:

| Option | When to use |
|---|---|
| **Video has ArUco markers** (checkbox) | Preferred. Marker width is taken as **15 mm**. Tried first if both boxes are ticked |
| **Video has QR codes** (checkbox) | Older datasets. QR code treated as **1 cm (10 mm)** |
| Neither ticked: **Manual calibration** panel appears | Enter **Known (mm)** and **Pixels**. Pixel size = mm ÷ pixels |

**Open Calibration Helper** (manual mode only): opens a small viewer on the first image of the video folder. Left-click two points of known distance (a distance line and pixel length are drawn), mouse wheel zooms, right-click-drag pans, **Clear Points** resets, **Copy Distance** copies the pixel length to the clipboard. Paste into *Pixels* and enter the real distance in *Known (mm)*. Example placeholders: 10 mm / 240 px.

**Right-hand buttons**

| Button | What it does |
|---|---|
| **Save** | Writes all fields to the global config and to `<project>/project_config.json` |
| **Preview video** | Opens the sequence viewer on the raw frames to eyeball image quality and segmentation |
| **Analyze Plant** | Validates inputs, saves config, and starts the analysis in a separate process |
| **Process all plants** | Runs post-processing for the whole project (see Step 5) |
| **Load config json from file** | Pick any saved `.json` config and fill the form |
| **Load previous configuration** | Restore the last saved settings (project config if it exists, otherwise global) |

**What happens after "Analyze Plant"** (two OpenCV windows, then tracking):
1. **"Select Plant ROI"** shows the **last** frame. Click-drag a rectangle around the plant (rectangular; include the whole root's final extent but avoid neighbouring plants if you can). Keys: **Enter** confirm · **R** redo · **Q** quit.
2. **"Select Root Origin"** shows the cropped ROI. Drag the trackbar to scrub through time; press **S** to toggle the segmentation colour overlay. **Click** where the root starts (a green cross and "Root Start" line appear). Keys: **Enter** confirm · **S** toggle segmentation · **Esc / C / Q** cancel. (Note: The model may sometimes missegment shoots as roots during early growth stages, it is important to go through the whole timelapse and make sure the you are selecting the true root origin to prevent inaccuracies in measurements)
3. Tracking runs through every frame

**Validation messages the user may see**
- "Please specify a video folder first!"
- "Video folder does not exist!"
- "No images found in the video folder!"
- "Found N images but no segmentation files! … Segmentation is required for analysis."
- "Please provide both known distance and pixel distance for manual calibration, or enable "Video has QR codes" or "Video has ArUco markers"!"
- "Calibration values must be positive numbers!" / "Invalid calibration values!" (known distance: number, pixel distance: **integer**)

---

### Tab 2: Analysis Overview

**[SCREENSHOT: table with a few plants]**

A sortable table listing every analysed plant under `<project>/Analysis/`.
Columns: **Experiment · Camera · Plant Number · Result ID · Error Rate · Status · Finish Date**

- **Status**: *Finished* when a `log.txt` exists in the result folder, otherwise *Not finished* (also shown while still running).
- **Error Rate**: read from the last line of `log.txt` (fraction of frames where tracking failed), rounded to 4 decimals. Lower is better.
- **Result ID** (`Results_0`, `Results_1`, …): each analysis run creates a new result folder (up to 50). Later steps use the **latest** one.

Buttons (select a row first):

| Button | What it does |
|---|---|
| Refresh | Reload the table |
| Open Path | Opens the plant's result folder in the system file manager |
| Remove Plant | Moves the folder to `<project>/Removed/…` (same structure). Hides it from reports without deleting data; to restore, move it back |
| Repeat Analysis | **Quick re-run**: re-tracks using the saved ROI and root start point |
| Process all plants | Same as on Tab 1 |

The table also refreshes whenever you switch to this tab.

---

### Tab 3: Plant Overlay

**[SCREENSHOT: left cropped plant with overlay, right summary plot]**

Visual QC of one plant.
- Left image: the **last frame**, cropped to the ROI. With **Overlay Image** ticked, the colour-coded tracking result is blended at 50 %.
- Right image: the plant's summary plot (`<experiment>_<camera>_<plant>.png`). A placeholder shows until post-processing has produced it.
- A plant dropdown (full result-folder paths) selects which plant to inspect.

Overlay colours (SegMulti visualization): main root **red**, lateral roots **green**, hypocotyl **yellow**, root tip marker **cyan**.

| Button | What it does |
|---|---|
| Refresh | Refresh the plant list |
| Open Folder | Open this plant's result folder |
| **View full sequence** | Opens the **ChronoRoot Viewer**: slider through every frame (click anywhere on the slider to jump), **Play/Pause**, **Toggle Segmentation**, mouse-wheel zoom, click-drag pan. Shows "Day: N  Time: HH:MM" |
| **Redo Analysis** | **Manual re-run**: discards the saved ROI and root start so you pick new ones |
| Remove Plant | Move to `Removed/` |

When to use which re-run: *Repeat Analysis* (Tab 2) keeps the same ROI and origin; *Redo Analysis* (Tab 3) starts from scratch with new selections.

---

### Tab 4: Generate Report

**[SCREENSHOT: Tab 4]**

Controls which analyses go into the report. Project folder, processing limit and capture interval are repeated here (kept in sync with Tab 1).

| Section | Controls | Defaults |
|---|---|---|
| **Statistics** | *Average intervals before testing* (checkbox). *Time series stats interval (dt, in hours)* | dt = 6 |
| Explanatory text | "Hypothesis testing uses Mann-Whitney test every dt interval. If selected, an average value will be used, or a step (i*dt) otherwise" | |
| **Functional PCA** | *Perform Functional PCA on time series*, *Normalize FPCA Boxplots*, *Number of components* | components = 2 |
| **Convex hull** | *Do Convex hull analysis*, *Save images for each day*, *Days to report* (comma-separated, e.g. `3,5,7`) | |
| **Growth speeds + Fourier** | *Evaluate Growth Speeds and perform Fourier Analysis*, *Speeds stats interval (dt, in hours)* | dt = 6 |
| **Lateral root angles** | *Do Lateral Root Angles Analysis*, *Emergence distance* (mm, default 2), *Days to report*, *First LR Tip Stats interval (dt, in hours)* | emergence 2 mm, dt = 6 |
| Bottom row | *Processing limit*, *Capture interval* | 0, 15 |

Buttons: **Save**, **Process all plants**, **Generate report**, **Load previous configuration**.

Run **Process all plants** first, then **Generate report**. Report generation can take a while; progress prints in the terminal. Statistical comparisons are between experiments (identifiers).

---

### Tab 5: Report

**[SCREENSHOT: a report figure displayed]**

A figure browser. The dropdown lists every PNG one level inside `<project>/Report/` (newest names first). Buttons: **Refresh**, **Open Report Path**.

### Tab 6: About
Logo, project description, link, **Check for Updates** (runs `git pull` in the install folder; restart afterwards) and the date of the last local commit.

---

### Output on disk

Per plant:
```
<Project>/Analysis/<Identifier>/cam_<Camera>/plant_<Plant>/Results_<k>/
    Results_raw.csv            per-frame: MainRootLength, LateralRootsLength, NumberOfLateralRoots, TotalLength, HypocotylLength
    PostProcess_Hour.csv       hourly, calibrated (mm) after "Process all plants"
    PostProcess_Original.csv
    metadata.json              ROI, root start, pixel size, paths
    log.txt                    completion date + error rate
    Images/ (Seg, SegMulti, Input*)    *Input only if "Save Cropped Images"
    Graphs/    RSML/           root graphs and RSML export
```
Project-level:
```
<Project>/Report/
    Individual plant plots/
    Temporal Parameters/              stats text files, summary table CSV, mean ± SE plots (png/svg)
    Temporal_Data.csv
    Convex Hull and Area Analysis/    (if enabled)  + Convex_Hull_Data.csv
    FPCA/                             (if enabled)
    GrowthSpeeds and Fourier/         (if enabled)
    Angles Analysis/                  (if enabled)  + LateralRootsData.csv, SyncronizedFirstLR.csv
<Project>/Removed/                    plants you removed
<Project>/project_config.json         saved settings (reproducibility)
```
Settings are also saved globally to `~/.config/chronoroot/mainInterfaceConfig.json`.

Measured temporal parameters in the report: Main Root Length, Lateral Roots Length, Total Length (all mm), Number of Lateral Roots, Discrete Lateral Density (LR/cm), Main Over Total (%), Hypocotyl Length (mm).

### Batch/headless scripts (in `singlePlantAnalysis/`)
`1_analysis.py --config <json> [--rerun | --restart]`, `2_postprocess.py --config <json>`, `3_generateReport.py --config <json>`, `5_rerun_all_analysis.py`. The GUI buttons call these.

### Troubleshooting
| Symptom | Cause / fix |
|---|---|
| "no segmentation files" | Run the Segmentation app first; need `Segmentation/Ensemble/` |
| Scale looks wrong / lengths off by a constant factor | Wrong calibration. Check ArUco/QR checkbox vs actual marker; if no marker is found in the first 20 images, post-processing falls back to a default of 0.04 mm/px **[VERIFY with the user how visible this is]** |
| Root start click ignored / window closes | Enter only confirms after a click; Esc/C/Q cancels |
| Plant stays "Not finished" | Analysis still running or crashed; check the terminal. Use Redo Analysis |
| High error rate | Poor segmentation or wrong ROI/origin. Use View full sequence with Toggle Segmentation, then Redo Analysis |
| Main root length missing/zero early in series | Known issue under investigation in the post-processing step (see `TODO.md`) |
| `no Qt platform plugin could be initialized` (Linux/WSL) | Missing Qt/X11 libraries or running under WSL1. See `WSL_INSTALL.md` |
| Folder opener does nothing | The app shows the path in a dialog to open manually |

---

## 4. Suggested page structure for the website

1. **Overview**: the three-app flow diagram above.
2. **Image Aligner** (short page)
3. **Segmentation** (medium)
4. **Single Plant Analysis** (long): break into the 7 workflow steps; tab reference as an accordion.
5. **Reference**: status glossaries, output folder trees, CLI commands, troubleshooting.

### Screenshot checklist (to capture)
- Aligner: loaded table with mixed statuses
- Segmentation: full window; Alpha dialog; a Different Alpha row
- Analysis: Tab 1 (ArUco mode) · Tab 1 (manual-calibration mode) · Calibration Helper · ROI window · Root-origin window · Tab 2 · Tab 3 with overlay · Sequence viewer · Tab 4 · Tab 5 · a sample report figure

### Notes for the writer
- The apps still say "ChronoRoot" in places (config folders, About tab, window titles). Keep names as shown in the UI.
- The Analysis app's OpenCV windows (ROI and root origin) are separate windows, not part of the main GUI.
- Some Segmentation app labels still say "Robots" instead of "Experiments" (for example the count after loading). Use "experiment" on the site.
