"""Einblick: Stufe 1 sichtbar machen – für die Schulung und die Sichtprüfung.

Liest und zeichnet, schreibt nichts. Zwei Abnehmer:

* `05_layout_einblick.ipynb` – der „mikroskopische Blick“ auf eine Seite:
  Render, 800x800-Tensor, 300 Rohhypothesen, Klassen, Masken, Zeigermatrix.
* `pipeline/layout_viewer.py` – der Gradio-Viewer über ganze Dokumente.

Die Rechenschritte selbst kommen unverändert aus `layout.py`. Hier liegt nur,
was man braucht, um sie anzusehen: Farben, Zeichnen, Rohläufe festhalten und
Auffälligkeiten einer Seite benennen.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import layout
from schema import Block, Lesekante, PP_LABELS, SeitenBefund, Strom

# ------------------------------------------------------------------- Farben

# 25 Klassen sind zu viele für unterscheidbare Farben. Gefärbt wird deshalb
# nach Familie (höchstens neun Töne), die genaue Klasse steht immer als
# Beschriftung an der Box – die Farbe trägt die Identität nie allein.
FAMILIEN: dict[str, tuple[str, str, set[str]]] = {
    # Familie:      (Farbe,     Anzeige,          Klassen)
    "text":        ("#2a78d6", "Fließtext",       {"text", "abstract", "content",
                                                   "reference", "reference_content",
                                                   "algorithm", "vertical_text"}),
    "titel":       ("#eb6834", "Überschrift",     {"doc_title", "paragraph_title"}),
    "bild":        ("#1baf7a", "Bild / Grafik",   {"image", "chart", "seal",
                                                   "header_image", "footer_image"}),
    "legende":     ("#eda100", "Bildbezug",       {"figure_title", "vision_footnote"}),
    "marginalie":  ("#e87ba4", "Marginalie",      {"aside_text"}),
    "tabelle":     ("#008300", "Tabelle",         {"table"}),
    "formel":      ("#4a3aa7", "Formel",          {"display_formula", "inline_formula",
                                                   "formula_number"}),
    "fussnote":    ("#e34948", "Fußnote",         {"footnote"}),
    "rahmen":      ("#8a8983", "Kopf / Fuß",      {"header", "footer", "number"}),
}
_FAMILIE_VON = {k: fam for fam, (_, _, klassen) in FAMILIEN.items() for k in klassen}

STROM_FARBE: dict[Strom, str] = {
    Strom.HAUPT: "#2a78d6",
    Strom.MARGINALIE: "#e87ba4",
    Strom.BOILERPLATE: "#8a8983",
    Strom.APPARAT: "#eb6834",
}

TINTE = "#0b0b0b"          # Text auf hellen Flächen
TINTE_HELL = "#ffffff"
KANTE = "#52514e"          # Pfeile der Lesefolge
WIDERSPRUCH = "#e34948"    # Lesekante mit negativer Marge


def familie(pp_label: str) -> str:
    return _FAMILIE_VON.get(pp_label, "text")


def farbe(block_oder_label: Block | str, faerbung: str = "klasse") -> str:
    if faerbung == "strom" and isinstance(block_oder_label, Block):
        return STROM_FARBE[block_oder_label.strom]
    label = (block_oder_label.pp_label if isinstance(block_oder_label, Block)
             else block_oder_label)
    return FAMILIEN[familie(label)][0]


def _rgb(hexwert: str) -> tuple[int, int, int]:
    h = hexwert.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _tinte_auf(hexwert: str) -> str:
    """Schwarz oder Weiß – je nachdem, was auf der Tagfarbe lesbarer ist."""
    r, g, b = (c / 255 for c in _rgb(hexwert))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return TINTE if lum > 0.55 else TINTE_HELL


def legende_html(faerbung: str = "klasse") -> str:
    """Kleine Farblegende für Gradio/Notebook."""
    if faerbung == "strom":
        eintraege = [(STROM_FARBE[s], s.value) for s in Strom]
    else:
        eintraege = [(f, name) for f, name, _ in FAMILIEN.values()]
    teile = [f'<span style="display:inline-flex;align-items:center;margin:0 10px 4px 0">'
             f'<span style="width:12px;height:12px;border-radius:3px;background:{f};'
             f'margin-right:5px;display:inline-block"></span>{n}</span>'
             for f, n in eintraege]
    return '<div style="font-size:13px;line-height:1.6">' + "".join(teile) + "</div>"


# ------------------------------------------------------------------ Zeichnen

def _schrift(groesse: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=groesse)
    except TypeError:                     # Pillow < 10.1
        return ImageFont.load_default()


def _als_pil(bild) -> Image.Image:
    if isinstance(bild, Image.Image):
        return bild.convert("RGB")
    return Image.fromarray(np.asarray(bild)).convert("RGB")


def _pfeil(zeichner: ImageDraw.ImageDraw, a, b, farbe_rgba, breite: int) -> None:
    zeichner.line([a, b], fill=farbe_rgba, width=breite)
    winkel = math.atan2(b[1] - a[1], b[0] - a[0])
    laenge = 4 * breite + 6
    for d in (0.45, -0.45):
        zeichner.line([b, (b[0] - laenge * math.cos(winkel + d),
                           b[1] - laenge * math.sin(winkel + d))],
                      fill=farbe_rgba, width=breite)


def zeichne_bloecke(bild, bloecke: list[Block], skala: float = 1.0, *,
                    kanten: list[Lesekante] | None = None,
                    faerbung: str = "klasse",
                    klassen: set[str] | None = None,
                    polygone: bool = True,
                    beschriftung: bool = True,
                    lesefolge: bool = True,
                    hervorheben: int | None = None) -> Image.Image:
    """Blöcke über ein Seitenbild legen.

    `skala` rechnet Bildpixel des Befunds (bei `render_dpi`) in Pixel des
    übergebenen Bildes um – der Viewer zeigt die Seite kleiner, als das
    Modell sie gesehen hat. `klassen` blendet alle anderen Klassen aus.
    """
    grund = _als_pil(bild)
    ebene = Image.new("RGBA", grund.size, (0, 0, 0, 0))
    z = ImageDraw.Draw(ebene)
    breite_px = grund.size[0]
    linie = max(2, round(breite_px / 600))
    schrift = _schrift(max(11, round(breite_px / 85)))

    sichtbar = [b for b in bloecke if klassen is None or b.pp_label in klassen]

    # Flächen und Umrisse
    for b in sichtbar:
        r, g, bl = _rgb(farbe(b, faerbung))
        hell = hervorheben is None or b.id == hervorheben
        fuell = (r, g, bl, 70 if b.id == hervorheben else (38 if hell else 12))
        rand = (r, g, bl, 255 if hell else 110)
        dicke = linie * 2 if b.id == hervorheben else linie
        if polygone and b.polygon:
            punkte = [(x * skala, y * skala) for x, y in b.polygon]
            z.polygon(punkte, fill=fuell)
            z.line(punkte + [punkte[0]], fill=rand, width=dicke, joint="curve")
        else:
            rechteck = [b.bbox.x0 * skala, b.bbox.y0 * skala,
                        b.bbox.x1 * skala, b.bbox.y1 * skala]
            z.rectangle(rechteck, fill=fuell, outline=rand, width=dicke)

    # Lesefolge: Pfeile zwischen den Mittelpunkten, Nummern in Kreisen
    if lesefolge and sichtbar:
        mitte = {b.id: ((b.bbox.x0 + b.bbox.x1) / 2 * skala,
                        (b.bbox.y0 + b.bbox.y1) / 2 * skala) for b in sichtbar}
        widerspruch = {(k.von, k.nach) for k in (kanten or [])
                       if k.marge is not None and k.marge < 0}
        folge = sorted(sichtbar, key=lambda b: (b.lese_index if b.lese_index
                                                is not None else 10**9, b.id))
        for a, b in zip(folge, folge[1:]):
            schlecht = (a.id, b.id) in widerspruch
            _pfeil(z, mitte[a.id], mitte[b.id],
                   _rgb(WIDERSPRUCH if schlecht else KANTE) + ((235 if schlecht else 150),),
                   linie * (2 if schlecht else 1))
        radius = max(9, round(breite_px / 110))
        # Im Kreis steht die Block-id: der Befund ist nach Lesefolge sortiert,
        # die id ist also zugleich die Position – und dieselbe Zahl wie in
        # Beschriftung, Tabelle und Auffälligkeiten.
        for b in folge:
            cx, cy = mitte[b.id]
            z.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                      fill=_rgb(KANTE) + (230,), outline=(255, 255, 255, 255), width=2)
            z.text((cx, cy), str(b.id), fill=TINTE_HELL, font=schrift, anchor="mm")

    # Beschriftung oben links an jeder Box
    if beschriftung:
        for b in sichtbar:
            f = farbe(b, faerbung)
            text = f"#{b.id} {b.pp_label} {b.score:.2f}"
            x, y = b.bbox.x0 * skala, b.bbox.y0 * skala
            l, o, r, u = z.textbbox((0, 0), text, font=schrift)
            h = u - o + 4
            y = y - h if y - h >= 0 else y
            z.rectangle([x, y, x + (r - l) + 6, y + h], fill=_rgb(f) + (235,))
            z.text((x + 3, y + 2 - o), text, fill=_tinte_auf(f), font=schrift)

    return Image.alpha_composite(grund.convert("RGBA"), ebene).convert("RGB")


def zeichne_befund(bild, befund: SeitenBefund, **kw) -> Image.Image:
    """Wie `zeichne_bloecke`, Skala aus der Bildbreite erschlossen."""
    grund = _als_pil(bild)
    skala = grund.size[0] / befund.bild_breite_px if befund.bild_breite_px else 1.0
    return zeichne_bloecke(grund, befund.bloecke, skala, kanten=befund.kanten, **kw)


# ----------------------------------------------------------- Rohlauf (Mikroskop)

@dataclass
class Rohlauf:
    """Alles, was zwischen Seite und Befund entsteht – nichts davon wird gespeichert."""

    bild: np.ndarray                  # Render bei `dpi`, HxWx3 uint8
    tensor: np.ndarray                # 1x3x800x800 float32
    ausgaben: dict[str, np.ndarray]   # logits, pred_boxes, order_logits, out_masks
    dauer_s: float
    dpi: int
    seite_pt: tuple[float, float]     # Breite, Höhe der PDF-Seite in Punkt

    @property
    def breite(self) -> int:
        return self.bild.shape[1]

    @property
    def hoehe(self) -> int:
        return self.bild.shape[0]

    @property
    def wahrscheinlichkeiten(self) -> np.ndarray:
        """(300, 25): sigmoid je Query und Klasse. Kein Softmax – DETR mit
        Focal Loss bewertet jede Klasse unabhängig."""
        return layout._sigmoid(self.ausgaben["logits"][0])

    @property
    def boxen_norm(self) -> np.ndarray:
        """(300, 4) xyxy in 0..1 – aus cxcywh, sonst unverändert."""
        cxcy, wh = self.ausgaben["pred_boxes"][0][:, :2], self.ausgaben["pred_boxes"][0][:, 2:]
        return np.concatenate([cxcy - wh / 2, cxcy + wh / 2], axis=1)

    def dekodieren(self, schwelle: float = 0.5, familien_retten: bool = True):
        return layout.dekodieren(self.ausgaben, self.breite, self.hoehe, schwelle,
                                 familien_retten=familien_retten)


def roh_rechnen(detektor: "layout.Detektor", pdf: Path, seite: int = 0,
                dpi: int = layout.RENDER_DPI) -> Rohlauf:
    """Genau die Schritte von `Detektor.erkenne`, aber mit allen Zwischenständen."""
    bild, pg = layout.seite_rendern(Path(pdf), dpi, seite)
    breite_pt, hoehe_pt = float(pg.rect.width), float(pg.rect.height)
    tensor = layout.vorverarbeiten(bild)
    t0 = time.perf_counter()
    roh = detektor.sitzung.run(None, {detektor.eingang: tensor})
    dauer = time.perf_counter() - t0
    return Rohlauf(bild=bild, tensor=tensor, ausgaben=dict(zip(detektor.ausgaenge, roh)),
                   dauer_s=dauer, dpi=dpi, seite_pt=(breite_pt, hoehe_pt))


def tensor_als_bild(tensor: np.ndarray) -> np.ndarray:
    """1x3x800x800 float -> 800x800x3 uint8, also das, was das Modell „sieht“."""
    t = tensor[0].transpose(1, 2, 0)
    if t.max() <= 1.0:
        t = t * 255.0
    return np.clip(t, 0, 255).astype(np.uint8)


def zeichne_queries(bild, lauf: Rohlauf, schwelle: float = 0.5,
                    nur_ueber: float = 0.0) -> Image.Image:
    """Alle 300 Hypothesen: Deckkraft ~ bester Klassenscore.

    Über der Schwelle kräftig in der Familienfarbe, darunter grau. Genau das
    Bild, das erklärt, warum DETR kein NMS braucht: die meisten Queries sind
    schlicht „kein Objekt“ und werden fast unsichtbar.
    """
    grund = _als_pil(bild)
    w, h = grund.size
    ebene = Image.new("RGBA", grund.size, (0, 0, 0, 0))
    z = ImageDraw.Draw(ebene)
    p = lauf.wahrscheinlichkeiten
    beste, klasse = p.max(axis=1), p.argmax(axis=1)
    boxen = lauf.boxen_norm * np.array([w, h, w, h])
    for i in np.argsort(beste):                    # starke zuletzt, also oben
        s = float(beste[i])
        if s < nur_ueber:
            continue
        ueber = s >= schwelle
        f = _rgb(farbe(PP_LABELS[int(klasse[i])])) if ueber else (90, 90, 90)
        alpha = int(40 + 215 * s) if ueber else int(25 + 200 * s)
        z.rectangle(boxen[i].tolist(), outline=f + (alpha,),
                    width=3 if ueber else 1)
    return Image.alpha_composite(grund.convert("RGBA"), ebene).convert("RGB")


def folgematrix(lauf: Rohlauf, query_ids: list[int]) -> np.ndarray:
    """P[i, j] = Wahrscheinlichkeit, dass Query j nach Query i gelesen wird.

    Aus der 300x300-Zeigermatrix, die nur ihr oberes Dreieck wirklich nutzt
    (`layout.folgt_auf`). In Lesereihenfolge sortiert steht oberhalb der
    Diagonale 1, unterhalb 0 – jede Abweichung ist eine Unsicherheit.
    """
    _, s = layout.lese_raenge(lauf.ausgaben["order_logits"][0])
    n = len(query_ids)
    m = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            if i != j and query_ids[i] != query_ids[j]:
                m[i, j] = layout.folgt_auf(s, query_ids[i], query_ids[j])
    return m


# -------------------------------------------------------------- Sichtprüfung

SCHWACHER_SCORE = 0.6
ENTHALTEN = 0.9
RANDSPALTE = 0.35      # Anteil der Seitenbreite, in dem eine Marginalie liegt


def auffaelligkeiten(befund: SeitenBefund) -> list[tuple[str, str]]:
    """Was an dieser Seite einen zweiten Blick verdient.

    Liefert (Schwere, Text) mit Schwere in {"fehler", "warnung", "hinweis"}.
    Die Regeln sind bewusst einfach und erklärbar – sie sortieren die Seiten
    für die Sichtprüfung vor, sie entscheiden nichts.
    """
    befunde: list[tuple[str, str]] = []
    if befund.fehler:
        befunde.append(("fehler", f"Seite übersprungen: {befund.fehler}"))
    if not befund.bloecke and not befund.fehler:
        befunde.append(("fehler", "Keine einzige Detektion."))

    for w in befund.warnungen:
        schwere = "hinweis" if ("zusammengeführt" in w or "gerettet" in w) else "warnung"
        befunde.append((schwere, w))

    for b in befund.bloecke:
        if b.score < SCHWACHER_SCORE:
            gerettet = (f", über Klassenfamilie gerettet ({b.familien_score:.2f})"
                        if b.familien_score is not None else "")
            befunde.append(("warnung", f"#{b.id} {b.pp_label}: unsicher "
                                       f"(Score {b.score:.2f}{gerettet})."))

    for a in befund.bloecke:
        for b in befund.bloecke:
            if a.id != b.id and a.bbox.enthalten_in(b.bbox) >= ENTHALTEN:
                befunde.append(("warnung", f"#{a.id} {a.pp_label} liegt in "
                                           f"#{b.id} {b.pp_label} – doppelt erkannt?"))

    for k in befund.kanten:
        if k.marge is not None and k.marge < 0:
            befunde.append(("warnung", f"Lesefolge #{k.von} → #{k.nach}: das Modell "
                                       f"widerspricht sich selbst (Marge {k.marge:.0f})."))

    if befund.stufe.value >= 2:
        for b in befund.bloecke:
            if b.textartig and not b.text and not b.ausschnitt:
                befunde.append(("warnung", f"#{b.id} {b.pp_label}: kein Text erkannt."))

    # Randspalten-Heuristik: schmaler Fließtext ganz am Rand ist oft eine
    # Marginalie, die das Modell nicht als aside_text erkannt hat.
    breite = befund.bild_breite_px or 1
    for b in befund.bloecke:
        if b.pp_label != "text" or b.bbox.breite > RANDSPALTE * breite:
            continue
        if b.bbox.x1 <= RANDSPALTE * breite or b.bbox.x0 >= (1 - RANDSPALTE) * breite:
            befunde.append(("hinweis", f"#{b.id} text liegt schmal in der Randspalte – "
                                       "Marginalie (aside_text)?"))
    return befunde


GEWICHT = {"fehler": 100, "warnung": 3, "hinweis": 1}


def verdachtswert(befund: SeitenBefund) -> int:
    return sum(GEWICHT[s] for s, _ in auffaelligkeiten(befund))
