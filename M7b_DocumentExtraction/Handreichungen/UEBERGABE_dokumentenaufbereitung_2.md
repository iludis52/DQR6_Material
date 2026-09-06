# Übergabe — Referenz-Implementierung KI-gestützte Dokumentenaufbereitung

**Projekt:** Umsetzung des Leitfadens „KI-gestützte Dokumentenaufbereitung und
Datenextraktion" (DQR 5/6) als lauffähige Referenz-Implementierung für eine lokale
LM-Studio-Umgebung
**Stand:** 06.09.2026
**Ersetzt:** die Fassung vom 07.09.2026 vollständig. Diese war an mehreren Stellen
überholt; wo eine frühere Aussage widerlegt wurde, ist das unten ausdrücklich
vermerkt.
**Zweck:** Kontextübergabe an eine Nachfolge-Sitzung ohne Anlaufverluste. Das
Dokument steht für sich; Vorwissen aus dem bisherigen Verlauf wird nicht
vorausgesetzt.

---

## 0. Geltung und Verhältnis zum SDD-Set

Dieses Dokument ist **keine `spec.md`**. Es hält den erreichten Stand, die
getroffenen Entscheidungen samt Begründung und die belegten Befunde fest — also
auch Technisches, das laut SDD-Regel nicht in eine Spezifikation gehört.

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
Beispielseiten.

### Einzelseiten (Entwicklung und Grenzfälle)

| Kürzel | Quelle | Charakter |
|---|---|---|
| `zimbardo` | Zimbardo, Psychologie, 18. Aufl. | born-digital, zwei Tabellen ineinander mit Diagramm, mehrspaltig |
| `wahrnehmung` | Wahrnehmungspsychologie | born-digital, Marginalspalte, Kasten mit inneren Spalten |
| `tietze` | Tietze/Schenk, Halbleiter-Schaltungstechnik, 2002 | 1-Bit-Scan **mit fehlerhaftem OCR-Textlayer**, viele Formeln |

Die dritte Seite ist der wichtigste Prüfstein: sie widerlegt die verbreitete
Triage-Regel „`get_text()` leer ⇒ Scan". Der Textlayer existiert, ist aber falsch
(`10 !2` statt `10 Ω`) und hat alle abgesetzten Formeln verworfen.

### Vollkorpus (seit dieser Etappe)

**`Buch`** — Fischer, Asal, Krueger: *Sozialpsychologie für Bachelor*, Springer.
**222 Seiten, 2657 Blöcke**, born-digital, durchgehend verarbeitet. Lehrbuchsatz mit
Marginalspalte, farbigen Kästen, Literaturseiten am Kapitelende und
Bildunterschriften, die **seitlich** neben der Abbildung stehen.

Dieser Korpus trägt alle quantitativen Aussagen in Abschnitt 4.

---

## 2. Erreichter Stand

Die Pipeline liegt seit dieser Etappe als **Module** vor, nicht mehr als Notebooks.
Alle Zahlen stammen aus tatsächlichen Läufen auf einem Mac (Apple Silicon, M4 Pro,
24 GB).

### Module

| Datei | Zeilen | Rolle | Abhängigkeiten |
|---|---|---|---|
| `schema.py` | 461 | Arbeitsformat, Koordinatenrahmen, Klassenabbildung, Ablage | pydantic |
| `layout.py` | 318 | Stufe 1: Layout-Erkennung (`Detektor`) | schema, onnxruntime, cv2, pymupdf, numpy |
| `erkennung.py` | 378 | Stufe 2: Zusammenführen, Ausschnitte, VLM (`Erkenner`) | schema, cv2, pymupdf, requests, numpy |
| `stapel.py` | 269 | Stapellauf A1–A4 über ein Buch | schema, pymupdf; layout/erkennung erst bei Bedarf |
| `kanonisch.py` | 460 | Stufe 4a: Übergang nach `DoclingDocument` | schema, docling-core |
| `sichtung.py` | 188 | Auswertung der Befunde; verändert nichts | schema |

Nur `schema.py` hat keine interne Abhängigkeit. Die Abhängigkeiten bilden einen
Stern, keinen Knoten.

### Einstiegspunkt

**`00_steuerung.ipynb`** ist der einzige Einstiegspunkt (E22). Es prüft die
Umgebung, führt Stufe 1 und 2, die Sichtung, den Nachlauf und Stufe 4a aus und
enthält die Kontrollzellen.

### Didaktische Notebooks

`01_layout_erkennung_und_schema.ipynb` bis `04_chunking_index_und_messung.ipynb`
dokumentieren den Weg und die Begründungen. Sie werden nicht mehr ausgeführt; ihr
Code liegt in den Modulen. Notebook 2 (Sondierung PaddleOCR-VL) ist reine Messung,
Notebook 4 (Chunking und Index) ist **noch nicht auf die Module umgestellt**.

### Laufzeiten am Vollkorpus

| Stufe | gesamt | Median je Seite | Maximum |
|---|---|---|---|
| 1 — Layout (ONNX, CPU) | 84,9 s | 0,38 s | 0,51 s |
| 2 — Erkennung (VLM) | 2527,1 s | 12,07 s | 17,71 s |
| 4a — kanonisches Dokument | Sekunden | – | – |

Also gut 40 Minuten für ein Buch, praktisch vollständig in Stufe 2. Bei zwölf
Blöcken je Seite entspricht das den 0,64 s je Block aus der Sondierung.

---

## 3. Getroffene Entscheidungen

### Modell und Erkennung

