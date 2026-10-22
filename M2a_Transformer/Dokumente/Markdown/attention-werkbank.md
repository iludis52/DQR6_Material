# Attention-Werkbank

Einstieg: `Lernapp/attention-werkbank.html`. Die vorhandenen Lernapps und
Notebooks wurden für diese Erweiterung nicht verändert.

Die Werkbank zeigt einen einzelnen Attention-Kopf des trainierten GuppyLM mit
den Originalgewichten. Sie schließt an die Embedding-Werkbank an, die mit der
ersten LayerNorm endet: Deren Ausgang x̂ ist hier der Eingang jedes Kopfes.

## Das Kreuz-Layout

Alle Elemente haben einen festen Platz, der ihre Funktion abbildet:

- **Zeile i** = fragendes Token. Links stehen x̂ (384 Komponenten), W_Q und die
  Query qᵢ (64 Komponenten), rechts der Kopfausgang hᵢ.
- **Spalte j** = angefragtes Token. Oben steht der Key kⱼ, unten der Value vⱼ,
  beide aus W_K bzw. W_V und denselben x̂ wie links.
- **Zelle (i, j)** liegt im Schnittpunkt von qᵢ und kⱼ und zeigt deren Bewertung
  qᵢ · kⱼ / √64 oder nach Softmax das Gewicht aᵢⱼ.

Die sieben Schritte decken die Elemente nacheinander auf, ohne dass etwas
seinen Platz wechselt: Eingang → Projektionen → Bewertungen (zunächst alle
Paare) → kausale Maske → Softmax je Zeile → Mischung der Values → Rückweg über
Concat und W_O. Nicht beteiligte Bereiche werden abgeblendet. Ab Schritt 5
schaltet „Matrix zeigt“ zwischen Bewertungen und Gewichten um.

Zeilen, Spalten, Zellen und einzelne Streifenkomponenten sind anklickbar; die
Erklärspalte rechnet die gewählte Stelle vor:

- **Projektion:** eine Komponente von q, k oder v als Summe der 384 Produkte aus
  Gewichtszeile und x̂ plus Bias, mit den fünf größten Beiträgen.
- **Bewertung:** die 64 Produkte qᵢ ⊙ kⱼ, ihre Summe und die Teilung durch 8.
- **Mischung:** hᵢ als gewichtete Summe der Values; jede Komponente liegt
  zwischen kleinstem und größtem Value-Wert der sichtbaren Positionen.

Didaktisch wichtig: Ein Kopf erhält **keinen Ausschnitt** von x̂. Jede seiner 64
Komponenten verrechnet alle 384 Komponenten. Beim Kopfwechsel bleibt x̂ gleich,
während sich q, k und v vollständig ändern. Aufgeteilt wird erst nach der
Projektion (im Notebook: `reshape` hinter `self.qkv`).

Schritt 4 greift außerdem die Fehlvorstellung auf, die Maske sei nur im
Training nötig. Grundlage ist ein Versuch mit dem Checkpoint: Greedy-Generierung
mit dem Prompt aus `vergleich_prompt.txt`, einmal mit und einmal ohne Maske.
Die Kopfausgänge der letzten Position in Block 1 bleiben gleich. Ab Block 2
weichen sie ab, weil frühere Positionen andere Vektoren liefern. Die Logits der
letzten Position unterscheiden sich um bis zu 2,0, und die Antworten lauten
„hi. i just found a nice spot in the corner.“ bzw. „hi there. i was just
thinking about food. i blew some bubbles earlier.“ Die beiden Antworten stehen
als fester Text in der App. Nach einem neuen Training den Versuch wiederholen.

## Die Query-Ebene statt PCA

Für die gewählte Query qᵢ wird jeder Key exakt in einer Ebene dargestellt:
waagrecht sein Anteil in Richtung qᵢ, senkrecht die Länge seines restlichen
Anteils. Die Bewertung hängt nur von der waagrechten Lage ab; Winkel und Längen
relativ zu qᵢ stimmen. Abstände zwischen zwei Keys gibt die Ebene nicht wieder.

Eine PCA wäre hier irreführend: Sie verwirft Komponenten und zentriert die
Daten, sodass die abgelesenen Skalarprodukte nicht mit den Bewertungen der
Matrix übereinstimmen würden.

## Datenauswahl

