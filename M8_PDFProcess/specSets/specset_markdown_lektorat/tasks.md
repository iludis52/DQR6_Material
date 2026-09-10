# Tasks: LLM-gestütztes Markdown-Lektorat für OCR-Dokumente

**Status:** Implementierungsbereit  
**Version:** 1.1  
**Datum:** 2026-09-08  
**Grundlagen:** `constitution.md` → `spec_final.md` → `plan_final.md`
**Review-Grundlage:** unabhängiger Cross-Artifact-Review vom 2026-09-08

---

## 1. Arbeitsregeln

Diese Taskliste wird strikt in Abhängigkeitsreihenfolge abgearbeitet.

Für alle automatisierbar testbaren Anforderungen gilt:

```text
RED-Test schreiben
    ↓
Test ausführen und erwartetes Scheitern bestätigen
    ↓
minimale Implementierung
    ↓
Test auf GREEN bringen
    ↓
bestehende Tests vollständig ausführen
    ↓
erst dann nächster Task
```

Ein Implementierungstask darf erst begonnen werden, wenn der unmittelbar zugehörige RED-Test existiert und erwartungsgemäß fehlschlägt.

### Taskformat

```text
- [ ] [Txxx] [RED|GREEN|REFACTOR|EVAL|HUMAN] Beschreibung mit konkretem Dateipfad
```

`[P]` bedeutet, dass ein Task parallel zu anderen entsprechend markierten Tasks ausgeführt werden kann, sofern seine expliziten Abhängigkeiten bereits erfüllt sind.

### Verbindliche Invarianten

Während aller Phasen gelten insbesondere:

- `<dok>.md` wird niemals überschrieben;
- Bildreferenzen bleiben literal unverändert und positionsstabil;
- Seitenumbruchmarker bleiben literal unverändert;
- Python trifft keine semantischen Layoutentscheidungen;
- das LLM schreibt keine Dateien;
- das LLM erzeugt keine freie Gesamtfassung des Dokuments;
- ungeklärte Fälle können `unresolved` bleiben;
- jede automatisch angewendete strukturelle Änderung erscheint im Reviewbericht.

---

# Phase 1 — Projektgerüst und Testbasis

**Ziel:** Eine lauffähige, aber fachlich noch leere Modulstruktur mit funktionierendem Test-Runner.

## Tests / Setup

- [ ] [T001] [GREEN] Projektverzeichnisse gemäß `plan.md` anlegen: `src/markdown_lektorat/`, `skills/markdown_lektorat/`, `tests/unit/`, `tests/integration/`, `tests/regression/cases/`, `notebooks/`
- [ ] [T002] [GREEN] Python-Paketgrundgerüst in `src/markdown_lektorat/__init__.py` und leere Moduldateien `config.py`, `paths.py`, `models.py`, `markdown_parser.py`, `protected.py`, `blocks.py`, `chunking.py`, `lm_client.py`, `prompts.py`, `edit_policy.py`, `patcher.py`, `validators.py`, `review.py`, `manifest.py`, `pipeline.py` anlegen
- [ ] [T003] [GREEN] Testkonfiguration für `pytest` in der bestehenden Projektkonfiguration ergänzen; Import von `markdown_lektorat` aus Tests sicherstellen
- [ ] [T004] [GREEN] Smoke-Test `tests/unit/test_package_import.py` anlegen und erfolgreich ausführen

**Checkpoint:** Paket und Testsuite sind ausführbar; noch keine Fachlogik.

---

# Phase 2 — Pfade, Input und Output-Namenskonvention

**Ziel:** Die bestehende Datenstruktur wird korrekt und ohne Kenntnis der OCR-Pipeline adressiert.

## Pfadauflösung

- [ ] [T005] [RED] Tests in `tests/unit/test_paths.py` schreiben: `data/processed/<dok>/<dok>.md` wird korrekt als Input aufgelöst; erwartete Ziele sind `<dok>_korr.md` und `<dok>_review.md`; Tests müssen wegen fehlender Implementierung fehlschlagen
- [ ] [T006] [GREEN] Pfadmodell und Pfadauflösung in `src/markdown_lektorat/paths.py` minimal implementieren, bis T005 grün ist
- [ ] [T007] [RED] Tests in `tests/unit/test_paths.py` ergänzen: fehlende Quelldatei erzeugt klaren Fehler; Eingabe mit anderem Basisnamen wird korrekt behandelt; existierendes Ziel wird gemäß Konfiguration nicht still überschrieben
- [ ] [T008] [GREEN] Fehler- und Overwrite-Verhalten in `src/markdown_lektorat/paths.py` implementieren, bis T007 grün ist
- [ ] [T009] [RED] Tests in `tests/unit/test_paths.py` ergänzen: gesetztes `output_dir` schreibt ausschließlich `_korr.md` und `_review.md` in das konfigurierte Zielverzeichnis; Quelle bleibt am Ursprungsort
- [ ] [T010] [GREEN] `output_dir`-Unterstützung in `src/markdown_lektorat/paths.py` implementieren

## Konfiguration

- [ ] [T011] [RED] [P] Tests in `tests/unit/test_config.py` für typisierte Konfiguration schreiben: Input-, LM-Studio-, Processing-, Confidence-, Output- und Logging-Konfiguration; ungültige Confidence-Werte müssen scheitern
- [ ] [T012] [GREEN] [P] Typisierte Konfigurationsmodelle in `src/markdown_lektorat/config.py` implementieren, bis T011 grün ist
- [ ] [T013] [RED] Tests in `tests/unit/test_config.py` ergänzen: Standardkodierung ist UTF-8; Decode-Fehler werden strikt gemeldet; abweichende explizite Quellkodierung ist konfigurierbar
- [ ] [T014] [GREEN] Encoding-Strategie aus `plan_final.md` in `config.py` und beim Dateiladen/-schreiben umsetzen
- [ ] [T015] [RED] Tests ergänzen: `ConfidenceConfig` kann modellbezogene Schwellen pro Modell-ID zusätzlich zu einer expliziten Default-Policy speichern und auflösen
- [ ] [T016] [GREEN] modellbezogene Threshold-Auflösung in `src/markdown_lektorat/config.py` implementieren

