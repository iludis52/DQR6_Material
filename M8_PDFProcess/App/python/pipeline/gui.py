"""Gradio-Oberfläche für die ganze Pipeline.

Start aus dem Notebook `04_pipeline_gui.ipynb` oder direkt:

    python python/pipeline/gui.py

Reiter: Auftrag (PDFs, Arbeitsbereich) · Lauf (Stufen starten, Protokoll) ·
Ergebnis (Vorschau, Ernte) · Einstellungen (LM Studio / DeepInfra, Modelle).

Läufe arbeiten in einem eigenen Thread; ihre `print`-Ausgabe wird je Thread
abgefangen und ins Protokoll gestreamt. Es läuft immer nur ein Auftrag. Das
Schließen des Browsers bricht einen Lauf nicht ab; ein abgebrochener Lauf
(Kernel-Neustart) setzt beim nächsten Start dort wieder auf.
"""

from __future__ import annotations

import io
import sys
import threading
import time
import traceback
from pathlib import Path

if __package__ in (None, ""):                         # direkter Skriptstart
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "pipeline"

import gradio as gr

import pipeline  # noqa: F401  (Suchpfad für pdf_extraction)
import pfade
from bild_optimierung.bild_kontext import BILD_RE as _BILD   # versteht \] im Alt-Text
from pipeline import arbeitsbereich, deepinfra, steuerung
from pipeline.konfig import PipelineKonfig

STUFEN = {"1 · Layout + OCR + Docling": 1, "2 · Lektorat": 2, "3 · Bilder + Metadaten": 3}
LOG_MAX = 60_000


# ------------------------------------------------------------ Protokoll je Thread

class _ThreadStdout(io.TextIOBase):
    """Leitet `print` aus registrierten Threads in deren Puffer um."""

    def __init__(self, original):
        self.original = original
        self.ziele: dict[int, list[str]] = {}

    def write(self, s: str) -> int:
        ziel = self.ziele.get(threading.get_ident())
        if ziel is not None:
            ziel.append(s)
        else:
            self.original.write(s)
        return len(s)

    def flush(self) -> None:
        self.original.flush()

    def __getattr__(self, name):                     # isatty, encoding, …
        return getattr(self.original, name)


def _proxy() -> _ThreadStdout:
    if not isinstance(sys.stdout, _ThreadStdout):
        sys.stdout = _ThreadStdout(sys.stdout)
    return sys.stdout


_LAUF = threading.Lock()


def _im_hintergrund(aufgabe, *args, **kwargs):
    """Generator: startet `aufgabe` im Thread und liefert laufend das Protokoll."""
    if not _LAUF.acquire(blocking=False):
        yield "Es läuft bereits ein Auftrag – bitte warten, bis er fertig ist."
        return
    proxy = _proxy()
    puffer: list[str] = []
    fertig = threading.Event()

    def ziel():
        proxy.ziele[threading.get_ident()] = puffer
        try:
            aufgabe(*args, **kwargs)
        except Exception:
            puffer.append("\n! Abbruch:\n" + traceback.format_exc())
        finally:
            proxy.ziele.pop(threading.get_ident(), None)
            puffer.append(f"\n[{time.strftime('%H:%M:%S')}] fertig.\n")
            fertig.set()
            _LAUF.release()

    threading.Thread(target=ziel, daemon=True, name="pipeline-lauf").start()
    while not fertig.wait(0.7):
        yield "".join(puffer)[-LOG_MAX:]
    yield "".join(puffer)[-LOG_MAX:]


# ------------------------------------------------------------ Auftrag

def _status_tabelle():
    zeilen = [s.zeile() for s in arbeitsbereich.status()]
    return zeilen or [["(keine Dokumente in data/raw)", None, "", "", "", ""]]


def _buecher_auswahl():
    b = arbeitsbereich.buecher()
    return gr.update(choices=b, value=b), gr.update(choices=b, value=b[0] if b else None)


