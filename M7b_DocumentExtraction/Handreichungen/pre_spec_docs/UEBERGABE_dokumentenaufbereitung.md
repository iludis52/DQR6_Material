# Übergabe — Referenz-Implementierung KI-gestützte Dokumentenaufbereitung

**Projekt:** Umsetzung des Leitfadens „KI-gestützte Dokumentenaufbereitung und
Datenextraktion" (DQR 5/6) als lauffähige Referenz-Implementierung für eine lokale
LM-Studio-Umgebung
**Stand:** 07.09.2026
**Zweck dieses Dokuments:** Kontextübergabe an eine Nachfolge-Sitzung ohne
Anlaufverluste

---

## 0. Geltung und Verhältnis zum SDD-Set

Dieses Dokument ist **keine `spec.md`**. Es hält den erreichten Stand, die
getroffenen Entscheidungen samt Begründung und die belegten Befunde fest — also auch
Technisches, das laut SDD-Regel nicht in eine Spezifikation gehört.

Für die nächste Etappe gilt:

- Abschnitt 6 (Anforderungen, EARS) ist der **fachliche Kern** und die Vorlage für
  eine `spec.md`.
- Die Abschnitte 3, 4 und 8 (Entscheidungen, Befunde, Fallen) gehören inhaltlich in
  eine `plan.md`.
- Abschnitt 7 (offene Fragen) ist noch nicht entscheidungsreif und gehört in keins
  von beidem, bis geklärt.

---

## 1. Ausgangslage

Der Leitfaden beschreibt ein Neun-Phasen-Prozessmodell (00–08) mit vier Grundsätzen:
**Schema vor Prompt**, **Trennung formaler und fachlicher Validierung**,
**Verankerung** und **Human-in-the-Loop**.

Die Erprobung läuft bewusst an realen Layout-Katastrophen, nicht an sauberen
Beispielseiten. Drei Testseiten:

| Kürzel | Quelle | Charakter |
|---|---|---|
| `zimbardo` | Zimbardo, Psychologie, 18. Aufl. | born-digital, zwei Tabellen, Diagramm, mehrspaltig |
| `wahrnehmung` | Wahrnehmungspsychologie | born-digital, Marginalspalte, Kasten mit inneren Spalten |
| `tietze` | Tietze/Schenk, Halbleiter-Schaltungstechnik, 2002 | 1-Bit-Scan **mit fehlerhaftem OCR-Textlayer**, viele Formeln |

Die dritte Seite ist der wichtigste Prüfstein: sie widerlegt die verbreitete
Triage-Regel „`get_text()` leer ⇒ Scan". Der Textlayer existiert, ist aber falsch
(`10 !2` statt `10 Ω`) und hat alle abgesetzten Formeln verworfen.

---

## 2. Erreichter Stand

Vier lauffähige Notebooks. Alle Zahlen unten stammen aus tatsächlichen Läufen auf
einem Mac (Apple Silicon), nicht aus Schätzungen.

### Notebook 1 — `01_layout_erkennung_und_schema.ipynb`

Phase 01b + 02. PDF-Seite → `SeitenBefund` mit typisierten, verorteten und
geordneten Blöcken. Ablage: `befunde/<name>_stufe1.json`.

Enthält außerdem das Koordinaten-Rahmenwerk (`Bbox` mit Pflichtfeld
`Bezugsrahmen`), die Klassen-Abbildung mit Verlustdokumentation und das
Strom-Konzept.

**Offen:** Die Diffs a–e aus dem Chat (Logit-Marge statt gesättigter Konfidenz,
`import time` nach oben, `nach_id`-Nachschlag, optionale IoU-Warnung) sind geliefert,
der Einbau ist **nicht bestätigt**. Die vorliegenden `*_stufe1.json` enthalten kein
Feld `marge`.

### Notebook 2 — `02_sondierung_paddleocr_vl.ipynb`