**Checkpoint:** Ein Dokument kann unabhängig von der OCR-Pipeline eindeutig adressiert werden.

---

# Phase 3 — Markdown-Struktur und stabile Blockrepräsentation

**Ziel:** Markdown wird analysiert, ohne es neu zu rendern.

## Parser-Basistests

- [ ] [T017] [RED] Tests in `tests/unit/test_markdown_parser.py` schreiben: Überschriften, Absätze, Listen, Tabellen, Bildreferenzen und HTML-Kommentare werden als strukturelle Elemente erkannt; Source-Line-Bereiche sind verfügbar
- [ ] [T018] [GREEN] `markdown-it-py`-basierte Analyse in `src/markdown_lektorat/markdown_parser.py` implementieren, bis T017 grün ist
- [ ] [T019] [RED] Tests ergänzen: Parser-Roundtrip ist ausdrücklich **nicht** Teil der API; Originaltext muss separat unverändert verfügbar bleiben
- [ ] [T020] [GREEN] Parser-API so begrenzen, dass sie Struktur-/Source-Mapping liefert, aber keine implizite vollständige Neu-Serialisierung verwendet

## Blockmodell

- [ ] [T021] [RED] Tests in `tests/unit/test_blocks.py` für interne Blockrepräsentation schreiben: `block_id`, `block_type`, `start_line`, `end_line`, `raw_text`, `content_hash`, `page_segment`
- [ ] [T022] [GREEN] Blockmodell und deterministische ID-/Hash-Erzeugung in `src/markdown_lektorat/blocks.py` implementieren
- [ ] [T023] [RED] Tests ergänzen: Nach Änderung und Re-Parse entstehen konsistente neue Blockzustände; alte Source-Spans werden nicht weiterverwendet
- [ ] [T024] [GREEN] Re-Parse-/Rebuild-Funktionalität in `blocks.py` und `markdown_parser.py` implementieren
- [ ] [T025] [RED] Tests in `tests/unit/test_markdown_parser.py` ergänzen: vorhandene Listen- und Math-Blöcke werden als Struktur erkannt und bleiben ohne expliziten Edit literal unverändert
- [ ] [T026] [GREEN] Listen-/Math-Erkennung und Preservation-Verhalten über bestehende Blocktypen/`replace_text`-Strategie absichern; keine separate semantische Python-Operation einführen

**Checkpoint:** Das Dokument ist strukturierbar, ohne sein Quell-Markdown neu zu schreiben.

---

# Phase 4 — Geschützte Elemente

**Ziel:** Bildreferenzen und Seitenumbrüche werden zu harten, automatisiert prüfbaren Invarianten.

## Inventar

- [ ] [T027] [RED] Tests in `tests/unit/test_protected.py` schreiben: alle Bildreferenzen und `<!-- Seitenumbruch -->`-Marker werden mit Literaltext, Reihenfolge und Position inventarisiert
- [ ] [T028] [GREEN] Inventarisierung in `src/markdown_lektorat/protected.py` implementieren

## Integritätsprüfung

- [ ] [T029] [RED] Tests schreiben: veränderte Bildreferenz muss fehlschlagen; entfernte Bildreferenz muss fehlschlagen; geänderte Bildreihenfolge muss fehlschlagen
- [ ] [T030] [GREEN] Bildreferenz-Validator implementieren
- [ ] [T031] [RED] Tests schreiben: entfernter, veränderter oder in der Reihenfolge verschobener Seitenumbruch muss fehlschlagen
- [ ] [T032] [GREEN] Seitenumbruch-Validator implementieren
- [ ] [T033] [RED] Integrationstest `tests/integration/test_protected_integrity.py`: ein ansonsten gültiger Korrekturlauf mit Integritätsverletzung darf nicht finalisiert werden
- [ ] [T034] [GREEN] Integritätsfehler als harten Pipeline-Fehler in `src/markdown_lektorat/validators.py` modellieren

**Checkpoint:** Geschützte Elemente können technisch nicht unbemerkt beschädigt werden.

---

# Phase 5 — LLM-Response-Contract und Operations-Whitelist

**Ziel:** Vor jedem echten Modellaufruf steht fest, welche Entscheidungen das LLM überhaupt zurückgeben darf.

## Contract-Modell

- [ ] [T035] [RED] Tests in `tests/unit/test_models.py` für einen gültigen Edit-Response schreiben: Ziel-ID, Kategorie, Operation, Source-Referenz, `confidence_score`, Begründung
- [ ] [T036] [GREEN] Pydantic-Modelle in `src/markdown_lektorat/models.py` implementieren
- [ ] [T037] [RED] Tests ergänzen: `confidence_score < 0` und `> 1` müssen ungültig sein; unbekannte Zusatzfelder müssen verworfen werden; fehlende Pflichtfelder müssen fehlschlagen
- [ ] [T038] [GREEN] Strikte Pydantic-Validierung implementieren

## Operations-Whitelist

- [ ] [T039] [RED] Contract-Tests für erlaubte Operationsfamilie schreiben: `replace_text`, `delete_duplicate`, `merge_blocks`, `move_text_block`, `replace_table`, `move_caption`, `keep_unchanged`, `unresolved`
- [ ] [T040] [GREEN] Operations-Enum/Discriminated-Union in `models.py` implementieren
- [ ] [T041] [RED] Tests schreiben: unbekannte Operation sowie generische `custom`-/Code-Ausführung werden strikt abgelehnt
- [ ] [T042] [GREEN] Whitelist strikt durchsetzen

## JSON-Schema

