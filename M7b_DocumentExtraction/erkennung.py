"""Stufe 2: das Feld `text` füllen.

Benachbarte Blöcke zusammenführen, Ausschnitte mit proportionalem Rand
schneiden, je nach Klasse einen der festen PaddleOCR-VL-Prompts schicken,
Ausgabe nachbereiten.

Inhaltlich unverändert gegenüber Notebook 3. Geändert ist die Fassung: der
Zugang zu LM Studio liegt in einer Klasse, die Modellzeit landet als
`Laufspur` im Befund statt als Satz in `warnungen`.
"""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import requests

from schema import (
    Bbox, Bezugsrahmen, Block, Lesekante, SeitenBefund, Strom, Stufe, TEXTARTIG,
)

PROBE_DPI = 300        # Ausschnitte höher auflösen als die Layout-Analyse
RAND_ANTEIL = 0.12     # Rand als Anteil der Boxhöhe
RAND_MIN_PX = 3        # untere Schranke, bei 200 dpi gemessen
RAND_MAX_PX = 16       # obere Schranke
MAX_LUECKE_PX = 40     # waagerechter Abstand, bis zu dem zusammengeführt wird
MIN_UEBERLAPP = 0.5    # senkrechte Überlappung, ab der zusammengeführt wird


# ------------------------------------------------------------ Zusammenführen

def _v_ueberlappung(a: Bbox, b: Bbox) -> float:
    """Senkrechte Überlappung, bezogen auf die kleinere der beiden Höhen."""
    oben, unten = max(a.y0, b.y0), min(a.y1, b.y1)
    if unten <= oben:
        return 0.0
    return (unten - oben) / max(1e-6, min(a.hoehe, b.hoehe))


def _h_luecke(a: Bbox, b: Bbox) -> float:
    """Waagerechter Abstand. 0, wenn sich die Boxen überlappen."""
    if a.x1 < b.x0:
        return b.x0 - a.x1
    if b.x1 < a.x0:
        return a.x0 - b.x1
    return 0.0


def gruppieren(bloecke: list[Block]) -> list[list[int]]:
    """Indizes zusammengehöriger Blöcke. Union-Find, weil Nachbarschaft transitiv ist."""
    n = len(bloecke)
    eltern = list(range(n))

    def finde(i: int) -> int:
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]      # Pfadverkürzung
            i = eltern[i]
        return i

    def vereine(i: int, j: int) -> None:
        a, b = finde(i), finde(j)
        if a != b:
            eltern[max(a, b)] = min(a, b)

    for i in range(n):
        for j in range(i + 1, n):
            a, b = bloecke[i], bloecke[j]
            if a.strom is not b.strom:
                continue
            if a.pp_label not in TEXTARTIG or b.pp_label not in TEXTARTIG:
                continue
            if _v_ueberlappung(a.bbox, b.bbox) < MIN_UEBERLAPP:
                continue
            if _h_luecke(a.bbox, b.bbox) > MAX_LUECKE_PX:
                continue
            vereine(i, j)

    gruppen: dict[int, list[int]] = {}
    for i in range(n):
        gruppen.setdefault(finde(i), []).append(i)
    return [sorted(g) for g in gruppen.values()]


