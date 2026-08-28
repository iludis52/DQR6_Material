# Arbeitsstand: Unterrichtseinheit PEFT/LoRA (Modul M3)

**Kontext:** Konzeptpapier „Entwurf eines Curriculums aufbauend auf KI DQR 5 zu DQR 6", 63 UE, Themengebiet 1, Bachelor Professional in KI und ML (IHK)
**Stand:** 17.08.2026
**Status:** Brainstorming, Modellwahl vorentschieden, Aufgabenstellung offen

---

## 1 Einordnung im Curriculum

Die UE gehört zu **M3 – Adaption (16 UE)**. M3 trägt die vollständige Entscheidungslinie

> Prompting → RAG → PEFT/LoRA → vollständiges Fine-Tuning

zuzüglich Quantisierung und Betrieb lokaler Modelle. Für den PEFT/LoRA-Block bleiben damit realistisch **4–6 UE**. Diese Budgetgrenze ist die härteste Randbedingung und bestimmt alle folgenden Entscheidungen.

**Verankerung:** RP 1.3.29 (Transfer Learning, Fine Tuning)
**Leitprinzip (Abschnitt 2.3 des Konzeptpapiers):** Code lesen und beurteilen statt Code schreiben. Die Teilnehmenden schreiben keinen Trainingscode; sie lesen ein Referenz-Notebook, konfigurieren, führen aus und bewerten.

---

## 2 Entschieden

### 2.1 Einheitliche Referenzgröße 1–2 B

Ein Modell, ein Tokenizer, ein Chat-Template, ein Notebook, eine Eval-Routine. Kein Wechsel zwischen Modellgrößen im Unterricht.

**Begründung für genau diese Größenklasse:** Erst ab ca. 1 B funktioniert die Gegenprobe. Ein instruct-getuntes 1B-Modell löst die Aufgabe per Few-Shot-Prompt bereits teilweise — nur dadurch wird der Vergleich „Prompt kostet nichts, LoRA kostet 20 Minuten und 200 gelabelte Beispiele, was bringt es?" überhaupt möglich. Bei 270–600 M ist die Basis so schwach, dass die Alternative nicht antritt und der Vergleich trivial wird.

### 2.2 Modellkandidaten

| | Primär | Fallback |
|---|---|---|
| Modell | **Qwen3-1.7B-Instruct** | **Llama-3.2-1B-Instruct** |
| Release | 04/2025 | 09/2024 |
| Lizenz | Apache 2.0 | Llama Community License (gated) |
| Architektur | Dense, volle Attention, GQA/RoPE/SwiGLU/RMSNorm | Dense, volle Attention, GQA |
| VRAM LoRA bf16 | ca. 8–10 GB Peak | ca. 6–7 GB Peak |
| VRAM QLoRA | ca. 5 GB | ca. 4–5 GB |

Weiterer Rückfallpunkt bei knapper Hardware: **Qwen3-0.6B** — gleiche Familie, gleiches Notebook, nur kleiner.

**Warum Llama-3.2-1B trotz Alters als Fallback taugt:** deutlich größerer Bestand vortrainierter Community-Adapter auf dem Hub (siehe Abschnitt 4.3). Falls die Adapter-Leseübung didaktisch hoch gewichtet wird, kann das die Wahl kippen — dann allerdings mit der restriktiveren Lizenz, was wiederum in M6 diskutierbar wird.

### 2.3 Bewusst *nicht* das aktuellste Modell

Geprüft und verworfen: **Qwen3.5-2B** (02/2026) und **Gemma-4-E2B** (04/2026).

Gründe:

1. **Architekturbruch zu M2.** Qwen3.5 nutzt in rund 75 % der Layer Gated DeltaNet (lineare Attention) plus Sparse MoE. M2 unterrichtet 16 UE lang Self-Attention, Positionskodierung, KV-Cache und quadratisches Skalierungsverhalten. Die Teilnehmenden würden `q_proj`/`v_proj` als LoRA-Ziele suchen und in der Mehrzahl der Layer nicht finden. Der KV-Cache existiert dort nicht — lineare Attention führt einen komprimierten Zustand statt gespeicherter Key-Value-Paare.
2. **MoE erzeugt eine Frage ohne curricularen Platz:** Adapter auf Experten, Router oder beides? Router-Instabilität beim Fine-Tuning ist ein eigenes Thema.
3. **Multimodalität und Thinking-Mode** vergrößern die Ausfallfläche und verschmutzen die Auswertung (Reasoning-Spuren müssen vor der Schema-Prüfung herausgefiltert werden).
4. **Ökosystem-Nachlauf** bei PEFT-Unterstützung für neue Architekturen.

