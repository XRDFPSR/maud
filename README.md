# MAUD — Materials Analysis Using Diffraction

**MAUD** is an open-source Java application for the combined analysis of materials using diffraction and spectroscopic techniques. Developed primarily at the **University of Trento** by **Luca Lutterotti**, it extends the Rietveld method into a unified framework capable of simultaneously refining multiple types of experimental data to extract comprehensive materials information.

> Current version: **2.99995** (pre-3.0, `version2` branch) — Licensed under **BSD 3-Clause**

---

## What MAUD Can Do

MAUD performs **Combined Analysis** — the simultaneous refinement of diffraction, fluorescence, and reflectivity data using a single structural model. It can determine:

| Category | What It Determines |
|---|---|
| **Crystal Structure** | Lattice parameters, atomic positions, site occupancies, thermal factors |
| **Microstructure** | Crystallite size, microstrain distributions, planar defects (stacking faults, twinning), dislocation densities |
| **Texture (ODF)** | Crystallographic texture via WIMV, EWIMV, harmonic, standard functions (fiber/spherical components), MTEX integration |
| **Residual Stress** | Macroscopic stress tensors, triaxial stress, EPSC elasto-plastic self-consistent modeling |
| **Phase Quantification** | Weight/volume fractions of crystalline and amorphous phases |
| **Chemical Composition** | Elemental analysis via X-ray fluorescence (XRF) including quantitative EDXRF and TXRF |
| **Reflectivity (XRR)** | Thin-film thickness, density, roughness via Parrat recursive method or matrix method |
| **Structure Solution** | *Ab initio* structure determination via Genetic Algorithm, Simulated Annealing, Reverse Monte Carlo, Charge Flipping (Superflip), Maximum Entropy Method (MEM) |
| **Pair Distribution Function** | PDF export for local structure analysis |
| **Electron Density Maps** | 3D Fourier / MEM electron density reconstruction |

### Supported Radiation Sources

- **X-ray** — lab tubes (Cu, Co, Cr, Mo, Fe, Ag, Ga, etc.), synchrotron, energy-dispersive
- **Neutron** — constant-wavelength (ILL D1B, D20, D19) and Time-of-Flight (LANSCE/HIPPO, ISIS GEM, IPNS)
- **Electron** — kinematical and dynamical (2-beam approximation) diffraction

### Supported Geometries

Bragg-Brentano, Debye-Scherrer, flat image plate (transmission/reflection/inclined), curved position-sensitive detectors (INEL CPS120/590), TOF multi-bank (HIPPO, GEM), Laue transmission, reflectivity, and more.

### Over 60 Data File Formats

Including Bruker/Siemens UXD/RAW, Philips XRDML, Rigaku, GSAS, FullProf, Dubna SKAT, TIFF images, CIF, HDF5, D1B/D20/D19 ILL, HIPPO, INEL, MDI, LCLS2, KCD/SYN (Nonius Kappa), stress rig data, and many others.

---

## Project Architecture

