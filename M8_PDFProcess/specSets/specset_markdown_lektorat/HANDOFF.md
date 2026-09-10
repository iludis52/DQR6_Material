# Übergabe – Markdown-Lektorat, Stand Checkpoint/Resume

## Verbindliche Hierarchie

1. `constitution.md`
2. `spec.md`
3. `plan.md`
4. `tasks.md`
5. Implementierung

## Projektziel

`data/processed/<dok>/<dok>.md` wird über ein lokal in LM Studio gehostetes LLM konservativ korrigiert.

Ausgaben:

- `<dok>_korr.md`
- `<dok>_review.md`

Bildreferenzen bleiben literal und positionsstabil; Seitenumbrüche bleiben unverändert. Python trifft keine semantischen Layoutentscheidungen.

## Reale Befunde

### Lauf 1 – Gemma 4 12B

- Thinking OFF
- Kontext 21k
- Abbruch wegen HTTP Read Timeout

Ursache: zu großer passweiter Request. Danach echtes Chunking implementiert.

### Lauf 2 – Gemma 4 12B

Nach ca. 27 Minuten Abbruch im Caption-Pass:

`JSONDecodeError: Unterminated string ...`

Die strukturierte Antwort war abgeschnitten/ungültig.

## Daraufhin implementiert

### Chunk-Checkpointing

Nach jedem erfolgreich verarbeiteten Chunk werden atomar aktualisiert:

- `<dok>_korr.md`
- `<dok>_review.md`
- `data/interim/lektorat/<dok>/checkpoint.json`

Zusätzlich wird der stabile Ausgang des aktuell laufenden Passes als:

`data/interim/lektorat/<dok>/pass_base.md`

gespeichert.

Alle Chunks eines Passes werden gegen diesen eingefrorenen Ausgang analysiert. Die bis dahin freigegebenen Edits werden nach jedem Chunk kumulativ auf `pass_base.md` angewandt. Dadurch bleiben Block-IDs innerhalb eines Passes stabil und ein Lauf kann exakt beim ersten nicht abgeschlossenen Chunk fortgesetzt werden.

### Resume

`ProcessingConfig.resume = True` ist Standard.

Bei Wiederaufnahme werden geprüft:

- Quell-Hash
- Modell-ID
- Hash von `<dok>_korr.md`
- rekonstruierbarer Zustand aus `pass_base.md` + persistierten Edits

Bei Abweichung wird ein unsicheres Resume verweigert.

### Reviewstatus

`<dok>_review.md` enthält während des Laufs:

- Status `UNVOLLSTÄNDIG`
- aktuellen Pass
- nächsten Chunk

Nach erfolgreichem Abschluss: `ABGESCHLOSSEN`.

### Kompakte LLM-Ausgabe

Prompt/Policy verlangen nur:

- tatsächliche Edits
- echte `unresolved`-Fälle

Keine einzelnen `keep_unchanged`-Antworten für unveränderte Blöcke.

### Kein automatischer Retry bei kaputtem JSON

Malformed/truncated Structured Output oder Schemafehler werden nicht automatisch erneut inferiert. Der aktuelle Chunk bleibt uncommitted und kann per Resume erneut versucht werden.

Transportfehler dürfen weiterhin gemäß `retry_count` technisch wiederholt werden.

## Aktuelle konservative Chunk-Startwerte

Für Gemma 4 12B bei 21k LM-Studio-Kontext:

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

## Tests

Aktueller Paketstand: alle vorhandenen Tests grün, einschließlich:

- Checkpoint-Roundtrip
- simuliertes Crash/Resume
- Resume auf einer Kopie von `RegenEnergie.md`
- kein automatischer Retry bei invalid/truncated JSON
- Chunking/Prompt-Einbindung

## Nächster Schritt

Auf dem echten Mac/LM-Studio-System denselben Gemma-4-12B-Lauf erneut starten. Ein vorhandener gültiger Checkpoint wird automatisch fortgesetzt; für einen bewusst komplett neuen Lauf muss der alte Checkpoint entfernt/archiviert bzw. eine Restart-Funktion ergänzt werden.

Bei erneutem Fehler bitte Traceback plus die ersten Zeilen von `<dok>_review.md` und `checkpoint.json` bereitstellen.