Kein Pipeline-Baustein, sondern eine Messung: taugt PaddleOCR-VL für Stufe 2?
Vergleich der VLM-Ausgabe gegen den PyMuPDF-Textlayer als unabhängige zweite Quelle.

Ergebnis (Zimbardo, MLX in LM Studio):

- mittlere Ähnlichkeit **0,99** über 9 Textblöcke
- **0,64 s** je Block, Streuung 0,21 s bis 2,37 s (hängt an der Ausgabelänge)
- höchste Ähnlichkeit zwischen zwei verschiedenen Prompts: **0,41** — die
  Prompt-Präfixe wirken also tatsächlich

### Notebook 3 — `03_erkennung_und_befund.ipynb`

Phase 01c. Füllt das Feld `text`. Ablage: `befunde/<name>_stufe2.json`.

Enthält das Zusammenführen benachbarter Blöcke, den proportionalen Ausschnittsrand,
die Prompt- und Token-Zuordnung und die Nachbereitung der Ausgabe.

### Notebook 4 — `04_chunking_index_und_messung.ipynb`

Phase 05 + 06. Chunking, Einbettung, Kosinus-Suche in NumPy, Messung gegen
Prüffragen. Ablage: `index/chunks.json` + `.npy`.

Bewusst **vor** der LLM-Anreicherung gebaut, damit sich deren Notwendigkeit belegen
statt vermuten lässt.

---

## 3. Getroffene Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| E1 | Eigener Detektor statt Vision-LLM für die Layout-Analyse | End-to-End-VLM erzeugt instabile Layout-Analyse und Halluzinationen bei mehrspaltigen Layouts; ein Detektor kann strukturell nicht halluzinieren |
| E2 | ONNX-Export **phungpx/PP-DocLayoutV3-ONNX**, nicht alex-dinh | phungpx exponiert die vier Rohköpfe inkl. `order_logits` (300×300) und `out_masks`; alex-dinh backt den Postprocess in den Graphen und liefert nur einen Rang ohne Gütemaß und keine Masken |
| E3 | Klassennamen aus der PaddleX-`config.json`, nicht aus `labels.json` des Exports | Beide Tabellen haben 25 Einträge, die Export-Tabelle legt aber fünf Klassen zusammen (5/15 → `formula`, 9 → `footer`, 13 → `header`, 23 → `text`). Zusammenlegen geht später immer, aufspalten nie |
| E4 | Vorverarbeitung: `INTER_CUBIC`, `/255`, **keine** ImageNet-Statistik | `config.json` sagt `interp: 2` und `norm_type: none`; `is_scale` fehlt, PaddleDetection-Default ist `True`, RT-DETR-Referenzen teilen durch 255. Der Beispielcode der Model Card widerspricht der eigenen Config und wurde verworfen |
| E5 | Provider gegen `ort.get_available_providers()` filtern, Default reines CPU | Fest verdrahtetes CUDA wirft auf dem Mac; CoreML fällt bei DETR-Graphen häufig teilweise zurück |
| E6 | PaddleOCR-VL-**1.5**, nicht 1.6 | Die MLX-Variante gibt es nur für 1.5. Windows: GGUF (`.gguf` **plus** `-mmproj.gguf` im selben Ordner), Mac: MLX. Beide laden in LM Studio, beide über dieselbe OpenAI-kompatible Schnittstelle |
| E7 | `display_formula` und `inline_formula` bleiben getrennt | Der Prompt ist derselbe, die Rückführung ins Dokument nicht: abgesetzt wird eigener Block, inline muss zurück in den Satz. Zahlt sich in Stufe 2 konkret aus |
| E8 | `text_format` und `text_quelle` als eigene Felder | Ohne `text_format` müsste Stufe 4 raten, wie `text` zu lesen ist. `quelle` sagt, woher der **Block** kommt, `text_quelle`, woher der **Text** kommt — ab Stufe 4 fällt beides auseinander |
| E9 | Beim Zusammenführen von Blöcken fällt das Polygon weg | Die Vereinigung zweier Umrisse ist kein Umriss; ein falsches Polygon ist schlechter als keins |
| E10 | Chunk-Zielgröße 1200 Zeichen | Keine Faustregel: die multilingual-E5-Modelle verarbeiten höchstens 512 Tokens und schneiden alles darüber **stillschweigend** ab. Für Deutsch sind das grob 1500–2000 Zeichen, abzüglich Überschriftenpfad |
| E11 | Kein Überlappen zwischen Chunks | Der übliche Grund entfällt, weil an Elementgrenzen geschnitten wird statt nach Zeichenzahl. Unmittelbarer Gewinn aus Stufe 1 |
| E12 | **`DoclingDocument` als kanonisches Zielformat** (07.09.2026) | Statt eines selbst erfundenen Seitenschemas. Begründung ausführlich in Abschnitt 5 |