- [ ] [T043] [RED] Test schreiben: Pydantic-Modell muss ein JSON Schema erzeugen, das die erlaubten Operationen und Scoregrenzen enthält
- [ ] [T044] [GREEN] JSON-Schema-Export für LM Studio aus `models.py` bereitstellen; keine separat manuell gepflegte Schemaquelle anlegen

**Checkpoint:** Der LLM-Vertrag ist testbar, bevor ein Modell angesprochen wird.

---

# Phase 6 — Source-Patcher

**Ziel:** Validierte Edits können lokal und deterministisch angewandt werden.

## Textreplacement

- [ ] [T045] [RED] Tests in `tests/unit/test_patcher.py`: einfacher `replace_text`-Edit ersetzt exakt den adressierten Source-Bereich und nichts anderes
- [ ] [T046] [GREEN] Minimalen Source-Patcher in `src/markdown_lektorat/patcher.py` implementieren

## Source-Match

- [ ] [T047] [RED] Tests: stimmt erwarteter Source-Text/Hash nicht mit aktuellem Dokument überein, muss der Edit abgelehnt werden
- [ ] [T048] [GREEN] Source-Match-Prüfung implementieren
- [ ] [T049] [RED] Tests: referenziert ein Edit eine im aktuellen Dokumentzustand nicht existente Block-/Ziel-ID, muss er vor jeder Patch-Anwendung abgelehnt werden
- [ ] [T050] [GREEN] explizite Ziel-ID-Existenzprüfung im Patcher/Validator implementieren

## Mehrere Edits

- [ ] [T051] [RED] Tests: mehrere nicht überlappende Edits werden korrekt vom hintersten zum vordersten Offset angewandt
- [ ] [T052] [GREEN] Mehrfach-Patching implementieren
- [ ] [T053] [RED] Tests: überlappende oder widersprüchliche Edits dürfen nicht heuristisch aufgelöst werden
- [ ] [T054] [GREEN] Edit-Konflikte als nicht automatisch anwendbar markieren

## Struktur-Operationen

- [ ] [T055] [RED] Tests für `delete_duplicate`, `merge_blocks` und `move_text_block` mit künstlichen eindeutigen Inputs schreiben
- [ ] [T056] [GREEN] Struktur-Operationen im Patcher implementieren
- [ ] [T057] [RED] Test für `move_caption`: ausschließlich Caption-Text wird verschoben; referenzierte Bildzeile bleibt byte-/literal-identisch an ihrer ursprünglichen Position
- [ ] [T058] [GREEN] `move_caption` implementieren, bis T057 grün ist

**Checkpoint:** Alle erlaubten Edit-Typen sind technisch ausführbar, ohne selbst semantisch zu entscheiden.

---

# Phase 7 — Konfidenz- und Anwendungspolitik

**Ziel:** LLM-Rohscores werden formal in Klassen und Freigabestatus überführt.

- [ ] [T059] [RED] Tests in `tests/unit/test_edit_policy.py` schreiben: konfigurierbare Rohscoregrenzen werden deterministisch auf `hoch`, `mittel`, `niedrig` gemappt
- [ ] [T060] [GREEN] Score-Mapping in `src/markdown_lektorat/edit_policy.py` implementieren
- [ ] [T061] [RED] Tests: Text- und Struktur-Edits verwenden getrennte Schwellen; mittlere/niedrige Konfidenz wird nicht automatisch angewandt
- [ ] [T062] [GREEN] risikoklassenspezifische Anwendungspolitik implementieren
- [ ] [T063] [RED] Test: `unresolved` wird unabhängig von hohem Score niemals als Dokumentänderung ausgeführt
- [ ] [T064] [GREEN] `unresolved`-Policy implementieren

**Checkpoint:** Python entscheidet nur über die Freigabepolicy, nicht über semantische Richtigkeit.

---

# Phase 8 — LM-Studio-Adapter

**Ziel:** Strukturierte LLM-Antworten werden über eine gekapselte OpenAI-kompatible Schnittstelle bezogen.

## Client-Schnittstelle

- [ ] [T065] [RED] Tests in `tests/unit/test_lm_client.py` mit Fake-Transport schreiben: Client akzeptiert `base_url`, Modell und Inferenzparameter; liefert validiertes Response-Modell
- [ ] [T066] [GREEN] `LLMClient`-Abstraktion und `LMStudioOpenAIClient` in `src/markdown_lektorat/lm_client.py` implementieren

## Preflight

- [ ] [T067] [RED] Tests mit Fake-Responses: nicht erreichbarer Server, leere Modellliste und nicht vorhandenes konfiguriertes Modell liefern klare Fehler
- [ ] [T068] [GREEN] LM-Studio-Preflight über OpenAI-kompatible Modellabfrage implementieren

## Structured Output

- [ ] [T069] [RED] Test: Chat-Completions-Anfrage muss das aus Pydantic erzeugte JSON Schema als Structured-Output-Format verwenden
- [ ] [T070] [GREEN] Schemaerzwungene Anfrage im Adapter implementieren

## Retry

- [ ] [T071] [RED] Tests: Retry nur bei technischem Fehler, Timeout, leerer/ungültiger oder schemawidriger Antwort; Retry-Limit wird eingehalten
- [ ] [T072] [GREEN] begrenzte technische Retry-Strategie implementieren
- [ ] [T073] [RED] Test: formal gültige, aber semantisch unerwünschte Modellantwort löst **keinen** Retry aus
- [ ] [T074] [GREEN] Retry-Logik entsprechend begrenzen

**Checkpoint:** LM Studio kann sicher angesprochen werden, ohne Dateizugriff oder Tool Calling.

---

# Phase 9 — Skill und Policy

**Ziel:** Das Modellverhalten wird versioniert außerhalb des Notebook-Codes festgelegt.