| # | Entscheidung | Begründung |
|---|---|---|
| E1 | Eigener Detektor statt Vision-LLM für die Layout-Analyse | End-to-End-VLM erzeugt instabile Layout-Analyse und Halluzinationen bei mehrspaltigen Layouts; ein Detektor kann strukturell nicht halluzinieren |
| E2 | ONNX-Export **phungpx/PP-DocLayoutV3-ONNX**, nicht alex-dinh | phungpx exponiert die vier Rohköpfe inkl. `order_logits` (300×300) und `out_masks`; alex-dinh backt den Postprocess in den Graphen und liefert nur einen Rang ohne Gütemaß und keine Masken |
| E3 | Klassennamen aus der PaddleX-`config.json`, nicht aus `labels.json` des Exports | Beide Tabellen haben 25 Einträge, die Export-Tabelle legt aber fünf Klassen zusammen (5/15 → `formula`, 9 → `footer`, 13 → `header`, 23 → `text`). Zusammenlegen geht später immer, aufspalten nie |
| E4 | Vorverarbeitung: `INTER_CUBIC`, `/255`, **keine** ImageNet-Statistik | `config.json` sagt `interp: 2` und `norm_type: none`; `is_scale` fehlt, PaddleDetection-Default ist `True`. Der Beispielcode der Model Card widerspricht der eigenen Config und wurde verworfen |
| E5 | Provider gegen `ort.get_available_providers()` filtern, Default reines CPU | Fest verdrahtetes CUDA wirft auf dem Mac; CoreML fällt bei DETR-Graphen häufig teilweise zurück |
| E6 | PaddleOCR-VL-**1.5**, nicht 1.6 | Die MLX-Variante gibt es nur für 1.5. Windows: GGUF (`.gguf` **plus** `-mmproj.gguf` im selben Ordner), Mac: MLX. Beide laden in LM Studio über dieselbe OpenAI-kompatible Schnittstelle |
| E7 | `display_formula` und `inline_formula` bleiben getrennt | Der Prompt ist derselbe, die Rückführung ins Dokument nicht: abgesetzt wird eigener Block, inline muss zurück in den Satz |
| E8 | `text_format` und `text_quelle` als eigene Felder | Ohne `text_format` müsste Stufe 4 raten, wie `text` zu lesen ist. `quelle` sagt, woher der **Block** kommt, `text_quelle`, woher der **Text** kommt |
| E9 | Beim Zusammenführen von Blöcken fällt das Polygon weg | Die Vereinigung zweier Umrisse ist kein Umriss; ein falsches Polygon ist schlechter als keins |

### Datenmodell und Ablauf

| # | Entscheidung | Begründung |
|---|---|---|
| E12 | **`DoclingDocument` als kanonisches Zielformat** | Statt eines selbst erfundenen Seitenschemas. Ausführlich in Abschnitt 5 |
| E13 | **Ein** `Block`-Typ mit allen Feldern; der Stand steht als `stufe` im Umschlag | Zwei Klassen (`BlockStufe1`/`BlockStufe2`) hätten jede Funktion zur Fallunterscheidung gezwungen. Ein Block bleibt dieselbe Sache, wenn er Text bekommt. `stufe` ist zugleich der Wiederaufsetzpunkt für A2 |
| E14 | Eine Datei je Seite, `befunde/<buch>/<seite:04d>.json`, am Platz überschrieben | Stufe 2 ist eine echte Obermenge von Stufe 1. Eine Datei je Buch hätte bei jeder fertigen Seite das ganze Buch neu geschrieben |
| E15 | Geschrieben wird über eine `.teil`-Datei mit anschließendem `replace()` | Ein Abbruch mitten im Schreiben hinterlässt sonst halbes JSON, das beim Wiederaufsetzen als fertige Seite zählt |
| E16 | Stapellauf **stufenweise**, nicht seitenweise | Detektor und VLM sind nie gleichzeitig geladen (24 GB), die ONNX-Sitzung wird einmal geöffnet, die Zeiten je Stufe bleiben trennbar. Preis: vor dem Ende der Stufe 1 ist keine Seite vollständig |
| E17 | Eine Seite mit gesetztem `fehler` gilt als **offen**, nicht als fertig | Sonst schreibt der erste Fehlschlag eine Seite für alle Zeiten fest. Ein Wiederaufsetzen versucht sie erneut |
| E18 | `Detektor` und `Erkenner` als Klassen; `stapel.py` importiert sie erst bei Bedarf | Vertragstest beim Öffnen statt mitten im Lauf; ein reiner Stufe-2-Lauf braucht kein onnxruntime; im Test ersetzbar |

### Stufe 4a

| # | Entscheidung | Begründung |
|---|---|---|
| E19 | Ströme → `ContentLayer`: haupt und **apparat** nach `BODY`, marginalie nach `NOTES`, boilerplate nach `FURNITURE` | Apparat nach BODY, weil sonst 19 Literaturseiten im Export leer wären (B10) |
| E20 | **Streng nach dem Label des Detektors.** Ein als `header` erkannter Abschnittstitel („Literatur") bleibt Boilerplate | Eine Häufigkeitsregel („seltener `header`-Text ist keine Boilerplate") wäre ein Eingriff in die Klassifikation und gehört nicht nach 4a. Folge: die Literaturlisten stehen ohne Überschrift da |
| E21 | Überschriftenebene aus der **Gliederungsnummer** (`4.2.2` → 3), sonst eine Ebene unter der zuletzt gesehenen | Deterministisch, ohne Textlayer, damit auch auf Scans anwendbar. Belegt an 396 Überschriften (B11) |
| E22 | Entdoppelt wird **nur bei identischem `pp_label`** und ≥ 90 % Enthaltensein | `text in text` und `table in table` sind Doppeldetektionen desselben Gegenstands. `paragraph_title in text` ist es nicht — dort sagen beide etwas Eigenes, beide bleiben |
| E23 | Bildunterschriften werden **nur im erzwungenen Fall** zugeordnet: eine Seite, ein Objekt, eine Unterschrift, kein Widerspruch im Wortlaut | Siehe B12. Wo eine Unterschrift steht, ist eine Gestaltungsentscheidung des jeweiligen Buchs. Jede Schwelle, die an einem Buch gemessen wird, ist beim nächsten wieder geraten |
| E24 | **A7 und A13 werden nicht umgesetzt. Seitengrenzen werden nirgends aufgehoben** | Dauerhafte Vorgabe: was auf einer Seite steht, bleibt dort, damit rückwärts stets eine Seitenzuweisung konstruierbar ist. `DoclingDocument` könnte es (B13), aber jeder Verbraucher müsste dann `charspan` auswerten — ein Chunker, der nur `prov[0].page_no` liest, unterschlüge die zweite Seite stillschweigend |

