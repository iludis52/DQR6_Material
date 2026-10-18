# Transformer-Werkbank: erster interaktiver Entwurf

Einstieg: `Lernapp/transformer-werkbank.html`.

Die App verbindet eine Gesamtübersicht mit einzeln untersuchbaren Rechenschritten.
Sie ergänzt das Lehrnotebook und die vorhandene BPE-Werkbank. Die vorhandenen
Notebooks und Lernapps wurden dafür nicht verändert.

## Bedienung und Lernweg

1. **Aufbau:** Zwei vollständige Transformer-Blöcke stehen untereinander:
   Block 1 grünlich, Block 2 violett. Jeder farbige Bereich umfasst drei parallele
   Attention-Köpfe, ein FFN, Normierungen und zwei Residualadditionen. Die Blöcke
   werden nacheinander durchlaufen. Die Blockstruktur entspricht dem Pre-Norm-Decoder
   aus dem Notebook; nur Zahl und Größe der Bauteile sind reduziert.
2. **Vorwärtslauf:** Mit „Weiter“ oder „Abspielen“ durch den Datenfluss gehen.
   Bewegte Linien markieren den jeweiligen Übergang. Vektoren und Tabellen zeigen
   die tatsächlich berechneten Werte. Abspielen führt keine Gewichtsupdates aus.
3. **Attention:** Eine Tokenposition und einen Kopf wählen. Q, K und V, ein
   ausgerechneter Score, die maskierte Attentionmatrix und das Zusammenführen der
   Kopfoutputs sind sichtbar. Die drei Köpfe sind in beiden Blöcken einzeln
   anklickbar. Die Auswahl kennzeichnet Block und Kopf im Diagramm und in den Detailwerten.
4. **Training:** Eingabe und verschobene Ziele vergleichen. Den Verlust betrachten,
   dann Backward aufrufen und erst danach das Gewichtsupdate auslösen. Die
   Updateansicht zeigt Gewichte, ihre Gradienten, die geplanten/neuen Werte und
   den erneut berechneten Verlust. Weitere Trainingsschritte lassen sich wiederholen.
5. **Generierung:** Das wahrscheinlichste Token an den Kontext anhängen und erneut
   vorwärts rechnen. Endtoken und Kontextgrenze beenden die Generierung. Die bis
   dahin trainierten Gewichte bleiben beim Wechsel zwischen den Ansichten erhalten.

Die **blauen Residualpfade** sowie die Pluszeichen sind anklickbar. Ein eigener
Erklärschritt zeigt den unveränderten Eingang, den berechneten Beitrag und ihre
komponentenweise Summe. Im ersten Block ist der Eingang bereits die Summe aus
Token- und Positions-Embedding; die Residualaddition fügt das Positions-Embedding
nicht erneut hinzu. Im zweiten Block wird der Ausgang des ersten Blocks weitergereicht.
Die blauen Pfade enthalten weder LayerNorm noch lernbare Gewichte. Die orangefarbenen
Gradientenpfeile bleiben davon unterscheidbar.

Die Navigation bleibt am oberen Bildschirmrand erreichbar; die Erklärung bleibt
auf breiten Bildschirmen beim Scrollen neben den Blöcken sichtbar. Auf schmalen
Bildschirmen steht sie vor dem seitlich verschiebbaren Gesamtplan.

Die Gradientenpfeile im Gesamtplan zeigen einen schematischen Rückweg. Die
Ableitungen selbst werden durch automatische Differenzierung des tatsächlichen
Rechengraphen berechnet, einschließlich aller Residualzweige und Weight tying.

## Was gerechnet und was vereinfacht wird

Es handelt sich um ein kleines, eigenständiges Modell mit reproduzierbar zufälligen
Startgewichten. Es werden keine GuppyLM-Checkpoints geladen. Alle angezeigten
Zahlen, Gradienten und Verluständerungen stammen aus diesem Modell.

| Merkmal | Lehrmodell in der App | Notebook, Grundkonfiguration |
|---|---|---|
| Blöcke | 2, jeweils eigene Gewichte | 6 |
| Modellbreite | 6 | 384 |
| Attentionköpfe | 3 pro Block, Breite je Kopf 2 | 6 pro Block, Breite je Kopf 64 |
| FFN | 6 → 24 → 6, GELU | 384 → 1536 → 384, GELU |
| Tokenisierung | 8 feste Wort-/Endtokens | trainierter Byte-Level-BPE-Tokenizer |
| Positionen | gelernte Tabelle, Kontext 8 | gelernte Tabelle, Kontext 128 |
| Ausgabe | an Token-Embedding gebunden | ebenso |
| Optimierer | SGD, konstante einstellbare Lernrate | AdamW, Lernratenplan, Gradient Clipping |
| Beispiele | ein ausgewähltes Beispiel je Update | zufällige Batches aus dem Datensatz |
| Weitere Vereinfachungen | keine ChatML-Rollen, kein Padding, kein Dropout | ChatML, rechtes Padding, Dropout im Training |

Die Kreise im FFN sind eine verkleinerte Darstellung der Einheiten. Sie bilden
noch keine vollständige neuronale Detailansicht aller Modellbausteine ab.

## Bereitstellen

Diese vier Dateien gemeinsam in dasselbe Verzeichnis des Webservers kopieren:

- `transformer-werkbank.html`
- `transformer-werkbank.css`
- `transformer-werkbank.js`
- `transformer-modell.js`

Die vorhandene `tokenizer-werkbank.html` sollte für den Rückverweis im selben
Verzeichnis liegen. Die App benötigt keinen Build, kein Backend, kein CDN und
keine Paketinstallation. Sie lässt sich auch direkt als lokale HTML-Datei öffnen.
Es werden keine Daten übertragen und keine Lernstände dauerhaft gespeichert.

## Prüfung

`node pruefe_transformer.js` prüft Dimensionen, Attentionnormierung und kausale
Abschirmung in beiden Blöcken und die beiden Residualadditionen je Block.
Numerische Ableitungen prüfen Backpropagation
an Token-/Positions-Embeddings, QKV, Ausgabeprojektion, FFN und Normierungen.
Backward lässt die Gewichte unverändert. Ein SGD-Update mit η = 0,03 senkt beim
ersten Lehrbeispiel den Verlust von etwa 2,350745 auf 2,029087.

Zusätzlich werden alle Lehrbeispiele und der maximale Generierungskontext geprüft.
Browserprüfungen betreffen die Ansichten, Attentionauswahl, den vollständigen
Trainingsschritt, Beispielwechsel, Rücksetzen und das Anhängen eines Tokens.

## Nächste didaktische Ausbaustufe

Die geplante zweite Ebene kann auf diesem Rechenkern aufbauen: einzelne
Vektorkomponenten als Kreise, Verbindungen mit zugehörigen Gewichten, getrennte
Q/K/V-Projektionen und ein vollständig aufgelöster Attentionkopf. Sinnvoll ist
eine eigene fokussierte Ansicht mit Rückverweis auf den jeweiligen Ort im Gesamtplan.