- [ ] [T075] [RED] Tests in `tests/unit/test_prompts.py`: fehlende `skills/markdown_lektorat/SKILL.md` oder `POLICY.md` verhindert einen produktiven Lauf
- [ ] [T076] [GREEN] Skill-/Policy-Loader in `src/markdown_lektorat/prompts.py` implementieren
- [ ] [T077] [GREEN] `skills/markdown_lektorat/SKILL.md` aus Constitution und Spec formulieren: Quelltreue, keine Erfindung, Confidence-Selbsteinschätzung, `unresolved`, strukturierte Antwort
- [ ] [T078] [GREEN] `skills/markdown_lektorat/POLICY.md` formulieren: erlaubte/verbotene Text-, Tabellen-, Struktur- und Caption-Operationen; Schutzregeln
- [ ] [T079] [RED] Tests: chunking-unabhängiger Systemprompt enthält Skill-Version, Policy, Pass-Anweisung und keinen Dateischreibauftrag
- [ ] [T080] [GREEN] chunking-unabhängige Systemprompt-Komposition implementieren
- [ ] [T081] [GREEN] Few-Shot-Beispiele unter `skills/markdown_lektorat/examples/` für Textkorrektur, Tabellen, Captions und mindestens einen `unresolved`-Fall anlegen

**Checkpoint:** Promptregeln sind versionierbar und unabhängig vom Notebook.

---

# Phase 10 — Chunking und Kontextfenster

**Ziel:** Dokumentkontext wird strukturbewusst bereitgestellt, ohne semantische Entscheidungen in Python zu kodieren.

- [ ] [T082] [RED] Tests in `tests/unit/test_chunking.py`: Target-Blöcke und Context-only-Blöcke sind unterscheidbar; Tabellen und geschützte Bild-/Seitenanker werden nicht technisch zerschnitten
- [ ] [T083] [GREEN] strukturorientierte Chunkbildung in `src/markdown_lektorat/chunking.py` implementieren
- [ ] [T084] [RED] Tests: überlappender Kontext enthält definierte Nachbarblöcke; Modell darf laut Request nur Target-IDs editieren
- [ ] [T085] [GREEN] Overlap- und Target-/Context-Markierung implementieren
- [ ] [T086] [RED] Tests in `tests/unit/test_prompts.py`: nach definierter Target-/Context-Repräsentation enthält der User-Prompt eindeutig getrennte Zielblöcke und Context-only-Blöcke; nur Target-IDs sind editierbar
- [ ] [T087] [GREEN] Target-/Context-Komposition in `src/markdown_lektorat/prompts.py` implementieren
- [ ] [T088] [RED] Test: Seitenumbruch darf als Kontextanker enthalten sein, ohne zwingend jeden LLM-Kontext dort abzuschneiden
- [ ] [T089] [GREEN] Seitenübergreifenden Kontext technisch ermöglichen

**Checkpoint:** Dem Modell kann genügend Kontext geliefert werden, ohne dass Python semantisch vorentscheidet.

---

# Phase 11 — Pass 1: Lokale Textkorrektur

**Ziel:** Rechtschreibung, Grammatik und lokale OCR-Schäden können erstmals end-to-end korrigiert werden.

- [ ] [T090] [RED] Integrationstests in `tests/integration/test_text_pass.py` mit Fake-LLM: eindeutiger OCR-Zeichenfehler wird vorgeschlagen und angewandt; geschützte Elemente bleiben erhalten
- [ ] [T091] [GREEN] Text-Pass-Orchestrierung in `src/markdown_lektorat/pipeline.py` implementieren
- [ ] [T092] [RED] Test: mittlere/niedrige Konfidenz verändert den Text nicht
- [ ] [T093] [GREEN] Confidence-Policy in Text-Pass integrieren
- [ ] [T094] [RED] Test: `unresolved` lässt Quelltext unverändert
- [ ] [T095] [GREEN] `unresolved` in Text-Pass integrieren
- [ ] [T096] [RED] Test: fremdsprachig wirkendes OCR-Artefakt darf nur verändert werden, wenn das Fake-LLM einen zulässigen Edit mit ausreichender Konfidenz liefert; Python entscheidet dies nicht selbst
- [ ] [T097] [GREEN] generische Edit-Anwendung sicherstellen, ohne sprachspezifische Python-Heuristik
- [ ] [T098] [RED] Integrationstest ergänzen: eine formal intakte Liste und mathematisches Markup bleiben ohne expliziten LLM-Edit unverändert; ein zulässiger lokaler Textedit erfolgt ausschließlich über `replace_text`
- [ ] [T099] [GREEN] Text-Pass so begrenzen, dass Listen/Math keine implizite Normalisierung erfahren

**Checkpoint:** Erster echter fachlicher End-to-End-Pass ist testbar.

---

# Phase 12 — Pass 2: Tabellen

**Ziel:** Tabellen können separat analysiert und formal abgesichert werden.

- [ ] [T100] [RED] Integrationstest `tests/integration/test_table_pass.py`: Fake-LLM liefert eindeutig reparierte Markdown-Tabelle; Ergebnis wird angewandt
- [ ] [T101] [GREEN] Tabellen-Pass implementieren
- [ ] [T102] [RED] Tests in `tests/unit/test_validators.py`: reparierte Tabelle muss parsebar sein, Trennerzeile besitzen und konsistente Spaltenzahl aufweisen
- [ ] [T103] [GREEN] formalen Tabellenvalidator in `src/markdown_lektorat/validators.py` implementieren
- [ ] [T104] [RED] Integrationstest: formal ungültige LLM-Reparatur wird verworfen und Originaltabelle bleibt erhalten
- [ ] [T105] [GREEN] Tabellen-Validierungsgate integrieren
- [ ] [T106] [RED] Test: `unresolved`-Tabelle bleibt unverändert und wird als Reviewfall geführt
- [ ] [T107] [GREEN] `unresolved`-Tabellenfluss implementieren

