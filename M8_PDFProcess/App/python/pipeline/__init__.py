"""Gemeinsame Steuerung der drei Pipeline-Stufen und des Arbeitsbereichs.

Die Module unter `python/pdf_extraction/` importieren sich gegenseitig flach
(`import pfade`); deshalb kommt ihr Ordner hier einmalig in den Suchpfad.
"""

from __future__ import annotations

import sys
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parents[1]
for _ordner in (PYTHON_DIR, PYTHON_DIR / "pdf_extraction"):
    if str(_ordner) not in sys.path:
        sys.path.insert(0, str(_ordner))
