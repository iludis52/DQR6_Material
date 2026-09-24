"""XMP-Paket bauen, nativ in JPEG/PNG einbetten und zurücklesen (Notebook 03,
Abschnitte 06/07). Dublin Core + IPTC Core + ein kleiner `docrag`-Namensraum."""

from __future__ import annotations

import binascii
import json
import re
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image

from .bild_konfig import BildKonfig

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
DC_NS = "http://purl.org/dc/elements/1.1/"
IPTC_CORE_NS = "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_XMP_KEYWORD = b"XML:com.adobe.xmp"
JPEG_XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"

# XML 1.0 erlaubt keine Steuerzeichen außer \t \n \r. Ein einziges davon in
# einer Modellantwort macht das Paket unlesbar – dann scheitert die
# Rück-Validierung erst nach dem teuren Vision-Aufruf.
_XML_UNGUELTIG = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _x(value: Any) -> str:
    return escape(_XML_UNGUELTIG.sub("", str(value or "")))


def lang_alt(value: str, lang: str) -> str:
    v = _x(value)
    return (f'<rdf:Alt><rdf:li xml:lang="x-default">{v}</rdf:li>'
            f'<rdf:li xml:lang="{_x(lang)}">{v}</rdf:li></rdf:Alt>')


def bag(values: list[str]) -> str:
    return "<rdf:Bag>" + "".join(f"<rdf:li>{_x(v)}</rdf:li>" for v in values if v) + "</rdf:Bag>"


def build_xmp_packet(semantic: dict[str, Any], source_info: dict[str, Any],
                     technical_class: str, output_width: int, output_height: int,
                     method: str, model: str | None, cfg: BildKonfig) -> bytes:
    caption = source_info.get("source_caption") or ""
    title = semantic.get("title") or caption
    alt = semantic.get("alt_text") or caption
    desc = semantic.get("description") or caption
    ext = semantic.get("extended_description") or ""
    kws = semantic.get("keywords") or []
    generated = semantic.get("_generated_at") or datetime.now(timezone.utc).isoformat()

    custom = {
        "schemaVersion": cfg.docrag_schema_version,
        "assetId": source_info.get("picture_ref") or "",
        "sourceDocument": source_info.get("source_document") or "",
        "sourcePage": str(source_info.get("page_no") or ""),
        "sourcePictureRef": source_info.get("picture_ref") or "",
        "sourceBBox": json.dumps(source_info.get("bbox"), separators=(",", ":")),
        "sourceCoordOrigin": source_info.get("bbox_coord_origin") or "",
        "sourceImageUri": source_info.get("source_uri") or "",
        "sourceWidth": str(source_info.get("source_width") or ""),
        "sourceHeight": str(source_info.get("source_height") or ""),
        "sourceDpi": str(source_info.get("source_dpi") or ""),
        "sourceCaption": caption,
        "sectionHeading": source_info.get("section_heading") or "",
        "optimizedWidth": str(output_width),
        "optimizedHeight": str(output_height),
        "maxPpi": str(cfg.max_ppi),
        "technicalClass": technical_class,
        "descriptionMethod": method,
        "descriptionModel": model or "",
        "metadataGeneratedAt": generated,
    }
    custom_xml = "\n".join(f"<docrag:{k}>{_x(v)}</docrag:{k}>" for k, v in custom.items())
    lang = cfg.metadata_language

    packet = f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
<rdf:RDF xmlns:rdf="{RDF_NS}">
<rdf:Description rdf:about="" xmlns:dc="{DC_NS}" xmlns:Iptc4xmpCore="{IPTC_CORE_NS}" xmlns:docrag="{cfg.docrag_namespace_uri}">
<dc:title>{lang_alt(title, lang)}</dc:title>
<dc:description>{lang_alt(desc, lang)}</dc:description>
<dc:subject>{bag(kws)}</dc:subject>
<dc:language><rdf:Bag><rdf:li>{_x(lang)}</rdf:li></rdf:Bag></dc:language>
<Iptc4xmpCore:AltTextAccessibility>{lang_alt(alt, lang)}</Iptc4xmpCore:AltTextAccessibility>
<Iptc4xmpCore:ExtDescrAccessibility>{lang_alt(ext, lang)}</Iptc4xmpCore:ExtDescrAccessibility>
{custom_xml}
</rdf:Description>
</rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return packet.encode("utf-8")


# ------------------------------------------------------------ PNG

def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def _png_chunks(data: bytes):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Not PNG")
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        yield kind, data[pos + 8:pos + 8 + length], data[pos:pos + 12 + length]
        pos += 12 + length
        if kind == b"IEND":
            break


def _ist_png_xmp(kind: bytes, payload: bytes) -> bool:
    return kind == b"iTXt" and payload.startswith(PNG_XMP_KEYWORD + b"\x00")


def embed_png_xmp(data: bytes, xmp: bytes) -> bytes:
    # iTXt: keyword \0 compression_flag compression_method language \0 translated \0 text
    xchunk = png_chunk(b"iTXt", PNG_XMP_KEYWORD + b"\x00\x00\x00\x00\x00" + xmp)
    out = bytearray(PNG_SIGNATURE)
    inserted = False
    for kind, payload, full in _png_chunks(data):
        if _ist_png_xmp(kind, payload):
            continue
        if kind == b"IDAT" and not inserted:
            out.extend(xchunk)
            inserted = True
        out.extend(full)
    if not inserted:
        raise ValueError("PNG contains no IDAT")
    return bytes(out)