**Checkpoint:** Python prüft Tabellenformalität, aber nicht Zellsemantik.

---

# Phase 13 — Pass 3: Struktur, Fragmente und Duplikate

**Ziel:** Strukturelle LLM-Entscheidungen werden mit konservativer Schwelle angewandt.

- [ ] [T108] [RED] Integrationstest `tests/integration/test_structure_pass.py`: hochkonfidentes Fake-LLM-Duplikat wird entfernt
- [ ] [T109] [GREEN] Struktur-Pass für `delete_duplicate` implementieren
- [ ] [T110] [RED] Test: nur textähnliche, aber vom Fake-LLM als `keep_unchanged` bewertete Wiederholung bleibt erhalten
- [ ] [T111] [GREEN] Pipeline respektiert ausschließlich Modellentscheidung + Confidence-Policy
- [ ] [T112] [RED] Test: hochkonfidentes `merge_blocks`/`move_text_block` wird korrekt gepatcht und danach re-parsed
- [ ] [T113] [GREEN] Merge-/Move-Fluss implementieren
- [ ] [T114] [RED] Test: struktureller Edit unterhalb der hohen Schwelle wird nicht ausgeführt
- [ ] [T115] [GREEN] konservative Struktur-Schwelle integrieren

**Checkpoint:** Strukturelle Edits funktionieren ohne Python-Semantik.

---

# Phase 14 — Pass 4: Abbildungs- und Tabellenbeschriftungen

**Ziel:** Das LLM kann Captions zuordnen; Bildreferenzen bleiben unangetastet.

- [ ] [T116] [RED] Integrationstest `tests/integration/test_caption_pass.py`: eindeutige Fake-LLM-Zuordnung verschiebt Caption an ein Bild, Bildreferenz bleibt positionsstabil
- [ ] [T117] [GREEN] Caption-Pass und `move_caption`-Orchestrierung implementieren; Python stellt nur Kontext bereit und übernimmt die semantische Zuordnung ausschließlich aus der validierten LLM-Response
- [ ] [T118] [RED] Test: gemeinsame Caption für mehrere Bilder kann als gültige strukturierte Entscheidung dargestellt werden, ohne künstliche 1:1-Zuordnung
- [ ] [T119] [GREEN] Response-Modell/Caption-Pass für Mehrfachbezüge erweitern, falls für das Contract-Schema nötig
- [ ] [T120] [RED] Test: zwei konkurrierende Bilder + `unresolved` führen zu keiner Verschiebung
- [ ] [T121] [GREEN] `unresolved`-Captionfluss implementieren
- [ ] [T122] [RED] Test: Tabellenbeschriftung kann analog zu einer Tabelle verschoben werden
- [ ] [T123] [GREEN] Tabellen-Caption-Unterstützung integrieren

**Checkpoint:** Die kritischste Layoutfunktion entspricht ausdrücklich der Constitution.

---

# Phase 15 — Reviewbericht

**Ziel:** Jede Entscheidung ist menschlich nachvollziehbar.

- [ ] [T124] [RED] Tests in `tests/unit/test_review.py`: Reviewbericht besitzt Laufdaten, Zusammenfassung, Textkorrekturen, strukturelle Änderungen, Tabellenkorrekturen, Caption-Zuordnungen, Reviewfälle, `unresolved` und Integritätsstatus
- [ ] [T125] [GREEN] Review-Datenmodell und Markdown-Renderer in `src/markdown_lektorat/review.py` implementieren
- [ ] [T126] [RED] Test: jeder angewendete strukturelle Edit enthält Original, Ergebnis/Operation, Score, Klasse, Begründung und Status
- [ ] [T127] [GREEN] strukturelle Auditdetails implementieren
- [ ] [T128] [RED] Test: ungeklärte Fälle erscheinen im Review, aber nicht als künstlicher Kommentar in `<dok>_korr.md`
- [ ] [T129] [GREEN] Trennung zwischen Ergebnis- und Reviewartefakt implementieren
- [ ] [T130] [RED] Test: verworfene schemawidrige oder formell ungültige LLM-Vorschläge können im Review dokumentiert werden
- [ ] [T131] [GREEN] Reviewstatus für verworfene Vorschläge implementieren
- [ ] [T132] [RED] Test: formal gültige, wegen mittlerer oder niedriger Konfidenz nicht angewendete Vorschläge erscheinen mit Score, Klasse, Begründung und Status im Reviewbericht
- [ ] [T133] [GREEN] explizite Reviewsektion für nicht angewendete mittel-/niedrigkonfidente Vorschläge implementieren

**Checkpoint:** Auditierbarkeit ist vollständig automatisiert.

---

# Phase 16 — Manifest, Checkpoints und atomare Ausgabe

**Ziel:** Ein Lauf ist technisch nachvollziehbar und kann nicht halbfertig als Erfolg erscheinen.

- [ ] [T134] [RED] Tests in `tests/unit/test_manifest.py`: Manifest enthält Run-ID, Inputpfad/-Hash, Modell, relevante Inferenzparameter, Skill-/Policy-Version, Passstatus und Output-Hashes
- [ ] [T135] [GREEN] Manifest-Erzeugung in `src/markdown_lektorat/manifest.py` implementieren
- [ ] [T136] [RED] Integrationstest: optionale Raw-Request/-Response-Artefakte landen unter `data/interim/lektorat/<dok>/<run_id>/`
- [ ] [T137] [GREEN] optionale technische Zwischenartefakte implementieren
- [ ] [T138] [RED] Integrationstest: Ausgabe wird zunächst temporär geschrieben; Integritätsfehler verhindert finale `<dok>_korr.md`
- [ ] [T139] [GREEN] atomare Finalisierung in `pipeline.py` implementieren
- [ ] [T140] [RED] Test: abgebrochener Pass erzeugt keinen erfolgreichen Gesamtstatus
- [ ] [T141] [GREEN] Pass-/Runstatus und Fehlerfinalisierung implementieren
- [ ] [T142] [RED] Tests in `tests/unit/test_validators.py` und Integrationstest ergänzen: durch einen Edit neu eingeführte formale Markdown-Strukturfehler werden vor Finalisierung erkannt; Validator verändert den Inhalt nicht selbst
- [ ] [T143] [GREEN] formale Markdown-Gesamtvalidierung durch Re-Parse in `src/markdown_lektorat/validators.py` integrieren

