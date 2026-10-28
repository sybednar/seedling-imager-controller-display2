# Content Inventory

Snapshot of everything on the ArabidopsisAnalysisV2 project site (`docs/`), gathered as input for a UI redesign. Content only: pages, text, images, links, structure. Visual styling is summarized at the end, not catalogued.

- Source of truth: the files under `docs/`. Page text below is copied verbatim from them.
- Liquid tags such as `{{ '/path' | relative_url }}` resolve to `/ArabidopsisAnalysisV2/path` on the deployed site (`baseurl`), and must stay that way in any redesign.
- Site: <https://calvinyong1.github.io/ArabidopsisAnalysisV2/> · repo `calvinyong1/ArabidopsisAnalysisV2`
- Site constraints from `docs/CLAUDE.md`: plain Jekyll (no Tailwind/bundler), one stylesheet, JS is progressive enhancement only, no mention of a Screening app.

## 1. Site map

| Page | Source file | URL (under baseurl) | Layout | Title tag |
|---|---|---|---|---|
| Landing | `index.html` | `/` | none (own full HTML) | `ArabidopsisAnalysisV2 \| root & hypocotyl phenotyping` |
| Install Guide | `docs/install.md` | `/docs/install.html` | `default` | Install Guide \| ArabidopsisAnalysisV2 |
| What's New in This Fork | `docs/model-and-improvements.md` | `/docs/model-and-improvements.html` | `default` | What's New in This Fork \| ArabidopsisAnalysisV2 |
| Fine-tuning nnU-Net | `docs/training.md` | `/docs/training.html` | `default` | Fine-tuning nnU-Net \| ArabidopsisAnalysisV2 |
| Architecture Notes | `docs/architecture.md` | `/docs/architecture.html` | `default` | Architecture Notes \| ArabidopsisAnalysisV2 |
| Changelog | `changelog.md` | `/changelog.html` | `default` (set in front matter) | Changelog \| ArabidopsisAnalysisV2 |

Other files: `_config.yml`, `_layouts/default.html`, `assets/css/style.css`, `assets/js/landing.js`, `assets/js/docs.js`, `README.md` (stale, excluded from build).

Navigation graph:

```
Landing (/)
 |- #apps ........... 3 app cards (no links)
 |- #whats-new ...... 4 entries -> "Read all improvements" -> What's New page
 |- #docs ........... 5 cards -> Install, What's New, Training, Architecture, Changelog
 |- hero CTAs ....... Install guide, Model Site (HF), Dataset Site (HF)
Doc pages (layout: default)
 |- header nav -> /#apps, What's New, /#docs, GitHub
 |- "<- All docs" back link -> /#docs
 |- (JS) "On this page" section rail built from headings
```

## 2. Shared chrome

### 2.1 Header (every page)
- Brand: `Arabidopsis` + `<span>Analysis</span>` + `V2` (links to `/`). The middle word is styled differently.
- Nav links:

| Label | Landing target | Doc-page target |
|---|---|---|
| Apps | `#apps` | `/#apps` |
| What's new | `#whats-new` | `/docs/model-and-improvements.html` |
| Docs | `#docs` | `/#docs` |
| GitHub | `https://github.com/calvinyong1/ArabidopsisAnalysisV2` | same |

- Landing only: a decorative scroll-progress line along the header's bottom edge.

### 2.2 Footer (every page)
`ArabidopsisAnalysisV2 · source` ("source" links to the GitHub repo).

### 2.3 Doc-page frame (`_layouts/default.html`)
Header, then `article.doc-body > .wrap > .doc-main` containing a back link (`&larr; All docs` -> `/#docs`) and the rendered markdown, then footer.

### 2.4 Fonts and head
IBM Plex Mono (400/500/600) and IBM Plex Sans via Google Fonts. Landing has a `<meta name="description">`: "A maintained fork of ChronoRoot2 for Arabidopsis and tomato root/hypocotyl phenotyping from timelapse imaging." `_config.yml` description: "Root and hypocotyl phenotyping for Arabidopsis and tomato timelapse imaging. A maintained fork of ChronoRoot2."

## 3. Landing page (`index.html`)

### 3.1 Hero
- H1: "Plant phenotyping,<br>tracked plant by plant."
- Lede: "A GUI pipeline for segmenting and measuring root and hypocotyl growth from Arabidopsis timelapse plates: image alignment, nnU-Net segmentation, and per-plant growth curves, end to end."
- Meta line: "Fork of `ngaggion/ChronoRoot2` · maintained at `calvinyong1/ArabidopsisAnalysisV2`" (both in `<code>`, not linked).
- CTA row:

| Button | Style | Target |
|---|---|---|
| Install guide | primary | `/docs/install.html` |
| Model Site | ghost | https://huggingface.co/calvinyong1/arabidopsis-segmentation-model |
| Dataset Site | primary | https://huggingface.co/datasets/calvinyong1/ArabidopsisDataset |

- Chart panel (inline SVG, 460x240, decorative illustration of fake data): label left "MainRootLength & HypocotylLength", label right "plate3 / plant_2"; 3 grid lines, 2 curves (main = primary, hypocotyl = secondary). `aria-label`: "Example root and hypocotyl growth curves over time". No axes or numbers.

### 3.2 Apps (`#apps`)
Section head: "Three GUI Apps, Each With Its Own run.py". Cards are not links.

| Card | Text |
|---|---|
| imageAligner | Aligns raw plate timelapses frame to frame before segmentation. Falls back to an identity transform when a reference-frame marker can't be found, so one bad frame doesn't block the whole plate. |
| segmentationApp | Runs nnU-Net inference over aligned frames (root, lateral root, hypocotyl, seed, leaf, and petiole classes) with GPU detection and a CPU fallback. |
| singlePlantAnalysis | Turns segmentation masks into per-plant growth curves (main/lateral root length, lateral count, hypocotyl length) and generates the final report. |

### 3.3 What's new (`#whats-new`)
Section head: "What's New in This Fork". Entries are a small tag (in the `.date` slot) plus heading and text.

| Tag | Heading | Text |
|---|---|---|
| Model | Accurate Segmentation of Elongated Hypocotyls | The original model often mislabeled long hypocotyls, cutting them short and throwing off their length. The retrained model segments them correctly. |
| macOS | Native macOS App | One installer sets up everything and adds clickable apps to Applications. On Apple Silicon, segmentation runs on the Mac's graphics chip. The original supported Macs only through Docker. |
| Alignment | New imageAligner App | Corrects small plate shifts between timelapse photos using printed markers, before anything is measured. A frame without a detectable marker is flagged instead of stopping the run. |
| Measurements | Fewer Silent Measurement Errors | Hypocotyls are no longer borrowed from neighboring plants or zeroed before the root is found, and growth charts now work at any photo interval. |

Link below the entries: "Read all improvements &rarr;" -> `/docs/model-and-improvements.html`.

### 3.4 Documentation index (`#docs`)
Section head: "Documentation". Each card is a whole-card link.

| Card title | Description | Target |
|---|---|---|
| Installation Guide | Step-by-step setup for Windows via WSL, including the WSL1-vs-WSL2 GUI gotcha. | `/docs/install.html` |
| What's New in This Fork | A plain-language rundown of what the plant-recognition model can do now, and how the pipeline got more reliable. | `/docs/model-and-improvements.html` |
| Training the Model | Dataset prep, splits, VM training, and checkpoint handling for the segmentation model. | `/docs/training.html` |
| Architecture Notes | Seed position vs. root base, class labels, path structure, and how main/lateral classification actually works. | `/docs/architecture.html` |
| Full Changelog | The dated history of bug fixes applied to the analysis pipeline. | `/changelog.html` |

Observations: the Installation Guide card only mentions Windows/WSL although the page also covers Linux and macOS. "What's New" content appears in three places (landing section, nav link, docs card). Terminology varies: "Model Site" / "Dataset Site" vs. "Install guide".

## 4. Images

| File | Size | Used on | Alt text | Caption |
|---|---|---|---|---|
| `assets/img/segmentation-old-model.jpg` | 1180x1152 JPEG | What's New (`.compare`) | Old model segmentation of an Arabidopsis plate: several hypocotyls are partly labeled as leaf or left unlabeled | Old Model |
| `assets/img/segmentation-new-model.jpg` | 1178x1166 JPEG | What's New (`.compare`) | New model segmentation of the same plate: hypocotyls are labeled continuously along their full length | New Model |
| `assets/img/hypocotyl-neighbor-before.png` | 235x213 PNG | What's New (`.compare.wide`) | Before the fix: the hypocotyl measurement (yellow) is drawn on the neighboring plant to the right, while the tracked plant's own root is shown in red | Before |
| `assets/img/hypocotyl-neighbor-after.png` | 235x213 PNG | What's New (`.compare.wide`) | After the fix: the hypocotyl measurement (yellow) sits on the tracked plant itself, directly above its red root | After |

Notes: all four are lazy-loaded and displayed as side-by-side before/after pairs. The neighbor images are small (235 px wide) and will look soft if enlarged. There is no logo, favicon, hero photo or screenshot of the apps. The only non-photo graphic is the hero SVG chart.

## 5. Links

