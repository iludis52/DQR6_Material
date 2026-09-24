# Offene Punkte

Stand: 24.09.2026. Gefunden beim Bau von `05_layout_einblick.ipynb` an der
Testseite `data/raw/Wahrnehmungspsychologie_Extracted.pdf` (Lehrbuchseite mit
Marginalspalte, Kasten, Bild mit Umfluss).

Zum Wiederaufnehmen: Befund im Layout-Viewer ansehen (Notebook 05, Teil B)
oder den HTML-Bericht `data/interim/kontrolle/<dok>_layout.html` öffnen.
Die Auffälligkeiten-Regeln stehen in `python/pdf_extraction/einblick.py`.

---

## Erledigt am 24.09.2026

| Nr. | Problem | Lösung |
|---|---|---|
| 3 | Bildunterschrift „Abb. 9.3“ verloren: Sicherheit verteilt auf `figure_title` 0.45 und `vision_footnote` 0.45, keine Einzelklasse erreicht 0.5 | Zweiter Durchgang in `layout.dekodieren()`: Familienrettung über `RETTUNGS_FAMILIEN` (Bildbezug, Überschriften, Formeln), p = 1 − Π(1 − pₖ). Neues Feld `Block.familien_score`, Vermerk in `warnungen`. Abschaltbar mit `familien_retten=False`. |
| 4 | `zusammengefuehrt_aus` verwies auf Block-ids der Stufe 1, die nach dem Überschreiben durch Stufe 2 nicht mehr existieren | Neues Feld `Block.zusammengefuehrt_queries` (Query-ids, über alle Stufen stabil). Die Meldung nennt jetzt Query-ids. Das alte Feld bleibt aus Kompatibilitätsgründen. |

**Noch zu prüfen:** Die Familienrettung ist nur an einer Seite getestet. Vor
einem großen Lauf an mehreren Büchern mit `familien_retten=True/False`
vergleichen: Wie viele Blöcke kommen dazu, und sind es echte Elemente?

---

## Offene Bugs

### 1. Marginalien werden als `text` erkannt und stören den Haupttext (hohe Priorität fürs RAG)

