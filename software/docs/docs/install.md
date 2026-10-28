---
layout: default
title: Install Guide
---

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
