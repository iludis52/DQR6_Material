"""Eine Konfiguration für alle Stufen, als JSON im Projekt-Root abgelegt.

Bisher standen LM-Studio-Adresse und Modell in jedem Notebook separat
(Stufe 1: localhost, Stufe 2/3: 192.168.178.27) – eine Änderung musste an
drei Stellen nachgezogen werden.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import pfade
from .deepinfra import STANDARD_LEKTORAT, STANDARD_VISION

KONFIG_DATEI = pfade.PROJEKT / "pipeline_config.json"


@dataclass
class PipelineKonfig:
    # --- Stufe 1: OCR (PaddleOCR-VL)
    ocr_url: str = "http://localhost:1234/v1"
    ocr_modell: str = ""                      # leer = automatisch (paddleocr im Namen)
    ocr_zeitlimit_s: int = 300
    layout_schwelle: float = 0.5

    # --- Stufe 2: Lektorat
    lektorat_anbieter: str = "lmstudio"       # "lmstudio" | "deepinfra"
    lektorat_deepinfra_modell: str = STANDARD_LEKTORAT
    lektorat_url: str = "http://192.168.178.27:1234/v1"
    lektorat_modell: str = "google/gemma-4-12b"
    lektorat_zeitlimit_s: float = 300.0
    lektorat_max_output_tokens: int = 4096
    lektorat_max_context_tokens: int = 21000
    lektorat_context_reserve_tokens: int = 2500
    lektorat_text_chunk_tokens: int = 2000
    lektorat_table_chunk_tokens: int = 2500
    lektorat_structure_chunk_tokens: int = 2500
    lektorat_caption_chunk_tokens: int = 2000
    lektorat_overlap_blocks: int = 2
    lektorat_retry_count: int = 2

    # --- Stufe 3: Bilder
    vision_anbieter: str = "lmstudio"         # "lmstudio" | "deepinfra"
    vision_deepinfra_modell: str = STANDARD_VISION
    vision_url: str = "http://192.168.178.27:1234/v1"
    vision_modell: str = "google/gemma-4-12b"
    vision_aktiv: bool = True
    bild_max_ppi: int = 144
    beschreibung_ins_markdown: bool = False

    # --- Ernte
    ergebnis_ordner: str = ""                 # leer = <Projekt>/ergebnisse

    @property
    def ergebnis_pfad(self) -> Path:
        return Path(self.ergebnis_ordner).expanduser() if self.ergebnis_ordner else pfade.ERGEBNISSE

    # ------------------------------------------------------------ Ablage

    @classmethod
    def laden(cls, pfad: Path = KONFIG_DATEI) -> "PipelineKonfig":
        if not pfad.is_file():
            return cls()
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        bekannt = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in daten.items() if k in bekannt})

    def speichern(self, pfad: Path = KONFIG_DATEI) -> Path:
        pfad.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return pfad

    # ------------------------------------------------------------ Ableitungen

    def zugang(self, stufe: str) -> tuple[str, str, str | None, dict]:
        """(URL, Modell, API-Key, Zusatzparameter) für 'lektorat' oder 'vision'.

        Der DeepInfra-Schlüssel kommt aus der Sitzung (`deepinfra.schluessel`)
        und steht nie in dieser Konfiguration.
        """
        from . import deepinfra
        if getattr(self, f"{stufe}_anbieter") == "deepinfra":
            key = deepinfra.schluessel()
            if not key:
                raise RuntimeError("DeepInfra gewählt, aber kein API-Key gesetzt "
                                   "(Oberfläche → Einstellungen, oder DEEPINFRA_API_KEY).")
            modell = getattr(self, f"{stufe}_deepinfra_modell")
            return deepinfra.BASIS_URL, modell, key, deepinfra.ohne_reasoning(modell)
        return getattr(self, f"{stufe}_url"), getattr(self, f"{stufe}_modell"), None, {}

    def lektorat_app_config(self, md: Path, *, neu_beginnen: bool = False):
        from markdown_lektorat.lekt_config import (
            AppConfig, ConfidenceConfig, InputConfig, LMStudioConfig, OutputConfig,
            ProcessingConfig, ThresholdPolicy,
        )
        url, modell, key, extra = self.zugang("lektorat")
        return AppConfig(
            input=InputConfig(document_path=md),
            lm=LMStudioConfig(base_url=url, model=modell, api_key=key, extra_body=extra,
                              timeout=self.lektorat_zeitlimit_s,
                              max_output_tokens=self.lektorat_max_output_tokens),
            processing=ProcessingConfig(
                max_context_tokens=self.lektorat_max_context_tokens,
                context_reserve_tokens=self.lektorat_context_reserve_tokens,
                text_chunk_tokens=self.lektorat_text_chunk_tokens,
                table_chunk_tokens=self.lektorat_table_chunk_tokens,
                structure_chunk_tokens=self.lektorat_structure_chunk_tokens,
                caption_chunk_tokens=self.lektorat_caption_chunk_tokens,
                overlap_blocks=self.lektorat_overlap_blocks,
                retry_count=self.lektorat_retry_count,
                resume=not neu_beginnen,
            ),
            confidence=ConfidenceConfig(default=ThresholdPolicy()),
            output=OutputConfig(overwrite=neu_beginnen),
        )

    def bild_konfig(self):
        from bild_optimierung.bild_konfig import BildKonfig
        url, modell, key, extra = self.zugang("vision") if self.vision_aktiv \
            else (self.vision_url, self.vision_modell, None, {})
        return BildKonfig(max_ppi=self.bild_max_ppi, enable_llm=self.vision_aktiv,
                          lm_base_url=url, lm_model=modell, lm_api_key=key, lm_extra_body=extra,
                          beschreibung_ins_markdown=self.beschreibung_ins_markdown)
