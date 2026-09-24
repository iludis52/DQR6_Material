"""Projektpolitik der Bildstufe – kalibrierte Schwellen aus
`image_optimization_calibration.v04.ipynb`, unverändert übernommen."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field


def _quality() -> dict[str, float]:
    return {
        "photo_ssim_min": 0.88,
        "mixed_ssim_min": 0.90,
        "graphic_ssim_min": 0.93,
        "edge_f1_min": 0.80,
        "bilevel_edge_f1_min": 0.86,
        "component_retention_min": 0.80,
        "color_deltae_mean_max": 6.0,
        "color_deltae_p95_max": 16.0,
        "preferred_graphic_ssim_min": 0.96,
        "preferred_edge_f1_min": 0.90,
        "preferred_component_retention_min": 0.90,
        "preferred_color_deltae_mean_max": 4.0,
        "preferred_color_deltae_p95_max": 10.0,
    }


def _classifier() -> dict[str, float]:
    return {
        "grayscale_distance_max": 0.020,
        "bilevel_extreme_fraction_min": 0.90,
        "bilevel_midtone_fraction_max": 0.08,
        "graphic_flat_area_min": 0.30,
        "graphic_edge_density_min": 0.12,
        "graphic_extreme_fraction_min": 0.45,
        "graphic_low_entropy_max": 0.78,
    }


@dataclass
class BildKonfig:
    # --- harte Projektpolitik
    max_ppi: int = 144
    allow_upscale: bool = False
    min_saving_ratio: float = 0.10

    jpeg_qualities: list[int] = field(default_factory=lambda: [85, 75, 65, 55, 45])
    png_palette_sizes: list[int] = field(
        default_factory=lambda: [2, 4, 8, 16, 32, 64, 128, 256])
    # Farbige technische Grafiken nie mit 2/4/8-Farben-Paletten.
    color_graphic_min_palette_colors: int = 16

    enable_pngquant: bool = True
    pngquant_binary: str | None = field(default_factory=lambda: shutil.which("pngquant"))
    pngquant_speed: int = 1
    pngquant_quality_profiles: list[tuple[int, int]] = field(
        default_factory=lambda: [(85, 100), (75, 95)])

    quality: dict[str, float] = field(default_factory=_quality)
    classifier: dict[str, float] = field(default_factory=_classifier)
    feature_max_side: int = 768

    # --- Metadaten
    metadata_language: str = "de"
    docrag_namespace_uri: str = "urn:docrag:metadata:1.0"
    docrag_schema_version: str = "1.0"

    # --- Vision-Modell über LM Studio
    enable_llm: bool = True
    lm_base_url: str = "http://localhost:1234/v1"
    lm_model: str = "google/gemma-4-12b"
    lm_timeout_s: float = 180
    lm_temperature: float = 0.1
    lm_max_tokens: int = 1200
    # Entfernter Anbieter (z. B. DeepInfra): Schlüssel nie in repr/Manifest.
    lm_api_key: str | None = field(default=None, repr=False)
    lm_extra_body: dict = field(default_factory=dict)   # z. B. {"reasoning_effort": "none"}
    max_keywords: int = 12
    max_alt_text_chars: int = 250
    kontext_zeichen: int = 1800

    # --- Verhalten
    # Bereits mit docrag-XMP versehene Bilder nicht erneut (verlustbehaftet)
    # kodieren und nicht erneut beschreiben lassen.
    erzwingen: bool = False
    # Beschreibung zusätzlich als Absatz unter das Bild ins Markdown schreiben
    # (so wie docling es beim Export von meta.description tut). Für reine
    # Text-Retriever hilfreich, verändert aber den Fließtext.
    beschreibung_ins_markdown: bool = False