Merksatz: Das Alter von Llama-3.2-1B ist ein Nachteil in der Außenwirkung, aber kein fachlicher. Der Architekturbruch der neuesten Modelle ist ein fachlicher.

**Verwertung im Unterricht:** Qwen3.5-2B trotzdem auftreten lassen — als Vergleichsgegenstand, nicht als Trainingsobjekt. Zehn Minuten „Warum trainieren wir nicht auf dem neuesten Modell?" sind wertvoller als der Versuch, es zu tun.

### 2.4 Kein Doppellauf LoRA vs. QLoRA

Ursprünglich erwogen, nach Diskussion verworfen. Gründe:

- **Die Randbedingung beißt bei 1 B nicht.** Beide Varianten passen mühelos auf jede aktuelle Karte. Beobachtung wäre lediglich „geht" und „geht auch, dauert länger" (QLoRA ca. 20–40 % langsamer). Die Ersparnis ist real, aber folgenlos — und die Folgenlosigkeit macht das Experiment didaktisch schwach. QLoRA wird erst bei 8 B oder 70 B sinnfällig.
- **Der Qualitätsvergleich misst Rauschen.** Der Unterschied liegt bei einer schmalen Formataufgabe voraussichtlich innerhalb der Lauf-zu-Lauf-Varianz. Zwei Trainingsläufe für eine Nullaussage.
- **Redundanz** mit dem ohnehin vorgesehenen Quantisierungsblock in M3, der Quantisierung dort behandelt, wo sie betrieblich auftritt: bei der Inferenz.
- **Umgebungsrisiko.** `bitsandbytes` ist die fragilste Komponente im Stack (CUDA-Versionskonflikte, historisch schwierig unter Windows, auf Apple Silicon nicht verfügbar). Verdoppelt die Ausfallfläche. Auf Colab entschärft sich das — Gewichtung hängt an der Hardwarefrage.

**Stattdessen:** QLoRA als **Messung plus Extrapolation**, Aufwand ca. 20 Minuten. Ein Flag im selben Notebook, `max_memory_allocated()` und Schritt-Zeit protokollieren. Ergebnis: weniger Speicher, mehr Zeit — widerlegt sauber die verbreitete Fehlvorstellung „quantisiert = schneller". Anschließend Hochrechnung: Was bräuchte volles Fine-Tuning eines 70B-Modells, was LoRA in bf16, was QLoRA? Erst in dieser Tabelle wird sichtbar, warum das Verfahren erfunden wurde.

Die frei werdende Laborzeit fließt in Variationen, die sichtbare Unterschiede erzeugen (siehe 3.3).

---

## 3 Didaktische Substanz

### 3.1 LoRA als Wiedersehen mit PCA

M1 behandelt PCA und Autoencoder als gelernte Repräsentation. LoRA ist derselbe Gedanke, angewandt auf das **Gewichtsupdate**: die Annahme, dass ΔW eine niedrige intrinsische Dimension besitzt und durch eine Rang-r-Approximation ersetzbar ist.

Umsetzung ohne zweites Modell und ohne Training: eine `q_proj`-Matrix aus dem geladenen 1,7B-Modell herausgreifen, Singulärwertspektrum plotten, Rekonstruktionsfehler über r auftragen. Fünf Zeilen Code. Damit steht die vertikale Klammer M1 → M3 am konkreten Gegenstand statt am Spielzeugbeispiel.

### 3.2 Die Speicherrechnung als Aufgabe, nicht als Folie

Vollständiges Fine-Tuning eines 1B-Modells mit AdamW: Gewichte + fp32-Master + Gradienten + zwei Momente ≈ 16–18 Byte/Parameter → 16–18 GB allein an Optimizer-Zuständen, zuzüglich Aktivierungen.

