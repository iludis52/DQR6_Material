# Bildoptimierung

## Zweck

`03_image_optimization.ipynb` optimiert die von Docling aus Scan-PDFs extrahierten Bildausschnitte für eine kompakte, portable Markdown-Ausgabe und ergänzt sie optional um semantische Metadaten mit einem lokal in LM Studio bereitgestellten Vision-Modell.

Ausgangspunkt ist ein bereits extrahiertes Dokument unter:

```text
data/processed/<DOKUMENT>/
├── <DOKUMENT>.md
├── <DOKUMENT>.json
└── <DOKUMENT>_artifacts/
```

Der Lauf verarbeitet die in Docling und Markdown referenzierten Bilder direkt im bestehenden `<DOKUMENT>_artifacts`-Ordner.

Grundprinzipien:

- Portabilität vor maximaler Bildqualität
- maximale Rasterdichte von 144 ppi
- keine Hochskalierung
- JPEG und PNG als kanonische Zielformate
- technische Bildoptimierung deterministisch in Python
- semantische Bildbeschreibung getrennt über ein lokales Vision-LLM
- XMP-Metadaten werden direkt in die finalen Bilddateien eingebettet
- Markdown, Docling-JSON und Bilddateien bleiben nach dem Lauf konsistent
- keine zusätzliche `_optimized_document`-Kopie

---

## Projektstruktur

Die App wird installationsfrei aus dem Projektordner geladen.

```text
projekt/
├── 01_pdf_extraction.ipynb
├── 02_markdown_lektorat.ipynb
├── 03_image_optimization.ipynb
├── python/
│   ├── pdf_extraction/
│   └── markdown_lektorat/
├── tests/
└── data/
    ├── raw/
    │   └── <DOKUMENT>.pdf
    └── processed/
        └── <DOKUMENT>/
            ├── <DOKUMENT>.md
            ├── <DOKUMENT>.json
            └── <DOKUMENT>_artifacts/
```

Das Notebook bestimmt den Projekt-Root automatisch anhand von `data/raw` und `data/processed`.

---

## Voraussetzungen

Erforderlich sind:

- Python 3.12 oder kompatibel
- Jupyter
- `numpy`
- `pandas`
- `Pillow`
- `opencv-python`
- `scikit-image`

Optional:

- `pngquant` für hochwertige, perceptual-optimierte PNG-Palettenreduktion
- LM Studio mit geladenem Vision-Modell
- Gemma 4 12B als aktuelles Zielmodell

Für die lokale Bildbeschreibung erwartet die aktuelle Konfiguration einen OpenAI-kompatiblen LM-Studio-Endpunkt.

---

## Verwendung

### 1. LM Studio starten

Falls semantische Bildmetadaten erzeugt werden sollen:

- Gemma 4 12B oder ein kompatibles Vision-Modell laden
- lokalen Server starten
- prüfen, ob das Modell über den konfigurierten OpenAI-kompatiblen Endpoint erreichbar ist

Im aktuellen Notebook sind folgende Werte vorgesehen:

```python
LMS = "http://192.168.178.27:1234/v1"
MODELL = "google/gemma-4-12b"
ENABLE_LLM = True
```

Wenn keine LLM-Metadaten erzeugt werden sollen, kann gesetzt werden:

```python
ENABLE_LLM = False
```

Die Bildoptimierung selbst funktioniert unabhängig vom LLM.

### 2. Notebook öffnen

```text
03_image_optimization.ipynb
```

Das Notebook liegt im Projekt-Root.

### 3. Dokument auswählen

Das Notebook sucht PDFs unter:

```text
data/raw/
```

Wenn `BUCH = None` gesetzt ist und genau ein PDF gefunden wird, wird der Dokumentname automatisch übernommen.

Bei mehreren PDFs sollte `BUCH` explizit gesetzt werden.

### 4. Lauf starten

Die Verarbeitung erfolgt direkt im Notebook von oben nach unten.

Die Quelldateien liegen unter:

```text
data/processed/<DOKUMENT>/
```

Die optimierten Bilddateien werden direkt in:

```text
data/processed/<DOKUMENT>/<DOKUMENT>_artifacts/
```

geschrieben.

---

## Verarbeitung

Die Verarbeitung erfolgt in mehreren technisch getrennten Schritten:

```text
Docling-JSON und Markdown einlesen
Bildreferenzen und Bounding Boxes auflösen
144-ppi-Zielauflösung berechnen
technische Bildmerkmale analysieren
Bildklasse bestimmen
JPEG-/PNG-Kandidaten erzeugen
Qualitätsmetriken berechnen
besten Kandidaten auswählen
optional Vision-Metadaten erzeugen
XMP einbetten
Bilddatei validieren
Markdown aktualisieren
Docling-JSON aktualisieren
alte Quelldatei bei Formatwechsel entfernen
Audit-Manifest schreiben
```

Die Bildoptimierung und die semantische Beschreibung sind bewusst voneinander getrennt.

---

## Auflösungsregel

Die maximale Rasterdichte beträgt:

```text
144 ppi
```

Die Zielgröße wird aus der Docling-Bounding-Box berechnet.

Da PDF-/Docling-Geometrie auf 72 Punkten pro Zoll basiert, gilt:

```python
target_width_px = bbox_width_pt / 72 * 144
target_height_px = bbox_height_pt / 72 * 144
```

Vereinfacht:

```python
target_width_px = bbox_width_pt * 2
target_height_px = bbox_height_pt * 2
```

Bilder werden niemals hochskaliert.

---

## Technische Bildklassifikation

Die Klassifikation erfolgt deterministisch anhand von Rastermerkmalen.

Aktuelle Klassen:

```text
PHOTO_COLOR
PHOTO_GRAYSCALE
LINE_ART_BILEVEL
LINE_ART_GRAYSCALE
SCREENSHOT_OR_TEXT_GRAPHIC
ALPHA_GRAPHIC
MIXED_CONTENT
```

Berücksichtigt werden unter anderem:

- Alpha-Kanal
- Farbkanal-Abweichungen
- Graustufencharakter
- Kantenanteil
- lokale Varianz
- homogene Flächen
- Helligkeitsverteilung
- near-bilevel-Struktur
- Entropie

Die Klassifikation ist technisch, nicht semantisch.

Sie entscheidet nicht, ob ein Bild beispielsweise eine Maschine, ein Diagramm oder ein Netzwerk zeigt, sondern nur, welche Kompressionsstrategie technisch sinnvoll ist.

---

## Formatwahl

### JPEG

JPEG wird bevorzugt für:

- Farbfotos
- Graustufenfotos
- kontinuierliche Tonwertbilder

Verwendete Qualitätskandidaten:

```text
85
75
65
55
45
```

Der endgültige Kandidat wird nicht nur anhand der Dateigröße, sondern anhand der Qualitätsmetriken ausgewählt.

### PNG

PNG wird bevorzugt für:

- Diagramme
- Screenshots
- Textgrafiken
- ehemalige Vektorgrafiken
- Strichzeichnungen
- Bilder mit Alpha-Kanal
- stark strukturierte Grafiken

Mögliche PNG-Kandidaten:

- Truecolor
- Graustufen
- bilevel
- Paletten-PNG

---

## Farbreduktion

Für farbige technische Grafiken gilt eine harte Untergrenze:

```python
COLOR_GRAPHIC_MIN_PALETTE_COLORS = 16
```

Damit sind 2-, 4- und 8-Farben-Paletten für farbige Diagramme und Screenshots ausgeschlossen.

Diese Regel wurde eingeführt, weil zu aggressive Palettenreduktion bei technischen Schaubildern zu sichtbarem Informations- und Farbverlust führen kann.

Zusätzlich werden CIEDE2000-Farbdifferenzen bewertet.

Verwendete Farbmetriken:

```text
deltae_mean
deltae_p95
```

Damit werden Kandidaten verworfen, deren Farbabweichung trotz guter Strukturmetriken zu hoch ist.

---

## pngquant

Wenn `pngquant` installiert ist, wird es automatisch erkannt:

```python
PNGQUANT_BINARY = shutil.which("pngquant")
```

`pngquant` erzeugt zusätzliche perceptual-optimierte PNG-Kandidaten.

Falls `pngquant` nicht installiert ist, arbeitet das Notebook vollständig mit Pillow weiter.

Die Pipeline bleibt dadurch portabel und funktionsfähig, erhält aber optional eine bessere Palette-Quantisierung.

---

## Qualitätsmetriken

Die Auswahl des finalen Bildes basiert auf mehreren objektiven Metriken.

### SSIM

SSIM bewertet die strukturelle Ähnlichkeit zwischen 144-ppi-Referenz und Kandidat.