### 5.1 External
| URL | Where |
|---|---|
| https://github.com/calvinyong1/ArabidopsisAnalysisV2 | header nav, footer (all pages) |
| https://huggingface.co/calvinyong1/arabidopsis-segmentation-model | landing CTA "Model Site"; training.md ("Model Weights") |
| https://huggingface.co/datasets/calvinyong1/ArabidopsisDataset | landing CTA "Dataset Site"; training.md Step 1 |
| https://huggingface.co/datasets/ngaggion/ChronoRoot2 | training.md Step 1 (upstream dataset) |
| https://github.com/calvinyong1/ArabidopsisAnalysisV2.git | install.md Step 4 (clone command) |
| https://www.nvidia.com/Download/index.aspx | install.md (Windows NVIDIA driver) |
| https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh | install.md (WSL Miniconda) |
| https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-$(uname ... | install.md (macOS Miniconda, in a shell command) |
| https://brew.sh | install.md (Homebrew) |
| https://pytorch.org/get-started/locally/ | training.md Step 7 |
| https://download.pytorch.org/whl/cu124 | training.md Step 7 (pip index URL in a command) |
| https://fonts.googleapis.com/... | all pages (IBM Plex) |

### 5.2 Internal
| From | Link text | To |
|---|---|---|
| Doc pages | "&larr; All docs" | `/#docs` |
| What's New | "training page" | `training.html` |
| What's New | "architecture notes" | `architecture.html` |
| What's New | "install guide" | `install.html#macos-installation` |
| What's New | "changelog" | `../changelog.html` |
| training.md | "Step 1", "Full retrain from scratch", "Preprocessing gotcha" | in-page anchors |
| training.md | "On this page" TOC | generated by kramdown from h2s |

Note: `docs/README.md` and the top-level `docs/CLAUDE.md` are not published.

## 6. Page structure (heading outlines)

### Install Guide (`docs/install.md`)

Three OS groups as h1s (Windows, Linux, macOS), each with Prerequisites -> Installation -> Troubleshooting. Steps are numbered `### N.` and become number badges via `docs.js`. Heavy on fenced shell blocks.

```
- Install Guide
  - Before You Start
- Windows Installation
  - Prerequisites
    - 1. Install WSL2 + Ubuntu (on Windows)
    - 2. NVIDIA GPU Users: Driver Setup (Windows Side, Not Inside WSL)
    - 3. Install Miniconda Inside WSL
  - Installation
    - 4. Clone the Repository
    - 5. Run the WSL Installer
    - 6. Launch the App
  - Windows Troubleshooting
  - A Known WSL Gotcha
  - System Dependencies (Windows/WSL and Linux Only)
  - GPU Verification
- Linux Installation
  - Prerequisites
    - 1. Confirm `git` Is Installed
    - 2. NVIDIA GPU Users: Driver Setup
    - 3. Install Miniconda
  - Installation
    - 4. Clone the Repository
    - 5. Run the Linux Installer
    - 6. Launch the App
  - Linux Troubleshooting
- macOS Installation
  - Prerequisites
    - 1. Install Xcode Command Line Tools
    - 2. Install Miniconda (Optional)
    - 3. GPU Acceleration: What to Expect
  - Installation
    - 4. Clone the Repository: To Where You Want It to Live
    - 5. Run the macOS Installer
    - 6. Launch the App
  - macOS Troubleshooting
  - Updating the Application
```

### What's New in This Fork (`docs/model-and-improvements.md`)

Prose plus bullet lists; two `.compare` image pairs.

```
- What's New in This Fork
  - Smarter and More Accurate Plant-Recognition Model
  - Native MacOS Support
  - More Reliable Overall Pipeline
    - New: Automatic Image Alignment
    - Fewer Silent Mistakes in the Measurements
  - Known Issues Still Being Worked On
```

### Fine-tuning nnU-Net (`docs/training.md`)

Has an inline `On this page` TOC block (`<nav class="toc">`), tables (class labels, file names, annotation controls), many code blocks, and `Step N:` headings that become number badges.

```
- Fine-tuning the Arabidopsis Segmentation Model
  - Class Labels
  - Prerequisites
  - Overview: What Has to Happen Before Training
    - 1. Format Conversion & Aggregation
    - 2. `dataset.json`
    - 3. Data Splitting
  - Step 1: Download the Training Dataset
  - Step 2: Identify Failure Frames
  - Step 3: Correct Labels in ITK-SNAP
    - Annotation Controls & Tips
    - The "Paint Over" Rule
  - Step 4: Organize New Cases for nnUNet
  - Step 5: Merge Correction Cases into `splits_final.json`
    - Merge the New Cases into Fold 0
    - Re-upload the Merged File
    - Variations
  - Step 6: Transfer Files to the VM
  - Step 7: Set Up nnUNetv2 on the VM
  - Step 8: Preprocess New Cases
  - Step 9: Fine-tune Fold 0
  - Step 10: Replace the Model Checkpoint
  - Alternative: Full Retrain from Scratch
    - Prepare dataset.json
    - Generate splits_final.json (Grouped by Video)
    - Plan, Preprocess, and Train
    - Use the Ensemble at Inference
  - FAQ
  - nnU-Net Gotchas
    - Preprocessing Doesn't Populate gt_segmentations
    - Splits Are Read Once
    - Checkpoints Are Infrequent
    - Small Correction Batches Get Diluted
    - Device Fallback
    - Model Weights
```

### Architecture Notes (`docs/architecture.md`)

Short reference page: one table, one code block.

```
- Architecture Notes
  - `fixed_seed_position` vs. `current_root_base`
  - Main / Lateral Classification Is Topology-Based, Not Per-Pixel
  - `SegMulti` Images Are Visualizations, Not Raw Masks
  - Class Labels (`dataset.json`)
  - Case Naming
  - What's Different from Upstream ChronoRoot2
```

### Changelog (`changelog.md`)

Dated h2s (`YYYY-MM-DD: ...`) that `docs.js` turns into date tags, then a `Still Open` list.

```
- Changelog
  - 2026-09-03: `analysis/imageUtils/seg.py`
  - 2026-08-24: Environment Pinning, `3_generateReport.py`
  - 2026-08-19: `analysis/dataWork.py`
  - 2026-08-19: `analysis/plantAnalysis.py`, `analysis/graphUtils/save.py`
  - 2026-08-19: `analysis/imageUtils/seg.py`
  - 2026-06-12: Path Structure Across `fileUtilities.py`, `run.py`, `2_postprocess.py`, `3_generateReport.py`
  - 2026-05-19: Image Discovery
  - 2026-04-16: `singlePlantAnalysis/run.py`
  - Still Open
```

### Landing page (`index.html`)
```
header (brand, nav, scroll-progress)
hero
  - h1, lede, meta line, 3 CTAs
  - chart panel (SVG)
section#apps        - section-head + 3 app cards
section#whats-new   - section-head + 4 entries + link
section#docs        - section-head + 5 doc cards
footer
```

## 7. Behaviors that depend on content

- `landing.js`: fade-up reveal on `.section-head`, `.app-card`, `.entry`, `.back-link`, `.doc-card`; header progress line; marks the current nav link. No-ops with reduced motion or no JS.
- `docs.js` pattern-matches heading text: `Step N:` and `N.` become number badges, `YYYY-MM-DD:` in h2 becomes a date tag, and h1/h2 with ids build the "On this page" rail (needs 3 or more items). Renaming headings can silently disable these.
- Install page groups the rail by OS because its h1s are the OS names.
- `training.md` hand-writes its own TOC with kramdown `{:toc}`.

## 8. Current visual language (for reference)

Tokens in `assets/css/style.css`: ink `#1f2320`, ink-soft `#5d6660`, paper `#ffffff`, paper-raised `#eef3ef`, paper-line `#dbe4dd`, moss `#4a6b57`, moss-dark `#36513f`, root `#2f4a3a`, root-soft `#9dbfa8`; IBM Plex Mono and Sans; content width 920px; body 17px/1.55. Sage-green on white, dark-green header with white nav text.

## 9. Content issues noticed while collecting

- Install Guide card on the landing page only mentions Windows/WSL.
- `model-and-improvements.md` intro grammar: "all the changes that has been made"; "installed and ran natively"; stray spaces before commas ("long hypocotyls\n  , which").
- "What's New" naming is used for both the full page and the landing section, with the landing section being a 4-item summary.
- Mixed capitalization: "MacOS" (page headings) vs "macOS" (landing, install).
- `changelog.md` says it mirrors `CHANGES.md` and must be kept in sync by hand.
- Landing hero meta shows repo names in code style but doesn't link them.
- The two HF buttons ("Model Site", "Dataset Site") are both styled `primary`, with "Model Site" `ghost`: the primary/ghost pattern is inconsistent.
- Hero chart is illustrative only, with no real data.
- No favicon, no social/OG meta, no logo.

---

## Appendix A. Full text of each page (verbatim source)

Front matter removed. Markdown/Liquid as written.

### A.What's New in This Fork

Source: `docs/model-and-improvements.md`

~~~~markdown
# What's New in This Fork

This page explains all the changes that has been made since forking from the original ChronoRoot repository

## Smarter and More Accurate Plant-Recognition Model

Every measurement this tool produces (root length, hypocotyl length, number
of side roots) starts from the software correctly telling apart the
different parts of the plant in a photo. That's the job of the segmentation
model, and it's the piece that's changed the most.

- **Better segmentations of various phenotypes**, especially seedlings with
  elongated hypocotyls. The original model often mislabeled long hypocotyls
  , which cut the hypocotyl short and threw off its length measurement.
   The new model segments these hypocotyls correctly.
   
- **Maintained specifically for Arabidopsis by this project**, with its own
  copy of the model weights, kept separate from the original project's.
  Support for other plant species (like tomato) still comes from the
  original project, so nothing was lost by branching off.

<div class="compare">
  <figure>
    <img src="{{ '/assets/img/segmentation-old-model.jpg' | relative_url }}" alt="Old model segmentation of an Arabidopsis plate: several hypocotyls are partly labeled as leaf or left unlabeled" loading="lazy">
    <figcaption>Old Model</figcaption>
  </figure>
  <figure>
    <img src="{{ '/assets/img/segmentation-new-model.jpg' | relative_url }}" alt="New model segmentation of the same plate: hypocotyls are labeled continuously along their full length" loading="lazy">
    <figcaption>New Model</figcaption>
  </figure>
</div>

More detail on how the model gets retrained is on the
[training page](training.html); the technical class-label reference lives
on the [architecture notes](architecture.html) page.

## Native MacOS Support

This project can now be installed and ran natively on MacOS machines

- **One installer does the whole setup.** Running `installer_conda_mac.sh`
  installs the Python environment the apps need (including Miniconda, if
  it isn't already there), the QR-code library, and the segmentation model.
- **Real Mac apps to click on.** The installer puts ChronoRoot Analysis,
  ChronoRoot Segmentation and ChronoRoot Image Aligner in your
  Applications folder, with shortcuts on your Desktop. There's no terminal
  needed day to day.
- **Faster segmentation on Apple Silicon.** On newer Macs (M1, M2, M3 and
  later), segmentation runs on the Mac's graphics chip instead of only the
  processor. Older Intel Macs still work, running on the processor.
- **Updating is one step.** Re-running the installer offers to download the
  latest version first, then brings everything else up to date to match.

Step-by-step instructions are in the [install guide](install.html#macos-installation).

## More Reliable Overall Pipeline

### New: Automatic Image Alignment

This project now ships an **imageAligner** app that corrects potential camera
drift automatically before any measurement happens, using small printed
markers placed in view of the camera as reference points.

### Fewer Silent Mistakes in the Measurements

A number of bugs that produced wrong numbers, with no error message at all,
have been found and fixed:

- **A neighboring plant's hypocotyl could get measured by mistake.** If a
  plant's own hypocotyl wasn't visible yet, the software could grab a
  nearby plant's instead, since it just picked the biggest matching blob it
  could see. It now anchors on where *that specific plant's* seed was
  originally placed, so it can no longer borrow a neighbor's growth.

<div class="compare wide">
  <figure>
    <img src="{{ '/assets/img/hypocotyl-neighbor-before.png' | relative_url }}" alt="Before the fix: the hypocotyl measurement (yellow) is drawn on the neighboring plant to the right, while the tracked plant's own root is shown in red" loading="lazy">
    <figcaption>Before</figcaption>
  </figure>
  <figure>
    <img src="{{ '/assets/img/hypocotyl-neighbor-after.png' | relative_url }}" alt="After the fix: the hypocotyl measurement (yellow) sits on the tracked plant itself, directly above its red root" loading="lazy">
    <figcaption>After</figcaption>
  </figure>
</div>

- **Hypocotyl length no longer gets wiped to zero early in an experiment.**
  Hypocotyl growth is measured independently of the root, but a bug caused
  it to be reported as `0` on any frame where the root hadn't been
  successfully detected yet, even though the real hypocotyl measurement was
  sitting right there. That data is no longer thrown away.
- **Growth charts no longer come out empty or cut short** for experiments
  that don't photograph every 15 minutes. The chart-building step assumed a
  fixed 15-minute interval between photos; any other interval (say, every 3
  hours) used to produce truncated or blank charts. It now adapts to
  whatever interval was actually used.
- **Growth curves no longer flatten out artificially at the end.** A
  smoothing step used to fabricate zero-valued data past the edge of the
  real measurements, which dragged down and flattened the last few points
  of every curve. The smoothing now stops at the real edge of the data
  instead of padding past it.
- **`.tif`/`.tiff` photos are recognized.** Experiments captured in those
  formats used to be silently skipped entirely, because the software only
  looked for `.png` files.
- **A crash on fresh installs during report generation was fixed.** A
  dependency update elsewhere had started breaking report generation for
  everyone, right after installation. This is now pinned to a working
  version.
- **Output folders are simpler.** An unused extra folder level (left over
  from a multi-camera-rig setup this project doesn't use) was removed from
  where results get saved.

The full dated list of every fix is on the [changelog](../changelog.html)
page.

## Known Issues Still Being Worked On

Nothing hides bugs here. These are known and tracked openly:

- Very small, newly-emerged roots or hypocotyls can occasionally disappear
  from a few frames of measurement before they've grown large enough to be
  reliably tracked. It usually self-corrects as the structure gets bigger.
- A step meant to clean up false-positive short roots detected right at the
  start of an experiment can, in rare cases, mistakenly wipe out real
  earlier measurements later in the same timelapse too. This is suspected
  but not yet confirmed as a cause of some "root length not calculated"
  reports.
~~~~

### A.Architecture Notes

Source: `docs/architecture.md`

~~~~markdown
# Architecture Notes

Things worth knowing before changing the analysis pipeline.

## `fixed_seed_position` vs. `current_root_base`

Both start as copies of the same manually-configured seed position.

- **`fixed_seed_position`** never changes for the rest of analysis.
- **`current_root_base`** gets reassigned every successfully-tracked frame,
  so it can drift over time.

Root component selection anchors on `current_root_base` (it should track
legitimate drift). Hypocotyl selection anchors on `fixed_seed_position`, so
it stays independent of any root-tracking mistakes and consistent
frame-to-frame.

## Main / Lateral Classification Is Topology-Based, Not Per-Pixel

`graphInit()` marks the longest weighted path from the seed as `root_type=10`
(main); everything else defaults to lateral. The skeleton is built from a
merged binary mask (classes 1+2 combined) before any per-pixel class
matters, so per-pixel main/lateral mislabeling in the segmentation mask
does **not** corrupt `MainRootLength` / `LateralRootsLength`. It only affects
the `SegMulti` visualization coloring used for human QC.

## `SegMulti` Images Are Visualizations, Not Raw Masks

BGR color key:

| Class | Color (BGR) | Grayscale value |
|---|---|---|
| Main root | `(0,0,255)` red | 76 |
| Lateral root | `(0,255,0)` green | 150 |
| Hypocotyl | `(0,255,255)` yellow | 179 |
| FTip marker | `(255,255,0)` cyan | 226 |

The real multi-class mask (pixel values 0&ndash;7) lives at the path in each
plant's `metadata.json` under the `SegPath` key, e.g.
`<video>/Segmentation/Ensemble/`.

## Class Labels (`dataset.json`)

```
0 = background
1 = main root
2 = lateral root
3 = seed
4 = hypocotyl   (spelled "hypocotil": typo, preserved for compatibility)
5 = leaf
6 = petiole
7 = ignore
```

## Case Naming

The live dataset and `corrected_to_nnunet_cases.py` /
`CreateArabidopsisDataset.ipynb` use `image_N`, not `CaseN`. If you see
`CaseN` anywhere, it's stale; reconcile it.

## What's Different from Upstream ChronoRoot2

- `chronoRootApp` (upstream name) was renamed to `singlePlantAnalysis` here.
- `imageAligner` exists only in this fork, not upstream.
- Upstream has a `chronoRootScreeningApp`; this fork does not.
~~~~

### A.Changelog

Source: `changelog.md`

~~~~markdown
# Changelog

Dated log of fixes applied to the analysis pipeline
(`singlePlantAnalysis/analysis/`). This page mirrors `CHANGES.md`. Keep
them in sync, or replace this content with an `include` of the real file.

## 2026-09-03: `analysis/imageUtils/seg.py`

**Hypocotyl component selection no longer borrows a neighbor's blob.**
Added a hard horizontal-distance gate (`max_horizontal_distance=80`) to
hypocotyl anchor selection. Previously, if a plant had no hypocotyl blob yet,
the nearest *available* component (even a distant neighbor's) was accepted
regardless of distance. Horizontal-only distance was chosen over Euclidean
because plants are plated in a row and a hypocotyl grows vertically: `80` is
half the ~170px minimum seed spacing, minus a margin for blob width.

## 2026-08-24: Environment Pinning, `3_generateReport.py`

**Report generation no longer crashes on fresh installs.** An unpinned
transitive dependency (`multimethod`) shipped a change that broke
`scikit-fda`'s operator registration with a metaclass-conflict error at
import time, taking down report generation entirely, even for configs with
FPCA disabled. Fixed by pinning `multimethod<2.0.2` and making the FPCA
import lazy and failure-tolerant.

## 2026-08-19: `analysis/dataWork.py`

**Growth charts respect the real capture interval.** The hourly
reconciliation formula assumed a fixed 15-minute interval; generalized to
`(N_exp - 1) * timeStep // 60 + 1`.

**Fixed a `medfilt` zero-padding artifact.** `scipy.signal.medfilt` implicitly
zero-pads past the array boundary, flattening the last few points of every
growth curve. Replaced with a centered rolling median that shrinks its
window near the edges instead of padding with fabricated data.

## 2026-08-19: `analysis/plantAnalysis.py`, `analysis/graphUtils/save.py`

**`HypocotylLength` no longer zeroed before root detection.** Hypocotyl
length is computed independently of root graph success, but every
early-return path in the "find first valid root structure" loop hardcoded
`saveProps(..., 0, 0)`, discarding the already-computed value. The real value
now survives all four early-return paths.

## 2026-08-19: `analysis/imageUtils/seg.py`

**Hypocotyl selection anchored on seed position instead of largest blob.**
Component selection previously picked whichever class-4 blob had the largest
pixel area, with no awareness of which plant it belonged to: a diagonally
grown root could widen the ROI enough to catch a neighbor's larger hypocotyl.
Selection now scores candidates by proximity to `fixed_seed_position`,
mirroring the pattern already used for root component selection.

## 2026-06-12: Path Structure Across `fileUtilities.py`, `run.py`, `2_postprocess.py`, `3_generateReport.py`

**Dropped a hardcoded multi-Raspberry-Pi path segment** that didn't match
the pipeline's actual single-rig capture setup. Output paths are now
`Analysis/{experiment}/{cam}/{plant}/...` instead of carrying an extra `rpi`
level.

**Missing ArUco marker on a plate's reference frame no longer blocks the
whole plate.** Alignment failure on the reference frame now falls back to
copying raw images through unaligned, so segmentation can still proceed;
the segmentation queue UI gained `Not Aligned` / `Partially Aligned` states.

## 2026-05-19: Image Discovery

**`.tif` / `.tiff` experiments are no longer silently dropped.** Image
discovery was hardcoded to `*.png` only. Added `loadImageFiles()`, which
globs `.png`, `.tif`, and `.tiff` together.

## 2026-04-16: `singlePlantAnalysis/run.py`

**Blank plate/camera/plant/experiment fields no longer corrupt output
paths.** Fields default to `"1"` when blank, with `editingFinished` handlers
so a blank field self-corrects as soon as focus leaves it.

---

## Still Open

- `prune()`'s skeleton erosion has no length-awareness: a structure shorter
  than roughly `2 x num_it` can be fully consumed before it regrows.
- The "remove spurious lateral roots at the beginning" logic in
  `dataWork.py` isn't actually scoped to the beginning; it runs across the
  entire sequence.
- `PostProcess_Hour.csv` has `NaN` in 2 of every 3 hourly rows whenever the
  capture interval doesn't divide 60 minutes evenly.
~~~~

### A.Install Guide

Source: `docs/install.md`

~~~~markdown
# Install Guide

This walks through getting this system running from a clean machine through
to launching the apps. Pick the section for your OS below.

## Before You Start

ArabidopsisAnalysisV2 ships three GUI apps (`imageAligner`, `segmentationApp`,
and `singlePlantAnalysis`), each with its own `run.py`. The installer scripts
(`installer_conda_{wsl,linux,mac}.sh`) set up a conda environment; how they
handle the repo itself differs by platform (see each section below).

---

# Windows Installation

Uses `installer_conda_wsl.sh`, which sets up a Linux (Ubuntu) environment
inside Windows via WSL2, installs the conda environment and dependencies, and
creates native Windows shortcuts that launch the GUI apps.

## Prerequisites

### 1. Install WSL2 + Ubuntu (on Windows)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

This installs WSL2 with Ubuntu as the default distro and enables WSLg (the
GUI subsystem that lets Linux apps display windows directly on your Windows
desktop, required for this project's PyQt5-based GUIs). Reboot if prompted.

If WSL is already installed but you don't have a distro yet:

```powershell
wsl --install -d Ubuntu
```

After install, launch "Ubuntu" from the Start Menu once to finish setup and
create your Linux username/password.

**Windows version note:** WSLg ships by default on Windows 11 and on
sufficiently updated Windows 10 (via Windows Update / `wsl --update`). If
GUI windows fail to appear later, run `wsl --update` from PowerShell first.

### 2. NVIDIA GPU Users: Driver Setup (Windows Side, Not Inside WSL)

If you have an NVIDIA GPU and want segmentation to run on it (the "Full
Node" option below), install the **Windows** NVIDIA driver only:

- https://www.nvidia.com/Download/index.aspx

**Do not** install a separate NVIDIA Linux driver inside WSL. WSL2 GPU
passthrough uses the Windows host driver directly via a compatibility
shim. Installing a Linux driver inside WSL on top of it will break GPU
access, not fix it.

Once the Windows driver is installed, verify it's visible from inside WSL
(after Step 1):

```bash
nvidia-smi
```

If this prints your GPU info, passthrough is working. If it's not found,
update the Windows driver and re-check before continuing; don't try to
"fix" it from inside WSL.

If you don't have a GPU, skip this; you can still install a CPU-only
("Lite Node") setup for analysis-only workflows.

### 3. Install Miniconda Inside WSL

Open your **Ubuntu (WSL)** terminal and run:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/etc/profile.d/conda.sh
conda init bash
```

Close and reopen your WSL terminal (or run `source ~/.bashrc`) so `conda` is
available on your `PATH`. The installer script requires `conda` to already be
present; it will not install it for you.

`git` normally ships with Ubuntu's WSL image already; if `git --version`
fails, install it with `sudo apt-get install -y git`.

## Installation

### 4. Clone the Repository

```bash
git clone https://github.com/calvinyong1/ArabidopsisAnalysisV2.git
cd ArabidopsisAnalysisV2
```

### 5. Run the WSL Installer

```bash
bash installer_conda_wsl.sh
```

The script will:

1. **Verify you're in WSL** and that `conda` is available.
2. **Detect your GPU** via `nvidia-smi` (informational at this stage).
3. **Install `libzbar0`** via `sudo apt-get` (needed for QR code support);
   you'll be prompted for your Linux password.
4. **Ask for an install directory** (default: `~/.local/chronoroot`). This is
   where the *deployed* copy of the app lives going forward, separate from
   the repo you just cloned in Step 4, which is only needed to obtain and run
   this installer script. It's safe to delete the Step 4 clone afterward.
5. **Clone/update the repo again** into that install directory (this is the
   copy the shortcuts will actually launch and that `git pull` will update on
   re-runs).
6. **Ask you to choose an installation type:**
   - **Full Node**: segmentation + analysis. Requires a GPU (you can
     proceed without one, but segmentation will be very slow on CPU).
   - **Lite Node**: analysis only, no segmentation model. Works on any
     laptop. You'll be separately asked whether to also install the
     Segmentation GUI in monitoring-only mode (useful if segmentation runs
     elsewhere, e.g. a shared server, and you just want to watch progress).
7. **Create the `ChronoRoot` conda environment** from the appropriate
   `environment.yml` / `environment_no_nnunet.yml`.
8. **Verify the GPU is actually usable by PyTorch** (Full Node only). This
   is a real check (`torch.cuda.is_available()`), not just the earlier
   `nvidia-smi` detection. If it fails here, revisit Step 2 before continuing,
   otherwise segmentation will otherwise silently fall back to CPU.
9. **Download the segmentation model weights** (Full Node only), which pulls your
   fine-tuned Arabidopsis model and syncs any other available models.
10. **Create Windows shortcuts** on your Desktop and in the Start Menu for
    each installed app (ChronoRoot Analysis, ChronoRoot Image Aligner, and
    ChronoRoot Segmentation if selected). This step calls out to
    `cmd.exe`/`powershell.exe` from within WSL, which requires WSL/Windows
    interop, which is enabled by default and normally needs no action from
    you.

### 6. Launch the App

Use the new shortcuts on your Desktop or Start Menu. The first launch may
take a few seconds longer while the conda environment activates.

## Windows Troubleshooting

- **"This script must be run inside WSL."**: you're running it from a
  native Windows shell (PowerShell/cmd), not a WSL terminal. Open "Ubuntu"
  from the Start Menu and run it from there.
- **`sudo apt-get install -y libzbar0` fails**: the installer assumes an
  Ubuntu/Debian-based WSL distro (uses `apt-get`). If you installed a
  different distro, install the equivalent `zbar` package manually with that
  distro's package manager first.
- **GUI windows never appear**: run `wsl --update` from PowerShell on the
  Windows side, then restart WSL (`wsl --shutdown` from PowerShell, then
  reopen your Linux terminal) and try again.
- **`torch.cuda.is_available()` check fails despite `nvidia-smi` working
  earlier**: this means a GPU is visible to WSL but the installed PyTorch
  build can't use it, usually a driver/CUDA version mismatch. Confirm the
  Windows NVIDIA driver is fully up to date (Step 2) and re-run the
  installer; it's safe to re-run (it updates the existing conda environment
  and repo rather than starting over).
- **Shortcuts weren't created / step 10 seemed to silently fail**: this
  relies on WSL-Windows interop (`cmd.exe`/`powershell.exe` callable from
  WSL) being enabled, which is the default. If you or your organization has
  disabled it, shortcut generation won't work; you can still launch the apps
  manually from inside WSL by running `python run.py` from
  `~/.local/chronoroot/ChronoRoot2/<appFolder>` with the `ChronoRoot` conda
  environment active.

## A Known WSL Gotcha

If `$DISPLAY` is completely empty inside WSL despite everything else
installing correctly, check `wsl --list --verbose` on the **Windows** side.
The distro may be running as WSL1, which has no GUI/WSLg support and never
populates `$DISPLAY`.

**Fix**, from PowerShell:

```powershell
wsl --set-version <DistroName> 2
wsl --shutdown
```

Then reopen your WSL terminal.

## System Dependencies (Windows/WSL and Linux Only)

The WSL and Linux installers set up Qt/X11 libraries (`libxcb-cursor0` and
friends). If you're on a fresh or minimal WSL/Linux image and see
`"no Qt platform plugin could be initialized"`, this step is what fixes it.
macOS uses Qt's native Cocoa backend and doesn't need this.

## GPU Verification

After install, the script checks `torch.cuda.is_available()` to confirm the
right `torch` build was actually installed, not just that `nvidia-smi`
reports a driver.

---

# Linux Installation

Uses `installer_conda_linux.sh`. Like the Windows/WSL installer (and unlike
the macOS one), this script clones the repo into its own **separate install
directory** rather than deploying from wherever you run it, so the clone
you make to obtain the script is not the copy that ends up running long
term.

## Prerequisites

### 1. Confirm `git` Is Installed

Most distros ship this already:

```bash
git --version
```

If it's missing, install it with your distro's package manager, e.g.
`sudo apt-get install -y git` (Debian/Ubuntu), `sudo dnf install -y git`
(Fedora), or `sudo pacman -S git` (Arch).

### 2. NVIDIA GPU Users: Driver Setup

If you have an NVIDIA GPU and want segmentation to run on it (the "Full
Node" option below), install the proprietary NVIDIA driver through your
distro's package manager or driver installer (e.g. Ubuntu's
"Additional Drivers" tool, or `sudo apt-get install nvidia-driver-<version>`)
rather than compiling from NVIDIA's site unless you have a reason to.

Verify it's working before continuing:

```bash
nvidia-smi
```

If this doesn't print your GPU info, resolve the driver install first;
otherwise segmentation will otherwise silently fall back to CPU.

If you don't have a GPU, skip this; a CPU-only ("Lite Node") setup works
fine for analysis-only workflows.

### 3. Install Miniconda

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/etc/profile.d/conda.sh
conda init bash    # or: conda init zsh, depending on your shell
```

Close and reopen your terminal (or `source ~/.bashrc`) so `conda` is on your
`PATH`. The installer script requires `conda` to already be present.

## Installation

### 4. Clone the Repository

```bash
git clone https://github.com/calvinyong1/ArabidopsisAnalysisV2.git
cd ArabidopsisAnalysisV2
```

This clone is only needed to obtain and run the installer script; it's
safe to delete afterward, same as on Windows/WSL.

### 5. Run the Linux Installer

```bash
bash installer_conda_linux.sh
```

The script will:

1. **Verify `conda` is available.**
2. **Detect your GPU** via `nvidia-smi` (informational at this stage).
3. **Install system dependencies**: `libzbar0` (QR code support) and the
   Qt/X11 libraries (`libxcb-cursor0` and friends) needed for the PyQt5
   GUIs, via `apt-get`. This assumes a Debian/Ubuntu-based distro; see
   Troubleshooting below if you're on something else.
4. **Ask for an install directory** (default: `~/.local/chronoroot`),
   separate from the Step 4 clone, which this step re-clones from.
5. **Clone/update the repo** into that install directory. This is the copy
   that gets launched going forward and that `git pull` updates on re-runs.
6. **Ask you to choose an installation type:**
   - **Full Node**: segmentation + analysis. Requires a GPU (you can
     proceed without one, but segmentation will be very slow on CPU).
   - **Lite Node**: analysis only, no segmentation model, with the option
     to also install the Segmentation GUI in monitoring-only mode.
7. **Create the `ChronoRoot` conda environment** from the appropriate
   `environment.yml` / `environment_no_nnunet.yml`.
8. **Verify the GPU is actually usable by PyTorch** (Full Node only) via
   `torch.cuda.is_available()`, a real check, not just the earlier
   `nvidia-smi` detection.
9. **Download the segmentation model weights** (Full Node only).
10. **Create application launcher entries** (a `.desktop` file per installed
    app, if your desktop environment supports the XDG Desktop Entry spec)
    so the apps show up in your application menu.

### 6. Launch the App

Use the new entries in your application menu. If your desktop environment
doesn't pick up `.desktop` files automatically (or you're on a minimal
window manager), launch manually instead:

```bash
conda activate ChronoRoot
cd ~/.local/chronoroot/ChronoRoot2/<appFolder>   # singlePlantAnalysis / segmentationApp / imageAligner
python run.py
```

## Linux Troubleshooting

- **`apt-get: command not found` / package install step fails**: the
  installer assumes a Debian/Ubuntu-based distro. On Fedora/RHEL, install
  the equivalent packages manually first: `sudo dnf install zbar
  xcb-util-cursor` (package names may vary by release); on Arch:
  `sudo pacman -S zbar xcb-util-cursor`. Then re-run the installer; it
  should skip past the dependency step if it detects they're already
  present, or you can comment out that step if it doesn't.
- **`torch.cuda.is_available()` fails despite `nvidia-smi` working**:
  usually a CUDA/driver version mismatch between the installed driver and
  the PyTorch build. Confirm your driver is current and re-run the
  installer; it's safe to re-run (it updates the existing conda environment
  and repo rather than starting over).
- **No application menu entry appears**: some minimal or tiling window
  managers don't read `.desktop` files automatically. Use the manual launch
  command above, or add the generated `.desktop` file's directory to
  whatever launcher/menu tool your WM uses.
- **GUI windows fail to open at all**: confirm you're running this in a
  graphical session (not over a bare SSH connection without `-X`/`-Y`
  forwarding, and not from a TTY). For SSH usage, connect with
  `ssh -X user@host` or set up a proper remote desktop session instead.

---

# macOS Installation

Uses `installer_conda_mac.sh`. This behaves differently from the
Windows/Linux installers in one important way: it deploys **in place**, from
whatever local checkout you run it from (`$SCRIPT_DIR`); it does not clone
a separate copy into its own install directory the way `installer_conda_wsl.sh`
and `installer_conda_linux.sh` do. That means **where you clone the repo is
where the app will live**, so pick that location deliberately before you
start (e.g. `~/Applications/ArabidopsisAnalysisV2` or wherever you keep long-
lived local projects). You won't get a second, separate "install directory"
step later to move it.

## Prerequisites

### 1. Install Xcode Command Line Tools

```bash
xcode-select --install
```

This provides `git` and the compiler toolchain some conda packages need to
build. If `git --version` already works, you can skip this.

### 2. Install Miniconda (Optional)

The macOS installer installs Miniconda to `~/miniconda3` for you if `conda`
isn't found, so you can skip this step. To install it yourself instead:

```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-$(uname -m).sh
bash Miniconda3-latest-MacOSX-$(uname -m).sh -b -p $HOME/miniconda3
source $HOME/miniconda3/etc/profile.d/conda.sh
conda init zsh   # or: conda init bash, depending on your shell
```

`$(uname -m)` picks the right installer automatically: `arm64` on Apple
Silicon, `x86_64` on Intel Macs. Close and reopen your terminal (or `source
~/.zshrc`) so `conda` is on your `PATH`.

[Homebrew](https://brew.sh) is also recommended. The installer uses it to
install `zbar` for QR code reading, and offers to continue without QR
support if Homebrew is missing.

### 3. GPU Acceleration: What to Expect

There's no CUDA on macOS. Segmentation uses Apple's **MPS** backend
(`torch.backends.mps.is_available()`) automatically on **Apple Silicon**
(M1/M2/M3/M4). No separate driver install needed, it's built into the OS
and PyTorch. On an **Intel Mac**, there is no MPS path either, so
segmentation falls back to CPU and will be considerably slower. If you're on
an Intel Mac and plan to do heavy segmentation work, the "Lite Node" +
monitoring-only option below (or running segmentation on a separate machine
with an NVIDIA GPU) is worth considering.

## Installation

### 4. Clone the Repository: To Where You Want It to Live

```bash
git clone https://github.com/calvinyong1/ArabidopsisAnalysisV2.git
cd ArabidopsisAnalysisV2
```

Unlike the Windows/Linux flow, **do not delete this clone afterward**: this
is the copy the app will run from going forward, not a temporary staging
copy.

### 5. Run the macOS Installer

```bash
bash installer_conda_mac.sh
```

The script will:

1. **Offer to pull the latest changes** (`git pull --ff-only`) into this
   checkout, so the environment, model weights and app code all come from
   the current version. Answer `n` to install from the checkout as it is.
   If the pull updates the installer itself, it restarts with the new
   version automatically. The step is skipped when the folder isn't a git
   clone or the branch has no upstream.
2. **Detect Apple Silicon vs. Intel.**
3. **Find `conda`**, or install Miniconda to `~/miniconda3` if it's missing.
4. **Install `zbar`** via Homebrew (needed for QR code support).
5. **Create or update the `ChronoRoot` conda environment** from
   `environment.yml`. On a re-run it updates the existing environment with
   `conda env update --prune` rather than recreating it. There's no
   Full/Lite choice on macOS; every install includes segmentation.
6. **Download the segmentation model weights** from Hugging Face.
7. **Create app launchers** in `~/Applications` (ChronoRoot Analysis,
   ChronoRoot Segmentation, ChronoRoot Image Aligner), with shortcuts on
   your Desktop.

To skip the update prompt entirely, run `bash installer_conda_mac.sh --no-pull`.

### 6. Launch the App

Open the apps from `~/Applications` or from the shortcuts on your Desktop.
They run the code in your cloned repo directly, so they always reflect the
checkout's current state.

The launchers aren't signed, so macOS blocks them the first time. Right-click
the app, choose **Open**, then **Open** again; after that it launches
normally.

You can also launch from a terminal:

```bash
conda activate ChronoRoot
cd singlePlantAnalysis   # or segmentationApp / imageAligner
python run.py
```

## macOS Troubleshooting

- **`conda: command not found`**: your terminal hasn't picked up the
  Miniconda install. Run `source $HOME/miniconda3/etc/profile.d/conda.sh`,
  or reopen your terminal after Step 2.
- **Segmentation runs on CPU despite having Apple Silicon**: confirm with
  `python -c "import torch; print(torch.backends.mps.is_available())"`
  inside the `ChronoRoot` environment. If this prints `False`, your PyTorch
  build may predate MPS support or is a CPU-only build; reinstalling the
  environment via the installer (safe to re-run) should pull a compatible
  version.
- **App won't launch / import errors**: make sure you're running `python
  run.py` with `ChronoRoot` activated (`conda activate ChronoRoot`), from
  inside the correct app folder (`singlePlantAnalysis`, `segmentationApp`,
  or `imageAligner`), not from the repo root.
- **"git pull failed" during the update step**: usually uncommitted local
  edits to tracked files, or a branch that has diverged from GitHub. Run
  `git status` in the repo folder, then commit, stash (`git stash`) or
  discard the changes and re-run. You can also answer `y` to continue
  installing from the current checkout without updating.
- **You cloned to the "wrong" place**: since the installer deploys in
  place, moving the app means moving the whole cloned folder and re-running
  `installer_conda_mac.sh` from its new location. The app launchers store
  the repo's path, so they point at the old location until you do.

---

## Updating the Application

- **Windows/Linux:** re-run `installer_conda_wsl.sh` / `installer_conda_linux.sh`
  any time. It detects the existing clone in your install directory and runs
  `git pull` instead of cloning fresh, and updates (rather than recreates)
  the existing `ChronoRoot` conda environment.
- **macOS:** re-run `bash installer_conda_mac.sh` from your clone and answer
  `y` at the update prompt. It pulls the latest changes into that same
  folder, then updates the `ChronoRoot` conda environment and model weights
  to match.
~~~~

### A.Fine-tuning nnU-Net

Source: `docs/training.md`

~~~~markdown
# Fine-tuning the Arabidopsis Segmentation Model

This guide covers fine-tuning the existing Arabidopsis nnUNetv2 model to correct
specific misclassification issues, specifically hypocotyl pixels being labeled as
leaf (class 5) instead of hypocotyl (class 4).

<nav class="toc" markdown="1">
**On this page**

{::options toc_levels="2" /}
* TOC
{:toc}
</nav>

## Class Labels

| Class | Value | Color in viewer |
|-------|:-----:|-----------------|
| Background | 0 | Black |
| Main root | 1 | Red |
| Lateral root | 2 | Green |
| Seed | 3 | Blue |
| Hypocotyl | 4 | Yellow |
| Leaf | 5 | Purple |
| Petiole | 6 | Purple |
| Ignore | 7 | None |

`Ignore` (7) is nnUNet's ignore label. Paint it over pixels you want excluded from
the training loss (e.g. ambiguous/uncertain regions), rather than forcing them into
one of the real classes. It's already declared in `dataset.json`'s `labels` block
(`"ignore": 7`) for `Dataset789_ChronoRoot2`.

## Prerequisites

- nnUNetv2 installed and environment variables set (`nnUNet_raw`, `nnUNet_preprocessed`, `nnUNet_results`)
- ITK-SNAP installed for annotation
- The ChronoRoot Jupyter notebooks for dataset organization
- The training dataset downloaded from HuggingFace (see [Step 1](#step-1-download-the-training-dataset))

## Overview: What Has to Happen Before Training

Three things have to happen before any `nnUNetv2_train` command can run. This is
the high-level shape of it; the numbered steps below (and
[Full retrain from scratch](#alternative-full-retrain-from-scratch)) cover each
part in detail.

### 1. Format Conversion & Aggregation

Use `trainerOrganization/`'s notebooks (`CreateArabidopsisDataset.ipynb`,
`CreateTomatoDataset.ipynb`) or the standalone `build_base_dataset.py` script to
aggregate your expert-annotated Robot/Camera folders and rename them into
nnU-Net's case convention, then move them into `imagesTr` and `labelsTr`:

| File | Name pattern |
|---|---|
| Image | `{CASE_ID}_0000.png` |
| Mask | `{CASE_ID}.png` |

> Masks are `.png`, **not** `.nii.gz`: `dataset.json` declares
> `"file_ending": ".png"`. `.nii.gz` only appears transiently, as the format
> ITK-SNAP needs for manual mask editing (Step 3).

See Step 4 for adding incremental correction cases to an existing dataset, or
"Full retrain from scratch" for building one from a fresh download.

### 2. `dataset.json`

Must be prepared manually in `nnUNet_raw/DatasetXXX/`:

- **New dataset:** copy the matching template from `trainerOrganization/`
  (`dataset_Arabidopsis.json` or `dataset_Tomato.json`), rename it to
  `dataset.json`, and set `numTraining` to your actual case count.
- **Incremental fine-tuning (Step 4):** update `numTraining` in place on the
  dataset's existing `dataset.json`.

### 3. Data Splitting

To prevent the model from memorizing plate geometry instead of learning to
generalize, cases must be grouped so frames from the same video never end up
split across train and validation. The dataset-creation notebook does this by
grouping images by their source folder (video/category), forcing certain
folders (e.g. any tagged `MultipleVids`) into training, and generating a
`splits_final.json`.

> **This file must be manually copied** to
> `nnUNet_preprocessed/DatasetXXX/splits_final.json` before training starts.
> nnU-Net does not do this for you, and without it silently auto-generates its
> own random split instead (see Step 5 for why that's a problem when adding
> correction cases).

---

## Step 1: Download the Training Dataset

This fork's annotated Arabidopsis dataset is hosted on HuggingFace at
[huggingface.co/datasets/calvinyong1/ArabidopsisDataset](https://huggingface.co/datasets/calvinyong1/ArabidopsisDataset).
It builds on the original ChronoRoot2 annotations
([ngaggion/ChronoRoot2](https://huggingface.co/datasets/ngaggion/ChronoRoot2))
and already includes this project's correction cases, laid out in nnU-Net's
format. Download it so your new cases can be merged with the existing ones:

```bash
hf download calvinyong1/ArabidopsisDataset --repo-type dataset \
    --local-dir nnUNet_raw/Dataset789_ChronoRoot2
```

```text
nnUNet_raw/Dataset789_ChronoRoot2/
    imagesTr/                 ← grayscale input PNGs
    labelsTr/                 ← mask PNGs (pixel values = class IDs above)
    imagesTs/, labelsTs/      ← held-out test cases
    dataset.json
    splits_final.json         ← train/val assignment from the last training round
    folder_assignments.json, folder_image_map.json   ← case → source video mapping
```

The full download already includes `splits_final.json`; Step 5 explains how
it's used when fine-tuning.

## Step 2: Identify Failure Frames

You do not need to label every frame. Only select frames where the
misclassification is visible: frames where the hypocotyl appears purple
instead of yellow. A few frames per affected video is sufficient.

Use the plant viewer (Tab 3 in the main app, "View full sequence") with
segmentation toggled on to scrub through and identify these frames. Note the
frame filenames.

The existing segmentation masks (your silver standard) are already at:

```text
<video_folder>/Segmentation/Ensemble/
```

These pre-filled masks are your starting point for correction in ITK-SNAP; you
only need to repaint the wrong regions, not label the entire image from scratch.

Once you've picked the frames to annotate, set them up in a new folder:

1. Create a new folder and copy the selected frame images into it.
2. Inside that folder, create a `Segmentation/Ensemble/` subfolder.
3. Copy each frame's matching segmentation mask into `Segmentation/Ensemble/`.

The result should look like this:

```text
<annotation_folder>/
    frame_001.png
    frame_002.png
    ...
    Segmentation/
        Ensemble/
            frame_001.png
            frame_002.png
            ...
```

## Step 3: Correct Labels in ITK-SNAP

1. Convert the selected images to NIfTI (`.nii.gz`) using the Jupyter notebook
   `trainerOrganization/PredToNii.ipynb`.
2. Open the original image and its corresponding segmentation mask in ITK-SNAP.
3. Using the paintbrush tool, repaint the incorrectly labeled hypocotyl pixels
   from class `5` (leaf) to class `4` (hypocotyl).
4. Save the corrected mask in NIfTI format.

### Annotation Controls & Tips

| Action | How |
|---|---|
| Brush shape | Always use the **Round Brush** for natural plant structures |
| Navigate | Select the **Magnifying Glass** tool |
| Zoom | Hold **right-click** and drag |
| Pan | Hold **left-click** and drag |

### The "Paint Over" Rule

To fix a misclassification (e.g. changing a model-predicted main root to a
lateral root):

1. Select the correct **Active Label** (e.g. green / lateral root).
2. Set the tool to **Paint Over Label** mode.
3. In the **Over** dropdown, select the incorrect label (e.g. red / main root).

> This way you only repaint the pixels that need correcting, and don't paint
> into the background.

## Step 4: Organize New Cases for nnUNet

Use the ChronoRoot Jupyter notebooks (`trainerOrganization/`) to:

1. Convert corrected NIfTI masks back to PNG.
2. Name the new cases following nnUNet convention, continuing from the current
   dataset's highest existing case number:
   - Image: `image_948_0000.png`, `image_949_0000.png`, ...
   - Mask: `image_948.png`, `image_949.png`, ...
3. Copy the new files into `nnUNet_raw/Dataset789_ChronoRoot2/imagesTr/` and `labelsTr/`.
4. Update `numTraining` in `dataset.json` to reflect the new total.

**Case numbering.** Numbering is
**1-indexed and contiguous**: `numTraining: 947` means cases run
`image_1`–`image_947`, so the next new case is `image_948` (`numTraining + 1`).

> `corrected_to_nnunet_cases.py`'s `--start-case` default is stale, so always
> pass it explicitly.

## Step 5: Merge Correction Cases into `splits_final.json`

The original `splits_final.json` from the base training run (the file assigning
cases to train/val for each fold) is archived on HuggingFace alongside the
dataset. Download it instead of approximating one from scratch, so fold 0's
validation set matches the actual frames the base model was validated against
rather than a synthetic random slice:

```bash
hf download calvinyong1/ArabidopsisDataset splits_final.json --repo-type dataset \
    --local-dir nnUNet_raw/Dataset789_ChronoRoot2
```

> If this file is ever missing (e.g. a repo that predates it being archived),
> nnUNet falls back to auto-generating a random 5-fold split across **all**
> cases (old + new) the first time you preprocess, so your new correction
> cases could by chance land in fold 0's validation set instead of its training
> set, i.e. not actually influence the fine-tuned weights.

### Merge the New Cases into Fold 0

This workflow only ever trains fold 0 (Step 9), and `nnUNet_wrapper.py` only
ever loads fold 0 at inference, so you only need fold 0's entry from the
downloaded file, with your correction cases merged into its `train` list. The
other 4 folds can be dropped. Run this **locally**, next to your
`nnUNet_raw/Dataset789_ChronoRoot2` folder:

```bash
python3 -c "
import json, os

dataset_dir = 'nnUNet_raw/Dataset789_ChronoRoot2'   # has case_mapping.json + splits_final.json
out_path = 'splits_final.json'

case_mapping = json.load(open(os.path.join(dataset_dir, 'case_mapping.json')))
new_cases = sorted(case_mapping.keys(), key=lambda c: int(c.replace('image_', '')))

original_splits = json.load(open(os.path.join(dataset_dir, 'splits_final.json')))
fold_0 = original_splits[0]

train = sorted(set(fold_0['train']) | set(new_cases), key=lambda c: int(c.replace('image_', '')))
val = sorted(fold_0['val'], key=lambda c: int(c.replace('image_', '')))

# nnUNet indexes splits_final.json by fold number at the command line
# (fold 0 -> splits[0]). Only fold 0 is ever trained/loaded in this
# workflow, so a single-entry list is sufficient.
splits = [{'train': train, 'val': val}]

json.dump(splits, open(out_path, 'w'), indent=2)
"
```

This merge only matters if `case_mapping.json` (produced in Step 4) exists;
it's what identifies which case IDs are new corrections versus original base
cases. If you're not tracking that, you can skip it and use fold 0 of the
downloaded `splits_final.json` as-is, though then your correction cases won't
be trained on at all.

> Correction cases go entirely into training (none held out for validation), so
> fold 0's validation loss reflects generalization on the original base dataset
> only, not whether the correction itself generalizes. Verify the fix by
> visually inspecting predictions on held-out misclassification frames after
> training, rather than relying on the validation loss curve alone.

### Re-upload the Merged File

**Do this so the next round doesn't lose your corrections.** The archived
`splits_final.json` isn't a fixed artifact from the original base run; it's
whatever the most recent fine-tuning round uploaded, already containing *that*
round's corrections merged into `train`. If you don't push your merged copy
back, the next person to fine-tune downloads the version from *before* your
corrections, merges in only their own new cases, and yours silently drop out of
training entirely.

As soon as you've generated the merged file (no need to wait for training, since the
file doesn't change during training), upload it back:

```bash
hf upload calvinyong1/ArabidopsisDataset splits_final.json splits_final.json --repo-type dataset
```

### Variations

- **Hold out one correction video for validation.** Instead of forcing *all*
  new cases into training, hold out the new cases from one source video (e.g.
  all of "plate2"'s corrected frames) as fold 0's validation set, and force only
  the rest into training. Fold 0's validation Dice then reflects whether the
  correction generalizes, at the cost of that video's corrections not directly
  influencing the trained weights. Use `case_mapping.json` (case ID → source
  filename) to pick which cases belong to that video. In the script above,
  move them out of `new_cases` and into `val` instead of `train`.
- **Want the full 5-fold ensemble instead?** That's a different workflow; see
  [Full retrain from scratch](#alternative-full-retrain-from-scratch), which
  trains all 5 folds from scratch rather than warm-starting a single fold.

## Step 6: Transfer Files to the VM

Reuse the existing model's plans and fingerprint instead of letting nnUNet
regenerate them; otherwise nnUNet may pick a different network configuration
and the existing checkpoint's weights won't load into it.

**On the VM**, create the destination folders first (so `scp -r` nests the
copied folder correctly instead of renaming it):

```bash
mkdir -p ~/ChronoRoot/nnUNet_raw ~/ChronoRoot/nnUNet_preprocessed ~/ChronoRoot/nnUNet_results
```

**On your local machine** (a separate terminal, not the VM's SSH session), push
the files over:

```bash
scp -r nnUNet_raw/Dataset789_ChronoRoot2 <vm-user>@<vm-host>:~/ChronoRoot/nnUNet_raw/

scp -r nnUNet_preprocessed/Dataset789_ChronoRoot2 <vm-user>@<vm-host>:~/ChronoRoot/nnUNet_preprocessed/

scp segmentationApp/models/Arabidopsis/fold_0/checkpoint_final.pth \
    <vm-user>@<vm-host>:~/ChronoRoot/checkpoint_final.pth
```

Before transfer, `nnUNet_preprocessed/Dataset789_ChronoRoot2` should contain:

| File | Where it comes from |
|---|---|
| `dataset_fingerprint.json` | Copied from `segmentationApp/models/Arabidopsis/dataset_fingerprint.json` |
| `nnUNetResEncUNetMPlans.json` | Copied from `segmentationApp/models/Arabidopsis/plans.json`, **renamed** (matches the `plans_name` field inside the file) |
| `splits_final.json` | Generated in Step 5 |
| `dataset.json` | Copied from `nnUNet_raw/Dataset789_ChronoRoot2/dataset.json`. Normally `plan_and_preprocess` does this automatically, but this workflow skips it to reuse the existing plan |

## Step 7: Set Up nnUNetv2 on the VM

Run these **on the VM** (bash):

1. Confirm the GPU and note the CUDA version:

   ```bash
   nvidia-smi
   ```

2. Check whether conda/Python already exist (skip install if so):

   ```bash
   which conda
   which python3
   ```

3. Install Miniconda if needed:

   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
   bash ~/miniconda.sh -b -p $HOME/miniconda3
   source $HOME/miniconda3/etc/profile.d/conda.sh
   ```

4. Create the environment and install PyTorch + nnUNetv2. Swap `cu124` for
   whatever `nvidia-smi` reported, and pick the right build from
   [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/):

   ```bash
   source $HOME/miniconda3/etc/profile.d/conda.sh
   conda create -y -n ChronoRoot python=3.10
   conda activate ChronoRoot
   pip install torch --index-url https://download.pytorch.org/whl/cu124
   pip install nnunetv2
   ```

5. Verify the GPU is visible to PyTorch:

   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```

   Must print `True`. If `False`, the CUDA build doesn't match the driver;
   recheck `nvidia-smi` and reinstall torch with the right `cuXXX`.

6. Set the three environment variables, persisted and exported for the current
   session:

   ```bash
   cat >> ~/.bashrc << 'EOF'
   export nnUNet_raw=~/ChronoRoot/nnUNet_raw
   export nnUNet_preprocessed=~/ChronoRoot/nnUNet_preprocessed
   export nnUNet_results=~/ChronoRoot/nnUNet_results
   EOF
   source ~/.bashrc
   ```

7. Confirm the transferred files landed correctly:

   ```bash
   ls ~/ChronoRoot/nnUNet_raw/Dataset789_ChronoRoot2
   ls ~/ChronoRoot/nnUNet_preprocessed/Dataset789_ChronoRoot2
   ```

   The first should show `imagesTr`, `labelsTr`, `dataset.json`; the second
   should show `dataset_fingerprint.json`, `nnUNetResEncUNetMPlans.json`,
   `splits_final.json`.

## Step 8: Preprocess New Cases

Run **on the VM**. This prepares all cases (old + new) using the transferred
plans, rather than generating a new (potentially incompatible) configuration.

```bash
nnUNetv2_preprocess -d 789 -plans_name nnUNetResEncUNetMPlans -c 2d --verify_dataset_integrity
```

> `-plans_name` must be passed explicitly. It defaults to `nnUNetPlans`, but the
> transferred plans file is `nnUNetResEncUNetMPlans.json` (matching the original
> model's `plans_name`), so without this flag preprocessing fails with
> `FileNotFoundError: .../nnUNetPlans.json`.

After preprocessing, populate `gt_segmentations/` manually; see
[Preprocessing gotcha](#preprocessing-doesnt-populate-gt_segmentations) below.

## Step 9: Fine-tune Fold 0

Only fold 0 is needed because the inference code in `nnUNet_wrapper.py` loads
only fold 0.

Run **on the VM**, using `--pretrained_weights` to warm-start from the existing
final checkpoint. `-p` needs the same plans identifier as Step 8, for the same
reason:

```bash
nnUNetv2_train 789 2d 0 -p nnUNetResEncUNetMPlans -pretrained_weights ~/ChronoRoot/checkpoint_final.pth
```

Training will be much shorter than the original run since the model already has
a strong starting point. Monitor the validation loss and stop (`Ctrl+C`) once
it stabilizes.

> Only use `--c` if you're resuming a fine-tuning run that was itself
> interrupted mid-training (it looks for `checkpoint_latest.pth`). Don't use
> `--c` against the original `checkpoint_final.pth`: nnUNet treats a
> `checkpoint_final.pth` as "training already complete" and won't continue from
> it.

## Step 10: Replace the Model Checkpoint

`nnUNet_wrapper.py:71` hardcodes `checkpoint_name='checkpoint_final.pth'`, so the
inference code will only load a file with that exact name, regardless of how
training actually ended.

nnUNet only writes `checkpoint_final.pth` if training runs to completion (the
full default of 1000 epochs). Since you'll typically stop fine-tuning early with
`Ctrl+C`, that file won't exist. Use `checkpoint_best.pth` instead (saved
automatically whenever EMA pseudo Dice improves; watch for the
`Yayy! New best EMA pseudo Dice: ...` log lines) and rename it on the way in:

```bash
# On your local machine:
scp <vm-user>@<vm-host>:~/ChronoRoot/nnUNet_results/Dataset789_ChronoRoot2/nnUNetTrainer__nnUNetResEncUNetMPlans__2d/fold_0/checkpoint_best.pth \
    segmentationApp/models/Arabidopsis/fold_0/checkpoint_final.pth
```

If you did let training run all the way to completion, use
`checkpoint_final.pth` from the VM instead; no rename needed.

> **Back up the old checkpoint first** so you can roll back if the fine-tuned
> model introduces regressions elsewhere.

---

## Alternative: Full Retrain from Scratch

Use this instead of Steps 5–10 when you're not warm-starting from an existing
checkpoint, e.g. training a brand-new model, adding a new class, or making a
large enough data change that reusing the base model's plans/fingerprint no
longer makes sense.

This is nnUNet's standard (non-fine-tuning) workflow: fresh
`plan_and_preprocess`, video-grouped splits, and a full 5-fold ensemble train.
It costs roughly 5× the compute of the fine-tuning path, and the extra folds
only help at inference once `nnUNet_wrapper.py` is also updated to load them;
it currently hardcodes `use_folds=(0,)` (line 70).

### Prepare dataset.json

This path assumes a fresh `Dataset` folder rather than merging into the existing
`Dataset789_ChronoRoot2`, so there's no existing `dataset.json` to bump
`numTraining` on. Copy the matching template from this repo instead:

- Arabidopsis: `trainerOrganization/dataset_Arabidopsis.json`
- Tomato: `trainerOrganization/dataset_Tomato.json`

Rename the copy to `dataset.json` inside `nnUNet_raw/DatasetXXX/`, and update the
`numTraining` field to match the actual number of cases in `imagesTr/`.

### Generate splits_final.json (Grouped by Video)

Group cases by Robot/Camera ID before splitting, so frames from the same video
are never split across train and validation. A plain random split lets the
model memorize plate geometry instead of learning to generalize, and validation
loss will look better than it actually is. The ChronoRoot Jupyter notebook does
this grouping and writes out `splits_final.json`.

> Copy the generated file to `nnUNet_preprocessed/DatasetXXX/splits_final.json`
> **before** preprocessing; otherwise nnUNet auto-generates its own random
> split the first time you run `plan_and_preprocess`.

### Plan, Preprocess, and Train

Run on the VM (see Step 7 for environment setup):

```bash
nnUNetv2_plan_and_preprocess -d [DATASET_ID] -c 2d
```

Then train all 5 folds of the ensemble:

```bash
nnUNetv2_train [DATASET_ID] 2d 0
nnUNetv2_train [DATASET_ID] 2d 1
nnUNetv2_train [DATASET_ID] 2d 2
nnUNetv2_train [DATASET_ID] 2d 3
nnUNetv2_train [DATASET_ID] 2d 4
```

Unlike the fine-tuning path, let each fold run to completion rather than
stopping early. There's no warm-start, so `checkpoint_final.pth` is expected to
be written normally per fold. Plan for full training time.

### Use the Ensemble at Inference

Update `nnUNet_wrapper.py`:

```python
use_folds=(0, 1, 2, 3, 4),
```

and copy all 5 folds' checkpoints into `segmentationApp/models/<Model>/fold_X/`
instead of just `fold_0/`.

---

## FAQ

**Why only fold 0?**
The inference wrapper (`nnUNet_wrapper.py:68`) uses `use_folds=(0,)`. Training
all 5 folds would give marginally better ensemble accuracy but requires 5× the
compute, and you would also need to update the inference code to load all folds.

**How many new frames do I need?**
20–50 well-corrected failure frames is typically sufficient for a targeted
fine-tuning correction.

**How do I roll back?**
Keep the original `checkpoint_final.pth` backed up before replacing it so you
can revert if the fine-tuned model introduces regressions elsewhere.

## nnU-Net Gotchas

### Preprocessing Doesn't Populate gt_segmentations

`nnUNetv2_preprocess` (the lower-level command used to reuse an existing
plan) does **not** populate `nnUNet_preprocessed/<dataset>/gt_segmentations/`.
Only the higher-level `nnUNetv2_plan_and_preprocess` does that copy. After
adding new cases:

```bash
cp labelsTr/*.png gt_segmentations/
```

Otherwise validation crashes with `FileNotFoundError` at the very end of
training, after all epochs. `gt_segmentations` should mirror **all** of
`labelsTr`, not just one split.

### Splits Are Read Once

`splits_final.json` is read once into memory when `nnUNetv2_train` starts and
never re-read. Editing it on disk does not affect an already-running or
checkpointed process; a full restart (not `--c` resume) is required for split
changes to take effect.

### Checkpoints Are Infrequent

`checkpoint_latest.pth` is only written every `save_every=50` epochs. A crash
can lose up to 49 epochs of progress on resume.

### Small Correction Batches Get Diluted

`num_iterations_per_epoch=250` is fixed regardless of dataset size, and case
sampling is uniform random *with replacement* (`infinite=True`). There's no
built-in oversampling, so small correction-case batches get diluted and there's
no per-epoch guarantee every case is even seen once.

### Device Fallback

`segmentationApp/nnUNet_wrapper.py` falls back `cuda` → `mps` (Apple Silicon
only) → `cpu`. There's no DirectML/Intel-XPU path, so Windows integrated
graphics always fall through to CPU-only inference.

### Model Weights

Weights are hosted at
[`huggingface.co/calvinyong1/arabidopsis-segmentation-model`](https://huggingface.co/calvinyong1/arabidopsis-segmentation-model)
(this fork's own fine-tuned model). `download_weights.sh` pulls this explicitly
for Arabidopsis, and separately scans `ngaggion`'s account for other species
models (e.g. tomato) that aren't forked here.
~~~~

### A.Landing page

Source: `index.html`. Text is reproduced in section 3 above.