```
maud/
├── src/
│   ├── com/radiographema/          # Entry points
│   │   ├── Maud.java               # Main application class (GUI mode)
│   │   ├── MaudText.java           # Headless/batch mode
│   │   ├── MaudWebStart.java       # Java Web Start launcher
│   │   ├── Maudette.java           # Lightweight version
│   │   ├── tools/                  # Batch processing tools, QTA utilities
│   │   └── fpsm/                   # FPSM native library bindings
│   │
│   ├── it/unitn/ing/rista/         # CORE ENGINE (~80% of codebase)
│   │   ├── diffr/                  # **Diffraction models — the heart of MAUD**
│   │   │   ├── Phase.java          # Phase definition & computation
│   │   │   ├── Sample.java         # Sample assembly
│   │   │   ├── Instrument.java     # Instrument definition
│   │   │   ├── Measurement.java    # Measurement types (θ-2θ, TOF, EDX, XRR...)
│   │   │   ├── Diffraction.java    # Core diffraction computation engine
│   │   │   ├── Fluorescence.java   # XRF computation
│   │   │   ├── Reflectivity.java   # XRR computation
│   │   │   ├── Absorption.java     # Absorption correction
│   │   │   ├── Texture.java        # Texture model orchestration
│   │   │   ├── Stress.java / Strain.java  # Residual stress analysis
│   │   │   ├── StructureFactor.java       # Fhkl computation
│   │   │   ├── SizeStrainModel.java       # Microstructure broadening
│   │   │   ├── PlanarDefects.java         # Stacking faults, twinning
│   │   │   ├── PoleFigure.java            # Pole figure computation
│   │   │   ├── XRDcat.java / Parameter.java  # Analysis file format (.par)
│   │   │   │
│   │   │   ├── data/               # ~60+ data file format readers
│   │   │   ├── cal/                # ~30+ angular/intensity calibration models
│   │   │   ├── geometry/           # Diffractometer geometry models
│   │   │   ├── detector/           # Detector types
│   │   │   ├── radiation/          # X-ray, neutron, electron radiation sources
│   │   │   ├── rta/                # Texture analysis (WIMV, EWIMV, harmonic, MTEX...)
│   │   │   ├── rsa/                # Residual stress & EPSC modeling
│   │   │   ├── sizestrain/         # Crystallite size & microstrain models
│   │   │   ├── sdpd/               # Structure solution (GA, SA, Superflip, MEM...)
│   │   │   ├── sfm/                # Structure factor models (Le Bail, Pawley, Rietveld...)
│   │   │   ├── reflectivity/       # XRR models (Parrat, matrix, GA fitting)
│   │   │   ├── fluorescence/       # XRF quantitative models
│   │   │   ├── forcefield/         # DFT (ABINIT), LJ, bond distance/angle restraints
│   │   │   ├── magnetic/           # Magnetic structure models
│   │   │   └── shape/              # Sample shape absorption correction
│   │   │
│   │   ├── comp/                   # Optimization algorithms
│   │   │   ├── MarqardLeastSquares.java    # Marquardt-Levenberg
│   │   │   ├── SimulatedAnnealingRefinement.java
│   │   │   ├── GeneticAlgorithmRefinement.java
│   │   │   ├── MonteCarloAlgorithmRefinement.java
│   │   │   ├── NelderMeadSimplex.java
│   │   │   └── MetaDynamicsSearch.java
│   │   │
│   │   ├── awt/                    # Java Swing GUI (Maud's extensive UI)
│   │   │   ├── mainFrame.java
│   │   │   ├── DiffractionMainFrame.java
│   │   │   └── treetable/          # Custom tree-table parameter editor
│   │   │
│   │   ├── render3d/               # OpenGL 3D rendering (JOGL/GL4Java)
│   │   │   ├── Structure3Djgl.java
│   │   │   ├── Crystallite3Djgl.java
│   │   │   ├── PoleRendering3Djgl.java
│   │   │   └── MapRendering3Djgl.java
│   │   │
│   │   ├── util/                   # Math, crystallography, I/O utilities
│   │   ├── io/                     # CIF parser, COD database, XML, JSON
│   │   ├── chemistry/              # Periodic table, X-ray scattering factors
│   │   ├── jpvm/                   # Parallel computation (PVM-like)
│   │   ├── neuralnetwork/          # ANN for spectrum recognition & indexing
│   │   └── ...
│   │
│   ├── it/unitn/ing/wizard/        # Guided wizards
│   │   ├── HIPPOWizard/            # HIPPO (LANSCE) TOF instrument wizard
│   │   ├── LCLS2Wizard/            # LCLS (XFEL) image wizard
│   │   └── LoskoWizard/            # Losko detector wizard
│   │
│   ├── it/unitn/ing/jgraph/        # Plotting library (Graph2D)
│   ├── it/unitn/ing/jsginfo/       # Space group symmetry (sginfo)
│   ├── it/unitn/ing/fortran/       # Fortran-style formatted I/O
│   │
│   ├── maud_mcp/                   # 🆕 Python AI Agent toolkit
│   │   ├── core/
│   │   │   ├── java_bridge.py      # Java subprocess bridge
│   │   │   ├── par_editor.py       # .par file editor
│   │   │   ├── data_manager.py     # Data file management
│   │   │   └── result_parser.py    # Refinement result parser
│   │   ├── server/
│   │   │   └── mcp_server.py       # MCP Server / REST API
│   │   ├── ai/
│   │   │   ├── diagnostics.py      # AI-powered analysis diagnostics
│   │   │   ├── params.py           # Parameter suggestion
│   │   │   └── reporter.py         # Automated report generation
│   │   ├── config.py               # Configuration management
│   │   ├── tests/                  # Unit tests
│   │   └── _legacy/                # Legacy MCP implementation
│   │
│   ├── org/la4j/                   # Linear algebra library
│   ├── gov/lanl/epsc4/             # EPSC4 elasto-plastic modeling
│   ├── gov/noaa/pmel/sgt/          # Scientific Graphics Toolkit
│   ├── Jama/                       # Matrix algebra (SVD, Eigen, Cholesky...)
│   ├── com/jtex/qta/               # Quantitative Texture Analysis (Beartex-compatible)
│   ├── HTTPClient/                 # HTTP client library
│   │
│   ├── help/                       # User documentation
│   ├── images/                     # Icons and images
│   ├── examples/                   # Example analysis files (.par, .raw, .cif)
│   └── files/                      # Default resources (xraydata.db, CIF databases...)
│
├── libs/current/                   # Dependencies (ij.jar, colt.jar, jogl, xraylib...)
├── libs/ant-libs/                  # Ant build helpers (Mac app bundler)
├── build.xml                       # Apache Ant build script
├── ant_maud_v2.properties          # Build configuration template
├── Compile.md                      # Build & compile guide
├── LICENSE                         # BSD 3-Clause
└── ImageJ/                         # ImageJ plugins for image processing
```

