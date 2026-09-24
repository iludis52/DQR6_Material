"""Layout-Viewer: Befunde seitenweise über dem Original-PDF ansehen.

Start aus dem Notebook `05_layout_einblick.ipynb` oder direkt:

    python python/pipeline/layout_viewer.py

Liest `data/interim/befunde/<dok>/<seite>.json` und legt die Blöcke über die
gerenderte PDF-Seite. Schreibt nichts. Zwei Quellen:

* **Befund (JSON)** – was die Pipeline gespeichert hat, nach Stufe 2 also
  schon mit zusammengeführten Blöcken und erkanntem Text.
* **Live-Modell** – dieselbe Seite frisch durch pp_doclayoutv3, mit frei
  wählbarer Schwelle. Die Rohausgabe wird je Seite einmal gerechnet und
  gemerkt; der Regler dekodiert nur neu.

Ein Klick auf eine Box zeigt Klasse, Score, Lesefolge, Text und Ausschnitt.
„Auffällige Seiten“ sortiert ein Dokument nach `einblick.verdachtswert`.
„HTML-Bericht“ schreibt über `einblick_html` eine eigenständige Datei zum
Verschicken.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):                         # direkter Skriptstart
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "pipeline"

import gradio as gr
import numpy as np
import pymupdf

import pipeline  # noqa: F401  (Suchpfad für pdf_extraction)
import einblick
import einblick_html
import layout
import pfade
from schema import SeitenBefund, Stufe, befund_laden

ANZEIGE_DPI = 110        # Seitenbild im Viewer; die Boxen werden umgerechnet
AUSSCHNITT_DPI = 160
QUELLE_JSON = "Befund (JSON)"
QUELLE_LIVE = "Live-Modell"
OPTIONEN = ["Polygone", "Beschriftung", "Lesefolge"]
FAMILIEN_WAHL = [(name, fam) for fam, (_, name, _) in einblick.FAMILIEN.items()]

CSS = """
#seite img { object-fit: contain; }
.auffaellig { font-size: 13px; }
"""


# ------------------------------------------------------------------ Bestand

def dokumente() -> list[str]:
    """Alle Dokumente mit PDF unter raw/ – mit oder ohne Befunde."""
    mit_befund = {p.name for p in pfade.BEFUNDE.iterdir() if p.is_dir()} \
        if pfade.BEFUNDE.is_dir() else set()
    mit_pdf = {p.stem for p in pfade.RAW.glob("*.pdf")} if pfade.RAW.is_dir() else set()
    return sorted(d for d in mit_befund | mit_pdf if pfade.quelle(d).exists())


@lru_cache(maxsize=32)
def seitenzahl(dok: str) -> int:
    with pymupdf.open(pfade.quelle(dok)) as d:
        return d.page_count


@lru_cache(maxsize=64)
def seitenbild(dok: str, seite: int, dpi: int = ANZEIGE_DPI) -> np.ndarray:
    bild, _ = layout.seite_rendern(pfade.quelle(dok), dpi, seite)
    return bild


def ausschnitt(dok: str, befund: SeitenBefund, block_id: int):
    """Bevorzugt das PNG aus Stufe 2, sonst frisch aus dem PDF geschnitten."""
    b = next((b for b in befund.bloecke if b.id == block_id), None)
    if b is None:
        return None
    if b.ausschnitt:
        datei = pfade.ausschnitt_ordner(dok) / b.ausschnitt
        if datei.exists():
            return str(datei)
    f = 72.0 / befund.render_dpi
    rand = 4
    clip = pymupdf.Rect(b.bbox.x0 * f - rand, b.bbox.y0 * f - rand,
                        b.bbox.x1 * f + rand, b.bbox.y1 * f + rand)
    with pymupdf.open(pfade.quelle(dok)) as d:
        pix = d[befund.seite].get_pixmap(dpi=AUSSCHNITT_DPI, clip=clip)
        return np.frombuffer(pix.samples, np.uint8).reshape(
            pix.height, pix.width, pix.n)[:, :, :3].copy()


# ------------------------------------------------------------------ Befunde

@lru_cache(maxsize=256)
def _json_befund(pfad: str, mtime: float) -> SeitenBefund:
    return befund_laden(Path(pfad))


_DETEKTOR: layout.Detektor | None = None


def _detektor() -> layout.Detektor:
    global _DETEKTOR
    if _DETEKTOR is None:
        _DETEKTOR = layout.Detektor(pfade.ONNX_STANDARD)
    return _DETEKTOR


@lru_cache(maxsize=16)
def _rohlauf(dok: str, seite: int) -> einblick.Rohlauf:
    return einblick.roh_rechnen(_detektor(), pfade.quelle(dok), seite)


def befund_holen(dok: str, seite: int, quelle: str,
                 schwelle: float) -> SeitenBefund | None:
    if quelle == QUELLE_LIVE:
        lauf = _rohlauf(dok, seite)
        bloecke, kanten = lauf.dekodieren(schwelle)
        return SeitenBefund(
            quelle_datei=pfade.quelle(dok).name, seite=seite,
            seite_breite_pt=lauf.seite_pt[0], seite_hoehe_pt=lauf.seite_pt[1],
            render_dpi=lauf.dpi, bild_breite_px=lauf.breite, bild_hoehe_px=lauf.hoehe,
            bloecke=bloecke, kanten=kanten, stufe=Stufe.LAYOUT)
    pfad = pfade.befund(dok, seite)
    if not pfad.exists():
        return None
    return _json_befund(str(pfad), pfad.stat().st_mtime)


def auffaellige_seiten(dok: str) -> list[tuple[str, int]]:
    """(Anzeige, Seite) aller Seiten mit Befund, auffälligste zuerst."""
    if not dok:
        return []
    ordner = pfade.befund_ordner(dok)
    if not ordner.is_dir():
        return []
    liste = []
    for datei in sorted(ordner.glob("*.json")):
        try:
            bf = _json_befund(str(datei), datei.stat().st_mtime)
        except Exception as e:
            liste.append((10**6, int(datei.stem), f"nicht lesbar: {type(e).__name__}"))
            continue
        hinweise = einblick.auffaelligkeiten(bf)
        if hinweise:
            arten = {s for s, _ in hinweise}
            art = "fehler" if "fehler" in arten else ("warnung" if "warnung" in arten
                                                     else "hinweis")
            liste.append((einblick.verdachtswert(bf), bf.seite,
                          f"{len(hinweise)} Auffälligkeit(en), schwerste: {art}"))
    liste.sort(key=lambda t: (-t[0], t[1]))
    return [(f"S. {s + 1} · {text}", s) for _, s, text in liste]


# ------------------------------------------------------------------ Anzeige

SYMBOL = {"fehler": "⛔", "warnung": "⚠️", "hinweis": "ℹ️"}


def _auffaelligkeiten_md(bf: SeitenBefund | None) -> str:
    if bf is None:
        return "_Kein Befund für diese Seite – Stufe 1 lief hier noch nicht. " \
               "Quelle **Live-Modell** wählen, um die Seite trotzdem zu sehen._"
    hinweise = einblick.auffaelligkeiten(bf)
    if not hinweise:
        return "✅ Keine Auffälligkeiten."
    return "\n".join(f"- {SYMBOL[s]} {t}" for s, t in hinweise)


def _tabelle(bf: SeitenBefund | None) -> list[list]:
    if bf is None:
        return []
    return [[b.id, b.pp_label, round(b.score, 3), b.lese_index, b.strom.value,
             (b.text or ("[Bild]" if b.ausschnitt else ""))[:80].replace("\n", " ")]
            for b in bf.bloecke]


def _kopfzeile(dok: str, seite: int, bf: SeitenBefund | None, quelle: str) -> str:
    teile = [f"**{dok}** · Seite {seite + 1} von {seitenzahl(dok)}"]
    if bf is not None:
        teile.append(f"{len(bf.bloecke)} Blöcke")
        teile.append(f"Stufe {bf.stufe.value}" if quelle == QUELLE_JSON
                     else "Stufe 1, nicht gespeichert")
        teile.append(" · ".join(f"{s.modell} {s.dauer_s:.2f}s" for s in bf.spuren)
                     if bf.spuren else "")
    return " · ".join(t for t in teile if t)


def _details_md(bf: SeitenBefund | None, block_id: int | None) -> str:
    if bf is None or block_id is None:
        return "_Auf eine Box im Bild oder eine Zeile der Tabelle klicken._"
    b = next((b for b in bf.bloecke if b.id == block_id), None)
    if b is None:
        return "_Block nicht (mehr) vorhanden._"
    kanten_rein = [k for k in bf.kanten if k.nach == b.id]
    kanten_raus = [k for k in bf.kanten if k.von == b.id]
    zeilen = [
        f"### #{b.id} · `{b.pp_label}`",
        f"| | |\n|---|---|",
        f"| Score | {b.score:.3f} |",
        f"| Query | {b.query_id} von 300 |",
        f"| Lese-Index | {b.lese_index} |",
        f"| Strom | {b.strom.value} |",
        f"| docling | {b.docling_label or '–'}"
        + (f" (Verlust: {b.verlust})" if b.verlust else "") + " |",
        f"| Bbox (px @ {bf.render_dpi} dpi) | {b.bbox.x0:.0f}, {b.bbox.y0:.0f} – "
        f"{b.bbox.x1:.0f}, {b.bbox.y1:.0f} |",
        f"| Polygon | {len(b.polygon)} Ecken |" if b.polygon else "| Polygon | – |",
    ]
    for k in kanten_rein:
        zeilen.append(f"| kommt von | #{k.von} (Marge {k.marge:.0f}) |"
                      if k.marge is not None else f"| kommt von | #{k.von} |")
    for k in kanten_raus:
        zeilen.append(f"| geht nach | #{k.nach} (Marge {k.marge:.0f}) |"
                      if k.marge is not None else f"| geht nach | #{k.nach} |")
    if b.zusammengefuehrt_queries:
        zeilen.append(f"| zusammengeführt aus Queries | {b.zusammengefuehrt_queries} |")
    elif b.zusammengefuehrt_aus:
        zeilen.append(f"| zusammengeführt aus (Stufe-1-ids) | {b.zusammengefuehrt_aus} |")
    if b.familien_score is not None:
        zeilen.append(f"| über Familie gerettet | kombiniert {b.familien_score:.2f} |")
    if b.text:
        zeilen.append(f"\n**Text** ({b.text_format or '?'}, {b.text_quelle or '?'}):\n")
        zeilen.append("```\n" + b.text.strip() + "\n```")
    elif b.ausschnitt:
        zeilen.append(f"\n**Ausschnitt statt Text:** `{b.ausschnitt}`")
    return "\n".join(zeilen)


def anzeigen(dok, seite_menschlich, quelle, schwelle, faerbung, optionen,
             familien, auswahl):
    """Alles, was sich bei jeder Änderung neu aufbaut."""
    if not dok:
        return None, "_Kein Dokument unter data/raw._", "", [], "", None
    seite = int(max(1, min(int(seite_menschlich or 1), seitenzahl(dok)))) - 1
    bf = befund_holen(dok, seite, quelle, float(schwelle))
    bild = seitenbild(dok, seite)

    erlaubt = {k for fam in (familien or []) for k in einblick.FAMILIEN[fam][2]}
    if bf is None:
        overlay = bild
    else:
        overlay = einblick.zeichne_befund(
            bild, bf, faerbung="strom" if faerbung == "Strom" else "klasse",
            klassen=erlaubt, polygone="Polygone" in optionen,
            beschriftung="Beschriftung" in optionen,
            lesefolge="Lesefolge" in optionen, hervorheben=auswahl)
    return (overlay, _kopfzeile(dok, seite, bf, quelle), _auffaelligkeiten_md(bf),
            _tabelle(bf), _details_md(bf, auswahl),
            ausschnitt(dok, bf, auswahl) if bf is not None and auswahl is not None else None)


def block_unter(dok, seite_menschlich, quelle, schwelle, evt: gr.SelectData):
    """Klick ins Bild -> kleinste Box, die den Punkt enthält."""
    seite = int(seite_menschlich) - 1
    bf = befund_holen(dok, seite, quelle, float(schwelle))
    if bf is None:
        return None
    x, y = evt.index
    skala = bf.bild_breite_px / seitenbild(dok, seite).shape[1]
    px, py = x * skala, y * skala
    treffer = [b for b in bf.bloecke
               if b.bbox.x0 <= px <= b.bbox.x1 and b.bbox.y0 <= py <= b.bbox.y1]
    return min(treffer, key=lambda b: b.bbox.flaeche).id if treffer else None


def zeile_gewaehlt(tabelle, evt: gr.SelectData):
    try:
        zeile = evt.index[0]
        return int(tabelle.iloc[zeile, 0]) if hasattr(tabelle, "iloc") \
            else int(tabelle[zeile][0])
    except Exception:
        return None


# --------------------------------------------------------------- Oberfläche

def baue_oberflaeche() -> gr.Blocks:
    alle = dokumente()
    with gr.Blocks(title="Layout-Viewer") as demo:
        gr.Markdown("## Layout-Viewer · pp_doclayoutv3")
        auswahl = gr.State(None)

        with gr.Row():
            dok = gr.Dropdown(alle, value=alle[0] if alle else None,
                              label="Dokument", scale=3)
            zurueck = gr.Button("◀", scale=0, min_width=50)
            seite = gr.Number(value=1, precision=0, minimum=1, label="Seite", scale=1)
            vor = gr.Button("▶", scale=0, min_width=50)
            verdacht = gr.Dropdown([], label="Auffällige Seiten (auffälligste zuerst)",
                                   scale=3)

        kopf = gr.Markdown()
        with gr.Row():
            with gr.Column(scale=3):
                bild = gr.Image(type="pil", interactive=False, show_label=False,
                                elem_id="seite", height=900)
            with gr.Column(scale=2):
                with gr.Row():
                    quelle = gr.Radio([QUELLE_JSON, QUELLE_LIVE], value=QUELLE_JSON,
                                      label="Quelle")
                    faerbung = gr.Radio(["Klasse", "Strom"], value="Klasse",
                                        label="Färbung")
                schwelle = gr.Slider(0.05, 0.95, value=0.5, step=0.05, visible=False,
                                     label="Schwelle (nur Live-Modell)")
                optionen = gr.CheckboxGroup(OPTIONEN, value=OPTIONEN, label="Anzeige")
                familien = gr.CheckboxGroup(FAMILIEN_WAHL,
                                            value=[f for _, f in FAMILIEN_WAHL],
                                            label="Klassenfamilien")
                legende = gr.HTML(einblick.legende_html())
                with gr.Accordion("Auffälligkeiten dieser Seite", open=True):
                    hinweise = gr.Markdown(elem_classes="auffaellig")
                with gr.Accordion("Gewählter Block", open=True):
                    details = gr.Markdown()
                    schnitt = gr.Image(show_label=False, interactive=False, height=220)
                with gr.Accordion("HTML-Bericht zum Verschicken", open=False):
                    gr.Markdown("Eine eigenständige HTML-Datei mit Seitenbildern und "
                                "Befunden – öffnet sich ohne Python in jedem Browser.")
                    exp_auff = gr.Checkbox(False, label="nur auffällige Seiten")
                    exp_dpi = gr.Slider(60, 150, value=100, step=10,
                                        label="Auflösung (dpi) – ca. 170 KB je Seite bei 100")
                    exp_knopf = gr.Button("HTML exportieren")
                    exp_datei = gr.File(label="Bericht", interactive=False)

        tabelle = gr.Dataframe(headers=["id", "Klasse", "Score", "Lese-Index",
                                        "Strom", "Text"],
                               interactive=False, wrap=True, label="Blöcke")

        eingaben = [dok, seite, quelle, schwelle, faerbung, optionen, familien, auswahl]
        ausgaben = [bild, kopf, hinweise, tabelle, details, schnitt]

        def _seitenwahl(d):
            return gr.update(choices=auffaellige_seiten(d), value=None), 1, None

        def _blaettern(d, s, schritt):
            return int(max(1, min(int(s or 1) + schritt, seitenzahl(d)))), None

        # Jede Änderung zeichnet neu; eine Seitenänderung löscht die Auswahl.
        dok.change(_seitenwahl, dok, [verdacht, seite, auswahl]).then(
            anzeigen, eingaben, ausgaben)
        zurueck.click(lambda d, s: _blaettern(d, s, -1), [dok, seite], [seite, auswahl]).then(
            anzeigen, eingaben, ausgaben)
        vor.click(lambda d, s: _blaettern(d, s, +1), [dok, seite], [seite, auswahl]).then(
            anzeigen, eingaben, ausgaben)
        seite.submit(lambda: None, outputs=auswahl).then(anzeigen, eingaben, ausgaben)
        verdacht.input(lambda s: (int(s) + 1 if s is not None else 1, None), verdacht,
                       [seite, auswahl]).then(anzeigen, eingaben, ausgaben)
        quelle.change(lambda q: (gr.update(visible=q == QUELLE_LIVE), None), quelle,
                      [schwelle, auswahl]).then(anzeigen, eingaben, ausgaben)
        faerbung.change(lambda f: einblick.legende_html(
            "strom" if f == "Strom" else "klasse"), faerbung, legende).then(
            anzeigen, eingaben, ausgaben)
        for regler in (optionen, familien):
            regler.change(anzeigen, eingaben, ausgaben)
        schwelle.change(lambda: None, outputs=auswahl).then(anzeigen, eingaben, ausgaben)
        bild.select(block_unter, [dok, seite, quelle, schwelle], auswahl).then(
            anzeigen, eingaben, ausgaben)
        tabelle.select(zeile_gewaehlt, tabelle, auswahl).then(anzeigen, eingaben, ausgaben)

        def _export(d, nur, dpi):
            try:
                return str(einblick_html.exportieren(d, nur_auffaellige=nur, dpi=int(dpi)))
            except (FileNotFoundError, ValueError) as e:
                raise gr.Error(str(e))

        exp_knopf.click(_export, [dok, exp_auff, exp_dpi], exp_datei)

        demo.load(_seitenwahl, dok, [verdacht, seite, auswahl]).then(
            anzeigen, eingaben, ausgaben)
    return demo


def starten(**launch_kwargs):
    """Viewer starten. Im Notebook: `starten(inbrowser=True, prevent_thread_lock=True)`."""
    demo = baue_oberflaeche()
    launch_kwargs.setdefault("allowed_paths", [str(pfade.KONTROLLE)])
    launch_kwargs.setdefault("css", CSS)
    launch_kwargs.setdefault("theme", gr.themes.Soft())
    demo.queue(default_concurrency_limit=2)
    demo.launch(**launch_kwargs)
    return demo


if __name__ == "__main__":
    starten(inbrowser=True)