| | Inhalt |
|---|---|
| Prompts | `hello guppy` und `fish fish fish`, jeweils im ChatML-Rahmen aus `vergleich_prompt.txt` (10 bzw. 11 Tokens) |
| Block 1 | Köpfe 4 („Nachbar“), 5 („Selbstbezug“), 6 („Rollenmarke“) |
| Block 6 | Köpfe 3 („Breit verteilt“), 4 („Anker“), 5 („Inhalt“) |

Die Kopfnamen beschreiben, was an diesen beiden Prompts zu beobachten ist. Sie
sind keine nachgewiesenen Funktionen; die App sagt das ausdrücklich. Bei
`fish fish fish` ist das erste `fish` ein anderes Token als die beiden folgenden
`Ġfish` (mit Leerzeichen). Dasselbe Token an zwei Positionen zeigen nur die
Positionen 4 und 5.

Block 1 enthält zusätzlich die Herkunft von x̂: Token-Embedding, Positions-
Embedding, Summe sowie γ und β der LayerNorm. Ab Block 2 ist x̂ die LayerNorm
des Residualstroms, also nicht mehr „Token plus Position“.

Nicht enthalten sind W_O und die übrigen drei Köpfe je Block. Schritt 7
beschreibt den Rückweg deshalb nur und verweist auf die Transformer-Werkbank.

## Daten erzeugen

In der Python-Umgebung des Lehrnotebooks im Projektordner ausführen:

```powershell
python Hilfsskripte/exportiere_attention.py Checkpoints/bestes_modell.pt --auswahl 1:4,5,6 6:3,4,5
```

Das Skript liest den Checkpoint mit `torch.load(..., weights_only=True)`,
prüft die Tokenizer-Prüfsumme und rechnet den Vorwärtslauf des Notebooks im
Evaluationsmodus nach. Bevor es exportiert, muss dieser Nachbau die gespeicherte
Greedy-Antwort aus `Hilfsskripte/vergleich_referenz.json` Token für Token
reproduzieren. Ausgabe ist `Data/attention-daten.js` (etwa 7 MiB): JSON in einer
JavaScript-Zuweisung, damit die App auch beim direkten Öffnen der HTML-Datei
ohne Webserver lädt. Werte werden als float32 mit 9 signifikanten Stellen
gespeichert und sind damit verlustfrei.

Nach einem neuen Training muss der Export erneut erzeugt werden. Die Kopfauswahl
sollte dann überprüft werden, weil sich die Muster ändern können. Ohne
`--auswahl` werden alle Köpfe der Blöcke 1 und 6 exportiert (etwa 13 MiB); das
eignet sich zum Sichten. `KOPFMUSTER` in `attention-werkbank.js` enthält die
Beschriftungen der aktuell gewählten Köpfe.

## Prüfung

Beim Laden rechnet der Browser jeden exportierten Wert aus x̂ und den
exportierten Gewichten nach: Projektionen, Bewertungen, Softmax, Kopfausgänge
und die LayerNorm in Block 1. Weicht ein Wert ab oder fehlt die Datei, zeigt die
App einen Hinweis und keine Ersatzwerte.

```powershell
node --check Lernapp/attention-modell.js
node --check Lernapp/attention-werkbank.js
node Hilfsskripte/pruefe_attention.js
```

Das Prüfskript wiederholt die Nachrechnung (aktuell 50.436 Werte, maximale
Abweichung etwa 2·10⁻⁶). Außerdem prüft es kausale Maske und Zeilennormierung
sowie die Exaktheit der Query-Ebene. Liegt der Export der Embedding-Werkbank
aus demselben Checkpoint vor, gleicht es die Embeddings damit ab. Zuletzt
prüft es, dass manipulierte Daten abgewiesen werden.

## Bereitstellen

Gemeinsam bereitstellen: `Lernapp/attention-werkbank.html`, `.css`, `.js`,
`Lernapp/attention-modell.js` und `Data/attention-daten.js`. Die relative Lage
von `Lernapp/` und `Data/` muss erhalten bleiben. Es gibt keinen Build, kein
Backend und kein CDN.

## Mögliche Ausbaustufe

Der KV-Cache kann in einer eigenen App folgen: Beim Generieren kommt pro
Schritt nur eine neue Zeile hinzu, während Keys und Values früherer Positionen
unverändert bleiben.
