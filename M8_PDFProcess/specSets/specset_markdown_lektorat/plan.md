# Implementierungsplan: LLM-gestützte Korrektur OCR-erzeugter Markdown-Dokumente

**Status:** Finaler Implementierungsplan  
**Version:** 1.0  
**Datum:** 2026-09-08  
**Grundlage:** `spec_final.md`, Version 1.0  
**Review-Grundlage:** unabhängiger Cross-Artifact-Review vom 2026-09-08  
**Zielkomponente:** unabhängige Post-Processing-Stufe für `data/processed/<dok>/<dok>.md`

---

## 1. Ziel dieses Plans

Dieser Plan beschreibt die technische Umsetzung der in `spec_final.md` definierten Korrekturstufe.

Ausgangspunkt ist die bestehende Pipeline-Struktur:

```text
data/
├── raw/<dok>.pdf
├── interim/
│   ├── befunde/<dok>/<seite:04d>.json
│   ├── ausschnitte/<dok>/<dok>_<seite:04d>_<block:02d>_<klasse>.png
│   └── kontrolle/<dok>_<seite:04d>.png
└── processed/<dok>/
    ├── <dok>.json
    ├── <dok>.md
    └── <dok>_artifacts/<dok>_<seite:04d>_<block:02d>_<klasse>.png
```

Die neue Komponente verwendet in Version 1 ausschließlich:

```text
data/processed/<dok>/<dok>.md
```

als fachlichen Input und erzeugt:

```text
data/processed/<dok>/<dok>_korr.md
data/processed/<dok>/<dok>_review.md
```

Die vorhandenen Dateien `<dok>.pdf`, `<dok>.json` und `<dok>_artifacts/*` sind keine erforderlichen Inputs der Version 1.

---

## 2. Technisches Leitbild

```text
Markdown-Quelle
      │
      ▼
deterministische Strukturierung
      │
      ▼
LLM-Analyse mit strukturiertem Ergebnis
      │
      ▼
formale Pydantic-/Integritätsvalidierung
      │
      ▼
konfidenzabhängige Edit-Freigabe
      │
      ▼
gezielte Source-Patches
      │
      ▼
erneute Validierung
      │
      ├── <dok>_korr.md
      └── <dok>_review.md
```

Wesentliche Architekturentscheidung:

> Das Markdown-Dokument wird weder vom LLM frei neu erzeugt noch aus einem Markdown-AST vollständig neu gerendert.

Der ursprüngliche Markdown-Quelltext bleibt die maßgebliche Repräsentation. Zulässige Änderungen werden als möglichst lokale Edits auf diesen Quelltext angewandt. Dadurch werden unbeabsichtigte Formatänderungen minimiert und insbesondere die Anforderungen an unveränderte Bildreferenzen und Seitenumbrüche abgesichert.

---

## 3. Einordnung in die Projektstruktur

### 3.1 Vorgeschlagene Erweiterung

```text
project/
├── data/
│   ├── raw/
│   ├── interim/
│   │   ├── befunde/
│   │   ├── ausschnitte/
│   │   ├── kontrolle/
│   │   └── lektorat/
│   │       └── <dok>/
│   │           └── <run_id>/
│   │               ├── manifest.json
│   │               ├── requests/
│   │               ├── responses/
│   │               └── checkpoints/
│   └── processed/
│       └── <dok>/
│           ├── <dok>.json
│           ├── <dok>.md
│           ├── <dok>_korr.md
│           ├── <dok>_review.md
│           └── <dok>_artifacts/
│
├── notebooks/
│   └── markdown_lektorat.ipynb
│
├── src/
│   └── markdown_lektorat/
│       ├── __init__.py
│       ├── config.py
│       ├── paths.py
│       ├── models.py
│       ├── markdown_parser.py
│       ├── protected.py
│       ├── blocks.py
│       ├── chunking.py
│       ├── lm_client.py
│       ├── prompts.py
│       ├── edit_policy.py
│       ├── patcher.py
│       ├── validators.py
│       ├── review.py
│       ├── manifest.py
│       └── pipeline.py
│
├── skills/
│   └── markdown_lektorat/
│       ├── SKILL.md
│       ├── POLICY.md
│       └── examples/
│           ├── textkorrektur.md
│           ├── tabellen.md
│           └── captions.md
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
│       ├── cases/
│       └── expected/
│
├── spec_final.md
└── plan.md
```

Die exakten vorhandenen Verzeichnisse für Notebook und `src/` können an das Projekt angepasst werden. Entscheidend ist die Trennung zwischen Notebook, wiederverwendbarer Python-Logik, versionierter LLM-Policy, Tests und Datenartefakten.

### 3.2 Unabhängigkeit von der OCR-Pipeline

Die neue Komponente soll über eine einzelne öffentliche Funktion aufrufbar sein, beispielsweise:

```python
correct_markdown(path_to_md, config)
```

Sie darf nicht voraussetzen, dass vorherige Notebook-Zellen der OCR-Pipeline ausgeführt wurden. Alle benötigten Zustände werden aus Markdown-Datei, Konfiguration, Skill-/Policy-Dateien und dem LM-Studio-Endpunkt neu aufgebaut.

---

## 4. Rolle des Jupyter-Notebooks

Das Notebook ist Orchestrierungs-, Experimentier- und Reviewoberfläche, nicht Speicherort der eigentlichen Fachlogik.