---

## 4. Belegte Befunde

Getrennt nach dem, was gemessen wurde, und dem, was daraus folgt. Zwei der Befunde
widerlegen vorherige Annahmen — das ist ausdrücklich festgehalten, damit sie nicht
wiederkehren.

### B1 — Die Erkennung ist auf born-digital-Seiten sehr gut

0,99 mittlere Ähnlichkeit gegen den Textlayer. In einem Fall (`figure_title`) las das
**VLM richtig und der Textlayer falsch**: „Weber'sche Konstanten" gegen „Konstante n",
ein Kerning-Artefakt des Satzprogramms. Die Ähnlichkeit misst Übereinstimmung, nicht
Wahrheit.

### B2 — PaddleOCR-VL gibt OTSL aus

Die Tabellenausgabe ist kein Freitext, sondern `<fcel>…<nl>` — das Tabellenvokabular
des docling-Ökosystems (`fcel` gefüllte Zelle, `ecel` leere, `lcel`/`ucel` verbundene,
`nl` Zeilenumbruch). `Chart Recognition:` liefert die **Datenreihe** eines Diagramms,
nicht dessen Beschreibung.

### B3 — Blockgrenzen laufen durch Wörter

Die Zimbardo-Fußzeile bestand aus drei Detektionen, die Grenzen schnitten „Exemplar"
mitten durch. Das VLM las `Inplar` — es meldet nicht „unlesbar", es rät. Behoben durch
das Zusammenführen in Notebook 3 (Union-Find über Strom, senkrechte Überlappung,
waagerechte Lücke). Verifiziert: Blöcke 10, 11, 12 → ein Streifen x=26…821.

### B4 — Die Kantenkonfidenz sättigt

Alle zwölf Kanten der Zimbardo-Seite haben `konfidenz: 1.0`. Ursache ist numerisch:
`float32` sättigt jenseits von etwa ±17 im Logit-Raum. Als Gütemaß unbrauchbar. Der
gelieferte Diff ersetzt sie durch die vorzeichenbehaftete **Logit-Marge**.

### B5 — OTSL ist auffindbar (**widerlegt eine Annahme**)

Erwartet worden war, dass OTSL-Chunks im Vektorindex abstürzen. Gemessen:

```
zimbardo:0:004 (OTSL)                Rang 1 von 13,  Ähnlichkeit 0.905
dieselbe Tabelle als Prosa                           Ähnlichkeit 0.911
```

Differenz 0,006 — Rauschen. E5 liest durch die Marken hindurch, weil die Zellinhalte
gewöhnliche Wörter sind. **Stufe 4b ist für Tabellen mit sprechenden Zellinhalten
nicht belegt.**

Einschränkung: die zweite Tabelle derselben Seite (fast nur Zahlen und
Millimeterangaben) landet auf Rang 5 bei 0,816. Vermutung, ungeprüft: Zahlentabellen
brauchen die Anreicherung, Begriffstabellen nicht.

### B6 — Isolierte Formeln sind im Index tot