**Beobachtung:** Die Randnotizen der Marginalspalte (#13–#15) und der Verweis
„▶ Definition Prägnanz“ (#17) kommen als `text` statt `aside_text` heraus.
Damit gehören sie zum Strom `haupt`. Die Lesefolge fädelt sie zwischen die
Absätze des Haupttexts ein.

**Folge:** Im Markdown stehen Satzfragmente der Randspalte mitten im
Fließtext. RAG-Chunks bekommen fremde Sätze, und die Zusammenfassung der
Randnotiz gewichtet den Nachbarabsatz doppelt.

**Lösungsidee:**
- Randspalte auf **Dokumentebene** erkennen: eine wiederkehrende, schmale
  x-Spalte außerhalb der Haupttextspalte über viele Seiten. Eine einzelne
  Seite reicht dafür nicht.
- Textblöcke darin kommen in den Strom `marginalie`. `pp_label` bleibt
  unverändert, weil es die Aussage des Modells ist.
- Voraussetzung: `Block.strom` ist heute eine Property, die aus `pp_label`
  abgeleitet wird (`schema.strom_fuer`). Sie muss ein speicherbares Feld
  werden, das eine Regel überschreiben darf, mit Herkunftsvermerk.
- Die Heuristik in `einblick.auffaelligkeiten` („schmal in der Randspalte“)
  ist nur ein Hinweis je Seite und kein Ersatz.

**Benötigt:** mehr Seiten aus dem Wahrnehmungspsychologie-Buch, am besten
20 bis 50.

### 2. Die Lesefolge widerspricht sich selbst (Symptom von Nr. 1)

**Beobachtung:** Kante #16 → #17 mit Marge −548. Die Rangfolge entsteht durch
Stimmenzählung über alle Paare (`layout.lese_raenge`). Der direkte
Paarvergleich sagt aber das Gegenteil. Betroffen ist genau der verkannte
Marginalienverweis.

**Umgang:** Nicht automatisch vertauschen, weil ein lokaler Tausch die
Nachbarbeziehungen verschlechtern kann. Erst Nr. 1 lösen, dann über den
Bestand zählen, wie viele negative Kanten übrig bleiben. Der Viewer markiert
sie rot.

### 5. Zusammenführung kann Spalten verbinden (latentes Risiko)

**Beobachtung:** `erkennung.gruppieren()` hat die zwei Spalten des Kastens
„Für die Praxis“ zu einem Block verbunden: senkrechte Überlappung ≥ 0.5 und
Spaltenabstand < `MAX_LUECKE_PX` (40 px). Die Regel ist für Bruchstücke
*einer* Zeile gedacht. PaddleOCR-VL hat diesmal richtig spaltenweise
gelesen, garantiert ist das nicht.

**Lösungsidee:** Nur zusammenführen, wenn mindestens ein Block einzeilig ist,
etwa über eine Höhe unter rund 2 Zeilenhöhen. Zusätzlich eine Auffälligkeit
„zwei mehrzeilige Blöcke zusammengeführt“.

### Kleinere Beobachtungen

- Die Seitenzahl „112“ (`number`) wurde mit der Kopfzeile zusammengeführt.
  Das ist Boilerplate und fürs RAG harmlos, das Label `number` geht aber
  verloren.
- Die Kastenüberschrift „Benutzerfreundliche Bildschirmmasken“ kommt als
  `text` mit Score 0.56 heraus, `paragraph_title` hatte 0.28.
- Kästen oder Sidebars als *Container* kennt das Modell nicht. Ihr Inhalt
  landet ohne Klammer im Haupttext.

### Designfrage: Namensregel blockiert den ganzen Bestand

`HalbleiterSchaltungstechnik_TietzeSchenk_2002_Extracted.pdf` hat einen Stamm
von 55 Zeichen, erlaubt sind 48 (`pfade.MAX_STAMM`). `lauf.verarbeite_alle`
bricht dann bewusst für *alle* Dokumente ab (SR-04). Zu klären: Soll ein
beanstandetes Dokument nur übersprungen werden statt den Lauf zu blockieren?
Bis dahin die Datei umbenennen, zum Beispiel in
`Halbleiter_TietzeSchenk_2002.pdf`.

---

## Neue Funktion: Chemische Strukturformeln (Wunsch der Chemie-Kollegen)

**Ziel:** Strukturformeln in Lehrbüchern nicht nur als Bild übernehmen,
sondern maschinenlesbar machen, etwa als SMILES oder Molfile. Dazu Name bzw.
Summenformel, damit ein RAG sie finden und ein LLM über sie sprechen kann.

**Ausgangslage in der Pipeline:**
- pp_doclayoutv3 hat **keine Klasse für Strukturformeln**. Sie kommen
  vermutlich als `image`, `chart` oder `display_formula` heraus. Erster
  Schritt: an Beispielseiten mit dem Viewer (Live-Modell) nachsehen, als was
  sie tatsächlich erkannt werden.
- Inline-Summenformeln im Text (H₂SO₄, Reaktionsgleichungen) sind ein
  *anderes* Problem. Das ist OCR bzw. LaTeX, eventuell `mhchem`, und läuft
  über Stufe 2.

**Möglicher Aufbau (noch zu evaluieren):**
1. **Erkennen, ob ein Bildblock eine Strukturformel ist:** ein kleiner
   Bildklassifikator auf `image`- und `chart`-Ausschnitten. DECIMER hat
   einen solchen Klassifikator; ein VLM-Prompt wäre eine Alternative.
2. **Strukturerkennung (OCSR):** Kandidaten sind DECIMER, MolScribe und OSRA.
   Genauigkeit an Lehrbuchgrafiken vergleichen, Lizenzen prüfen.
3. **Plausibilitätsprüfung mit RDKit:** SMILES parsen, Summenformel und
   Molmasse berechnen, das Molekül zurückzeichnen und neben das Original
   stellen. Im Layout-Viewer wäre das eine gute Sichtprüfung.
4. **Ausgabe:** Bild bleibt, dazu SMILES, Summenformel und optional ein Name
   (PubChem-Abfrage, also online) im Markdown bzw. im Bild-Manifest.
5. **Einordnung:** Stufe 2 (`erkennung`, Routing je Klasse) oder Stufe 3
   (Bildoptimierung, dort liegt schon der Bildkontext).

**Schwierige Fälle:** Reaktionsschemata mit Pfeilen und Bedingungen,
Markush-Strukturen (R-Gruppen), Mesomerie, Stereochemie (Keile) sowie
Strukturformeln mitten im Text.

**Benötigt:** eine Handvoll typischer Seiten aus Chemiebüchern der
Kollegen, darunter einfache Moleküle, Reaktionsschemata und Skelettformeln.
Dazu, wenn möglich, die richtigen SMILES als Vergleich.
