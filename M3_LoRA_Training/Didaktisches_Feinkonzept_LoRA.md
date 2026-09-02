# Didaktisches Feinkonzept
## Unterrichtseinheit: LoRA-Prinzip und LoRA-Training

**Stand:** 2026
**Status:** Synthese / Feinkonzept
**Kontext:** Bachelor Professional in KI und ML (IHK), DQR 6
**Modulbezug:** M3 – Adaption
**Themenfeld:** PEFT / LoRA / praktische Umsetzung
**Voraussetzungen der Teilnehmenden:**
Die Teilnehmenden wissen, was ein Transformer ist, und verstehen grob, wie er arbeitet.

---

## 1. Ausgangslage und Zielrichtung

Die Unterrichtseinheit führt in das Prinzip von Low-Rank Adaptation (LoRA) sowie in die praktische Durchführung von LoRA-Training ein. Im Zentrum steht die praktische Anwendbarkeit: Die Teilnehmenden sollen LoRA nicht nur konzeptionell verstehen, sondern tatsächlich in einem lokalen, betrieblich realistischen Setting einsetzen können.

Gleichzeitig ist eine robuste Modellvorstellung erforderlich. LoRA ist kein „magisches Feintuning“, sondern ein gezieltes, parameterisoliertes Adaptionsverfahren, das Verhalten, Formatierung und Stil verändern kann, aber nur begrenzt geeignet ist, neues Faktenwissen zu injizieren. Diese Unterscheidung ist didaktisch besonders wertvoll, weil sie später die Abgrenzung zwischen LoRA und RAG empirisch nachvollziehbar macht.

Die Unterrichtseinheit basiert auf drei vorliegenden Arbeitsdokumenten:

* `UE_PEFT_LoRA_Arbeitsstand.md`
* `einfuehrung_LoRA.md`
* `LoRA_DeepDive_Leitfaden.md`

Der Entwurf ist bewusst nicht als starre Abfolge einzelner Unterrichtseinheiten (UE) angelegt, sondern als inhaltliche Kapitelstruktur. Dadurch erhält die Lehrkraft Flexibilität für unterschiedliche Zeitbudgets, Diskussionstiefen und technische Probleme im Labor.

---

## 2. Didaktische Grundentscheidungen

### 2.1 Fokus auf praktische Anwendbarkeit

Die Teilnehmenden sollen LoRA nicht nur theoretisch kennenlernen, sondern praktisch erfahren, wie sich Konfiguration, Datenbasis und Trainingsparameter auf das Ergebnis auswirken. Der Schwerpunkt liegt deshalb auf:

* Konfiguration statt Implementierung,
* Experiment statt Boilerplate-Code,
* Evaluation statt bloßem Training,
* Einordnung statt Werkzeug-Hype.

### 2.2 On-Premise- und Datenschutzrealität

Das Labor findet auf lokalen Maschinen statt. Dies entspricht der betrieblichen Realität vieler Teilnehmenden, da in Unternehmen häufig Datenschutz-, Sicherheits- oder Compliance-Vorgaben gegen die Nutzung externer Cloud-Dienste sprechen.

Daher werden insbesondere berücksichtigt:

* lokale Inferenz und lokales Training,
* begrenzte Hardware-Ressourcen,
* unterschiedliche Systemumgebungen,
* CUDA-basierte GPUs,
* Apple Silicon mit Metal Performance Shaders (MPS),
* Fallback-Strategien bei geringem Speicherbedarf.

### 2.3 Modellwahl

Als primäres Referenzmodell wird ein Modell aus der Klasse von etwa 1 bis 2 Milliarden Parametern verwendet, insbesondere:

* **Qwen3-1.7B-Instruct** als Primärmodell,
* **Qwen3-0.6B** als Fallback bei sehr knapper Hardware,
* optional Llama-3.2-1B-Instruct als alternative Referenz.

Die Modellgröße ist didaktisch bewusst gewählt:
Ein Modell unterhalb von etwa 1 Milliarde Parametern ist häufig zu schwach, um eine sinnvolle Few-Shot-Vergleichsbasis zu bilden. Ein Modell oberhalb von 2 Milliarden Parametern ist für lokale Laborumgebungen häufig zu speicherintensiv.

Die gewählte Größenklasse ermöglicht:

* lokale Trainingsfähigkeit,
* sichtbare Few-Shot-Fähigkeiten des Basismodells,
* messbare Unterschiede zwischen Prompting und LoRA,
* realistische On-Premise-Szenarien.

