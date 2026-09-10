# Markdown-Lektorat

## Zweck

`markdown_lektorat` korrigiert OCR-beschädigte Markdown-Dokumente konservativ mit einem lokal in LM Studio bereitgestellten Sprachmodell.

Ausgangspunkt ist ein bereits erzeugtes Markdown-Dokument:

```text
data/processed/<DOKUMENT>/<DOKUMENT>.md
```

Der Lauf erzeugt:

```text
<DOKUMENT>_korr.md
<DOKUMENT>_review.md
```

Zusätzlich werden technische Zwischenstände und Checkpoints unter `data/interim/lektorat/` abgelegt.

Grundprinzipien:

- Quelltreue vor stilistischer Verbesserung
- keine freie fachliche Modernisierung
- Bildreferenzen bleiben unverändert und in ihrer Reihenfolge erhalten
- Seitenumbruchmarker bleiben unverändert
- unsichere Fälle werden als `unresolved` dokumentiert
- Änderungen werden blockweise und nachvollziehbar verarbeitet

---

## Projektstruktur

Die App wird installationsfrei aus dem Projektordner geladen.

```text
projekt/
├── 01_pdf_extraction.ipynb
├── 02_markdown_lektorat.ipynb
├── python/
│   ├── pdf_extraction/
│   └── markdown_lektorat/
│       ├── __init__.py
│       ├── lekt_bloecke.py
│       ├── lekt_checkpoint.py
│       ├── lekt_config.py
│       ├── lekt_kontext.py
│       ├── lekt_lauf.py
│       ├── lekt_llm.py
│       ├── lekt_manifest.py
│       ├── lekt_markdown.py
│       ├── lekt_patches.py
│       ├── lekt_pfade.py
│       ├── lekt_policy.py
│       ├── lekt_prompts.py
│       ├── lekt_review.py
│       ├── lekt_schema.py
│       ├── lekt_schutz.py
│       ├── lekt_validierung.py
│       └── skills/
│           └── markdown_lektorat/
│               ├── SKILL.md
│               ├── POLICY.md
│               └── examples/
├── tests/
└── data/
    ├── processed/
    └── interim/
```

Das Notebook fügt den Ordner `python/` beim Start zu `sys.path` hinzu. Für die eigenen Projektmodule ist deshalb kein `pip install -e .` und kein `pyproject.toml` erforderlich.

---

## Voraussetzungen

Erforderlich sind:

- Python 3.12 oder kompatibel
- Jupyter
- `pydantic`
- `markdown-it-py`
- `openai`
- LM Studio mit geladenem Modell

Der aktuelle Workflow wurde mit einem lokal bereitgestellten Gemma-Modell betrieben.

Für diesen Workflow hat sich **Thinking OFF** als notwendige Betriebsbedingung erwiesen. Mit aktiviertem Thinking konnte das Modell das Output-Tokenbudget verbrauchen, bevor eine finale strukturierte Antwort erzeugt wurde.

---

## Verwendung

### 1. LM Studio starten

- gewünschtes Modell laden
- lokalen Server starten
- Thinking deaktivieren
- prüfen, ob das Modell über den konfigurierten OpenAI-kompatiblen Endpoint erreichbar ist

Standardmäßig erwartet die Konfiguration:

```text
http://localhost:1234/v1
```

### 2. Notebook öffnen

```text
02_markdown_lektorat.ipynb
```

Das Notebook liegt im Projekt-Root.

### 3. Dokument auswählen

Die Eingabedatei liegt unter:

```text
data/processed/<DOKUMENT>/<DOKUMENT>.md
```

### 4. Lauf starten

Der zentrale Einstiegspunkt ist:

```python
ERGEBNIS = lekt_lauf.correct_markdown(config, client=CLIENT)
```

Nach erfolgreichem Abschluss enthält `ERGEBNIS` unter anderem die Pfade zur korrigierten Markdown-Datei, zum Review und zum Manifest.

---

## Verarbeitung

Die Verarbeitung erfolgt in mehreren Passes:

```text
text
table
structure
caption
```

Die Passes arbeiten blockweise auf einem strukturierten Markdown-Modell.