### Edge F1

`edge_f1` bewertet, ob Kanten, Linien und Konturen erhalten bleiben.

Dies ist besonders wichtig für:

- Diagramme
- Strichzeichnungen
- Screenshots
- kleine technische Symbole

### Connected Component Retention

`component_retention` prüft, ob kleine zusammenhängende Strukturen erhalten bleiben.

Damit können Verluste bei:

- Textstrichen
- Punkten
- dünnen Linien
- Symbolteilen

erkannt werden.

### CIEDE2000

Für farbige Grafiken wird zusätzlich die Farbdifferenz in CIELAB gemessen.

Aktuell werden verwendet:

```text
deltae_mean
deltae_p95
```

---

## Qualitätszonen

Die Pipeline verwendet zwei Qualitätsstufen:

```text
preferred
minimum
```

Wenn mindestens ein Kandidat die strengere `preferred`-Zone erreicht, wird der kleinste Kandidat innerhalb dieser Zone ausgewählt.

Nur wenn kein Kandidat die `preferred`-Zone erreicht, wird auf die `minimum`-Zone zurückgefallen.

Damit wird verhindert, dass ein extrem kleiner, aber sichtbar stärker reduzierter Kandidat automatisch gewinnt.

---

## XMP-Metadaten

Die finalen JPEG- und PNG-Dateien erhalten eingebettete XMP-Metadaten.

Verwendete Standardfelder sind unter anderem:

```text
dc:title
dc:description
dc:subject
dc:language
Iptc4xmpCore:AltTextAccessibility
Iptc4xmpCore:ExtDescrAccessibility
```

Zusätzlich wird ein eigener `docrag`-Namespace verwendet.

Darin werden technische Provenance-Informationen gespeichert, zum Beispiel:

```text
schemaVersion
assetId
sourceDocument
sourcePage
sourcePictureRef
sourceBBox
sourceCoordOrigin
sourceImageUri
sourceWidth
sourceHeight
sourceDpi
sourceCaption
sectionHeading
optimizedWidth
optimizedHeight
maxPpi
technicalClass
descriptionMethod
descriptionModel
metadataGeneratedAt
```

Der aktuelle Namespace lautet:

```text
urn:docrag:metadata:1.0
```

Für eine langfristige organisationale Nutzung sollte dieser später durch einen organisationskontrollierten Namespace ersetzt werden.

---

## Vision-LLM

Wenn `ENABLE_LLM = True` gesetzt ist, erhält das lokale Vision-Modell:

- das final optimierte Bild
- die Docling-Caption
- die nächstgelegene Abschnittsüberschrift
- nahe Dokumenttexte

Das Modell erzeugt strukturiert:

```text
title
alt_text
description
extended_description
keywords
semantic_visual_type
contains_visible_text
visible_text_summary
```

Die Ausgabe wird über ein JSON-Schema beschränkt.

Wichtig:

Das Vision-Modell beeinflusst nicht:

- Formatwahl
- Auflösung
- JPEG-Qualität
- PNG-Palettengröße
- technische Quality Gates

Diese Entscheidungen bleiben vollständig deterministisch.

---

## LM-Studio-Fehlerbehandlung

Wenn das LLM deaktiviert oder nicht erreichbar ist, läuft die Bildoptimierung trotzdem weiter.

In diesem Fall wird ein deterministischer Fallback aus vorhandenen Docling-Daten verwendet.

Der Metadatenstatus wird entsprechend markiert:

```text
SEMANTIC_METADATA_PENDING
```

Die Bilddatei enthält weiterhin technische Provenance-Metadaten.

---

## In-place-Verarbeitung

Die Bilddateien werden direkt im bestehenden Artefaktordner verarbeitet:

```text
data/processed/<DOKUMENT>/<DOKUMENT>_artifacts/
```

Es wird bewusst kein zusätzlicher Ordner wie

```text
_optimized_document
```

erzeugt.

Das ist Teil der Architektur.

Der Artefaktordner gilt bereits als Arbeitskopie der ursprünglichen PDF-Inhalte.

---

## Sicherer Formatwechsel

Wenn sich das Dateiformat ändert, beispielsweise:

```text
image.png
```

zu:

```text
image.jpg
```

erfolgt der Wechsel in definierter Reihenfolge:

