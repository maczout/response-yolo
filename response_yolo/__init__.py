"""
response-yolo: Python clone of Response-2000 (R2K)
===================================================

A faithful replica of Evan Bentz's Response-2000 reinforced concrete
sectional analysis software, built around the Modified Compression
Field Theory (MCFT) by Vecchio & Collins (1986).

Currently implements:
  - Sectional moment-curvature (M-phi) analysis
  - Full MCFT / Popovics / Hognestad concrete models
  - Bilinear and trilinear reinforcing steel models
  - Ramberg-Osgood prestressing strand model
  - R2T input file parsing and JSON I/O

Planned (stubs provided):
  - Sectional shear analysis (V-gamma)
  - Moment-shear interaction (M-V)
  - Full member response analysis
  - Pushover / load-deformation analysis
"""

__version__ = "0.1.0"
__codename__ = "yolo"  # You Only Layer Once
