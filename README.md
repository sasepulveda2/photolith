# Maskless Photolithography System for Micro and Nanofabrication (Digital Mask)

**English** • [Español](README_ES.md)

Open-source maskless photolithography system for transferring micrometric patterns onto copper substrates coated with dry film photoresist.

## Table of Contents
1. [Hardware Overview & Workstation Assembly](#hardware-overview--workstation-assembly)
2. [Requirements and Installation](#requirements-and-installation)
3. [Physical Environment Pre-Configuration](#physical-environment-pre-configuration)
4. [User Guide and Operation Manual](#user-guide-and-operation-manual)
    * [Step 1: Hardware Connection and Linking](#step-1-hardware-connection-and-linking)
    * [Step 2: Loading and Ingestion of the Lithographic Pattern](#step-2-loading-and-ingestion-of-the-lithographic-pattern)
    * [Step 3: Digital Conditioning and Binarization](#step-3-digital-conditioning-and-binarization)
    * [Step 4: Spatial Calibration (µm/px)](#step-4-spatial-calibration-mutextmpx)
    * [Step 5: Segmentation and Step-and-Repeat Configuration](#step-5-segmentation-and-step-and-repeat-configuration)
    * [Step 6: Dose Adjustment and UV Exposure](#step-6-dose-adjustment-and-uv-exposure)
    * [Step 7: Autonomous Calibration Modules](#step-7-autonomous-calibration-modules)
5. [Quick Chemical Protocol (Dry Film)](#quick-chemical-protocol-dry-film)
6. [Software Architecture & Control Flow](#software-architecture--control-flow)
7. [Repository Structure](#repository-structure)
8. [Citation](#citation)
9. [License](#license)



## Hardware Overview & Workstation Assembly

<p align="center">
  <img src="images/system_assembly.jpg" alt="Physical Lithography Workstation" width="60%" />
</p>
<p align="center">
  <em>Figure 1a: Lithography stepper with motorized XYZ stage.</em>
</p>

The physical workstation couples an optical projection engine with a three-axis motorized motion stage controlled via serial communication:

| No. | Component | Technical Specification / Role |
| :---: | :--- | :--- |
| **1** | Projector Chassis | Modified DLP projector casing housing high-power UV light emission. |
| **2** | Ultraviolet Illumination Source | High-radiance optical engine emitting in the 385–405 nm UV band for photopolymerization. |
| **3** | UV Containment Cover | 3D-printed 6 mm PLA shroud preventing stray UV radiation and eye exposure. |
| **4** | Optical System Mount | Heat-resistant 3D-printed ABS bracket designed to prevent thermal creep (Tg ~105 °C). |
| **5** | Focal Spacer Ring | Optical spacer calibrating working focal distance to the substrate plane. |
| **6** | Projection Optics Assembly | Compound lens stack for focal reduction and micrometric plane imaging. |
| **7** | Color Wheel Bypass Circuit | NE555 timer circuit generating a 120 Hz (10% duty cycle) square wave to bypass projector firmware locks. |
| **8** | Kinematic Translation Stage | Micrometric 3-axis translation stage. |
| **9** | NEMA 17 Stepper Motors | Motion at 6,400 steps/mm with geared reductions. |
| **10** | Creality Controller Board | Microcontroller executing motion instructions with G-code. |

## Requirements and Installation

### System Requirements

- **Operating System:** Windows 10/11 (recommended) or compatible Linux distributions.
- **Python 3** installed.

### Installing Dependencies

1. Clone the repository:
```bash
git clone https://github.com/sasepulveda2/photolith.git
cd photolith
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

*Essential dependencies:* `PyQt5`, `opencv-python`, `numpy`, `matplotlib`, `pyserial`, `PyMuPDF` (`fitz` module for SVG), `ezdxf`.

## Physical Environment Pre-Configuration

1. **Display Settings (OS):** Configure the projector display mode to **Extend these displays** (1920×1080 native resolution).
2. **Safety Lighting:** Do not expose laminated substrates to direct white light or sunlight (an amber/yellow safe-light environment is recommended).
3. **Substrate Alignment:** Mount the laminated copper board onto the motorized stage, leveling the focal plane directly beneath the projection optics.

<p align="center">
  <img src="images/uv_exposure_stage.png" alt="Substrate Focal Alignment" width="45%" />
</p>
<p align="center">
  <em>Figure 2: Laminated copper substrate aligned on the motion stage under focused UV projection.</em>
</p>

## User Guide and Operation Manual

### Step 1: Hardware Connection and Linking

1. Run the main application:
```bash
python platform/main.py
```

2. Expand the **MOTORS (X, Y, Z)** side panel.
3. Click the **CONNECT HARDWARE** button:
- The software automatically detects the corresponding COM port and transmits the initialization sequence: disable software/physical endstops (`M211 S0`), bypass cold extrusion and thermal locks (`M302 S0`), and switch to relative positioning mode (`G91`).
- Connection status is displayed at the `[INFO]` level in the lower terminal console.

<p align="center">
  <img src="images/gui_motor_control.png" alt="Motor Control Panel" width="340px" />
</p>
<p align="center">
  <em>Figure 3: Motor control interface featuring jog keypad, pulse distance scaling, and emergency stop.</em>
</p>

4. Using the directional control pad ($X+$, $X-$, $Y+$, $Y-$, $Z+$, $Z-$), jog the stage manually to the substrate origin position. You can toggle between full steps (*Steps*) or millimeters (*mm*).
5. Set the virtual work origin to initialize internal odometry.

### Step 2: Loading and Ingestion of the Lithographic Pattern

1. Click **Load pattern** in the top toolbar (or drag and drop the file directly onto the central canvas).
2. Supported formats:
- **Raster:** `.png`, `.jpg`, `.bmp`, `.tiff` files. Loaded and normalized in grayscale.
- **Vector SVG:** Rasterized internally at a minimum resolution of $4,000\text{ px}$ along its major axis.
- **Vector DXF:** Rendered monochromatically at a minimum density of $400\text{ DPI}$.

### Step 3: Digital Conditioning and Binarization

1. Open the **BINARY** side panel:
- **Enable binary mode (0/1):** Required checkbox to convert the image into a strict cutoff binary matrix ($0$ and $255$).
- **Threshold:** Adjust using the slider or numeric input (recommended empirical value: $50\% - 65\%$, depending on fine trace density).
- **Invert Color (Negative):** Enable when using negative photoresist (standard blue dry film). Exposed areas photopolymerize and resist chemical etching; unexposed dark areas dissolve in the developer.
- **Lock Threshold:** Check to prevent accidental alterations while manipulating the UI.

2. Set the **Projection brightness** in the top toolbar to $100\%$ for lithographic exposure.

<p align="center">
  <img src="images/gui_pattern_loaded.png" alt="Loaded Pattern Canvas" width="58%" />
</p>
<p align="center">
  <em>Figure 4: (a) Active pattern loaded on the main canvas.</em>
</p>

<p align="center">
  <img src="images/gui_binarization.png" alt="Binarization Panel" width="38%" />
</p>
<p align="center">
  <em>Figure 4: (b) Digital binarization, inversion, and threshold lock controls.</em>
</p>

### Step 4: Spatial Calibration ($\mu\text{m/px}$)

To ensure the software maps projector pixel displacements accurately to stage movements:

1. Navigate to the top tab **Pattern calibration**.
2. Load an image or pattern of known physical dimensions (e.g., a calibration stage micrometer or a $100\ \mu\text{m}$ reference target).
3. Draw a straight line on the canvas by clicking on both endpoints of the reference feature.
4. The system calculates the distance in pixels ($L_{px}$).
5. In the **Actual measurement** field, enter the real physical dimension in millimeters or microns.
6. Click **Save calibration**. The software computes the system spatial resolution:

$$\text{Scale Factor} = \frac{\text{Actual Distance (mm)}}{L_{px}}\quad [\text{mm/px}]$$

$$\text{Resolution} = \text{Scale Factor} \times 1000\quad [\mu\text{m/px}]$$

This factor is automatically saved to `file_structure.json` (and `platform/cache_photolith/file_structure.json`) for subsequent sessions.

<p align="center">
  <img src="images/gui_spatial_calibration.png" alt="Spatial Calibration Module" width="68%" />
</p>

<p align="center">
  <em>Figure 5: Spatial calibration module computing scale factor (µm/px) from a measured reference distance.</em>
</p>

### Step 5: Segmentation and Step-and-Repeat Configuration

If the pattern exceeds the single-exposure optical field of view:

1. Navigate to the **Grid view** tab.
2. Configure grid dimensions:
- **Grid Mode:** Define chunk width and height in pixels. The tool applies magnetic snapping (*snap*) to align cells with pattern boundaries.
- **Automatic Mode:** Automatically partitions the image into standard chunks based on the native projector resolution.

### Step 6: Dose Adjustment and UV Exposure

1. Expand the **EXPOSURE** side panel:
- **Exposure time:** Calibrated for dry film photopolymerization ($7\text{ s} - 15\text{ s}$).
- **Wide traces (> 200 µm):** $7–10\text{ s}$.
- **Fine features (30–60 µm):** $15\text{ s}$.
- *Warning:* Exposure times near or exceeding $20\text{ s}$ cause lateral over-polymerization and track broadening.
- **Trigger mode:** Continuous or Pulsed (frequency between $1$ and $100\text{ Hz}$).

2. Click **Projections > Start Sequence**.
3. The *Step-and-Repeat* cycle executes autonomously through a non-blocking multithreaded pipeline:
```
[Move Motor] ──> [Settling Delay (1.5 s)] ──> [Project Chunk] ──> [UV Exposure] ──> [Blank Screen] ──> (Next Chunk)
```
4. In case of motor stall, misalignment, or collision risk, immediately press the red **STOP** button to abort the routine.

<p align="center">
  <img src="images/multithread_sequence_diagram.png" alt="Execution Sequence Diagram" width="58%" />
</p>

<p align="center">
  <em>Figure 6: (a) Sequence diagram showing asynchronous coordination between GUI, worker thread, and serial hardware.</em>
</p>

<p align="center">
  <img src="images/exposure_calibration_lines.jpg" alt="Exposure Line Calibration" width="38%" />
</p>

<p align="center">
  <em>Figure 6: (b) Microphotograph of dose-calibrated test tracks (130 µm down to 60 µm) exposed at 15 s.</em>
</p>

### Step 7: Autonomous Calibration Modules

#### Exposure Matrix Generator

Determines the optimal exposure dose on a single test board:

1. Open the utilities menu and select **Sweep Matrix**.
2. Configure the test pattern (parallel line grid with decreasing trace widths).
3. Start the test: the system projects stripes in an incremental, cumulative sequence using Qt timers. Each stripe receives a distinct dose (steps from $2$ to $20\text{ s}$), allowing post-development microscopic inspection to pinpoint optimal polymerization.

#### Micrometer Ruler Module (*RulerScaleMixin*)

Fabricates calibrated physical measurement scales on glass or copper substrates:

1. Open the **Scale ruler** view.
2. Set major tick spacing in pixels (computed from the system scale factor), subdivision count, line thickness, and total travel length.
3. Click **Start scale sequence**: the stage moves sequentially along the X-axis with backlash compensation, exposing the graduated scale segment by segment.

<p align="center">
  <img src="images/gui_ruler_module.png" alt="Ruler Module GUI" width="56%" />
</p>
<p align="center">
  <em>Figure 7: (a) Scale ruler generator interface.</em>
</p>
<p align="center">

<img src="images/micrometric_ruler_glass.png" alt="Microfabricated Ruler on Glass" width="40%" />
</p>
<p align="center">
  <em>Figure 7: (b) Microfabricated micrometer ruler on glass, verified against a 100 µm reference wire.</em>
</p>

## Quick Chemical Protocol (Dry Film)

To ensure adequate adhesion and edge definition of fabricated patterns:

<p align="center">
  <img src="images/copper_sanding.png" alt="Copper Sanding" width="45%" />
</p>
<p align="center">
  <em>Figure 8: (a) Surface oxide removal using 1250-grit sandpaper.</em>
</p>
<p align="center">
  <img src="images/chemical_development.png" alt="Chemical Development Bath" width="45%" />
</p>
<p align="center">
  <em>Figure 8: (b) Alkaline development in 1% w/v Na2CO3 bath.</em>
</p>
1. **Mechanical Conditioning:** Wet-sand the bare copper board with 1250-grit sandpaper using gentle, even strokes until all surface oxide ($CuO / Cu_2O$) is removed.
2. **Chemical Decontamination:**
- Clean with **Acetone ($C_3H_6O$)** to strip grease, oils, and organic residues.
- Rinse immediately with **Isopropyl Alcohol ($C_3H_8O$)** to remove acetone residues. *Do not reverse this order*.
3. **Thermal Lamination:**
- Preheat the board to $110\ ^\circ\text{C}$ (a 3D printer heated bed works well).
- Peel off the inner polyethylene protective film from the dry film resist using adhesive tape.
- Lay the resist onto the heated substrate and immediately pass through a hot-roll laminator to eliminate trapped microbubbles.
4. **Exposure:** Project the digital mask onto the stage for $7 - 15\text{ s}$.
5. **Alkaline Development:**
- Peel off the outer transparent polyester carrier film.
- Submerge the board in a **$1\%\text{ w/v}$ Sodium Carbonate ($Na_2CO_3$)** aqueous solution (in distilled water) for **2 minutes** with gentle agitation.
6. **Stop Bath and Neutralization:**
- Remove with tweezers and immediately immerse in a clean distilled water bath for 2 minutes to halt developer action.
- Gently clear unpolymerized resist channels using an ultra-soft bristle brush under running distilled water.

## Software Architecture & Control Flow

The control engine is architected around a centralized multi-mixin design pattern, isolating UI, image processing pipelines, and kinematic serial control without monolithic coupling:

<p align="center">
  <img src="images/mixin_architecture.png" alt="Mixin Class Architecture" width="56%" />
</p>
<p align="center">
  <em>Figure 9: (a) Modular controller composition via 13 mixins + QWidget.</em>
</p>
<p align="center">
  <img src="images/backlash_softlimits_flow.png" alt="Backlash and Soft Limits Flowchart" width="40%" />
</p>
<p align="center">
  <em>Figure 9: (b) Kinematic decision tree enforcing soft travel limits and backlash absorption.</em>
</p>

- **Asynchronous Execution:** Long-running jobs run in a secondary `QThread` (`CamWorker`), keeping the main Qt event loop responsive.
- **Backlash Compensation:** The kinematic controller evaluates movement direction changes and automatically injects pre-calibrated compensation pulses.
- **Software Travel Limits (*Soft Limits*):** Validates every incoming Cartesian vector against physical stage boundaries before transmitting G-code, preventing mechanical collisions.

## Repository Structure

```text
photolith/
├── requirements.txt        # Python environment dependencies
├── file_structure.json     # Calibration persistence and exposure parameters
├── images/                 # Screenshots, system diagrams, and microphotographs
└── platform/               # Application source root
    ├── main.py             # Application entry point
    ├── system_functions.py # LithographySimulator main class (mixin composition)
    ├── constants.py        # Global constants and tuneable parameters
    ├── projection_window.py# Secondary UV projection display window
    ├── motors/             # Serial motor control subsystem
    ├── mixins/             # 13 functional subsystems (UI, vision, processing)
    └── UI/                 # Panels, widgets, themes, and async worker
```

## Citation

This software was developed as part of an engineering thesis at **Universidad de los Andes (Chile)**, **Facultad de Ciencias e Ingeniería**. If you use this platform, software algorithms, or calibration methodologies in academic or technical work, please cite:

```bibtex
@thesis{sepulveda2026photolith,
  author       = {Sergio A. Sepúlveda Véliz},
  title        = {Maskless Photolithography System for Micro and Nanofabrication (Digital Mask)},
  school       = {Universidad de los Andes},
  department   = {Facultad de Ciencias e Ingeniería},
  year         = {2026},
  address      = {Santiago, Chile},
  note         = {Open-source repository}
}
```

## License

This project is open-source software licensed under the [MIT License](LICENSE).