1. neuer Bildkandidat wird im Artefaktordner geschrieben
2. XMP wird eingebettet
3. Bild wird erneut geöffnet und validiert
4. neue Datei wird atomar committed
5. Markdown wird aktualisiert
6. Docling-JSON wird aktualisiert
7. erst danach wird die alte Bilddatei gelöscht

Dadurch bleibt die Pipeline auch bei Formatwechseln konsistent.

---

## Markdown-Aktualisierung

Bildreferenzen werden automatisch angepasst.

Beispiel:

```markdown
![Image](Dokument_artifacts/bild.png)
```

kann werden zu:

```markdown
![Generierter Alt-Text](Dokument_artifacts/bild.jpg)
```

Dabei werden sowohl:

- Dateiendung
- Alt-Text

aktualisiert.

---

## Docling-JSON-Aktualisierung

Zusätzlich zum Markdown wird auch die Bildinformation im Docling-JSON aktualisiert.

Geändert werden:

```text
image.uri
image.mimetype
image.dpi
image.size.width
image.size.height
```

Damit bleibt das JSON nach der Optimierung weiterhin als konsistente Dokumentrepräsentation nutzbar.

---

## Atomare Schreibvorgänge

Temporäre Dateien werden im gleichen Zielordner geschrieben.

Erst nach erfolgreicher Validierung werden sie mit `os.replace()` auf den finalen Pfad verschoben.

Dies reduziert das Risiko beschädigter Bilddateien bei abgebrochenen Schreibvorgängen.

---

## Validierung

Nach jedem finalen Bild werden unter anderem geprüft:

- Datei lässt sich wieder öffnen
- erwartetes Format stimmt
- Pixelabmessungen stimmen
- XMP ist vorhanden
- XMP lässt sich parsen
- Markdown-Referenz zeigt auf eine existierende Datei
- Docling-JSON-URI zeigt auf eine existierende Datei

Ein Bild gilt erst nach erfolgreichem Read-back als abgeschlossen.

---

## Audit-Manifest

Der Lauf erzeugt zwei kleine technische Audit-Dateien:

```text
<DOKUMENT>.image-optimization.json
<DOKUMENT>.image-optimization.csv
```

Sie liegen direkt unter:

```text
data/processed/<DOKUMENT>/
```

Das Manifest enthält unter anderem:

- Quellpfad
- Quell-Hash
- ursprüngliche Größe
- Zielgröße
- technische Bildklasse
- ausgewählten Encoder
- Qualitätsparameter
- SSIM
- Edge F1
- Component Retention
- Delta-E-Werte
- Dateigröße vorher/nachher
- Einsparungsquote
- LLM-Status
- LLM-Modell
- XMP-Validierungsstatus

Die Audit-Dateien enthalten keine zusätzlichen Bildkopien.

---

## Konfiguration

Wichtige Einstellungen befinden sich direkt im Notebook.

### Dokument

```python
BUCH = None
MARKDOWN_OVERRIDE = None
```

### Auflösung

```python
MAX_PPI = 144
ALLOW_UPSCALE = False
```

### Formate und JPEG

```python
JPEG_QUALITIES = [85, 75, 65, 55, 45]
```

### PNG

```python
PNG_PALETTE_SIZES = [2, 4, 8, 16, 32, 64, 128, 256]
COLOR_GRAPHIC_MIN_PALETTE_COLORS = 16
ENABLE_PNGQUANT = True
```

### LLM

```python
LMS = "http://192.168.178.27:1234/v1"
MODELL = "google/gemma-4-12b"
ENABLE_LLM = True
```

### Metadaten

```python
METADATA_LANGUAGE = "de"
DOCRAG_NAMESPACE_URI = "urn:docrag:metadata:1.0"
DOCRAG_SCHEMA_VERSION = "1.0"
```

---

## Architektur

Die wichtigsten Funktionsgruppen im Notebook haben folgende Aufgaben:

| Bereich | Aufgabe |
|---|---|
| Pfadauflösung | Projekt-Root, Dokument und Artefaktordner bestimmen |
| Docling-Parsing | Bilder, Bounding Boxes, Captions und Kontext laden |
| Rasteranalyse | technische Bildmerkmale berechnen |
| Klassifikation | technische Bildklasse bestimmen |
| Resampling | 144-ppi-Zielgröße erzeugen |
| Candidate Generation | JPEG-/PNG-Kandidaten erzeugen |
| Quality Gates | Struktur-, Kanten- und Farbqualität prüfen |
| Candidate Selection | kleinsten Kandidaten in der besten Qualitätszone wählen |
| LM Studio | semantische Bildbeschreibung erzeugen |
| XMP | Metadaten erstellen und in JPEG/PNG einbetten |
| Markdown Rewrite | Bildpfade und Alt-Texte aktualisieren |
| Docling Rewrite | Bild-URI, MIME-Type und Abmessungen aktualisieren |
| Validation | Bild, XMP und Referenzen prüfen |
| Manifest | technische Laufdaten dokumentieren |

