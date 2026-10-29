---
layout: default
title: What's New in This Fork
---

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
