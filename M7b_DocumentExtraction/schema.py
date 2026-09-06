"""Arbeitsformat der Dokumentenaufbereitung.

Ein Schema für alle Stufen. Der `SeitenBefund` wächst von Stufe zu Stufe,
statt in verschiedene Typen zu zerfallen: Stufe 1 verortet die Blöcke,
Stufe 2 füllt ihren Text, Stufe 4 überführt sie ins kanonische Format.
Welchen Stand eine Datei hat, sagt das Feld `stufe` im Umschlag.

Dieses Modul ist bewusst frei von schweren Abhängigkeiten: kein
onnxruntime, kein cv2, kein docling. Es beschreibt, was beobachtet wurde,
und weiß nicht, wer es beobachtet hat.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------- Koordinaten

class Ursprung(str, Enum):
    OBEN_LINKS = "oben_links"
    UNTEN_LINKS = "unten_links"


class Bezugsrahmen(str, Enum):
    MODELL_800 = "modell_800"
    BILD_PIXEL = "bild_pixel"
    SEITE_PUNKT = "seite_punkt"
    NORMIERT_1000 = "normiert_1000"


class Bbox(BaseModel):
    """Achsenparalleles Rechteck. Bezugsrahmen und Ursprung sind Pflicht.

    Ohne Rahmenangabe ist ein Zahlenpaar bedeutungslos: 400 kann ein
    Modellpixel, ein Bildpixel oder ein PDF-Punkt sein. Die Wächter unten
    verhindern, dass zwei Rahmen versehentlich verrechnet werden.
    """

    x0: float
    y0: float
    x1: float
    y1: float
    rahmen: Bezugsrahmen
    ursprung: Ursprung = Ursprung.OBEN_LINKS

    @model_validator(mode="after")
    def _sortiert(self) -> "Bbox":
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError(
                f"Bbox nicht sortiert: {self.x0},{self.y0} - {self.x1},{self.y1}")
        return self

    @property
    def breite(self) -> float:
        return self.x1 - self.x0

    @property
    def hoehe(self) -> float:
        return self.y1 - self.y0

    @property
    def flaeche(self) -> float:
        return self.breite * self.hoehe

    @classmethod
    def aus_cxcywh(cls, cx, cy, w, h, rahmen, **kw) -> "Bbox":
        """DETR gibt Mittelpunkt plus Größe aus, nicht Ecken."""
        return cls(x0=cx - w / 2, y0=cy - h / 2, x1=cx + w / 2, y1=cy + h / 2,
                   rahmen=rahmen, **kw)

    def _gleicher_rahmen(self, andere: "Bbox", was: str) -> None:
        if self.rahmen is not andere.rahmen or self.ursprung is not andere.ursprung:
            raise ValueError(
                f"{was} über Rahmengrenze: {self.rahmen.value}/{self.ursprung.value} "
                f"gegen {andere.rahmen.value}/{andere.ursprung.value}")

    def iou(self, andere: "Bbox") -> float:
        self._gleicher_rahmen(andere, "IoU")
        x0, y0 = max(self.x0, andere.x0), max(self.y0, andere.y0)
        x1, y1 = min(self.x1, andere.x1), min(self.y1, andere.y1)
        if x1 <= x0 or y1 <= y0:
            return 0.0
        schnitt = (x1 - x0) * (y1 - y0)
        vereinigung = self.flaeche + andere.flaeche - schnitt
        return schnitt / vereinigung if vereinigung else 0.0

    def enthalten_in(self, andere: "Bbox") -> float:
        """Anteil der eigenen Fläche, der in `andere` liegt. 1.0 = ganz drin.

        Anders als IoU asymmetrisch — genau das braucht man, um eine kleine
        Detektion in einer großen zu erkennen.
        """
        self._gleicher_rahmen(andere, "Enthaltensein")
        x0, y0 = max(self.x0, andere.x0), max(self.y0, andere.y0)
        x1, y1 = min(self.x1, andere.x1), min(self.y1, andere.y1)
        if x1 <= x0 or y1 <= y0 or not self.flaeche:
            return 0.0
        return ((x1 - x0) * (y1 - y0)) / self.flaeche


def zurueck_ins_bild(box: Bbox, bild_breite: int, bild_hoehe: int) -> Bbox:
    """800x800 -> Bildpixel. Wegen keep_ratio=false eine achsenweise Streckung."""
    if box.rahmen is not Bezugsrahmen.MODELL_800:
        raise ValueError(f"Erwarte MODELL_800, bekommen {box.rahmen.value}")
    fx, fy = bild_breite / 800, bild_hoehe / 800
    return Bbox(x0=box.x0 * fx, y0=box.y0 * fy, x1=box.x1 * fx, y1=box.y1 * fy,
                rahmen=Bezugsrahmen.BILD_PIXEL, ursprung=box.ursprung)


def ins_pdf(box: Bbox, dpi: int) -> Bbox:
    """Bildpixel -> PDF-Punkte. Der Ursprung bleibt, nur die Einheit ändert sich."""
    if box.rahmen is not Bezugsrahmen.BILD_PIXEL:
        raise ValueError(f"Erwarte BILD_PIXEL, bekommen {box.rahmen.value}")
    f = 72.0 / dpi
    return Bbox(x0=box.x0 * f, y0=box.y0 * f, x1=box.x1 * f, y1=box.y1 * f,
                rahmen=Bezugsrahmen.SEITE_PUNKT, ursprung=box.ursprung)


def nach_gemma(box: Bbox, bild_breite: int, bild_hoehe: int) -> list[int]:
    """Bildpixel -> Gemma-Format [y0, x0, y1, x1], normiert auf 1000x1000."""
    if box.rahmen is not Bezugsrahmen.BILD_PIXEL:
        raise ValueError(f"Erwarte BILD_PIXEL, bekommen {box.rahmen.value}")
    sx, sy = 1000 / bild_breite, 1000 / bild_hoehe
    return [round(box.y0 * sy), round(box.x0 * sx),
            round(box.y1 * sy), round(box.x1 * sx)]


# -------------------------------------------------------------------- Klassen

# Reihenfolge exakt wie die label_list der PaddleX-config.json.
# Der Index IST die Klassen-ID des Detektorkopfs.
PP_LABELS: list[str] = [
    "abstract", "algorithm", "aside_text", "chart", "content",
    "display_formula", "doc_title", "figure_title", "footer", "footer_image",
    "footnote", "formula_number", "header", "header_image", "image",
    "inline_formula", "number", "paragraph_title", "reference",
    "reference_content", "seal", "table", "text", "vertical_text",
    "vision_footnote",
]

# Gegenprobe: labels.json des ONNX-Exports. Gleiche Gewichte, gröbere Namen.
# Fünf Klassen fallen dort zusammen (5/15, 9, 13, 23). Nicht verwendet,
# nur als Beleg dafür, warum die PaddleX-Tabelle die richtige ist.
HF_ID2LABEL: dict[int, str] = {
    0: "abstract", 1: "algorithm", 2: "aside_text", 3: "chart", 4: "content",
    5: "formula", 6: "doc_title", 7: "figure_title", 8: "footer", 9: "footer",
    10: "footnote", 11: "formula_number", 12: "header", 13: "header", 14: "image",
    15: "formula", 16: "number", 17: "paragraph_title", 18: "reference",
    19: "reference_content", 20: "seal", 21: "table", 22: "text", 23: "text",
    24: "vision_footnote",
}

# (docling-Label, was beim Mappen verloren geht). None = verlustfrei.
# Die Verlustspalte ist keine Zierde: sie sagt, was das Arbeitsformat
# weiterhin tragen muss, weil das kanonische Format es nicht kann.
PP_NACH_DOCLING: dict[str, tuple[str | None, str | None]] = {
    "doc_title":         ("title",          None),
    "paragraph_title":   ("section_header", None),
    "text":              ("text",           None),
    "figure_title":      ("caption",        None),
    "image":             ("picture",        None),
    "chart":             ("chart",          None),
    "table":             ("table",          None),
    "display_formula":   ("formula",        None),
    "footnote":          ("footnote",       None),
    "header":            ("page_header",    None),
    "footer":            ("page_footer",    None),
    "reference":         ("reference",      None),
    "content":           ("text", "Inhaltsverzeichnis – document_index gilt in "
                                  "docling nur für ein TableItem"),
    "aside_text":        ("text",      "Marginalie – eigener Lesestrom"),
    "inline_formula":    ("formula",   "inline statt abgesetzt"),
    "formula_number":    ("text",      "Formelnummer"),
    "abstract":          ("text",      "Rolle als Zusammenfassung"),
    "algorithm":         ("code",      "nur näherungsweise"),
    "reference_content": ("reference", "fällt mit reference zusammen"),
    "vision_footnote":   ("footnote",  "Bezug zur Abbildung"),
    "header_image":      ("picture",   "Zugehörigkeit zur Kopfzeile"),
    "footer_image":      ("picture",   "Zugehörigkeit zur Fußzeile"),
    "number":            ("text",      "Seitenzahl"),
    "vertical_text":     ("text",      "Schreibrichtung"),
    "seal":              ("picture",   "Siegeleigenschaft"),
}


# --------------------------------------------------------------------- Ströme

class Strom(str, Enum):
    HAUPT = "haupt"
    MARGINALIE = "marginalie"
    BOILERPLATE = "boilerplate"
    APPARAT = "apparat"          # Fußnoten, Referenzen


BOILERPLATE = {"header", "footer", "header_image", "footer_image", "number"}
APPARAT = {"footnote", "vision_footnote", "reference", "reference_content"}

# Labels, deren Regionen aus Textzeilen bestehen. Nur solche Blöcke dürfen
# waagerecht zusammengeführt werden; eine Tabelle neben einer Tabelle ist
# nicht eine breitere Tabelle.
TEXTARTIG = {
    "text", "paragraph_title", "doc_title", "abstract", "aside_text", "footnote",
    "vision_footnote", "figure_title", "content", "header", "footer", "number",
    "reference", "reference_content", "algorithm", "vertical_text", "formula_number",
}


def strom_fuer(pp_label: str) -> Strom:
    if pp_label in BOILERPLATE:
        return Strom.BOILERPLATE
    if pp_label == "aside_text":
        return Strom.MARGINALIE
    if pp_label in APPARAT:
        return Strom.APPARAT
    return Strom.HAUPT


# ---------------------------------------------------------------------- Stand

class Stufe(int, Enum):
    """Wie weit eine Seite bearbeitet ist. Der Wiederaufsetzpunkt für A2."""

    LAYOUT = 1      # Blöcke verortet, typisiert, geordnet. Kein Text.
    ERKANNT = 2     # Feld `text` gefüllt.
    KANONISCH = 4   # ins DoclingDocument überführt.


class Laufspur(BaseModel):
    """Wer hat wann wie lange gerechnet. Messung, nicht Warnung."""

    stufe: Stufe
    modell: str = Field(description="ONNX-Datei bzw. Modell-ID aus LM Studio")
    dauer_s: float
    zeitstempel: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = SCHEMA_VERSION


# --------------------------------------------------------------------- Blöcke

class Block(BaseModel):
    """Ein detektiertes Layout-Element.

    Die Felder ab `text_format` sind erst nach Stufe 2 gefüllt. Sie stehen
    hier und nicht in einer eigenen Klasse, weil ein Block dieselbe Sache
    bleibt, wenn er Text bekommt.
    """

    id: int = Field(description="laufender Index innerhalb des Befunds")
    query_id: int = Field(description="Index der Query im Detektor, 0..299")
    pp_label: str = Field(description="Native Klasse aus der label_list – wörtlich")
    score: float = Field(ge=0.0, le=1.0)
    bbox: Bbox
    lese_index: int | None = Field(
        default=None, description="Rang aus der Zeigermatrix; kleiner = früher")
    polygon: list[tuple[float, float]] | None = Field(
        default=None, description="aus der Instanzmaske abgeleitet, falls vorhanden")
    quelle: Literal["pp_doclayout", "pymupdf", "vlm", "mensch"] = "pp_doclayout"
    text: str | None = Field(default=None, description="erst ab Stufe 2 gefüllt")

    # --- ab Stufe 2
    text_format: Literal["klartext", "latex", "otsl", "datenreihe"] | None = Field(
        default=None, description="Wie `text` zu lesen ist. None = kein Text erzeugt.")
    text_quelle: Literal["paddleocr_vl", "pymupdf", "mensch"] | None = Field(
        default=None, description="Wer den Text erzeugt hat – unabhängig von `quelle`.")
    zusammengefuehrt_aus: list[int] | None = Field(
        default=None, description="Block-ids der Stufe 1, falls zusammengeführt.")
    ausschnitt: str | None = Field(
        default=None, description="Pfad zum PNG, wenn kein Text erzeugt wurde.")

    @property
    def docling_label(self) -> str | None:
        return PP_NACH_DOCLING.get(self.pp_label, (None, None))[0]

    @property
    def verlust(self) -> str | None:
        """Was beim Mappen nach docling verloren geht. None = verlustfrei."""
        return PP_NACH_DOCLING.get(self.pp_label, (None, None))[1]

    @property
    def strom(self) -> Strom:
        return strom_fuer(self.pp_label)

    @property
    def textartig(self) -> bool:
        return self.pp_label in TEXTARTIG


class Lesekante(BaseModel):
    """Gerichtete Kante aus der 300x300-Zeigermatrix: von -> nach.

    `von` und `nach` sind Block-`id`, nicht `query_id`.
    """

    von: int
    nach: int
    konfidenz: float = Field(ge=0.0, le=1.0)
    marge: float | None = Field(
        default=None,
        description="Logit-Marge für 'nach folgt auf von'. Sättigt nicht, "
                    "anders als konfidenz. Positiv = Modell stimmt zu.")


class SeitenBefund(BaseModel):
    """Umschlag: alles, was über eine Seite bekannt ist.

    Eine Seite, eine Datei. Seitengrenzen werden nirgends aufgehoben –
    jede Aussage bleibt einer Seite zurechenbar.
    """

    quelle_datei: str
    seite: int = Field(ge=0, description="0-basiert wie in PyMuPDF")
    seite_breite_pt: float
    seite_hoehe_pt: float
    render_dpi: int
    bild_breite_px: int
    bild_hoehe_px: int
    bloecke: list[Block] = Field(default_factory=list)
    kanten: list[Lesekante] = Field(default_factory=list)
    warnungen: list[str] = Field(default_factory=list)

    stufe: Stufe | None = Field(
        default=None, description="None nur beim Einlesen alter Dateien; "
                                  "wird dann aus dem Inhalt erschlossen.")
    spuren: list[Laufspur] = Field(default_factory=list)
    fehler: str | None = Field(
        default=None, description="gesetzt, wenn die Seite übersprungen wurde (A3)")
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def _stufe_erschliessen(self) -> "SeitenBefund":
        """Altlast-Brücke: Dateien vor Einführung des Feldes tragen es nicht."""
        if self.stufe is None:
            hat_text = any(b.text is not None or b.ausschnitt is not None
                           for b in self.bloecke)
            self.stufe = Stufe.ERKANNT if hat_text else Stufe.LAYOUT
        return self

    @property
    def seite_menschlich(self) -> int:
        """1-basiert. docling zählt Seiten ab 1, PyMuPDF ab 0."""
        return self.seite + 1

    def lesefolge(self, strom: Strom = Strom.HAUPT) -> list[Block]:
        """Blöcke eines Stroms in Lesereihenfolge.

        Bevorzugt den `lese_index` aus der Zeigermatrix. Fehlt er, wird
        greedy über die Kantenkonfidenz gelaufen: Startpunkt ist der Block
        ohne eingehende Kante, danach jeweils die stärkste ausgehende Kante.
        """
        erlaubt = {b.id: b for b in self.bloecke if b.strom is strom}
        if not erlaubt:
            return []

        if all(b.lese_index is not None for b in erlaubt.values()):
            return sorted(erlaubt.values(), key=lambda b: (b.lese_index, b.id))

        kanten = [k for k in self.kanten if k.von in erlaubt and k.nach in erlaubt]
        ziele = {k.nach for k in kanten}
        aktuell = next((i for i in erlaubt if i not in ziele), min(erlaubt))
        folge, gesehen = [], set()
        while aktuell is not None and aktuell not in gesehen:
            gesehen.add(aktuell)
            folge.append(erlaubt[aktuell])
            weiter = [k for k in kanten if k.von == aktuell and k.nach not in gesehen]
            aktuell = max(weiter, key=lambda k: k.konfidenz).nach if weiter else None
        folge += [b for i, b in erlaubt.items() if i not in gesehen]
        return folge

    def schwaechste_kanten(self, anzahl: int = 5) -> list[Lesekante]:
        """Die unsichersten Übergänge – der billigste Einstieg in die Fehlersuche.

        Sortiert nach der Logit-Marge, weil `konfidenz` bei sicheren Seiten
        durchgehend auf 1.0 sättigt und dann nicht mehr unterscheidet.
        """
        if self.kanten and all(k.marge is not None for k in self.kanten):
            return sorted(self.kanten, key=lambda k: k.marge)[:anzahl]
        return sorted(self.kanten, key=lambda k: k.konfidenz)[:anzahl]

    def spur_hinzufuegen(self, stufe: Stufe, modell: str, dauer_s: float) -> None:
        """Messung eintragen und den Stand fortschreiben."""
        self.spuren.append(Laufspur(stufe=stufe, modell=modell, dauer_s=dauer_s))
        if self.stufe is None or stufe.value > self.stufe.value:
            self.stufe = stufe


# --------------------------------------------------------------------- Ablage

def befund_pfad(wurzel: Path, buch: str, seite: int) -> Path:
    """befunde/<buch>/<seite:04d>.json – eine Seite, eine Datei.

    Der Stand steht im Feld `stufe`, nicht im Dateinamen. Damit überschreibt
    Stufe 2 die Datei der Stufe 1, statt eine zweite daneben zu legen; sie
    ist eine echte Obermenge, es geht nichts verloren.
    """
    return wurzel / buch / f"{seite:04d}.json"


def befund_speichern(befund: SeitenBefund, pfad: Path) -> Path:
    """Erst neben die Zieldatei schreiben, dann umbenennen.

    Ein Abbruch mitten im Schreiben hinterlässt sonst eine halbe JSON-Datei,
    die beim Wiederaufsetzen als fertige Seite gilt.
    """
    pfad.parent.mkdir(parents=True, exist_ok=True)
    vorlaeufig = pfad.with_suffix(".json.teil")
    vorlaeufig.write_text(befund.model_dump_json(indent=2), encoding="utf-8")
    vorlaeufig.replace(pfad)
    return pfad


def befund_laden(pfad: Path) -> SeitenBefund:
    return SeitenBefund.model_validate_json(pfad.read_text(encoding="utf-8"))


def ist_fertig(pfad: Path, mindestens: Stufe) -> bool:
    """A2: Ist diese Seite schon weit genug?

    Nicht lesbare Dateien und Seiten mit gesetztem `fehler` gelten als offen.
    Ein Wiederaufsetzen versucht sie damit erneut, statt einen Fehlschlag für
    alle Zeiten festzuschreiben.
    """
    if not pfad.exists():
        return False
    try:
        befund = befund_laden(pfad)
    except Exception:
        return False
    return befund.fehler is None and befund.stufe.value >= mindestens.value


# ------------------------------------------------------------------ Selbsttest

def selbsttest_docling() -> dict[str, int]:
    """Prüft die Klassenabbildung gegen das echte DocItemLabel-Enum.

    Bewusst eine Funktion und kein Modulcode: `schema.py` soll auch ohne
    installiertes docling-core importierbar sein.
    """
    from docling_core.types.doc import DocItemLabel

    gueltig = {l.value for l in DocItemLabel}
    assert len(PP_LABELS) == len(HF_ID2LABEL) == 25, "Der Kopf hat 25 Ausgänge."
    fehlend = [l for l in PP_LABELS if l not in PP_NACH_DOCLING]
    assert not fehlend, f"ohne Mapping: {fehlend}"
    ungueltig = {k: v for k, (v, _) in PP_NACH_DOCLING.items()
                 if v and v not in gueltig}
    assert not ungueltig, f"kein gültiges DocItemLabel: {ungueltig}"

    verlustfrei = [l for l in PP_LABELS if PP_NACH_DOCLING[l][1] is None]
    return {"klassen": len(PP_LABELS),
            "verlustfrei": len(verlustfrei),
            "verlustbehaftet": len(PP_LABELS) - len(verlustfrei)}