Es soll:

1. Konfiguration laden;
2. Eingabedokument auswählen;
3. LM-Studio-Verfügbarkeit prüfen;
4. verwendetes Modell anzeigen;
5. einen Dry Run ermöglichen;
6. den Korrekturlauf starten;
7. Laufstatistiken anzeigen;
8. Pfade zu Ergebnis und Reviewbericht ausgeben;
9. optional Reviewfälle anzeigen;
10. Modellbenchmarks und Kalibrierung anstoßen können.

Die Fachlogik bleibt in `src/markdown_lektorat/`. Dadurch kann dieselbe Implementierung später aus Notebook, Python-Skript, Tests oder CLI aufgerufen werden.

---

## 5. Konfiguration

Die Laufzeitkonfiguration wird typisiert modelliert. Vorgesehene Gruppen:

```text
InputConfig
LMStudioConfig
ProcessingConfig
ConfidenceConfig
OutputConfig
LoggingConfig
```

Beispielhafte Felder:

### `InputConfig`

```text
document_path
encoding = "utf-8"
decode_errors = "strict"
```

Kodierungsstrategie für Version 1:

- Markdown wird standardmäßig als UTF-8 gelesen und geschrieben;
- die Quelldatei wird mit `errors="strict"` dekodiert;
- Dekodierungsfehler führen zu einem klaren Preflight-Fehler und werden nicht durch stilles Ersetzen beschädigter Bytes kaschiert;
- `<dok>_korr.md` und `<dok>_review.md` werden als UTF-8 geschrieben;
- eine abweichende Quellkodierung kann explizit über `InputConfig.encoding` gesetzt werden.

### `LMStudioConfig`

```text
base_url
model
timeout
temperature
max_output_tokens
optional reasoning parameters
```

### `ProcessingConfig`

```text
context_strategy
max_context_tokens
overlap
retry_count
```

### `ConfidenceConfig`

```text
default_thresholds
model_thresholds
```

`default_thresholds` enthält mindestens:

```text
text_high_threshold
text_medium_threshold
structural_high_threshold
structural_medium_threshold
```

`model_thresholds` darf dieselbe Struktur modellbezogen überschreiben. Die konkrete Modell-ID bzw. Benchmark-Konfiguration ist der Schlüssel. Damit können verschiedene lokal evaluierte Modelle getrennt kalibriert werden, ohne modellabhängige Fachlogik einzuführen.

### `OutputConfig`

```text
output_dir = null
overwrite
write_intermediate_artifacts
write_raw_responses
```

Ist `output_dir` nicht gesetzt, werden `<dok>_korr.md` und `<dok>_review.md` im Verzeichnis der Eingabedatei erzeugt. Ist `output_dir` gesetzt, werden ausschließlich die neuen Ausgabe- und Reviewartefakte dort geschrieben; die Quelldatei bleibt an ihrem Ursprungsort und unverändert.

Gemma 4 12B Unified und Qwen3.8-27B werden ausschließlich über Konfiguration ausgewählt. Der Kerncode enthält keine modellabhängigen Verzweigungen, sofern spätere empirische Tests solche nicht zwingend erforderlich machen.

---

## 6. LM-Studio-Anbindung

### 6.1 Primärer Adapter

Für Version 1 wird der OpenAI-kompatible LM-Studio-Endpunkt verwendet.

Vorgesehener Client:

```python
from openai import OpenAI
```

mit lokaler `base_url`.

Gründe:

- LM Studio unterstützt OpenAI-kompatible Endpunkte;
- bestehende OpenAI-Clients lassen sich mit abweichender `base_url` verwenden;
- Structured Output steht über `/v1/chat/completions` bereit;
- der fachliche Kern bleibt gegenüber dem konkreten Serving-Backend relativ unabhängig.

### 6.2 Endpunkte

Server-/Modellprüfung:

```text
GET /v1/models
```

Inferenz:

```text
POST /v1/chat/completions
```

mit:

```text
response_format.type = json_schema
```

### 6.3 Kein Tool Calling

Version 1 nutzt kein LLM Tool Calling. Das Modell erhält keine Werkzeuge zum Lesen, Schreiben, Verschieben oder Löschen von Dateien und keinen Betriebssystemzugriff.

Das LLM liefert nur deklarative, strukturierte Entscheidungen; Python führt zugelassene Operationen aus.

### 6.4 Client-Abstraktion

Der Zugriff wird hinter einem kleinen Interface gekapselt, beispielsweise:

```python
class LLMClient(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        ...
```

Konkrete Implementierung:

```text
LMStudioOpenAIClient
```

---

## 7. Pydantic als einzige Schemaquelle

Die strukturierte LLM-Antwort wird als Pydantic-Modell definiert. Daraus wird das JSON Schema für LM Studio erzeugt.

```text
Pydantic Model
      │
      ├── Validierung der Modellantwort
      └── Generierung des JSON Schema für LM Studio
```

Damit werden ein manuell gepflegtes JSON-Schema und ein separates Python-Modell als doppelte Wahrheitsquellen vermieden.

Für LLM-Antwortmodelle ist strikte Validierung mit unbekannten Feldern als Fehler vorgesehen.

Grundstruktur:

```text
analysis_id
edits[]
unresolved[]
```

Ein Edit enthält mindestens:

```text
edit_id
target_ids
category
operation
source_text
replacement_text
confidence_score
reason
```

Nicht jede Operation benötigt `replacement_text`.

---

## 8. Operationsmodell

### 8.1 Whitelist

Nur bekannte Operationen werden ausgeführt. Vorgesehene Familie:

```text
replace_text
delete_duplicate
merge_blocks
move_text_block
replace_table
move_caption
keep_unchanged
unresolved
```

Die exakte Liste wird bei der Schemaimplementierung präzisiert.

### 8.2 Verbot generischer Ausführung

Nicht zulässig sind beispielsweise:

```text
operation = custom
python_code = ...
```

### 8.3 Ziel-ID- und Source-Match-Prüfung

Jeder verändernde Edit muss gültige Ziel-IDs und den erwarteten Ausgangszustand referenzieren. Vor Anwendung prüft Python:

- ob jede referenzierte Ziel-ID im aktuellen Dokumentzustand existiert;
- ob der adressierte Bereich noch dem analysierten Source-Text bzw. dessen Hash entspricht.

Eine nicht existente Ziel-ID oder ein fehlgeschlagener Source-Match ist ein formaler Validierungsfehler. Der Edit wird nicht angewendet.

---

## 9. Markdown-Parsing und interne Dokumentrepräsentation

### 9.1 Parser

Vorgesehen ist `markdown-it-py` mit CommonMark als Basis und aktivierter Tabellenunterstützung.

### 9.2 Verwendung

Der Parser dient zur Erkennung von:

- Blockgrenzen;
- Überschriften;
- Absätzen;
- Listen;
- Tabellen;
- Bild-Tokens;
- HTML-Blöcken;
- Source-Line-Mappings.

Die von `markdown-it-py` bereitgestellten Source-Maps (`Token.map`) werden zur Zuordnung von Block-Tokens zu Quellzeilen verwendet.

### 9.3 Kein Round-Trip-Rendering

Das finale Markdown wird nicht grundsätzlich aus der Tokenstruktur neu gerendert. Ein Renderer könnte semantisch äquivalente, aber textuell veränderte Leerzeilen, Einrückungen, Tabellenformatierungen, Listen oder Escape-Sequenzen erzeugen.

Listen und mathematisches Markup erhalten in Version 1 keine eigene Edit-Operation. Zulässige lokale Korrekturen erfolgen über `replace_text`. Listenstruktur darf nur auf LLM-Vorschlag geändert werden und muss anschließend formal parsebar bleiben. Mathematisches Markup wird konservativ behandelt und nicht semantisch durch Python umgeformt. Bereits plausible Listen- oder Math-Syntax wird nicht aus Formatierungspräferenz normalisiert.

### 9.4 Formale Markdown-Gesamtvalidierung

Nach jedem verändernden Pass und vor Finalisierung wird das resultierende Dokument erneut geparst. Die Validierung prüft, dass durch Edits keine neu entstandenen formalen Markdown-Strukturfehler eingeführt wurden und zuvor erkannte strukturelle Anker weiterhin formal auffindbar sind.

Diese Prüfung ist ausschließlich formal. Sie repariert keine semantischen Inhalte und rendert das Dokument nicht neu.

### 9.5 Interne Blockstruktur

Jeder relevante Block erhält mindestens:

```text
block_id
block_type
start_line
end_line
raw_text
content_hash
page_segment
protected_spans
```

Typen beispielsweise:

```text
heading
paragraph
list
table
image
html_comment
math
other
```

### 9.5 Reparse nach jedem Pass

Block-IDs gelten stabil innerhalb eines Verarbeitungspasses. Nach einem abgeschlossenen Änderungs-Pass wird das Dokument erneut geparst und ein neuer Blockzustand aufgebaut. Dadurch führen frühere Zeilenverschiebungen nicht zu veralteten Source-Spans in späteren Pässen.

---

## 10. Schutz von Bildreferenzen und Seitenumbrüchen

Vor der ersten LLM-Anfrage wird ein Inventar erstellt:

```text
protected_images[]
protected_pagebreaks[]
```

Für jedes Element werden gespeichert:

```text
literal_text
occurrence_index
source_position
hash
```

Die gesamte Markdown-Bildreferenz ist geschützt. `<!-- Seitenumbruch -->` wird als geschützter Anker behandelt.

Vor Ausgabe werden mindestens folgende Invarianten geprüft:

```text
Anzahl Bildreferenzen identisch
Literalwerte identisch
Reihenfolge identisch

Anzahl Seitenumbrüche identisch
Literalwerte identisch
Reihenfolge identisch
```

Eine Caption wird als Textblock bewegt. Die Bildreferenz selbst wird niemals bewegt.

---

## 11. Patch-Strategie

Änderungen werden auf konkrete Quellbereiche angewandt.

Für jeden Verarbeitungspass:

1. freigegebene Edits sammeln;
2. Source-Matches prüfen;
3. Überlappungen erkennen;
4. Konflikte nicht heuristisch auflösen;
5. nicht überlappende Edits vom hintersten zum vordersten Source-Offset anwenden;
6. Ergebnis neu parsen;
7. Integrität prüfen.

Zwei widersprüchliche Edits auf denselben Bereich werden nicht durch Python inhaltlich entschieden. Der Bereich wird als Konflikt/Reviewfall behandelt.

