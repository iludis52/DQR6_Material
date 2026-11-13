# GuppyLM: Einen Transformer verstehen und trainieren

Aufgabenentwurf zum `guppylm_lehrnotebook.ipynb` – Grundlage für die anschließende didaktische Überarbeitung.

## Ziel und Arbeitsweise

Sie verfolgen den Weg vom Text über die Bauteile eines Transformers bis zur erzeugten Antwort und trainieren das Modell selbst. Das Notebook führt Sie dabei eng durch die Umsetzung. Größere Teile der Architektur müssen Sie nicht selbst programmieren.

Vorausgesetzt werden PyTorch sowie ein Trainingszyklus mit Batches beziehungsweise DataLoader, Gradientenberechnung, Optimierer, Validierung und Early Stopping. Im Mittelpunkt stehen die Besonderheiten des autoregressiven Sprachmodells.

Nach der Bearbeitung können Sie:

- den Datenfluss durch Token- und Positions-Embeddings, Attention, FFN, Residualverbindungen und Ausgabeprojektion erklären;
- begründen, wie Tokenversatz und kausale Maske die Vorhersage des nächsten Tokens ermöglichen;
- das Modell trainieren und Verlustwerte zusammen mit Beispielantworten beurteilen;
- erklären, wie aus den Modellvorhersagen durch Sampling eine Antwort entsteht.

Halten Sie Ihre Ergebnisse kurz in eigenen Worten fest. Bei den Experimenten gilt: **Erwartung formulieren → Versuch durchführen → Beobachtung erklären.** Eine nicht bestätigte Erwartung ist ein Ergebnis, das Sie untersuchen sollen.

Die Unterrichtssprache ist Deutsch. Der mitgelieferte Datensatz enthält englische Fragen und Antworten. Verwenden Sie für die regulären Antworttests deshalb englische Fragen.

## 1. Vom Text zum Trainingsbeispiel

Bearbeiten Sie die Abschnitte 1 bis 3 des Notebooks.

1. Laden Sie den lokalen Datensatz und betrachten Sie ein Beispiel. Markieren Sie Benutzerfrage, Modellantwort und Rollenmarkierungen. Welche Aufgabe erfüllen die Sondertokens?
2. Tokenisieren Sie einen kurzen englischen Satz und vergleichen Sie Textstücke und IDs. Ändern Sie ein Wort und untersuchen Sie die Zerlegung. Prüfen Sie die Rückübersetzung. Warum entspricht ein Token nicht grundsätzlich einem Wort?
3. Notieren Sie die tatsächliche Vokabulargröße. Unterscheiden Sie diese von der beim Tokenizertraining eingestellten Zielgröße.
4. Wählen Sie eine kurze Tokenfolge. Schreiben Sie zunächst selbst die zugehörigen Folgen `x` und `y` auf und vergleichen Sie sie anschließend mit der Notebookausgabe. Benennen Sie für zwei Positionen jeweils Eingabetoken und Zieltoken.
5. Betrachten Sie einen Batch mit unterschiedlich langen Beispielen. Welche Ziele gehen in den Verlust ein? Erklären Sie dabei den Unterschied zwischen einer Token-ID mit dem Wert 0 und der Position 0 einer Sequenz.
6. Lesen Sie die Längenverteilung ab. Unterscheiden Sie die konfigurierte maximale Kontextlänge von der tatsächlichen Länge eines dynamisch gepaddeten Batches. Was bedeutet eine größere tatsächliche Sequenzlänge für die Attention-Berechnung?

**Ergebnis:** Ein kommentiertes Beispiel von Text, Tokens und verschobenen Eingabe-Ziel-Folgen.

## 2. Den Datenfluss durch das Modell verfolgen

Bearbeiten Sie Abschnitt 4 des Notebooks. Verwenden Sie `B` für die Batchgröße, `T` für die Sequenzlänge, `C` für `d_model`, `H` für die Kopfzahl und `V` für die tatsächliche Vokabulargröße.

### 2.1 Embeddings und Ausgabe

