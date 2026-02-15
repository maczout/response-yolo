response-yolo is a faithful Python implementation of Response-2000 (R2K), the reinforced concrete sectional analysis software by Evan Bentz. The implementation provides a command-line kernel for automated workflows (CI/CD, parameter studies, optimization) based on the Modified Compression Field Theory (MCFT).
The implementation faithfully reproduces R2K's algorithms from Bentz (2000) and Collins & Mitchell (1991), enabling automated reinforced concrete design workflows while maintaining compatibility with existing R2T input files.
Core Analysis Engine

    Moment-curvature (M-φ) analysis: Full sectional analysis with Newton-Raphson iteration for strain equilibrium
        Tracks cracking, yield, and ultimate moments
        Supports combined axial load and bending
        Failure detection (concrete crushing, rebar fracture, tendon rupture)
    Material constitutive models:
        Concrete: Popovics, Hognestad, and Collins-Mitchell compression models with MCFT tension stiffening
        Reinforcing steel: Trilinear and bilinear models with strain hardening
        Prestressing steel: Ramberg-Osgood power formula and bilinear models
    Section geometry: Rectangular, Tee, and circular sections with automatic layer discretization

Input/Output

    R2T format parser: Compatible with original Response-2000 text input files
    JSON input/output: Structured format for automation workflows
    CSV export: For post-processing and visualization
    CLI interface: response-yolo run, response-yolo info, --version commands

Cross-Section Management

    Layered concrete discretization for accurate stress integration
    Support for individual rebar bars and layers
    Prestressing tendon support with initial prestrain
    Automatic section property calculations (centroid, gross moment of inertia)

Testing & Examples

    Comprehensive test suite covering materials, geometry, I/O, and analysis
    Example inputs: simple beam, prestressed beam, column with axial load (both R2T and JSON formats)
    Benchmark validation against hand calculations and R2K results

Future Work (Stubs Provided)

    Shear analysis (V-γ) via MCFT
    Moment-shear interaction envelopes (M-V)
    Full member response (load-deflection)
    Pushover analysis

Implementation Details

    Pure Python: No external dependencies beyond stdlib (Python ≥ 3.10)
    Sign convention: Compression negative, tension positive (R2K-compatible)
    Reference axis: Bottom of section (y = 0) by default
    Layered analysis: Horizontal concrete layers with linear strain distribution (plane sections remain plane)
    Convergence: Newton-Raphson iteration with configurable tolerance and max iterations
    Extensible design: Material models and section shapes can be easily extended