**Checkpoint:** Fehlerhafte oder unvollständige Läufe können nicht als erfolgreich erscheinen.

---

# Phase 17 — Gesamtorchestrierung

**Ziel:** Alle Pässe laufen über eine einzige öffentliche API.

- [ ] [T144] [RED] Integrationstest `tests/integration/test_pipeline_end_to_end.py` mit Fake-LLM für vollständigen Ablauf: Input → Preflight → Text → Tabelle → Struktur → Caption → Validierung → `_korr.md` + `_review.md`
- [ ] [T145] [GREEN] öffentliche Funktion `correct_markdown(...)` in `src/markdown_lektorat/pipeline.py` implementieren und aus `src/markdown_lektorat/__init__.py` exportieren
- [ ] [T146] [RED] Test: Aufruf benötigt keinen Zustand aus der vorgelagerten OCR-Pipeline und keine `<dok>.json`
- [ ] [T147] [GREEN] Abhängigkeiten ausschließlich auf `.md`, Konfiguration, Skill/Policy und LM-Studio-Client begrenzen
- [ ] [T148] [RED] Test mit einer Kopie von `RegenEnergie.md`: Quelle bleibt nach vollständigem Fake-Lauf byte-identisch
- [ ] [T149] [GREEN] Source-Unveränderlichkeit im End-to-End-Fluss sicherstellen

**Checkpoint:** Version 1 ist funktional mit Fake-LLM vollständig testbar.

---

# Phase 18 — Reales Regressionstest-Korpus

**Ziel:** Reale OCR-Probleme bilden die Grundlage für Modellwahl und Konfidenzkalibrierung.

- [ ] [T150] [EVAL] Repräsentative isolierte Fälle unter `tests/regression/cases/` anlegen und die FR-161-Mindestklassen vollständig abdecken: fehlerfreier deutscher Fließtext; leichte OCR-Fehler; schwere OCR-Fehler; Silbentrennung; fehlerhafte Wortzusammenziehung; vermischte Spalten; Duplikate; fragmentierte Sätze; intakte Markdown-Tabelle als Preservation-Fall; beschädigte Tabelle; Abbildungsbeschriftung; Tabellenbeschriftung; Seitenumbruch als eigener Invariantenfall; mehrere konkurrierende Caption-Kandidaten; mehrere Bilder mit gemeinsamer Caption; absichtlich nicht eindeutig lösbarer Fall. `RegenEnergie.md` dient als zentrale reale Ausgangsquelle.
- [ ] [T151] [EVAL] Für jeden Regressionstestfall `expected.yaml` mit `protected`, `required_edits`, `allowed_edits`, `forbidden_edits`, `expected_unresolved` und Risikoklasse erstellen
- [ ] [T152] [RED] Regression-Harness-Test `tests/regression/test_cases.py` schreiben, der alle Fälle parametrisiert lädt und zunächst mangels vollständiger Evaluationslogik fehlschlägt
- [ ] [T153] [GREEN] Regression-Harness implementieren: dasselbe Korpus kann gegen beliebige konfigurierte LLM-Clients ausgeführt werden
- [ ] [T154] [RED] Tests: geschützte Strings und verbotene Edits werden in der Regression automatisch bewertet
- [ ] [T155] [GREEN] automatische harte Regression-Metriken implementieren
- [ ] [T156] [EVAL] Bewertungsfelder für semantisch manuell zu prüfende Fälle ergänzen; keine künstliche Volltext-Goldfassung erzwingen

**Checkpoint:** Reale Dokumentfehler sind als wiederholbares Testkorpus verfügbar.

---

# Phase 19 — Reale LM-Studio-Modelltests und Kalibrierung

**Ziel:** Produktionsmodell und Confidence-Schwellen werden empirisch statt intuitiv gewählt.

## Preflight

- [ ] [T157] [EVAL] Konkrete lokal verfügbare Modell-ID und Quantisierung für Gemma 4 12B Unified dokumentieren
- [ ] [T158] [EVAL] Konkrete lokal verfügbare Modell-ID und Quantisierung für Qwen3.8-27B dokumentieren

## Modellläufe

- [ ] [T159] [EVAL] Gesamtes Regressionstest-Korpus mit Gemma 4 12B Unified unter fixierten Inferenzparametern ausführen und Rohresultate speichern
- [ ] [T160] [EVAL] Dasselbe Korpus mit Qwen3.8-27B unter vergleichbaren fixierten Inferenzparametern ausführen und Rohresultate speichern

## Auswertung

- [ ] [T161] [EVAL] Pro Modell erfassen: korrekte Edits, Überkorrekturen, Halluzinationen, `unresolved`, Caption-/Tabellenentscheidungen, Schemafehler, Latenz und Scoreverteilung
- [ ] [T162] [EVAL] Hochkonfident falsche Entscheidungen separat analysieren und dokumentieren
- [ ] [T163] [EVAL] Rohscorebereiche gegen tatsächlich korrekte Entscheidungen auswerten
- [ ] [T164] [EVAL] Empirische Grenzen für `hoch`, `mittel`, `niedrig` separat für Text- und Strukturänderungen bestimmen
- [ ] [T165] [RED] Kalibrierte Schwellen als Regressionstest festschreiben: bekannte Testfälle müssen erwartete Apply-/Review-/Reject-Entscheidung erhalten
- [ ] [T166] [GREEN] Produktionsschwellen modellbezogen in `ConfidenceConfig.model_thresholds` übernehmen und T165 grün setzen; Default-Policy nur explizit verwenden
- [ ] [T167] [EVAL] Produktionsmodell anhand projektbezogener Qualität und Stabilität auswählen; Entscheidung und Quantisierung im Projekt dokumentieren