---

## Quick Start

### Pre-built Binary

Download the latest installer from the [MAUD website](http://maud.radiographema.com/) for Windows, macOS, or Linux.

### Building from Source

**Requirements:**
- JDK 21+ (Oracle JDK or OpenJDK/Zulu)
- Apache Ant
- IntelliJ IDEA (recommended for development)

```bash
# 1. Configure build
cp ant_maud_v2.properties ~/.ant_maud_v2.properties
# Edit the file:
#   - Set JAVA_HOME (JDK location)
#   - Set openjdk (OpenJDK location for bundled JRE builds)
#   - Set build (output directory)
#   - Set installerDir

# 2. Create build number file
mkdir build_numbers
touch build_numbers/Maud_full_build.number

# 3. Build via Ant
ant -f build.xml compile_open   # Compile only
ant -f build.xml build_full     # Build full installer
```

See `Compile.md` for detailed instructions (by S. Merkel & L. Lutterotti, July 2024).

---

## maud_mcp — Python AI Agent Interface

The `src/maud_mcp/` package provides a Python interface for AI Agents (LLMs) to interact with MAUD programmatically:

```python
from maud_mcp.core.java_bridge import JavaBridge

bridge = JavaBridge()
status = bridge.get_status()

# Load an analysis, run refinement, get results
bridge.load_analysis("my_sample.par")
result = bridge.run_refinement()
report = bridge.get_refinement_report()
```

**Key modules:**
- **`java_bridge.py`** — Manages MAUD as a Java subprocess with full lifecycle control
- **`par_editor.py`** — Read/write/modify `.par` analysis files
- **`data_manager.py`** — Handle data file loading and format detection
- **`result_parser.py`** — Parse refinement output (Rwp, GoF, phase fractions, cell params...)
- **`mcp_server.py`** — MCP (Model Context Protocol) server for AI agent integration
- **`ai/diagnostics.py`** — Automated analysis quality assessment
- **`ai/reporter.py`** — Generate human-readable analysis reports

**Configuration** (environment variables):
| Variable | Default | Description |
|---|---|---|
| `MAUD_HOME` | auto-detect | MAUD installation directory |
| `MAUD_JAVA_HOME` | `JAVA_HOME` | JDK installation |
| `MAUD_WORK_DIR` | `/tmp/maud_work` | Working directory for temp files |
| `MAUD_MAX_MEM` | `2g` | Java heap size |
| `MAUD_TIMEOUT` | `180` | Refinement timeout (seconds) |

---

## Key Features

### Refinement Algorithms
- **Marquardt Least Squares** (primary) — with Cholesky decomposition, weighting schemes (Q-space, log, sqrt)
- **Genetic Algorithm** — global optimization for indexing, structure solution
- **Hybrid GA + Least Squares** — best of both worlds
- **Simulated Annealing** — for rugged parameter landscapes
- **Nelder-Mead Simplex** — derivative-free optimization
- **Reverse Monte Carlo** / **Meta-Dynamics**
- **Parallel computation** support (multi-core & XGrid distributed)

### Texture Analysis
- **WIMV** (Williams-Imhof-Matthies-Vinel)
- **EWIMV** (Entropy-Weighted WIMV)
- **Harmonic** method (including Van Houtte exponential form for ODF positivity)
- **Standard Functions** (fiber & spherical components, Beartex-compatible)
- **March-Dollase** model
- **MTEX** integration (calls MTEX binaries directly, no Matlab required)
- ODF import/export with Beartex, PopLA, GSAS

### Microstructure Modeling
- Crystallite size & microstrain (isotropic & anisotropic via Popa model)
- Distributions of crystallite sizes and microstrains
- Warren-Averbach Fourier analysis
- Antiphase boundaries, planar defects (Warren model, single-layer Ufer model)
- Modulated turbostratic structures (clays, graphite)
- Single-chain polymer disorder models

### Structure Solution (SDPD)
- Genetic Algorithm indexing (evolutionary smart indexing)
- *Ab initio* structure solution via GA, SA, Reverse Monte Carlo
- Charge Flipping (Superflip integration)
- Maximum Entropy Method (MEM) for Fourier maps
- Neural Network based indexing
- DICVOL91 integration
- Le Bail and Pawley intensity extraction

### X-ray Fluorescence
- Quantitative XRF with matrix correction
- EDXRF and TXRF support
- Simultaneous XRF + diffraction refinement
- GIXRF (Grazing-Incidence XRF) coupled with reflectivity
- M and N line support for heavy elements

---

## References

**Combined Analysis:**
- Lutterotti, L. et al. "Combined analysis of diffraction, fluorescence and reflectivity data", *IUCrJ* (in preparation)
- Lutterotti, L. "Total pattern fitting for the combined size–strain–stress–texture determination in thin film diffraction", *Nucl. Instr. Meth. B*, 268, 334–340 (2010)

**RITA / Texture:**
- Wenk, H.-R., Matthies, S. & Lutterotti, L. "Texture analysis from diffraction spectra", *Mater. Sci. Forum*, 157-162, 473-480 (1994)
- Matthies, S., Lutterotti, L. & Wenk, H.-R. "Advances in Texture Analysis from Diffraction Spectra", *J. Appl. Cryst.*, 30, 31-42 (1997)

**RISTA / Stress:**
- Ferrari, M. & Lutterotti, L. "Method for the simultaneous determination of anisotropic residual stresses and texture by X-ray diffraction", *J. Appl. Phys.*, 76(11), 7246-55 (1994)

**Microstructure:**
- Lutterotti, L. & Scardi, P. "Simultaneous Structure and Size-Strain Refinement by the Rietveld Method", *J. Appl. Cryst.*, 23, 246-252 (1990)

---

## License

BSD 3-Clause License. See [LICENSE](./LICENSE).

---

## Contributing

The upstream repository is at [github.com/luttero/maud](https://github.com/luttero/maud). For contributions, bug reports, or questions, contact:

- **Luca Lutterotti** — luca.lutterotti@unitn.it
- MAUD website: [http://maud.radiographema.com/](http://maud.radiographema.com/)
