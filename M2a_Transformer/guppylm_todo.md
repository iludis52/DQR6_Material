# TODO — GuppyLM-Lehrmaterial

Offene Punkte aus der Durchsicht vom 29.08.2026. Sortiert nach Wirkung,
nicht nach Aufwand.

---

## Hohe Priorität

- [ ] **Abschnitt „Kaputtmachen und beobachten" ergänzen** (Lehrnotebook)
  Das Material hat keine Fehlererfahrung — alles läuft durch. Wer die kausale
  Maske einmal entfernt und sieht, wie der Startverlust unter 8,32 fällt, hat
  verstanden, wozu sie da ist. Kandidaten:
  - [ ] Maske abschalten → Startverlust sinkt unter ln(4096)
  - [ ] `ignore_index` weglassen → Verlust sinkt scheinbar schneller
  - [ ] Lernrate auf 3e-2 → Training divergiert
  - [ ] Positions-Embedding weglassen → Wortsalat trotz sinkendem Verlust

- [ ] **Aussage zum Auseinanderlaufen der Kurven korrigieren** (Lehrnotebook
  Abschnitt 5, Lehrtext Teil 3)
  Trainings- und Testteil stammen aus demselben Vorlagengenerator. Der Abstand
  bleibt vermutlich klein, das gelehrte Warnsignal tritt also gar nicht auf.
  Entweder als Einschränkung benennen oder mit einem zweiten Beispiel
  unterlegen (z. B. Training auf 500 Beispielen statt 57.000).

- [ ] **Beobachtungszellen auf Vorhersagen-dann-Prüfen umstellen**
  Bisher nur bei der Parameterbilanz genutzt, dort aber am wirksamsten.
  Nachziehen bei:
  - [ ] kausale Maske — wie viele Werte sind ungleich null?
  - [ ] Residualbeitrag — wie stark ändert ein Block den Strom?
  - [ ] Temperaturvergleich — bei welcher Temperatur kippt es?
  - [ ] Sequenzlängen — wo liegt das 99-Prozent-Quantil?

---

## Mittlere Priorität

- [ ] **`backward()` als Lücke markieren** (Lehrnotebook Abschnitt 5)
  Eine Zeile enthält den gesamten Lernmechanismus. Für „Lesen und Beurteilen
  vor Schreiben" vertretbar, aber es steht nirgends, dass hier etwas fehlt.
  Mindestens ein Absatz, der die Lücke benennt und einordnet.

- [ ] **Quiz um anspruchsvollere Aufgaben erweitern**
  Zehn Fragen auf Stufe *Verstehen*, keine auf *Analysieren* oder *Beurteilen*.
  Für DQR-6 zu flach. Ergänzen:
  - [ ] Verlustkurve zeigen → „Was ist hier passiert?"
  - [ ] Startverlust 6,1 statt 8,32 → „Woran liegt das?"
  - [ ] Zwei Konfigurationen vergleichen → „Welche und warum?"
  - [ ] Fehlerhafte Gewichtsabbildung → „Wo ist der Fehler?"

- [ ] **Token-IDs im Lehrtext durch echte Werte ersetzen**
  Das Beispiel „guppy mag blasen" in Teil 1 hat erfundene IDs. Nach dem
  nächsten Trainingslauf die tatsächliche Zellenausgabe übernehmen.

---

## Formales

- [ ] **`HERKUNFT.md` anlegen** — Vorlage steht im Chatverlauf
- [ ] **Commit-SHA einsetzen** — Platzhalter `<SHA>` in beiden Notebook-Kopfzeilen
- [ ] **Issue bei `arman-bd/guppylm` eröffnen** — fehlende `LICENSE`-Datei;
      README nennt MIT, die verlinkte Datei liefert 404
- [ ] **Modell umbenennen** — nicht `guppylm-9M` (belegt und inhaltlich falsch),
      eher `guppylm-12M-de`

---

## Vor dem Einsatz im Unterricht

- [ ] **Neu trainieren** — die Umstellung auf GELU und `ffn_hidden = 1536` ist
      noch nicht in einem vollständigen Lauf gelandet
- [ ] **Gegenprobe mit `llama-cli`** — der einzige ungetestete Schritt der
      Exportkette:
      `llama-cli -m guppy/guppylm-f16.gguf -p "hallo guppy" --temp 0 -n 32`
      Muss dieselbe Antwort liefern wie das Notebook bei Temperatur nahe 0.
- [ ] **Einmal komplett auf dem Zielrechner durchlaufen lassen** — inklusive
      LM-Studio-Import, mit realistischer Zeitmessung für die Kursplanung

---

## Erledigt

- [x] Colab-Abhängigkeiten entfernt, lokal lauffähig
- [x] Didaktischer Neuaufbau in Bausteinen, `%%writefile` entfernt
- [x] Attrappen entfernt (`(idx, [])`, `(total, 0)`, doppelter Konfigpfad)
- [x] Übersetzung ins Deutsche
- [x] GELU statt ReLU, `ffn_hidden` 768 → 1536
- [x] Exportweg nach GPT-2/GGUF, Abbildung verifiziert (Δ = 2,9e-06)
- [x] Lehrtext in einfacher Sprache
- [x] Quiz mit zehn Fragen, Antwortlängen ausgeglichen
- [x] Mermaid-Bug behoben (`+` wurde als Markdown-Liste geparst)