**Checkpoint:** Modell und Confidence-Policy beruhen auf realen Projektdaten.

---

# Phase 20 — Jupyter-Steuerungsnotebook

**Ziel:** Das Modul wird in der gewünschten Arbeitsumgebung komfortabel steuerbar, ohne Logik ins Notebook zurückzuverlagern.

- [ ] [T168] [RED] Integrationstest bzw. importbasierter Smoke-Test sicherstellen: alle Notebook-benötigten öffentlichen APIs sind aus `markdown_lektorat` importierbar
- [ ] [T169] [GREEN] öffentliche API bei Bedarf bereinigen
- [ ] [T170] [GREEN] `notebooks/markdown_lektorat.ipynb` mit Zellen für Imports, Dokument-/Modellkonfiguration, Preflight, Dry Run, Korrekturlauf, Zusammenfassung und Reviewpfade erstellen
- [ ] [T171] [GREEN] Notebook-Dry-Run anzeigen lassen: Blockzahl, Tabellenzahl, Bildreferenzen, Seitenumbrüche, ohne LLM-Änderung
- [ ] [T172] [GREEN] Notebook-Ausgabe auf Laufstatus, Anzahl angewendeter Edits, Reviewfälle, `unresolved` und Artefaktpfade begrenzen
- [ ] [T173] [EVAL] Notebook einmal vollständig gegen ein kleines Regressionstest-Dokument und den ausgewählten realen LM-Studio-Stack ausführen

**Checkpoint:** Der vorgesehene VS-Code/Jupyter-Workflow funktioniert.

---

# Phase 21 — Vollständige automatisierte Abnahme

**Ziel:** Vor dem Human-in-the-loop müssen alle automatisierbaren Constitution-/Spec-Anforderungen grün sein.

- [ ] [T174] [EVAL] Gesamte Unit-Test-Suite ausführen; alle Tests müssen grün sein
- [ ] [T175] [EVAL] Gesamte Integrationstest-Suite mit Fake-LLM ausführen; alle Tests müssen grün sein
- [ ] [T176] [EVAL] Regressionstest-Korpus mit Produktionsmodell und Produktionskonfiguration ausführen
- [ ] [T177] [EVAL] Constitution-/Code-Review-Check durchführen: keine veränderten/verschobenen Bildreferenzen; keine veränderten Seitenumbrüche; kein LLM-Dateischreiben; keine semantische Python-Heuristik in `edit_policy.py`, `chunking.py`, Caption-/Tabellenlogik oder anderer Produktionslogik; `output_dir` und Encoding-Verhalten entsprechen `plan_final.md`; Markdown-Gesamtvalidator bleibt formal und repariert nicht semantisch
- [ ] [T178] [EVAL] Prüfen, dass `spec_final.md`, `plan.md`, `tasks.md` und implementiertes Verhalten keine bekannte offene Diskrepanz enthalten
- [ ] [T179] [EVAL] Erst bei vollständig erfolgreicher automatisierter Abnahme Phase 22 freigeben

---

# Phase 22 — Human-in-the-loop

**Ziel:** Reale Dokumentqualität wird abschließend durch menschliche Wahrnehmung beurteilt.

Dieser Block ist bewusst der letzte Taskblock des ersten Entwicklungszyklus.

## Reale Dokumentprüfung

- [ ] [T180] [HUMAN] Mehrere repräsentative reale OCR-Dokumente mit der Produktionskonfiguration verarbeiten; mindestens ein einfaches, ein stark beschädigtes und ein layout-chaotisches Dokument verwenden
- [ ] [T181] [HUMAN] Je Dokument `<dok>.md`, `<dok>_korr.md` und `<dok>_review.md` manuell gegeneinander prüfen
- [ ] [T182] [HUMAN] Bildreferenzen und Seitenumbrüche stichprobenartig bzw. automatisiert bestätigt mit der visuellen Dokumentstruktur abgleichen
- [ ] [T183] [HUMAN] Textkorrekturen bewerten: fehlende Korrektur, falsche Korrektur, Überkorrektur, Halluzination
- [ ] [T184] [HUMAN] Strukturänderungen bewerten: falsches Duplikat, falsches Merge/Move, falsche Lesereihenfolge
- [ ] [T185] [HUMAN] Caption-/Tabellenzuordnungen bewerten: korrekt, falsch, hätte `unresolved` sein müssen, unnötig nicht entschieden
- [ ] [T186] [HUMAN] Confidence-Verhalten beurteilen: besonders hochkonfident falsche Entscheidungen und problematische Schwellen dokumentieren
- [ ] [T187] [HUMAN] Reviewbericht auf praktische Nutzbarkeit und ausreichende Nachvollziehbarkeit prüfen

## Abschlussentscheidung

- [ ] [T188] [HUMAN] Alle gefundenen Probleme klassifizieren als **Implementierungsfehler**, **Planungsfehler**, **fehlende/fehlerhafte Spezifikationsanforderung** oder **Constitution-Grundsatzproblem**
- [ ] [T189] [HUMAN] Wenn ausschließlich lokale Implementierungsfehler bestehen: neue RED-Regressionstests als Folgetasks anlegen und Implementierung korrigieren
- [ ] [T190] [HUMAN] Wenn Anforderungen oder Architekturannahmen betroffen sind: Living-Spec-Zyklus eröffnen und in der Reihenfolge `constitution` (nur falls Grundprinzip betroffen) → `spec` → `plan` → `tasks` aktualisieren
- [ ] [T191] [HUMAN] Wenn keine blockierenden Befunde verbleiben: Version 1 des Markdown-Lektorats als fachlich abgenommen markieren