Vier von 13 Chunks liegen unter 120 Zeichen, drei davon sind alleinstehende
LaTeX-Formeln aus dem Tietze. Eine natürlichsprachliche Frage trifft
`\frac{4kT}{R}` nicht, und der Chunk trägt keinen Satz, der erklärte, wovon die Formel
handelt.

**Das ist die belegte Lücke — und sie gehört in 4a, nicht 4b:** eine abgesetzte Formel
gehört zu dem Absatz, der sie einführt. Der einleitende Satz endet mit Doppelpunkt,
die Formel steht darunter. Deterministisch erkennbar.

### B7 — Die Messung ist gesättigt (**Konstruktionsfehler**)

R@3 = 1,00, MRR = 0,917 bei 13 Chunks aus **zwei völlig verschiedenen Büchern**. Das
Modell muss nicht die richtige Stelle finden, nur das richtige Fach. Der Zufall läge
bei R@3 ≈ 0,23.

Experiment A (mit/ohne Überschriftenpfad) lieferte **Ziffer für Ziffer identische**
Ergebnisse, weil von 13 Chunks genau einer überhaupt einen Pfad trug.

### B8 — Eingezogene Zwischentitel werden nicht erkannt

Auf der Tietze-Seite: null Überschriften, obwohl „Ohmscher Widerstand:",
„Bipolartransistor:" vorhanden sind. Sie stehen fett am Absatzanfang, ohne eigene
Zeile, und bilden keine eigene Region. Der Detektor klassifiziert sie als `text` —
geometrisch korrekt, strukturell falsch. Typisch für Fachliteratur.

### B9 — E5-Ähnlichkeitswerte sind komprimiert