LoRA mit r = 8 auf `q_proj`/`v_proj`: ca. 2–3 M trainierbare Parameter, also **rund 0,2 %**, Basismodell eingefroren bei ca. 2–3 GB.

Diese Rechnung stellen die Teilnehmenden selbst auf, bevor ein Notebook geöffnet wird. Sie liefert die Begründung für PEFT vollständig und ist prüfbar.

### 3.3 Sinnvolle Laborvariationen (arbeitsteilig auf Gruppen)

| Variation | Werte | Was sichtbar wird |
|---|---|---|
| Datenmenge | 100 / 300 / 1000 Beispiele | betrieblich wichtigste Frage — bestimmt den Labeling-Aufwand |
| Rang r | 4 / 16 / 64 | Kapazität vs. Überanpassung, am Loss-Verlauf ablesbar |
| `target_modules` | nur Attention vs. alle Linear-Layer | Parameterzahl gegen Wirkung |
| Few-Shot-Prompt | — | Nulllinie; ohne sie bleibt die Entscheidungslinie aus M3 unbelegt |

### 3.4 Die didaktisch wertvollste Falle

Eine LoRA auf wenigen hundert Beispielen ändert **Form und Verhalten, nicht Wissen**. Wenn Teilnehmende erwarten, das Modell „kenne jetzt die Firmendaten", und das messbar nicht eintritt, ist das das beste erreichbare Lernergebnis in M3 — es begründet die Entscheidung RAG-vs-LoRA empirisch statt behauptend. Das Szenario ist bewusst so zu bauen, dass dieser Irrtum auftritt und dann widerlegt wird.

Kostenlose Nebenbeobachtungen:

- **Katastrophales Vergessen** — nach dem Tuning allgemeine Fragen stellen, Qualitätsverlust beobachten → Anknüpfung M5 (Robustheit)
- **Reproduzierbarkeit** — zwei Läufe mit gleicher Konfiguration liefern verschiedene Ergebnisse → Anknüpfung M6 (Dokumentation)

### 3.5 Werkzeugwahl

`transformers` + `peft` + `trl` (SFTTrainer), bewusst **ohne Unsloth**, damit die Mechanik nicht hinter einer Ein-Zeilen-API verschwindet. Unsloth als Hinweis auf betriebliche Praxis erwähnen.

**Ausfallsicherung:** Drei vorab trainierte Adapter mitliefern. Dann ist die Auswertungs-UE auch durchführbar, wenn im Labor die Umgebung klemmt.

---

## 4 UE-Skizze (5 UE)

| UE | Inhalt |
|---|---|
| 1 | Warum PEFT — Speicherrechnung selbst aufstellen, Full-FT-Grenze zeigen |
| 2 | Low-Rank-Prinzip — SVD-Demo am Modell selbst, ΔW = B·A, r/α/`target_modules` als Stellgrößen |
| 3–4 | Labor — Referenz-Notebook, Vorher/Nachher, Konfigurationsvariation arbeitsteilig |
| 5 | Auswertung und Entscheidung — Gruppenergebnisse gegeneinander, Few-Shot-Gegenprobe, Entscheidungsmatrix RAG vs. LoRA vs. Full FT |

### 4.1 Meta-didaktischer Vorschlag

Die Modellauswahl selbst nicht als gesetzte Voraussetzung präsentieren, sondern als **dokumentierte Entscheidung mit Kriterien und Ampelbewertung** an den Anfang der UE stellen. Abwägung Aktualität ↔ Architekturtreue ↔ Ökosystem ↔ Lizenz ist der DQR-6-Deskriptor in Reinform. Die Teilnehmenden bekommen dieselbe Entscheidungsstruktur damit zweimal: einmal beim Modell, einmal bei Prompting-vs-LoRA-vs-RAG.

### 4.2 Anschluss an M4 und M6

Die Aufgabe muss so gewählt sein, dass das Ergebnis **messbar** ist (Schema-Validitätsrate, Exact-Match) — dann schlägt die Auswertungs-UE unmittelbar die Brücke zur Testmengen-Konstruktion in M4. Lizenzunterschied Apache 2.0 (Qwen) vs. Llama Community License ist in M6 verwertbar.