def zusammenfuehren(befund: SeitenBefund) -> SeitenBefund:
    """Neuer Befund mit zusammengeführten Blöcken. Der alte bleibt unberührt."""
    gruppen = gruppieren(befund.bloecke)
    gruppen.sort(key=lambda g: min(befund.bloecke[i].lese_index if
                                   befund.bloecke[i].lese_index is not None
                                   else befund.bloecke[i].id for i in g))

    neu: list[Block] = []
    abbildung: dict[int, int] = {}          # alte Block-id -> neue Block-id

    for neue_id, gruppe in enumerate(gruppen):
        mitglieder = [befund.bloecke[i] for i in gruppe]
        for m in mitglieder:
            abbildung[m.id] = neue_id

        if len(mitglieder) == 1:
            neu.append(mitglieder[0].model_copy(update={"id": neue_id}))
            continue

        # Der breiteste Block gibt Label und Query vor – er trägt am meisten Inhalt.
        leit = max(mitglieder, key=lambda b: b.bbox.breite)
        neu.append(Block(
            id=neue_id,
            query_id=leit.query_id,
            pp_label=leit.pp_label,
            score=min(m.score for m in mitglieder),      # konservativ
            bbox=Bbox(
                x0=min(m.bbox.x0 for m in mitglieder),
                y0=min(m.bbox.y0 for m in mitglieder),
                x1=max(m.bbox.x1 for m in mitglieder),
                y1=max(m.bbox.y1 for m in mitglieder),
                rahmen=Bezugsrahmen.BILD_PIXEL),
            lese_index=min((m.lese_index for m in mitglieder
                            if m.lese_index is not None), default=None),
            polygon=None,                                # Vereinigung wäre gelogen
            zusammengefuehrt_aus=[m.id for m in mitglieder],
        ))

    # Kanten umschreiben: interne fallen weg, doppelte werden pessimistisch vereint
    kanten: dict[tuple[int, int], Lesekante] = {}
    for k in befund.kanten:
        v, n = abbildung.get(k.von), abbildung.get(k.nach)
        if v is None or n is None or v == n:
            continue
        vorhanden = kanten.get((v, n))
        if vorhanden is None or (k.marge is not None and vorhanden.marge is not None
                                 and k.marge < vorhanden.marge):
            kanten[(v, n)] = Lesekante(von=v, nach=n, konfidenz=k.konfidenz,
                                       marge=k.marge)

    warnungen = list(befund.warnungen)
    for b in neu:
        if b.zusammengefuehrt_aus:
            warnungen.append(
                f"Blöcke {b.zusammengefuehrt_aus} zu #{b.id} ({b.pp_label}) "
                "zusammengeführt.")

    return befund.model_copy(update={
        "bloecke": neu, "kanten": list(kanten.values()), "warnungen": warnungen})


# ----------------------------------------------------------------- Ausschnitte

class Seitenbild:
    """Hält die hoch aufgelöste Seite und schneidet Blöcke daraus.

    Layout auf der verkleinerten Kopie, Ausschnitte aus dem Original: die
    Boxen liegen bei `befund.render_dpi`, geschnitten wird bei `dpi`.
    """

    def __init__(self, pdf: Path, befund: SeitenBefund, dpi: int = PROBE_DPI,
                 dok: "pymupdf.Document | None" = None):
        eigenes_dok = dok is None
        dok = dok or pymupdf.open(pdf)
        try:
            self.pg = dok[befund.seite]
            pix = self.pg.get_pixmap(dpi=dpi)
            roh = np.frombuffer(pix.samples, dtype=np.uint8)
            self.bild = np.ascontiguousarray(
                roh.reshape(pix.height, pix.width, pix.n)[:, :, :3])
        finally:
            if eigenes_dok:
                dok.close()
        self.faktor = dpi / befund.render_dpi
        self.dpi = dpi

    def rand(self, box: Bbox) -> float:
        """Rand in Befund-Pixeln, proportional zur Boxhöhe und beidseitig gedeckelt.

        Ein fester Rand ist für einen Fließtextblock unauffällig und für eine
        31 px hohe Seitenzahl ein Viertel der Bildhöhe.
        """
        return float(np.clip(box.hoehe * RAND_ANTEIL, RAND_MIN_PX, RAND_MAX_PX))

    def ausschnitt(self, block: Block) -> np.ndarray:
        bx = block.bbox
        r = self.rand(bx) * self.faktor
        h, b = self.bild.shape[:2]
        x0 = int(max(0, bx.x0 * self.faktor - r))
        y0 = int(max(0, bx.y0 * self.faktor - r))
        x1 = int(min(b, bx.x1 * self.faktor + r))
        y1 = int(min(h, bx.y1 * self.faktor + r))
        return self.bild[y0:y1, x0:x1]


def als_datenurl(bild_rgb: np.ndarray) -> str:
    ok, puffer = cv2.imencode(".png", bild_rgb[:, :, ::-1])      # cv2 will BGR
    if not ok:
        raise RuntimeError("PNG-Kodierung fehlgeschlagen")
    return "data:image/png;base64," + base64.b64encode(puffer).decode("ascii")


# ------------------------------------------------------- Prompt und Token-Deckel

