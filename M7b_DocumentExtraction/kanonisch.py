"""Stufe 4a: aus den Seitenbefunden eines Buchs ein `DoclingDocument`.

Der Übergang vom Arbeitsformat (Beobachtung, mit Widersprüchen) zum
kanonischen Format (Entscheidung: eine Region, ein Label, ein Text).
Vollständig deterministisch, ohne Sprachmodell – das ist der Sinn der
Trennung von 4a und 4b: der prüfbare Teil bleibt prüfbar.

Umgesetzt: A5, A6, A8, A9, A10, A11, A12, A14, A15. A16 fällt aus der
Provenienz von selbst ab.

**Nicht** umgesetzt, bewusst: A7 (Absatz über Seitengrenze) und A13
(Inline-Formel zurück in den Satz). Seitengrenzen werden nirgends
aufgehoben, damit jede Aussage einer Seite zurechenbar bleibt.

Entscheidungen, die hier gefallen sind und anderswo anders ausfallen könnten:

* Ströme -> ContentLayer: haupt und apparat nach BODY, marginalie nach NOTES,
  boilerplate nach FURNITURE. Streng nach dem Label des Detektors – ein als
  `header` erkannter Abschnittstitel ("Literatur") bleibt damit Boilerplate.
* Überschriftenebene aus der Gliederungsnummer, ersatzweise eine Ebene unter
  der zuletzt gesehenen.
* Entdoppelt wird nur bei identischem Label; gemischte Überlappungen bleiben
  stehen, weil dort beide Detektionen etwas Eigenes aussagen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from docling_core.types.doc import (
    BoundingBox, ContentLayer, CoordOrigin, DocItemLabel, DoclingDocument,
    ImageRef, ProvenanceItem, Size, TableCell, TableData,
)
from docling_core.types.doc.items.picture.charts import PictureTabularChartData
from docling_core.types.doc.utils import parse_otsl_table_content

from schema import (
    Block, PP_NACH_DOCLING, SeitenBefund, Strom, befund_laden, ins_pdf,
)

def _erlaubte_textlabels() -> set[str]:
    """Welche Labels trägt ein TextItem? Aus dem Modell ausgelesen, nicht geraten.

    `DocItemLabel` hat 31 Werte, `TextItem` lässt 14 davon zu. Die Differenz
    fällt sonst erst zur Laufzeit auf, und zwar mitten im Buch.
    """
    from typing import get_args
    from docling_core.types.doc.document import TextItem
    return {l.value for l in get_args(TextItem.model_fields["label"].annotation)}


TEXTLABELS = _erlaubte_textlabels()

# Ab diesem Anteil gilt eine Box als in einer anderen liegend.
ENTHALTEN_SCHWELLE = 0.9

STROM_NACH_LAYER: dict[Strom, ContentLayer] = {
    Strom.HAUPT: ContentLayer.BODY,
    Strom.APPARAT: ContentLayer.BODY,        # sonst wären Literaturseiten leer
    Strom.MARGINALIE: ContentLayer.NOTES,
    Strom.BOILERPLATE: ContentLayer.FURNITURE,
}

# Klassen, die als Abbildung ins Dokument gehen.
BILDARTIG = {"image", "header_image", "footer_image", "seal"}
NUMMER = re.compile(r"^\s*(\d+(?:\.\d+)*)[.\s)]")
# Stufe 2 legt Formeln mit Delimitern ab ($…$ bzw. $$…$$), damit die
# Markdown-Vorschau lesbar ist. Docling setzt beim Export eigene – ohne
# Abstreifen entsteht $$$…$$$.
DELIMITER = re.compile(r"^\s*\$\$?\s*(.*?)\s*\$\$?\s*$", re.S)
# Worauf sich eine Bildunterschrift dem Wortlaut nach bezieht.
# `^\W*` statt `^\s*`, weil der Satz Aufzählungszeichen voranstellt ("▶ Abb. 2.2").
# Kein `\b` am Ende: nach einem Punkt gibt es keine Wortgrenze, das Muster
# griffe dann nie – ein Fehler, den erst der Test sichtbar gemacht hat.
UNTERSCHRIFT_TABELLE = re.compile(r"^\W*(tab\.|tabelle|table)", re.I)
UNTERSCHRIFT_ABBILDUNG = re.compile(
    r"^\W*(abb\.|abbildung|fig\.|figure|grafik|diagramm|schema)", re.I)


@dataclass
class Bericht:
    seiten: int = 0
    elemente: int = 0
    ueberschriften: int = 0
    tabellen: int = 0
    diagramme: int = 0
    abbildungen: int = 0
    formeln: int = 0
    unterschriften: int = 0
    offene_unterschriften: list[tuple[int, int, list[int]]] = field(default_factory=list)
    entdoppelt: int = 0
    pruefbeduerftig: list[int] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)

    def zusammenfassung(self) -> str:
        zeilen = [
            f"{self.seiten} Seiten, {self.elemente} Elemente",
            f"  {self.ueberschriften} Überschriften, {self.tabellen} Tabellen, "
            f"{self.diagramme} Diagramme, {self.abbildungen} Abbildungen, "
            f"{self.formeln} Formeln",
            f"  {self.unterschriften} Bildunterschriften zugeordnet, "
            f"{len(self.offene_unterschriften)} offen (Arbeitsliste für 4b), "
            f"{self.entdoppelt} Blöcke entdoppelt",
        ]
        if self.pruefbeduerftig:
            zeilen.append(f"  prüfbedürftig: {len(self.pruefbeduerftig)} Seiten "
                          f"{self.pruefbeduerftig[:12]}")
        if self.warnungen:
            zeilen.append(f"  {len(self.warnungen)} Warnungen")
        return "\n".join(zeilen)


# ------------------------------------------------------------ Überschriften

def ebene_aus_nummer(text: str) -> int | None:
    """'4.2.2 Titel' -> 3. Ohne Gliederungsnummer None."""
    treffer = NUMMER.match(text or "")
    return treffer.group(1).count(".") + 1 if treffer else None


def _einzeilig(text: str) -> str:
    """Docling-Überschriften sind einzeilig; der Satz bricht sie trotzdem um."""
    return " ".join((text or "").split())


class Ebenen:
    """Fortlaufende Ebenenlogik über das ganze Buch.

    Nummerierte Überschriften setzen die Ebene und den Bezugspunkt. Alles
    Unnummerierte – Kästen wie '? Kontrollfragen', 'Vorwort' – landet eine
    Ebene darunter, statt die Gliederung zu zerschießen.
    """

    def __init__(self) -> None:
        self.zuletzt = 0

    def fuer(self, text: str, ist_dokumenttitel: bool = False) -> int:
        if ist_dokumenttitel:
            self.zuletzt = 1
            return 1
        ebene = ebene_aus_nummer(text)
        if ebene is not None:
            self.zuletzt = ebene
            return ebene
        return min(100, max(1, self.zuletzt + 1))


# --------------------------------------------------------------- Entdoppeln

def entdoppeln(befund: SeitenBefund) -> tuple[SeitenBefund, list[str]]:
    """Identisch benannte Blöcke, die ineinanderliegen, auf einen reduzieren.

    Nur bei gleichem `pp_label`: 'text in text' und 'table in table' sind
    Doppeldetektionen desselben Gegenstands. 'paragraph_title in text' ist es
    nicht – dort sagen beide Detektionen etwas Eigenes, und beide bleiben.
    Es gewinnt der höhere Score; bei Gleichstand die größere Fläche.
    """
    besiegt_von: dict[int, int] = {}
    verworfen: set[int] = set()
    meldungen: list[str] = []

    for a in befund.bloecke:
        for b in befund.bloecke:
            if a.id >= b.id or a.id in verworfen or b.id in verworfen:
                continue
            if a.pp_label != b.pp_label:
                continue
            try:
                innen = max(a.bbox.enthalten_in(b.bbox), b.bbox.enthalten_in(a.bbox))
            except ValueError:
                continue
            if innen < ENTHALTEN_SCHWELLE:
                continue
            sieger, verlierer = ((a, b) if (a.score, a.bbox.flaeche)
                                 >= (b.score, b.bbox.flaeche) else (b, a))
            verworfen.add(verlierer.id)
            besiegt_von[verlierer.id] = sieger.id

    # Enthaltensein ist transitiv: #5 kann gegen #6 verlieren und #6 gegen #7.
    # Gemeldet wird der Überlebende am Ende der Kette, nicht der Zwischensieger.
    for verlierer_id, sieger_id in besiegt_von.items():
        gesehen = {verlierer_id}
        while sieger_id in besiegt_von and sieger_id not in gesehen:
            gesehen.add(sieger_id)
            sieger_id = besiegt_von[sieger_id]
        label = next(b.pp_label for b in befund.bloecke if b.id == verlierer_id)
        meldungen.append(
            f"S{befund.seite}: #{verlierer_id} verworfen zugunsten von "
            f"#{sieger_id} ({label}).")

    if not verworfen:
        return befund, []
    neu = befund.model_copy(update={
        "bloecke": [b for b in befund.bloecke if b.id not in verworfen]})
    return neu, meldungen


# ------------------------------------------------------- Bildunterschriften

def _widerspricht(objekt: Block, text: str) -> bool:
    """Nennt die Unterschrift dem Wortlaut nach etwas anderes als das Objekt?

    'Tab. 5.1' an einer Abbildung ist auch dann falsch, wenn es das einzige
    Objekt der Seite ist. Mehr Layoutwissen steckt hier nicht drin.
    """
    if UNTERSCHRIFT_TABELLE.match(text or ""):
        return objekt.pp_label != "table"
    if UNTERSCHRIFT_ABBILDUNG.match(text or ""):
        return objekt.pp_label == "table"
    return False


def unterschriften_zuordnen(befund: SeitenBefund
                            ) -> tuple[dict[int, int], list[tuple[int, list[int]]]]:
    """({Objekt-Blockid: Unterschrift-Blockid}, offene Fälle).

    Zugeordnet wird ausschließlich der erzwungene Fall: **ein** Objekt und
    **eine** Unterschrift auf der Seite. Dann gibt es nichts abzuwägen.

    Alles andere bleibt offen und wird gemeldet. Wo eine Bildunterschrift
    steht – darunter, seitlich in der Marginalspalte, im Bild – ist eine
    Gestaltungsentscheidung des jeweiligen Buchs und keine Regelmäßigkeit,
    die sich über Bücher hinweg in Schwellen fassen ließe. Diese Zuordnung
    gehört deshalb nach 4b, vor ein Bildmodell, nicht hierher.
    """
    objekte = [b for b in befund.bloecke
               if b.pp_label in ("table", "chart") or b.pp_label in BILDARTIG]
    unterschriften = [b for b in befund.bloecke if b.pp_label == "figure_title"]
    if not objekte or not unterschriften:
        return {}, [(u.id, [o.id for o in objekte]) for u in unterschriften]

    if len(objekte) == 1 and len(unterschriften) == 1:
        objekt, unterschrift = objekte[0], unterschriften[0]
        if not _widerspricht(objekt, unterschrift.text or ""):
            return {objekt.id: unterschrift.id}, []

    return {}, [(u.id, [o.id for o in objekte]) for u in unterschriften]


# ----------------------------------------------------------------- Inhalte

def datenreihe_zu_tabelle(text: str) -> TableData | None:
    """'Chart Recognition:' liefert die Datenreihe als Zeilen mit '|'.

    Erste Zeile ist die Kopfzeile. Schlägt der Zuschnitt fehl, gibt es None
    und der Aufrufer behält die Abbildung ohne Datenannotation.
    """
    zeilen = [z.strip() for z in (text or "").splitlines() if z.strip()]
    if len(zeilen) < 2:
        return None
    felder = [[t.strip() for t in z.split("|")] for z in zeilen]
    spalten = max(len(f) for f in felder)
    if spalten < 2:
        return None

    zellen: list[TableCell] = []
    for r, zeile in enumerate(felder):
        for c in range(spalten):
            zellen.append(TableCell(
                text=zeile[c] if c < len(zeile) else "",
                start_row_offset_idx=r, end_row_offset_idx=r + 1,
                start_col_offset_idx=c, end_col_offset_idx=c + 1,
                column_header=(r == 0)))
    return TableData(table_cells=zellen, num_rows=len(felder), num_cols=spalten)


def _bildgroesse(pfad: Path, block: Block, befund: SeitenBefund) -> Size:
    """Echte Pixelmaße, sonst aus der Box geschätzt."""
    try:
        from PIL import Image
        with Image.open(pfad) as bild:
            return Size(width=bild.width, height=bild.height)
    except Exception:
        faktor = 300 / befund.render_dpi          # PROBE_DPI der Stufe 2
        return Size(width=round(block.bbox.breite * faktor),
                    height=round(block.bbox.hoehe * faktor))


def provenienz(block: Block, befund: SeitenBefund,
               zeichen: int) -> ProvenanceItem:
    """A8/A16: Quelldatei steckt im Dokumentnamen, Seite und Rechteck hier.

    Das Rechteck kommt in PDF-Punkten mit Ursprung oben links – docling führt
    den Ursprung ausdrücklich mit, eine Umrechnung ist nicht nötig.
    """
    box = ins_pdf(block.bbox, befund.render_dpi)
    return ProvenanceItem(
        page_no=befund.seite_menschlich,
        bbox=BoundingBox(l=box.x0, t=box.y0, r=box.x1, b=box.y1,
                         coord_origin=CoordOrigin.TOPLEFT),
        charspan=(0, zeichen))


# ------------------------------------------------------------- Der Übergang

def nach_docling(befunde: list[SeitenBefund], name: str) -> tuple[DoclingDocument, Bericht]:
    """Die Seitenbefunde eines Buchs -> genau ein kanonisches Dokument (A5)."""
    dok = DoclingDocument(name=name)
    bericht = Bericht(seiten=len(befunde))
    ebenen = Ebenen()

    for befund in sorted(befunde, key=lambda b: b.seite):
        dok.add_page(page_no=befund.seite_menschlich,
                     size=Size(width=befund.seite_breite_pt,
                               height=befund.seite_hoehe_pt))
        if befund.fehler:
            bericht.warnungen.append(f"S{befund.seite}: {befund.fehler}")
            continue

        befund, meldungen = entdoppeln(befund)
        bericht.entdoppelt += len(meldungen)
        bericht.warnungen += meldungen

        zuordnung, offen = unterschriften_zuordnen(befund)
        bericht.offene_unterschriften += [(befund.seite, uid, oids)
                                          for uid, oids in offen]
        als_unterschrift = set(zuordnung.values())
        nach_id = {b.id: b for b in befund.bloecke}

        # A6: Lesereihenfolge über alle Ströme hinweg, in einem Durchgang.
        # Die Trennung der Ströme leistet danach der ContentLayer.
        geordnet = sorted(befund.bloecke,
                          key=lambda b: (b.lese_index if b.lese_index is not None
                                         else 10**6, b.id))

        for blk in geordnet:
            if blk.id in als_unterschrift:
                continue                       # hängt an seinem Objekt
            schicht = STROM_NACH_LAYER[blk.strom]
            unterschrift = None
            if blk.id in zuordnung:
                u = nach_id[zuordnung[blk.id]]
                unterschrift = dok.add_text(
                    label=DocItemLabel.CAPTION, text=_einzeilig(u.text or ""),
                    prov=provenienz(u, befund, len(u.text or "")),
                    content_layer=schicht)
                bericht.unterschriften += 1

            neu = _element_anlegen(dok, blk, befund, schicht, unterschrift,
                                   ebenen, bericht)
            if neu is not None:
                bericht.elemente += 1

    return dok, bericht


def _element_anlegen(dok: DoclingDocument, blk: Block, befund: SeitenBefund,
                     schicht: ContentLayer, unterschrift, ebenen: Ebenen,
                     bericht: Bericht):
    """Ein Block -> ein Element. Die Fallunterscheidung des ganzen Moduls."""
    text = blk.text or ""
    prov = provenienz(blk, befund, len(text))
    label = blk.pp_label

    # --- A10/A11: Tabellen
    if label == "table":
        daten = None
        if blk.text_format == "otsl" and text:
            try:
                daten = parse_otsl_table_content(text)
            except Exception as e:
                bericht.warnungen.append(
                    f"S{befund.seite}: #{blk.id} OTSL nicht lesbar "
                    f"({type(e).__name__}) – Ausgabe unverändert erhalten.")
        if daten is None:
            # A11: erhalten, nicht wegwerfen, und die Seite kennzeichnen.
            if befund.seite not in bericht.pruefbeduerftig:
                bericht.pruefbeduerftig.append(befund.seite)
            return dok.add_text(label=DocItemLabel.TEXT, text=text, prov=prov,
                                content_layer=schicht)
        bericht.tabellen += 1
        return dok.add_table(data=daten, caption=unterschrift, prov=prov,
                             content_layer=schicht)

    # --- Diagramme: die Datenreihe als native Annotation
    if label == "chart":
        annotationen = []
        daten = datenreihe_zu_tabelle(text) if blk.text_format == "datenreihe" else None
        if daten is not None:
            annotationen.append(PictureTabularChartData(
                title=_einzeilig((text or "").splitlines()[0])[:120],
                chart_data=daten))
        elif text:
            bericht.warnungen.append(
                f"S{befund.seite}: #{blk.id} Datenreihe nicht zerlegbar.")
        bild = dok.add_picture(annotations=annotationen or None,
                               caption=unterschrift, prov=prov,
                               content_layer=schicht)
        bild.label = DocItemLabel.CHART
        bericht.diagramme += 1
        return bild

    # --- A14: Abbildungen als Datei ablegen und darauf verweisen
    if label in BILDARTIG:
        verweis = None
        if blk.ausschnitt:
            pfad = Path(blk.ausschnitt)
            verweis = ImageRef(mimetype="image/png", dpi=300,
                               size=_bildgroesse(pfad, blk, befund), uri=pfad)
        bericht.abbildungen += 1
        return dok.add_picture(image=verweis, caption=unterschrift, prov=prov,
                               content_layer=schicht)

    # --- A12: abgesetzte Formeln bleiben eigene Elemente an ihrer Stelle
    if label in ("display_formula", "inline_formula"):
        bericht.formeln += 1
        treffer = DELIMITER.match(text)
        return dok.add_formula(text=treffer.group(1) if treffer else text,
                               prov=prov, content_layer=schicht)

    # --- Überschriften
    if label in ("doc_title", "paragraph_title"):
        bericht.ueberschriften += 1
        return dok.add_heading(text=_einzeilig(text),
                               level=ebenen.fuer(text, label == "doc_title"),
                               prov=prov, content_layer=schicht)

    # --- alles Übrige: Text mit dem gemappten Label
    ziel = PP_NACH_DOCLING.get(label, ("text", None))[0] or "text"
    if ziel == "code":
        return dok.add_code(text=text, prov=prov, content_layer=schicht)
    if ziel not in TEXTLABELS:
        meldung = (f"Label {ziel!r} (aus {label!r}) ist auf einem TextItem "
                   "nicht zulässig – als 'text' abgelegt.")
        if meldung not in bericht.warnungen:
            bericht.warnungen.append(meldung)
        ziel = "text"
    return dok.add_text(label=DocItemLabel(ziel), text=text, prov=prov,
                        content_layer=schicht)


# ---------------------------------------------------------------- Bequemlich

def buch_umwandeln(buch: str, wurzel: Path = Path("data/interim/befunde"),
                   ziel_json: Path | None = None, ziel_md: Path | None = None,
                   zeige_bericht: bool = True) -> tuple[DoclingDocument, Bericht]:
    """Alle Befunde eines Buchs einlesen, umwandeln, ablegen.

    Die Ausgabe ist abgeleitet und wird nie von Hand gepflegt.
    """
    dateien = sorted((wurzel / buch).glob("*.json"))
    if not dateien:
        raise FileNotFoundError(f"Keine Befunde unter {wurzel / buch}")
    dok, bericht = nach_docling([befund_laden(p) for p in dateien], buch)

    ziel_json = ziel_json or Path("data/processed/dokumente") / f"{buch}.json"
    ziel_md = ziel_md or Path("data/processed/md") / f"{buch}.md"
    ziel_json.parent.mkdir(parents=True, exist_ok=True)
    ziel_md.parent.mkdir(parents=True, exist_ok=True)
    dok.save_as_json(ziel_json)
    ziel_md.write_text(
        dok.export_to_markdown(page_break_placeholder="<!-- Seitenumbruch -->"),
        encoding="utf-8")

    if zeige_bericht:
        print(bericht.zusammenfassung())
        print(f"\n{ziel_json}\n{ziel_md}")
    return dok, bericht