1. Welche Form haben die Token-IDs, die nachgeschlagenen Token-Embeddings und die Summe aus Token- und Positions-Embeddings?
2. Warum werden Positionsinformationen benötigt, obwohl die Eingabe als geordnete Folge vorliegt?
3. Welche Form haben die Logits am Ende des Modells? Erklären Sie den Unterschied zwischen Logits und Wahrscheinlichkeiten.
4. Betrachten Sie das Weight Tying: Welche Matrix wird geteilt und welche Parameter werden dadurch eingespart? Warum bedeutet die gemeinsame Matrix nicht, dass die Ausgabeprojektion die mathematische Umkehrung des Embeddings ist?

### 2.2 Attention

1. Beschreiben Sie Query, Key und Value anhand ihrer Rolle in der Berechnung. Verfolgen Sie die Formen beim Aufteilen in Köpfe, beim Berechnen der Attention-Gewichte und beim Zusammenführen der Köpfe.
2. Sagen Sie vor der Beobachtungszelle voraus, auf wie viele Positionen die Positionen 0, 2 und `T-1` zugreifen dürfen. Beachten Sie die Diagonale der Maske.
3. Prüfen Sie Ihre Vorhersage. Warum summiert sich jede Zeile der Attention-Gewichte vor dem Dropout zu 1, obwohl einige Einträge maskiert wurden?
4. Unterscheiden Sie den Einfluss der kausalen Maske von dem Einfluss von `ignore_index` auf die Verlustberechnung.

### 2.3 FFN, Residualverbindungen und Block

1. Welche Informationen werden durch Attention zwischen Positionen ausgetauscht? Welche Dimension verändert das FFN, und welche Positionen verarbeitet es gemeinsam beziehungsweise unabhängig?
2. Zeichnen Sie einen Block mit den beiden Residualadditionen und den vorgeschalteten LayerNorm-Schichten. Tragen Sie die Tensorformen ein.
3. Sagen Sie voraus, ob die Form des Residualstroms beim Durchlaufen eines Blocks verändert wird. Vergleichen Sie diese Aussage mit der gemessenen Änderung seiner Werte. Was zeigt diese Messung, und was zeigt sie nicht?
4. Schätzen Sie vor der Parameterbilanz, welcher Bauteil den größten Anteil enthält. Prüfen und erklären Sie das Ergebnis.

**Ergebnis:** Eine beschriftete Skizze des Gesamtmodells und eines einzelnen Blocks mit den wesentlichen Tensorformen.

## 3. Experiment: Kann das Modell in die Zukunft schauen?

Dieses Experiment findet **vor dem Training** statt. Es untersucht die Architektur und benötigt kein gelerntes Sprachverständnis.

1. Formulieren Sie Ihre Erwartung: Zwei gleich lange Eingaben sind bis einschließlich Position `p` identisch. Nur spätere Tokens unterscheiden sich. An welchen Positionen müssen die Logits bei aktiver kausaler Maske übereinstimmen?
2. Vergleichen Sie beide Eingaben mit demselben Modell im Evaluationsmodus und ohne Gradientenberechnung. Bestimmen Sie die größte absolute Abweichung der Logits bis einschließlich `p`. Verwenden Sie eine kleine numerische Toleranz statt eines Vergleichs auf exakte Gleichheit.
3. Wiederholen Sie den Vergleich mit vorübergehend deaktivierter kausaler Maske. Ändern Sie sonst nichts. Was beobachten Sie?
4. Erklären Sie, warum das Zieltoken für Position `p` während des Trainings bereits in einer späteren Eingabeposition stehen kann. Weshalb ist die Maske für dieses Training erforderlich?
5. Stellen Sie vor dem regulären Training die kausale Maske wieder her.

**Ergebnis:** Erwartung, Messwerte mit und ohne Maske sowie eine Erklärung des Zusammenhangs zwischen Tokenversatz und Kausalität.

## 4. Den Trainingslauf vorbereiten und durchführen

Bearbeiten Sie Abschnitt 5 des Notebooks.

