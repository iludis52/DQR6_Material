"""Layout-Bericht als eigenständige HTML-Datei – zum Verschicken.

Eine Datei, kein Server, keine Python-Umgebung beim Empfänger: Seitenbilder
(JPEG) und Befunde stecken eingebettet darin, die Overlays zeichnet der
Browser als SVG. Filtern, Anklicken und Blättern funktionieren offline.

    import einblick_html
    einblick_html.exportieren("Buch")                       # alle Seiten mit Befund
    einblick_html.exportieren("Buch", nur_auffaellige=True) # nur die Prüffälle

Größe: rund 170 KB je Seite bei 100 dpi (Base64-JPEG). Für dicke Bücher
`nur_auffaellige`, `seiten` oder ein niedrigeres `dpi` wählen.

Schreibt ausschließlich die eine HTML-Datei (Vorgabe `pfade.kontrolle_html`).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

import pymupdf

import einblick
import pfade
from schema import SeitenBefund, Strom, befund_laden

GROESSE_WARNUNG_MB = 40


def _seite_daten(bf: SeitenBefund, pg: "pymupdf.Page", dpi: int, qualitaet: int) -> dict:
    jpeg = pg.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=qualitaet)
    return {
        "seite": bf.seite,
        "w": bf.bild_breite_px, "h": bf.bild_hoehe_px,
        "stufe": bf.stufe.value,
        "fehler": bf.fehler,
        "spuren": [f"{s.modell} {s.dauer_s:.2f}s" for s in bf.spuren],
        "bild": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
        "bloecke": [{
            "id": b.id, "q": b.query_id, "label": b.pp_label, "score": round(b.score, 4),
            "lese": b.lese_index, "strom": b.strom.value, "fam": einblick.familie(b.pp_label),
            "box": [round(v, 1) for v in (b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1)],
            "poly": [[round(x, 1), round(y, 1)] for x, y in b.polygon] if b.polygon else None,
            "text": b.text, "fmt": b.text_format, "zus": b.zusammengefuehrt_queries or b.zusammengefuehrt_aus,
            "zus_art": "Queries" if b.zusammengefuehrt_queries else "Stufe-1-ids",
            "fam_score": b.familien_score,
            "ausschnitt": b.ausschnitt, "docling": b.docling_label, "verlust": b.verlust,
        } for b in bf.bloecke],
        "kanten": [{"von": k.von, "nach": k.nach,
                    "marge": None if k.marge is None else round(k.marge, 1)}
                   for k in bf.kanten],
        "auff": einblick.auffaelligkeiten(bf),
        "verdacht": einblick.verdachtswert(bf),
    }


def exportieren(dok: str, ziel: Path | None = None,
                seiten: Sequence[int] | None = None,
                nur_auffaellige: bool = False,
                dpi: int = 100, qualitaet: int = 70) -> Path:
    """Befunde eines Dokuments -> eine HTML-Datei. Gibt den Pfad zurück.

    `seiten` 0-basiert; None = alle Seiten, für die ein Befund vorliegt.
    """
    ordner = pfade.befund_ordner(dok)
    dateien = sorted(ordner.glob("*.json")) if ordner.is_dir() else []
    if not dateien:
        raise FileNotFoundError(f"Keine Befunde unter {ordner} – erst Stufe 1 laufen lassen.")
    gewuenscht = None if seiten is None else {int(s) for s in seiten}

    daten, unlesbar = [], []
    with pymupdf.open(pfade.quelle(dok)) as pdf:
        for datei in dateien:
            try:
                bf = befund_laden(datei)
            except Exception as e:
                unlesbar.append(f"{datei.name}: {type(e).__name__}")
                continue
            if gewuenscht is not None and bf.seite not in gewuenscht:
                continue
            if nur_auffaellige and not einblick.auffaelligkeiten(bf):
                continue
            daten.append(_seite_daten(bf, pdf[bf.seite], dpi, qualitaet))
        seiten_gesamt = pdf.page_count

    if not daten:
        raise ValueError("Keine Seite erfüllt die Auswahl – nichts exportiert.")

    kopf = {
        "dok": dok,
        "quelle": pfade.quelle(dok).name,
        "seiten_gesamt": seiten_gesamt,
        "erzeugt": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "auswahl": ("nur auffällige Seiten" if nur_auffaellige else "alle Seiten mit Befund")
                   + ("" if gewuenscht is None else f", {len(gewuenscht)} gewählt"),
        "unlesbar": unlesbar,
        "familien": {fam: {"farbe": f, "name": n}
                     for fam, (f, n, _) in einblick.FAMILIEN.items()},
        "stroeme": {s.value: einblick.STROM_FARBE[s] for s in Strom},
        "widerspruch": einblick.WIDERSPRUCH,
        "kante": einblick.KANTE,
    }
    nutzlast = json.dumps({"kopf": kopf, "seiten": daten}, ensure_ascii=False)
    nutzlast = nutzlast.replace("</", "<\\/")          # kein vorzeitiges </script>

    ziel = Path(ziel) if ziel else pfade.kontrolle_html(dok)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    html = VORLAGE.replace("__TITEL__", f"Layout · {dok}").replace("__DATEN__", nutzlast)
    ziel.write_text(html, encoding="utf-8")

    mb = ziel.stat().st_size / 1e6
    print(f"{len(daten)} Seite(n) exportiert → {ziel}  ({mb:.1f} MB)")
    if mb > GROESSE_WARNUNG_MB:
        print(f"! Über {GROESSE_WARNUNG_MB} MB – für den Versand `nur_auffaellige=True` "
              "oder ein kleineres `dpi` erwägen.")
    return ziel


# ------------------------------------------------------------------ Vorlage

VORLAGE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITEL__</title>
<style>
:root {
  color-scheme: light;
  --bg: #f4f3ef; --panel: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #8a8983;
  --line: #e2e1dc; --accent: #2a78d6; --sel: #fff4d6;
  --fehler: #c62828; --warnung: #b26a00; --hinweis: #52514e;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #121211; --panel: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8a8983;
    --line: #2e2e2c; --accent: #3987e5; --sel: #3a3220;
    --fehler: #ff7b72; --warnung: #f0b44a; --hinweis: #c3c2b7;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #121211; --panel: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8a8983;
  --line: #2e2e2c; --accent: #3987e5; --sel: #3a3220;
  --fehler: #ff7b72; --warnung: #f0b44a; --hinweis: #c3c2b7;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
header { display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: baseline;
         padding: 12px 16px; border-bottom: 1px solid var(--line); background: var(--panel); }
header h1 { font-size: 17px; margin: 0; }
header .meta { color: var(--ink-2); font-size: 13px; }
main { display: grid; grid-template-columns: 210px minmax(0, 1fr) 380px; gap: 12px;
       padding: 12px 16px; align-items: start; }
.karte { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.karte h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
            color: var(--ink-2); margin: 0 0 8px; }
#liste { max-height: calc(100vh - 150px); overflow: auto; padding: 4px; }
#liste button { display: flex; justify-content: space-between; width: 100%; border: 0;
  background: none; color: var(--ink); padding: 6px 8px; border-radius: 6px; cursor: pointer;
  font: inherit; text-align: left; }
#liste button:hover { background: var(--bg); }
#liste button[aria-current="true"] { background: var(--accent); color: #fff; }
.badge { font-size: 11px; padding: 0 6px; border-radius: 9px; border: 1px solid currentColor; }
.b-fehler { color: var(--fehler); } .b-warnung { color: var(--warnung); } .b-hinweis { color: var(--hinweis); }
#liste button[aria-current="true"] .badge { color: #fff; }
.buehne { position: sticky; top: 12px; }
.leiste { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; margin-bottom: 8px; }
.leiste button { font: inherit; padding: 4px 10px; border: 1px solid var(--line); border-radius: 6px;
  background: var(--panel); color: var(--ink); cursor: pointer; }
.leiste label { display: inline-flex; gap: 4px; align-items: center; cursor: pointer; color: var(--ink-2); }
#seite { width: 100%; height: calc(100vh - 190px); display: block; background: #fff;
         border-radius: 4px; border: 1px solid var(--line); }
#seite .blk { cursor: pointer; }
.familien { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; }
.familien label { display: inline-flex; gap: 5px; align-items: center; cursor: pointer; }
.punkt { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
.rechts { display: flex; flex-direction: column; gap: 12px; max-height: calc(100vh - 110px); overflow: auto; }
ul.auff { margin: 0; padding-left: 18px; font-size: 13px; }
ul.auff li { margin-bottom: 3px; }
ul.auff .s { font-weight: 600; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; }
tbody tr { cursor: pointer; } tbody tr:hover { background: var(--bg); }
tbody tr.gewaehlt { background: var(--sel); }
td.num { font-variant-numeric: tabular-nums; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 3px 10px; margin: 0; font-size: 13px; }
dt { color: var(--ink-2); }
pre { white-space: pre-wrap; background: var(--bg); padding: 8px; border-radius: 6px;
      font-size: 12px; max-height: 260px; overflow: auto; margin: 8px 0 0; }
.leer { color: var(--ink-3); font-style: italic; }
@media (max-width: 1100px) {
  main { grid-template-columns: 1fr; }
  #liste { max-height: 180px; display: flex; flex-wrap: wrap; gap: 4px; }
  #liste button { width: auto; }
  .buehne { position: static; } #seite { height: auto; aspect-ratio: 3 / 4; }
  .rechts { max-height: none; }
}
</style>
</head>
<body>
<header>
  <h1 id="titel"></h1>
  <span class="meta" id="meta"></span>
</header>
<main>
  <nav class="karte" aria-label="Seiten">
    <h2>Seiten</h2>
    <label style="font-size:13px;color:var(--ink-2);display:flex;gap:5px;margin-bottom:6px">
      <input type="checkbox" id="nurAuff"> nur auffällige</label>
    <div id="liste"></div>
  </nav>
  <section class="buehne">
    <div class="karte">
      <div class="leiste">
        <button id="zurueck" title="Pfeil links">◀</button>
        <strong id="seitenname"></strong>
        <button id="vor" title="Pfeil rechts">▶</button>
        <label><input type="checkbox" id="optPoly" checked> Polygone</label>
        <label><input type="checkbox" id="optLabel" checked> Beschriftung</label>
        <label><input type="checkbox" id="optFolge" checked> Lesefolge</label>
        <label><input type="radio" name="faerb" value="klasse" checked> Klasse</label>
        <label><input type="radio" name="faerb" value="strom"> Strom</label>
      </div>
      <div class="familien" id="familien"></div>
      <div class="familien" id="stromlegende" hidden style="margin-top:4px"></div>
      <svg id="seite" role="img" aria-label="Seite mit erkannten Layout-Blöcken"></svg>
    </div>
  </section>
  <aside class="rechts">
    <div class="karte"><h2>Auffälligkeiten</h2><div id="auff"></div></div>
    <div class="karte"><h2>Gewählter Block</h2><div id="details"></div></div>
    <div class="karte"><h2>Blöcke</h2>
      <table><thead><tr><th>id</th><th>Klasse</th><th>Score</th><th>Lese</th><th>Strom</th><th>Text</th></tr></thead>
      <tbody id="tabelle"></tbody></table></div>
  </aside>
</main>
<script type="application/json" id="daten">__DATEN__</script>
<script>
(() => {
const D = JSON.parse(document.getElementById("daten").textContent);
const K = D.kopf, S = D.seiten, NS = "http://www.w3.org/2000/svg";
const zustand = { i: 0, sel: null, faerb: "klasse", poly: true, label: true, folge: true,
                  fam: new Set(Object.keys(K.familien)), nurAuff: false };
const $ = id => document.getElementById(id);
const el = (tag, attrs = {}, text) => { const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text; return e; };
const sv = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
const schwerste = s => s.auff.some(a => a[0] === "fehler") ? "fehler"
  : s.auff.some(a => a[0] === "warnung") ? "warnung" : s.auff.length ? "hinweis" : null;
const farbe = b => zustand.faerb === "strom" ? K.stroeme[b.strom] : K.familien[b.fam].farbe;
const tinte = hex => { const n = parseInt(hex.slice(1), 16);
  const l = (0.2126 * (n >> 16 & 255) + 0.7152 * (n >> 8 & 255) + 0.0722 * (n & 255)) / 255;
  return l > 0.55 ? "#0b0b0b" : "#ffffff"; };

$("titel").textContent = K.dok;
$("meta").textContent = `${K.quelle} · ${S.length} von ${K.seiten_gesamt} Seiten (${K.auswahl}) · erzeugt ${K.erzeugt}`
  + (K.unlesbar.length ? ` · ${K.unlesbar.length} Befund(e) unlesbar` : "");

// Familien-Filter
for (const [fam, f] of Object.entries(K.familien)) {
  const lab = el("label"); const cb = el("input", { type: "checkbox", checked: "" });
  cb.addEventListener("change", () => { cb.checked ? zustand.fam.add(fam) : zustand.fam.delete(fam); zeichnen(); });
  const p = el("span", { class: "punkt" }); p.style.background = f.farbe;
  lab.append(cb, p, document.createTextNode(f.name)); $("familien").append(lab);
}

for (const [name, f] of Object.entries(K.stroeme)) {
  const p = el("span", { class: "punkt" }); p.style.background = f;
  const s = el("span", { style: "display:inline-flex;gap:5px;align-items:center" });
  s.append(p, document.createTextNode("Strom " + name)); $("stromlegende").append(s);
}

function liste() {
  const box = $("liste"); box.replaceChildren();
  S.forEach((s, i) => {
    if (zustand.nurAuff && !s.auff.length) return;
    const b = el("button", { "aria-current": i === zustand.i ? "true" : "false" });
    b.append(el("span", {}, `S. ${s.seite + 1}`));
    const art = schwerste(s);
    if (art) b.append(el("span", { class: `badge b-${art}`, title: `${s.auff.length} Auffälligkeit(en)` }, String(s.auff.length)));
    b.addEventListener("click", () => gehe(i)); box.append(b);
  });
}

function gehe(i) {
  zustand.i = Math.max(0, Math.min(S.length - 1, i)); zustand.sel = null;
  liste(); zeichnen();
  const aktiv = $("liste").querySelector('[aria-current="true"]');
  if (aktiv) aktiv.scrollIntoView({ block: "nearest" });
}

function zeichnen() {
  const s = S[zustand.i], svg = $("seite");
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${s.w} ${s.h}`);
  $("stromlegende").hidden = zustand.faerb !== "strom";
  $("seitenname").textContent = `Seite ${s.seite + 1} · Stufe ${s.stufe}`;
  const defs = sv("defs");
  for (const [id, f] of [["pfeil", K.kante], ["pfeilRot", K.widerspruch]]) {
    const m = sv("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto" });
    m.append(sv("path", { d: "M0,0 L10,5 L0,10 z", fill: f })); defs.append(m);
  }
  svg.append(defs, sv("image", { href: s.bild, x: 0, y: 0, width: s.w, height: s.h }));

  const sicht = s.bloecke.filter(b => zustand.fam.has(b.fam));
  const fs = Math.max(14, s.w / 60), r = Math.max(12, s.w / 90);

  for (const b of sicht) {
    const f = farbe(b), gew = zustand.sel === b.id, dunkel = zustand.sel !== null && !gew;
    const attrs = { class: "blk", "data-id": b.id, fill: f, "fill-opacity": gew ? 0.28 : dunkel ? 0.05 : 0.14,
      stroke: f, "stroke-opacity": dunkel ? 0.4 : 1, "stroke-width": gew ? 4 : 2, "vector-effect": "non-scaling-stroke" };
    let form;
    if (zustand.poly && b.poly) form = sv("polygon", { ...attrs, points: b.poly.map(p => p.join(",")).join(" ") });
    else form = sv("rect", { ...attrs, x: b.box[0], y: b.box[1], width: b.box[2] - b.box[0], height: b.box[3] - b.box[1] });
    const t = sv("title"); t.textContent = `#${b.id} ${b.label} ${b.score.toFixed(2)}`; form.append(t);
    svg.append(form);
  }

  if (zustand.folge && sicht.length) {
    const mitte = b => [(b.box[0] + b.box[2]) / 2, (b.box[1] + b.box[3]) / 2];
    const wider = new Set(s.kanten.filter(k => k.marge !== null && k.marge < 0).map(k => `${k.von}-${k.nach}`));
    const folge = [...sicht].sort((a, b) => (a.lese ?? 1e9) - (b.lese ?? 1e9) || a.id - b.id);
    for (let j = 0; j + 1 < folge.length; j++) {
      const [x1, y1] = mitte(folge[j]), [x2, y2] = mitte(folge[j + 1]);
      const rot = wider.has(`${folge[j].id}-${folge[j + 1].id}`);
      const d = Math.hypot(x2 - x1, y2 - y1) || 1, kx = x2 - (x2 - x1) * r / d, ky = y2 - (y2 - y1) * r / d;
      svg.append(sv("line", { x1, y1, x2: kx, y2: ky, stroke: rot ? K.widerspruch : K.kante,
        "stroke-opacity": rot ? 0.95 : 0.6, "stroke-width": rot ? 3.5 : 1.5, "vector-effect": "non-scaling-stroke",
        "marker-end": `url(#${rot ? "pfeilRot" : "pfeil"})`, "pointer-events": "none" }));
    }
    for (const b of folge) {
      const [cx, cy] = mitte(b);
      svg.append(sv("circle", { cx, cy, r, fill: K.kante, stroke: "#fff", "stroke-width": 2,
        "vector-effect": "non-scaling-stroke", "pointer-events": "none" }));
      const t = sv("text", { x: cx, y: cy, "font-size": r * 1.15, fill: "#fff", "text-anchor": "middle",
        "dominant-baseline": "central", "font-family": "system-ui, sans-serif", "pointer-events": "none" });
      t.textContent = b.id; svg.append(t);
    }
  }

  if (zustand.label) {
    for (const b of sicht) {
      const f = farbe(b), text = `#${b.id} ${b.label} ${b.score.toFixed(2)}`;
      const w = text.length * fs * 0.56 + fs * 0.5, h = fs * 1.3;
      const y = b.box[1] - h >= 0 ? b.box[1] - h : b.box[1];
      svg.append(sv("rect", { x: b.box[0], y, width: w, height: h, fill: f, "fill-opacity": 0.92,
        "data-id": b.id, class: "blk" }));
      const t = sv("text", { x: b.box[0] + fs * 0.25, y: y + h * 0.72, "font-size": fs, fill: tinte(f),
        "font-family": "system-ui, sans-serif", "pointer-events": "none" });
      t.textContent = text; svg.append(t);
    }
  }
  seitentafeln();
}

function seitentafeln() {
  const s = S[zustand.i];
  // Auffälligkeiten
  const auff = $("auff"); auff.replaceChildren();
  if (s.fehler) auff.append(el("p", { class: "b-fehler" }, `Seite übersprungen: ${s.fehler}`));
  if (!s.auff.length) auff.append(el("p", { class: "leer" }, "Keine Auffälligkeiten."));
  else { const ul = el("ul", { class: "auff" });
    for (const [art, text] of s.auff) { const li = el("li");
      li.append(el("span", { class: `s b-${art}` }, art + ": "), document.createTextNode(text)); ul.append(li); }
    auff.append(ul); }
  // Tabelle
  const tb = $("tabelle"); tb.replaceChildren();
  for (const b of s.bloecke) {
    const tr = el("tr", zustand.sel === b.id ? { class: "gewaehlt" } : {});
    tr.append(el("td", { class: "num" }, b.id), el("td", {}, b.label), el("td", { class: "num" }, b.score.toFixed(3)),
      el("td", { class: "num" }, b.lese ?? "–"), el("td", {}, b.strom),
      el("td", {}, (b.text || (b.ausschnitt ? "[Bild]" : "")).slice(0, 60)));
    tr.addEventListener("click", () => waehle(b.id)); tb.append(tr);
  }
  // Details
  const det = $("details"); det.replaceChildren();
  const b = s.bloecke.find(x => x.id === zustand.sel);
  if (!b) { det.append(el("p", { class: "leer" }, "Auf eine Box oder eine Tabellenzeile klicken.")); return; }
  const dl = el("dl");
  const zeile = (k, v) => dl.append(el("dt", {}, k), el("dd", { style: "margin:0" }, v));
  zeile("Block", `#${b.id} · ${b.label}`); zeile("Score", b.score.toFixed(3));
  zeile("Query", `${b.q} von 300`); zeile("Lese-Index", b.lese ?? "–"); zeile("Strom", b.strom);
  zeile("docling", (b.docling || "–") + (b.verlust ? ` (Verlust: ${b.verlust})` : ""));
  zeile("Box (px)", b.box.map(v => Math.round(v)).join(", "));
  zeile("Polygon", b.poly ? `${b.poly.length} Ecken` : "–");
  for (const k of s.kanten.filter(k => k.nach === b.id)) zeile("kommt von", `#${k.von}` + (k.marge !== null ? ` (Marge ${Math.round(k.marge)})` : ""));
  for (const k of s.kanten.filter(k => k.von === b.id)) zeile("geht nach", `#${k.nach}` + (k.marge !== null ? ` (Marge ${Math.round(k.marge)})` : ""));
  if (b.zus) zeile("zusammengeführt", `${b.zus_art} ${b.zus.join(", ")}`);
  if (b.fam_score !== null && b.fam_score !== undefined) zeile("über Familie gerettet", `kombiniert ${b.fam_score.toFixed(2)}`);
  det.append(dl);
  if (b.text) det.append(el("pre", {}, b.text));
  else if (b.ausschnitt) det.append(el("p", { class: "leer" }, `Ausschnitt statt Text: ${b.ausschnitt}`));
}

function waehle(id) { zustand.sel = zustand.sel === id ? null : id; zeichnen(); }

$("seite").addEventListener("click", e => {
  const t = e.target.closest(".blk");
  if (t) { waehle(Number(t.dataset.id)); return; }
  zustand.sel = null; zeichnen();
});
$("zurueck").addEventListener("click", () => gehe(zustand.i - 1));
$("vor").addEventListener("click", () => gehe(zustand.i + 1));
$("optPoly").addEventListener("change", e => { zustand.poly = e.target.checked; zeichnen(); });
$("optLabel").addEventListener("change", e => { zustand.label = e.target.checked; zeichnen(); });
$("optFolge").addEventListener("change", e => { zustand.folge = e.target.checked; zeichnen(); });
document.querySelectorAll('input[name="faerb"]').forEach(r => r.addEventListener("change", e => {
  zustand.faerb = e.target.value; zeichnen(); }));
$("nurAuff").addEventListener("change", e => { zustand.nurAuff = e.target.checked; liste(); });
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "ArrowLeft") gehe(zustand.i - 1);
  else if (e.key === "ArrowRight") gehe(zustand.i + 1);
  else if (e.key === "Escape") { zustand.sel = null; zeichnen(); }
});
gehe(0);
})();
</script>
</body>
</html>
"""