### Werkzeuge und Ablage

| # | Entscheidung | Begründung |
|---|---|---|
| E25 | **KISS als Grundlinie des Regelwerks** | Layout-Gestaltung ist je Buch zu individuell, um sie deterministisch abzudecken. Eindeutige Fälle im Skript, nicht-eindeutige in einen VLM-Pass (4b) |
| E26 | **Das Steuerungsnotebook ist der einzige Einstiegspunkt**, die `.py` sind Module | Der Jupyter-Kernel startet im Ordner der Notebook-Datei, VS Code startet `.py` im Workspace-Ordner. Ohne Konfigurationsänderung, weil 38 Studierende über Teams zu betreuen sind |
| E27 | Ordnerstruktur nach **Cookiecutter Data Science** (`data/raw`, `data/interim`, `data/processed`) | Verbreitete Konvention; tragende Regel ist, dass Rohdaten nie überschrieben werden |
| E10 | Chunk-Zielgröße 1200 Zeichen | Die multilingual-E5-Modelle verarbeiten höchstens 512 Tokens und schneiden darüber **stillschweigend** ab. Für Deutsch grob 1500–2000 Zeichen, abzüglich Überschriftenpfad |
| E11 | Kein Überlappen zwischen Chunks | Es wird an Elementgrenzen geschnitten statt nach Zeichenzahl |

---

## 4. Belegte Befunde

Getrennt nach dem, was gemessen wurde, und dem, was daraus folgt. Befunde, die
frühere Annahmen widerlegen, sind als solche gekennzeichnet, damit sie nicht
wiederkehren.

### B1 — Die Erkennung ist auf born-digital-Seiten sehr gut

0,99 mittlere Ähnlichkeit gegen den PyMuPDF-Textlayer über 9 Textblöcke. In einem
Fall (`figure_title`) las das **VLM richtig und der Textlayer falsch**:
„Weber'sche Konstanten" gegen „Konstante n", ein Kerning-Artefakt des
Satzprogramms. Die Ähnlichkeit misst Übereinstimmung, nicht Wahrheit.

**Folge für die Beschleunigung:** der naheliegende Hebel — Textblöcke aus dem
Textlayer statt aus dem VLM — widerspricht diesem Befund direkt und ist keine
Handgriffs-, sondern eine Entscheidungsfrage.

### B2 — PaddleOCR-VL gibt OTSL aus

Die Tabellenausgabe ist kein Freitext, sondern `<fcel>…<nl>` — das
Tabellenvokabular des docling-Ökosystems (`fcel` gefüllte Zelle, `ecel` leere,
`lcel`/`ucel` verbundene, `nl` Zeilenumbruch). `Chart Recognition:` liefert die
**Datenreihe** eines Diagramms, nicht dessen Beschreibung.

### B3 — Blockgrenzen laufen durch Wörter

Die Zimbardo-Fußzeile bestand aus drei Detektionen, die Grenzen schnitten
„Exemplar" mitten durch. Das VLM las `Inplar` — es meldet nicht „unlesbar", es rät.
Behoben durch das Zusammenführen in `erkennung.py` (Union-Find über Strom,
senkrechte Überlappung, waagerechte Lücke). Am Vollkorpus greift die Regel
**197-mal**; sie ist der mit Abstand häufigste Eingriff der Stufe 2.

### B4 — Die Kantenkonfidenz sättigt

Alle Kanten sicherer Seiten haben `konfidenz: 1.0`. Ursache ist numerisch: `float32`
sättigt jenseits von etwa ±17 im Logit-Raum. Als Gütemaß unbrauchbar. Ersetzt durch
die vorzeichenbehaftete **Logit-Marge** (`marge_fuer`), die nicht sättigt.
`schwaechste_kanten()` sortiert danach.

**Eingebaut und bestätigt.** Die frühere Fassung dieses Dokuments führte den Einbau
als „nicht bestätigt" — das war falsch.

### B5 — OTSL ist auffindbar (**widerlegt eine Annahme**)

Erwartet worden war, dass OTSL-Chunks im Vektorindex abstürzen. Gemessen:

```
zimbardo:0:004 (OTSL)                Rang 1 von 13,  Ähnlichkeit 0,905
dieselbe Tabelle als Prosa                           Ähnlichkeit 0,911
```

Differenz 0,006 — Rauschen. E5 liest durch die Marken hindurch, weil die
Zellinhalte gewöhnliche Wörter sind. **Stufe 4b ist für Tabellen mit sprechenden
Zellinhalten nicht belegt.** Einschränkung: die zweite Tabelle derselben Seite (fast
nur Zahlen) landet auf Rang 5 bei 0,816. Vermutung, ungeprüft: Zahlentabellen
brauchen die Anreicherung, Begriffstabellen nicht.

