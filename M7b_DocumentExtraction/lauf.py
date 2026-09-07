"""Erfassung, Eingangsprüfung und Dokumentenlauf (plan.md 6).

`erfassen` und `pruefen` decken T5: den Eingangsbestand vollständig als
Arbeitsliste führen (SR-01) und vor jeder Verarbeitung sowohl das
Namensregelwerk (SR-02 bis SR-04, über `pfade.namen_pruefen`) als auch die
rein technische Öffnungsprüfung (SR-05) über den **ganzen** Bestand laufen
lassen, bevor irgendetwas angelegt wird. Beide Prüfungen fassen keinen
Seiteninhalt an – das leistet Stufe 1 ohnehin, seitenweise und mit
Übergehen statt Abbruch (plan.md 5.2).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pymupdf

import pfade
import stapel
from schema import Stufe, ist_fertig


def erfassen(wurzel: Path = pfade.RAW) -> list[Path]:
    """SR-01: der Eingangsbestand als Arbeitsliste.

    Ohne Rekursion – ein Unterordner unter `raw/` ist kein Quelldokument,
    sondern ein Versehen. Die Endung wird ohne Rücksicht auf Groß-/Klein-
    schreibung erkannt, weil ein Glob-Muster `*.pdf` unter Windows/macOS
    (case-insensitives Dateisystem) anders träfe als unter Linux – die
    Erfassung soll überall dieselben Dateien finden, die Beanstandung der
    falschen Schreibweise übernimmt `pfade.namen_pruefen`.
    """
    return sorted(p for p in wurzel.iterdir()
                 if p.is_file() and p.suffix.lower() == ".pdf")


def _technische_pruefung(pfad: Path) -> list[str]:
    """SR-05: nur Öffnen, `needs_pass`/`is_encrypted`, `page_count`.

    Keine Prüfung, die Seiteninhalte anfasst (plan.md 5.2) – eine
    Integritätsprüfung über alle Seiten kostet in der Größenordnung eines
    Layoutlaufs und beantwortet eine Frage, die Stufe 1 ohnehin seitenweise
    beantwortet, dort mit Übergehen der Seite statt mit einem Abbruch am
    Eingang.
    """
    try:
        with pymupdf.open(pfad) as dok:
            if dok.needs_pass or dok.is_encrypted:
                return ["Zugangsgeschützt (Kennwort erforderlich)."]
            if dok.page_count <= 0:
                return ["Enthält keine Seiten."]
    except Exception as e:
        return [f"Lässt sich nicht als PDF öffnen ({type(e).__name__}: {e})."]
    return []


def pruefen(dateien: list[Path]) -> dict[Path, list[str]]:
    """Namensregelwerk (SR-02 bis SR-04) und technische Prüfung (SR-05)
    über den ganzen Bestand, in einem Durchgang gemeinsam ermittelt
    (plan.md 5.3). Nur beanstandete Pfade erscheinen im Ergebnis.
    """
    ergebnis: dict[Path, list[str]] = {
        pfad: list(gruende) for pfad, gruende in pfade.namen_pruefen(dateien).items()
    }
    for pfad in dateien:
        technisch = _technische_pruefung(pfad)
        if technisch:
            ergebnis.setdefault(pfad, []).extend(technisch)
    return ergebnis


# ---------------------------------------------------------- Dokumentenlauf

def offene_dokumente(dateien: list[Path], bis: Stufe) -> list[str]:
    """SR-09: welche Dokumente aus `dateien` sind bei Stufe `bis` noch offen?

    Bei `bis=Stufe.KANONISCH` genügt die Existenz des einen Zielartefakts
    (`pfade.dokument_json`) – keine Seitendatei wird dafür geöffnet. Für
    eine frühere Stufe gibt es kein einzelnes Zielartefakt; dort entscheidet
    `schema.ist_fertig` je Seite, und `all(...)` hält beim ersten offenen
    Ergebnis an, ohne die restlichen Seiten dieses Dokuments noch zu laden.
    """
    offene: list[str] = []
    for pdf in dateien:
        buch = pdf.stem
        if bis.value >= Stufe.KANONISCH.value:
            if not pfade.dokument_json(buch).exists():
                offene.append(buch)
            continue

        anzahl = stapel.seitenzahl(pdf)
        if not all(ist_fertig(pfade.befund(buch, seite), bis)
                  for seite in range(anzahl)):
            offene.append(buch)
    return offene


@dataclass
class Dokumentbericht:
    dok: str
    zustand: Literal["fertig", "gescheitert"]
    dauer_s: float
    fehler: str | None = None


@dataclass
class Laufbericht:
    dokumente: list[Dokumentbericht] = field(default_factory=list)

    @property
    def gescheitert(self) -> list[Dokumentbericht]:
        return [d for d in self.dokumente if d.zustand == "gescheitert"]

    def zusammenfassung(self) -> str:
        zeilen = []
        for d in self.dokumente:
            zeile = f"{d.dok}: {d.zustand}, {d.dauer_s:.1f}s"
            if d.fehler:
                zeile += f" – {d.fehler}"
            zeilen.append(zeile)
        return "\n".join(zeilen)


def verarbeite_alle(bis: Stufe = Stufe.KANONISCH, neu: bool = False,
                    detektor=None, erkenner=None,
                    zeige_fortschritt: bool = True) -> Laufbericht:
    """SR-01, SR-06, SR-07: der ganze Bestand in einem Aufruf.

    Prüft zuerst den ganzen Bestand (SR-02 bis SR-05) und hält bei jeder
    Beanstandung an, bevor irgendetwas angelegt wird (SR-04). Erst danach
    läuft je Dokument der bestehende Stufenlauf aus `stapel.py`; dessen
    Seitenlogik bleibt unangetastet.

    Detektor und Erkenner werden einmal erzeugt und über alle Dokumente
    weitergereicht (SR-06), statt sie je Dokument neu zu bauen – Layout-
    Modell und Sprachmodell bleiben dabei trotzdem nacheinander geladen,
    weil `stapel.py` weiterhin stufenweise über die Seiten läuft.

    Ein Dokument, dessen Stufenlauf eine gescheiterte Seite oder eine
    unerwartete Ausnahme meldet, wird vermerkt und übersprungen (SR-07);
    die übrigen Dokumente werden trotzdem verarbeitet.

    Ein bereits abgeschlossenes Dokument (SR-09, `offene_dokumente`) wird
    nicht einmal an `stapel.verarbeite_buch` übergeben – ein zweiter Lauf
    über einen fertigen Bestand rührt nichts an, statt jede Seite erneut
    als "schon fertig" zu bestätigen oder die kanonische Stufe klaglos
    neu zu erzeugen. `neu=True` erzwingt trotzdem einen vollständigen Lauf.
    """
    dateien = erfassen()
    beanstandungen = pruefen(dateien)
    if beanstandungen:
        meldung = "\n".join(
            f"{pfad.name}: {grund}"
            for pfad in sorted(beanstandungen)
            for grund in beanstandungen[pfad])
        raise ValueError(
            f"{len(beanstandungen)} Datei(en) beanstandet, "
            f"nichts wurde verarbeitet:\n{meldung}")

    offen = {pdf.stem for pdf in dateien} if neu else set(offene_dokumente(dateien, bis))

    bericht = Laufbericht()
    for pdf in dateien:
        if pdf.stem not in offen:
            bericht.dokumente.append(Dokumentbericht(
                dok=pdf.stem, zustand="fertig", dauer_s=0.0))

    zu_verarbeiten = [pdf for pdf in dateien if pdf.stem in offen]
    if not zu_verarbeiten:
        return bericht

    if detektor is None:
        from layout import Detektor          # zieht onnxruntime erst hier herein
        detektor = Detektor(pfade.ONNX_STANDARD)
    if erkenner is None and bis.value >= Stufe.ERKANNT.value:
        from erkennung import Erkenner       # zieht requests erst hier herein
        erkenner = Erkenner()

    for pdf in zu_verarbeiten:
        buch = pdf.stem
        t0 = time.perf_counter()
        try:
            teillauf = stapel.verarbeite_buch(
                pdf, buch=buch, bis=bis, detektor=detektor, erkenner=erkenner,
                neu=neu, zeige_fortschritt=zeige_fortschritt)
            if teillauf.gescheitert:
                fehler = "; ".join(f"S{s}: {t}" for s, t in teillauf.gescheitert)
                bericht.dokumente.append(Dokumentbericht(
                    dok=buch, zustand="gescheitert",
                    dauer_s=time.perf_counter() - t0, fehler=fehler))
                continue

            if bis.value >= Stufe.KANONISCH.value:
                import kanonisch              # zieht docling-core erst hier herein
                kanonisch.buch_umwandeln(buch, zeige_bericht=zeige_fortschritt)

            bericht.dokumente.append(Dokumentbericht(
                dok=buch, zustand="fertig", dauer_s=time.perf_counter() - t0))
        except Exception as e:
            bericht.dokumente.append(Dokumentbericht(
                dok=buch, zustand="gescheitert", dauer_s=time.perf_counter() - t0,
                fehler=f"{type(e).__name__}: {e}"))

    return bericht