def _hat_arbeit() -> bool:
    return any(arbeitsbereich.buecher()) or any(pfade.PROCESSED.glob("*"))


def neuer_auftrag(dateien, verwerfen: bool):
    if not dateien:
        return "Bitte zuerst PDF-Dateien auswählen."
    if _hat_arbeit() and not verwerfen:
        return ("Im Arbeitsbereich liegt noch Arbeit. Erst ernten – oder "
                "„Unfertige Arbeit verwerfen“ ankreuzen.")
    if _LAUF.locked():
        return "Es läuft gerade ein Auftrag."
    return "\n".join(arbeitsbereich.neuer_auftrag([Path(f) for f in dateien]))


def pdfs_hinzufuegen(dateien):
    if not dateien:
        return "Bitte zuerst PDF-Dateien auswählen."
    return "\n".join(arbeitsbereich.pdfs_uebernehmen([Path(f) for f in dateien]))


def zuruecksetzen(bestaetigt: bool):
    if not bestaetigt:
        return "Zum Zurücksetzen bitte bestätigen."
    if _LAUF.locked():
        return "Es läuft gerade ein Auftrag."
    arbeitsbereich.zuruecksetzen()
    return "Arbeitsbereich geleert und neu angelegt."


# ------------------------------------------------------------ Lauf

def lauf_starten(buecher, stufen, stufe1_neu, lektorat_neu, bilder_neu, ernten):
    if not buecher:
        yield "Kein Dokument gewählt."
        return
    if not stufen:
        yield "Keine Stufe gewählt."
        return
    konfig = PipelineKonfig.laden()
    yield from _im_hintergrund(
        steuerung.gesamtlauf, konfig, list(buecher),
        stufen=tuple(sorted(STUFEN[s] for s in stufen)), ernten=ernten,
        stufe1_neu=stufe1_neu, lektorat_neu=lektorat_neu, bilder_erzwingen=bilder_neu)


# ------------------------------------------------------------ Ergebnis

def _datei_url(pfad: Path) -> str:
    return f"/gradio_api/file={pfad.resolve()}"


def vorschau(buch: str | None, fassung: str):
    if not buch:
        return "", "", [], ""
    ordner = pfade.dokument_ordner(buch)
    md = pfade.dokument_korr_md(buch) if fassung == "lektoriert" else pfade.dokument_md(buch)
    if not md.is_file():
        return f"*{md.name} gibt es (noch) nicht.*", "", [], ""
    text = md.read_text(encoding="utf-8")
    gerendert = _BILD.sub(
        lambda m: f"![{m.group('alt')}]({_datei_url(ordner / m.group('path'))})", text)
    bilder = [(str(ordner / m.group("path")), m.group("alt").replace("\\", ""))
              for m in _BILD.finditer(text) if (ordner / m.group("path")).is_file()]
    review = pfade.dokument_review_md(buch)
    return (gerendert, text, bilder,
            review.read_text(encoding="utf-8") if review.is_file() else "*Kein Reviewbericht.*")


def ernten_klick(trotzdem: bool):
    if _LAUF.locked():
        return "Es läuft gerade ein Auftrag."
    konfig = PipelineKonfig.laden()
    liste, zurueck = arbeitsbereich.ernten_und_zuruecksetzen(konfig.ergebnis_pfad, trotzdem=trotzdem)
    if not liste:
        return "Nichts zu ernten."
    zeilen = []
    for e in liste:
        zeilen.append(f"{e.buch}: {e.ziel or 'NICHT geerntet'}")
        zeilen += [f"   ! {p}" for p in e.probleme]
    zeilen.append("Arbeitsbereich zurückgesetzt." if zurueck
                  else "Arbeitsbereich NICHT zurückgesetzt – nicht alles ließ sich ernten.")
    return "\n".join(zeilen)


def ernten_liste():
    konfig = PipelineKonfig.laden()
    return "\n".join(str(p) for p in arbeitsbereich.fruehere_ernten(konfig.ergebnis_pfad)) \
        or "(noch keine)"