Die finale Datei wird zunächst temporär geschrieben und erst nach bestandener Endvalidierung als Zielartefakt finalisiert.

---

## 12. Mehrstufige Verarbeitung

### Pass 0 — Preflight

- Quelldatei laden;
- Eingabehash bilden;
- geschützte Elemente erfassen;
- Markdown parsen;
- Struktur erfassen;
- LM Studio prüfen;
- Modell prüfen;
- Run-Manifest anlegen.

Keine LLM-Änderung.

### Pass 1 — Lokale Textkorrektur

Ziele:

- Rechtschreibung;
- Grammatik;
- OCR-Zeichenfehler;
- Worttrennungen;
- lokal rekonstruierbare Satzfragmente.

Kontext:

- Zielblock;
- mehrere vorhergehende/nachfolgende Blöcke;
- Überschriftshierarchie;
- Seitenumbruchinformation.

Das Modell darf nur ausdrücklich markierte Zielblöcke editieren.

Danach:

- Confidence-Policy anwenden;
- patchen;
- reparse;
- Integrität prüfen;
- Checkpoint.

### Pass 2 — Tabellen

Ziele:

- beschädigte Markdown-Tabellen;
- Zellfragmentierung;
- vermischte Tabellen-/Fließtextteile;
- Tabellenbeschriftung.

Python prüft anschließend nur die formale Tabellenstruktur, nicht die semantische Zellzuordnung.

### Pass 3 — Struktur und Lesereihenfolge

Ziele:

- echte Duplikate;
- auseinandergerissene Sätze/Absätze;
- layoutbedingte Fehlreihenfolge;
- zusammengehörige Textfragmente.

Dieser Pass erhält größere Dokumentfenster als Pass 1. Automatische Änderungen erfolgen nur bei der kalibrierten hohen Schwelle für strukturelle Edits.

### Pass 4 — Captions

Ziele:

- Bildbeschriftungen;
- Diagrammbeschriftungen;
- Tabellenbeschriftungen;
- mehrteilige Captions;
- konkurrierende Caption-Kandidaten.

Das Modell erhält Bildreferenzen als Textanker, umliegende Blöcke, Seitenumbrüche, Überschriften, Nummerierungen, Fließtextverweise und benachbarte Tabellen/Bilder. Der Bildinhalt selbst wird nicht übermittelt.

Mögliche Ergebnisse:

```text
move_caption
keep_unchanged
unresolved
```

Die Bildreferenz bleibt positionsstabil.

### Pass 5 — Schlussprüfung

Keine freie Schlussredaktion durch das LLM.

Stattdessen:

- finaler Markdown-Parse;
- Tabellenprüfung;
- Bildintegrität;
- Seitenumbrüche;
- Edit-Konflikte;
- Vollständigkeit aller Pässe.

Danach werden `<dok>_korr.md` und `<dok>_review.md` erzeugt.

---

## 13. Chunking- und Kontextstrategie

Chunking ist ausschließlich technische Kontextverwaltung und keine semantische Entscheidungslogik.

Chunks werden bevorzugt entlang vorhandener Markdown-Strukturen gebildet:

- Überschriftenabschnitte;
- Seitenumbruchsegmente;
- Tabellen;
- Bild-/Caption-Cluster;
- Absätze.

Benachbarte Chunks erhalten überlappenden Kontext. Dabei wird explizit getrennt zwischen:

```text
target blocks
context-only blocks
```

Das Modell darf nur Target-Blöcke editieren.

Ein Seitenumbruch ist kein zwingender Kontextabbruch. Bei Strukturaufgaben darf Kontext benachbarter Seiten einbezogen werden; der Marker selbst bleibt geschützt.

Das Tokenbudget wird nicht allein anhand der maximal möglichen Modellkontextlänge gewählt, sondern empirisch bezüglich Qualität, Latenz und Zuverlässigkeit bestimmt.

---

## 14. Skill-/Prompt-System

Der Projekt-„Skill“ ist in Version 1 kein ausführbares Tool, sondern ein versioniertes Prompt-/Policy-Paket.

### `SKILL.md`

Enthält:

- Rolle;
- Ziel;
- Prioritäten;
- Quelltreue;
- Verbot freier Erfindungen;
- Verbot fachlicher Modernisierung;
- Pflicht zur Confidence-Selbsteinschätzung;
- Pflicht zu `unresolved` bei Mehrdeutigkeit.

### `POLICY.md`

Enthält:

- geschützte Elemente;
- Risikoklassen;
- Caption-Regeln;
- Tabellenregeln;
- Duplikatregeln;
- Textkorrekturregeln;
- Beispiele verbotener Überkorrektur.

### Few-Shot-Beispiele

Nach Aufgabenklasse getrennt, jeweils mit:

- Input;
- zulässigem Ergebnis;
- unzulässiger Überkorrektur;
- `unresolved`-Beispiel.

### Prompt-Aufbau

```text
SYSTEM
  ├── SKILL
  ├── POLICY
  └── pass-spezifische Anweisung

USER
  ├── Dokumentkontext
  ├── Zielblöcke
  ├── Kontextblöcke
  └── Aufgabe

RESPONSE FORMAT
  └── JSON Schema
```

---

## 15. Konfidenzmodell

Das LLM liefert:

```text
confidence_score ∈ [0.0, 1.0]
```

Python mappt auf:

```text
hoch
mittel
niedrig
```

Die Grenzwerte bleiben konfigurierbar und werden durch das Regressionstest-Korpus empirisch bestimmt. Kalibrierte Schwellen werden modellbezogen gespeichert. Existiert für ein Modell keine spezifische Kalibrierung, darf nur eine ausdrücklich konfigurierte Default-Policy verwendet werden.

Mindestens zwei Schwellenregime werden pro Modell vorgesehen:

```text
Textedits
Strukturelle Edits
```

Strukturelle Edits erhalten strengere Schwellen.

Für jeden Modellkandidaten werden Rohscores gegen reale Korrektheit ausgewertet. Hochkonfident falsche Entscheidungen werden gesondert untersucht.

`unresolved` ist ein zulässiges und erwünschtes Sicherheitsverhalten, wenn die Quelle keine eindeutige Entscheidung erlaubt.

---

## 16. Reviewbericht

Ausgabe:

```text
data/processed/<dok>/<dok>_review.md
```

Vorgeschlagene Struktur:

```markdown
# Reviewbericht: <dok>

## 1. Laufdaten
## 2. Zusammenfassung
## 3. Angewendete Textkorrekturen
## 4. Angewendete strukturelle Änderungen
## 5. Tabellenkorrekturen
## 6. Caption-Zuordnungen
## 7. Review empfohlen
## 8. Nicht angewendete Vorschläge mittlerer/niedriger Konfidenz
## 9. Ungeklärte Stellen
## 10. Verworfene / ungültige Modellantworten
## 11. Validierungs- und Integritätsprüfung
```

Jeder Änderungseintrag enthält mindestens:

```text
Edit-ID
Block-ID
Kategorie
Operation
Original
Ergebnis
Confidence-Score
Confidence-Klasse
Modellbegründung
Status
```

`<dok>_korr.md` bleibt frei von Review-Kommentaren und LLM-Metadaten.

---

## 17. Laufmanifest und Zwischenartefakte

Der Markdown-Reviewbericht ist das primäre menschliche Audit-Artefakt. Zusätzlich wird für Entwicklung/Reproduzierbarkeit ein technisches Manifest vorgesehen:

```text
data/interim/lektorat/<dok>/<run_id>/manifest.json
```

Mindestens:

```text
run_id
input_path
input_sha256
started_at
finished_at
model
base_url
inference parameters
skill version/hash
code version, soweit verfügbar
pass status
output hashes
```

Während der Entwicklung können Requests und strukturierte Responses optional gespeichert werden. Dies ist konfigurierbar.

---

## 18. Retry- und Fehlerstrategie

Automatische Wiederholung nur bei technischen Fehlern:

- Timeout;
- Verbindungsabbruch;
- temporärer Serverfehler;
- leere Antwort;
- nicht parsebare Antwort;
- Schemafehler.

Eine inhaltlich unerwünschte, aber formal gültige Entscheidung wird nicht wiederholt abgefragt, bis ein gewünschtes Ergebnis entsteht.

Nach Erreichen des Retry-Limits bleibt der Zielbereich unverändert und der technische Fehler wird protokolliert.

---

## 19. Teststrategie

### 19.1 Unit-Tests

Ohne LLM.

Zu testen:

- Pfadauflösung und Ausgabenamen;
- Bildreferenzinventar;
- Seitenumbruchinventar;
- Parser und Source-Maps;
- Pydantic-Schema;
- Scorebereich `[0,1]`;
- Operations-Whitelist;
- Patcher;
- Source-Mismatch;
- Edit-Konflikte;
- Tabellenvalidator;
- Integritätsverletzungen.

### 19.2 Integrationstests

Mit Fake-LLM-Client:

```text
Markdown → Request → strukturierte Antwort → Patch → Review
```

Damit kann die Pipeline ohne echtes Modell reproduzierbar getestet werden.

### 19.3 LLM-Regressionstests

Mit echtem LM Studio und festem Modell.

Erfasst werden mindestens:

```text
expected operation
actual operation
expected unresolved
actual unresolved
source preservation
confidence score
latency
schema-valid response
empty/truncated response
```

Dasselbe Korpus wird parametrisiert über verschiedene Modelle und Konfigurationen ausgeführt.

---

## 20. Regressionstest-Korpus

Jeder Fall erhält ein eigenes Verzeichnis:

```text
tests/regression/cases/<case_id>/
├── input.md
├── expected.yaml
└── notes.md
```

`expected.yaml` beschreibt unter anderem:

```text
protected elements
required edits
allowed edits
forbidden edits
expected unresolved
risk class
```

Das Korpus soll überwiegend aus isolierten realen Problemstellen der vorhandenen OCR-Dokumente entstehen. Es muss die in `spec_final.md` geforderten Mindestklassen vollständig abdecken:

- fehlerfreier deutscher Fließtext;
- leichte OCR-Fehler;
- schwere OCR-Fehler;
- Silbentrennung;
- fehlerhafte Wortzusammenziehung;
- vermischte Spalten;
- Duplikate;
- fragmentierte Sätze;
- intakte Markdown-Tabelle als Preservation-Fall;
- beschädigte Tabelle;
- Abbildungsbeschriftung;
- Tabellenbeschriftung;
- Seitenumbruch als eigener Invariantenfall;
- mehrere konkurrierende Caption-Kandidaten;
- mehrere Bilder mit gemeinsamer Caption;
- absichtlich nicht eindeutig lösbarer Fall.

