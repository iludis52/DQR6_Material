"""T0 — Prüfstand (tasks.md).

Baut unter einem temporären Verzeichnis den in T0 benannten Fehlerbestand
auf: zwei gültige Dokumente und je Fehlerart aus SR-02 bis SR-05 mindestens
eine Datei. Dazu zwei Attrappen für `layout.Detektor` und `erkennung.Erkenner`,
die dieselbe Schnittstelle bedienen, aber ohne ONNX-Sitzung und ohne LM
Studio auskommen – der Stufenlauf aus `stapel.py` kann sie unverändert
entgegennehmen.

Dieses Modul ist Testinfrastruktur für T1 bis T10, keine Pipeline-Stufe, und
taucht deshalb nicht im Modulschnitt aus plan.md Abschnitt 3 auf.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pymupdf

from schema import Bbox, Bezugsrahmen, Block, Lesekante, SeitenBefund, Stufe

# --------------------------------------------------- Namen des Prüfbestands

GUELTIG_LEHRBUCH = "Lehrbuch.pdf"
GUELTIG_ZWEITES_BUCH = "zweites_buch.pdf"
UNGUELTIGE_ZEICHEN = "Buch mit Leerzeichen.pdf"
NICHT_ASCII = "Ökonomie.pdf"
FUEHRENDER_STRICH = "-fuehrender_strich.pdf"
# 49 Zeichen im Stamm – einer mehr als MAX_STAMM = 48 (plan.md 5.1). Der
# Grenzfall ist der Zweck der Datei, nicht eine beliebig gewählte Länge.
ZU_LANG = ("a" * 49) + ".pdf"
GROSS_KLEIN_KOLLISION = "Lehrbuch.PDF"
RESERVIERTER_NAME = "CON.pdf"
GESCHUETZT = "geschuetzt.pdf"
LEER = "leer.pdf"
KAPUTT = "kaputt.pdf"

ALLE_DATEINAMEN = [
    GUELTIG_LEHRBUCH, GUELTIG_ZWEITES_BUCH, UNGUELTIGE_ZEICHEN, NICHT_ASCII,
    FUEHRENDER_STRICH, ZU_LANG, GROSS_KLEIN_KOLLISION, RESERVIERTER_NAME,
    GESCHUETZT, LEER, KAPUTT,
]


# --------------------------------------------------------------- PDF-Bausteine

def _gueltiges_pdf(pfad: Path, seiten: int) -> None:
    """Unverschlüsselte PDF-Datei mit `seiten` Seiten, jede mit etwas Inhalt."""
    dok = pymupdf.open()
    for i in range(seiten):
        seite = dok.new_page()
        seite.insert_text((72, 72), f"{pfad.stem} – Seite {i + 1}")
    dok.save(pfad)
    dok.close()


def _leere_pdf(pfad: Path) -> None:
    """0 Seiten. PyMuPDF verweigert `save()` bei einem leeren Seitenbaum
    (``ValueError: cannot save with zero pages``) – deshalb von Hand
    geschrieben: minimal, aber syntaktisch ein gültiges PDF mit Count 0."""
    pfad.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"trailer\n<< /Size 3 /Root 1 0 R >>\n%%EOF\n"
    )


def _geschuetztes_pdf(pfad: Path, kennwort: str = "geheim") -> None:
    dok = pymupdf.open()
    dok.new_page()
    dok.save(pfad, encryption=pymupdf.PDF_ENCRYPT_AES_256,
              user_pw=kennwort, owner_pw=kennwort)
    dok.close()


def _kaputte_pdf(pfad: Path) -> None:
    """Textdatei mit `.pdf`-Endung – die Endung allein macht kein PDF daraus."""
    pfad.write_text(
        "Das ist keine PDF-Datei, nur eine Textdatei mit falscher Endung.\n",
        encoding="utf-8")


# ------------------------------------------------------------------- Bestand

@contextlib.contextmanager
def pruefbestand() -> Iterator[Path]:
    """Legt den Prüfbestand aus T0 an und räumt ihn danach wieder weg.

    Kontextmanager statt einer bloßen Erzeugungsfunktion, damit „entsteht und
    verschwindet wieder" (T0, Fertig-Kriterium) nicht vom Aufrufer separat
    sichergestellt werden muss – auch nicht bei einer Ausnahme im Testlauf.
    """
    with TemporaryDirectory(prefix="probelauf_p0_") as tmp:
        wurzel = Path(tmp)
        _gueltiges_pdf(wurzel / GUELTIG_LEHRBUCH, 3)
        _gueltiges_pdf(wurzel / GUELTIG_ZWEITES_BUCH, 2)
        _gueltiges_pdf(wurzel / UNGUELTIGE_ZEICHEN, 1)
        _gueltiges_pdf(wurzel / NICHT_ASCII, 1)
        _gueltiges_pdf(wurzel / FUEHRENDER_STRICH, 1)
        _gueltiges_pdf(wurzel / ZU_LANG, 1)
        _gueltiges_pdf(wurzel / GROSS_KLEIN_KOLLISION, 1)
        _gueltiges_pdf(wurzel / RESERVIERTER_NAME, 1)
        _geschuetztes_pdf(wurzel / GESCHUETZT)
        _leere_pdf(wurzel / LEER)
        _kaputte_pdf(wurzel / KAPUTT)
        yield wurzel


# ------------------------------------------------ Attrappen für Stufe 1 und 2

# Schlüssel: Dateiname (`SeitenBefund.quelle_datei`). Wert: die Menge der
# Seiten, die scheitern sollen, oder `None` für das ganze Dokument – dann
# scheitert jede seiner Seiten.
Schalter = dict[str, "set[int] | None"]


def _soll_scheitern(schalter: Schalter, dokument: str, seite: int) -> bool:
    if dokument not in schalter:
        return False
    seiten = schalter[dokument]
    return seiten is None or seite in seiten


class DetektorAttrappe:
    """Ersetzt `layout.Detektor`: keine ONNX-Sitzung, kein Rendern.

    Liefert je Seite genau zwei fest verortete Blöcke – eine Überschrift,
    einen Textblock – in Lesereihenfolge. Der Schalter `scheitern_bei` löst
    an der genannten Seite (oder, mit `None`, an jeder Seite eines
    genannten Dokuments) eine Ausnahme aus, bevor ein Befund entsteht.

    `erzeugungen` zählt Konstruktionen dieser Klasse (T6: Nachweis, dass
    `lauf.verarbeite_alle` den Detektor einmal erzeugt und über alle
    Dokumente weiterreicht, statt ihn je Dokument neu zu bauen). Klassenweit,
    nicht je Instanz – ein Test liest die Differenz vor/nach seinem Lauf.
    """

    erzeugungen: int = 0

    def __init__(self, scheitern_bei: Schalter | None = None):
        DetektorAttrappe.erzeugungen += 1
        self.scheitern_bei: Schalter = scheitern_bei or {}

    def erkenne(self, pfad: Path, seite: int = 0, dpi: int = 200,
                schwelle: float = 0.5, dok=None) -> SeitenBefund:
        name = Path(pfad).name
        if _soll_scheitern(self.scheitern_bei, name, seite):
            raise RuntimeError(
                f"Attrappe: Seite {seite} von {name!r} soll planmäßig scheitern.")

        breite, hoehe = 595.0, 842.0
        if dok is not None:
            rect = dok[seite].rect
            breite, hoehe = float(rect.width), float(rect.height)

        bloecke = [
            Block(id=0, query_id=0, pp_label="paragraph_title", score=0.99,
                  lese_index=0,
                  bbox=Bbox(x0=50, y0=40, x1=500, y1=90,
                            rahmen=Bezugsrahmen.BILD_PIXEL)),
            Block(id=1, query_id=1, pp_label="text", score=0.97,
                  lese_index=1,
                  bbox=Bbox(x0=50, y0=110, x1=500, y1=700,
                            rahmen=Bezugsrahmen.BILD_PIXEL)),
        ]
        kanten = [Lesekante(von=0, nach=1, konfidenz=0.9, marge=3.0)]
        befund = SeitenBefund(
            quelle_datei=name, seite=seite,
            seite_breite_pt=breite, seite_hoehe_pt=hoehe,
            render_dpi=dpi, bild_breite_px=800, bild_hoehe_px=1000,
            bloecke=bloecke, kanten=kanten, stufe=Stufe.LAYOUT)
        befund.spur_hinzufuegen(Stufe.LAYOUT, "attrappe-detektor", 0.0)
        return befund


class ErkennerAttrappe:
    """Ersetzt `erkennung.Erkenner`: trägt Text ein, ohne LM Studio oder
    irgendeine andere Schnittstelle anzusprechen.

    `erzeugungen` zählt Konstruktionen wie bei `DetektorAttrappe` (T6).
    """

    erzeugungen: int = 0

    def __init__(self, scheitern_bei: Schalter | None = None):
        ErkennerAttrappe.erzeugungen += 1
        self.scheitern_bei: Schalter = scheitern_bei or {}

    def erkenne_seite(self, befund: SeitenBefund, pdf: Path, buch: str,
                       ausschnitt_dir: Path = Path("."),
                       zeige_fortschritt: bool = False, dok=None) -> SeitenBefund:
        if _soll_scheitern(self.scheitern_bei, befund.quelle_datei, befund.seite):
            raise RuntimeError(
                f"Attrappe: Seite {befund.seite} von {befund.quelle_datei!r} "
                "soll planmäßig scheitern.")

        for blk in befund.bloecke:
            blk.text = f"Attrappentext für Block {blk.id} ({blk.pp_label})."
            blk.text_format = "klartext"
            blk.text_quelle = "mensch"   # kein Modell im Spiel; nächstliegender Wert
        befund.spur_hinzufuegen(Stufe.ERKANNT, "attrappe-erkenner", 0.0)
        return befund