Typische Fehlerkategorien sind:

- Orthografie
- Grammatik
- OCR-Zeichenfehler
- Worttrennung
- Satzfragmente
- Duplikate
- Lesereihenfolge
- Tabellenfehler
- Abbildungs- und Tabellenbeschriftungen
- unklare Fälle

Das Sprachmodell liefert strukturierte Änderungsvorschläge. Diese werden in Python validiert, anhand ihrer Konfidenz bewertet und anschließend entweder angewendet, zur Prüfung markiert, verworfen oder als `unresolved` dokumentiert.

Fehlerhafte Einzelvorschläge innerhalb einer ansonsten gültigen Modellantwort brechen den gesamten Chunk nicht mehr ab; sie werden separat als `invalid` protokolliert.

---

## Schutzmechanismen

### Geschützte Inhalte

Folgende Elemente dürfen nicht verändert oder verschoben werden:

- Markdown-Bildreferenzen
- Seitenumbruchmarker

Die Pipeline erstellt vor der Bearbeitung ein Inventar dieser Elemente und prüft nach Änderungen, ob die Invarianten weiterhin erfüllt sind.

### Markdown-Validierung

Nach Änderungen werden unter anderem geprüft:

- Markdown-Struktur
- geschlossene Code-Fences
- Tabellenstruktur
- geschützte Elemente

Ungültige Kandidaten werden nicht übernommen.

---

## Checkpoint und Resume

Die Verarbeitung kann bei langen Dokumenten jederzeit unterbrochen werden.

Nach jedem erfolgreich verarbeiteten Chunk werden atomar gespeichert:

- aktuelles korrigiertes Markdown
- Review-Zwischenstand
- Checkpoint

Der Checkpoint enthält unter anderem:

- Quell-Hash
- Modell-ID
- aktuellen Pass
- nächsten Chunk
- bereits abgeschlossene Chunks
- bisher angewandte Edits
- Hash des aktuellen korrigierten Dokuments

Ein Resume wird nur durchgeführt, wenn der gespeicherte Zustand konsistent ist.

Wenn ein Checkpoint vorhanden ist, aber zugehörige Arbeitsdateien fehlen, verweigert die Pipeline aus Sicherheitsgründen das Resume.

Für einen bewussten Neustart kann der dokumentbezogene Zwischenordner unter

```text
data/interim/lektorat/<DOKUMENT>/
```

gelöscht werden.

Nach Schema- oder Protokolländerungen ist ein frischer Lauf grundsätzlich sinnvoller als die Wiederaufnahme eines alten Checkpoints.

---

## LM-Studio-Fehlerbehandlung

Unterschiedliche Fehlerklassen werden bewusst unterschiedlich behandelt.

### Kein automatischer Retry

Bei:

- invalidem oder abgeschnittenem JSON
- Schema-/Pydantic-Fehlern, die die gesamte Modellantwort betreffen
- echten fehlerhaften Requests

Der betroffene Chunk bleibt uncommitted und kann später sicher erneut ausgeführt werden.

### Automatischer Retry

Bei transienten LM-Studio-Engine-/Channel-Fehlern, z. B.:

```text
Engine protocol predict request failed
Channel Error
fetch failed
model has crashed
model has unloaded or crashed
```

Solche Fehler können durch kurzfristige Störungen der lokalen Inference-Engine, Treiber, Betriebssystemprozesse oder des Modell-Workers entstehen.

Die Anzahl der Wiederholungen wird über `retry_count` konfiguriert.

---

## Review-Datei

`<DOKUMENT>_review.md` dokumentiert den Lauf für Menschen.

Typische Bereiche:

- Laufdaten
- Zusammenfassung
- angewendete Textkorrekturen
- strukturelle Änderungen
- Tabellenkorrekturen
- Caption-Zuordnungen
- Review-Empfehlungen
- ungeklärte Stellen
- verworfene/ungültige Vorschläge
- Integritätsprüfung

Der Review dient sowohl der Qualitätskontrolle als auch dem Debugging.

---

## Konfiguration

Zentrale Einstellungen liegen in `lekt_config.py`.

Wichtige Bereiche:

### LM Studio

