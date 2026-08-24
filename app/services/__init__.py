"""Service package initialization for NarrativeForge.

The mixcut feature branch installs a small retrieval-planning wrapper around the
existing ordered stock downloader. Keeping the hook here lets the experiment reuse
all existing provider/cache/download behavior without changing unrelated retrieval
modes. Once the MVP is validated, the wrapper can be folded into material.py.
"""

from app.services import material as _material
from app.services import material_retrieval as _material_retrieval

_material_retrieval.install(_material)