---

# Phase 23 — Living-Spec-Folgeschleife bei Bedarf

**Diese Phase wird nur aktiviert, wenn T188–T190 dies erfordern.**

- [ ] [T192] [EVAL] Für jeden systematischen Human-in-the-loop-Befund zunächst einen reproduzierbaren Regressionstest erstellen, sofern automatisierbar
- [ ] [T193] [EVAL] Betroffene Anforderung in `spec_final.md` präzisieren oder ergänzen, falls fachliches Verhalten geändert werden muss
- [ ] [T194] [EVAL] `plan.md` nur dort aktualisieren, wo die technische Strategie aufgrund der geänderten Spec angepasst werden muss
- [ ] [T195] [EVAL] Neue dependency-geordnete RED/GREEN-Tasks an diese `tasks.md` anhängen
- [ ] [T196] [EVAL] Neue Schleife ab den betroffenen Tasks durchführen und erneut mit Phase 21 und Phase 22 abschließen

---

# Abhängigkeitsübersicht

```text
Phase 1  Projektgerüst
   ↓
Phase 2  Pfade / Konfiguration
   ↓
Phase 3  Markdown / Blöcke
   ↓
Phase 4  Protected Elements
   ↓
Phase 5  LLM Contract
   ↓
Phase 6  Patcher
   ↓
Phase 7  Confidence Policy
   ↓
Phase 8  LM Studio Client
   ↓
Phase 9  Skill / Policy
   ↓
Phase 10 Chunking
   ↓
Phase 11 Text
   ↓
Phase 12 Tabellen
   ↓
Phase 13 Struktur
   ↓
Phase 14 Captions
   ↓
Phase 15 Review
   ↓
Phase 16 Manifest / atomare Ausgabe
   ↓
Phase 17 Gesamtpipeline
   ↓
Phase 18 Regressionstest-Korpus
   ↓
Phase 19 Modellbenchmark / Kalibrierung
   ↓
Phase 20 Notebook
   ↓
Phase 21 automatisierte Abnahme
   ↓
Phase 22 Human-in-the-loop
   ↓
       PASS → Version 1 abgeschlossen
       FAIL
         ↓
Phase 23 Living-Spec-Loop
```

---

# Parallelisierbare Arbeit

Parallelisierung ist nur sinnvoll, wenn sie das TDD- und Abhängigkeitsmodell nicht umgeht.

Nach Abschluss der jeweiligen Grundlagen können insbesondere parallel erfolgen:

```text
T011–T012  Konfigurationsmodell
```

Später können einzelne Regressionstestfälle in T150–T151 parallel vorbereitet werden.

Die semantischen Verarbeitungspässe sollen zunächst **nicht** parallel implementiert werden, weil sie denselben Contract-, Patcher-, Review- und Pipelinekern benutzen und frühe Erkenntnisse aus einem Pass die folgenden beeinflussen können.

---

# Review-Korrekturen vor Implementierungsstart

Die in diesem Dokument eingearbeiteten Änderungen schließen die im unabhängigen Cross-Artifact-Review festgestellten Punkte B1–B8: vollständiges Regressionstest-Korpus, alternativer Ausgabeordner, allgemeine Markdown-Validierung, modellbezogene Confidence-Schwellen, Prompt-/Chunking-Abhängigkeit, Encoding-Strategie, explizite Listen-/Math-Abdeckung und Review nicht angewendeter Vorschläge. Die nicht sinnvoll automatisierbaren Heuristik-Abwesenheitsprüfungen wurden in den Constitution-Code-Review von Phase 21 verschoben.

---

# Definition of Done

Der erste Entwicklungszyklus ist erst abgeschlossen, wenn:

- alle verpflichtenden Tasks bis einschließlich Phase 21 grün bzw. abgeschlossen sind;
- das reale Produktionsmodell und seine Quantisierung dokumentiert sind;
- Confidence-Schwellen empirisch bestimmt sind;
- `<dok>.md` unverändert bleibt;
- `<dok>_korr.md` korrekt erzeugt wird;
- `<dok>_review.md` vollständig erzeugt wird;
- geschützte Bildreferenzen und Seitenumbrüche unverletzt bleiben;
- keine semantische Python-Heuristik eingeführt wurde;
- `unresolved` praktisch funktioniert;
- der Human-in-the-loop aus Phase 22 erfolgreich abgeschlossen wurde;
- oder bei Befunden ein expliziter Living-Spec-Folgezyklus eröffnet wurde.


---

# Living-Spec-Folgezyklus: Resume nach Chunk-Abbruch

- [x] [T197] [RED] Checkpoint-Roundtrip-Test für `checkpoint.json` ergänzen.
- [x] [T198] [GREEN] `lekt_checkpoint.py` mit atomarem Lesen/Schreiben implementieren.
- [x] [T199] [RED] Integrationstest: Crash nach erfolgreichem Chunk muss `_korr.md`, `_review.md` und Checkpoint erhalten.
- [x] [T200] [GREEN] Commit nach jedem erfolgreichen Chunk implementieren.
- [x] [T201] [RED] Integrationstest: zweiter Lauf setzt beim ersten nicht abgeschlossenen Chunk fort.
- [x] [T202] [GREEN] Resume gegen eingefrorenen Pass-Ausgang plus persistierte kumulative Edits implementieren.
- [x] [T203] [GREEN] Reviewbericht um Status, aktuellen Pass und nächsten Chunk ergänzen.
- [x] [T204] [GREEN] LLM-Policy auf kompakte Ausgabe (`edits`/`unresolved`, keine unveränderten Blöcke) präzisieren.
- [x] [T205] [GREEN] konservativere Default-Chunkgrößen 2000/2500/2500/2000 setzen.
- [x] [T206] [EVAL] Resume-Verhalten auf Kopie von `RegenEnergie.md` mit simuliertem Crash und Fortsetzung verifizieren.
