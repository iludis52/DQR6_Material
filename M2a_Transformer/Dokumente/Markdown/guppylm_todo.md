# TODO — GuppyLM-Lehrmaterial

Stand: 17.10.2026. Fachliche und technische Korrekturen sind von den noch
geplanten didaktischen Experimenten getrennt.

## Vor dem Unterricht noch zu prüfen

- [ ] Einen vollständigen Trainingslauf mit dem korrigierten Byte-Alphabet ausführen.
  Alte Checkpoints ohne eingebetteten Tokenizer werden bewusst nicht weiterverwendet.
- [ ] Tatsächliche Laufzeiten auf Mac und PC beziehungsweise den Kursgeräten messen.
- [ ] GGUF-Konvertierung mit einem dokumentierten lokalen llama.cpp-Stand ausführen.
- [ ] Tokenisierung und Logits in llama.cpp mit identischen Prompts und
  Generierungseinstellungen prüfen; F16-Abweichungen berücksichtigen.
- [ ] Import und Einstellungen in LM Studio auf dem Zielgerät prüfen.
- [ ] Die Überschneidung von Trainings- und Validierungsdialogen bei der
  Beurteilung berücksichtigen; neue englische Testformulierungen vorbereiten.

## Didaktische Weiterentwicklung

Grundlage ist `guppylm_aufgaben.md`. PyTorch und der Trainingszyklus einschließlich
Validierung und Early Stopping werden vorausgesetzt.

- [ ] Beobachtungszellen behutsam auf Vorhersage → Versuch → Erklärung umstellen.
- [ ] Den Kausalitätstest mit identischem Präfix und verändertem Suffix ergänzen.
  Ein sinkender Startverlust bei abgeschalteter Maske ist kein garantiertes Ergebnis.
- [ ] Feste englische Antwortproben vor, während und nach dem Training ergänzen.
- [ ] Isolierten Temperaturvergleich auf denselben nächsten Tokenlogits ergänzen.
- [ ] Optionalen Vergleich ohne Positions-Embeddings vorbereiten; Ergebnis offen untersuchen.
- [ ] Quiz bei Bedarf um Analyseaufgaben erweitern; Basisfragen sind fachlich korrigiert.

## Herkunft und Reproduzierbarkeit

- [ ] Ursprünglichen Bearbeitungsstand des Ausgangsprojekts rekonstruieren, falls möglich.
  Es wird bis dahin kein unbekannter Commit-SHA behauptet.
- [ ] Lizenzunterlagen des Ausgangsprojekts vor einer Weiterverteilung prüfen;
  `notice.md` dokumentiert den vorhandenen Kenntnisstand.

## Eingepflegte Korrekturen

- [x] Lokales Lesen der entpackten `train.jsonl` und `eval.jsonl`, keine `datasets`-Abhängigkeit.
- [x] Reguläre Tokenizer- und Antwortproben auf Englisch; UTF-8-Proben separat eingeordnet.
- [x] Vollständiges Byte-Alphabet und Prüfungen der verlustfreien Rückübersetzung.
- [x] Gemeinsame Konfiguration vor der Sequenzaufbereitung; IDs aus dem Tokenizer.
- [x] Kein stilles Abschneiden zu langer Trainingsbeispiele oder Generierungskontexte.
- [x] Greedy-Decoding bei Temperatur 0; Prüfung ungültiger Temperaturen.
- [x] Endtoken, Tokenlimit und Kontextgrenze als getrennte Abbruchgründe.
- [x] Tokenizer einschließlich Prüfsumme im Checkpoint, beim Laden auf Konsistenz geprüft.
- [x] Bestes Modell vor allen regulären Antworttests laden.
- [x] Validierung über gültige Tokens gewichtet und Stichprobengröße explizit ausgewiesen.
- [x] Erklärungen zu Startverlust, Padding, Residualpfaden und Verlustkurven korrigiert.
- [x] Parameterangaben an tatsächliche Vokabulargröße gebunden; erfundene Ausgaben entfernt.
- [x] Export mit lokalem llama.cpp-Ordner und standardmäßig deaktiviertem Download.
- [x] Export-Patch standardmäßig deaktiviert und nur bei erkanntem Tokenizerfehler anwendbar.
- [x] HF-Tokenisierung und Chatvorlage nach erneutem Laden geprüft.
- [x] Ungültige Herkunftsverweise korrigiert; begleitende Texte und Quiz nachgezogen.
- [x] Alte Notebookausgaben entfernt; Paketversionen für die lokale Funktionsprüfung festgehalten.

## Funktionsprüfung

`pruefe_notebooks.py` führt ohne Datendownload einen kurzen Testlauf mit einem
kleinen Modell durch. Er prüft den lokalen Datensatz, den Tokenizer, Kausalität,
Padding, drei Optimierungsschritte, Checkpointzuordnung, Generierung sowie die
HF-Abbildung und Exportfehlerpfade. Er ersetzt kein vollständiges Training und
keine GGUF-/LM-Studio-Prüfung.