Die Architektur trennt bewusst technische Bildverarbeitung von semantischer Bildbeschreibung.

---

## Fehlerverhalten

Die Pipeline bricht bei kritischen Struktur- oder Dateifehlern bewusst ab.

Typische harte Fehler:

- Docling-JSON fehlt
- Markdown-Datei fehlt
- Artefaktordner fehlt
- neue Bilddatei lässt sich nicht validieren
- XMP kann nicht gelesen werden
- Docling-JSON verweist nach dem Commit auf fehlende Bilder
- Markdown verweist nach dem Commit nicht auf die neuen Pfade

Nicht-kritisch ist dagegen ein ausgefallenes LLM.

Dann bleibt die Bildoptimierung gültig und die semantische Beschreibung kann später nachgeholt werden.

---

## Wiederholte Läufe

Da das Notebook in-place arbeitet, sollte ein erneuter Lauf bewusst erfolgen.

Die Pipeline startet jeweils vom aktuellen Inhalt des `<DOKUMENT>_artifacts`-Ordners.

Für produktive Massenläufe sollte deshalb sichergestellt sein, dass die vorgelagerte PDF-Extraktion die Artefakte reproduzierbar neu erzeugt, wenn ein kompletter Neustart gewünscht ist.

Lossy JPEG-Dateien sollten nicht unnötig mehrfach hintereinander rekodiert werden.

---

## Tests und Qualitätssicherung

Die aktuelle Pipeline wurde anhand eines realen Docling-Bildkorpus kalibriert.

Abgesicherte Bereiche sind unter anderem:

- 144-ppi-Geometrie
- JPEG-/PNG-Klassifikation
- Farbfoto-Kompression
- technische Diagramme
- ehemalige Vektorgrafiken
- Paletten-PNG
- Schutz vor zu kleinen Farbpaletten
- SSIM
- Edge F1
- Connected Component Retention
- CIEDE2000-Farbdifferenz
- XMP-Einbettung in JPEG
- XMP-Einbettung in PNG
- XMP-Read-back
- Markdown-Pfadaktualisierung
- Docling-JSON-Aktualisierung

Für größere Änderungen sollte erneut mit einem repräsentativen Bildkorpus getestet werden.

---

## Entwicklungshinweise

Für Änderungen am Notebook gilt:

1. Auflösungslogik, Formatwahl und LLM-Metadaten nicht gleichzeitig umbauen
2. neue Bildklassen zunächst auf einem realen Korpus kalibrieren
3. Quality-Gate-Schwellen nicht ohne Sichtprüfung ändern
4. bei Änderungen der Pfadstruktur immer gemeinsam prüfen:
   - Markdown
   - Docling-JSON
   - Artefaktordner
5. neue XMP-Felder auf Read-back-Kompatibilität prüfen
6. bei Änderungen der Palettenstrategie farbige Diagramme gezielt regressionsprüfen
7. `pngquant` immer als optionalen Optimierer behandeln; der Pillow-Fallback muss funktionsfähig bleiben

---

## Aktueller Betriebszustand

Der aktuelle Stand gilt als funktional stabil.

Die Pipeline:

- verarbeitet reale Docling-Bildartefakte vollständig
- reduziert die Auflösung auf maximal 144 ppi
- wählt JPEG oder PNG abhängig vom Bildtyp
- schützt farbige technische Grafiken vor zu aggressiver Palettenreduktion
- kann optional semantische Metadaten mit Gemma 4 12B erzeugen
- bettet XMP direkt in die finalen Bilder ein
- aktualisiert Markdown und Docling-JSON konsistent
- schreibt die optimierten Bilder direkt in den vorhandenen Artefaktordner
- erzeugt keine redundante zusätzliche Bildkopie

Weitere funktionale Änderungen sollten erst vorgenommen werden, wenn ein konkretes reproduzierbares Qualitäts- oder Integritätsproblem beobachtet wird.
