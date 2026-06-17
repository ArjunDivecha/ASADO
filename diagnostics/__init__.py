"""ASADO diagnostics package.

spectral.py — spectral diagnostics (source conditions, Marchenko-Pastur edges,
effective rank) per docs/SPECTRAL_DIAGNOSTICS.md.
"""

from diagnostics.spectral import (  # noqa: F401
    source_condition_slope,
    mp_edges,
    effective_rank,
    eigenspectrum,
    panel_report,
)