`RegenEnergie.md` ist ein geeigneter Ausgangspunkt für zahlreiche dieser realen Fälle.

Für chaotische OCR-Dokumente soll nicht ausschließlich auf einen vollständigen Stringvergleich gesetzt werden. Pro Fall werden zwingende, verbotene und zulässige Änderungen explizit beschrieben.

---

## 21. Modellbenchmark

Initiale Kandidaten:

```text
Gemma 4 12B Unified
Qwen3.8-27B
```

jeweils in der konkret lokal verwendeten Quantisierung.

Die Quantisierung wird als Teil der Modellkonfiguration und des Benchmarks dokumentiert.

### Qualitätsmetriken

- korrekte Textedits;
- unerlaubte Überkorrekturen;
- semantische Erfindungen;
- korrekte `unresolved`-Entscheidungen;
- Caption-Zuordnungen;
- Tabellenkorrekturen;
- Duplikaterkennung.

### Structured-Output-Metriken

- Schema-Erfolgsrate;
- ungültige JSON-Antworten;
- leere Antworten;
- abgeschnittene Antworten.

### Confidence-Metriken

- Scoreverteilung;
- Trefferquote je Scorebereich;
- hochkonfident falsche Entscheidungen.

### Betriebsmetriken

- Inputtokens;
- Outputtokens;
- Laufzeit;
- Speicher-/VRAM-Verhalten soweit praktikabel;
- sinnvoll nutzbare Kontextgröße.

Das größere Modell wird nicht automatisch als Gewinner angenommen. Das Produktionsmodell wird anhand des projektspezifischen Benchmarks gewählt.

---

## 22. Inferenzparameter

Finale Inferenzparameter werden empirisch bestimmt.

Zu evaluieren:

```text
temperature
max_output_tokens
context size
reasoning mode/effort, sofern vom Backend unterstützt
```

Grundsätze:

- gleiche Parameter innerhalb eines Benchmark-Laufs;
- Parameter vollständig im Manifest dokumentieren;
- Parameteränderungen lösen Regressionstests aus;
- für strukturierte Korrekturaufgaben zunächst niedrige Varianz anstreben, ohne einen Wert vor der Evaluation normativ festzulegen.

---

## 23. Tabellenvalidierung

Nach einer LLM-Tabellenreparatur prüft Python nur formale Eigenschaften:

```text
Tabelle parsebar
Trennerzeile vorhanden
Spaltenzahl je Zeile konsistent
keine geschützten Elemente verloren
```

Python ordnet Zellinhalte nicht semantisch neu zu.

Scheitert die formale Prüfung:

```text
Edit verwerfen
Originaltabelle erhalten
Revieweintrag erzeugen
```

---

## 24. Caption-Verarbeitung ohne Bildanalyse

Version 1 lädt Bilder nicht.

Das Modell sieht beispielsweise:

```text
[BLOCK p42] ...
[IMAGE img07] ![Image](...)
[BLOCK p43] Abb. 2 ...
```

sowie größeren Kontext.

Python markiert nur strukturelle Elemente und vorhandene Seitenumbrüche. Die Caption-Zuordnung nimmt ausschließlich das LLM vor.

Mögliche strukturierte Ausgabe:

```text
decision = move_caption
image_id = ...
caption_block_id = ...
placement = before | after
confidence_score = ...
```

oder:

```text
decision = unresolved
candidate_ids = [...]
confidence_score = ...
reason = ...
```

Wenn Markdown allein nicht genügt, kann später `data/processed/<dok>/<dok>.json` als zusätzliche Evidenz eingebunden werden. Docling-Provenienz kann dabei Seitennummern und Bounding Boxes bereitstellen. Dies bleibt außerhalb von Version 1.

---

## 25. Schutz vor ungewollten Inhaltsänderungen

Vor Finalisierung werden mindestens geprüft:

```text
source hash unverändert
protected images vollständig
protected page breaks vollständig
keine unbekannte Edit-Operation
alle angewandten Edits auditiert
alle Source-Matches bestanden
```

Zusätzlich wird eine Laufstatistik erzeugt:

```text
Anzahl Blöcke untersucht
Anzahl Edits vorgeschlagen
Anzahl automatisch angewendet
Anzahl Review
Anzahl unresolved
Anzahl verworfen
```

Eine ungewöhnlich hohe Änderungsquote kann als Warnung im Reviewbericht erscheinen, blockiert den Lauf aber nicht allein aufgrund eines heuristischen Schwellenwertes.

---

## 26. Ausgabe- und Überschreibstrategie

`<dok>.md` wird niemals verändert.

Für die Entwicklungsphase wird empfohlen:

```text
overwrite = false
```

bei bereits vorhandenem `<dok>_korr.md`. Ein explizites Konfigurationsflag kann Überschreiben erlauben.

Das korrigierte Dokument wird zunächst temporär geschrieben und erst nach bestandener Validierung finalisiert.

---

## 27. Notebook-Ablauf

Vorgesehene Zellen:

### 1. Imports und Projektpfad

```python
from markdown_lektorat import ...
```

### 2. Konfiguration

```python
DOC = "RegenEnergie"
MODEL = "..."
```

### 3. Preflight