### B6 — Isolierte Formeln sind im Index tot

Vier von 13 Chunks lagen unter 120 Zeichen, drei davon alleinstehende LaTeX-Formeln
aus dem Tietze. Eine natürlichsprachliche Frage trifft `\frac{4kT}{R}` nicht, und
der Chunk trägt keinen Satz, der erklärte, wovon die Formel handelt.

### B7 — Die frühere Messung war gesättigt (**Konstruktionsfehler**)

R@3 = 1,00, MRR = 0,917 bei 13 Chunks aus **zwei völlig verschiedenen Büchern**. Das
Modell musste nicht die richtige Stelle finden, nur das richtige Fach. Zufall läge
bei R@3 ≈ 0,23. Experiment A (mit/ohne Überschriftenpfad) lieferte **Ziffer für
Ziffer identische** Ergebnisse, weil von 13 Chunks genau einer einen Pfad trug.

**Teilweise behoben:** mit 222 Seiten liegt jetzt ein zusammenhängender Korpus aus
einem Buch vor. Die Messung selbst ist noch nicht wiederholt worden.

### B8 — Eingezogene Zwischentitel werden nicht erkannt

Auf der Tietze-Seite: null Überschriften, obwohl „Ohmscher Widerstand:",
„Bipolartransistor:" vorhanden sind. Sie stehen fett am Absatzanfang, ohne eigene
Zeile, und bilden keine eigene Region. Der Detektor klassifiziert sie als `text` —
geometrisch korrekt, strukturell falsch. Typisch für Fachliteratur.

**Am Vollkorpus tritt das Problem nicht auf:** 387 `paragraph_title`, nur 32 von 222
Seiten ohne jede Überschrift. Das Problem ist buch-, nicht modellabhängig.

### B9 — E5-Ähnlichkeitswerte sind komprimiert