### 2.4 Datensatzdomäne: IT-Störmeldungen

Als durchgängige Fachdomäne werden IT-Störmeldungen verwendet. Ausgangspunkt sind unstrukturierte Freitext-Störmeldungen. Ziel ist die Erzeugung strukturierter Ausgaben, insbesondere eines festen JSON-Schemas.

Diese Domäne eignet sich besonders, weil:

* sie betrieblich plausibel ist,
* der Effekt von LoRA schnell sichtbar wird,
* das Ergebnis messbar ist,
* Formatkonformität trainiert werden kann,
* keine sensiblen Originaldaten erforderlich sind,
* synthetische Daten gut erzeugt werden können.

Beispielhafte Zielaufgabe:

> Aus einer freien IT-Störmeldung soll ein strukturiertes JSON-Objekt mit Feldern wie Komponente, Schweregrad, Fehlerkategorie und empfohlenem Next Step erzeugt werden.

### 2.5 Drei Datensätze statt nur eines Trainingsdatensatzes

Für eine saubere didaktische Dramaturgie werden drei Datensätze verwendet:

1. **Manuell kuratierter Datensatz**
   Die Teilnehmenden erstellen selbst eine kleine Anzahl strukturierter Beispiele. Dadurch erleben sie den Aufwand und die Schwierigkeit von Labeling, Schema-Definition und Datenqualität.
2. **Vorgefertigter Format-Datensatz**
   Ein größerer, synthetisch erzeugter Datensatz mit IT-Störmeldungen und zugehörigen JSON-Zielstrukturen. Dieser Datensatz dient dem erfolgreichen LoRA-Training für Format- und Verhaltenstreue.
3. **Vorgefertigter Wissens-Fallen-Datensatz**
   Ein Datensatz, mit dem versucht wird, dem Modell neues Faktenwissen beizubringen, zum Beispiel zu einem fiktiven IT-System oder einem internen Tool. Dieser Datensatz ist didaktisch als bewusste Falle angelegt: Er zeigt, dass LoRA Verhalten und Format gut adaptieren kann, aber nur begrenzt geeignet ist, neues Faktenwissen stabil zu verankern.

Diese Dreiteilung ermöglicht eine sehr klare spätere Differenzierung:

* Prompting für einfache Aufgaben,
* RAG für Faktenwissen,
* LoRA für Format, Stil, Verhalten und Latenzoptimierung.

---

## 3. Grobe Struktur der Unterrichtseinheit

Die Unterrichtseinheit wird in sechs inhaltliche Kapitel gegliedert. Diese können je nach Zeitbudget, Vorkenntnissen und technischer Infrastruktur unterschiedlich gewichtet werden.

| Kapitel | Thema | Schwerpunkt |
| :--- | :--- | :--- |
| 1 | Warum LoRA? | Einordnung, Motivation, Entscheidungsrahmen |
| 2 | Wie LoRA funktioniert | Transformer, Low-Rank-Prinzip, Bypass, Mathematik |
| 3 | Daten und Wissensfalle | Datensatzdesign, Formate, Labeling, didaktische Falle |
| 4 | Praktisches Labor | On-Premise-Training, Konfiguration, Variationen |
| 5 | Evaluation und Einordnung | Metriken, Aha-Momente, RAG-LoRA-Abgrenzung |
| 6 | Betrieb und Ökosystem | Adapter, Deployment, Lizenz, Supply-Chain |

---

## Kapitel 1: Warum LoRA?

### 1.1 Historische Einordnung

Die Teilnehmenden erhalten eine kurze Einordnung in die Entwicklung der Modelladaptierung.

Früher war klassisches Fine-Tuning häufig der Standard, um Modelle für spezialisierte Fachdomänen anzupassen. Inzwischen haben sich jedoch mehrere Entwicklungen ergeben:

* Basismodelle sind deutlich leistungsfähiger geworden.
* Kontextfenster sind stark gewachsen.
* Reasoning-Fähigkeiten haben sich verbessert.
* RAG hat sich als effiziente Methode zur Einbindung externen Wissens etabliert.
* Prompt Engineering und Context Engineering sind zentrale Werkzeuge geworden.
* Agent Skills ermöglichen prozedurale Anpassungen ohne klassisches Training.

Daraus entsteht die zentrale Frage:

> Wann lohnt sich heute überhaupt noch Fine-Tuning?

### 1.2 Moderne Entscheidungslogik

Die Teilnehmenden lernen eine mehrstufige Entscheidungslogik kennen:

1. **Prompt Engineering / Context Engineering**
   Die einfachste und schnellste Methode.
2. **RAG**
   Wenn externes, aktuelles oder internes Faktenwissen benötigt wird.
3. **Agent Skills / Werkzeuge**
   Wenn prozedurales Wissen oder externe Aktionen benötigt werden.
4. **PEFT / LoRA**
   Wenn Verhalten, Format, Stil, Latenz oder domänenspezifische Ausgabestrukturen zuverlässig trainiert werden sollen.
5. **Full Fine-Tuning**
   Wenn sehr spezifische Anforderungen vorliegen und Ressourcen ausreichend sind.

Diese Logik bildet den roten Faden der Unterrichtseinheit.

### 1.3 Warum On-Premise?

Da viele Teilnehmende aus Unternehmenskontexten kommen, wird bewusst ein On-Premise-Szenario gewählt.

Gründe:

* Datenschutz,
* Informationssicherheit,
* Compliance,
* keine Übertragung sensibler Daten in externe Cloud-Dienste,
* realistische betriebliche Restriktionen.

Die Teilnehmenden sollen lernen, dass Modelladaptation nicht nur ein Cloud-Thema ist, sondern auch in lokalen, kontrollierten Umgebungen funktionieren muss.

### 1.4 Erste Leitfrage

Die zentrale Leitfrage dieses Kapitels lautet:

> Wenn ein starkes Basismodell viele Aufgaben bereits per Prompting oder Few-Shot lösen kann: Warum sollten wir dann überhaupt LoRA trainieren?

Diese Frage wird im Verlauf der Unterrichtseinheit empirisch beantwortet.

---

## Kapitel 2: Wie LoRA funktioniert

### 2.1 Kurzreview Transformer-Architektur

Bevor LoRA eingeführt wird, findet ein kurzes Review der Transformer-Funktionalität statt.

Im Zentrum stehen:

* Self-Attention als Mechanismus zur Kontextbildung,
* Feed-Forward-Netzwerke als Speicher für Muster und Wissen,
* die Stapelung vieler Schichten,
* die zunehmende Abstraktion über die Schichten hinweg.

Vereinfachtes Modellbild:

| Bereich | Funktion |
| :--- | :--- |
| Attention | Kontext, Beziehungen, Abhängigkeiten zwischen Tokens |
| FFN | Muster, Wissen, Transformation der Repräsentation |
| untere Schichten | Syntax, lokale Wortbeziehungen |
| mittlere Schichten | Kontextaufbau, Referenzen, lokale Semantik |
| obere Schichten | abstrakte Bedeutung, Stil, Logik, Aufgabe |

Dieses Modellbild ist bewusst vereinfacht, aber für die LoRA-Einordnung hilfreich.

### 2.2 Das Grundproblem von Fine-Tuning

Klassisches Fine-Tuning verändert die Gewichtsmatrizen des gesamten Modells. Das führt zu mehreren Problemen:

* hoher Speicherbedarf,
* hohe Rechenkosten,
* Risiko von Catastrophic Forgetting,
* schwierige Wartbarkeit,
* große Adaptergröße,
* geringere Flexibilität im Betrieb.

Die Teilnehmenden sollen verstehen, dass die Anpassung eines Milliardenparameter-Modells nicht trivial ist.

### 2.3 Die Grundidee von LoRA

LoRA steht für Low-Rank Adaptation.

Die Grundidee lautet:

> Statt die großen Gewichtsmatrizen des Basismodells direkt zu verändern, wird ein kleiner, zusätzlich trainierbarer Bypass eingefügt.

Das Basismodell bleibt eingefroren. Nur die LoRA-Matrizen werden trainiert.

Die zentrale Formel lautet:

`h = Wx + BAx`

Dabei gilt:

* `W`: eingefrorene Originalgewichtsmatrix,
* `x`: Eingabe,
* `B` und `A`: kleine LoRA-Matrizen,
* `BA`: niedrigdimensionale Approximation der Gewichtsveränderung,
* `h`: Ausgabe der adaptierten Schicht.

### 2.4 Metapher: Der parallele Bypass

LoRA kann als paralleler Bypass verstanden werden.