```python
LMStudioConfig(
    base_url=...,
    model=...,
    timeout=...,
    temperature=0.0,
    max_output_tokens=...
)
```

### Verarbeitung

```python
ProcessingConfig(
    max_context_tokens=...,
    context_reserve_tokens=...,
    text_chunk_tokens=...,
    table_chunk_tokens=...,
    structure_chunk_tokens=...,
    caption_chunk_tokens=...,
    overlap_blocks=...,
    retry_count=...,
    resume=True,
)
```

### Confidence

Für Text- und Strukturänderungen existieren getrennte Schwellen für hohe und mittlere Konfidenz.

Hohe Konfidenz kann automatisch angewendet werden, mittlere Konfidenz wird zur Prüfung markiert, niedrige Konfidenz verworfen. `unresolved` bleibt ein eigener Zustand.

---

## Architektur

Die wichtigsten Module haben folgende Aufgaben:

| Modul | Aufgabe |
|---|---|
| `lekt_config.py` | Konfiguration |
| `lekt_bloecke.py` | stabile Dokumentblöcke und Block-IDs |
| `lekt_markdown.py` | Markdown parsen |
| `lekt_kontext.py` | Chunking und Kontextfenster |
| `lekt_prompts.py` | System- und User-Prompts |
| `lekt_schema.py` | strukturierter LLM-Vertrag |
| `lekt_llm.py` | LM-Studio-/OpenAI-kompatibler Client |
| `lekt_policy.py` | Confidence-Entscheidungen |
| `lekt_patches.py` | Änderungen anwenden |
| `lekt_schutz.py` | geschützte Elemente |
| `lekt_validierung.py` | Markdown-/Tabellenvalidierung |
| `lekt_checkpoint.py` | Checkpoint speichern/laden |
| `lekt_review.py` | Reviewbericht |
| `lekt_manifest.py` | technische Laufmetadaten |
| `lekt_pfade.py` | Ausgabepfade |
| `lekt_lauf.py` | Orchestrierung des gesamten Workflows |

`lekt_lauf.correct_markdown(...)` ist der zentrale öffentliche Einstiegspunkt.

---

## Tests

Die Tests liegen unter:

```text
tests/
```

Wesentliche abgesicherte Bereiche sind:

- Chunking
- Prompt-Inhalte
- Structured-Output-Fehler
- kein unnötiger Retry bei invalidem JSON
- Retry bei transienten LM-Studio-Enginefehlern
- Schema-Verträge
- Patch-Verhalten
- Checkpoint-Roundtrip
- Crash und Resume
- erfolgreicher End-to-End-Edit mit FakeClient

Ausführen:

```bash
python -m pytest
```

Die Tests verwenden dieselbe installationsfreie Importstrategie wie das Notebook: `tests/conftest.py` fügt den Ordner `python/` zu `sys.path` hinzu.

---

## Entwicklungshinweise

Für Änderungen am Projekt gilt:

1. funktionierende Infrastruktur nicht gleichzeitig mit fachlicher Logik umbauen
2. Änderungen möglichst in kleinen, getrennten Changesets durchführen
3. zuerst Regressionstest, dann Produktionscode ändern
4. Checkpoint-Kompatibilität bei Schemaänderungen bewusst prüfen
5. nach Änderungen an Python-Dateien den Jupyter-Kernel neu starten
6. bei Änderungen der Ordnerstruktur immer gemeinsam prüfen:
   - Notebook-Startort
   - `sys.path`
   - Datenpfade
   - Skill-Pfade
   - Tests

Die Ordnerstruktur und die Importstrategie sind Teil der Architektur und sollten nicht unabhängig voneinander geändert werden.

---

## Aktueller Betriebszustand

Der aktuelle Stand gilt als funktional stabil.

Die App verarbeitet reale OCR-Dokumente vollständig, erzeugt eine korrigierte Markdown-Datei und einen Reviewbericht und kann nach transienten LM-Studio-Ausfällen über Checkpoints sicher fortgesetzt werden.

Weitere funktionale Änderungen sollten erst vorgenommen werden, wenn ein konkreter neuer Fehler oder ein reproduzierbares Qualitätsproblem beobachtet wird.
