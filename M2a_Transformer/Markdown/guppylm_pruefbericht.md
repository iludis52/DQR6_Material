# Korrekturen und Funktionsprüfung

Stand: 18.10.2026.

## Didaktische Vereinfachung am 18.10.2026

- Daten werden direkt aus den vorbereiteten Dateien `guppy/data/train.jsonl` und
  `guppy/data/eval.jsonl` gelesen. ZIP-Verarbeitung, eigene Existenzprüfungen und
  Inhaltsvalidierung entfallen. Das Entpacken ist als Vorbereitung beschrieben.
- Modellgrößen werden als sinnvoll vorausgesetzt; die fachlich wichtige
  Teilbarkeitsprüfung für die Attention-Köpfe bleibt erhalten.
- Tokenizertrainer und Konfigurationsänderungen sind separat benannt;
  `dataclasses.replace` ersetzt verschachteltes Zusammenführen von Dictionaries.
- Batchaufbereitung, Attention, FFN und Sampling zeigen die Zwischenschritte.
  Die Rechenoperationen und die GPT-2-Gewichtsabbildung bleiben erhalten.
- Validierungsbatches, Bewertungsfunktion und Trainingsschleife stehen in eigenen,
  erläuterten Zellen. Die Bewertung stellt im regulären Ablauf den vorherigen
  Modellmodus wieder her; ein zusätzliches `try/finally` entfällt.
- Gleitender Mittelwert, Checkpointaufbau und Exportnamen sind ausgeschrieben.
  Tokenizerbindung, Prüfsummen sowie fachliche Kontext- und Exportprüfungen bleiben erhalten.
- Begleittexte und Funktionsprüfung wurden an die neue Zellaufteilung und den
  direkten Dateizugriff angepasst. Fehlende Dateien melden sich über `open`.

## Eingepflegte Änderungen

- Beide Notebooks und Begleitmaterialien verwenden englische reguläre Modellproben.
- Der lokale Datensatz bleibt die alleinige Trainingsdatenquelle.
- Vollständiges Byte-Alphabet im Tokenizer; Vokabulargröße und Sondertoken-IDs werden übernommen.
- Zentrale Architekturkonfiguration vor der Sequenzaufbereitung; verständliche Meldungen bei zu langen Beispielen oder unzulässiger Kopfzahl.
- Temperatur 0 verwendet Greedy-Decoding. Negative oder nicht endliche Temperaturen werden abgewiesen.
- Die Generierung schneidet den Kontext nicht still ab und gibt auf Wunsch den Abbruchgrund aus.
- Checkpoints enthalten den zugehörigen Tokenizer mit Prüfsumme. Alte Checkpoints ohne diese Zuordnung werden abgewiesen.
- Vor Antworttests wird der beste Checkpoint geladen.
- Die Validierung verwendet standardmäßig 320 Beispiele und gewichtet den Verlust nach gültigen Tokens.
- Fachliche Erklärungen und Zahlen in Lehrtext und Quiz wurden an das tatsächliche Verfahren angepasst.
- Der Export unterstützt lokale llama.cpp-Quellen ohne automatischen Download, prüft HF-Tokenizer und Chatvorlage und behandelt Konvertierungsfehler gezielt.
- Veraltete Notebookausgaben wurden entfernt. Paketstände sind in den beiden Requirements-Dateien festgehalten.

## Ausgeführte Prüfung

Aufruf: `.venv/Scripts/python.exe pruefe_notebooks.py` unter Windows mit Python 3.12.
Installiert wurden die Versionen aus `requirements-training.txt` und
`requirements-export.txt`, zusätzlich `nbformat==5.11.1` für die Formatprüfung.
Die Prüfung verwendete lokale Daten und lokale Modelle ohne Hugging-Face-Download.

| Prüfung | Ergebnis |
|---|---|
| Notebookformat und Python-Syntax | bestanden |
| Lokales Laden aller 57.000 Trainings- und 3.000 Evaluationsdialoge | bestanden |
| Tokenizertraining auf den vollständigen lokalen Trainingsdaten | bestanden, V = 2.597 |
| Rückübersetzung mit Großbuchstaben, Umlauten und Emoji | bestanden |
| Regulärer Dateifehler bei fehlenden Daten; Meldungen bei zu langen Beispielen und unzulässiger Kopfzahl | bestanden |
| Kausale Abschirmung und Unabhängigkeit gültiger Positionen von rechtem Padding | bestanden |
| Drei Optimierungsschritte mit einem kleinen Modell desselben Rechengraphen | bestanden |
| Nach Tokens gewichtete Validierung und Erhalt des vorherigen Modellmodus | bestanden |
| Laden des eingebetteten Tokenizers trotz veränderter separater Tokenizerdatei | bestanden |
| Abweisung alter beziehungsweise inkonsistenter Checkpoints | bestanden |
| Greedy-Decoding, Sampling und Temperaturprüfung | bestanden |
| Endtoken, Tokenlimit und Kontextgrenze | bestanden |
| GPT-2-Abbildung im kleinen Prüfmodell | maximale Logitabweichung ca. 1,49 × 10⁻⁷ |
| HF-Speichern und erneutes Laden von Tokenizer und Chatvorlage | bestanden |
| Simulierte GGUF-Konvertierungsfehler und standardmäßig deaktivierter Patch | bestanden |

Die Zahl V = 2.597 gehört zum hier geprüften Tokenizerlauf. Im Notebook werden
die Größe und die Parameterzahl stets neu gemessen. Bei diesem V und den
unveränderten Architekturwerten ergeben sich rechnerisch 11.693.952 Parameter.

## Noch nicht ausgeführt

- Vollständiger Trainingslauf mit 3.000 Schritten und Beurteilung der Antwortqualität.
- Ausführung auf einem Mac oder auf der Kurs-GPU.
- GGUF-Konvertierung, numerische Gegenprobe in llama.cpp und Import in LM Studio.

Die neue Tokenisierung erfordert einen neuen Trainingslauf. Die erfolgreichen
Funktionsprüfungen belegen die getesteten Abläufe, keine bestimmte Antwortqualität.
Die Datensplits wurden unverändert gelassen; ihre Überschneidungen sind im
Notebook und im Begleittext erläutert.

Die geplanten didaktischen Experimente aus `guppylm_aufgaben.md` sind noch kein
Bestandteil dieser Korrekturrunde.