# PaddleOCR-VL nimmt keine freien Anweisungen entgegen: eines von sechs Präfixen.
PROMPT_FUER: dict[str, str | None] = {
    "text": "OCR:", "paragraph_title": "OCR:", "doc_title": "OCR:",
    "abstract": "OCR:", "aside_text": "OCR:", "footnote": "OCR:",
    "vision_footnote": "OCR:", "figure_title": "OCR:", "content": "OCR:",
    "header": "OCR:", "footer": "OCR:", "number": "OCR:",
    "reference": "OCR:", "reference_content": "OCR:", "algorithm": "OCR:",
    "vertical_text": "OCR:", "formula_number": "OCR:",
    "display_formula": "Formula Recognition:",
    "inline_formula": "Formula Recognition:",
    "table": "Table Recognition:",
    "chart": "Chart Recognition:",
    "seal": "Seal Recognition:",
    "image": None, "header_image": None, "footer_image": None,
}

FORMAT_FUER: dict[str, str] = {
    "OCR:": "klartext",
    "Formula Recognition:": "latex",
    "Table Recognition:": "otsl",
    "Chart Recognition:": "datenreihe",
    "Seal Recognition:": "klartext",
}

# Sicherung, keine Optimierung: eine Seitenzahl, die plötzlich 1024 Tokens
# erzeugt, ist keine Seitenzahl mehr, sondern eine Schleife.
MAX_TOKENS_FUER: dict[str, int] = {
    "number": 64, "header": 256, "footer": 256, "formula_number": 64,
    "inline_formula": 256, "display_formula": 512,
    "table": 4096, "chart": 1024,
    "content": 4096,        # Inhaltsverzeichnis: eine Spalte, viele Zeilen
    "reference": 4096,      # Literaturseiten sind ein einziger langer Block
    "text": 2048,
}
MAX_TOKENS_STANDARD = 1024


def nachbereiten(text: str, pp_label: str) -> tuple[str, list[str]]:
    """Rohantwort -> (bereinigter Text, Warnungen).

    Das Modell liefert für beide Formelklassen `\\[…\\]`, die Notation für
    abgesetzte Mathematik. Den Unterschied kennen wir, nicht es: er steht im
    `pp_label`. OTSL bleibt unangetastet – jede Umwandlung hier wäre eine
    Interpretation zur falschen Zeit.
    """
    t = text.strip()
    warnungen: list[str] = []

    if pp_label in ("inline_formula", "display_formula"):
        treffer = re.fullmatch(r"\\\[(.*?)\\\]", t, flags=re.S)
        if treffer:
            inhalt = treffer.group(1).strip()
            t = f"${inhalt}$" if pp_label == "inline_formula" else f"$$\n{inhalt}\n$$"
        elif not t.startswith("$"):
            warnungen.append(f"Formel ohne erkennbare Delimiter: {t[:40]!r}")

    if pp_label == "table" and "<fcel>" not in t and "<ecel>" not in t:
        warnungen.append("Tabelle ohne OTSL-Marken – Ausgabe unstrukturiert.")

    if not t:
        warnungen.append("Leere Antwort.")

    return t, warnungen


# ---------------------------------------------------------------- Der Erkenner

