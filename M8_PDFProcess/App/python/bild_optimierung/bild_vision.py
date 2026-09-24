"""Semantische Bildmetadaten über ein lokales Vision-Modell (LM Studio,
OpenAI-kompatibel, Structured Output). Notebook 03, Abschnitt 05."""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bild_konfig import BildKonfig

SYSTEM_PROMPT = (
    "Erzeuge Metadaten für Bilder aus deutschen technischen Dokumenten. "
    "Beschreibe ausschließlich das tatsächlich gelieferte Bild. Nutze Dokumentkontext "
    "nur zur Plausibilisierung. Erfinde keinen unlesbaren Text und keine unsicheren "
    "Objekte. alt_text muss kurz und barrierefrei sein. description ist eine kompakte "
    "visuelle Beschreibung; extended_description darf für RAG ausführlicher sein. "
    "keywords enthält spezifische, nicht redundante Suchbegriffe."
)


def _schema(cfg: BildKonfig) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "image_semantic_metadata",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "alt_text": {"type": "string", "maxLength": cfg.max_alt_text_chars},
                    "description": {"type": "string"},
                    "extended_description": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"},
                                 "maxItems": cfg.max_keywords},
                    "semantic_visual_type": {"type": "string"},
                    "contains_visible_text": {"type": "boolean"},
                    "visible_text_summary": {"type": "string"},
                },
                "required": ["title", "alt_text", "description", "extended_description",
                             "keywords", "semantic_visual_type", "contains_visible_text",
                             "visible_text_summary"],
                "additionalProperties": False,
            },
        },
    }


def http_json(url: str, payload: dict | None = None, timeout: float = 20,
              api_key: str | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="GET" if payload is None else "POST")
    for versuch in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and versuch < 2:
                time.sleep(2 ** (versuch + 1))          # Anbieter ausgelastet: kurz warten
                continue
            # Fehlertext des Servers mitgeben statt nur "HTTP Error 400".
            raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from None
    raise RuntimeError("unerreichbar")


class VisionClient:
    """Einmal auflösen, dann je Bild aufrufen.

    Bisher wurde die Modellliste bei jedem Bild neu abgefragt, und ohne
    Treffer griff ein fest verdrahteter Rückfall auf "gemma … 12b".
    """

    def __init__(self, cfg: BildKonfig):
        self.cfg = cfg
        self.base_url = cfg.lm_base_url.rstrip("/")
        self.extra_body = dict(cfg.lm_extra_body)
        self.model_id = self._resolve(cfg.lm_model)

    def _resolve(self, preferred: str) -> str:
        ids = [m.get("id") for m in http_json(f"{self.base_url}/models", timeout=15,
                                              api_key=self.cfg.lm_api_key).get("data", [])
               if m.get("id")]
        if preferred in ids:
            return preferred
        treffer = [mid for mid in ids if preferred.lower() in mid.lower()]
        if len(treffer) == 1:
            return treffer[0]
        raise RuntimeError(f"Vision-Modell {preferred!r} nicht eindeutig verfügbar. "
                           f"Verfügbar: {ids[:25]}{' …' if len(ids) > 25 else ''}")

    def beschreibe(self, image_path: Path, kontext: dict[str, str]) -> dict[str, Any]:
        mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        return self.beschreibe_bytes(image_path.read_bytes(), mime, kontext)

    def beschreibe_bytes(self, data: bytes, mime: str, kontext: dict[str, str]) -> dict[str, Any]:
        """Direkt aus dem Speicher – die temporäre `.llm`-Datei des Notebooks entfällt."""
        cfg = self.cfg
        url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Dokumentkontext:\n"
                     + json.dumps(kontext, ensure_ascii=False, indent=2)},
                    {"type": "image_url", "image_url": {"url": url}},
                ]},
            ],
            "temperature": cfg.lm_temperature,
            "max_tokens": cfg.lm_max_tokens,
            "response_format": _schema(cfg),
        }
        try:
            response = http_json(f"{self.base_url}/chat/completions",
                                 {**payload, **self.extra_body}, cfg.lm_timeout_s, cfg.lm_api_key)
        except RuntimeError as exc:
            if not (self.extra_body and "HTTP 400" in str(exc) and "reason" in str(exc).lower()):
                raise
            self.extra_body = {}     # Modell kennt den Reasoning-Schalter nicht
            response = http_json(f"{self.base_url}/chat/completions", payload,
                                 cfg.lm_timeout_s, cfg.lm_api_key)
        choice = response["choices"][0]
        if choice.get("finish_reason") == "length":
            raise RuntimeError("Vision-Antwort am Token-Deckel abgeschnitten")
        inhalt = re.sub(r"<think>.*?</think>", "", choice["message"]["content"] or "", flags=re.S)
        zaun = re.match(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", inhalt, re.S)
        result = json.loads(zaun.group(1) if zaun else inhalt)
        result["alt_text"] = str(result.get("alt_text", "")).strip()[:cfg.max_alt_text_chars]
        result["keywords"] = list(dict.fromkeys(
            k.strip() for k in result.get("keywords", []) if isinstance(k, str) and k.strip()
        ))[:cfg.max_keywords]
        result["_model_id"] = self.model_id
        result["_generated_at"] = datetime.now(timezone.utc).isoformat()
        return result


def fallback_metadata(row: dict[str, Any], cfg: BildKonfig) -> dict[str, Any]:
    caption = (row.get("source_caption") or "").strip()
    section = (row.get("section_heading") or "").strip()
    return {
        "title": caption or section or f"Bild auf Seite {row.get('page_no')}",
        "alt_text": (caption or "Bild")[:cfg.max_alt_text_chars],
        "description": caption,
        "extended_description": "",
        "keywords": [],
        "semantic_visual_type": "",
        "contains_visible_text": False,
        "visible_text_summary": "",
        "_model_id": None,
        "_generated_at": datetime.now(timezone.utc).isoformat(),
    }