Das Basismodell bleibt die Hauptstraße. LoRA fügt einen kleinen zusätzlichen Pfad hinzu, der das Ausgangssignal gezielt verändert.

Diese Metapher ist besonders nützlich, weil sie mehrere Punkte gleichzeitig erklärt:

* Das Basismodell bleibt erhalten.
* Die Veränderung ist additiv.
* Der Bypass ist klein.
* Der Bypass kann aktiviert oder deaktiviert werden.
* Mehrere Bypässe können prinzipiell nebeneinander existieren.

### 2.5 LoRA als Wiedersehen mit PCA

Eine besonders elegante didaktische Brücke ergibt sich zur Hauptkomponentenanalyse (PCA).

LoRA basiert auf der Annahme, dass die für eine Anpassung relevante Veränderung der Gewichtsmatrix eine niedrige intrinsische Dimension besitzt.

Statt eine große Matrix vollständig zu verändern, reicht häufig eine Approximation mit niedrigem Rang.

Didaktisch lässt sich dies über eine kleine Demonstration zeigen:

* Eine Gewichtsmatrix, zum Beispiel `q_proj`, wird aus dem Modell ausgelesen.
* Ihre Singulärwerte werden geplottet.
* Die Teilnehmer sehen, dass viele Singulärwerte schnell abfallen.
* Daraus folgt: Eine niedrigrangige Approximation kann einen großen Teil der Struktur abbilden.

Damit wird LoRA nicht als isoliertes Verfahren präsentiert, sondern als bekannte Idee der Dimensionsreduktion in neuem Kontext.

### 2.6 Speicherrechnung als aktive Aufgabe

Die Teilnehmenden sollen die Speicherersparnis nicht nur behauptet bekommen, sondern selbst nachvollziehen.

Beispielhafte Fragestellung:

> Wie viel Speicher benötigt vollständiges Fine-Tuning eines 1B-Modells im Vergleich zu LoRA?

Dabei werden berücksichtigt:

* Modellgewichte,
* Optimizer-Zustände,
* Gradienten,
* Master-Weights,
* Aktivierungen,
* trainierbare Parameter.

Ziel ist die Einsicht:

> LoRA reduziert den trainierbaren Anteil der Parameter drastisch und macht Fine-Tuning dadurch auf lokaler Hardware praktikabel.

### 2.7 Wichtige LoRA-Parameter

Die Teilnehmenden lernen die zentralen Stellgrößen kennen.

#### Rang `r`

Der Rang bestimmt die Kapazität des LoRA-Bypasses.

* kleiner Rang: wenig Parameter, starke Regularisierung,
* größerer Rang: mehr Anpassungsfähigkeit,
* sehr großer Rang: höhere Gefahr von Overfitting.

#### Alpha `alpha`

Alpha wirkt als Skalierungsfaktor für das LoRA-Signal.

Faustregel:

`alpha ≈ 2r`

#### Dropout

LoRA-Dropout kann regularisierend wirken.

#### Target Modules

Es kann entschieden werden, an welchen Stellen des Transformers LoRA angebracht wird:

* nur Attention-Bereiche, zum Beispiel `q_proj`, `v_proj`,
* alle Attention-Projektionen,
* zusätzlich FFN-Schichten,
* alle linearen Schichten.

Diese Wahl beeinflusst:

* Parameterzahl,
* Speicherbedarf,
* Trainingszeit,
* Anpassungsfähigkeit,
* Risiko von Überanpassung.

---

## Kapitel 3: Daten und Wissensfalle

### 3.1 Die Rolle der Daten

LoRA ist stark datenabhängig. Die Qualität der Trainingsdaten entscheidet wesentlich über den Erfolg der Adaptierung.

Die Teilnehmenden lernen:

* Datenqualität vor Datenmenge,
* konsistente Formate,
* klare Zielstruktur,
* saubere Trennung von Training und Test,
* realistische Aufgabenstellung,
* Vermeidung von Zielkonflikten.

### 3.2 Drei Datensätze

Die Unterrichtseinheit arbeitet mit drei Datensätzen.

#### Datensatz A: Manuell kuratierter Datensatz

Die Teilnehmenden erstellen selbst eine kleine Anzahl von Beispielen.

Beispiel:

**Eingabe:**

> „Der Exchange-Server antwortet seit heute Morgen nicht mehr. Mehrere Nutzer melden, dass keine E-Mails versendet werden können. Neustart hat nichts gebracht.“