class Erkenner:
    """Zugang zu PaddleOCR-VL über die OpenAI-kompatible Schnittstelle von LM Studio."""

    def __init__(self, url: str = "http://localhost:1234/v1",
                 modell_id: str | None = None, zeitlimit: int = 300):
        self.url = url.rstrip("/")
        self.zeitlimit = zeitlimit
        self.modell_id = modell_id or self.geladene_modelle()[0]

    def geladene_modelle(self) -> list[str]:
        antwort = requests.get(f"{self.url}/models", timeout=10)
        antwort.raise_for_status()
        return [m["id"] for m in antwort.json()["data"]]

    def erkennen(self, bild_rgb: np.ndarray, prompt: str,
                 max_tokens: int) -> tuple[str, float, str | None]:
        """temperature=0: eine Pipeline, deren Ausgabe sich beim zweiten Lauf
        ändert, lässt sich weder prüfen noch gegen ein Goldset messen."""
        nutzlast = {
            "model": self.modell_id,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": als_datenurl(bild_rgb)}},
                    {"type": "text", "text": prompt},
                ],
            }],
        }
        t0 = time.perf_counter()
        antwort = requests.post(f"{self.url}/chat/completions", json=nutzlast,
                                timeout=self.zeitlimit)
        dauer = time.perf_counter() - t0
        if not antwort.ok:
            raise RuntimeError(
                f"LM Studio {antwort.status_code} bei Modell {self.modell_id!r}: "
                f"{antwort.text[:400]}")
        wahl = antwort.json()["choices"][0]
        return wahl["message"]["content"], dauer, wahl.get("finish_reason")

    def erkenne_seite(self, befund: SeitenBefund, pdf: Path, buch: str,
                      ausschnitt_dir: Path = Path("ausschnitte"),
                      zeige_fortschritt: bool = False,
                      dok: "pymupdf.Document | None" = None) -> SeitenBefund:
        """Befund der Stufe 1 -> Befund mit gefülltem Feld `text`.

        Bildblöcke bekommen keinen Modellaufruf. Ihr Ausschnitt landet als PNG,
        der Pfad im Feld `ausschnitt` – damit kann Stufe 4 sie aufgreifen, ohne
        die Seite neu zu rendern.
        """
        t0 = time.perf_counter()
        befund = zusammenfuehren(befund)
        seite = Seitenbild(pdf, befund, dok=dok)
        ausschnitt_dir.mkdir(parents=True, exist_ok=True)

        for blk in befund.bloecke:
            aus = seite.ausschnitt(blk)
            prompt = PROMPT_FUER.get(blk.pp_label)

            if prompt is None:                       # Bildblock: nur ablegen
                ziel = ausschnitt_dir / (
                    f"{buch}_{befund.seite:04d}_{blk.id:02d}_{blk.pp_label}.png")
                cv2.imwrite(str(ziel), aus[:, :, ::-1])
                blk.ausschnitt = str(ziel)
                if zeige_fortschritt:
                    print(f"  #{blk.id:2d} {blk.pp_label:18s} -> {ziel.name}")
                continue

            deckel = MAX_TOKENS_FUER.get(blk.pp_label, MAX_TOKENS_STANDARD)
            text, dauer, grund = self.erkennen(aus, prompt, deckel)
            if grund == "length":
                befund.warnungen.append(
                    f"#{blk.id} ({blk.pp_label}): am Token-Deckel {deckel} "
                    "abgeschnitten – Ausgabe unvollständig.")

            text, warnungen = nachbereiten(text, blk.pp_label)
            blk.text = text
            blk.text_format = FORMAT_FUER[prompt]
            blk.text_quelle = "paddleocr_vl"
            befund.warnungen += [f"#{blk.id}: {w}" for w in warnungen]

            if zeige_fortschritt:
                vorschau = text[:58].replace("\n", " ")
                print(f"  #{blk.id:2d} {blk.pp_label:18s} {dauer:5.2f}s "
                      f"{len(text):5d}z  {vorschau}")

        befund.spur_hinzufuegen(Stufe.ERKANNT, self.modell_id,
                                time.perf_counter() - t0)
        return befund


# ------------------------------------------------------------------- Kontrolle

def als_markdown(befund: SeitenBefund, strom: Strom = Strom.HAUPT) -> str:
    """Grobe Vorschau. Die richtige Umwandlung ist Stufe 4 – hier geht es ums Prüfen.

    Wenn der Hauptstrom sich flüssig lesen lässt, stimmen Lesereihenfolge,
    Zuschnitt und Erkennung zugleich.
    """
    zeilen: list[str] = []
    for blk in befund.lesefolge(strom):
        if blk.ausschnitt:
            zeilen.append(f"![{blk.pp_label}]({blk.ausschnitt})")
        elif blk.text is None:
            zeilen.append(f"<!-- #{blk.id} {blk.pp_label}: kein Text -->")
        elif blk.pp_label == "doc_title":
            zeilen.append(f"# {blk.text}")
        elif blk.pp_label == "paragraph_title":
            zeilen.append(f"## {blk.text}")
        elif blk.pp_label == "figure_title":
            zeilen.append(f"*{blk.text}*")
        elif blk.text_format in ("otsl", "datenreihe"):
            zeilen.append(f"```{blk.text_format}\n{blk.text}\n```")
        else:
            zeilen.append(blk.text)
        zeilen.append("")
    return "\n".join(zeilen)
