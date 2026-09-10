# PDF-Extraktion

## Zweck

`01_pdf_extraction.ipynb` ist der einzige Einstiegspunkt der Dokumentenaufbereitung. Die Pipeline überführt Scan-PDFs in ein kanonisches, durchsuchbares Dokumentformat (DoclingDocument als JSON und Markdown) – seitenweise, deterministisch prüfbar, mit getrennten Stufen für Layout, Texterkennung und Kanonisierung.

Ausgangspunkt ist ein Eingangsbestand unter:

```text
data/raw/<DOKUMENT>.pdf
```

Der Lauf erzeugt je Dokument:

```text
data/processed/<DOKUMENT>/
├── <DOKUMENT>.md
├── <DOKUMENT>.json
└── <DOKUMENT>_artifacts/
```

Grundprinzipien:

- Eine Seite, ein Befund, eine Datei – Seitengrenzen werden nirgends aufgehoben
- Stufenweise Verarbeitung: erst alle Seiten durch Stufe 1, dann alle durch Stufe 2
- Layout-Erkennung deterministisch (ONNX), Texterkennung lokal über ein Vision-Modell
- Pfadbildung nur in einem einzigen Modul (`pfade.py`), nie im Notebook oder in einzelnen Modulen
- Alle Zwischenergebnisse atomar geschrieben (`.json.teil`, dann umbenennen)
- Wiederaufsetzen auf Seitenebene: fertige Seiten werden übersprungen, gescheiterte erneut versucht
- Kanonische Stufe ohne Sprachmodell – der prüfbare Teil bleibt prüfbar

---

## Projektstruktur

Die App wird installationsfrei aus dem Projektordner geladen.

```text
projekt/
├── 01_pdf_extraction.ipynb
├── python/
│   └── pdf_extraction/
│       ├── pfade.py
│       ├── schema.py
│       ├── layout.py
│       ├── erkennung.py
│       ├── stapel.py
│       ├── lauf.py
│       ├── kanonisch.py
│       └── sichtung.py
├── models/
│   ├── pp_doclayoutv3.onnx
│   ├── labels.json
│   └── README.md
├── data/
│   ├── raw/
│   ├── interim/
│   │   ├── befunde/
│   │   ├── ausschnitte/
│   │   ├── kontrolle/
│   │   └── lektorat/
│   └── processed/
└── tests/
```

Das Notebook fügt den Ordner `python/pdf_extraction/` beim Start zu `sys.path` hinzu. Für die eigenen Projektmodule ist deshalb kein `pip install -e .` und kein `pyproject.toml` erforderlich.

Alle Pfade werden in `pfade.py` gebildet. Kein anderes Modul und kein Notebook trägt ein Verzeichnisliteral – wer einen neuen Ort braucht, erweitert dieses Modul statt die Regel zu umgehen.

---

## Voraussetzungen

Erforderlich sind:

- Python 3.12 oder kompatibel
- Jupyter
- `pymupdf`
- `pydantic`
- `numpy`
- `opencv-python`
- `onnxruntime`
- `requests`
- `docling-core`

Optional:

- `Pillow` für echte Pixelmaße der kopierten Ausschnitte (sonst Schätzung aus der Bounding Box)
- LM Studio mit geladenem Vision-Modell
- PaddleOCR-VL als aktuelles Zielmodell

Die Installation erfolgt über die bestehende Umgebung; ein Abhängigkeits-Lockfile existiert nicht. Die schweren Abhängigkeiten (`onnxruntime`, `requests`, `docling-core`) werden erst beim tatsächlichen Bedarf importiert – ein reiner Stufe-1-Lauf braucht weder LM Studio noch docling-core.

---

## Verwendung

### 1. LM Studio starten

Falls Text erkannt werden soll (Stufe 2 und darüber hinaus):

- PaddleOCR-VL oder ein kompatibles Vision-Modell laden
- lokalen Server starten
- Thinking deaktivieren

Standardmäßig erwartet die Konfiguration:

```text
http://localhost:1234/v1
```

Die beiden schweren Modelle laufen bewusst nie gleichzeitig: der Lauf ist stufenweise, die ONNX-Sitzung und das Sprachmodell werden nacheinander geladen.

Stufe 1 allein kostet Sekunden pro Seite und braucht LM Studio überhaupt nicht.

### 2. Notebook öffnen

```text
01_pdf_extraction.ipynb
```

Das Notebook liegt im Projekt-Root und bestimmt den Projekt-Root selbst; relative Pfade werden gegen das Arbeitsverzeichnis aufgelöst. Die Startzelle prüft die Umgebung und meldet ein falsches Arbeitsverzeichnis, statt es zu kaschieren.