### 4.3 Vortrainierte Adapter als Lesegegenstand

Passt unmittelbar zu Leitprinzip 2.3 und kostet keine Rechenzeit:

- `adapter_config.json` lesen: `r`, `lora_alpha`, `target_modules`, `lora_dropout` — die vollständige Konfiguration in zwanzig Zeilen
- Größenprüfung: Basismodell 2–3 GB, Adapter 10–50 MB. Macht den PEFT-Gedanken schlagartiger als jede Folie
- Mehrere Adapter auf derselben eingefrorenen Basis nacheinander laden und Verhalten umschalten — das Deployment-Argument für LoRA schlechthin (ein Basismodell im Speicher, n Spezialisierungen)
- **Herkunftsprüfung:** Wer hat trainiert, auf welchen Daten, unter welcher Lizenz, was passiert bei ungeprüfter Übernahme in ein produktives System? Lieferkettenrisiko am konkreten Objekt → M6

Einschränkung: Adapterdichte auf dem Hub konzentriert sich auf etablierte Basen. Für Llama-3.2-1B groß, für Qwen3-1.7B kleiner. Für die Kernübungen genügen drei selbst erzeugte Adapter.

---

## 5 Nebenbefund für das Konzeptpapier

Betrifft **Abschnitt 5, Streichung RP 1.3.24/1.3.25 (RNN, LSTM)**.

Die Streichungsbegründung — fehlende betriebliche Relevanz — trägt weiterhin. Aber Gated DeltaNet in Qwen3.5 ist der Sache nach ein rekurrenter Zustandsspeicher: Die Idee des komprimierten, sequenziell fortgeschriebenen Zustands ist 2026 in der Spitzenarchitektur zurück, ohne die Trainingsprobleme der LSTM-Ära.

Die vorhandene M2-Formulierung „kurze historische Einordnung sequenzieller Zustandsmodelle" deckt das ab, wenn man sie nach vorn öffnet: nicht nur historisch, sondern als wiederkehrendes Prinzip. Ein-Satz-Zusatz, der die Streichung gegen den naheliegenden Einwand im Abstimmungsgespräch absichert.

---

## 6 Offene Punkte

### 6.1 Aufgabenstellung und Datensatz — **nächster Arbeitsschritt**

Die Aufgabe bestimmt den Datensatz, nicht umgekehrt. Bisheriger Arbeitsvorschlag, noch nicht entschieden:

> **Format-/Schema-Konformität statt Wissensvermittlung.**
> Beispiel: Freitext-Störmeldungen → festes JSON-Schema mit fixem Label-Vokabular.

Begründung: Effekt ist groß und sofort sichtbar; er ist **messbar** (Schema-Validitätsrate, Exact-Match auf Labels); und er provoziert genau die Fehlvorstellung aus 3.4.

Zu klären:

1. Fachdomäne — betriebsnah zu den Teilnehmenden oder neutral?
2. Datenherkunft — öffentlicher Datensatz, synthetisch erzeugt oder aus Betriebskontext abgeleitet? Bei Betriebsdaten: Datenschutz und Verwertbarkeit im Kurs
3. Umfang — für die Variation nach 3.3 werden mindestens 1000 Beispiele plus separate Testmenge gebraucht
4. Testmenge — Konstruktion und Kontaminationsfreiheit; Schnittstelle zu M4
5. Erzeugungsweg — falls synthetisch: mit welchem Modell, und wie wird Zirkularität vermieden

### 6.2 Hardware — bestimmt Feinjustierung

Colab/Cloud, lokale Labor-GPUs oder Teilnehmer-Notebooks (Windows/NVIDIA vs. Apple Silicon)? Davon hängt ab, ob bf16-LoRA, QLoRA oder doch das 0,6B-Modell die Basis wird, und wie stark das `bitsandbytes`-Risiko wiegt.

### 6.3 Vor Kursbeginn zu verifizieren

Der Modellmarkt bewegt sich schnell. Die Kandidatenliste kurz vor Kursbeginn erneut prüfen. Die Argumentationslinie bleibt stabil, weil sie an der Architektur hängt und nicht am Release-Datum.