1. Ordnen Sie die bekannten Schritte eines Trainingszyklus im Code zu: Batchbildung, Vorwärtsrechnung, Verlust, Rückwärtsrechnung, Clipping, Optimierung, Validierung und Checkpointspeicherung. Welche davon sind spezifisch für dieses Sprachmodell?
2. Berechnen Sie `ln(V)` mit der tatsächlichen Vokabulargröße. Erklären Sie, warum dies der Kreuzentropieverlust einer Gleichverteilung ist. Vergleichen Sie ihn mit dem gemessenen Startverlust. Warum muss ein zufällig initialisiertes Modell nicht exakt diesen Wert liefern?
3. Lesen Sie den Lernratenverlauf und notieren Sie die Trainingskonfiguration. Halten Sie außerdem Gerät, Schrittzahl und Laufzeit fest.
4. Führen Sie den Trainingslauf aus. Bewahren Sie die Verlustkurve und den besten Checkpoint auf.
5. Beschreiben Sie die Entwicklung der Verluste. Berücksichtigen Sie, dass der Trainingsverlust mit Dropout und wechselnden Gewichten entsteht, die Validierung dagegen ohne Dropout. Ein niedrigerer Validierungsverlust ist deshalb nicht automatisch ein Fehler.
6. Prüfen Sie, wie viele Beispiele tatsächlich für die Validierung verwendet werden. Welche Rolle spielt dieser Split bei der Auswahl des besten Checkpoints?

**Einordnung der Daten:** Im mitgelieferten lokalen Datensatz kommen 2.320 der 3.000 Evaluationsdialoge wortgleich im Training vor. Unter den ersten 320 Evaluationsbeispielen sind es 248. Der Validierungsverlust beschreibt daher überwiegend die Leistung auf bereits bekannten Dialogen. Er belegt allein keine Generalisierung auf neue Formulierungen. Die folgenden Antworttests ergänzen diese Messung, ersetzen aber keinen systematischen unabhängigen Testdatensatz.

**Ergebnis:** Trainingskonfiguration, Laufzeit und Verlustkurve mit einer kurzen, begründeten Interpretation.

## 5. Experiment: Was verändert das Training an den Antworten?

Die Frageliste und die Bedingungen werden **vor dem Training** festgelegt. Die Antworten werden am untrainierten Modell, an einem festgelegten Zwischenstand und am besten gespeicherten Modell verglichen.

1. Wählen Sie drei unterschiedliche englische Fragen aus den Trainingsdaten. Formulieren Sie zu jeder eine sinngleiche neue Frage und prüfen Sie, dass diese Formulierung nicht wortgleich unter den Trainingsfragen vorkommt.
2. Ergänzen Sie eine englische Frage zu einem Thema außerhalb der Fischgespräche. Halten Sie fest, welche Art von Antwort Sie erwarten. Eine bestimmte Ablehnungsformulierung ist nicht garantiert.
3. Verwenden Sie an allen drei Modellständen dieselben Fragen und identische Generierungseinstellungen. Verwenden Sie für den Hauptvergleich Greedy-Decoding, also die Auswahl des jeweils wahrscheinlichsten Tokens. Dazu ist eine explizite Argmax-Auswahl erforderlich; eine Temperatur nahe 0 ist nur eine Annäherung.
4. Beurteilen Sie die Antworten nach sprachlicher Plausibilität, thematischer Passung und dem erzeugten Endtoken. Unterscheiden Sie ein gelerntes Ende vom Abbruch durch das Tokenlimit.
5. Vergleichen Sie bekannte und neu formulierte Fragen. Wo stimmen sinkender Verlust und bessere Antworten überein? Wo reicht der Verlust zur Beurteilung nicht aus?

Verwenden Sie beispielsweise diese Ergebnistabelle:

| Frage und Typ | Vor dem Training | Zwischenstand | Bester Checkpoint | Beobachtung |
|---|---|---|---|---|
| Bekannte Trainingsfrage | | | | |
| Neue Formulierung dazu | | | | |
| Frage außerhalb der Themen | | | | |

**Ergebnis:** Antwortvergleich mit einer Einschätzung, was das Experiment über das Gelernte aussagt und welche Fragen offenbleiben.

## 6. Experiment: Was verändert die Temperatur?

Bearbeiten Sie Abschnitt 6 mit dem trainierten Modell.

1. Wählen Sie einen festen englischen Prompt. Betrachten Sie zunächst nur die Vorhersage des nächsten Tokens. Sagen Sie voraus, wie sich die Wahrscheinlichkeitsverteilung bei den Temperaturen 0,1, 0,7 und 1,5 verändert.
2. Berechnen Sie die Verteilungen aus denselben Logits. Deaktivieren Sie für diesen Vergleich Top-k, damit nur der Temperatureffekt untersucht wird. Vergleichen Sie die fünf wahrscheinlichsten Tokens und ihre Wahrscheinlichkeiten.
3. Erzeugen Sie anschließend mehrere vollständige Antworten je Temperatur, beispielsweise fünf. Halten Sie Prompt, Modell und übrige Einstellungen gleich. Verwenden Sie für jeden Temperaturwert dieselbe Folge vorher festgelegter Seeds.
4. Vergleichen Sie Vielfalt, Passung und Antwortlänge. Halten Sie fest, ob ein Endtoken erzeugt oder das Tokenlimit erreicht wurde. Behandeln Sie die wenigen Antworten als Beobachtungen, nicht als statistischen Nachweis.
5. Erklären Sie, warum veränderte Antworten hier kein weiteres Lernen bedeuten. Welche Größen werden verändert, welche bleiben gleich?