**Erwartete Ausgabe:**

```json
{
  "komponente": "Mailserver",
  "system": "Exchange",
  "schweregrad": "hoch",
  "fehlerkategorie": "Dienst nicht erreichbar",
  "naechster_schritt": "Dienststatus prüfen und ggf. Service neu starten"
}
```

Ziele:

* Verständnis für Labeling,
* Verständnis für Schema-Design,
* Erkennen von Mehrdeutigkeiten,
* Aufwand der Datenkuratierung erleben.

#### Datensatz B: Vorgefertigter Format-Datensatz

Ein größerer synthetischer Datensatz mit IT-Störmeldungen und JSON-Zielstruktur.

Zweck:

* erfolgreiches LoRA-Training,
* Erlernen stabiler Formatkonformität,
* Vergleich mit Few-Shot-Prompting,
* Messung der Schema-Validitätsrate.

#### Datensatz C: Wissens-Fallen-Datensatz

Ein Datensatz, der versucht, dem Modell neues Faktenwissen beizubringen.

Beispiel:

> Ein fiktives internes System namens „NexusCMDB 4.2“ mit speziellen Fehlercodes, Betriebshandbüchern und internen Eskalationsstufen.

Zweck:

* LoRA soll scheinbar neues Wissen lernen,
* das Ergebnis bleibt instabil oder unzuverlässig,
* dadurch entsteht die Erkenntnis: LoRA ist nicht automatisch ein Wissens-Injector.

Diese Falle ist didaktisch besonders wertvoll.

### 3.3 Die didaktische Wissensfalle

Die zentrale Fehlvorstellung vieler Teilnehmender lautet:

> „Mit LoRA bringe ich dem Modell einfach unsere Firmenfacts bei.“

Die Unterrichtseinheit führt diese Erwartung kontrolliert herbei und widerlegt sie anschließend empirisch.

Lernziel:

> LoRA eignet sich besonders gut für Verhalten, Format, Stil und Aufgabensteuerung. Für Faktenwissen ist häufig RAG die bessere Architektur.

Dadurch wird die Entscheidung zwischen LoRA und RAG nicht nur behauptet, sondern praktisch erfahrbar.

### 3.4 Datenformate

Die Teilnehmenden lernen typische Trainingsformate kennen.

#### Instruction-Format

Beispiel:

```json
{
  "instruction": "Extrahiere aus der Störmeldung die relevanten Felder.",
  "input": "Der Exchange-Server antwortet seit heute Morgen nicht mehr.",
  "output": "{\"komponente\": \"Mailserver\", ...}"
}
```

#### Chat-Format

Beispiel:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein Assistent für IT-Störmeldungen. Antworte ausschließlich mit validem JSON."
    },
    {
      "role": "user",
      "content": "Der Exchange-Server antwortet seit heute Morgen nicht mehr."
    },
    {
      "role": "assistant",
      "content": "{\"komponente\": \"Mailserver\", ...}"
    }
  ]
}
```

Die Wahl des Formats hat praktische Konsequenzen für:

* Chat-Template,
* Tokenisierung,
* Rollentrennung,
* Inferenzverhalten,
* Wiederverwendbarkeit.

---

## Kapitel 4: Praktisches Labor

### 4.1 Ziel des Labors

Im Labor führen die Teilnehmenden ein LoRA-Training auf lokalen Maschinen durch. Der Fokus liegt nicht auf dem Schreiben eines vollständigen Trainings-Frameworks, sondern auf:

* Nachvollziehen des Referenz-Notebooks,
* Konfigurieren relevanter Parameter,
* Durchführen kurzer Trainingsläufe,
* Beobachten von Verlustkurven,
* Vergleichen von Varianten,
* Erkennen praktischer Einschränkungen.

### 4.2 Hardware- und Systemvarianten

Das Labor soll unterschiedliche lokale Umgebungen abbilden.

#### CUDA-Umgebung

Für Windows- und Linux-Systeme mit NVIDIA-GPU:

* Training mit CUDA,
* bevorzugt bf16 oder fp16,
* lokale Ausführung,
* optional QLoRA-Demo bei ausreichender Hardware.

#### Apple Silicon / MPS

Für macOS-Systeme:

* Training über Metal Performance Shaders,
* bewusst vereinfachte Konfiguration,
* mögliche Einschränkungen bei bestimmten Quantisierungs-Backends,
* bevorzugt kleinere Modelle, zum Beispiel Qwen3-0.6B oder Qwen3-1.7B,
* Fokus auf lauffähige LoRA- statt komplexe QLoRA-Experimente.

#### Fallback bei knapper Hardware

Falls der Speicher nicht ausreicht:

* kleineres Modell verwenden,
* Batch-Size reduzieren,
* Sequenzlänge begrenzen,
* Rang reduzieren,
* weniger Zielmodule verwenden,
* ggf. nur kurze Trainingsdemo durchführen.

### 4.3 Referenz-Notebook

Das Labor nutzt ein vorbereitetes Referenz-Notebook.

Es enthält:

* Laden des Basismodells,
* Laden des Tokenizers,
* Vorbereitung des Datensatzes,
* Definition der LoRA-Konfiguration,
* Start des Trainings,
* Speicherung des Adapters,
* Inferenz mit und ohne LoRA,
* einfache Evaluation.

Die Teilnehmenden schreiben nicht den gesamten Trainingscode selbst. Stattdessen lernen sie:

* welche Parameter wichtig sind,
* welche Auswirkungen Änderungen haben,
* wie man Ergebnisse interpretiert,
* wie man Fehlerquellen erkennt.

### 4.4 Trainingskonfiguration

Beispielhafte LoRA-Konfiguration:

```python
from peft import LoraConfig

lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=[
        "q_proj",
        "v_proj"
    ],
    bias="none",
    task_type="CAUSAL_LM"
)
```

Mögliche Varianten für Gruppenarbeit:

| Gruppe | Variation | Ziel |
| :--- | :--- | :--- |
| Gruppe 1 | `r=4` | sehr kleine Kapazität |
| Gruppe 2 | `r=16` | mittlere Kapazität |
| Gruppe 3 | `r=64` | hohe Kapazität / Overfitting-Risiko |
| Gruppe 4 | nur Attention | minimale Anpassung |
| Gruppe 5 | Attention + FFN | breitere Anpassung |
| Gruppe 6 | wenige Daten | Einfluss kleiner Datensätze |
| Gruppe 7 | mehr Daten | Einfluss größerer Datensätze |

### 4.5 Vergleichsgruppen

Besonders wichtig ist eine Few-Shot-Baseline.

Die Teilnehmenden vergleichen:

1. Basismodell ohne LoRA,
2. Basismodell mit gutem Prompt,
3. Basismodell mit Few-Shot-Beispielen,
4. Basismodell mit LoRA.

Dadurch wird sichtbar:

* Prompting ist schnell und billig,
* Few-Shot kann überraschend gut funktionieren,
* LoRA kann stabiler und latenzärmer sein,
* LoRA ist nicht automatisch immer besser.

### 4.6 Mögliche Laboraufgaben

#### Aufgabe 1: Modell laden

Die Teilnehmenden laden das Basismodell lokal und prüfen:

* Modellgröße,
* Speicherbedarf,
* Gerätetyp,
* Lauffähigkeit.

#### Aufgabe 2: Inferenz ohne LoRA

Eine IT-Störmeldung wird ohne Anpassung verarbeitet.

Fragestellungen:

* Hält sich das Modell an das JSON-Schema?
* Erfindet es Felder?
* Nutzt es erlaubte Labels?
* Wie stabil ist die Ausgabe?

#### Aufgabe 3: Few-Shot-Baseline

Dasselbe Problem wird mit wenigen Beispielen im Prompt gelöst.

Fragestellungen:

* Verbessert sich die Ausgabe?
* Wie groß wird der Prompt?
* Welche Latenz entsteht?
* Wie robust ist das Verhalten?

#### Aufgabe 4: LoRA-Training

Die Teilnehmenden trainieren einen kleinen Adapter auf dem Format-Datensatz.

Fragestellungen:

* Sinkt der Loss?
* Wie lange dauert das Training?
* Wie groß ist der Adapter?
* Ändert sich das Ausgabenverhalten?

#### Aufgabe 5: Wissensfalle testen

Die Teilnehmenden trainieren oder testen einen Adapter auf dem Wissens-Fallen-Datensatz.

Fragestellungen:

* Kann das Modell neue Fakten zuverlässig wiedergeben?
* Halluziniert es?
* Verwechselt es Fakten?
* Bleibt das Basiswissen erhalten?

---

## Kapitel 5: Evaluation und Einordnung

### 5.1 Ziel der Evaluation

Evaluation ist nicht als nachgelagerter Schritt zu verstehen, sondern als zentrales Element der Unterrichtseinheit.

Die Teilnehmenden sollen lernen:

* Training ohne Evaluation ist Blindflug,
* subjektive Einschätzung reicht nicht aus,
* Metriken müssen zur Aufgabe passen,
* Testdaten müssen sauber getrennt sein,
* Ergebnisse müssen interpretiert werden.

### 5.2 Mögliche Metriken

Für die gewählte IT-Störmeldungs-Domäne bieten sich an:

#### Schema-Validitätsrate

Anteil der Ausgaben, die valide JSON-Strukturen erzeugen.

Beispiel:

`Schema-Validitätsrate = Anzahl valider JSON-Ausgaben / Anzahl getesteter Ausgaben`

#### Label-Exact-Match

Anteil exakt korrekt vorhergesagter Labels.

Beispiel:

* `schweregrad` korrekt,
* `fehlerkategorie` korrekt,
* `komponente` korrekt.

#### Feld-Recall

Anteil der erwarteten Felder, die tatsächlich vorhanden sind.

#### Feld-Precision

Anteil der erzeugten Felder, die tatsächlich erlaubt sind.

#### Latenz

Zeit pro Inferenz.

#### Tokenkosten

Länge von Prompt und Antwort.

### 5.3 Zentrale Vergleichsmatrix

Die Ergebnisse können in einer Entscheidungsmatrix zusammengeführt werden.

| Methode | Gut für | Weniger gut für | Vorteil | Risiko |
| :--- | :--- | :--- | :--- | :--- |
| Prompting | schnelle Anpassung, einfache Aufgaben | sehr stabile Formate, hohe Zuverlässigkeit | kein Training | Prompt kann lang und fragil werden |
| Few-Shot | verständliche Aufgaben mit Beispielen | sehr große Datenmengen, Produktionsskalierung | sofort einsetzbar | Kontextfenster, Latenz |
| RAG | Faktenwissen, interne Dokumente | Format- und Stiltraining | aktuell, erweiterbar | Retrieval-Qualität entscheidend |
| LoRA | Format, Stil, Verhalten, Latenz | neues Faktenwissen | klein, lokal, modular | Datenqualität entscheidend |
| Full Fine-Tuning | sehr spezifische Gesamtausbung | Ressourcenknappheit | maximale Anpassung | teuer, riskanter |

### 5.4 Der Aha-Moment

Der wichtigste Moment der Einheit entsteht, wenn die Teilnehmenden erkennen:

> LoRA kann das Modell sehr zuverlässig dazu bringen, ein bestimmtes Format einzuhalten.
> Aber LoRA macht das Modell nicht automatisch zu einer Wissensdatenbank.

Daraus folgt die Architekturentscheidung:

* **Faktenwissen** → RAG,
* **Verhalten und Format** → LoRA,
* **Kombination** → RAG + LoRA.

### 5.5 Katastrophales Vergessen

Ein weiteres wichtiges Thema ist Catastrophic Forgetting.

Beim klassischen Fine-Tuning kann das Modell zuvor gelerntes Wissen verlieren. LoRA reduziert dieses Risiko, weil das Basismodell eingefroren bleibt.

Didaktisch kann dies gezeigt werden, indem das Modell nach dem Training mit allgemeinen Fragen getestet wird:

* „Was ist eine IP-Adresse?“
* „Erkläre kurz DNS.“
* „Was bedeutet HTTP-Statuscode 500?“

Wenn das Modell weiterhin sinnvoll antwortet, zeigt dies die Stärke der Parameterisolation.

---

## Kapitel 6: Betrieb, Ökosystem und Supply-Chain

### 6.1 Adapter als Betriebsobjekt

LoRA-Adapter sind im Betrieb besonders attraktiv, weil sie klein und modular sind.

Ein Basismodell kann im Speicher bleiben, während verschiedene Adapter geladen werden.

Beispiel:

* Adapter A: IT-Störmeldungen als JSON,
* Adapter B: Support-Antworten in freundlichem Ton,
* Adapter C: technische Dokumentation als Markdown.

Dadurch entsteht ein wirtschaftlich interessantes Deployment-Szenario:

> Ein Basismodell im Speicher, mehrere Spezialisierungen auf der Festplatte.

### 6.2 Adapterdateien lesen

Die Teilnehmenden sollen verstehen, dass ein LoRA-Adapter kein undurchsichtiges Artefakt ist.

Wichtige Dateien:

* `adapter_model.safetensors` oder `adapter_model.bin`,
* `adapter_config.json`.

In `adapter_config.json` finden sich typischerweise:

* `r`,
* `lora_alpha`,
* `target_modules`,
* `lora_dropout`,
* `bias`,
* `task_type`.

Die Teilnehmenden lernen, diese Datei zu lesen und zu interpretieren.

### 6.3 Lizenz- und Compliance-Fragen

Da Modelle und Adapter in Unternehmen eingesetzt werden, sind Lizenzfragen relevant.

Beispielhafte Themen:

* Apache-2.0-Lizenz,
* eingeschränkte Community-Lizenzen,
* kommerzielle Nutzbarkeit,
* Weitergabe von Modellgewichten,
* Herkunft von Trainingsdaten,
* interne Freigabeprozesse.

### 6.4 Supply-Chain-Risiko

Fremde Adapter aus öffentlichen Repositories können Risiken enthalten:

* unbekannte Trainingsdaten,
* unklare Lizenz,
* versteckte Verzerrungen,
* manipulierte Gewichtungsdateien,
* inkompatible Konfiguration,
* unzureichende Dokumentation.

Die Teilnehmenden sollen lernen:

> Ein Adapter ist ein Softwareartefakt mit betrieblichem Risiko und sollte ähnlich geprüft werden wie andere externe Komponenten.

### 6.5 Brücke zu späteren Modulen

Die Unterrichtseinheit bereitet mehrere spätere Themen vor:

* Testmengen-Konstruktion,
* systematische Evaluation,
* Robustheitsprüfung,
* Dokumentation,
* Reproduzierbarkeit,
* Modellbetrieb,
* Compliance,
* Deployment-Pipelines.

---

## 4. Empfohlene dramaturgische Gesamtlogik

Die Unterrichtseinheit folgt einer bewussten Lernkurve:

1. **Motivation**
   Warum brauchen wir überhaupt noch Fine-Tuning?
2. **Verständnis**
   Was macht LoRA technisch?
3. **Datenarbeit**
   Welche Daten braucht LoRA?
4. **Praxis**
   Wie trainiert man LoRA lokal?
5. **Evaluation**
   Wo hilft LoRA wirklich?
6. **Einordnung**
   Wann nutzt man Prompting, RAG oder LoRA?

Die wichtigste didaktische Pointe lautet:

> LoRA ist kein universeller Wissens-Upload, sondern ein effizientes Verfahren zur Anpassung von Verhalten, Struktur, Format und Aufgabenstil.

---

## 5. Zusammenfassung der Lernziele

Nach der Unterrichtseinheit sollen die Teilnehmenden in der Lage sein:

* die Grundidee von LoRA zu erklären,
* die relevanten LoRA-Parameter zu deuten,
* ein kleines LoRA-Training lokal durchzuführen,
* Datensätze für LoRA sinnvoll zu beurteilen,
* den Unterschied zwischen Formatlernen und Wissenslernen zu erklären,
* LoRA gegenüber Prompting und RAG abzugrenzen,
* einfache Evaluationen durchzuführen,
* Adapter als betriebliche Artefakte zu verstehen,
* Risiken von externen Adaptern einzuschätzen,
* LoRA in eine lokale On-Premise-Strategie einzuordnen.

---

## 6. Kurzform für die Lehrkraft

**Kernidee der Einheit:**
LoRA wird nicht als isoliertes Fine-Tuning-Werkzeug unterrichtet, sondern als praktische Entscheidungsoption innerhalb einer modernen Adaptionsstrategie.

**Zentrale Praxis:**
Die Teilnehmenden trainieren lokal einen kleinen Adapter auf IT-Störmeldungen, um ein festes JSON-Schema zu erzeugen.

**Zentrale didaktische Falle:**
Ein zusätzlicher Datensatz versucht, neues Faktenwissen zu trainieren. Das Scheitern oder die Instabilität dieses Ansatzes führt zur Erkenntnis: Fakten gehören eher in RAG, Verhalten und Format eher in LoRA.

**Zentrale Metrik:**
Schema-Validitätsrate.

**Zentrale Schlussfolgerung:**
Prompting, RAG und LoRA sind keine Konkurrenten, sondern komplementäre Werkzeuge.