def extract_png_xmp(data: bytes) -> bytes | None:
    if not data.startswith(PNG_SIGNATURE):
        return None
    for kind, payload, _ in _png_chunks(data):
        if _ist_png_xmp(kind, payload):
            rest = payload[len(PNG_XMP_KEYWORD) + 1:]
            flag, rest = rest[0], rest[2:]
            rest = rest[rest.find(b"\x00") + 1:]          # Sprachkennung
            text = rest[rest.find(b"\x00") + 1:]          # übersetztes Schlüsselwort
            if flag != 0:
                raise NotImplementedError("compressed XMP iTXt")
            return text
    return None


# ------------------------------------------------------------ JPEG

def iter_jpeg_segments(data: bytes):
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Not JPEG")
    pos = 2
    while pos < len(data) and data[pos] == 0xFF:
        start = pos
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            yield marker, start, pos, b""
            continue
        seglen = struct.unpack(">H", data[pos:pos + 2])[0]
        end = pos + seglen
        yield marker, start, end, data[pos + 2:end]
        if marker == 0xDA:
            break
        pos = end


def strip_jpeg_xmp(data: bytes) -> bytes:
    out = bytearray(b"\xff\xd8")
    last = 2
    for marker, start, end, payload in iter_jpeg_segments(data):
        if start > last:
            out.extend(data[last:start])
        if not (marker == 0xE1 and payload.startswith(JPEG_XMP_HEADER)):
            out.extend(data[start:end])
        last = end
        if marker == 0xDA:
            out.extend(data[end:])
            return bytes(out)
    out.extend(data[last:])
    return bytes(out)


def embed_jpeg_xmp(data: bytes, xmp: bytes) -> bytes:
    data = strip_jpeg_xmp(data)
    payload = JPEG_XMP_HEADER + xmp
    seglen = len(payload) + 2
    if seglen > 65535:
        raise ValueError("XMP too large for single standard JPEG APP1")
    return data[:2] + b"\xff\xe1" + struct.pack(">H", seglen) + payload + data[2:]


def extract_jpeg_xmp(data: bytes) -> bytes | None:
    for marker, _, _, payload in iter_jpeg_segments(data):
        if marker == 0xE1 and payload.startswith(JPEG_XMP_HEADER):
            return payload[len(JPEG_XMP_HEADER):]
    return None


# ------------------------------------------------------------ gemeinsam

def format_von(data: bytes) -> str | None:
    if data.startswith(PNG_SIGNATURE):
        return "PNG"
    if data.startswith(b"\xff\xd8"):
        return "JPEG"
    return None


def embed_xmp(data: bytes, fmt: str, xmp: bytes) -> bytes:
    return embed_png_xmp(data, xmp) if fmt == "PNG" else embed_jpeg_xmp(data, xmp)


def extract_xmp(data: bytes, fmt: str) -> bytes | None:
    return extract_png_xmp(data) if fmt == "PNG" else extract_jpeg_xmp(data)


def parse_xmp(xmp: bytes, cfg: BildKonfig | None = None) -> dict[str, Any]:
    cfg = cfg or BildKonfig()
    cleaned = re.sub(r"<\?xpacket[^>]*\?>", "", xmp.decode("utf-8")).strip()
    root = ET.fromstring(cleaned)
    ns = {"rdf": RDF_NS, "dc": DC_NS, "iptc": IPTC_CORE_NS}

    def alt(xpath: str) -> str:
        el = root.find(xpath, ns)
        if el is None:
            return ""
        vals = [li.text for li in el.findall(".//rdf:li", ns) if li.text]
        return vals[0] if vals else ""

    docrag = {}
    praefix = "{" + cfg.docrag_namespace_uri + "}"
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.startswith(praefix):
            docrag[el.tag[len(praefix):]] = el.text or ""

    return {
        "title": alt(".//dc:title"),
        "description": alt(".//dc:description"),
        "alt_text": alt(".//iptc:AltTextAccessibility"),
        "extended_description": alt(".//iptc:ExtDescrAccessibility"),
        "keywords": [li.text or "" for li in root.findall(".//dc:subject/rdf:Bag/rdf:li", ns)],
        "docrag": docrag,
    }


def lies_docrag(path: Path, cfg: BildKonfig) -> dict[str, Any] | None:
    """Metadaten eines bereits verarbeiteten Bildes, sonst None."""
    try:
        data = path.read_bytes()
        fmt = format_von(data)
        xmp = extract_xmp(data, fmt) if fmt else None
        if not xmp:
            return None
        parsed = parse_xmp(xmp, cfg)
    except Exception:
        return None
    return parsed if parsed["docrag"].get("schemaVersion") else None


def validate_written_image(path: Path, expected_format: str, cfg: BildKonfig) -> dict[str, Any]:
    data = path.read_bytes()
    xmp = extract_xmp(data, expected_format)
    if xmp is None:
        raise ValueError("XMP read-back failed")
    parsed = parse_xmp(xmp, cfg)
    with Image.open(path) as im:
        im.load()
        if im.format != expected_format:
            raise ValueError(f"format mismatch {im.format}")
        size = im.size
    return {"size": size, "xmp_bytes": len(xmp), "metadata": parsed}
