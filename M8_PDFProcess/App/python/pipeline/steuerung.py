"""Die drei Stufen als Funktionen – dieselben Aufrufe für Notebook und Oberfläche.

    stufe1(...)  PDF -> Befunde -> <BUCH>.json / <BUCH>.md / <BUCH>_artifacts/
    stufe2(...)  <BUCH>.md -> <BUCH>_korr.md (+ _review.md)
    stufe3(...)  Bilder optimieren, beschreiben, XMP; beide Markdown-Fassungen nachziehen

Fortschritt geht über `print`; die Oberfläche fängt ihn je Lauf ab.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Callable

import pfade
from . import arbeitsbereich
from .konfig import PipelineKonfig

_DETEKTOR = None     # ONNX-Sitzung über Läufe hinweg wiederverwenden


def _md_hash(buch: str) -> str | None:
    md = pfade.dokument_md(buch)
    return sha256(md.read_bytes()).hexdigest() if md.is_file() else None


def detektor():
    global _DETEKTOR
    if _DETEKTOR is None:
        from layout import Detektor
        _DETEKTOR = Detektor(pfade.ONNX_STANDARD)
    return _DETEKTOR


def erkenner(konfig: PipelineKonfig):
    from erkennung import Erkenner
    return Erkenner(url=konfig.ocr_url, modell_id=konfig.ocr_modell or None,
                    zeitlimit=konfig.ocr_zeitlimit_s)


def modelle(url: str) -> list[str]:
    """Modell-IDs eines LM-Studio-Servers (für Auswahllisten)."""
    import requests
    antwort = requests.get(f"{url.rstrip('/')}/models", timeout=5)
    antwort.raise_for_status()
    return [m["id"] for m in antwort.json().get("data", [])]


# ------------------------------------------------------------ Stufe 1

def stufe1(konfig: PipelineKonfig, buecher: list[str] | None = None, *,
           neu: bool = False, zeige_fortschritt: bool = True):
    """Eingangsprüfung, Layout, OCR, kanonisches Dokument – je Dokument."""
    import lauf
    from schema import Stufe

    vorher = {b: _md_hash(b) for b in (buecher or arbeitsbereich.buecher())}
    print("Stufe 1: Layout + OCR + Docling")
    bericht = lauf.verarbeite_alle(
        bis=Stufe.KANONISCH, neu=neu, detektor=detektor(), erkenner=erkenner(konfig),
        zeige_fortschritt=zeige_fortschritt, nur=buecher)
    print(bericht.zusammenfassung())

    # Neu erzeugtes Markdown entwertet Lektorat und Bildstufe des alten.
    for buch, alt in vorher.items():
        if alt is not None and _md_hash(buch) != alt:
            weg = arbeitsbereich.abgeleitetes_verwerfen(buch)
            if weg:
                print(f"{buch}: Markdown neu erzeugt – verworfen: {', '.join(weg)}")
    return bericht


# ------------------------------------------------------------ Stufe 2

def stufe2(konfig: PipelineKonfig, buch: str, *, neu_beginnen: bool = False,
           fortschritt: Callable[[str], None] | None = print):
    from markdown_lektorat import lekt_lauf, lekt_llm

    md = pfade.dokument_md(buch)
    if not md.is_file():
        raise FileNotFoundError(f"{md} fehlt – erst Stufe 1 laufen lassen.")
    zustand = arbeitsbereich.lektorat_zustand(buch)
    if zustand == "veraltet":
        print(f"{buch}: Checkpoint gehört zu einer älteren Fassung von {md.name} – Neubeginn.")
        neu_beginnen = True
    if zustand == "fertig" and not neu_beginnen:
        print(f"{buch}: Lektorat bereits abgeschlossen ({pfade.dokument_korr_md(buch).name}).")
        return None

    config = konfig.lektorat_app_config(md, neu_beginnen=neu_beginnen)
    client = lekt_llm.LMStudioOpenAIClient(config.lm, retry_count=config.processing.retry_count)
    print(f"Stufe 2: Lektorat {buch} mit {config.lm.model} @ {config.lm.base_url}")
    ergebnis = lekt_lauf.correct_markdown(config, client=client, fortschritt=fortschritt,
                                          modellwechsel_erlauben=True)
    unresolved = sum(e.status == "unresolved" for e in ergebnis.entries)
    angewendet = sum(e.status == "applied" for e in ergebnis.entries)
    review = sum(e.status == "review" for e in ergebnis.entries)
    print(f"{buch}: {angewendet} Korrekturen angewendet, {review} zur Durchsicht, "
          f"{unresolved} ungeklärt -> {ergebnis.corrected_path.name}")
    return ergebnis


# ------------------------------------------------------------ Stufe 3

def stufe3(konfig: PipelineKonfig, buch: str, *, erzwingen: bool = False,
           ohne_lektorat: bool = False, fortschritt: Callable[[str], None] | None = print):
    from bild_optimierung.bild_lauf import optimiere_dokument

    zustand = arbeitsbereich.lektorat_zustand(buch)
    if zustand in ("unterbrochen", "veraltet"):
        # Die Bildstufe schreibt <BUCH>.md um; ein offener Lektorat-Checkpoint
        # passte danach nicht mehr zur Quelle und ließe sich nicht fortsetzen.
        raise RuntimeError(f"{buch}: Lektorat ist {zustand} – erst Stufe 2 abschließen.")
    if zustand == "fehlt" and not ohne_lektorat:
        raise RuntimeError(f"{buch}: noch kein Lektorat. Erst Stufe 2 – oder "
                           "`ohne_lektorat=True`, um nur die OCR-Fassung zu bearbeiten.")
    cfg = konfig.bild_konfig()
    cfg.erzwingen = erzwingen
    print(f"Stufe 3: Bilder {buch}")
    return optimiere_dokument(pfade.dokument_ordner(buch), buch, cfg, fortschritt=fortschritt)


# ------------------------------------------------------------ alles

def gesamtlauf(konfig: PipelineKonfig, buecher: list[str] | None = None, *,
               stufen: tuple[int, ...] = (1, 2, 3), ernten: bool = False,
               stufe1_neu: bool = False, lektorat_neu: bool = False,
               bilder_erzwingen: bool = False) -> bool:
    """Die gewählten Stufen für die gewählten Dokumente; optional ernten und zurücksetzen.

    Ein gescheitertes Dokument hält die anderen nicht auf. Geerntet (und dann
    zurückgesetzt) wird nur, wenn alles fehlerfrei durchlief.
    """
    buecher = buecher or arbeitsbereich.buecher()
    if not buecher:
        print("Keine Dokumente unter data/raw.")
        return False
    fehler: dict[str, str] = {}

    if 1 in stufen:
        try:
            bericht = stufe1(konfig, buecher, neu=stufe1_neu)
        except Exception as exc:          # etwa: LM Studio nicht erreichbar
            print(f"! Stufe 1 nicht gestartet: {type(exc).__name__}: {exc}")
            return False
        fehler.update({d.dok: d.fehler or "gescheitert" for d in bericht.gescheitert})
    for buch in buecher:
        if buch in fehler:
            continue
        try:
            if 2 in stufen:
                stufe2(konfig, buch, neu_beginnen=lektorat_neu)
            if 3 in stufen:
                ergebnis = stufe3(konfig, buch, erzwingen=bilder_erzwingen,
                                  ohne_lektorat=2 not in stufen)
                if ergebnis.probleme:
                    fehler[buch] = f"{len(ergebnis.probleme)} Problem(e) in der Bildstufe"
        except Exception as exc:
            fehler[buch] = f"{type(exc).__name__}: {exc}"
            print(f"! {buch}: {fehler[buch]}")

    print("\n=== Ergebnis")
    for buch in buecher:
        print(f"  {buch}: {'FEHLER – ' + fehler[buch] if buch in fehler else 'ok'}")
    if fehler:
        print("Nicht geerntet, Arbeitsbereich bleibt erhalten (Wiederaufnahme möglich).")
        return False
    if ernten:
        ernte_liste, zurueck = arbeitsbereich.ernten_und_zuruecksetzen(konfig.ergebnis_pfad)
        for e in ernte_liste:
            print(f"  Ernte {e.buch}: {e.ziel or '-'}" + (f"  ! {'; '.join(e.probleme)}" if e.probleme else ""))
        print("Arbeitsbereich zurückgesetzt." if zurueck else "Nicht zurückgesetzt (Ernte unvollständig).")
        return zurueck
    return True
