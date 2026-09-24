"""Kontext für das Vision-Modell und Docling-Auswertung (Notebook 03, Abschnitt 01).

Neu: der Textkontext kommt vorrangig aus dem **lektorierten** Markdown
(`<BUCH>_korr.md`) rund um den Bildverweis. Das Docling-JSON trägt nur den
unkorrigierten OCR-Text und dient als Rückfall.
"""

from __future__ import annotations

import re
from typing import Any

BILD_RE = re.compile(r"!\[(?P<alt>(?:\\.|[^\]\\])*)\]\((?P<path>[^)\s]+)\)")
UEBERSCHRIFT_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", re.M)
KOMMENTAR_RE = re.compile(r"<!--.*?-->", re.S)


# ------------------------------------------------------------ Docling-JSON

def deref_text(doc: dict[str, Any], ref: str | None) -> str | None:
    if not ref or not ref.startswith("#/texts/"):
        return None
    try:
        item = doc["texts"][int(ref.rsplit("/", 1)[-1])]
        return item.get("text") or item.get("orig")
    except (KeyError, IndexError, ValueError):
        return None


def picture_caption(doc: dict[str, Any], picture: dict[str, Any]) -> str | None:
    vals = []
    for item in picture.get("captions", []):
        if isinstance(item, dict):
            val = deref_text(doc, item.get("$ref"))
            if val and val.strip():
                vals.append(val.strip())
    return " ".join(vals) if vals else None


def _vertikal(bbox: dict[str, Any]) -> tuple[float, float]:
    """(Oberkante, Unterkante), beide von oben gemessen – für beide Ursprünge.

    Stufe 1 schreibt TOPLEFT; Docling selbst verwendet oft BOTTOMLEFT. Das
    Notebook nahm stillschweigend TOPLEFT an.
    """
    t, b = float(bbox.get("t", 0)), float(bbox.get("b", 0))
    if str(bbox.get("coord_origin", "TOPLEFT")).upper().endswith("BOTTOMLEFT"):
        t, b = -t, -b
    return min(t, b), max(t, b)


def nearest_section_heading(doc: dict[str, Any], page_no: int, picture_bbox: dict) -> str | None:
    picture_top = _vertikal(picture_bbox)[0]
    candidates = []
    for item in doc.get("texts", []):
        if item.get("label") != "section_header":
            continue
        for prov in item.get("prov", []):
            if prov.get("page_no") == page_no:
                top = _vertikal(prov.get("bbox", {}))[0]
                if top <= picture_top:
                    candidates.append((top, item.get("text") or item.get("orig") or ""))
    return max(candidates, key=lambda x: x[0])[1].strip() if candidates else None


def nearby_text(doc: dict[str, Any], page_no: int, bbox: dict[str, Any], max_chars: int) -> str:
    pt, pb = _vertikal(bbox)
    candidates = []
    for item in doc.get("texts", []):
        if item.get("content_layer") == "furniture":     # Kopf-/Fußzeilen
            continue
        text = (item.get("text") or item.get("orig") or "").strip()
        if not text:
            continue
        for prov in item.get("prov", []):
            if prov.get("page_no") != page_no:
                continue
            tt, tbot = _vertikal(prov.get("bbox", {}))
            dist = max(0.0, max(tt, pt) - min(tbot, pb))
            candidates.append((dist, tt, text))
            break
    chunks, used = [], 0
    for _, _, text in sorted(candidates, key=lambda x: (x[0], x[1])):
        if used >= max_chars:
            break
        piece = text[:max_chars - used]
        chunks.append(piece)
        used += len(piece) + 2
    return "\n\n".join(chunks)


# ------------------------------------------------------------ Markdown

def _bereinigt(text: str) -> str:
    text = KOMMENTAR_RE.sub(" ", text)
    text = BILD_RE.sub(" ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def markdown_kontext(md_text: str, uri: str, max_chars: int) -> dict[str, str] | None:
    """Überschrift und Text rund um den ersten Verweis auf `uri`.

    Zwei Drittel des Budgets vor dem Bild (Einleitung, Bezug), ein Drittel
    danach (Bildunterschrift, Erläuterung).
    """
    treffer = next((m for m in BILD_RE.finditer(md_text) if m.group("path") == uri), None)
    if treffer is None:
        return None
    davor, danach = md_text[:treffer.start()], md_text[treffer.end():]
    ueberschriften = UEBERSCHRIFT_RE.findall(davor)
    heading = ueberschriften[-1][1].strip() if ueberschriften else ""
    vor = _bereinigt(davor)
    nach = _bereinigt(danach)
    if len(vor) > max_chars * 2 // 3:                  # an einer Wortgrenze beginnen
        vor = vor[-(max_chars * 2 // 3):].split(None, 1)[-1]
    if len(nach) > max_chars // 3:                     # an einer Wortgrenze enden
        nach = nach[:max_chars // 3].rsplit(None, 1)[0]
    return {"section": heading, "text_before": vor, "text_after": nach}
