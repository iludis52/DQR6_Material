# Pipeline Dokumentenaufbereitung – Gesamtdokumentation

| | |
|---|---|
| **Gegenstand** | Dreiteilige Pipeline zur Digitalisierung von PDF-Dokumenten nach Markdown |
| **Stand** | 10.09.2026 |
| **Charakter** | Beschreibung des Ist-Zustands – keine Soll-Planung |
| **Zielgruppe** | Nutzer:innen und Entwickler:innen |
| **Einordnung** | Voll leistungsfähiger Zwischenschritt auf dem Weg zu einem möglichen späteren Produkt |

Dieses Dokument ist die übergreifende Dokumentation der Pipeline. Es beschreibt, *wie die drei Teile zusammenwirken*. Die Details jedes Teils stehen in den READMEs der Teilprojekte. Wo diese READMEs und dieses Dokument voneinander abweichen, gilt dieses Dokument. Die bekannten Abweichungen sind in [Anhang A](#anhang-a--offene-punkte-to-do) aufgeführt.

Aufbau des Dokuments (angelehnt an das Diátaxis-Schema):

1. [Überblick](#1-überblick) – was die Pipeline tut
2. [Hintergrund](#2-hintergrund-warum-die-pipeline-so-gebaut-ist) – warum sie so gebaut ist
3. [Erster Durchlauf](#3-erster-durchlauf-schritt-für-schritt) – Schritt für Schritt vom PDF zum Markdown
4. [Anleitungen](#4-anleitungen-für-typische-aufgaben) – typische Aufgaben im Betrieb
5. [Referenz](#5-referenz) – Dateien, Formate, Konfiguration, Verhalten
6. [Entscheidungsprotokoll](#6-entscheidungsprotokoll) – tragende Entscheidungen und ihre Historie
7. [Anhang A – Offene Punkte](#anhang-a--offene-punkte-to-do)
8. [Anhang B – Glossar](#anhang-b--glossar)
9. [Anhang C – Quellen](#anhang-c--quellen)

---

## 1. Überblick

### 1.1 Zweck

Die Pipeline überführt PDF-Dokumente beliebiger Herkunft in ein **portables Markdown-Dokument mit eingebundenen, optimierten Bilddateien**. Dabei bleiben die Seitengrenzen strikt erhalten.

Das Markdown-Dokument ist das **maßgebliche Ergebnis**. Es ist ausdrücklich zur weiteren Bearbeitung durch Menschen gedacht und muss auch nachbearbeitet werden. Auf dieser Grundlage lassen sich unter anderem

- Dokumente klein und portabel halten,
- Dokumente schnell in weitere Zielformate umwandeln (z. B. HTML),
- RAG-Pipelines schnell und effizient aufbauen.

Die RAG-Fähigkeit ergibt sich dabei aus einem vollständigen Markdown von selbst. Sie ist kein eigenes Ziel der Pipeline.

### 1.2 Die drei Teile

| Nr. | Teil | Notebook | Kurzbeschreibung |
|---|---|---|---|
| 01 | PDF-Extraktion | `01_pdf_extraction.ipynb` | Layout-Erkennung, Texterkennung, Zusammensetzen zu Markdown (+ JSON, Bildausschnitte) |
| 02 | Markdown-Lektorat | `02_markdown_lektorat.ipynb` | Konservative sprachliche Korrektur des Markdowns durch ein lokales LLM |
| 03 | Bildoptimierung | `03_image_optimization.ipynb` | Bildausschnitte auf 144 ppi bringen, Format wählen, XMP-Metadaten einbetten |

Die Laufreihenfolge ist fest: **01 → 02 → 03**.

### 1.3 Datenfluss

```text
data/raw/<DOK>.pdf
      │
      ▼
┌──────────────────────────────────────────────────────────────────┐
│ 01 PDF-Extraktion                                                │
│   Stufe 1  Layout-Erkennung   (PP-DocLayoutV3, ONNX)             │
│   Stufe 2  Texterkennung      (PaddleOCR-VL über LM Studio)      │
│   Stufe 4a Zusammensetzen     (deterministisch, ohne LLM)        │
└──────────────────────────────────────────────────────────────────┘
      │  data/processed/<DOK>/<DOK>.md
      │  data/processed/<DOK>/<DOK>.json          (Backup-Format)
      │  data/processed/<DOK>/<DOK>_artifacts/    (Bildausschnitte)
      ▼
┌──────────────────────────────────────────────────────────────────┐
│ 02 Markdown-Lektorat          (Gemma über LM Studio)             │
└──────────────────────────────────────────────────────────────────┘
      │  <DOK>_korr.md   (korrigiertes Markdown)
      │  <DOK>_review.md (Prüfbericht)
      ▼
┌──────────────────────────────────────────────────────────────────┐
│ 03 Bildoptimierung            (deterministisch; optional Gemma 4)│
│   arbeitet in-place im Ordner <DOK>_artifacts/                   │
└──────────────────────────────────────────────────────────────────┘
      │  optimierte Bilder mit XMP, aktualisierte Bildreferenzen,
      │  <DOK>.image-optimization.json / .csv (Audit)
      ▼
Manueller Schritt: Endfassung benennen (derzeit <DOK>_final.md)
und von Hand nachbearbeiten
```

Die Stufennummerierung von 01 (1, 2, 4a) ist historisch gewachsen. Stufe 3 und Stufe 4b gibt es nicht, siehe [E-07](#e-07-stufen-3-und-4b-entfallen).

### 1.4 Was die Pipeline zusichert – und was nicht

**Zugesichert (im Rahmen der dokumentierten Schutzmechanismen):**

- Jede Seite des PDFs wird verarbeitet oder als gescheitert vermerkt. Stillschweigende Lücken gibt es nicht.
- Seitengrenzen werden nicht aufgehoben. Was auf einer Seite steht, bleibt im Markdown innerhalb dieser Seite.
- Das Lektorat verändert und verschiebt weder Bildreferenzen noch Seitenumbruchmarker.
- Bilddateien gelten erst nach erfolgreichem Read-back als abgeschlossen.
- Unterbrochene Läufe lassen sich in 01 und 02 sicher wieder aufnehmen.

**Nicht zugesichert:**

- Fehlerfreier Text. Das Lektorat arbeitet bewusst konservativ, unsichere Fälle bleiben stehen.
- Fehlerfreie Zusammensetzung. Um Abbildungen herum kann Text doppelt oder zerrissen auftreten.
- Vollständig normalisierte Markdown-Syntax (Listen, Fußnoten, Hervorhebungen).

Das Endergebnis ist deshalb ein **hochwertiger Arbeitsstand, der eine Nachbearbeitung durch Menschen voraussetzt**. Beobachtete Fehlerbilder sind in [Anhang A](#anhang-a--offene-punkte-to-do) dokumentiert.

---

## 2. Hintergrund: Warum die Pipeline so gebaut ist

### 2.1 PDFs sind nicht deterministisch lesbar

PDF-Dokumente folgen keinem festen, erwartbaren Schema. Aus der Praxis sind unter anderem folgende Fälle bekannt:

- **a) Gestaltung:** Layout-Designer:innen gestalten nach ästhetischen Regeln. Raster können innerhalb eines Dokuments wechseln. Bildunterschriften stehen je nach Dokument über, unter oder neben dem Objekt. Tabellen sind aus gestalterischen Gründen verschachtelt, Bildelemente oft nicht geradlinig. Lehrbücher enthalten Randspalten (Marginalien). Selbst born-digital-PDFs sind dadurch kaum deterministisch erfassbar.
- **b) Scans** sind oft schief und enthalten Artefakte wie Schatten oder größere dunkle Bereiche.
- **c) 1-Bit-Bitmaps** verlieren beim Herunterskalieren jede Lesbarkeit.
- **d) Teilweise vorhandene Textebenen:** Einige Bereiche sind über den Textlayer lesbar, die meisten nicht. Triage-Filter versagen hier regelmäßig.
- **e) Text als Vektorgrafik** kann nicht als Text erfasst werden.

### 2.2 Folgerung: Das Dokument lesen wie ein Mensch

Daraus folgt der Grundsatz der Pipeline: **Die Bildebene jeder Seite ist die einzige verlässliche Quelle.** Eine vorhandene PDF-Textebene wird nicht verwendet und auch nicht zum Abgleich herangezogen.

Jede Seite wird deshalb

1. als Bild gerendert,
2. per Layout-Erkennung in typisierte Blöcke zerlegt, samt Lesereihenfolge,
3. blockweise per OCR bzw. Vision-Modell gelesen und
4. seitenweise wieder zusammengesetzt.

Layout-Erkennung und OCR sind nach aktuellem Stand der Technik kein teurer Rechenschritt mehr, weil die Modelle klein, effizient und schnell sind.

### 2.3 Seitenzurechenbarkeit

Jede Aussage im Markdown soll einer Seite des Originals zugeordnet werden können. Findet etwa ein RAG-System einen Eintrag auf einer bestimmten Seite des Markdowns, muss dieser im Original eindeutig auffindbar sein.

Die Seitenzuordnung steckt **absichtlich im Markdown selbst**, als Seitenumbruchmarker. Sie liegt nicht in einer externen Datei, weil das Markdown das maßgebliche und nachbearbeitete Dokument ist. Das aktuelle Markerformat ist in [5.4](#54-markdown-ist-format) beschrieben.

### 2.4 Trennung von Deterministik und Sprachmodell

In allen drei Teilen gilt dieselbe Arbeitsteilung:

| Deterministisch (prüfbar, reproduzierbar) | Sprachmodell (lokal, Temperatur 0, Thinking OFF) |
|---|---|
| Layout-Erkennung (ONNX) | Texterkennung je Block (PaddleOCR-VL) |
| Zusammensetzen, Überschriftenebenen, Tabellen-Parsing | Sprachliche Korrekturvorschläge (Lektorat) |
| Validierung, Schutz von Bildreferenzen und Seitenmarkern | Semantische Bildbeschreibung (optional) |
| Auflösung, Formatwahl, Quality Gates der Bilder | – |

Sprachmodelle *schlagen vor* oder *lesen*. Was davon übernommen wird, entscheidet Python-Code nach festen Regeln. Grundlinie ist KISS: Eindeutige Fälle werden deterministisch entschieden, nicht eindeutige Fälle bleiben offen oder werden als ungeklärt vermerkt.

### 2.5 Lokale Verarbeitung

Alle Modelle laufen lokal. Die Layout-Erkennung läuft als ONNX-Sitzung, die Sprach- und Vision-Modelle über den OpenAI-kompatiblen Server von LM Studio. Die schweren Modelle laufen nie gleichzeitig, weil die Verarbeitung stufenweise erfolgt.

---

## 3. Erster Durchlauf: Schritt für Schritt

Dieser Abschnitt beschreibt einen vollständigen Durchlauf eines Dokuments, so wie er aktuell ausgeführt wird.

### Schritt 1 – Umgebung bereitstellen

Voraussetzungen:

- Python 3.12 oder kompatibel, Jupyter
- LM Studio mit den benötigten Modellen (siehe [5.6](#56-modelle-und-lm-studio))
- Die Python-Pakete aus [5.7](#57-abhängigkeiten)

Die eigenen Module werden **nicht installiert**. Die Notebooks liegen im Projekt-Root und ergänzen `sys.path` beim Start selbst.

### Schritt 2 – PDF ablegen

Die PDF-Datei direkt nach `data/raw/` legen, ohne Unterordner. Der Dateiname muss dem Namensregelwerk entsprechen (siehe [5.9](#59-namensregelwerk-eingang)). Unzulässige Namen werden gemeldet und mit einem Ersatzvorschlag versehen, aber nicht automatisch geändert.

### Schritt 3 – PDF-Extraktion (01)

1. LM Studio starten, PaddleOCR-VL laden, Server starten, **Thinking deaktivieren**.
2. `01_pdf_extraction.ipynb` öffnen und in der Zellvariable `BUCH` das Dokument setzen.
3. Lauf starten, entweder für den ganzen Bestand

   ```python
   bericht = lauf.verarbeite_alle(erkenner=ERKENNER)
   ```

   oder kontrolliert für ein einzelnes Dokument:

   ```python
   lauf_einzelbuch = stapel.verarbeite_buch(PDF, buch=BUCH, bis=Stufe.KANONISCH, ...)
   ```

4. Ergebnis prüfen. Die read-only-Analyse `sichtung.py` liefert Kennzahlen zum Zwischenbestand. Die grobe Markdown-Vorschau zeigt, ob sich der Hauptstrom flüssig lesen lässt.

Ergebnis: `data/processed/<DOK>/<DOK>.md`, `<DOK>.json` und `<DOK>_artifacts/`.

### Schritt 4 – Markdown-Lektorat (02)

1. In LM Studio das Lektoratsmodell (Gemma) laden, **Thinking deaktivieren**.
2. `02_markdown_lektorat.ipynb` öffnen und das Dokument auswählen.
3. Lauf starten:

   ```python
   ERGEBNIS = lekt_lauf.correct_markdown(config, client=CLIENT)
   ```

4. `<DOK>_review.md` durchsehen, insbesondere die Empfehlungen, ungeklärten Stellen und die Integritätsprüfung.

Ergebnis: `<DOK>_korr.md` und `<DOK>_review.md`.

### Schritt 5 – Bildoptimierung (03)

1. Optional: In LM Studio Gemma 4 12B laden, falls semantische Bildmetadaten erzeugt werden sollen (`ENABLE_LLM = True`). Ohne LLM läuft die Optimierung vollständig weiter.
2. `03_image_optimization.ipynb` öffnen und `BUCH` setzen, bei nur einem PDF in `data/raw/` geschieht das automatisch. Über `MARKDOWN_OVERRIDE` lässt sich die zu aktualisierende Markdown-Datei festlegen.
3. Das Notebook von oben nach unten ausführen.
4. Die Audit-Dateien `<DOK>.image-optimization.json/.csv` prüfen.

### Schritt 6 – Endfassung

Die Endfassung wird derzeit **manuell** benannt (z. B. `<DOK>_final.md`) und von Hand nachbearbeitet. Vor der Nachbearbeitung sollte geprüft werden, ob jede Bildreferenz auf eine existierende Datei zeigt. Hintergrund ist ein bekannter Fehler bei Formatwechseln, siehe [A-01](#a-01-formatwechsel-der-bilder-erreicht-die-endfassung-nicht).

---

## 4. Anleitungen für typische Aufgaben

### 4.1 Einen unterbrochenen Lauf fortsetzen

| Teil | Vorgehen |
|---|---|
| 01 | Lauf einfach erneut starten. Fertige Seiten werden übersprungen, gescheiterte Seiten erneut versucht, fertige Dokumente nicht angerührt. Offene Seiten zeigt `stapel.offene_seiten`, offene Dokumente `lauf.offene_dokumente`. |
| 02 | Lauf erneut starten (`resume=True`). Wiederaufgenommen wird nur, wenn der Checkpoint konsistent ist. Fehlen zugehörige Arbeitsdateien, verweigert die Pipeline das Resume. |
| 03 | Es gibt kein Resume. Ein erneuter Lauf startet vom aktuellen Inhalt des Artefaktordners (siehe [4.3](#43-bildoptimierung-erneut-ausführen)). |

### 4.2 Einen bewussten Neustart erzwingen

| Teil | Vorgehen |
|---|---|
| 01 | `neu=True` setzen oder `data/interim/befunde/<DOK>/` löschen |
| 02 | `data/interim/lektorat/<DOK>/` löschen. Nach Schema- oder Protokolländerungen ist ein frischer Lauf grundsätzlich vorzuziehen. |
| 03 | Die Artefakte müssen von 01 reproduzierbar neu erzeugt werden, weil 03 in-place arbeitet |

### 4.3 Bildoptimierung erneut ausführen

03 überschreibt die Bilder im Artefaktordner. Ein zweiter Lauf rekodiert bereits verlustbehaftet komprimierte JPEGs erneut. Wiederholte Läufe deshalb nur bewusst ausführen und für einen sauberen Neustart die Artefakte vorher über 01 neu erzeugen.

### 4.4 Ohne Sprachmodell arbeiten

- **01:** Stufe 1 (`bis=Stufe.LAYOUT`) braucht weder LM Studio noch `docling-core`. Für Text ist PaddleOCR-VL erforderlich.
- **02:** Ohne Sprachmodell nicht sinnvoll nutzbar.
- **03:** `ENABLE_LLM = False` setzen. Die Metadaten werden dann deterministisch aus vorhandenen Daten gebildet und mit `SEMANTIC_METADATA_PENDING` markiert.

### 4.5 Das Markdown nachbearbeiten, ohne die Seitenzuordnung zu zerstören

Die Seitenmarker tragen derzeit keine Seitennummer. Die Seitenzuordnung ergibt sich allein aus ihrer **Anzahl und Reihenfolge** (siehe [5.4](#54-markdown-ist-format)). Bei der Nachbearbeitung gilt deshalb:

1. Keinen Marker `<!-- Seitenumbruch -->` löschen, duplizieren oder verschieben.
2. Keinen Text über einen Marker hinweg verschieben, auch nicht zum Zusammenführen getrennter Wörter oder Absätze.
3. Bildreferenzen nicht umbenennen. Der Dateiname kodiert den Seitenindex.
4. Doppelte Textpassagen nur *innerhalb* derselben Seite bereinigen.

Zur Kontrolle nach der Bearbeitung: Die Anzahl der Marker muss der Seitenzahl des PDFs minus eins entsprechen.

---

## 5. Referenz

### 5.1 Projektstruktur

```text
projekt/
├── 01_pdf_extraction.ipynb
├── 02_markdown_lektorat.ipynb
├── 03_image_optimization.ipynb
├── python/
│   ├── pdf_extraction/          Module von 01
│   │   ├── pfade.py  schema.py  layout.py  erkennung.py
│   │   └── stapel.py  lauf.py  kanonisch.py  sichtung.py
│   └── markdown_lektorat/       Paket von 02
│       ├── lekt_*.py
│       └── skills/markdown_lektorat/  SKILL.md, POLICY.md, examples/
├── models/
│   ├── pp_doclayoutv3.onnx
│   ├── labels.json
│   └── README.md
├── tests/
└── data/
    ├── raw/                     Eingang: <DOK>.pdf (keine Unterordner)
    ├── interim/                 Zwischenbestand
    │   ├── befunde/             01: SeitenBefunde je Dokument
    │   ├── ausschnitte/         01: Bildausschnitte
    │   ├── kontrolle/           01
    │   └── lektorat/            02: Checkpoints, Zwischenstände
    └── processed/
        └── <DOK>/               Ergebnisbestand je Dokument
```

03 hat kein eigenes Modul. Der gesamte Code liegt im Notebook.

### 5.2 Dateien je Teil: Lesen und Schreiben

| Teil | Liest | Schreibt | Verändert in-place |
|---|---|---|---|
| 01 | `data/raw/<DOK>.pdf` | `interim/befunde/…`, `interim/ausschnitte/…`, `processed/<DOK>/<DOK>.md`, `<DOK>.json`, `<DOK>_artifacts/` | – |
| 02 | `processed/<DOK>/<DOK>.md` | `<DOK>_korr.md`, `<DOK>_review.md`, Manifest, `interim/lektorat/<DOK>/…` | – |
| 03 | `<DOK>.md` (oder `MARKDOWN_OVERRIDE`), `<DOK>.json`, `<DOK>_artifacts/` | `<DOK>.image-optimization.json/.csv` | Bilder in `<DOK>_artifacts/`, Bildreferenzen im Markdown, Bildangaben im JSON |
| manuell | Ergebnis von 02/03 | `<DOK>_final.md` (Konvention, derzeit manuell) | – |

### 5.3 Rolle der Formate

| Datei | Rolle |
|---|---|
| `<DOK>_final.md` bzw. das Lektoratsergebnis | **maßgebliches Dokument**, wird nachbearbeitet |
| `<DOK>.md` | unkorrigiertes Ergebnis von 01 |
| `<DOK>.json` (DoclingDocument) | **nur Backup-Format**, wird nicht weiterverwendet |
| `<DOK>_review.md` | Prüfbericht des Lektorats für Menschen |
| `<DOK>.image-optimization.*` | Audit der Bildoptimierung |
| Bilddateien | tragen eigene Herkunftsdaten als XMP (siehe [5.5](#55-bilddateien-und-xmp)) |

### 5.4 Markdown-Ist-Format

Die folgenden Konventionen wurden am Beispieldokument `FachkundeMechatronik_I4-0_final.md` festgestellt. Sie beschreiben den Ist-Zustand und sind keine Norm.

**Seitenumbruchmarker**

```markdown
<!-- Seitenumbruch -->
```

- Der Marker steht auf einer eigenen Zeile mit Leerzeilen davor und danach.
- Er enthält **keine Seitennummer**.
- Vor der ersten Seite steht kein Marker. Ein Dokument mit *n* Seiten enthält also *n − 1* Marker. Die Seite *k* (1-basiert) ist der Text nach dem (*k − 1*)-ten Marker.
- Das Lektorat schützt die Marker vor Veränderung und Verschiebung.

**Bildreferenzen**

```markdown
![Image](<DOK>_artifacts/<DOK>_<SSSS>_<BB>_image.<ext>)
```

- `<SSSS>` ist der **0-basierte** Seitenindex, vierstellig (`0003` = vierte Seite).
- `<BB>` ist die Block-Kennung des Bildes auf dieser Seite.
- `<ext>` ist `png` oder `jpg`, je nach Formatwahl in 03.
- Der Alt-Text lautet nach 01 `Image`. 03 kann ihn laut Konzept durch einen generierten Alt-Text ersetzen.
- Das Lektorat schützt Bildreferenzen und ihre Reihenfolge.

**Weitere Elemente**

| Element | Ist-Darstellung |
|---|---|
| Überschriften | `##` bis `####`, Ebene aus der Gliederungsnummer hergeleitet, ersatzweise eine Ebene unter der zuletzt gesehenen |
| Bildunterschriften | gewöhnlicher Absatz (`Bild 1: …`), vor oder nach dem Bild |
| Fußnoten | gewöhnliche Absätze am Seitenende, vor dem Seitenmarker |
| Formeln, Hochstellungen | Inline-LaTeX `\( … \)` |
| Tabellen | aus OTSL geparst; nicht lesbare Tabellen bleiben als Text erhalten |
| Kopf-/Fußzeilen, gedruckte Seitenzahlen | nicht im Markdown enthalten (Content-Layer FURNITURE) |

### 5.5 Bilddateien und XMP

- **Auflösung:** höchstens 144 ppi, berechnet aus der Bounding Box in PDF-Punkten (`px = pt × 2`). Hochskaliert wird nie.
- **Formate:** JPEG (Qualitätsstufen 85/75/65/55/45) für fotoartige Inhalte. PNG (Truecolor, Graustufen, bilevel, Palette) für Grafiken, Screenshots und Strichzeichnungen. Farbige Grafiken erhalten mindestens 16 Palettenfarben.
- **Auswahl:** Gewählt wird der kleinste Kandidat in der besten erreichten Qualitätszone (`preferred` vor `minimum`). Bewertet werden SSIM, Edge F1, Component Retention und CIEDE2000 (`deltae_mean`, `deltae_p95`).
- **XMP-Standardfelder:** `dc:title`, `dc:description`, `dc:subject`, `dc:language`, `Iptc4xmpCore:AltTextAccessibility`, `Iptc4xmpCore:ExtDescrAccessibility`.
- **Eigener Namespace** `urn:docrag:metadata:1.0` mit Herkunftsdaten, darunter `sourceDocument`, `sourcePage` (**1-basiert**), `sourceBBox`, `sourceCoordOrigin`, `sourceDpi`, `sourceCaption`, `sectionHeading`, `optimizedWidth/Height`, `maxPpi`, `technicalClass`, `descriptionModel`.

Dasselbe Bild trägt seinen Seitenbezug also zweimal: 0-basiert im Dateinamen und 1-basiert im XMP-Feld `sourcePage`.

### 5.6 Modelle und LM Studio

| Teil | Modell | Aufgabe | Endpunkt (Standard) | Thinking |
|---|---|---|---|---|
| 01 | PP-DocLayoutV3 (ONNX-Export mit Rohköpfen, 25 Klassen, 300 Queries, Apache 2.0) | Layout-Erkennung | lokal, ohne Server | – |
| 01 | PaddleOCR-VL 1.5 | Texterkennung je Block | `http://localhost:1234/v1` | OFF |
| 02 | Gemma (lokal) | Lektorat | `http://localhost:1234/v1` | OFF (notwendig) |
| 03 | Gemma 4 12B (optional) | semantische Bildmetadaten | im Notebook fest: `http://192.168.178.27:1234/v1` | nicht dokumentiert |

Für alle Sprachmodellaufrufe gilt Temperatur 0. PaddleOCR-VL erhält keine freien Anweisungen, sondern je Blockklasse ein festes Präfix (`OCR:`, `Formula Recognition:`, `Table Recognition:`, `Chart Recognition:`, `Seal Recognition:`) und einen festen Token-Deckel.

### 5.7 Abhängigkeiten

| Paket | 01 | 02 | 03 |
|---|:-:|:-:|:-:|
| `pydantic` | ● | ● | |
| `numpy` | ● | | ● |
| `opencv-python` | ● | | ● |
| `pymupdf` | ● | | |
| `onnxruntime` | ● | | |
| `requests` | ● | | |
| `docling-core` | ● | | |
| `markdown-it-py` | | ● | |
| `openai` | | ● | |
| `pandas` | | | ● |
| `Pillow` | ○ | | ● |
| `scikit-image` | | | ● |
| `pngquant` (Programm) | | | ○ |

● erforderlich · ○ optional. Ein Lockfile existiert nicht. In 01 werden schwere Abhängigkeiten erst bei Bedarf importiert.

### 5.8 Wiederaufnahme im Vergleich

| | 01 | 02 | 03 |
|---|---|---|---|
| Einheit | Seite | Chunk je Pass | – |
| Zustand in | `interim/befunde/` (Feld `stufe` im Befund) | `interim/lektorat/` (Checkpoint mit Hashes) | – |
| Atomar | `.json.teil` → umbenennen | ja, nach jedem Chunk | temporäre Datei → `os.replace()` |
| Idempotent | ja | ja, bei konsistentem Checkpoint | nein |

### 5.9 Namensregelwerk (Eingang)

Geprüft wird vor jeder Verarbeitung, für den ganzen Bestand in einem Durchgang:

- Zeichenvorrat `A–Z a–z 0–9 - _`, erstes Zeichen Buchstabe oder Ziffer
- Stammlänge höchstens 48 Zeichen (hergeleitet aus der Windows-Pfadgrenze von 260 Zeichen beim längsten abgeleiteten Pfad)
- keine unter Windows reservierten Namen
- keine Kollision, die nur auf Groß-/Kleinschreibung beruht

Hinzu kommt eine technische Öffnungsprüfung (Verschlüsselung, leer, nicht öffnbar). Bei jeder Beanstandung hält der Lauf an, bevor irgendetwas angelegt wird.

### 5.10 Fehlerverhalten im Vergleich

| Situation | Verhalten |
|---|---|
| Beanstandete Quelldatei (01) | Abbruch vor jeder Verarbeitung, alle Beanstandungen gemeinsam |
| Gescheiterte Seite (01) | Platzhalter-Befund mit Fehlertext. Die Seite bleibt offen und wird im nächsten Lauf erneut versucht. Das Dokument wird im Gesamtlauf übersprungen. |
| Unvollständige Modellausgabe (01, Stufe 2) | wird vermerkt, nicht verworfen (Token-Deckel, fehlende OTSL-Marken, leere Antwort) |
| Ungültiges JSON oder Schemafehler der ganzen Antwort (02) | kein Retry, der Chunk bleibt uncommitted |
| Einzelner ungültiger Vorschlag (02) | wird als `invalid` protokolliert, der Chunk läuft weiter |
| Transienter LM-Studio-Fehler (02) | automatischer Retry (`retry_count`) |
| Fehlende Eingabedatei, Validierung scheitert (03) | Abbruch |
| LLM nicht erreichbar (03) | Optimierung läuft weiter, Metadatenstatus `SEMANTIC_METADATA_PENDING` |

### 5.11 Lektorat: Passes und Entscheidungsregel

- Passes: `text` → `table` → `structure` → `caption`, jeweils blockweise.
- Das Modell liefert strukturierte Änderungsvorschläge mit Konfidenz. Python validiert und entscheidet: Hohe Konfidenz wird angewendet, mittlere zur Prüfung markiert, niedrige verworfen. `unresolved` ist ein eigener Zustand.
- Nach Änderungen werden Markdown-Struktur, Code-Fences, Tabellen und geschützte Elemente geprüft. Ungültige Kandidaten werden nicht übernommen.

### 5.12 Tests

Die Tests liegen gemeinsam unter `tests/` und werden mit `python -m pytest` ausgeführt. Sie verwenden dieselbe installationsfreie Importstrategie wie die Notebooks. 03 wurde an einem realen Bildkorpus kalibriert, automatisierte Tests sind für 03 nicht dokumentiert.

### 5.13 Gemeinsame Entwicklungsregeln

Diese Regeln finden sich übereinstimmend in den READMEs:

1. Infrastruktur und fachliche Logik nicht gleichzeitig umbauen, in kleinen, getrennten Changesets arbeiten.
2. Deterministische Schritte und Sprachmodellaufrufe nicht mischen.
3. Nach Änderungen an Python-Dateien den Jupyter-Kernel neu starten.
4. Bei Änderungen der Ordnerstruktur gemeinsam prüfen: Notebook-Startort, `sys.path`, Datenpfade, Skill-Pfade, Tests sowie Markdown, JSON und Artefaktordner.
5. Weitere funktionale Änderungen erst, wenn ein konkreter Fehler oder ein reproduzierbares Qualitätsproblem beobachtet wurde.

---

## 6. Entscheidungsprotokoll

Das Protokoll folgt dem Muster der Architecture Decision Records: Kontext, Entscheidung, Konsequenzen und Status. Abgelöste Entscheidungen bleiben stehen und werden als abgelöst markiert, damit die Entstehungsgeschichte nachvollziehbar bleibt.

### E-01 Bildebene als einzige Quelle

- **Kontext:** Die Qualität eingehender PDFs ist nicht vorhersagbar (siehe [2.1](#21-pdfs-sind-nicht-deterministisch-lesbar)).
- **Entscheidung:** Jede Seite wird als Bild behandelt und per Layout-Erkennung und OCR gelesen. Die PDF-Textebene wird weder genutzt noch zum Abgleich verwendet. Gebaut wird für den ungünstigsten Fall.
- **Konsequenzen:** Die Pipeline ist robust gegen alle bekannten Fälle. OCR-Fehler sind unvermeidbar und machen das Lektorat nötig.
- **Status:** angenommen

### E-02 Layout-Erkennung mit PP-DocLayoutV3 als ONNX-Export mit Rohköpfen

- **Kontext:** Die Lesereihenfolge und die Masken werden als Rohdaten gebraucht.
- **Entscheidung:** Verwendet wird der Export `phungpx/PP-DocLayoutV3-ONNX` (mit `order_logits`, `out_masks`), nicht der Export mit eingebautem Postprocess.
- **Konsequenzen:** Das Dekodieren liegt im eigenen Code. Ein Export mit eingebautem Postprocess scheitert bewusst schon im Konstruktor.
- **Status:** angenommen

### E-03 Texterkennung mit PaddleOCR-VL 1.5

- **Kontext:** Das Modell muss unter Windows (GGUF) und macOS (MLX) in LM Studio laufen.
- **Entscheidung:** Version 1.5, weil nur für sie eine MLX-Variante existiert.
- **Status:** angenommen

### E-04 Das Markdown ist maßgeblich, das JSON nur Backup

- **Kontext:** Das Ergebnis muss von Menschen nachbearbeitet werden und portabel sein.
- **Entscheidung:** Maßgeblich ist das Markdown-Dokument. Das DoclingDocument (JSON) wird nur noch als Backup aufbewahrt.
- **Konsequenzen:** Korrekturen aus Lektorat und Nachbearbeitung existieren nur im Markdown. Das JSON bleibt auf dem Stand der Extraktion.
- **Status:** angenommen (10.09.2026). Löst ab: *„DoclingDocument ist das kanonische Zielformat, Markdown wird daraus abgeleitet“* (07.09.2026).

### E-05 Seitengrenzen werden nie aufgehoben

- **Kontext:** Jede Aussage muss einer Originalseite zurechenbar bleiben.
- **Entscheidung:** Keine Absätze über Seitengrenzen hinweg, keine Rückführung von Inline-Formeln in den Satz über Seiten hinweg. Die Seitenzuordnung steht als Marker im Markdown.
- **Konsequenzen:** Über eine Seite getrennte Wörter und Sätze bleiben getrennt.
- **Status:** angenommen

### E-06 Feste Reihenfolge 01 → 02 → 03

- **Entscheidung:** Das Lektorat läuft vor der Bildoptimierung.
- **Konsequenzen:** 03 muss seine Formatwechsel in das Lektoratsergebnis übertragen. Das geschieht derzeit nicht zuverlässig, siehe [A-01](#a-01-formatwechsel-der-bilder-erreicht-die-endfassung-nicht).
- **Status:** angenommen

### E-07 Stufen 3 und 4b entfallen

- **Kontext:** In 01 waren eine Stufe 3 und eine Stufe 4b (Zuordnung von Bildunterschriften durch ein Bildmodell) vorgesehen.
- **Entscheidung:** Beide sind Planungs- und Implementierungsartefakte ohne Funktion in der Pipeline.
- **Status:** abgelöst bzw. entfallen

### E-08 Bildoptimierung auf 144 ppi, in-place

- **Entscheidung:** Portabilität geht vor maximaler Bildqualität. Die Bilder werden direkt im Artefaktordner ersetzt, eine zusätzliche Kopie (`_optimized_document`) gibt es nicht.
- **Konsequenzen:** 03 ist nicht idempotent. Ein Neustart setzt voraus, dass 01 die Artefakte neu erzeugt.
- **Status:** angenommen

### E-09 Temperatur 0, Thinking OFF

- **Kontext:** Mit aktiviertem Thinking hat das Modell im Lektorat das Token-Budget verbraucht, bevor eine strukturierte Antwort entstand.
- **Entscheidung:** Alle Sprachmodellaufrufe laufen mit Temperatur 0 und ohne Thinking.
- **Status:** angenommen

### E-10 Eingangsdateinamen prüfen, nicht umschreiben

- **Entscheidung:** Unzulässige Namen werden mit einem Ersatzvorschlag abgelehnt. Jedes Dokument erhält einen eigenen Ausgabeordner.
- **Status:** angenommen (07.09.2026)

### E-11 Installationsfreie Module, Notebooks als Einstieg

- **Kontext:** Die Pipeline wird auch in der Lehre eingesetzt. Anleitungen zur Konfiguration von Entwicklungsumgebungen sollen vermieden werden.
- **Entscheidung:** Die Notebooks sind der Einstiegspunkt. Die Module werden per `sys.path` geladen, ohne `pip install -e .` und ohne `pyproject.toml`.
- **Status:** angenommen

---

## Anhang A – Offene Punkte (To-do)

Die folgenden Punkte beschreiben beobachtete Fehler, Lücken und Unstimmigkeiten. **Sie sind nicht umgesetzt.** Sie dienen als Ausgangspunkt für spätere, jeweils einzeln zu entscheidende Schritte.

### Fehler

#### A-01 Formatwechsel der Bilder erreicht die Endfassung nicht

- **Beobachtung:** In der Endfassung sind einige Bilder nicht eingebunden. 03 hat die Datei von `.png` auf `.jpg` umgestellt, die Referenz im maßgeblichen Markdown zeigt aber weiter auf `.png`. Da 03 die alte Datei nach dem Formatwechsel löscht, zeigt die Referenz ins Leere.
- **Zusammenhang:** 03 aktualisiert laut README `<DOK>.md` bzw. die über `MARKDOWN_OVERRIDE` gesetzte Datei. Wie das Lektoratsergebnis `<DOK>_korr.md` an 03 übergeben wird, ist nicht festgelegt.

#### A-02 Generierte Alt-Texte fehlen in der Endfassung

- **Beobachtung:** Im Beispieldokument lauten alle Bildreferenzen `![Image](…)`, obwohl die Bilder bereits generierte Alt-Texte im XMP tragen. Wahrscheinlich gleiche Ursache wie A-01.

### Seitenzurechenbarkeit

#### A-03 Seitenmarker ohne Seitennummer

- **Beobachtung:** `<!-- Seitenumbruch -->` trägt keine Nummer. Die Seite ergibt sich nur durch Zählen, und ein gelöschter oder doppelter Marker bei der Nachbearbeitung verschiebt alle folgenden Seiten.
- **Recherchehinweis:** Für genau diesen Fall gibt es einen etablierten Standard, die W3C-Rolle `doc-pagebreak` aus DPUB-ARIA. Die Seitennummer steht dort im `aria-label` oder im Elementinhalt, die Markierung ist in EPUB und ONIX als „Print-equivalent page numbering“ etabliert (Quellen in Anhang C). Ob und wie das übernommen wird, ist offen.

#### A-04 Drei Zählweisen für Seiten

- **Beobachtung:** Der Dateiname der Bilder zählt 0-basiert, das XMP-Feld `sourcePage` 1-basiert, und die gedruckten Seitenzahlen des Originals werden gar nicht geführt.

#### A-05 Gedruckte Seitenzahlen fehlen im Markdown

- **Beobachtung:** Kopf- und Fußzeilen samt Seitenzahlen landen in FURNITURE und damit nicht im Markdown. Querverweise wie „Bild 1, Seite 611“ lassen sich im Markdown nicht auflösen. Das wiegt schwer bei Büchern, die ihre Abbildungen seitenweise nummerieren.

#### A-06 Verhalten des Lektorats an Seitengrenzen undokumentiert

- **Beobachtung:** Das Lektorat arbeitet mit `overlap_blocks` und korrigiert unter anderem Worttrennungen. Dokumentiert ist, dass Marker nicht verschoben werden. Ob Korrekturen Text über einen Marker hinweg zusammenziehen dürfen, ist nicht dokumentiert.

### Textqualität

Die folgenden Beobachtungen stammen aus dem Beispieldokument.

#### A-07 Doppelte oder zerrissene Textpassagen um Abbildungen

- **Beispiele:** Auf Seite 1 steht „So- mit können intelligente Wortwahl“, danach erneut „mit können …“. Auf Seite 5 erscheint der Absatz ab „…waltungsschalen zusammengefasst“ zweimal.
- **Vermutete Ursache:** Zusammensetzung bzw. Lesereihenfolge in 01, nicht OCR.

#### A-08 Verbliebene Wort- und Zeichenfehler

- **Beispiele:** „loTS“ statt „IoTS“, „Einsatz-eins-Beziehung“, „Zur Verletzung von Assets“ (gemeint: Vernetzung), „einen Komponentenmanager sowie einen Komponentenmanager“.

#### A-09 Markdown-Syntax nicht normalisiert

- **Beispiele:** Aufzählungen als `■`/`☐` statt als Listensyntax, gemischte Fußnotennotation (`\(^{1)}\)`, `¹)`, `1)`), Unterstreichungen als `\(\underline{\text{…}}\)`.

#### A-10 Diagrammtext als Fließtext

- **Beobachtung:** Beschriftungen aus Diagrammen erscheinen als Textzeilen im Markdown, z. B. „Ebene 3 • Algorithmen …“.

### Konventionen und Betrieb

#### A-11 Endfassung wird manuell benannt

- **Beobachtung:** `<DOK>_final.md` entsteht durch manuelle Umbenennung. Keine Stufe erzeugt diese Datei.
- **Hinweis:** Das Suffix `_korr` weicht vom früher geplanten Suffix `_k` ab.

#### A-12 Ablageort der Lektoratsergebnisse nicht dokumentiert

- **Beobachtung:** Das README von 02 nennt nur die Dateinamen `_korr.md`/`_review.md`, nicht den Ordner.

#### A-13 Uneinheitliche Importstrategie

- **Beobachtung:** 01 legt `python/pdf_extraction/` auf `sys.path`, 02 den Ordner `python/`, 03 enthält keinen Modulcode. Beide READMEs beschreiben ein `tests/conftest.py` mit unterschiedlichem Pfad.

#### A-14 Festverdrahteter Endpunkt in 03

- **Beobachtung:** In 03 steht eine LAN-IP statt `localhost` fest im Notebook. Die Einstellung Thinking OFF ist für 03 nicht dokumentiert.

#### A-15 03 nicht idempotent

- **Beobachtung:** 03 arbeitet in-place, wiederholte Läufe rekodieren verlustbehaftete JPEGs erneut, und es gibt kein Resume.

#### A-16 Namespace `urn:docrag` als Altlast

- **Beobachtung:** Der Namespace stammt aus der verworfenen RAG-Ausrichtung. Das README von 03 empfiehlt selbst, ihn später durch einen Namespace unter eigener Kontrolle zu ersetzen.

#### A-17 JSON-Pflege ohne Nutzen

- **Beobachtung:** 03 aktualisiert weiterhin das JSON, obwohl es nur Backup ist. Das Lektorat korrigiert das JSON nicht, sodass JSON und Markdown inhaltlich auseinanderlaufen.

#### A-18 Veraltete Aussagen in den Teil-READMEs

- **Beobachtung:** Das README von 01 nennt das DoclingDocument als kanonisches Format, erwähnt Stufe 4b und bezeichnet sich als „einzigen Einstiegspunkt“. Diese Aussagen widersprechen E-04 und E-07.

#### A-19 Marginalien im Markdown ungeprüft

- **Beobachtung:** Marginalien werden dem Content-Layer NOTES zugeordnet. Ob sie im Markdown erscheinen, ist nicht dokumentiert.

#### A-20 Keine automatisierten Tests für 03

- **Beobachtung:** 03 wurde am Korpus kalibriert, ein Testordner für 03 ist nicht beschrieben.

---

## Anhang B – Glossar

| Begriff | Bedeutung |
|---|---|
| **Befund / SeitenBefund** | Arbeitsformat von 01, eine Datei je Seite. Es wächst von Stufe zu Stufe (Layout → Text). |
| **Strom** | Lesestrom eines Blocks: `haupt`, `marginalie`, `boilerplate`, `apparat` |
| **Content-Layer** | docling-Ebene: BODY (haupt, apparat), NOTES (marginalie), FURNITURE (boilerplate) |
| **OTSL** | Tabellenauszeichnung, die PaddleOCR-VL ausgibt und 01 parst |
| **Chunk / Pass** | Verarbeitungseinheit bzw. Durchgang im Lektorat |
| **Quality Gate** | Mindestanforderung an einen Bildkandidaten (SSIM, Edge F1, Component Retention, ΔE) |
| **XMP** | in die Bilddatei eingebettete Metadaten |
| **Folio** | gedruckte Seitenzahl des Originals, im Unterschied zum PDF-Seitenindex |

---

## Anhang C – Quellen

**Projektinterne Quellen**

- README PDF-Extraktion (Teil 01)
- README Markdown-Lektorat (Teil 02)
- README Bildoptimierung (Teil 03)
- Beispieldokument `FachkundeMechatronik_I4-0_final.md` mit Bildartefakten (Stand 10.09.2026)

**Externe Quellen (Recherchestand September 2026)**

- W3C: Digital Publishing WAI-ARIA Module 1.1, Rolle `doc-pagebreak` – https://www.w3.org/TR/dpub-aria-1.1/
- DAISY Accessible Publishing Knowledge Base: `doc-pagebreak` – https://kb.daisy.org/publishing/docs/html/dpub-aria/doc-pagebreak.html
- DAISY Knowledge Base: `pageBreakMarkers` (ONIX-Zuordnung) – https://kb.daisy.org/publishing/docs/metadata/schema.org/accessibilityFeature/pageBreakMarkers.html
- docling: Seitenumbruch-Platzhalter beim Markdown-Export – https://github.com/docling-project/docling/discussions/3173
- Diátaxis (Dokumentationsschema) – https://diataxis.fr/
- Architecture Decision Records (Nygard-Format) – https://adr.github.io/