### 3. Dokument auswählen

Das Notebook sucht PDFs unter:

```text
data/raw/
```

Der Name wird über die Zellvariable `BUCH` gesetzt. Die Erfassung läuft ohne Rekursion – ein Unterordner unter `raw/` ist kein Quelldokument, sondern ein Versehen.

### 4. Lauf starten

Der zentrale Einstiegspunkt für den ganzen Bestand ist:

```python
bericht = lauf.verarbeite_alle(erkenner=ERKENNER)
```

Für die genaue Kontrolle eines einzelnen Buchs:

```python
lauf_einzelbuch = stapel.verarbeite_buch(PDF, buch=BUCH, bis=Stufe.LAYOUT, ...)
```

`bis` sagt, wie weit gelaufen wird:

```text
Stufe.LAYOUT    # nur Layout-Erkennung, kein LM Studio
Stufe.ERKANNT   # Text gefüllt, Bildausschnitte abgelegt
Stufe.KANONISCH # ins DoclingDocument überführt, JSON und Markdown erzeugt
```

---

## Verarbeitung

Die Verarbeitung erfolgt in Stufen:

```text
Erfassen und Prüfen des ganzen Bestands
  ├── Namensregelwerk über alle Quelldateien
  └── technische Öffnungsprüfung (Verschlüsselung, Seitenzahl)

Stufe 1 — Layout-Erkennung (alle Seiten)
  Seite rendern (200 dpi)
  auf 800x800 verkleinern, vorverarbeiten
  ONNX-Inferenz (PP-DocLayoutV3)
  dekodieren: Boxen, Klassen, Lesereihenfolge, Polygone
  SeitenBefund atomar ablegen

Stufe 2 — Texterkennung (alle Seiten)
  benachbarte Textblöcke zusammenführen (Union-Find)
  Ausschnitte mit proportionalem Rand bei 300 dpi schneiden
  je Klasse einen der festen PaddleOCR-VL-Prompts schicken
  Bildblöcke ohne Modellaufruf als PNG ablegen
  Ausgabe nachbereiten (Formel-Delimiter, OTSL-Marken)

Stufe 4a — Kanonisierung (je Dokument, ohne LLM)
  Blöcke entdoppeln
  Bildunterschriften zuordnen (nur der erzwungene Fall)
  Überschriftenebenen fortlaufend herleiten
  Tabellen aus OTSL parsen, Diagrammdatenreihen zerlegen
  Bildausschnitte nach processed/ kopieren
  DoclingDocument erzeugen und als JSON + Markdown ablegen
```

### Arbeitsformat

Das Arbeitsformat ist `SeitenBefund` (in `schema.py`). Es wächst von Stufe zu Stufe, statt in verschiedene Typen zu zerfallen:

```text
Stufe 1 (LAYOUT):   Blöcke verortet, typisiert, geordnet. Kein Text.
Stufe 2 (ERKANNT):  Feld `text` gefüllt.
Stufe 4 (KANONISCH): ins DoclingDocument überführt.
```

Welchen Stand eine Datei hat, sagt das Feld `stufe` im Umschlag – nicht der Dateiname. Stufe 2 überschreibt die Datei der Stufe 1, weil sie eine echte Obermenge ist.

Das Schema ist bewusst frei von schweren Abhängigkeiten: kein onnxruntime, kein cv2, kein docling. Es beschreibt, was beobachtet wurde, und weiß nicht, wer es beobachtet hat.

### Koordinaten

Koordinaten ohne Bezugsrahmen sind bedeutungslos. Jede Bounding Box trägt deshalb Pflichtangaben für Rahmen und Ursprung:

```text
modell_800    Rohoutput des Detektors, 800x800 normiert
bild_pixel    gerendertes Seitenbild (je Stufe anderes dpi)
seite_punkt   PDF-Punkte
normiert_1000 Gemma-Vision-Format [y0, x0, y1, x1]
```

Verrechnungen über Rahmengrenzen hinweg werden vom Schema abgelehnt, nicht stillschweigend umgerechnet.

---

## Auflösungsregeln

Die Layout-Analyse rendert bei:

```text
RENDER_DPI = 200
```

Der Modelleingang ist ein festes:

```text
800x800 (RGB, auf [0,1] skaliert, bicubic, keep_ratio=false)
```

Wegen `keep_ratio=false` erfolgt die Rücktransformation der Boxen achsenweise, nicht proportional. Die Texterkennung schneidet Ausschnitte höher aufgelöst:

```text
PROBE_DPI = 300
```

