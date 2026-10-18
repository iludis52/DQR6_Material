# Embedding-Werkbank

Die eigenständige Seite liegt in `Lernapp/embeddings-werkbank.html`. Die bestehende
Transformer-Werkbank wurde für diese Erweiterung nicht verändert.

## Originalgewichte laden

1. `Checkpoints/bestes_modell.pt` vom Trainingsrechner synchronisieren.
2. In der Python-Umgebung des Lehrnotebooks ausführen:

   ```powershell
   python exportiere_embeddings.py Checkpoints/bestes_modell.pt
   ```

3. Die HTML-Datei öffnen und über **Checkpoint-Export laden** die erzeugte
   `Data/embeddings-checkpoint.json` auswählen. Die Datei bleibt lokal.

Alternativ im Projektordner einen lokalen Webserver starten:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Dann `http://127.0.0.1:8765/Lernapp/embeddings-werkbank.html` öffnen.
Über HTTP lädt die Seite den Export automatisch; fehlt er, wird
`Data/tokenizer.json` geladen. Ohne Gewichte gibt es nur Tokenisierung und IDs,
keine Ersatzvektoren. Nach erneutem Training den Export neu erzeugen und die
Seite neu laden oder die neue JSON-Datei auswählen. Das JSON enthält bei der
aktuellen Konfiguration ungefähr 21 MiB.

## Was gezeigt wird

- ByteLevel-BPE mit dem im Checkpoint eingebetteten Tokenizer, einschließlich
  Sondertokens, UTF-8 und vollständiger Merge-Liste. Kein zusätzliches Training
  des Tokenizers und keine automatische Chatformatierung.
- `tok_emb.weight`: hier 2.597 Tokens × 384 Dimensionen. Die tatsächliche
  Konfiguration wird aus dem Checkpoint gelesen, nicht auf 6 Lehrdimensionen reduziert.
- `pos_emb.weight`: hier 128 Positionen × 384 Dimensionen. **Gelernte** absolute
  Positionen, keine sinusförmigen Positionskodierungen.
- Komponentenweise Addition und anschließend `blocks.0.norm1` mit den originalen
  trainierten Werten von γ und β sowie `eps=1e-5` wie im Lehrnotebook.
- Berechnung im Inferenzmodus: Das Dropout nach der Addition ist deaktiviert.
  Die erste LayerNorm liegt nur im Attentionzweig; der Residualweg erhält die Summe.

Die Darstellung zeigt bis zu zwölf Tokenzeilen pro Seite. Alle Tokens bleiben
anwählbar. Längere Sequenzen als die Kontextlänge werden mit einer Erklärung
abgewiesen und nicht still gekürzt. „Dimensionen“ zoomt nur die Darstellung;
die LayerNorm rechnet immer über sämtliche Modelldimensionen. Alle Dimensionen
sind über die Zahlenansicht zugänglich.

Negative Werte sind blau, null ist hell, positive Werte orange. Token-,
Positions- und Summenansicht verwenden eine gemeinsame symmetrische Farbskala
über alle Positionen und Dimensionen des aktuellen Satzes. Nach LayerNorm gilt
eine eigene, beschriftete Farbskala. Farben verschiedener Sätze sind wegen der
jeweils neu bestimmten Skala nicht unmittelbar vergleichbar.

## Datenherkunft und Prüfung

Das Exportskript liest den Checkpoint mit `torch.load(..., weights_only=True)`.
Es benötigt weder ein erneutes Training noch die Ausführung des Notebooks.
Es exportiert nur die benötigten Tabellen und LayerNormparameter, nicht das
ganze Sprachmodell. Tensoren werden als float32 erwartet und als ungerundete
JSON-Zahlen gespeichert. Zusätzlich enthalten sind Trainingsschritt, Evalverlust,
Checkpoint-SHA-256, der originale Tokenizertext und dessen SHA-256 sowie mit
`tokenizers` und PyTorch berechnete Referenz-IDs und LayerNormausgaben.

Beim Import prüft der Browser Vokabulargröße, Sondertoken-IDs, Tabellenformen,
endliche Zahlenwerte, die Tokenizer-Prüfsumme und die Referenzberechnungen.
Ein separat geladener Tokenizer ersetzt den aktuellen Datensatz vollständig;
er wird niemals mit den Gewichten eines anderen Exports kombiniert.

JavaScript berechnet Summe und LayerNorm in doppelter Genauigkeit, PyTorch im
Notebook verwendet float32. Kleine numerische Abweichungen sind zu erwarten;
die Browserprüfung nutzt eine absolute plus relative Toleranz von jeweils
`2e-5`. Es werden weder Token- noch Positionsgewichte nachgebildet oder zufällig erzeugt.

```powershell
node --check Lernapp/embeddings-modell.js
node --check Lernapp/embeddings-werkbank.js
node pruefe_embeddings.js
```

`Data/embedding-tokenizer-referenzen.json` enthält 455 Referenzfälle aus der
Python-Bibliothek `tokenizers`: 200 Texte aus `eval.jsonl`, fünf Fälle zu Unicode,
Whitespace und Sondertokens sowie 250 reproduzierbare Zufallstexte (Seed 18).
Sie beziehen sich auf die vorhandene `Data/tokenizer.json`. Zusätzlich prüft
jeder Checkpoint-Export seine eigenen Tokenisierungs- und Normreferenzen.