Ein inhaltlich völlig unbeteiligter Tietze-Chunk erreicht 0,837 auf eine Frage nach
Weber'schen Konstanten; der richtige Treffer 0,905. **Absolutwerte bedeuten nichts,
nur die Rangfolge zählt.** Ein Schwellenwert („ab 0,8 relevant") wäre ein Filter, der
alles durchlässt.

---

## 5. Datenmodell: zwei Schichten

### Entscheidung E12 im Detail

Kanonisches Zielformat ist `DoclingDocument` aus `docling-core`. Kein Eigenbau.

Recherchierte Alternativen und warum sie nicht passen:

- **METS + ALTO** (Library of Congress) ist der Standard der Massendigitalisierung.
  ALTO wurde jedoch gebaut, um das ursprüngliche Erscheinungsbild rekonstruierbar zu
  machen — Regionen, Wortkoordinaten, Maße in 1/10 mm. Es kennt keine Tabelle als
  Datenstruktur und keine Formel als LaTeX. Falsches Werkzeug für Weiterverarbeitung,
  richtiges Werkzeug für Archivierung.
- **TEI** ist flexibler und reicher annotierbar als ALTO, aber ein eigenes Universum
  ohne Anbindung an die KI-Werkzeuglandschaft. **JATS/BITS** ist Verlagswelt.

Für `DoclingDocument` sprechen vier Punkte:

1. Es war ohnehin schon als Ziel gewählt (`PP_NACH_DOCLING` in Notebook 1).
2. Die Ströme existieren dort bereits: `ContentLayer.BODY` gegen
   `ContentLayer.FURNITURE`, wobei Furniture beim Iterieren standardmäßig ausgelassen
   wird und über `included_content_layers` einbeziehbar ist. Das ist exakt
   `Strom.BOILERPLATE`.
3. **Das OTSL-Problem ist gelöst, ohne einen Parser zu schreiben:** in
   `docling_core/types/doc/utils.py` liegen `otsl_extract_tokens_and_text` und
   `otsl_parse_texts`; `parse_otsl_table_content(otsl_content)` liefert ein
   `TableData`-Objekt mit Zeilen, Spalten und Zellinhalten, das sich nach Markdown
   oder HTML exportieren lässt.
4. Ökosystem: Export nach Markdown, HTML, JSON, DocTags; veröffentlichtes JSON-Schema
   zur Validierung; fertige Chunker und Anbindungen an LangChain, LlamaIndex,
   Haystack.

### Die Schichten

| Schicht | Format | Rolle | Ablage |
|---|---|---|---|
| Arbeitsformat | `SeitenBefund` (eigen) | **Beobachtung** — alles Gesehene samt Widersprüchen und konkurrierenden Kandidaten | `befunde/*_stufe{1,2}.json` |
| Kanonisch | `DoclingDocument` | **Entscheidung** — eine Region, ein Label, ein Text | `dokumente/<buch>.json` |
| Ausgabe | Markdown, HTML | abgeleitet, **nie von Hand gepflegt** | `md/<buch>.md` |

Was `DoclingDocument` nicht kann und deshalb im Arbeitsformat bleibt: konkurrierende
Kandidaten mit Score, das native `pp_label`, `text_quelle`, die Kantenmarge.

**Der Übergang von Schicht 1 nach Schicht 2 ist Stufe 4a.** Das ist keine neue
Aufgabe, sie hat jetzt nur ein definiertes Ziel.

### Aufgabenteilung der Stufe 4

| Stufe | Inhalt | Modell | prüfbar |
|---|---|---|---|
| 4a | Inline-Elemente zurückschieben, Fortsetzungen zusammenkleben, Hierarchie aus Titeln, OTSL → `TableData`, Abbildung auf `DoclingDocument` | **keins** | ja, gegen Goldset |
| 4b | Zusammenfassung von Zahlentabellen und Diagrammen, Bildbeschreibung, Typisierung der Kästen ohne Klasse | Gemma 4 12B | nein, keine eindeutig richtige Form |

Diese Trennung ist der Kern: Deterministisches und Generatives auseinanderzuhalten
hält den prüfbaren Teil prüfbar. Dieselbe Logik, aus der der Detektor nicht durch ein
VLM ersetzt wurde.

---

## 6. Anforderungen an die nächste Etappe (fachlich, EARS)

Ziel der Etappe: **ein vollständiges Buch durchgehend digitalisieren und nach
Markdown wandeln.**

### Stapelverarbeitung

- **A1** Das System soll alle Seiten eines Dokuments in einem Lauf verarbeiten.
- **A2** Wenn ein Lauf abbricht, soll das System beim Wiederaufsetzen bereits
  fertiggestellte Seiten überspringen.
- **A3** Wenn die Verarbeitung einer Seite fehlschlägt, soll das System die Seite
  überspringen, den Fehler dem Seitenbefund beifügen und mit der nächsten Seite
  fortfahren.
- **A4** Das System soll je Seite die verbrauchte Zeit und die verwendete
  Modellversion festhalten.

### Kanonisches Dokument

- **A5** Das System soll aus den Seitenbefunden eines Dokuments genau ein kanonisches
  Dokument erzeugen.
- **A6** Das System soll die Lesereihenfolge über Seitengrenzen hinweg fortführen.
- **A7** Wenn ein Absatz über eine Seitengrenze läuft, soll das System seine Teile zu
  einem Element zusammenfassen.
- **A8** Das System soll jedem Element seinen Ursprung mitgeben: Quelldatei, Seite und
  Rechteck.
- **A9** Solange ein Element dem Strom Boilerplate angehört, soll das System es vom
  Lesefluss ausnehmen, ohne es zu verwerfen.

### Lesbare Ausgabe

- **A10** Das System soll Tabellen als lesbare Markdown-Tabellen ausgeben.
- **A11** Wenn eine Tabellenausgabe nicht in eine Tabellenstruktur überführbar ist,
  soll das System sie unverändert erhalten und die Seite als prüfbedürftig
  kennzeichnen.
- **A12** Das System soll abgesetzte Formeln dem Absatz zuordnen, der sie einführt.
- **A13** Das System soll inline stehende Formeln an ihrer Fundstelle in den
  umgebenden Satz zurückführen.
- **A14** Das System soll Abbildungen als Datei ablegen und im Dokument darauf
  verweisen.
- **A15** Das System soll für alle Seiten und alle Bücher dieselbe Gliederung
  erzeugen.

### Nachvollziehbarkeit

- **A16** Das System soll für jede Aussage der Ausgabe den Rückweg zur Fundstelle im
  Ursprungsdokument offenhalten.
- **A17** Sofern eine unabhängige zweite Quelle vorliegt, soll das System die
  Übereinstimmung je Element festhalten.
- **A18** Wenn keine zweite Quelle vorliegt, soll das System das Element als
  unverankert kennzeichnen.

> **A18 betrifft den gesamten Tietze.** Auf Scans ist das VLM die einzige Quelle. Eine
> flüssig lesbare, fachlich plausible Ausgabe ist dort genau der Fall, in dem sich
> richtig und überzeugend nicht unterscheiden lassen.

---

## 7. Offene Fragen

### Messung

| # | Frage | Weg zur Klärung |
|---|---|---|
| M1 | Der Korpus ist zu klein und zu heterogen (B7) | Ein zusammenhängendes Kapitel aus **einem** Buch, 20–30 Seiten. Bei 8 s je Seite rund 4 Minuten |
| M2 | Sechs Prüffragen reichen nicht | Auf 25–30 erweitern, davon bewusst schwierige: Antwort über zwei Seiten verteilt, Suchbegriffe nicht wörtlich im Zielchunk |
| M3 | Der Marker-Trick prüft Anwesenheit, nicht Relevanz | Ein Chunk, der `0,003` zufällig enthält, zählt als Treffer |
| M4 | Trägt der Überschriftenpfad? | Experiment A wiederholen, sobald M1 und M2 erledigt sind |
| M5 | **Die Kernthese ist ungeprüft** | Zweiter Index: `page.get_text()`, alle 800 Zeichen geschnitten, keine Metadaten. Dieselben Fragen. Besonders am Tietze, wo der Textlayer die Lüge ist |
| M6 | Hybrid mit BM25 | Vektorsuche versagt bei Eigennamen und Zahlen |

**M5 ist die wichtigste.** Das ganze Projekt behauptet, dass Layout-Analyse dem
Retrieval nützt. Belegt ist das nicht.

### Fachlich

| # | Frage |
|---|---|
| F1 | Eingezogene Zwischentitel (B8) — über Fettung im Textlayer erkennbar? Über ein Modell? |
| F2 | Kästen ohne Klasse („Für die Praxis", „Definition") — Vektorobjekte aus PyMuPDF als deterministischer Regionsnachweis |
| F3 | Überlappende Detektionen (Tabelle und Diagramm ineinander) — auflösen oder beide behalten? |
| F4 | Verschachtelung: ein Kasten mit zwei inneren Spalten. `DoclingDocument` kennt Gruppen — reicht das? |
| F5 | Formelvalidierung: die Tietze-Formeln sind in sich stimmig (`S = I_C,A/U_T` taucht definiert und verwendet auf). Prüfbar gegen die Definitionen, die daneben stehen |
| F6 | Zahlentabellen gegen Begriffstabellen (B5) — braucht nur die erste Sorte Anreicherung? |

---

## 8. Bekannte Fallen

Alle bereits einmal getreten. Nicht erneut nötig.

| Falle | Symptom | Ursache |
|---|---|---|
| `onnx.load()` in `onnxruntime` | `AttributeError` | Zwei verschiedene Pakete. Signatur stattdessen aus der `InferenceSession` lesen |
| Fest verdrahtete Provider | Ausnahme beim Öffnen | Auf dem Mac gibt es kein CUDA. Gegen `get_available_providers()` filtern |
| Falscher ONNX-Export | `KeyError` auf `order_logits`, oder ein einzelner `(300,7)`-Tensor | Zwei Exporte mit unvereinbaren Verträgen (E2) |
| Fehlende `mmproj` | HTTP 400, „model does not support images" | GGUF braucht beide Dateien im selben Ordner |
| E5-Präfixe vertauscht | Qualitätsverlust ohne Fehlermeldung | Die **Instruct**-Variante will bei Dokumenten **kein** Präfix und bei Anfragen `Instruct: {Aufgabe}\nQuery: {…}`. Die Nicht-Instruct-Variante will `passage:`/`query:` |
| Chunk über 512 Tokens | funktioniert scheinbar | Wird stillschweigend abgeschnitten. Die zweite Hälfte ist nie durchsuchbar |
| `float32`-Sättigung | alle Konfidenzen 1,0 | Im Logit-Raum rechnen (B4) |
| Fester Ausschnittsrand | Nachbartext im Ergebnis | 8 px sind bei einer 31 px hohen Seitenzahl ein Viertel der Bildhöhe. Proportional zur Boxhöhe, beidseitig gedeckelt |
| Überschrift mitten im Chunk | leerer Überschriftenpfad | Eine Überschrift muss einen neuen Chunk beginnen und ihn anführen |

---

## 9. Umgebung und Artefakte

### Laufzeitumgebung

- Python 3.12, `pymupdf`, `pdfplumber`, `pydantic`, `opencv-python-headless`,
  `numpy`, `onnxruntime`, `requests`, `docling-core`
- LM Studio mit lokalem Server auf Port 1234, OpenAI-kompatible Schnittstelle
- Modelle: PaddleOCR-VL-1.5 (MLX auf Mac, GGUF + mmproj auf Windows),
  `text-embedding-multilingual-e5-large-instruct`, Gemma 4 12B (für 4b vorgesehen)
- `models/pp_doclayoutv3.onnx` (134 MB) neben den Notebooks
- Kein Docker, kein WSL, kein PaddlePaddle, kein vLLM — ausdrückliche Randbedingung

### Verzeichnisse

```
uploads/      Quell-PDFs
models/       pp_doclayoutv3.onnx
befunde/      <name>_stufe1.json, <name>_stufe2.json
ausschnitte/  PNG je Bildblock
kontrolle/    Overlay-Bilder der Layout-Erkennung
sondierung/   Ausschnitte der Sondierung
index/        chunks.json + chunks.npy
```

### Für die Nachfolge-Sitzung mitzugeben

**Sofort:** dieses Dokument, Notebook 3 und Notebook 4 (der aktuelle Stand),
`befunde/zimbardo_stufe2.json` als Beispiel eines vollständigen Befunds.

**Auf Anforderung:** Notebook 1 (Schema, Koordinaten, Klassenabbildung — wird
gebraucht, sobald am `SeitenBefund` etwas geändert wird), Notebook 2 (nur als Beleg
für die Messwerte).

Notebook 1 ist mit Abstand das längste. Es lohnt sich, es erst nachzureichen, wenn
tatsächlich am Schema gearbeitet wird — die getroffenen Entscheidungen stehen in
Abschnitt 3 dieses Dokuments.

### Anmerkung zur Duplizierung

Das `SeitenBefund`-Schema steht derzeit **doppelt** in Notebook 1 und Notebook 3.
Beim Umbau auf Stapelverarbeitung gehört es in ein Modul `schema.py`, das alle
Notebooks importieren. Das ist der naheliegende erste Schritt der nächsten Etappe.

---

## 10. Reihenfolgevorschlag

1. `schema.py` herausziehen, Diffs a–e aus Notebook 1 einbauen
2. Stapelverarbeitung über ein Kapitel (A1–A4) — erzeugt gleichzeitig den Korpus für
   M1
3. Stufe 4a: Übergang nach `DoclingDocument` (A5–A15), OTSL über
   `parse_otsl_table_content`
4. Prüfset erweitern (M2), Experiment A wiederholen (M4)
5. **M5** — der Vergleich gegen naives Chunking
6. Erst danach 4b, und nur für das, was M5 und B5/B6 als Lücke ausweisen