Ein inhaltlich unbeteiligter Chunk erreicht 0,837 auf eine Frage nach Weber'schen
Konstanten; der richtige Treffer 0,905. **Absolutwerte bedeuten nichts, nur die
Rangfolge zählt.** Ein Schwellenwert („ab 0,8 relevant") wäre ein Filter, der alles
durchlässt.

### B10 — Der Korpus in Zahlen

2657 Blöcke auf 222 Seiten, 12,0 je Seite.

| Klasse | n | | Strom | n | | Textformat | n |
|---|---|---|---|---|---|---|---|
| `text` | 1667 | | haupt | 2185 | | klartext | 2581 |
| `paragraph_title` | 387 | | boilerplate | 405 | | bild | 63 |
| `header` | 205 | | apparat | 65 | | otsl | 7 |
| `number` | 197 | | marginalie | 2 | | datenreihe | 5 |
| `image` | 62 | | | | | latex | 1 |
| `reference` | 38 | | | | | | |
| `figure_title` | 37 | | | | | | |

Weiter: `vision_footnote` 21, `doc_title` 9, `content` 9, `table` 7,
`reference_content` 6, `chart` 5, `footer` 2, `aside_text` 2, `footer_image` 1,
`abstract` 1, `inline_formula` 1.

Bemerkenswert: **15 % aller Blöcke sind Kopfzeilen und Seitenzahlen** — und damit
15 % der Modellzeit für Boilerplate.

**19 Seiten haben keinen Hauptstrom.** Sie treten in Paaren auf (51/52, 84/85,
122/123, 141/142, 173/174) und sind Literaturseiten: ein `header` „Literatur", eine
`number` und ein einziger langer `reference`-Block. Ohne E19 wären sie im Export
leer.

### B11 — Die Gliederung trägt, die Ebenen kommen aus der Nummer

163 von 396 Überschriften tragen eine Gliederungsnummer, verteilt auf
**12 / 55 / 96** über die Ebenen 1 / 2 / 3 — eine saubere Buchpyramide.

Die 233 unnummerierten sind keine verpassten Fachüberschriften, sondern Titelei
(`Vorwort`, `Inhaltsverzeichnis`), wiederkehrende Lehrbuchelemente
(`? Kontrollfragen`) und Satzartefakte (`Sozial-psychologie`, vermutlich ein
Buchrücken). Die Nummerierung erfasst genau den Teil, der eine Hierarchie hat.

### B12 — Bildunterschriften stehen **seitlich** (**widerlegt eine Annahme**)

Erwartet worden war „darunter, waagerecht bündig". Gemessen an zwölf Fällen: **elf
stehen seitlich neben der Abbildung**, in der Marginalspalte, mal links, mal rechts.
Senkrechte Überlappung 0,80 bis 1,00, waagerechte Lücke 39 bis 471 px, waagerechte
Überlappung **null**. Die eine Ausnahme (`Tab. 5.1`) steht **über** der Tabelle.

Zwischen „passt vollständig" und „passt gar nicht" liegt nichts: keine einzige
waagerechte Überlappung zwischen 0 und 1. Das ist keine Verteilung, bei der eine
Schwelle knapp danebenliegt — es sind zwei verschiedene Satzentscheidungen.

**Daraus folgt E23 und E25:** die Zuordnung ist kein deterministisches Problem. Sie
gehört vor ein Bildmodell.

### B13 — `DoclingDocument` kann mehr als angenommen

Geprüft an der installierten Fassung **docling-core 2.95.0**, nicht erinnert:

| Fund | Bedeutung |
|---|---|
| `ContentLayer` hat **fünf** Werte: `body`, `furniture`, `background`, `invisible`, `notes` | Drei der vier Ströme haben ein natives Ziel. `DEFAULT_CONTENT_LAYERS` ist `{BODY}` |
| `BoundingBox` trägt `coord_origin`, Default **`TOPLEFT`**, dazu `to_bottom_left_origin()` | Unser `oben_links` überlebt den Übergang; nur die Einheit muss nach Punkt |
| `DocItem.prov` ist eine **Liste** von `ProvenanceItem(page_no, bbox, charspan)` | Ein seitenübergreifender Absatz behielte die Seitenzuweisung zeichengenau (siehe E24) |
| `add_inline_group()` existiert | A13 wäre darstellbar; ungelöst bleibt die **Lokalisierung** im erkannten Text |
| `PictureTabularChartData(title, chart_data: TableData)` | Die Datenreihe aus `Chart Recognition:` hat ein natives Ziel statt Freitext |
| `parse_otsl_table_content(otsl) -> TableData` in `docling_core.types.doc.utils` | Kein eigener OTSL-Parser nötig |
| **`TextItem` lässt nur 14 der 31 `DocItemLabel` zu** | `document_index` etwa ist ausschließlich auf einem `TableItem` gültig. Siehe Falle 9 |
| `add_page()` zählt Seiten **ab 1**, PyMuPDF ab 0 | Umrechnung an genau einer Stelle: `SeitenBefund.seite_menschlich` |

### B14 — A11 ist erledigt

**7 von 7 OTSL-Blöcken parsen fehlerfrei** nach `TableData`, Median 15 × 6 Zellen,
kein Block ohne Marken. Der Zweig braucht keinen Fallback, nur einen Wächter. Auch
5 Diagramme und **eine** Formel im ganzen Buch: dieser Korpus ist Fließtext, kein
Formelapparat.

### B15 — Der Token-Deckel schneidet still ab (**der wichtigste Fund dieser Etappe**)

`content` und `reference` standen nicht in `MAX_TOKENS_FUER` und bekamen den
Standardwert 1024. Das reicht für Deutsch etwa 3200 Zeichen.

**45 Blöcke liegen über 2000 Zeichen, der längste bei genau 3198.** Elf der fünfzehn
längsten enden mitten im Wort oder mitten in einer Literaturangabe
(`…Winslow, M. P. & Fried, C. B. (19`), alle zwischen 2982 und 3198 Zeichen. Das ist
der Deckel, kein Textmerkmal.

Konkrete Folge: **im Inhaltsverzeichnis fehlte das gesamte Kapitel 9.** Der Verlust
wäre in einem RAG-Index unsichtbar geblieben — die Chunks lesen sich flüssig, sie
hören nur früher auf.

Behoben durch drei Änderungen an `erkennung.py`: `finish_reason` auswerten,
`"length"` als Warnung in den Befund schreiben, Deckel für `content`, `reference`,
`table` und `text` anheben. **Der Nachlauf über die 23 betroffenen Seiten stand zum
Zeitpunkt dieser Übergabe noch aus.**

### B16 — Zwei Einzelfälle im Korpus

- **S119 #8 halluziniert:** `'…Forderung, in den Forderung, in den Forderung, in den'`
  — eine Wiederholungsschleife. Hier hat der Deckel als Sicherung funktioniert und
  den Schaden begrenzt. **Das Anheben des Deckels macht es an dieser Stelle
  schlimmer.** Braucht einen Blick von Hand.
- **S202 #3 ist ein `paragraph_title` mit 3052 Zeichen.** Eine Überschrift von 3000
  Zeichen ist keine. Detektorfehler, der sich in 4a als absurde Gliederungsebene
  niederschlägt.

### B17 — Ergebnis der Stufe 4a am Vollkorpus

```
222 Seiten, 2645 Elemente
  396 Überschriften, 5 Tabellen, 3 Diagramme, 63 Abbildungen, 1 Formeln
  4 Bildunterschriften zugeordnet, 8 Blöcke entdoppelt
  8 Warnungen
```

Die Gegenrechnung geht auf: 2657 − 8 entdoppelte − 4 als Unterschrift eingehängte =
2645. Tabellen 7 − 2, Diagramme 5 − 2, Abbildungen 62 + 1. Alle 8 Warnungen sind
Entdopplungsmeldungen; keine OTSL-, Datenreihen- oder Leermeldung.

Die 21 ineinanderliegenden Paare auf 13 Seiten setzen sich zusammen aus:
`paragraph_title in text` 6, `text in text` 4, `reference in text` 4,
`table in table` 2, `chart in chart` 2, `reference_content in text` 2,
`inline_formula in text` 1. Entdoppelt werden nach E22 nur die 8 mit identischem
Label.

**Die 4 zugeordneten Bildunterschriften stammen aus der alten, gescheiterten
Regel.** Nach dem Umbau auf E23 ist die Zahl noch nicht neu gemessen; nach
Augenmaß der Stichprobe sollten es rund elf von zwölf sein.

---

## 5. Datenmodell: zwei Schichten

### Warum `DoclingDocument`

Recherchierte Alternativen und warum sie nicht passen:

- **METS + ALTO** (Library of Congress) ist der Standard der Massendigitalisierung.
  ALTO wurde jedoch gebaut, um das ursprüngliche Erscheinungsbild rekonstruierbar zu
  machen — Regionen, Wortkoordinaten, Maße in 1/10 mm. Es kennt keine Tabelle als
  Datenstruktur und keine Formel als LaTeX. Falsches Werkzeug für
  Weiterverarbeitung, richtiges für Archivierung.
- **TEI** ist reicher annotierbar, aber ein eigenes Universum ohne Anbindung an die
  KI-Werkzeuglandschaft. **JATS/BITS** ist Verlagswelt.

Für `DoclingDocument` sprechen die Ströme als `ContentLayer`, der vorhandene
OTSL-Parser, das veröffentlichte JSON-Schema und die Anbindung an LangChain,
LlamaIndex und Haystack. Einzelheiten in B13.

### Die Schichten

| Schicht | Format | Rolle | Ablage |
|---|---|---|---|
| Arbeitsformat | `SeitenBefund` (eigen) | **Beobachtung** — alles Gesehene samt Widersprüchen und konkurrierenden Kandidaten | `data/interim/befunde/<buch>/<seite>.json` |
| Kanonisch | `DoclingDocument` | **Entscheidung** — eine Region, ein Label, ein Text | `data/processed/dokumente/<buch>.json` |
| Ausgabe | Markdown, HTML | abgeleitet, **nie von Hand gepflegt** | `data/processed/md/<buch>.md` |

Was `DoclingDocument` nicht kann und deshalb im Arbeitsformat bleibt: konkurrierende
Kandidaten mit Score, das native `pp_label`, `text_quelle`, die Kantenmarge, die
Laufspuren.

### Aufgabenteilung der Stufe 4

| Stufe | Inhalt | Modell | prüfbar |
|---|---|---|---|
| 4a | Entdopplung, Hierarchie aus Gliederungsnummern, OTSL → `TableData`, Datenreihe → `PictureTabularChartData`, Abbildung auf `DoclingDocument`, Provenienz | **keins** | ja, gegen Goldset |
| 4b | **Bildunterschriften zuordnen**, Zusammenfassung von Zahlentabellen und Diagrammen, Bildbeschreibung, Typisierung der Kästen ohne Klasse | Gemma 4 12B o. ä. | nein, keine eindeutig richtige Form |

Diese Trennung ist der Kern: Deterministisches und Generatives auseinanderzuhalten
hält den prüfbaren Teil prüfbar. Dieselbe Logik, aus der der Detektor nicht durch
ein VLM ersetzt wurde.

`kanonisch.py` liefert die Arbeitsliste für 4b bereits mit:
`bericht.offene_unterschriften` als `(Seite, Unterschrift-Blockid,
Objekt-Blockids)`. Die Ausschnitte liegen als PNG vor, die Kandidatentexte in den
Befunden — es muss nichts neu berechnet werden.

---

## 6. Anforderungen (fachlich, EARS)

Ziel der abgeschlossenen Etappe: **ein vollständiges Buch durchgehend digitalisieren
und nach Markdown wandeln.**

### Stapelverarbeitung

| # | Anforderung | Stand |
|---|---|---|
| A1 | Das System soll alle Seiten eines Dokuments in einem Lauf verarbeiten. | erfüllt |
| A2 | Wenn ein Lauf abbricht, soll das System beim Wiederaufsetzen bereits fertiggestellte Seiten überspringen. | erfüllt |
| A3 | Wenn die Verarbeitung einer Seite fehlschlägt, soll das System die Seite überspringen, den Fehler dem Seitenbefund beifügen und mit der nächsten fortfahren. | erfüllt |
| A4 | Das System soll je Seite die verbrauchte Zeit und die verwendete Modellversion festhalten. | erfüllt (`Laufspur`) |

Alle vier sind gegen Attrappen geprüft (`probelauf_stapel.py`): erzwungene Fehler in
Stufe 1 und 2, Wiederaufsetzen, erneutes Scheitern, Schließen der Lücke.

### Kanonisches Dokument

| # | Anforderung | Stand |
|---|---|---|
| A5 | Genau ein kanonisches Dokument je Buch. | erfüllt |
| A6 | Lesereihenfolge über Seitengrenzen hinweg fortführen. | erfüllt |
| A7 | Absatz über eine Seitengrenze zu einem Element zusammenfassen. | **verworfen** (E24) |
| A8 | Jedem Element seinen Ursprung mitgeben: Quelldatei, Seite, Rechteck. | erfüllt |
| A9 | Boilerplate vom Lesefluss ausnehmen, ohne sie zu verwerfen. | erfüllt (`FURNITURE`) |

### Lesbare Ausgabe

| # | Anforderung | Stand |
|---|---|---|
| A10 | Tabellen als lesbare Markdown-Tabellen ausgeben. | erfüllt |
| A11 | Nicht überführbare Tabellenausgabe unverändert erhalten und die Seite kennzeichnen. | erfüllt; am Korpus nie ausgelöst (B14) |
| A12 | Abgesetzte Formeln dem einführenden Absatz zuordnen. | teilweise — die Formel bleibt eigenes Element an ihrer Stelle |
| A13 | Inline stehende Formeln an ihrer Fundstelle zurückführen. | **zurückgestellt** (E24, B13) |
| A14 | Abbildungen als Datei ablegen und im Dokument darauf verweisen. | erfüllt (`ImageRef`) |
| A15 | Für alle Seiten und Bücher dieselbe Gliederung erzeugen. | erfüllt — ein Codepfad |

### Nachvollziehbarkeit

| # | Anforderung | Stand |
|---|---|---|
| A16 | Für jede Aussage den Rückweg zur Fundstelle offenhalten. | erfüllt — fällt aus der Provenienz ab |
| A17 | Sofern eine zweite Quelle vorliegt, die Übereinstimmung je Element festhalten. | **offen** |
| A18 | Ohne zweite Quelle das Element als unverankert kennzeichnen. | **offen** |

> **A18 betrifft den gesamten Tietze.** Auf Scans ist das VLM die einzige Quelle.
> Eine flüssig lesbare, fachlich plausible Ausgabe ist dort genau der Fall, in dem
> sich richtig und überzeugend nicht unterscheiden lassen.

---

## 7. Offene Fragen

### Unmittelbar

| # | Punkt |
|---|---|
| U1 | **Nachlauf für die 23 Seiten mit abgeschnittenen Blöcken** (B15). Danach prüfen, ob Kapitel 9 im Inhaltsverzeichnis wieder vollständig ist |
| U2 | **S119** (B16): Wiederholungsschleife. Der angehobene Deckel verschlimmert sie |
| U3 | **S202** (B16): 3052-Zeichen-`paragraph_title`. Ein Wächter in `kanonisch.py` — Überschriften über einer Zeichengrenze als Text ablegen und melden — ist vorgeschlagen, aber **nicht entschieden und nicht gebaut** |
| U4 | Nach dem Umbau auf E23: wie viele der 37 Bildunterschriften werden jetzt zugeordnet? |
| U5 | Notebook 4 (Chunking und Index) ist noch nicht auf die Module umgestellt |

### Messung

| # | Frage | Weg zur Klärung |
|---|---|---|
| M1 | Der Korpus war zu klein und heterogen (B7) | **erledigt** — 222 Seiten aus einem Buch liegen vor |
| M2 | Sechs Prüffragen reichen nicht | Auf 25–30 erweitern, davon bewusst schwierige: Antwort über zwei Seiten verteilt, Suchbegriffe nicht wörtlich im Zielchunk |
| M3 | Der Marker-Trick prüft Anwesenheit, nicht Relevanz | Ein Chunk, der `0,003` zufällig enthält, zählt als Treffer |
| M4 | Trägt der Überschriftenpfad? | Experiment A wiederholen, jetzt mit 396 echten Überschriften statt einer |
| M5 | **Die Kernthese ist ungeprüft** | Zweiter Index: `page.get_text()`, alle 800 Zeichen geschnitten, keine Metadaten. Dieselben Fragen. Besonders am Tietze, wo der Textlayer die Lüge ist |
| M6 | Hybrid mit BM25 | Vektorsuche versagt bei Eigennamen und Zahlen |

**M5 ist die wichtigste.** Das ganze Projekt behauptet, dass Layout-Analyse dem
Retrieval nützt. Belegt ist das nicht.

### Fachlich

| # | Frage |
|---|---|
| F1 | Eingezogene Zwischentitel (B8) — über Fettung im Textlayer erkennbar? Über ein Modell? |
| F2 | Kästen ohne Klasse („Für die Praxis", „Definition") — Vektorobjekte aus PyMuPDF als deterministischer Regionsnachweis. Am Vollkorpus vermutlich die Ursache eines Teils der 37 `figure_title` |
| F3 | Überlappende Detektionen | **entschieden** (E22): identisches Label entdoppeln, gemischte stehen lassen |
| F4 | Verschachtelung: ein Kasten mit zwei inneren Spalten. `DoclingDocument` kennt Gruppen — reicht das? |
| F5 | Formelvalidierung: die Tietze-Formeln sind in sich stimmig. Prüfbar gegen die Definitionen, die daneben stehen |
| F6 | Zahlentabellen gegen Begriffstabellen (B5) — braucht nur die erste Sorte Anreicherung? |
| F7 | Beschleunigung: parallele Anfragen an LM Studio; Verzicht auf Modellaufrufe für Boilerplate (15 % der Blöcke); Textlayer statt VLM für born-digital — Letzteres widerspricht B1 |

---

## 8. Bekannte Fallen

Alle bereits einmal getreten. Nicht erneut nötig.

| # | Falle | Symptom | Ursache |
|---|---|---|---|
| 1 | `onnx.load()` in `onnxruntime` | `AttributeError` | Zwei verschiedene Pakete. Signatur aus der `InferenceSession` lesen |
| 2 | Fest verdrahtete Provider | Ausnahme beim Öffnen | Auf dem Mac gibt es kein CUDA. Gegen `get_available_providers()` filtern |
| 3 | Falscher ONNX-Export | `KeyError` auf `order_logits`, oder ein einzelner `(300,7)`-Tensor | Zwei Exporte mit unvereinbaren Verträgen (E2) |
| 4 | Fehlende `mmproj` | HTTP 400, „model does not support images" | GGUF braucht beide Dateien im selben Ordner |
| 5 | **Falsches Modell in LM Studio geladen** | HTTP 400 auf jeder Seite | `Erkenner` ohne `modell_id` nimmt das erste geladene. Steht ein Einbettungsmodell daneben, greift es das falsche |
| 6 | **`raise_for_status()` verwirft den Antwortkörper** | 400 ohne Begründung | Der Grund steht in `antwort.text`. Erst nach dem Umbau sichtbar |
| 7 | **Token-Deckel schneidet still ab** | Ausgabe liest sich flüssig, hört früher auf | `finish_reason == "length"` auswerten (B15) |
| 8 | E5-Präfixe vertauscht | Qualitätsverlust ohne Fehlermeldung | Die **Instruct**-Variante will bei Dokumenten **kein** Präfix und bei Anfragen `Instruct: {Aufgabe}\nQuery: {…}`. Die Nicht-Instruct-Variante will `passage:`/`query:` |
| 9 | **`DocItemLabel` ≠ zulässiges Label** | `ValidationError` mitten im Buch | `TextItem` lässt nur 14 der 31 Werte zu. Zulässigkeit aus dem Modell auslesen, nicht erinnern |
| 10 | Chunk über 512 Tokens | funktioniert scheinbar | Wird stillschweigend abgeschnitten. Die zweite Hälfte ist nie durchsuchbar |
| 11 | `float32`-Sättigung | alle Konfidenzen 1,0 | Im Logit-Raum rechnen (B4) |
| 12 | Fester Ausschnittsrand | Nachbartext im Ergebnis | 8 px sind bei einer 31 px hohen Seitenzahl ein Viertel der Bildhöhe. Proportional zur Boxhöhe, beidseitig gedeckelt |
| 13 | Überschrift mitten im Chunk | leerer Überschriftenpfad | Eine Überschrift muss einen neuen Chunk beginnen und ihn anführen |
| 14 | **Arbeitsverzeichnis** | Ordner landen eine Ebene zu hoch | Jupyter startet im Ordner der Datei, VS Code startet `.py` im Workspace-Ordner (E26) |
| 15 | **`Path.glob` auf fehlendem Ordner** | leere Liste, kein Fehler | Ein falscher Pfad meldet sich nicht, er liefert null Treffer |
| 16 | **Verschieben von `ausschnitte/`** | 63 leere Bildverweise, kein Absturz | `blk.ausschnitt` steht relativ in den Befunden. Nach dem Umzug umschreiben |
| 17 | **Doppelte Formeldelimiter** | `$$$…$$$` im Markdown | Stufe 2 legt `$…$` ab, docling setzt beim Export eigene. Vor `add_formula` abstreifen |
| 18 | **`\b` nach einem Punkt** | regulärer Ausdruck greift nie | `tab\.\b` matcht nicht, weil zwischen `.` und Leerzeichen keine Wortgrenze liegt |

---

## 9. Umgebung und Ablage

### Laufzeitumgebung

- Python 3.12, `pymupdf`, `pdfplumber`, `pydantic`, `opencv-python-headless`,
  `numpy`, `onnxruntime`, `requests`, **`docling-core` ≥ 2.95**
- LM Studio mit lokalem Server auf Port 1234, OpenAI-kompatible Schnittstelle
- Modelle: PaddleOCR-VL-1.5 (MLX auf Mac: `mlx-community/paddleocr-vl-1.5`;
  GGUF + mmproj auf Windows), `text-embedding-multilingual-e5-large-instruct`,
  Gemma 4 12B (für 4b vorgesehen)
- `models/pp_doclayoutv3.onnx` (134 MB)
- Kein Docker, kein WSL, kein PaddlePaddle, kein vLLM — ausdrückliche Randbedingung
- Zwei Arbeitsmaschinen: Windows mit Dual-GPU (40 GB VRAM), Mac M4 Pro mit 24 GB

### Ordnerstruktur

```
M7b_DocumentExtraction/
├── 00_steuerung.ipynb          ← einziger Einstiegspunkt
├── 01…04_*.ipynb               didaktische Originale
├── schema.py  layout.py  erkennung.py
├── stapel.py  kanonisch.py  sichtung.py
├── probelauf_stapel.py
├── werkzeugskripte/            zum Hineinkopieren, nicht zum Ausführen
├── models/                     pp_doclayoutv3.onnx
└── data/
    ├── raw/                    Quell-PDFs
    ├── interim/
    │   ├── befunde/            <buch>/<seite:04d>.json
    │   ├── ausschnitte/        PNG je Bildblock
    │   └── kontrolle/          Overlay-Bilder
    └── processed/
        ├── dokumente/          <buch>.json
        ├── md/                 <buch>.md
        └── index/              chunks.json + .npy
```

Nach **Cookiecutter Data Science** (E27). Tragende Regel: Rohdaten werden nie
überschrieben.

### Arbeitsweise

**Notebooks führen aus, `.py`-Dateien werden importiert.** Wer eine `.py` direkt
startet, bekommt das falsche Arbeitsverzeichnis (Falle 14). Abschnitt 0 des
Steuerungsnotebooks meldet das sichtbar, statt es stillschweigend richtigzustellen.

Diese Regel ist auch didaktisch begründet: das Material wird an 38 Studierende über
Teams ausgegeben, und eine Anleitung zur `launch.json` wäre dort nicht betreubar.

### Für die Nachfolge-Sitzung mitzugeben

**Sofort:** dieses Dokument, `schema.py`, `kanonisch.py`, `00_steuerung.ipynb`,
ein `befunde/<buch>/0000.json` als Beispiel eines vollständigen Befunds.

**Auf Anforderung:** `layout.py` und `erkennung.py` (nur nötig, wenn an Stufe 1
oder 2 gearbeitet wird), `sichtung.py`, `stapel.py`, die didaktischen Notebooks.

---

## 10. Reihenfolgevorschlag

1. **U1** — Nachlauf für die 23 Seiten, dann Inhaltsverzeichnis prüfen. Das ist der
   einzige bekannte inhaltliche Fehler im Korpus.
2. **U4** — die Zahl der zugeordneten Bildunterschriften nach E23 messen, damit die
   Arbeitsliste für 4b belastbar ist.
3. **U3** — entscheiden, ob der Überschriftenwächter gebaut wird.
4. Notebook 4 auf die Module umstellen (**U5**), Chunking gegen den echten Korpus.
5. Prüfset erweitern (**M2**), Experiment A wiederholen (**M4**).
6. **M5** — der Vergleich gegen naives Chunking. Der wichtigste offene Punkt des
   ganzen Projekts.
7. Erst danach **4b**, und nur für das, was M5, B5 und B6 als Lücke ausweisen. Die
   Bildunterschriften sind dort die erste und am besten umrissene Aufgabe.