**Ergebnis:** Vergleich der nächsten Tokenverteilung und ausgewählter Antworten mit einer Erklärung der Samplingwirkung.

## 7. Abschluss: Den gesamten Weg erklären

Erklären Sie anhand eines eigenen Beispiels den Weg von einer Frage bis zur Antwort:

1. Wie werden Text, Sondertokens und Positionen repräsentiert?
2. Wie verändern Attention und FFN diese Repräsentationen?
3. Wie entstehen Logits und wie wird daraus das nächste Token gewählt?
4. Was wird beim Training parallel berechnet, und was muss bei der Generierung schrittweise erfolgen?
5. Welche Beobachtungen belegen, dass sich das Modell durch Training verbessert hat? Welche weitergehenden Aussagen lassen sich daraus nicht ableiten?

Laden Sie abschließend den besten Checkpoint und prüfen Sie eine Ihrer festen Fragen erneut. Welche Dateien und Informationen benötigen Sie, um dasselbe Modell später wieder zu verwenden?

**Ergebnis:** Eine kurze zusammenhängende Erklärung, gestützt auf Ihre Skizze und die Experimentergebnisse.

## Optionale Vertiefung: Ohne Positions-Embeddings trainieren

Dieses Experiment benötigt einen weiteren Trainingslauf.

1. Formulieren Sie eine Hypothese: Welche Aufgaben könnten ohne explizite Positions-Embeddings schwieriger werden? Berücksichtigen Sie, dass die kausale Maske weiterhin eine gerichtete Struktur vorgibt.
2. Trainieren Sie ein frisch initialisiertes Vergleichsmodell, bei dem die Positions-Embeddings nicht zum Token-Embedding addiert werden. Verwenden Sie dieselbe übrige Konfiguration, dieselben Daten und dieselbe Anzahl an Trainingsschritten. Legen Sie getrennte Checkpointpfade fest.
3. Vergleichen Sie Verluste und Antworten auf dieselben festen Fragen. Lassen sich die beobachteten Unterschiede mit Ihrer Hypothese vereinbaren?
4. Erläutern Sie die Grenzen des Vergleichs: Ein kurzer, stark vorlagenbasierter Datensatz und ein einzelner Lauf können Unterschiede verdecken. Ein geringer Effekt beweist nicht, dass Positionsinformationen allgemein unnötig sind.

**Ergebnis:** Hypothese, dokumentierter Vergleich und vorsichtige Interpretation.

## Hinweise für die anschließende Notebooküberarbeitung

Die Aufgaben beschreiben den geplanten Ablauf. Die technischen Korrekturen
sind bereits eingepflegt: explizites Greedy-Decoding, sichtbare Abbruchgründe,
Tokenisierung mit vollständigem Byte-Alphabet, Laden des besten Checkpoints samt
Tokenizer sowie korrigierte Erklärungen zu Padding, Startverlust und Validierung.
Die didaktische Einbettung der Experimente steht noch aus:

- kurze Vorhersagefelder und gezielte Hinweise auf die relevanten Tensorformen;
- eine vorbereitete Zelle für den Vergleich zukünftiger Tokenänderungen mit und ohne kausale Maske;
- feste englische Antwortproben vor und während des Trainings zusätzlich zu den vorhandenen Tests danach;
- ein isolierter Vergleich der nächsten Tokenverteilung bei verschiedenen Temperaturen;
- Speicherung der ergänzenden Zwischenstandergebnisse.

Die Aufgaben führen keine eigene Implementierung von DataLoader oder Early
Stopping ein. Der bestehende Trainingszyklus dient als vertrauter Rahmen.
Der LM-Studio-Export bleibt eine separate Erweiterung nach Abschluss der Kerneinheit.
