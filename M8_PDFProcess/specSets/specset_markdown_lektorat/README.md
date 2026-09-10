# Markdown-Lektorat – studentische Flat-Module-Variante

Diese Variante folgt derselben Importkonvention wie die bestehende OCR-Pipeline: Python-Module liegen direkt im Projektwurzelverzeichnis und werden ohne Paketinstallation importiert.

Beispiel:

```python
%load_ext autoreload
%autoreload 2

import lekt_pfade, lekt_schema, lekt_markdown, lekt_schutz, lekt_llm, lekt_lauf
from lekt_config import AppConfig, InputConfig, LMStudioConfig, ConfidenceConfig, ThresholdPolicy, OutputConfig
```

Voraussetzung: Das Jupyter-Notebook wird mit dem Projektwurzelverzeichnis als aktuellem Arbeitsverzeichnis ausgeführt – genau wie `01_pdf_extraction.ipynb`.

Es ist kein `pip install -e .` erforderlich. Bibliotheksabhängigkeiten (`pydantic`, `markdown-it-py`, `openai`) müssen im verwendeten Python-Environment vorhanden sein.

## Kontextfenster und lokale LLM-Laufzeit

Die Verarbeitung sendet das Markdown **nicht mehr als einen einzigen Request** an LM Studio.
Stattdessen werden pro Verarbeitungspass kleinere, strukturerhaltende Fenster erzeugt.

Die wichtigsten Einstellungen stehen im Notebook in `ProcessingConfig`:

```python
ProcessingConfig(
    max_context_tokens=21000,      # harte Obergrenze des lokalen Modellkontexts
    context_reserve_tokens=2500,   # Reserve für JSON-Schema/Protokolloverhead
    text_chunk_tokens=3000,        # kleine Fenster für OCR/Textkorrektur
    table_chunk_tokens=4500,
    structure_chunk_tokens=5000,
    caption_chunk_tokens=5000,
    overlap_blocks=2,
)
```

`max_context_tokens` ist dabei **nicht** die gewünschte Größe jedes Requests. Die kleineren
`*_chunk_tokens` begrenzen die eigentlichen Arbeitsfenster. Kontextblöcke werden in ihrer
ursprünglichen Dokumentreihenfolge beigefügt und ausdrücklich als nicht editierbar markiert.

`SKILL.md` und `POLICY.md` werden bei jedem Request vollständig in den Systemprompt eingebunden.

Für lokal laufende Modelle ist ein HTTP-Timeout von 120 Sekunden oft knapp. Die Beispielkonfiguration
verwendet deshalb 300 Sekunden. Das ersetzt das Chunking nicht, sondern verhindert lediglich unnötige
Abbrüche einzelner kleiner Requests auf langsamer Hardware.


## Resume / Checkpoints

Die Verarbeitung speichert nach jedem erfolgreich verarbeiteten Chunk atomar:

- `<dok>_korr.md`
- `<dok>_review.md`
- `data/interim/lektorat/<dok>/checkpoint.json`

Zusätzlich wird für den aktuell laufenden Pass `pass_base.md` gespeichert. Dadurch kann ein unterbrochener Lauf beim ersten noch nicht erfolgreich abgeschlossenen Chunk fortgesetzt werden.

`ProcessingConfig(resume=True)` ist der Standard. Wenn ein gültiger Checkpoint vorhanden ist, dürfen die bereits vorhandenen `_korr.md`-/`_review.md`-Dateien trotz `overwrite=False` für genau diesen Lauf fortgeschrieben werden. Stimmen Quell-Hash, Modell oder korrigierter Zwischenstand nicht zum Checkpoint, wird die Wiederaufnahme aus Sicherheitsgründen verweigert.

Empfohlene Startwerte für Gemma 4 12B bei 21k Kontext:

```python
ProcessingConfig(
    max_context_tokens=21000,
    context_reserve_tokens=2500,
    text_chunk_tokens=2000,
    table_chunk_tokens=2500,
    structure_chunk_tokens=2500,
    caption_chunk_tokens=2000,
    overlap_blocks=2,
    retry_count=2,
    resume=True,
)
```

Das LLM soll nur tatsächliche Edits und echte `unresolved`-Fälle zurückgeben; unveränderte Blöcke werden nicht einzeln ausgegeben.

### Verhalten bei abgeschnittenem Structured Output

Wenn LM Studio eine abgeschnittene oder schemawidrige JSON-Antwort liefert, wird dieser Chunk **nicht** automatisch mehrfach neu inferiert. Der Lauf stoppt am betreffenden Chunk; der letzte erfolgreiche Checkpoint bleibt erhalten. Beim nächsten Aufruf mit `resume=True` wird genau dieser Chunk erneut versucht.
