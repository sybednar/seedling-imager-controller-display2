# Seedling Imager — Hardware Design Files

<img width="1244" height="1146" alt="full_assembly_dual_bearing_belt_drive_2026-Jun-17_05-32-08PM-000_CustomizedView62023610162" src="https://github.com/user-attachments/assets/85371141-0100-47e5-9087-8e2302f285bb" />


Open-source hardware for an automated, six-plate time-lapse seedling imaging robot.
This folder contains the mechanical design files, bill of materials, and licensing
for the imager; the Raspberry Pi controller and image-acquisition/registration
software live in the root of this repository.

## Overview

The instrument is a rotating hexagonal carousel that holds up to six Petri plates and
presents each in turn to a fixed high-resolution camera. It is controlled by a
Raspberry Pi with a stepper motor and optical position sensors, so every plate returns
to the same imaging position on each cycle. Plates are illuminated with both transmitted
and reflected 940 nm infrared light, allowing seedlings to be grown and imaged either in
the light or in complete darkness (etiolated), typically at 1–2 hour intervals over 5–7
days. The system captures 16-bit grayscale TIFF images and automatically aligns
successive frames of each plate by phase cross-correlation (frame-to-frame registration
to ~2 pixels in current data).

The design was inspired by the open-source SPIRO Petri-plate imaging robot
(Ohlsson et al., 2024, *The Plant Journal* 118:584–600) and extends it with greater
plate capacity, dual transmitted + reflected IR illumination, and improved registration
reproducibility for quantitative time-lapse growth analysis.

## Contents

| File | Description |
|------|-------------|
| `imager_assembly.step.zip` | Full assembly in neutral STEP format (zipped). Opens in any CAD package (FreeCAD, SolidWorks, Onshape, etc.). Unzip before opening. |
| `imager_assembly.f3z` | Native Autodesk Fusion archive of the complete assembly, with all components and joints. For users who want to edit the design in Fusion. |
| `BOM.csv` | Bill of materials — parts, quantities, suppliers, and approximate cost. |
| `LICENSE-CERN-OHL-S-v2.txt` | Hardware license (see Licensing below). |
| `NOTICE.txt` | Required CERN-OHL-S copyright/license notice. |
| *(individual part STEP/STL files — to be added)* | Per-part files for 3D printing / fabrication. |

## Opening the design files

- **STEP (.step):** Unzip `imager_assembly.step.zip`, then open the `.step` in any CAD
  program. STEP preserves exact solid geometry and is the recommended starting point for
  reuse or modification outside Fusion.
- **Fusion archive (.f3z):** In Autodesk Fusion, use *File ▸ Open* and select the `.f3z`,
  or upload it to your Fusion data panel. This is the fully editable source design.

## Bill of materials

See `BOM.csv`. Key subsystems: Raspberry Pi single-board computer; [camera model — to be added];
stepper motor and driver; optical position sensors; 940 nm IR illumination (transmitted and
reflected); carousel and bearing/belt drive hardware; frame and plate holders.
*(Replace bracketed items with your specific part numbers and suppliers.)*

## Build and operation

Mechanical assembly notes: see `assembly.md` *(to be added)*.
Controller setup, camera configuration, and operation: see the documentation in the
repository root (`README.md`, `Camera configuration_user guide`,
`Setting manual camera focus instructions`).

## Licensing

This project uses two licenses:

- **Hardware design files** (CAD, STEP, STL, BOM) in this folder are licensed under the
  **CERN Open Hardware Licence Version 2 — Strongly Reciprocal (CERN-OHL-S v2)**.
  See `LICENSE-CERN-OHL-S-v2.txt` and `NOTICE.txt`.
- **Software** (the Raspberry Pi controller and image-acquisition/registration code) in
  the repository root is licensed under the **[MIT / BSD-3-Clause — FILL IN]** license.
  See the `LICENSE` file at the repository root.

## Citation

If you use this hardware or software, please cite the archived release:

> Bednarek, S. Y., Yong, C. W. J., Hoey, E. A. and Murua, K. (2026). *seedling-imager-controller-display2: control and image-acquisition
> software and hardware design files for an open-source six-plate infrared seedling imaging
> robot* (v1.1) [Software and hardware design files]. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX

*(Replace with the DOI minted when you archive the GitHub release on Zenodo.)*

## Contact

Sebastian Y. Bednarek, University of Wisconsin–Madison — sybednar@wisc.edu
