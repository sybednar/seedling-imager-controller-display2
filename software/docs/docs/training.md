---
layout: default
title: Fine-tuning nnU-Net
---

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