Layout auf der verkleinerten Kopie, Ausschnitte aus dem Original: die Boxen liegen bei `befund.render_dpi`, geschnitten wird bei `dpi`. Der Rand ist proportional zur Boxhöhe und beidseitig gedeckelt (3–16 px), damit ein Fließtextblock unauffällig bleibt und eine 31 px hohe Seitenzahl nicht zum Viertel des Bilds wird.

---

## Layout-Klassen

Der Detektorkopf hat 25 Ausgänge. Die Reihenfolge der Klassenliste ist exakt die der PaddleX-`label_list`; der Index ist die Klassen-ID. Die gröbere `labels.json` des ONNX-Exports (fünf Klassen fallen dort zusammen) dient nur als Gegenprobe, nicht als Dekodierquelle.

Die Klassen werden beim Übergang ins kanonische Format nach docling gemappt. Das Mapping führt ausdrücklich eine Verlustspalte: sie sagt, was das Arbeitsformat weiterhin tragen muss, weil das kanonische Format es nicht kann (etwa die Rolle „Zusammenfassung" oder die Inline-Stelle einer Formel).

### Ströme

Blöcke werden unabhängig von der Seite in vier Leseströme eingeteilt:

```text
haupt        Fließtext, Überschriften, Tabellen, Abbildungen
marginalie   Marginalien – eigener Lesestrom
boilerplate  Kopf- und Fußzeile, Seitenzahlen
apparat      Fußnoten, Referenzen
```

Nur textartige Klassen innerhalb desselben Stroms dürfen waagerecht zusammengeführt werden; eine Tabelle neben einer Tabelle ist nicht eine breitere Tabelle.

### Lesereihenfolge

Die Lesereihenfolge stammt aus der 300x300-Zeigermatrix des Modells, als Rang je Query. Weil `konfidenz` bei sicheren Seiten auf 1.0 sättigt, wird zusätzlich die vorzeichenbehaftete Logit-Marge mitgeführt – nur sie bleibt als Gütemaß brauchbar. Die unsichersten Übergänge sind der billigste Einstieg in die Fehlersuche.

---

## Sicherungsmechanismen

### Namensregelwerk

Quelldateinamen werden geprüft, bevor irgendetwas verarbeitet wird:

- zulässiger Zeichenvorrat (A-Z, a-z, 0-9, -, _)
- erstes Zeichen Buchstabe oder Ziffer
- maximale Stammlänge (48 Zeichen, hergeleitet aus der Windows-Pfadgrenze von 260 Zeichen beim längsten abgeleiteten Pfad)
- keine unter Windows reservierten Namen
- keine Kollision nur durch Groß-/Kleinschreibung über den Bestand hinweg

Beanstandete Namen werden genannt und ein Ersatzname vorgeschlagen, aber nirgends automatisch geändert.

### Eingangsprüfung

Der ganze Bestand wird vor jeder Verarbeitung geprüft – Namensregelwerk und technische Öffnungsprüfung in einem Durchgang. Bei jeder Beanstandung hält der Lauf an, bevor irgendetwas angelegt wird. Keine Prüfung fasst Seiteninhalte an; das leistet Stufe 1 ohnehin, seitenweise und mit Übergehen statt Abbruch.

### Atomare Schreibvorgänge

Befunde werden erst neben die Zieldatei (`.json.teil`) geschrieben, dann umbenannt. Ein Abbruch mitten im Schreiben hinterlässt sonst eine halbe JSON-Datei, die beim Wiederaufsetzen als fertige Seite gälte.

### Dateinamen ohne Pfade

Bildausschnitte werden im Befund als bloßer Dateiname geführt, nie als Pfad. Ein Pfad im Feld wird gemeldet, nicht stillschweigend gekürzt – sonst verschiebt sich der Zwischenbestand lautlos zu leeren Bildverweisen.

---

## Wiederaufsetzen

Der Lauf ist idempotent und setzt auf Seitenebene wieder auf:

```text
Fertige Seiten (Stufe erreicht)  -> übersprungen
Gescheiterte Seiten              -> Fehler beigefügt, im nächsten Lauf erneut versucht
Fertige Dokumente                -> gar nicht erst angerührt
```

Welche Seiten fehlen noch, beantwortet `stapel.offene_seiten`, ohne etwas zu rechnen; für Dokumente gibt es `lauf.offene_dokumente`. Ein Wiederaufsetzen versucht nicht lesbare Dateien und Seiten mit gesetztem `fehler` erneut, statt einen Fehlschlag für alle Zeiten festzuschreiben. `neu=True` erzwingt trotzdem einen vollständigen Lauf.

Für einen bewussten Neustart kann der dokumentbezogene Zwischenordner unter `data/interim/befunde/<DOKUMENT>/` gelöscht werden.

---

## Sichtprüfung

`sichtung.py` liest ausschließlich und beantwortet die Fragen, an denen der Zuschnitt von Stufe 4a hängt, mit Zahlen aus dem eigenen Korpus statt mit Vermutungen:

```bash
python sichtung.py                  # befunde/, alle Bücher
python sichtung.py befunde Buch     # nur ein Buch
```

Abgedeckt sind unter anderem:

- Klassenverteilung und Ströme
- Textformate, Textlängen, leere Antworten
- OTSL wirklich parsebar? (Zeilen x Spalten, misslungene Blöcke)
- Bildblöcke je Seite
- Ineinanderliegende Detektionen (Doppeldetektionen)
- Seiten ohne jede Überschrift
- Seiten ohne Hauptstrom
- Warnungsarten
- Laufzeiten und Modellversionen je Stufe

Die grobe Markdown-Vorschau (`erkennung.als_markdown`) ist die Leseprobe: Lässt sich der Hauptstrom flüssig lesen, stimmen Lesereihenfolge, Zuschnitt und Erkennung zugleich. Die richtige Umwandlung ist Stufe 4a.

---

## Fehlerverhalten

Die Pipeline unterscheidet bewusst drei Fehlerorten.

### Am Eingang: Abbruch

Beanstandete Quelldateien (Name, Endung, Kollision, Verschlüsselung, leer, nicht öffnbar) brechen den Lauf vor der ersten Verarbeitung ab. Nichts wird verarbeitet, alle Beanstandungen erscheinen gemeinsam.

### Je Seite: Übergehen

Eine gescheiterte Seite bekommt einen Platzhalter-Befund mit Herkunft und Fehlertext; der Lauf macht mit den übrigen Seiten weiter. Der Platzhalter gilt als offen – ein späterer Lauf versucht die Seite erneut. Ein Dokument mit gescheiterten Seiten wird im Gesamtlauf vermerkt und übersprungen, die übrigen Dokumente werden trotzdem verarbeitet.

### In Stufe 2: Vermerken statt Wegwerfen

Unvollständige oder unstrukturierte Modellausgaben werden nicht verworfen, sondern im Befund vermerkt (Token-Deckel erreicht, Tabelle ohne OTSL-Marken, Formel ohne Delimiter, leere Antwort). Nicht lesbare OTSL-Tabellen werden als Text erhalten und die Seite als prüfbedürftig gekennzeichnet – erhalten, nicht wegwerfen.

Nicht-kritisch ist das Fehlen des Maskenkopfs: Polygone fallen auf die Bounding Box zurück, der Lauf bleibt gültig.

---

## Konfiguration

Wichtige Einstellungen befinden sich direkt im Notebook.

### Dokument

```python
BUCH = None
LMS = "http://localhost:1234/v1"
```

### Auflösung und Schwelle

```python
RENDER_DPI = 200     # layout.py, Standard für die Layout-Analyse
PROBE_DPI = 300      # erkennung.py, Ausschnitte höher auflösen
SCHWELLE = 0.5       # Detektionsschwelle, standardmäßig im Stufenlauf
```

### Modell

```python
ONNX_STANDARD = models/pp_doclayoutv3.onnx
```

Das Modell ist der ONNX-Export von PaddlePaddle/PP-DocLayoutV3 (DETR-artig, 300 Queries, 25 Klassen, Apache 2.0). Ein Export mit eingebackenem Postprocess scheitert bewusst schon im Konstruktor, nicht erst mitten im Stapellauf.

### Prompts und Token-Deckel

PaddleOCR-VL nimmt keine freien Anweisungen entgegen – eines von sechs festen Präfixen je Klasse:

```python
"OCR:", "Formula Recognition:", "Table Recognition:",
"Chart Recognition:", "Seal Recognition:"
```

Je Klasse existiert ein fester Token-Deckel, damit eine Seitenzahl, die plötzlich 1024 Tokens erzeugt, auffällt, statt stumm in den Lauf zu rutschen:

```python
"number": 64, "header": 256, "table": 4096, "text": 2048, ...
```

---

## Architektur

Die wichtigsten Module haben folgende Aufgaben:

| Modul | Aufgabe |
|---|---|
| `pfade.py` | einzige Stelle, die Pfade und Namensregeln bildet |
| `schema.py` | Arbeitsformat: Koordinaten, Klassen, Ströme, Befunde, Ablage |
| `layout.py` | Stufe 1: PDF-Seite -> verortete, typisierte Blöcke |
| `erkennung.py` | Stufe 2: Blöcke zusammenführen, Ausschnitte schneiden, Text füllen |
| `stapel.py` | stufenweise Verarbeitung eines Dokuments mit Wiederaufsetzen |
| `lauf.py` | Erfassung, Eingangsprüfung, Dokumentenlauf über den ganzen Bestand |
| `kanonisch.py` | Stufe 4a: Übergang ins kanonische DoclingDocument |
| `sichtung.py` | read-only Analyse des Zwischenbestands |
| `Detektor` | gekapselte ONNX-Sitzung, einmal öffnen, beliebig oft aufrufen |
| `Erkenner` | Zugang zu PaddleOCR-VL über LM Studio |

Die Architektur trennt bewusst:

- Beobachtung (Arbeitsformat, mit Widersprüchen) von Entscheidung (kanonisches Format: eine Region, ein Label, ein Text)
- deterministische Schritte (Layout, Kanonisierung) von Sprachmodellaufrufen (Texterkennung)
- Zwischenbestand (`interim/`) von Ergebnisbestand (`processed/`)

Entscheidungen, die in Stufe 4a gefallen sind und anderswo anders ausfallen könnten:

- Ströme -> ContentLayer: haupt und apparat nach BODY, marginalie nach NOTES, boilerplate nach FURNITURE
- Überschriftenebene aus der Gliederungsnummer, ersatzweise eine Ebene unter der zuletzt gesehenen
- Entdoppelt wird nur bei identischem Label; gemischte Überlappungen bleiben stehen, weil dort beide Detektionen etwas Eigenes aussagen
- Bildunterschriften werden nur zugeordnet, wenn genau ein Objekt und genau eine Unterschrift auf der Seite stehen – alles andere bleibt offen und gehört nach 4b, vor ein Bildmodell

Bewusst nicht umgesetzt: Absätze über Seitengrenzen hinweg und Inline-Formeln zurück in den Satz. Seitengrenzen werden nirgends aufgehoben, damit jede Aussage einer Seite zurechenbar bleibt.

---

## Tests

Die Tests liegen unter `tests/` und verwenden dieselbe installationsfreie Importstrategie wie das Notebook: `tests/conftest.py` fügt den Ordner `python/pdf_extraction/` zu `sys.path` hinzu. Ausführen:

```bash
python -m pytest
```

---

## Entwicklungshinweise

Für Änderungen am Projekt gilt:

1. Pfade nur in `pfade.py` bilden – die Regel ist Teil der Architektur
2. das Arbeitsformat wächst von Stufe zu Stufe; keine verschiedenen Typen je Stufe einführen
3. Koordinaten nie ohne Bezugsrahmen weitergeben
4. schwere Abhängigkeiten erst bei Bedarf importieren; das Modul muss ohne sie einlesbar bleiben
5. deterministische Schritte (4a) und Sprachmodellaufrufe (4b) nicht mischen
6. seitengrenzenüberschreitende Logik nur mit Rückkehr zur Seitenzurechenbarkeit einführen
7. bei Änderungen der Klassenabbildung den Selbsttest in `schema.selbsttest_docling()` laufen lassen
8. `save_as_json` und `export_to_markdown` nur mit `PLACEHOLDER` bzw. `REFERENCED` aufrufen – die Bibliothek bettet sonst jedes Bild als base64 ins JSON
9. nach Änderungen an Python-Dateien den Jupyter-Kernel neu starten (autoreload wirkt auf Modulebene, nicht auf Klasseninstanzen)
10. für Massenläufe beachten: Lossy-Rekognition läuft über LM Studio; Temperatur 0 ist Pflicht, sonst lässt sich die Ausgabe weder prüfen noch messen

---

## Aktueller Betriebszustand

Der aktuelle Stand gilt als funktional stabil.

Die Pipeline:

- verarbeitet den Eingangsbestand vollständig und prüft ihn vor der Verarbeitung
- verortet, typisiert und ordnet Layoutblöcke deterministisch per ONNX-Modell
- füllt Text über ein lokales Vision-Modell mit festen Prompts und Token-Deckeln
- erzeugt pro Dokument ein kanonisches DoclingDocument als JSON und Markdown
- kopiert Bildausschnitte in den Ergebnisbestand und verweist auf tragfähige relative URIs
- setzt auf Seitenebene wieder auf und vermerkt gescheiterte Seiten, statt sie festzuschreiben
- hebt Seitengrenzen nirgends auf, damit jede Aussage einer Seite zurechenbar bleibt

Weitere funktionale Änderungen sollten erst vorgenommen werden, wenn ein konkreter neuer Fehler oder ein reproduzierbares Qualitätsproblem beobachtet wird.
