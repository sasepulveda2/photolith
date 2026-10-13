# Maskless Photolithography System for Micro and Nanofabrication (Digital Mask)

Open-source maskless photolithography system for transferring micrometric patterns onto copper substrates coated with dry film photoresist.

---

## Table of Contents

1. [Requirements and Installation](https://www.google.com/search?q=%23requirements-and-installation)
2. [Physical Environment Pre-Configuration](https://www.google.com/search?q=%23physical-environment-pre-configuration)
3. [User Guide and Operation Manual](https://www.google.com/search?q=%23user-guide-and-operation-manual)
    * [Step 1: Hardware Connection and Linking](https://www.google.com/search?q=%23step-1-hardware-connection-and-linking)
    * [Step 2: Loading and Ingestion of the Lithographic Pattern](https://www.google.com/search?q=%23step-2-loading-and-ingestion-of-the-lithographic-pattern)
    * [Step 3: Digital Conditioning and Binarization](https://www.google.com/search?q=%23step-3-digital-conditioning-and-binarization)
    * [Step 4: Spatial Calibration ($\mu\text{m/px}$)](https://www.google.com/search?q=%23step-4-spatial-calibration-mutextmpx)
    * [Step 5: Segmentation and Step-and-Repeat Configuration](https://www.google.com/search?q=%23step-5-segmentation-and-step-and-repeat-configuration)
    * [Step 6: Dose Adjustment and UV Exposure](https://www.google.com/search?q=%23step-6-dose-adjustment-and-uv-exposure)
    * [Step 7: Autonomous Calibration Modules](https://www.google.com/search?q=%23step-7-autonomous-calibration-modules)
4. [Quick Chemical Protocol (Dry Film)](https://www.google.com/search?q=%23quick-chemical-protocol-dry-film)
5. [Repository Structure](https://www.google.com/search?q=%23repository-structure)

---

## Requirements and Installation

### System Requirements

* **Operating System:** Windows 10/11 (recommended) or compatible Linux distributions.
* **Python 3** installed.

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

---

## Physical Environment Pre-Configuration

1. **Display Settings (OS):** Configure the projector display mode to **Extend these displays**.
2. **Safety Lighting:** Do not expose laminated substrates to direct white light or sunlight (an amber/yellow safe-light environment is recommended).
3. **Substrate Alignment:** Mount the laminated copper board onto the motorized stage, leveling the focal plane with respect to the projection lens.

---

## User Guide and Operation Manual

### Step 1: Hardware Connection and Linking

1. Run the main application:
```bash
python main.py

```


2. Expand the **MOTORS (X, Y, Z)** side panel.
3. Click the **CONNECT HARDWARE** button.
* The software will detect the corresponding COM port and send the G-code initialization sequence: disable software/physical endstops (`M211 S0`), bypass cold extrusion and thermal protections (`M302 S0`), and set relative positioning mode (`G91`).
* The bottom console will confirm the connection at the `[INFO]` level.


4. Using the directional control pad ($X+$, $X-$, $Y+$, $Y-$, $Z+$, $Z-$), jog the stage manually to the substrate origin position. You can toggle between full steps (*Steps*) or millimeters (*mm*).
5. Set the virtual work origin to initialize internal odometry.

### Step 2: Loading and Ingestion of the Lithographic Pattern

1. Click **Load pattern** in the top toolbar (or drag and drop the file directly onto the central canvas).
2. Supported formats:
* **Raster:** `.png`, `.jpg`, `.bmp`, `.tiff` files. Loaded and normalized in grayscale.
* **Vector SVG:** Rasterized internally at a minimum resolution of $4,000\text{ px}$ along its major axis.
* **Vector DXF:** Rendered monochromatically at a minimum density of $400\text{ DPI}$.



### Step 3: Digital Conditioning and Binarization

1. Open the **BINARY** side panel:
* **Enable binary mode (0/1):** Required checkbox to convert the image into a strict cutoff binary matrix ($0$ and $255$).
* **Threshold:** Adjust using the slider or numeric input (recommended empirical value: $50\% - 65\%$, depending on fine trace density).
* **Invert Color (Negative):** Enable when using negative photoresist (standard blue dry film). Exposed areas photopolymerize and resist chemical etching; unexposed dark areas dissolve in the developer.
* **Lock Threshold:** Check to prevent accidental alterations while manipulating the UI.


2. Set the **Projection brightness** in the top toolbar to $100\%$ for lithographic exposure.

### Step 4: Spatial Calibration ($\mu\text{m/px}$)

To ensure the software maps projector displacements accurately to the physical substrate:

1. Navigate to the top tab **Pattern calibration**.
2. Load an image or pattern of known physical dimensions (e.g., a calibration stage micrometer or a $100\ \mu\text{m}$ reference target).
3. Draw a straight line on the canvas by clicking on both endpoints of the reference feature.
4. The system calculates the distance in pixels ($L_{px}$).
5. In the **Actual measurement** field, enter the physical dimension in millimeters or microns.
6. Click **Save calibration**. The software derives the system spatial resolution:

$$\text{Scale Factor} = \frac{\text{Actual Distance (mm)}}{L_{px}}\quad [\text{mm/px}]$$


$$\text{Resolution} = \text{Scale Factor} \times 1000\quad [\mu\text{m/px}]$$



This factor is automatically saved to `config.json` for subsequent sessions.

### Step 5: Segmentation and Step-and-Repeat Configuration

If the pattern exceeds the single-exposure optical field of view:

1. Navigate to the **Grid view** tab.
2. Configure grid dimensions:
* **Grid Mode:** Define chunk width and height in pixels. The tool applies magnetic snapping (*snap*) to align cells with pattern boundaries.
* **Automatic Mode:** Automatically partitions the image into standard chunks based on the native projector resolution.



### Step 6: Dose Adjustment and UV Exposure

1. Expand the **EXPOSURE** side panel:
* **Exposure time:** Set according to substrate characterization.
* **Calibrated optimal range:** $7\text{ s}$ to $15\text{ s}$.
* **Wide traces (> 200 µm):** $7–10\text{ s}$.
* **Fine features (30–60 µm):** $15\text{ s}$.

* *Warning:* Exposure times near or exceeding $20\text{ s}$ cause lateral over-polymerization and unwanted feature widening.


* **Trigger mode:** Continuous or Pulsed (frequency between $1$ and $100\text{ Hz}$).


2. Click **Projections > Start Sequence**.
3. The *Step-and-Repeat* cycle executes autonomously through the state machine:
```
[Move Motor] ──> [Settling Delay (1.5 s)] ──> [Project Chunk] ──> [UV Exposure] ──> [Blank Screen] ──> (Next Chunk)

```


4. In case of motor stall, misalignment, or collision risk, immediately press the red **STOP** button to abort the routine.

---

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

---

## Quick Chemical Protocol (Dry Film)

To ensure adequate adhesion and edge definition of fabricated patterns:

1. **Mechanical Conditioning:** Wet-sand the bare copper board with 1250-grit sandpaper using gentle, even strokes until all surface oxide ($CuO / Cu_2O$) is removed.
2. **Chemical Decontamination:**
* Clean with **Acetone ($C_3H_6O$)** to strip grease, oils, and organic residues.
* Rinse immediately with **Isopropyl Alcohol ($C_3H_8O$)** to remove acetone residues. *Do not reverse this order*.


3. **Thermal Lamination:**
* Preheat the board to $110\ ^\circ\text{C}$ (a 3D printer heated bed works well).
* Peel off the inner polyethylene protective film from the dry film resist using adhesive tape.
* Lay the resist onto the heated substrate and immediately pass through a hot-roll laminator to eliminate trapped microbubbles.


4. **Exposure:** Project the digital mask onto the stage for $7 - 15\text{ s}$.
5. **Alkaline Development:**
* Peel off the outer transparent polyester carrier film.
* Submerge the board in a **$1\%\text{ w/v}$ Sodium Carbonate ($Na_2CO_3$)** aqueous solution (in distilled water) for **2 minutes** with gentle agitation.


6. **Stop Bath and Neutralization:**
* Remove with tweezers and immediately immerse in a clean distilled water bath for 2 minutes to halt developer action.
* Gently clear unpolymerized resist channels using an ultra-soft bristle brush under running distilled water.



---

## Repository Structure

```text
photolith/
├── main.py                  # Application entry point
├── requirements.txt         # Python environment dependencies
├── config.json              # Calibration persistence, soft limits, and backlash
├── controllers/
│   ├── creality_controller.py # G-code abstraction layer, odometry, and PySerial
│   └── worker.py              # Asynchronous worker thread (CamWorker on QThread)
├── mixins/
│   ├── ui_setup_mixin.py      # Modular UI assembly of panels and widgets
│   ├── image_processing_mixin.py # Binarization, inversion, and transformations
│   ├── grid_mixin.py          # Chunk splitting and overlap algorithms
│   ├── spatial_calibration_mixin.py # Micrometric scale calculation
│   ├── ruler_scale_mixin.py   # Step-and-Repeat routine for graduated scales
│   ├── projection_mixin.py    # Secondary projector window lifecycle management
│   ├── file_management_mixin.py # Ingestion and rasterization of SVG/DXF/raster
│   └── preferences_mixin.py   # JSON parameter serialization and persistence
├── docs/
│   └── images/                # Screenshots and technical system diagrams
└── tests/                    # Unit tests for kinematics and segmentation

```
