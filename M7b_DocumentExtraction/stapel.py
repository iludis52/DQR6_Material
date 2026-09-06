"""Stapelverarbeitung: ein ganzes Dokument statt einer Beispielseite.

Setzt A1 bis A4 um:

* A1  alle Seiten in einem Lauf,
* A2  beim Wiederaufsetzen fertige Seiten überspringen,
* A3  eine gescheiterte Seite überspringen, den Fehler beifügen, weitermachen,
* A4  je Seite Zeit und Modellversion festhalten (als `Laufspur` im Befund).

Der Lauf ist **stufenweise**: erst alle Seiten durch Stufe 1, dann alle durch
Stufe 2. Der Detektor und das VLM sind damit nie gleichzeitig geladen, die
ONNX-Sitzung wird einmal geöffnet, und die Zeiten je Stufe bleiben trennbar.
Preis: vor dem Ende der Stufe 1 ist keine Seite vollständig.

Seitengrenzen werden nirgends aufgehoben. Eine Seite, ein Befund, eine Datei –
sonst ließe sich später keine Fundstelle mehr auf eine Seite zurückführen.

Die schweren Abhängigkeiten (onnxruntime, requests) werden erst beim
tatsächlichen Bedarf importiert. Ein reiner Stufe-2-Lauf braucht kein
onnxruntime, und dieses Modul lässt sich ohne beides einlesen.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import pymupdf

from schema import (
    SeitenBefund, Stufe, befund_laden, befund_pfad, befund_speichern, ist_fertig,
)

BEFUND_WURZEL = Path("data/interim/befunde")
AUSSCHNITT_WURZEL = Path("data/interim/ausschnitte")
ONNX_STANDARD = Path("models") / "pp_doclayoutv3.onnx"


# --------------------------------------------------------------------- Bericht

@dataclass
class Stufenbericht:
    stufe: Stufe
    verarbeitet: int = 0
    uebersprungen: int = 0
    gescheitert: list[tuple[int, str]] = field(default_factory=list)
    dauer_s: float = 0.0

    def zeile(self) -> str:
        return (f"Stufe {self.stufe.value}: {self.verarbeitet} verarbeitet, "
                f"{self.uebersprungen} übersprungen, {len(self.gescheitert)} "
                f"gescheitert, {self.dauer_s:.1f} s")


@dataclass
class Lauf:
    buch: str
    pdf: Path
    seiten: list[int]
    berichte: list[Stufenbericht] = field(default_factory=list)

    @property
    def gescheitert(self) -> list[tuple[int, str]]:
        return [e for b in self.berichte for e in b.gescheitert]

    def zusammenfassung(self) -> str:
        kopf = f"{self.buch}: {len(self.seiten)} Seiten aus {self.pdf.name}"
        return "\n".join([kopf] + [f"  {b.zeile()}" for b in self.berichte])


# ----------------------------------------------------------------- Hilfsmittel

def seitenzahl(pdf: Path) -> int:
    with pymupdf.open(pdf) as dok:
        return dok.page_count


def _seitenliste(pdf: Path, seiten: Sequence[int] | range | None) -> list[int]:
    """None = alle Seiten. Sonst die angegebenen, 0-basiert wie in PyMuPDF."""
    gesamt = seitenzahl(pdf)
    if seiten is None:
        return list(range(gesamt))
    ausgewaehlt = sorted({int(s) for s in seiten})
    daneben = [s for s in ausgewaehlt if s < 0 or s >= gesamt]
    if daneben:
        raise ValueError(f"Seiten außerhalb des Dokuments ({gesamt} Seiten): {daneben}")
    return ausgewaehlt


def _fehlbefund(pdf: Path, seite: int, dok, fehler: str,
                render_dpi: int) -> SeitenBefund:
    """Platzhalter für eine gescheiterte Seite (A3).

    Trägt keine Blöcke, aber Herkunft und Fehlertext. `ist_fertig` wertet ihn
    als offen, ein späterer Lauf versucht die Seite also erneut.
    """
    breite = hoehe = 0.0
    try:
        rect = dok[seite].rect
        breite, hoehe = float(rect.width), float(rect.height)
    except Exception:
        pass
    return SeitenBefund(
        quelle_datei=pdf.name, seite=seite,
        seite_breite_pt=breite, seite_hoehe_pt=hoehe,
        render_dpi=render_dpi, bild_breite_px=0, bild_hoehe_px=0,
        stufe=Stufe.LAYOUT, fehler=fehler)


def _kurzfehler(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}".strip()[:500]


# ------------------------------------------------------------------- Die Läufe

def stufe1_lauf(pdf: Path, buch: str, seiten: list[int], detektor,
                wurzel: Path = BEFUND_WURZEL, dpi: int = 200,
                schwelle: float = 0.5, neu: bool = False,
                zeige_fortschritt: bool = True) -> Stufenbericht:
    """Layout-Erkennung über alle Seiten. Eine offene Sitzung, ein offenes PDF."""
    bericht = Stufenbericht(stufe=Stufe.LAYOUT)
    t_start = time.perf_counter()

    with pymupdf.open(pdf) as dok:
        for seite in seiten:
            ziel = befund_pfad(wurzel, buch, seite)
            if not neu and ist_fertig(ziel, Stufe.LAYOUT):
                bericht.uebersprungen += 1
                continue
            try:
                befund = detektor.erkenne(pdf, seite=seite, dpi=dpi,
                                          schwelle=schwelle, dok=dok)
                befund_speichern(befund, ziel)
                bericht.verarbeitet += 1
                if zeige_fortschritt:
                    print(f"  S{seite:4d}  {len(befund.bloecke):3d} Blöcke, "
                          f"{befund.spuren[-1].dauer_s:5.2f}s")
            except Exception as e:
                text = _kurzfehler(e)
                bericht.gescheitert.append((seite, text))
                befund_speichern(_fehlbefund(pdf, seite, dok, text, dpi), ziel)
                if zeige_fortschritt:
                    print(f"  S{seite:4d}  ! {text}")

    bericht.dauer_s = time.perf_counter() - t_start
    return bericht


def stufe2_lauf(pdf: Path, buch: str, seiten: list[int], erkenner,
                wurzel: Path = BEFUND_WURZEL,
                ausschnitt_wurzel: Path = AUSSCHNITT_WURZEL,
                neu: bool = False, zeige_fortschritt: bool = True,
                zeige_bloecke: bool = False) -> Stufenbericht:
    """Erkennung über alle Seiten, die Stufe 1 hinter sich haben."""
    bericht = Stufenbericht(stufe=Stufe.ERKANNT)
    t_start = time.perf_counter()
    ausschnitt_dir = ausschnitt_wurzel / buch

    with pymupdf.open(pdf) as dok:
        for seite in seiten:
            ziel = befund_pfad(wurzel, buch, seite)
            if not neu and ist_fertig(ziel, Stufe.ERKANNT):
                bericht.uebersprungen += 1
                continue
            if not ist_fertig(ziel, Stufe.LAYOUT):
                text = "Stufe 1 fehlt oder gescheitert."
                bericht.gescheitert.append((seite, text))
                if zeige_fortschritt:
                    print(f"  S{seite:4d}  ! {text}")
                continue
            try:
                befund = erkenner.erkenne_seite(
                    befund_laden(ziel), pdf, buch,
                    ausschnitt_dir=ausschnitt_dir,
                    zeige_fortschritt=zeige_bloecke, dok=dok)
                befund_speichern(befund, ziel)
                bericht.verarbeitet += 1
                if zeige_fortschritt:
                    mit_text = sum(1 for b in befund.bloecke if b.text)
                    print(f"  S{seite:4d}  {mit_text:3d}/{len(befund.bloecke):3d} "
                          f"Blöcke mit Text, {befund.spuren[-1].dauer_s:5.1f}s")
            except Exception as e:
                text = _kurzfehler(e)
                bericht.gescheitert.append((seite, text))
                # Der Befund der Stufe 1 bleibt erhalten, bekommt aber den Vermerk.
                try:
                    alt = befund_laden(ziel)
                    alt.fehler = text
                    befund_speichern(alt, ziel)
                except Exception:
                    pass
                if zeige_fortschritt:
                    print(f"  S{seite:4d}  ! {text}")

    bericht.dauer_s = time.perf_counter() - t_start
    return bericht


def verarbeite_buch(pdf: Path | str, buch: str | None = None,
                    seiten: Sequence[int] | range | None = None,
                    bis: Stufe = Stufe.ERKANNT,
                    wurzel: Path = BEFUND_WURZEL,
                    ausschnitt_wurzel: Path = AUSSCHNITT_WURZEL,
                    onnx: Path = ONNX_STANDARD,
                    detektor=None, erkenner=None,
                    dpi: int = 200, schwelle: float = 0.5,
                    neu: bool = False, zeige_fortschritt: bool = True,
                    zeige_bloecke: bool = False) -> Lauf:
    """Ein Dokument von vorne bis hinten durch die Pipeline.

    `buch` ist der Ordnername unter `befunde/`; ohne Angabe der Dateiname ohne
    Endung. `bis` sagt, wie weit gelaufen wird – `Stufe.LAYOUT` macht nur die
    Layout-Erkennung, ohne LM Studio überhaupt anzusprechen.

    `detektor` und `erkenner` können übergeben werden, um sie über mehrere
    Läufe hinweg wiederzuverwenden oder im Test zu ersetzen. Ohne Angabe
    werden sie hier erzeugt – und nur dann werden die schweren Abhängigkeiten
    importiert.
    """
    pdf = Path(pdf)
    if not pdf.exists():
        raise FileNotFoundError(pdf)
    buch = buch or pdf.stem
    liste = _seitenliste(pdf, seiten)
    lauf = Lauf(buch=buch, pdf=pdf, seiten=liste)

    if zeige_fortschritt:
        print(f"{buch}: {len(liste)} Seiten aus {pdf.name}\n--- Stufe 1")

    if detektor is None:
        from layout import Detektor          # zieht onnxruntime erst hier herein
        detektor = Detektor(onnx)
    lauf.berichte.append(stufe1_lauf(
        pdf, buch, liste, detektor, wurzel=wurzel, dpi=dpi, schwelle=schwelle,
        neu=neu, zeige_fortschritt=zeige_fortschritt))

    if bis.value >= Stufe.ERKANNT.value:
        if zeige_fortschritt:
            print("--- Stufe 2")
        if erkenner is None:
            from erkennung import Erkenner   # zieht requests erst hier herein
            erkenner = Erkenner()
        lauf.berichte.append(stufe2_lauf(
            pdf, buch, liste, erkenner, wurzel=wurzel,
            ausschnitt_wurzel=ausschnitt_wurzel, neu=neu,
            zeige_fortschritt=zeige_fortschritt, zeige_bloecke=zeige_bloecke))

    if zeige_fortschritt:
        print("---")
        print(lauf.zusammenfassung())
        if lauf.gescheitert:
            print("\nGescheiterte Seiten:")
            for seite, text in lauf.gescheitert:
                print(f"  S{seite:4d}  {text}")

    return lauf


def offene_seiten(pdf: Path | str, buch: str | None = None,
                  bis: Stufe = Stufe.ERKANNT,
                  wurzel: Path = BEFUND_WURZEL) -> list[int]:
    """Welche Seiten fehlen noch? Beantwortet A2, ohne etwas zu rechnen."""
    pdf = Path(pdf)
    buch = buch or pdf.stem
    return [s for s in range(seitenzahl(pdf))
            if not ist_fertig(befund_pfad(wurzel, buch, s), bis)]