- Input vorhanden;
- LM Studio erreichbar;
- Modell verfügbar;
- Ausgabeziele anzeigen.

### 4. Optionaler Dry Run

- Struktur analysieren;
- Blöcke zählen;
- Tabellen zählen;
- Bilder zählen;
- Seitenumbrüche zählen;
- noch keine LLM-Änderung.

### 5. Korrekturlauf

```python
result = correct_markdown(...)
```

### 6. Zusammenfassung

- Laufstatus;
- Editzahlen;
- unresolved;
- Pfade.

### 7. Optional: Reviewfälle anzeigen

Das Notebook implementiert keine eigene Patch-, Parsing- oder Promptlogik.

---

## 28. Geplante Python-Module

### `config.py`
Typisierte Laufzeitkonfiguration.

### `paths.py`
Auflösung der bestehenden Datenpfade.

### `models.py`
Pydantic-Modelle für Dokumentblöcke, Requests, Responses, Edits, Revieweinträge und Laufresultate.

### `markdown_parser.py`
Markdown-Parsing und Source-Map-Aufbereitung.

### `protected.py`
Inventar und Validierung geschützter Elemente.

### `blocks.py`
Interne Blockrepräsentation.

### `chunking.py`
Kontextfenster und Target-/Context-Trennung.

### `lm_client.py`
LM-Studio/OpenAI-kompatibler API-Adapter.

### `prompts.py`
Laden und Zusammensetzen von Skill, Policy und Pass-Prompts.

### `edit_policy.py`
Mapping von Confidence-Score und Risikoklasse auf `apply / review / reject`. Keine semantische Layoutentscheidung.

### `patcher.py`
Source-Patches und Konflikterkennung.

### `validators.py`
Formale Validierung.

### `review.py`
Erstellung von `<dok>_review.md`.

### `manifest.py`
Technische Laufmetadaten.

### `pipeline.py`
Orchestriert die Verarbeitungspässe.

---

## 29. Implementierungsreihenfolge

### Phase A — deterministischer Kern

Noch ohne LLM:

1. Projektstruktur;
2. Konfiguration;
3. Pfadauflösung;
4. Markdown-Parser;
5. Blockmodell;
6. Protected-Element-Inventar;
7. Patcher;
8. Validatoren;
9. Reviewmodell;
10. Unit-Tests.

**Exit-Kriterium:** Ein künstlich vorgegebener Edit kann sicher auf eine Markdown-Datei angewandt werden, ohne geschützte Elemente zu beschädigen.

### Phase B — LLM-Vertrag

1. Pydantic-Responsemodelle;
2. JSON-Schema-Generierung;
3. LM-Studio-Client;
4. Server-/Modell-Preflight;
5. minimaler Testprompt;
6. Schemafehler-/Retry-Verhalten.

**Exit-Kriterium:** Ein lokales Modell liefert wiederholt parsebare, validierte strukturierte Responses.

### Phase C — Textkorrektur

1. Skill-Grundfassung;
2. Pass-1-Prompt;
3. Textchunking;
4. zunächst konfigurierbare Confidence-Policy;
5. Reviewausgabe.

**Exit-Kriterium:** Einfache OCR-Fehler werden korrigiert; geschützte Elemente bleiben garantiert unverändert.

### Phase D — Tabellen und Struktur

1. Tabellenpass;
2. Fragment-/Duplikatpass;
3. strukturelle Operationsmodelle;
4. konservative Confidence-Policy.

**Exit-Kriterium:** Repräsentative Problemfälle werden entweder korrekt geändert oder `unresolved` klassifiziert.

### Phase E — Captions

1. Caption-Prompt;
2. größere Kontextfenster;
3. Move-Caption-Operation;
4. mehrere Bilder / gemeinsame Caption;
5. `unresolved`-Fälle.

**Exit-Kriterium:** Das Modell kann eindeutige Fälle zuordnen und unklare Fälle stehen lassen, ohne Bildreferenzen zu bewegen.

### Phase F — Regression und Modellwahl

1. reales Testkorpus;
2. Gemma 4 12B Unified;
3. Qwen3.8-27B;
4. Quantisierungen dokumentieren;
5. Confidence-Kalibrierung;
6. Schwellen festlegen;
7. Produktionskonfiguration wählen.

### Phase G — Notebook-Integration

Erst nachdem die Kernpipeline getestet ist:

1. schlankes Steuerungsnotebook;
2. Dry Run;
3. Lauf;
4. Ergebnisanzeige;
5. Reviewanzeige.

---

## 30. Definition of Done

Version 1 ist abgeschlossen, wenn:

- `data/processed/<dok>/<dok>.md` allein als Dokumentinput genügt;
- `<dok>.md` niemals verändert wird;
- `<dok>_korr.md` erzeugt wird;
- `<dok>_review.md` erzeugt wird;
- Bildreferenzen literal und positionsstabil bleiben;
- Seitenumbrüche unverändert bleiben;
- das LLM ausschließlich strukturierte Edit-Vorschläge erzeugt;
- Python keine semantische Caption-/Layoutentscheidung trifft;
- `unresolved` vollständig unterstützt wird;
- Pydantic-Validierung aktiv ist;
- Source-Patches statt Gesamt-Neurendering verwendet werden;
- Unit- und Integrationstests vorhanden sind;
- Regressionstest-Korpus vorhanden ist;
- mindestens Gemma 4 12B Unified und Qwen3.8-27B evaluiert wurden;
- Confidence-Schwellen empirisch festgelegt wurden;
- jeder automatisch angewendete strukturelle Edit im Reviewbericht dokumentiert ist;
- ein fehlgeschlagener Integritätstest die Finalisierung verhindert.

