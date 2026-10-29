# Installing ChronoRoot on Windows via WSL

This walks through getting this system running on a Windows machine, from a
clean Windows install through to launching the apps from your Desktop. It
uses `installer_conda_wsl.sh`, which sets up a Linux (Ubuntu) environment
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
desktop — required for this project's PyQt5-based GUIs). Reboot if prompted.

If WSL is already installed but you don't have a distro yet:

```powershell
wsl --install -d Ubuntu
```

After install, launch "Ubuntu" from the Start Menu once to finish setup and
create your Linux username/password.

**Windows version note:** WSLg ships by default on Windows 11 and on
sufficiently updated Windows 10 (via Windows Update / `wsl --update`). If
GUI windows fail to appear later, run `wsl --update` from PowerShell first.

### 2. NVIDIA GPU users — driver setup (Windows side, not inside WSL)

If you have an NVIDIA GPU and want segmentation to run on it (the "Full
Node" option below), install the **Windows** NVIDIA driver only:

- https://www.nvidia.com/Download/index.aspx

**Do not** install a separate NVIDIA Linux driver inside WSL — WSL2 GPU
passthrough uses the Windows host driver directly via a compatibility
shim. Installing a Linux driver inside WSL on top of it will break GPU
access, not fix it.

Once the Windows driver is installed, verify it's visible from inside WSL
(after Step 1):

```bash
nvidia-smi
```

If this prints your GPU info, passthrough is working. If it's not found,
update the Windows driver and re-check before continuing — don't try to
"fix" it from inside WSL.

If you don't have a GPU, skip this — you can still install a CPU-only
("Lite Node") setup for analysis-only workflows.

### 3. Install Miniconda inside WSL

Open your **Ubuntu (WSL)** terminal and run:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/etc/profile.d/conda.sh
conda init bash
```

Close and reopen your WSL terminal (or run `source ~/.bashrc`) so `conda` is
available on your `PATH`. The installer script requires `conda` to already be
present — it will not install it for you.

`git` normally ships with Ubuntu's WSL image already; if `git --version`
fails, install it with `sudo apt-get install -y git`.

## Installation

### 4. Clone the repository

```bash
git clone https://github.com/calvinyong1/ArabidopsisAnalysisV2.git
cd ArabidopsisAnalysisV2
```

### 5. Run the WSL installer

```bash
bash installer_conda_wsl.sh
```

The script will:

1. **Verify you're in WSL** and that `conda` is available.
2. **Detect your GPU** via `nvidia-smi` (informational at this stage).
3. **Install `libzbar0`** via `sudo apt-get` (needed for QR code support) —
   you'll be prompted for your Linux password.
4. **Ask for an install directory** (default: `~/.local/chronoroot`). This is
   where the *deployed* copy of the app lives going forward — separate from
   the repo you just cloned in Step 4, which is only needed to obtain and run
   this installer script. It's safe to delete the Step 4 clone afterward.
5. **Clone/update the repo again** into that install directory (this is the
   copy the shortcuts will actually launch and that `git pull` will update on
   re-runs).
6. **Ask you to choose an installation type:**
   - **Full Node** — segmentation + analysis. Requires a GPU (you can
     proceed without one, but segmentation will be very slow on CPU).
   - **Lite Node** — analysis only, no segmentation model. Works on any
     laptop. You'll be separately asked whether to also install the
     Segmentation GUI in monitoring-only mode (useful if segmentation runs
     elsewhere, e.g. a shared server, and you just want to watch progress).
7. **Create the `ChronoRoot` conda environment** from the appropriate
   `environment.yml` / `environment_no_nnunet.yml`.
8. **Verify the GPU is actually usable by PyTorch** (Full Node only) — this
   is a real check (`torch.cuda.is_available()`), not just the earlier
   `nvidia-smi` detection. If it fails here, revisit Step 2 before continuing
   — segmentation will otherwise silently fall back to CPU.
9. **Download the segmentation model weights** (Full Node only) — pulls your
   fine-tuned Arabidopsis model and syncs any other available models.
10. **Create Windows shortcuts** on your Desktop and in the Start Menu for
    each installed app (ChronoRoot Analysis, ChronoRoot Image Aligner, and
    ChronoRoot Segmentation if selected). This step calls out to
    `cmd.exe`/`powershell.exe` from within WSL — this requires WSL/Windows
    interop, which is enabled by default and normally needs no action from
    you.

### 6. Launch the app

Use the new shortcuts on your Desktop or Start Menu. The first launch may
take a few seconds longer while the conda environment activates.

## Troubleshooting

- **"This script must be run inside WSL."** — you're running it from a
  native Windows shell (PowerShell/cmd), not a WSL terminal. Open "Ubuntu"
  from the Start Menu and run it from there.
- **`sudo apt-get install -y libzbar0` fails** — the installer assumes an
  Ubuntu/Debian-based WSL distro (uses `apt-get`). If you installed a
  different distro, install the equivalent `zbar` package manually with that
  distro's package manager first.
- **GUI windows never appear** — run `wsl --update` from PowerShell on the
  Windows side, then restart WSL (`wsl --shutdown` from PowerShell, then
  reopen your Linux terminal) and try again.
- **`torch.cuda.is_available()` check fails despite `nvidia-smi` working
  earlier** — this means a GPU is visible to WSL but the installed PyTorch
  build can't use it, usually a driver/CUDA version mismatch. Confirm the
  Windows NVIDIA driver is fully up to date (Step 2) and re-run the
  installer; it's safe to re-run (it updates the existing conda environment
  and repo rather than starting over).
- **Shortcuts weren't created / step 10 seemed to silently fail** — this
  relies on WSL-Windows interop (`cmd.exe`/`powershell.exe` callable from
  WSL) being enabled, which is the default. If you or your organization has
  disabled it, shortcut generation won't work; you can still launch the apps
  manually from inside WSL by running `python run.py` from
  `~/.local/chronoroot/ChronoRoot2/<appFolder>` with the `ChronoRoot` conda
  environment active.

## Re-running the installer

The script is safe to run again later (e.g. to pick up updates): it detects
the existing clone and runs `git pull` instead of cloning fresh, and updates
(rather than recreates) the existing `ChronoRoot` conda environment.
