"""Stufe 3 für ein Dokument: optimieren, beschreiben, XMP einbetten, Verweise
nachziehen (Notebook 03, Abschnitte 08–10).

Gegenüber dem Notebook geändert:

* Markdown: `<BUCH>_korr.md` (Lektorat) ist führend und wird zusammen mit
  `<BUCH>.md` umgeschrieben. Bisher wurde nur `<BUCH>.md` angepasst, und die
  Bildverweise in `_korr.md` zeigten danach auf gelöschte PNGs.
* Kontext fürs Vision-Modell aus dem lektorierten Text rund um den Bildverweis.
* Jedes Bild bekommt Metadaten – auch wenn keine Ersparnis erzielt wurde oder
  kein Kandidat die Qualitätsschranke nahm (dann auf dem Original).
* Wiederaufsetzbar: Bilder mit docrag-XMP werden übernommen statt erneut
  verlustbehaftet kodiert und beschrieben.
* Ein Fehler bei einem Bild bricht den Lauf nicht ab.
* Die Beschreibung steht zusätzlich standardkonform im Docling-JSON
  (`meta.description`, `meta.keywords`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from PIL import Image

from .bild_analyse import waehle_kandidat
from .bild_kontext import (
    BILD_RE, markdown_kontext, nearby_text, nearest_section_heading, picture_caption,
)
from .bild_konfig import BildKonfig
from .bild_vision import VisionClient, fallback_metadata
from .bild_xmp import (
    build_xmp_packet, embed_xmp, format_von, lies_docrag, validate_written_image,
)

MIME = {"JPEG": "image/jpeg", "PNG": "image/png"}
ENDUNG = {"JPEG": ".jpg", "PNG": ".png"}
_STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _saeubern(semantic: dict[str, Any]) -> dict[str, Any]:
    """Steuerzeichen aus Modellantworten entfernen, Schlagworte entdoppeln."""
    out = {k: (_STEUERZEICHEN.sub("", v) if isinstance(v, str) else v) for k, v in semantic.items()}
    if isinstance(out.get("keywords"), list):
        out["keywords"] = list(dict.fromkeys(
            _STEUERZEICHEN.sub("", k).strip() for k in out["keywords"] if isinstance(k, str) and k.strip()))
    return out


@dataclass
class BildErgebnis:
    buch: str
    records: list[dict[str, Any]] = field(default_factory=list)
    markdown_dateien: list[Path] = field(default_factory=list)
    manifest_json: Path | None = None
    manifest_csv: Path | None = None
    entfernte_assets: list[str] = field(default_factory=list)
    probleme: list[str] = field(default_factory=list)

    def tabelle(self) -> pd.DataFrame:
        return pd.DataFrame(self.records)

    def zusammenfassung(self) -> str:
        from collections import Counter
        status = Counter(r.get("status") for r in self.records)
        meta = Counter(r.get("metadata_status") for r in self.records if r.get("metadata_status"))
        vorher = sum(r.get("source_bytes") or 0 for r in self.records)
        nachher = sum(r.get("output_bytes") or 0 for r in self.records)
        zeilen = [f"{self.buch}: {len(self.records)} Bilder",
                  "  Status: " + ", ".join(f"{k} {v}" for k, v in status.most_common())]
        if meta:
            zeilen.append("  Metadaten: " + ", ".join(f"{k} {v}" for k, v in meta.most_common()))
        if vorher and nachher:
            zeilen.append(f"  Größe: {vorher/1e6:.2f} MB -> {nachher/1e6:.2f} MB "
                          f"({1 - nachher/vorher:.0%} gespart)")
        zeilen.append("  Markdown: " + ", ".join(p.name for p in self.markdown_dateien))
        if self.probleme:
            zeilen.append(f"  ! {len(self.probleme)} Problem(e):")
            zeilen += [f"    {p}" for p in self.probleme[:20]]
        return "\n".join(zeilen)


# ------------------------------------------------------------ Hilfen

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def json_safe(v: Any) -> Any:
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if np.isnan(v) else float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, dict):
        return {str(k): json_safe(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(x) for x in v]
    return v


def _alt_escape(text: str) -> str:
    return (str(text).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            .replace("\n", " "))


def rewrite_markdown_images(text: str, rewrites: dict[str, tuple[str, str, str | None]],
                            beschreibung: bool) -> str:
    """Pfad und Alt-Text nachziehen; optional die Beschreibung darunter setzen."""
    def repl(m):
        old = m.group("path")
        if old not in rewrites:
            return m.group(0)
        new_path, new_alt, desc = rewrites[old]
        link = f"![{_alt_escape(new_alt)}]({new_path})"
        if beschreibung and desc:
            nachher = text[m.end():m.end() + len(desc) + 8]
            if desc not in nachher:                     # idempotent
                link += f"\n\n{desc}"
        return link
    return BILD_RE.sub(repl, text)


def _ziel_groesse(bbox_w_pt: float, bbox_h_pt: float, src_w: int, src_h: int,
                  cfg: BildKonfig) -> tuple[int, int]:
    max_w = max(1, round(bbox_w_pt / 72 * cfg.max_ppi))
    max_h = max(1, round(bbox_h_pt / 72 * cfg.max_ppi))
    scale = min(max_w / src_w, max_h / src_h) if src_w and src_h else 1.0
    if not cfg.allow_upscale:
        scale = min(1.0, scale)
    return max(1, round(src_w * scale)), max(1, round(src_h * scale))


# ------------------------------------------------------------ Lauf

def optimiere_dokument(dokument_ordner: Path, buch: str, cfg: BildKonfig | None = None,
                       fortschritt: Callable[[str], None] | None = print) -> BildErgebnis:
    cfg = cfg or BildKonfig()
    melde = fortschritt or (lambda _z: None)
    dokument_ordner = Path(dokument_ordner)
    docling_json = dokument_ordner / f"{buch}.json"
    artifact_dir = dokument_ordner / f"{buch}_artifacts"
    md_dateien = [p for p in (dokument_ordner / f"{buch}_korr.md", dokument_ordner / f"{buch}.md")
                  if p.is_file()]
    if not docling_json.is_file():
        raise FileNotFoundError(docling_json)
    if not md_dateien:
        raise FileNotFoundError(f"Kein Markdown unter {dokument_ordner}")
    if not md_dateien[0].name.endswith("_korr.md"):
        melde(f"! Kein {buch}_korr.md – Kontext und Verweise nur aus der unlektorierten Fassung.")

    ergebnis = BildErgebnis(buch=buch, markdown_dateien=md_dateien)
    doc = json.loads(docling_json.read_text(encoding="utf-8"))
    md_texte = {p: p.read_text(encoding="utf-8") for p in md_dateien}
    fuehrend = md_texte[md_dateien[0]]
    quelle_name = doc.get("origin", {}).get("filename") or doc.get("name") or buch

    vision = None
    if cfg.enable_llm:
        try:
            vision = VisionClient(cfg)
            melde(f"Vision-Modell: {vision.model_id} @ {cfg.lm_base_url}")
        except Exception as exc:
            melde(f"! Vision-Modell nicht verfügbar ({exc}) – Metadaten aus Docling-Kontext.")

    rewrites: dict[str, tuple[str, str, str | None]] = {}
    json_updates: dict[str, dict[str, Any]] = {}
    pictures = doc.get("pictures", [])

    for nr, picture in enumerate(pictures, 1):
        ref = picture.get("self_ref")
        prov = (picture.get("prov") or [{}])[0]
        bbox = prov.get("bbox") or {}
        page_no = prov.get("page_no")
        image = picture.get("image") or {}
        uri = image.get("uri")
        base = {
            "picture_ref": ref, "source_uri": uri, "page_no": page_no,
            "source_caption": picture_caption(doc, picture),
            "section_heading": nearest_section_heading(doc, page_no, bbox) if page_no else None,
        }
        if not uri:
            ergebnis.records.append({**base, "status": "NO_IMAGE"})
            continue

        try:
            record = _ein_bild(picture, uri, bbox, base, doc, fuehrend, quelle_name,
                               artifact_dir, dokument_ordner, cfg, vision,
                               rewrites, json_updates)
        except Exception as exc:
            record = {**base, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
            ergebnis.probleme.append(f"{ref}: {record['error']}")
        ergebnis.records.append(record)
        melde(f"  [{nr}/{len(pictures)}] S{page_no} {Path(uri).name}: {record['status']}"
              + (f" ({record.get('metadata_status')})" if record.get("metadata_status") else ""))

    _festschreiben(ergebnis, doc, docling_json, md_texte, rewrites, json_updates,
                   dokument_ordner, buch, cfg)
    melde(ergebnis.zusammenfassung())
    return ergebnis


def _kontext(base, uri, bbox, doc, fuehrend, cfg) -> dict[str, str]:
    """Lektoriertes Markdown zuerst, Docling-JSON als Rückfall."""
    md = markdown_kontext(fuehrend, uri, cfg.kontext_zeichen)
    kontext = {
        "section": (md or {}).get("section") or base["section_heading"] or "",
        "source_caption": base["source_caption"] or "",
    }
    if md and (md["text_before"] or md["text_after"]):
        kontext["text_before_image"] = md["text_before"]
        kontext["text_after_image"] = md["text_after"]
    elif base["page_no"]:
        kontext["nearby_document_text"] = nearby_text(doc, base["page_no"], bbox, cfg.kontext_zeichen)
    return kontext


def _nachbeschreiben(fertig: Path, fmt: str, meta: dict, kontext: dict, vision,
                     cfg: BildKonfig) -> dict[str, Any] | None:
    """Bild mit Ersatz-Metadaten nachträglich beschreiben – ohne neu zu kodieren.

    Fiel das Vision-Modell während eines Laufs aus, bekamen die übrigen
    Bilder nur Metadaten aus der Bildunterschrift; ohne diesen Schritt
    galten sie danach für immer als fertig.
    """
    daten = fertig.read_bytes()
    try:
        semantic = _saeubern(vision.beschreibe_bytes(daten, MIME[fmt], kontext))
    except Exception:
        return None
    dr = meta["docrag"]
    try:
        bbox = json.loads(dr.get("sourceBBox") or "null")
    except ValueError:
        bbox = None
    source_info = {
        "picture_ref": dr.get("assetId"), "source_document": dr.get("sourceDocument"),
        "page_no": dr.get("sourcePage"), "bbox": bbox,
        "bbox_coord_origin": dr.get("sourceCoordOrigin"), "source_uri": dr.get("sourceImageUri"),
        "source_width": dr.get("sourceWidth"), "source_height": dr.get("sourceHeight"),
        "source_dpi": dr.get("sourceDpi"), "source_caption": dr.get("sourceCaption"),
        "section_heading": dr.get("sectionHeading"),
    }
    with Image.open(fertig) as im:
        breite, hoehe = im.size
    xmp = build_xmp_packet(semantic, source_info, dr.get("technicalClass", ""), breite, hoehe,
                           "vision-llm", semantic.get("_model_id"), cfg)
    temp = fertig.with_name(f".{fertig.name}.tmp")
    try:
        temp.write_bytes(embed_xmp(daten, fmt, xmp))
        validate_written_image(temp, fmt, cfg)
        os.replace(temp, fertig)
    finally:
        temp.unlink(missing_ok=True)
    return semantic


def _ein_bild(picture, uri, bbox, base, doc, fuehrend, quelle_name, artifact_dir,
              dokument_ordner, cfg, vision, rewrites, json_updates) -> dict[str, Any]:
    stem = Path(uri).stem
    bbox_w = abs(float(bbox.get("r", 0)) - float(bbox.get("l", 0)))
    bbox_h = abs(float(bbox.get("b", 0)) - float(bbox.get("t", 0)))

    # --- schon verarbeitet? (Wiederaufsetzen nach Abbruch, zweiter Lauf)
    if not cfg.erzwingen:
        for endung in (".jpg", ".png"):
            fertig = artifact_dir / f"{stem}{endung}"
            meta = lies_docrag(fertig, cfg) if fertig.is_file() else None
            if meta:
                neu_uri = f"{artifact_dir.name}/{fertig.name}"
                rewrites[uri] = (neu_uri, meta["alt_text"] or "Bild",
                                 meta["extended_description"] or meta["description"])
                with Image.open(fertig) as im:
                    breite, hoehe, fmt = im.width, im.height, im.format
                dr = meta["docrag"]
                semantic = {**meta, "_model_id": dr.get("descriptionModel") or None}
                methode, status = dr.get("descriptionMethod", ""), "FROM_XMP"
                if methode != "vision-llm" and vision is not None:
                    nachtrag = _nachbeschreiben(fertig, fmt, meta,
                                                _kontext(base, uri, bbox, doc, fuehrend, cfg),
                                                vision, cfg)
                    if nachtrag is not None:
                        semantic, methode, status = nachtrag, "vision-llm", "LLM_GENERATED_NACHTRAG"
                        meta = {**meta, **{k: nachtrag.get(k) or "" for k in
                                           ("alt_text", "title", "description", "extended_description")}}
                        rewrites[uri] = (neu_uri, meta["alt_text"] or "Bild",
                                         meta["extended_description"] or meta["description"])
                json_updates[picture.get("self_ref")] = _json_update(
                    neu_uri, fmt, breite, hoehe, bbox_w, semantic, methode)
                alt_pfad = (dokument_ordner / uri)
                return {**base, "status": "ALREADY_PROCESSED",
                        "technical_class": dr.get("technicalClass"),
                        "output_path": str(fertig), "output_bytes": fertig.stat().st_size,
                        "old_source_path": str(alt_pfad) if alt_pfad.resolve() != fertig.resolve() else None,
                        "new_source_uri": neu_uri, "metadata_status": status,
                        "alt_text": meta["alt_text"], "title": meta["title"]}

    # --- Quelle nur innerhalb des Dokumentordners auflösen
    src = next((p.resolve() for p in (dokument_ordner / uri, artifact_dir / Path(uri).name)
                if p.is_file()), None)
    if src is None:
        return {**base, "status": "SOURCE_MISSING"}

    source_bytes = src.stat().st_size
    with Image.open(src) as im:
        src_w, src_h = im.size
    tw, th = _ziel_groesse(bbox_w, bbox_h, src_w, src_h, cfg)
    wahl = waehle_kandidat(src, tw, th, cfg)

    if wahl.candidate is not None:
        daten, fmt = wahl.candidate.data, wahl.candidate.format
        breite, hoehe = wahl.reference.size
    else:
        # Kein Umkodieren, aber trotzdem Metadaten – auf dem Original.
        daten = src.read_bytes()
        fmt = format_von(daten)
        if fmt is None:
            return {**base, "status": wahl.status, "technical_class": wahl.technical_class,
                    "metadata_status": "SKIPPED_UNSUPPORTED_FORMAT"}
        breite, hoehe = src_w, src_h

    kontext = _kontext(base, uri, bbox, doc, fuehrend, cfg)

    row = {**base}
    if vision is not None:
        try:
            semantic = _saeubern(vision.beschreibe_bytes(daten, MIME[fmt], kontext))
            metadata_status, method, model = "LLM_GENERATED", "vision-llm", semantic.get("_model_id")
        except Exception as exc:
            semantic = fallback_metadata(row, cfg)
            metadata_status = f"SEMANTIC_METADATA_PENDING:{type(exc).__name__}"
            method, model = "docling-context-fallback", None
    else:
        semantic = fallback_metadata(row, cfg)
        metadata_status, method, model = "SEMANTIC_METADATA_PENDING", "docling-context-fallback", None

    source_info = {
        "picture_ref": base["picture_ref"], "source_document": quelle_name,
        "page_no": base["page_no"],
        "bbox": {k: bbox.get(k) for k in ("l", "t", "r", "b")},
        "bbox_coord_origin": bbox.get("coord_origin"), "source_uri": uri,
        "source_width": src_w, "source_height": src_h,
        "source_dpi": (picture.get("image") or {}).get("dpi"),
        "source_caption": base["source_caption"], "section_heading": kontext["section"],
    }
    xmp = build_xmp_packet(semantic, source_info, wahl.technical_class, breite, hoehe,
                           method, model, cfg)
    final = embed_xmp(daten, fmt, xmp)

    output_path = artifact_dir / f"{Path(uri).stem}{ENDUNG[fmt]}"
    temp = artifact_dir / f".{output_path.name}.tmp"
    try:
        temp.write_bytes(final)
        validate_written_image(temp, fmt, cfg)
        os.replace(temp, output_path)
    finally:
        temp.unlink(missing_ok=True)

    neu_uri = f"{artifact_dir.name}/{output_path.name}"
    rewrites[uri] = (neu_uri, semantic.get("alt_text") or "Bild",
                     semantic.get("extended_description") or semantic.get("description"))
    json_updates[base["picture_ref"]] = _json_update(neu_uri, fmt, breite, hoehe, bbox_w,
                                                     semantic, method)
    m = wahl.metrics or {}
    return {
        **base,
        "status": wahl.status,
        "source_sha256": sha256_file(src) if src != output_path.resolve() else None,
        "source_bytes": source_bytes, "source_width": src_w, "source_height": src_h,
        "target_width": breite, "target_height": hoehe,
        "technical_class": wahl.technical_class, "class_reasons": wahl.class_reasons,
        "selected_candidate": wahl.candidate.candidate_id if wahl.candidate else "original",
        "selected_format": fmt,
        "selected_params": wahl.candidate.params if wahl.candidate else {},
        "selection_zone": wahl.selection_zone,
        "ssim": m.get("ssim"), "edge_f1": m.get("edge_f1"),
        "component_retention": m.get("component_retention"),
        "deltae_mean": m.get("deltae_mean"), "deltae_p95": m.get("deltae_p95"),
        "output_path": str(output_path), "output_bytes": output_path.stat().st_size,
        "saving_ratio": 1 - output_path.stat().st_size / source_bytes,
        "metadata_status": metadata_status, "description_method": method,
        "description_model": model,
        "title": semantic.get("title"), "alt_text": semantic.get("alt_text"),
        "description": semantic.get("description"),
        "extended_description": semantic.get("extended_description"),
        "keywords": semantic.get("keywords"),
        "xmp_readback_valid": True,
        "old_source_path": str(src) if src != output_path.resolve() else None,
        "new_source_uri": neu_uri,
    }


def _json_update(uri: str, fmt: str, breite: int, hoehe: int, bbox_w_pt: float,
                 semantic: dict[str, Any], method: str) -> dict[str, Any]:
    upd: dict[str, Any] = {
        "uri": uri, "mimetype": MIME.get(fmt, "image/png"),
        "size": {"width": int(breite), "height": int(hoehe)},
    }
    if bbox_w_pt > 0:
        # Tatsächliche Auflösung statt pauschal MAX_PPI: ein Bild, das schon
        # unter der Grenze lag, wurde nicht auf 144 ppi gebracht.
        upd["dpi"] = max(1, round(breite / (bbox_w_pt / 72)))
    if method == "vision-llm":
        text = semantic.get("extended_description") or semantic.get("description")
        if text:
            upd["description"] = {"text": text, "created_by": semantic.get("_model_id")}
        if semantic.get("keywords"):
            upd["keywords"] = {"values": list(semantic["keywords"])}
    return upd


def _festschreiben(ergebnis: BildErgebnis, doc, docling_json: Path, md_texte: dict[Path, str],
                   rewrites, json_updates, dokument_ordner: Path, buch: str,
                   cfg: BildKonfig) -> None:
    # 1) Markdown (alle Fassungen) in memory nachziehen
    neue_md = {p: rewrite_markdown_images(t, rewrites, cfg.beschreibung_ins_markdown)
               for p, t in md_texte.items()}

    # 2) Docling-JSON nachziehen
    for picture in doc.get("pictures", []):
        upd = json_updates.get(picture.get("self_ref"))
        if not upd:
            continue
        image = picture.setdefault("image", {})
        image["uri"] = upd["uri"]
        image["mimetype"] = upd["mimetype"]
        image.setdefault("size", {}).update(upd["size"])
        if "dpi" in upd:
            image["dpi"] = upd["dpi"]
        if "description" in upd or "keywords" in upd:
            meta = picture.get("meta") or {}
            for key in ("description", "keywords"):
                if key in upd:
                    meta[key] = upd[key]
            picture["meta"] = meta

    # Standardkonformität prüfen, bevor irgendetwas überschrieben wird.
    try:
        from docling_core.types.doc import DoclingDocument
        DoclingDocument.model_validate(doc)
    except ImportError:
        pass
    except Exception as exc:
        raise RuntimeError(f"Aktualisiertes Docling-JSON ist ungültig, nichts geschrieben: {exc}")

    # 3) Festschreiben – je Datei atomar
    for p, t in neue_md.items():
        _atomic_write_text(p, t)
    _atomic_write_text(docling_json, json.dumps(doc, ensure_ascii=False, indent=2))

    # 4) Alte Rasterdatei nur löschen, wenn das neue Ziel existiert und kein
    #    Markdown mehr darauf verweist.
    verweise = {m.group("path") for t in neue_md.values() for m in BILD_RE.finditer(t)}
    for r in ergebnis.records:
        alt, neu = r.get("old_source_path"), r.get("output_path")
        if not alt or not neu or not Path(neu).exists():
            continue
        alt_p = Path(alt)
        if alt_p.resolve() == Path(neu).resolve() or not alt_p.exists():
            continue
        if r.get("source_uri") in verweise:
            ergebnis.probleme.append(f"{alt_p.name} wird noch referenziert – nicht gelöscht.")
            continue
        alt_p.unlink()
        ergebnis.entfernte_assets.append(str(alt_p))

    # 5) Audit-Manifeste
    ergebnis.manifest_json = dokument_ordner / f"{buch}.image-optimization.json"
    ergebnis.manifest_csv = dokument_ordner / f"{buch}.image-optimization.csv"
    manifest = {
        "schema_version": "production-0.7-inplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_document": doc.get("origin", {}).get("filename") or buch,
        "document_dir": str(dokument_ordner),
        "markdown_files": [str(p) for p in md_texte],
        "max_ppi": cfg.max_ppi,
        "canonical_formats": ["JPEG", "PNG"],
        "llm": {"enabled": cfg.enable_llm, "base_url": cfg.lm_base_url,
                "configured_model": cfg.lm_model},
        "removed_old_assets": ergebnis.entfernte_assets,
        "assets": [json_safe(x) for x in ergebnis.records],
    }
    _atomic_write_text(ergebnis.manifest_json, json.dumps(manifest, ensure_ascii=False, indent=2))
    df = ergebnis.tabelle()
    for col in df.columns:
        df[col] = df[col].map(lambda x: json.dumps(json_safe(x), ensure_ascii=False, sort_keys=True)
                              if isinstance(x, (list, dict)) else x)
    tmp = ergebnis.manifest_csv.with_name(f".{ergebnis.manifest_csv.name}.tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, ergebnis.manifest_csv)

    # 6) Abschlussprüfung: jeder Verweis in JSON und Markdown muss auflösen.
    for picture in doc.get("pictures", []):
        uri = (picture.get("image") or {}).get("uri")
        if uri and not (dokument_ordner / uri).is_file():
            ergebnis.probleme.append(f"JSON verweist auf fehlende Datei: {uri}")
    for p, t in neue_md.items():
        for m in BILD_RE.finditer(t):
            if not (dokument_ordner / m.group("path")).is_file():
                ergebnis.probleme.append(f"{p.name} verweist auf fehlende Datei: {m.group('path')}")