# ------------------------------------------------------------ Einstellungen

ANBIETER = {"LM Studio": "lmstudio", "DeepInfra": "deepinfra"}
ANBIETER_NAME = {v: k for k, v in ANBIETER.items()}

FELDER = ["ocr_url", "ocr_modell",
          "lektorat_anbieter", "lektorat_url", "lektorat_modell", "lektorat_deepinfra_modell",
          "vision_anbieter", "vision_url", "vision_modell", "vision_deepinfra_modell",
          "vision_aktiv", "beschreibung_ins_markdown", "bild_max_ppi",
          "lektorat_max_context_tokens", "lektorat_max_output_tokens", "ergebnis_ordner"]
_GANZZAHL = {"bild_max_ppi", "lektorat_max_context_tokens", "lektorat_max_output_tokens"}


def einstellungen_speichern(*werte):
    konfig = PipelineKonfig.laden()
    for name, wert in zip(FELDER, werte):
        if name in _GANZZAHL:
            wert = int(wert)
        elif name.endswith("_anbieter"):
            wert = ANBIETER[wert]
        setattr(konfig, name, wert if wert is not None else "")
    pfad = konfig.speichern()
    return f"Gespeichert: {pfad} (ohne API-Key)"


def modelle_abfragen(url: str, aktuell: str):
    try:
        ids = steuerung.modelle(url)
    except Exception as exc:
        return gr.update(), f"{url}: nicht erreichbar ({type(exc).__name__})"
    # Nur die Auswahl auffüllen, den Wert nie still auf das erste Modell setzen –
    # beim OCR-Modell hieße leer "automatisch", und [0] wäre oft ein Chatmodell.
    hinweis = "" if not aktuell or aktuell in ids else f" – ! {aktuell!r} nicht darunter"
    return gr.update(choices=ids, value=aktuell), f"{url}: {len(ids)} Modell(e){hinweis}"


def deepinfra_modelle(lek_aktuell: str, vis_aktuell: str):
    try:
        text, vision = deepinfra.modell_ids("text"), deepinfra.modell_ids("vision")
    except Exception as exc:
        return gr.update(), gr.update(), f"DeepInfra-Katalog nicht erreichbar ({type(exc).__name__})"
    return (gr.update(choices=text, value=lek_aktuell), gr.update(choices=vision, value=vis_aktuell),
            f"DeepInfra: {len(text)} Chat-, davon {len(vision)} Vision-Modelle "
            "(Modelle ohne Reasoning stehen oben)")


def schluessel_uebernehmen(wert: str):
    deepinfra.schluessel_setzen(wert)
    # Feld leeren, damit der Schlüssel nicht im Browser stehen bleibt.
    return "", f"API-Key: {deepinfra.schluessel_status()}"


def schluessel_testen():
    try:
        return f"API-Key: {deepinfra.schluessel_status()} – {deepinfra.schluessel_pruefen()}"
    except Exception as exc:
        return f"DeepInfra nicht erreichbar ({type(exc).__name__}: {exc})"


def _sichtbar(anbieter: str):
    di = ANBIETER[anbieter] == "deepinfra"
    return gr.update(visible=not di), gr.update(visible=di)


# ------------------------------------------------------------ Aufbau

CSS = """
#protokoll textarea { font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
.klein { font-size: 0.9em; opacity: 0.85; }
"""