---

## 31. Noch nicht blockierende Implementierungsparameter

Vor dem Coding sind noch konkret festzulegen:

1. verwendete Python-Version;
2. bestehende Paket-/Environment-Verwaltung;
3. tatsächlicher LM-Studio-Port bzw. `base_url`;
4. verfügbare Hardware / VRAM;
5. konkrete GGUF-/MLX-Quantisierung der Modellkandidaten;
6. Verhalten bei bereits vorhandenem `<dok>_korr.md`;
7. bestehende Namenskonventionen für Notebook- und `src/`-Module.

Diese Parameter beeinflussen Konfiguration und Projektintegration, nicht die fachliche Architektur.

---

## 32. Recherchebegründete Architekturentscheidungen

### 32.1 LM Studio Structured Output

LM Studio dokumentiert strukturierte JSON-Ausgaben über JSON Schema für `/v1/chat/completions`. Daraus folgt die Entscheidung, LLM-Ausgaben als typisierte Edit-Liste und nicht als frei formuliertes Markdown zurückzunehmen.

Quelle: https://lmstudio.ai/docs/developer/openai-compat/structured-output

### 32.2 OpenAI-kompatible API

LM Studio dokumentiert die Wiederverwendung bestehender OpenAI-Clients durch Austausch der `base_url`. Daraus folgt die Entscheidung für einen dünnen OpenAI-kompatiblen Adapter.

Quelle: https://lmstudio.ai/docs/developer/openai-compat

### 32.3 Pydantic / JSON Schema

Pydantic kann aus `BaseModel`-Definitionen JSON Schema erzeugen. Daraus folgt die Entscheidung, Pydantic als einzige Schemaquelle für Validierung und LM-Studio-Responseformat zu verwenden.

Quelle: https://pydantic.dev/docs/validation/latest/concepts/json_schema/

### 32.4 Markdown-Parsing

`markdown-it-py` stellt Block-/Inline-Tokens, Tabellenunterstützung und Source-Line-Mappings über `Token.map` bereit. Daraus folgt: Parser zur Strukturerkennung, Source-Mapping für lokale Edits, kein verpflichtendes Gesamtrendering.

Quellen:

https://markdown-it-py.readthedocs.io/en/latest/using.html

https://markdown-it-py.readthedocs.io/en/latest/api/markdown_it.token.html

### 32.5 Parametrisierte Regressionstests

Pytest unterstützt parametrisierte Tests und Fixtures. Dies eignet sich für dasselbe OCR-Testkorpus über verschiedene Modelle und Konfigurationen.

Quelle: https://docs.pytest.org/en/stable/how-to/parametrize.html

### 32.6 Docling als spätere Evidenzquelle

Das Docling-Dokumentmodell unterstützt Provenienz mit Seitennummer, Bounding Box und Character Span. Dadurch kann `<dok>.json` später optional als zusätzlicher LLM-Kontext eingebunden werden, ohne Version 1 davon abhängig zu machen.

Quelle: https://docling-project.github.io/docling/reference/docling_document/

### 32.7 Qwen3.8-27B

Die offizielle Qwen3.8-Dokumentation führt `Qwen/Qwen3.8-27B` und demonstriert OpenAI-kompatibles Serving.

Quelle: https://github.com/QwenLM/Qwen3.8

---

## 33. Empfohlener nächster SDD-Schritt

Vor dem Coding werden aus `spec_final.md` und `plan.md` folgende Implementierungsartefakte abgeleitet:

```text
1. Pydantic-Datenmodell für LLM-Edits
2. genaue Operations-Whitelist
3. SKILL.md / POLICY.md
4. erstes Regressionstest-Korpus
5. Skeleton der Python-Paketstruktur
```

Insbesondere soll das Response-/Edit-Schema **vor** der Promptoptimierung implementiert werden. Damit ist früh festgelegt, was das LLM entscheiden und was Python tatsächlich ausführen darf.


---

# Ergänzung v1.1 — Checkpoint-/Resume-Architektur

Die Pipeline wird nach jedem erfolgreichen Chunk committed. Für den aktuellen Pass wird ein stabiler Ausgang in `data/interim/lektorat/<dok>/pass_base.md` gespeichert. Der Checkpoint `checkpoint.json` ist die maschinenlesbare Source of Truth für die Wiederaufnahme.

Commit-Reihenfolge je Chunk:

```text
LLM-Antwort → Schema/Policy → kumulative Edits auf pass_base → Integritätsprüfung
→ <dok>_korr.md atomar schreiben → <dok>_review.md atomar schreiben → checkpoint.json atomar schreiben
```

Der Checkpoint wird zuletzt geschrieben und fungiert als Commit-Marker. Bei einem API-/JSON-/Timeout-Fehler wird der fehlerhafte Chunk nicht als abgeschlossen markiert. Der nächste Lauf beginnt erneut bei genau diesem Chunk.

Empfohlene Startbudgets für Gemma 4 12B / 21k Kontext: Text 2000, Tabellen 2500, Struktur 2500, Captions 2000 Target-Tokens.
