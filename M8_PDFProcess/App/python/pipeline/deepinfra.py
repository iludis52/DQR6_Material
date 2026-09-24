"""DeepInfra als Alternative zu LM Studio für Lektorat (Stufe 2) und Bilder (Stufe 3).

DeepInfra spricht dieselbe OpenAI-kompatible Schnittstelle; es ändern sich
nur Adresse, Schlüssel und – für Reasoning-Modelle – ein Zusatzparameter,
der das Nachdenken abschaltet.

Der API-Schlüssel lebt nur im Speicher dieses Prozesses (Sitzung): er wird
nie in `pipeline_config.json` oder sonst auf die Platte geschrieben. Ist
keiner gesetzt, gilt ersatzweise die Umgebungsvariable DEEPINFRA_API_KEY.
"""

from __future__ import annotations

import os
import time

import requests

BASIS_URL = "https://api.deepinfra.com/v1/openai"
STANDARD_LEKTORAT = "Qwen/Qwen3-235B-A22B-Instruct-2507"
STANDARD_VISION = "Qwen/Qwen3-VL-30B-A3B-Instruct"

_schluessel: str | None = None
_modelle_cache: tuple[float, list[dict]] | None = None


# ------------------------------------------------------------ Schlüssel

def schluessel_setzen(wert: str | None) -> None:
    global _schluessel
    _schluessel = (wert or "").strip() or None


def schluessel() -> str | None:
    return _schluessel or os.environ.get("DEEPINFRA_API_KEY") or None


def schluessel_status() -> str:
    if _schluessel:
        return f"gesetzt für diese Sitzung (…{_schluessel[-4:]})"
    if os.environ.get("DEEPINFRA_API_KEY"):
        return "aus Umgebungsvariable DEEPINFRA_API_KEY"
    return "nicht gesetzt"


def schluessel_pruefen() -> str:
    """Kleiner authentifizierter Aufruf; liefert eine lesbare Auskunft."""
    key = schluessel()
    if not key:
        return "Kein API-Key gesetzt."
    antwort = requests.post(
        f"{BASIS_URL}/chat/completions", timeout=30,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "mistralai/Mistral-Small-3.2-24B-Instruct-2506", "max_tokens": 1,
              "messages": [{"role": "user", "content": "ok"}]})
    if antwort.status_code == 401:
        return "API-Key abgelehnt (401)."
    if not antwort.ok:
        return f"DeepInfra antwortet {antwort.status_code}: {antwort.text[:200]}"
    return "API-Key gültig."


# ------------------------------------------------------------ Modelle

def modelle(neu: bool = False) -> list[dict]:
    """Modellkatalog (öffentlich, ohne Schlüssel), 10 Minuten zwischengespeichert."""
    global _modelle_cache
    if not neu and _modelle_cache and time.time() - _modelle_cache[0] < 600:
        return _modelle_cache[1]
    antwort = requests.get(f"{BASIS_URL}/models", timeout=15)
    antwort.raise_for_status()
    daten = antwort.json().get("data", [])
    _modelle_cache = (time.time(), daten)
    return daten


def _tags(modell_id: str) -> set[str]:
    try:
        for m in modelle():
            if m.get("id") == modell_id:
                return set((m.get("metadata") or {}).get("tags", []))
    except Exception:
        pass
    return set()


def modell_ids(art: str) -> list[str]:
    """'text' = Chatmodelle, 'vision' = Modelle mit Bildeingang.

    Modelle ohne Reasoning zuerst – die brauchen keinen Abschaltparameter.
    """
    auswahl = []
    for m in modelle():
        tags = set((m.get("metadata") or {}).get("tags", []))
        if "chat" not in tags or (art == "vision" and "vision" not in tags):
            continue
        auswahl.append((("reasoning" in tags) and "reasoning_effort" not in tags, m["id"]))
    return [mid for _, mid in sorted(auswahl, key=lambda x: (x[0], x[1].lower()))]


def ohne_reasoning(modell_id: str) -> dict:
    """Zusatzparameter, die das Nachdenken abschalten (leer = nicht nötig).

    DeepInfra: `reasoning_effort: "none"` für Modelle mit Stufenregelung,
    sonst `reasoning: {"enabled": false}` (laut Doku gleichwertig).
    """
    tags = _tags(modell_id)
    if "reasoning_effort" in tags:
        return {"reasoning_effort": "none"}
    if "reasoning" in tags:
        return {"reasoning": {"enabled": False}}
    return {}