def baue_oberflaeche() -> gr.Blocks:
    arbeitsbereich.anlegen()
    k = PipelineKonfig.laden()
    b = arbeitsbereich.buecher()

    with gr.Blocks(title="PDF-Pipeline") as demo:
        gr.Markdown("## PDF-Pipeline &nbsp;·&nbsp; Layout → OCR → Lektorat → Bilder")

        # ---------------------------------------------------- Auftrag
        with gr.Tab("Auftrag"):
            status = gr.Dataframe(headers=arbeitsbereich.STATUS_SPALTEN, value=_status_tabelle(),
                                  interactive=False, label="Arbeitsbereich (data/)")
            aktualisieren = gr.Button("Status aktualisieren", size="sm")
            with gr.Row():
                with gr.Column(scale=3):
                    upload = gr.File(label="PDF-Dateien", file_count="multiple",
                                     file_types=[".pdf"], type="filepath")
                with gr.Column(scale=2):
                    verwerfen = gr.Checkbox(label="Unfertige Arbeit verwerfen", value=False)
                    btn_neu = gr.Button("Neuer Auftrag (leeren + übernehmen)", variant="primary")
                    btn_dazu = gr.Button("Zum laufenden Auftrag hinzufügen")
            auftrag_info = gr.Textbox(label="Meldungen", lines=4, interactive=False)
            with gr.Accordion("Arbeitsbereich zurücksetzen", open=False):
                gr.Markdown("Löscht **alles** unter `data/` (Rohdateien, Befunde, "
                            "Checkpoints, Ergebnisse) und legt die leere Struktur neu an. "
                            "Geerntete Ergebnisse bleiben unberührt.", elem_classes="klein")
                reset_ok = gr.Checkbox(label="Ja, alles unter data/ löschen", value=False)
                btn_reset = gr.Button("Zurücksetzen", variant="stop")

        # ---------------------------------------------------- Lauf
        with gr.Tab("Lauf"):
            with gr.Row():
                lauf_buecher = gr.CheckboxGroup(b, value=b, label="Dokumente")
                lauf_stufen = gr.CheckboxGroup(list(STUFEN), value=list(STUFEN), label="Stufen")
            with gr.Row():
                opt_neu1 = gr.Checkbox(label="Stufe 1 komplett neu (sonst Wiederaufnahme)")
                opt_neu2 = gr.Checkbox(label="Lektorat neu beginnen")
                opt_neu3 = gr.Checkbox(label="Bilder neu kodieren/beschreiben")
                opt_ernte = gr.Checkbox(label="Danach ernten + zurücksetzen", value=False)
            btn_start = gr.Button("Lauf starten", variant="primary")
            protokoll = gr.Textbox(label="Protokoll", lines=24, max_lines=24, autoscroll=True,
                                   interactive=False, elem_id="protokoll")
            gr.Markdown("Die Einstellungen (Anbieter, Adressen, Modelle) kommen aus dem "
                        "Reiter **Einstellungen** – dort vorher speichern.", elem_classes="klein")

        # ---------------------------------------------------- Ergebnis
        with gr.Tab("Ergebnis"):
            with gr.Row():
                erg_buch = gr.Dropdown(b, value=b[0] if b else None, label="Dokument")
                erg_fassung = gr.Radio(["lektoriert", "OCR-Rohfassung"], value="lektoriert",
                                       label="Fassung")
                btn_zeigen = gr.Button("Anzeigen")
            with gr.Tab("Gerendert"):
                erg_md = gr.Markdown(height=600)
            with gr.Tab("Markdown-Quelle"):
                erg_quelle = gr.Code(language="markdown", lines=30)
            with gr.Tab("Bilder"):
                erg_bilder = gr.Gallery(columns=4, height=560, label="Bilder mit Alt-Text")
            with gr.Tab("Lektorat-Review"):
                erg_review = gr.Markdown(height=600)
            gr.Markdown("---")
            with gr.Row():
                with gr.Column():
                    ernte_trotzdem = gr.Checkbox(
                        label="Auch nicht erntereife Dokumente ernten (sonst nur vollständige)")
                    btn_ernte = gr.Button("Ernten + zurücksetzen", variant="primary")
                ernte_info = gr.Textbox(label="Ernte", lines=5, interactive=False)
            fruehere = gr.Textbox(label="Frühere Ernten", value=ernten_liste(), lines=4,
                                  interactive=False)

        # ---------------------------------------------------- Einstellungen
        with gr.Tab("Einstellungen"):
            gr.Markdown("**Stufe 1 – OCR (PaddleOCR-VL)**")
            with gr.Row():
                e_ocr_url = gr.Textbox(k.ocr_url, label="LM-Studio-URL")
                e_ocr_mod = gr.Dropdown([k.ocr_modell] if k.ocr_modell else [], value=k.ocr_modell,
                                        allow_custom_value=True,
                                        label="Modell (leer = automatisch 'paddleocr')")
                b_ocr = gr.Button("Modelle abfragen", size="sm")
            gr.Markdown("**DeepInfra** – Alternative zu LM Studio für Lektorat und Bilder")
            with gr.Row():
                e_key = gr.Textbox(label="API-Key", type="password", placeholder="nur für diese Sitzung",
                                   scale=3)
                b_key = gr.Button("Übernehmen", size="sm")
                b_key_test = gr.Button("Prüfen", size="sm")
                b_di = gr.Button("DeepInfra-Modelle laden", size="sm")
            key_info = gr.Markdown(f"API-Key: {deepinfra.schluessel_status()} · Reasoning wird "
                                   "für DeepInfra-Modelle automatisch abgeschaltet.",
                                   elem_classes="klein")

            gr.Markdown("**Stufe 2 – Lektorat**")
            e_lek_anb = gr.Radio(list(ANBIETER), value=ANBIETER_NAME[k.lektorat_anbieter],
                                 label="Anbieter")
            with gr.Row(visible=k.lektorat_anbieter == "lmstudio") as lek_lms:
                e_lek_url = gr.Textbox(k.lektorat_url, label="LM-Studio-URL")
                e_lek_mod = gr.Dropdown([k.lektorat_modell], value=k.lektorat_modell,
                                        allow_custom_value=True, label="Modell")
                b_lek = gr.Button("Modelle abfragen", size="sm")
            with gr.Row(visible=k.lektorat_anbieter == "deepinfra") as lek_di:
                e_lek_di = gr.Dropdown([k.lektorat_deepinfra_modell], value=k.lektorat_deepinfra_modell,
                                       allow_custom_value=True, label="DeepInfra-Modell")
            with gr.Row():
                e_ctx = gr.Number(k.lektorat_max_context_tokens, label="Kontextfenster (Tokens)",
                                  precision=0)
                e_out = gr.Number(k.lektorat_max_output_tokens, label="Max. Ausgabe (Tokens)",
                                  precision=0)

            gr.Markdown("**Stufe 3 – Bilder**")
            e_vis_anb = gr.Radio(list(ANBIETER), value=ANBIETER_NAME[k.vision_anbieter],
                                 label="Anbieter")
            with gr.Row(visible=k.vision_anbieter == "lmstudio") as vis_lms:
                e_vis_url = gr.Textbox(k.vision_url, label="LM-Studio-URL")
                e_vis_mod = gr.Dropdown([k.vision_modell], value=k.vision_modell,
                                        allow_custom_value=True, label="Vision-Modell")
                b_vis = gr.Button("Modelle abfragen", size="sm")
            with gr.Row(visible=k.vision_anbieter == "deepinfra") as vis_di:
                e_vis_di = gr.Dropdown([k.vision_deepinfra_modell], value=k.vision_deepinfra_modell,
                                       allow_custom_value=True, label="DeepInfra-Vision-Modell")
            with gr.Row():
                e_vis_on = gr.Checkbox(k.vision_aktiv, label="Bildbeschreibung per Vision-Modell")
                e_desc_md = gr.Checkbox(k.beschreibung_ins_markdown,
                                        label="Beschreibung auch als Absatz ins Markdown")
                e_ppi = gr.Number(k.bild_max_ppi, label="Max. ppi", precision=0)
            gr.Markdown("**Ernte**")
            e_ernte = gr.Textbox(k.ergebnis_ordner, label="Ergebnisordner",
                                 placeholder=str(pfade.ERGEBNISSE))
            with gr.Row():
                btn_save = gr.Button("Speichern", variant="primary")
                einst_info = gr.Textbox(label="", lines=1, interactive=False, container=False)

        # ---------------------------------------------------- Verdrahtung
        def nach_aenderung():
            lb, eb = _buecher_auswahl()
            return _status_tabelle(), lb, eb

        refresh = [status, lauf_buecher, erg_buch]
        aktualisieren.click(nach_aenderung, outputs=refresh)
        btn_neu.click(neuer_auftrag, [upload, verwerfen], auftrag_info).then(nach_aenderung, outputs=refresh)
        btn_dazu.click(pdfs_hinzufuegen, upload, auftrag_info).then(nach_aenderung, outputs=refresh)
        btn_reset.click(zuruecksetzen, reset_ok, auftrag_info).then(nach_aenderung, outputs=refresh)

        btn_start.click(lauf_starten,
                        [lauf_buecher, lauf_stufen, opt_neu1, opt_neu2, opt_neu3, opt_ernte],
                        protokoll).then(nach_aenderung, outputs=refresh) \
            .then(ernten_liste, outputs=fruehere)

        btn_zeigen.click(vorschau, [erg_buch, erg_fassung], [erg_md, erg_quelle, erg_bilder, erg_review])
        erg_buch.change(vorschau, [erg_buch, erg_fassung], [erg_md, erg_quelle, erg_bilder, erg_review])
        erg_fassung.change(vorschau, [erg_buch, erg_fassung], [erg_md, erg_quelle, erg_bilder, erg_review])
        btn_ernte.click(ernten_klick, ernte_trotzdem, ernte_info) \
            .then(nach_aenderung, outputs=refresh).then(ernten_liste, outputs=fruehere)

        felder = [e_ocr_url, e_ocr_mod,
                  e_lek_anb, e_lek_url, e_lek_mod, e_lek_di,
                  e_vis_anb, e_vis_url, e_vis_mod, e_vis_di,
                  e_vis_on, e_desc_md, e_ppi, e_ctx, e_out, e_ernte]
        e_lek_anb.change(_sichtbar, e_lek_anb, [lek_lms, lek_di])
        e_vis_anb.change(_sichtbar, e_vis_anb, [vis_lms, vis_di])
        b_key.click(schluessel_uebernehmen, e_key, [e_key, key_info])
        e_key.submit(schluessel_uebernehmen, e_key, [e_key, key_info])
        b_key_test.click(schluessel_testen, outputs=key_info)
        b_di.click(deepinfra_modelle, [e_lek_di, e_vis_di], [e_lek_di, e_vis_di, einst_info])
        btn_save.click(einstellungen_speichern, felder, einst_info)
        b_ocr.click(modelle_abfragen, [e_ocr_url, e_ocr_mod], [e_ocr_mod, einst_info])
        b_lek.click(modelle_abfragen, [e_lek_url, e_lek_mod], [e_lek_mod, einst_info])
        b_vis.click(modelle_abfragen, [e_vis_url, e_vis_mod], [e_vis_mod, einst_info])

        demo.load(nach_aenderung, outputs=refresh).then(
            vorschau, [erg_buch, erg_fassung], [erg_md, erg_quelle, erg_bilder, erg_review])
    return demo


def starten(**launch_kwargs):
    """Oberfläche starten. Im Notebook: `starten(inbrowser=True)`."""
    demo = baue_oberflaeche()
    konfig = PipelineKonfig.laden()
    erlaubt = [str(pfade.PROJEKT), str(konfig.ergebnis_pfad)]
    launch_kwargs.setdefault("allowed_paths", erlaubt)
    launch_kwargs.setdefault("css", CSS)
    launch_kwargs.setdefault("theme", gr.themes.Soft())
    demo.queue(default_concurrency_limit=4)
    return demo.launch(**launch_kwargs)


if __name__ == "__main__":
    starten(inbrowser=True)
