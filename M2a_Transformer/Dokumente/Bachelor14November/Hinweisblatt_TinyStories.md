# Hinweisblatt: GuppyLM auf TinyStories trainieren

**Transformer, Lernsession · Hinweise zur Orientierung**

> **Auftrag:** Trainieren Sie den Guppy-Transformer auf einem anderen Datensatz: TinyStories, kurze englische Geschichten in einfacher Sprache. Dieses Blatt gibt Anhaltspunkte, keine fertige Lösung.

Datensatz: [huggingface.co/datasets/roneneldan/TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories)

## 1. Kann das überhaupt funktionieren?

Ja. TinyStories wurde genau für sehr kleine Sprachmodelle entworfen. Die Autoren zeigen, dass schon Modelle unter 10 Millionen Parametern mit einer Embedding-Dimension von 256 flüssige, zusammenhängende Geschichten erzeugen [1]. Guppy liegt mit knapp 12 Millionen Parametern und Dimension 384 darüber.

Die Architektur muss also nicht geändert werden. Ändern müssen Sie den Weg der Daten ins Modell.

```mermaid
flowchart LR
    A["TinyStories<br/>2,12 Mio. Geschichten"] --> B["Teilmenge<br/>wählen"]
    B --> C["Lange Geschichten<br/>aussortieren"]
    C --> D["Start- und Endtoken<br/>ergänzen"]
    D --> E["Tokenizer<br/>neu trainieren"]
    E --> F["Training<br/>deutlich länger"]
    F --> G["Fortsetzen<br/>statt antworten"]
```

## 2. Der wichtigste Unterschied zu Guppy

Bei Guppy ändert sich nach etwa 3.000 Schritten nichts mehr. Bei TinyStories ist das anders.

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 170" width="100%" style="max-width:760px" font-family="Helvetica, Arial, sans-serif" role="img">
<rect x="0" y="0" width="760" height="170" rx="10" fill="#ffffff" stroke="#e5e7eb"/>
<text x="30" y="34" font-size="15" fill="#1f2937" text-anchor="start" font-weight="bold">Wie viel von TinyStories sieht ein Lauf mit 3.000 Schritten?</text>
<rect x="30" y="56" width="700" height="34" fill="#f3f4f6" stroke="#6b7280" stroke-width="1.5"/>
<rect x="30" y="56" width="31.7" height="34" fill="#dbeafe" stroke="#2563eb" stroke-width="1.5"/>
<text x="30" y="112" font-size="12" fill="#2563eb" text-anchor="start">96.000 gezogene Geschichten (3.000 Schritte × 32)</text>
<text x="730" y="112" font-size="12" fill="#6b7280" text-anchor="end">2,12 Millionen Geschichten im Trainingssplit</text>
<text x="30" y="146" font-size="12" fill="#1f2937" text-anchor="start">Bei Guppy reichen 3.000 Schritte, weil sich die Daten ständig wiederholen. Hier ist fast jede Geschichte neu.</text>
</svg>

| | Guppy-Dialoge | TinyStories |
|---|---|---|
| Trainingsbeispiele | 57.000, davon 15.613 verschiedene | 2,12 Millionen [2] |
| Umfang in Tokens | klein | rund 500 Millionen, je nach Tokenizer [3] |
| Typische Länge eines Beispiels | kurz | etwa 200 Tokens [3] |
| Validierungsdaten | zu großen Teilen im Training enthalten | eigener Split mit 22.000 Geschichten [2] |

Ein Lauf mit 3.000 Schritten sieht 96.000 Geschichten, also rund 4 bis 5 % des Datensatzes. Zum Vergleich: Nachbauten der TinyStories-Modelle trainieren auf etwa 1 Milliarde [4] bis 2 Milliarden Tokens [5]. Das ist das 50- bis 100-Fache.

**Folge:** Nach 3.000 Schritten dürfen Sie geschichtenartigen Text erwarten, aber noch keine durchgehend schlüssige Handlung. Der Verlust fällt weiter, wenn Sie länger trainieren. Beobachten Sie genau das.

## 3. Fünf Hinweise zur Datenaufbereitung

### Hinweis 1: Nicht den ganzen Datensatz laden

Das Notebook tokenisiert alle Beispiele vorab und hält sie als Python-Listen im Speicher. Bei 57.000 kurzen Dialogen ist das unproblematisch. Bei 2,12 Millionen Geschichten dauert es lange und kostet viel Arbeitsspeicher.

- Ein Lauf mit 3.000 Schritten zieht ohnehin nur 96.000 Beispiele.
- Eine Teilmenge von etwa 100.000 Geschichten genügt für den Einstieg.
- **Zum Nachdenken:** Was ändert sich, wenn Sie später 20.000 Schritte trainieren? Wie groß sollte die Teilmenge dann sein, damit das Modell nicht dieselben Geschichten immer wieder sieht?

### Hinweis 2: Zu lange Geschichten aussortieren

`zu_sequenzen` bricht mit einer Fehlermeldung ab, sobald ein Beispiel länger als `max_seq_len + 1` Tokens ist. Es wird nichts stillschweigend abgeschnitten. Das ist Absicht und bleibt so.

- Lassen Sie sich zuerst die Längenverteilung zeigen (die Zelle dafür gibt es schon in Abschnitt 2 des Notebooks).
- Entscheiden Sie dann: Geschichten oberhalb einer Grenze weglassen oder das Kontextfenster vergrößern.
- **Zum Nachdenken:** Warum ist Weglassen hier besser als Abschneiden? Was würde ein Modell aus abgeschnittenen Geschichten über das Ende einer Geschichte lernen?

### Hinweis 3: Das Kontextfenster bewusst wählen

Muss `max_seq_len` auf 512? Nicht zwingend.

- Das Originalpaper arbeitet mit Kontextlänge 512 [1], ein anderer veröffentlichter Aufbau mit 256 [5].
- Die meisten Geschichten haben etwa 200 Tokens [3].
- Mit einer Filtergrenze von 256 Tokens und `max_seq_len = 256` behalten Sie den Großteil der Daten und sparen viel Rechenzeit.

Der Rechenaufwand der Attention wächst mit dem Quadrat der Sequenzlänge. Eine Verdopplung von 256 auf 512 kostet deshalb deutlich mehr als das Doppelte, sobald die Batches tatsächlich so lang werden.

### Hinweis 4: Anfang und Ende markieren

Guppys Daten liegen im ChatML-Format vor, mit Rollen für Frage und Antwort. TinyStories enthält nur Fließtext.

- Ohne Endmarkierung lernt das Modell nie, eine Geschichte zu beenden. Die Generierung läuft dann immer bis zum Tokenlimit.
- Die Sondertokens des Notebooks lassen sich weiterverwenden: eines am Anfang, eines am Ende jeder Geschichte.
- **Prüfen Sie am ersten geladenen Beispiel,** ob ein Eintrag wirklich eine ganze Geschichte ist. Die ursprünglichen Textdateien trennen Geschichten nicht durch Zeilenumbrüche, sondern durch eine Endmarke; je nach Ladeweg erhalten Sie sonst einzelne Zeilen [6].

### Hinweis 5: Fortsetzen statt antworten

Die Funktion `antworte` baut einen Chat-Prompt mit Rollen. Für Geschichten passt das nicht mehr.

- Sie brauchen eine Funktion, die einen Geschichtenanfang kodiert und `erzeuge` direkt aufruft.
- Typische Anfänge: `Once upon a time`, `One day, a little girl named Lily`.
- `erzeuge` sperrt das Starttoken. Überlegen Sie, ob das für Ihr neues Format weiterhin sinnvoll ist.

## 4. Was sonst noch anzupassen ist

| Stelle | Guppy | TinyStories |
|---|---|---|
| Tokenizer | auf Fischdialogen trainiert | neu trainieren; Groß- und Kleinschreibung, Satzzeichen und Namen kommen hinzu |
| Vokabulargröße | Zielgröße 4.096, tatsächlich kleiner | Zielgröße 4.096 wird voraussichtlich ausgeschöpft; ein veröffentlichter Aufbau nutzt genau diese Größe [5], das Originalpaper 10.000 [1] |
| `MAX_STEPS` | 3.000 genügen | deutlich mehr; Verlustkurve beobachten |
| Validierung | 320 Beispiele, viele Duplikate | eigener Validierungssplit; der Wert ist hier aussagekräftiger |
| Positionstabelle | 128 Zeilen | entsprechend dem neuen `max_seq_len` |

## 5. Wie lange dauert das?

Die folgenden Zahlen sind **Schätzungen**, keine Messungen. Sie gehen von einem Gerät aus, das 3.000 Guppy-Schritte in etwa fünf Minuten schafft.

| Einstellung | Aufwand je Schritt gegenüber Guppy | 3.000 Schritte | 15.000 Schritte |
|---|---|---|---|
| Kontext 256, Geschichten gefiltert | etwa 3- bis 5-fach | 15 bis 25 Minuten | 1,5 bis 2 Stunden |
| Kontext 512, ungefiltert | etwa 8- bis 15-fach | 40 bis 75 Minuten | 3,5 bis 6 Stunden |

**Empfehlung:** Machen Sie zuerst einen Probelauf mit 300 Schritten. Aus dessen Laufzeit können Sie den großen Lauf hochrechnen und über Nacht starten.

## 6. Was Sie beobachten und festhalten sollten

1. Verlustkurve: Wo flacht sie ab? Flacht sie überhaupt ab?
2. Textproben zum selben Anfang nach 1.000, 3.000 und der letzten Stufe, jeweils bei Temperatur 0 und bei 0,7.
3. Abbruchgrund: Lernt das Modell, eine Geschichte zu beenden?
4. Vergleich mit Guppy: Was ist bei diesem Datensatz schwerer, was leichter? Woran liegt das?
5. Trainings- gegen Validierungsverlust: Sehen Sie Anzeichen von Auswendiglernen?

## 7. Anschluss: Instruction-Tuning

Wenn Ihr Modell brauchbare Geschichten schreibt, können Sie ihm in einer zweiten Phase beibringen, Vorgaben zu befolgen.

- Vom selben Autor gibt es dafür **TinyStoriesInstruct** [7]. Jedes Beispiel beginnt mit Kopfzeilen und enthält danach die Geschichte. Die Kopfzeilen nennen etwa Wörter, die vorkommen sollen (`Words:`), Eigenschaften der Geschichte (`Features:`), eine Zusammenfassung (`Summary:`) oder einen Satz, der enthalten sein muss (`Random sentence:`) [8].
- **Zweischritt:** zuerst auf reinen Geschichten vortrainieren, dann mit kleinerer Lernrate auf dem Instruct-Format weitertrainieren.
- Wegen der Kopfzeilen sind die Beispiele länger. Hier ist ein Kontextfenster von 512 tatsächlich sinnvoll.
- **Prüfidee:** Geben Sie drei Wörter vor. Kommen sie in der Geschichte vor? Vergleichen Sie mit dem nur vortrainierten Modell.

**Zum Nachdenken:** Guppy wurde in einem einzigen Schritt auf Dialogen trainiert. Worin unterscheidet sich Ihr zweistufig trainiertes Modell von Guppy, und was haben beide gemeinsam? Welche Verlustfunktion verwenden die beiden Phasen?

## Quellen

1. Eldan, R.; Li, Y. (2023): *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* [arXiv:2305.07759](https://arxiv.org/abs/2305.07759), lesbare Fassung: [ar5iv.labs.arxiv.org/html/2305.07759](https://ar5iv.labs.arxiv.org/html/2305.07759)
2. Datensatzseite TinyStories (Größe der Splits, Dateien, Lizenz CDLA-Sharing-1.0). [huggingface.co/datasets/roneneldan/TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories)
3. *Small is Beautiful: Building Tiny LLMs* (Erfahrungsbericht: Umfang in Tokens, typische Länge, Packen von Beispielen). [jaelisans.substack.com/p/small-is-beautiful-building-tiny](https://jaelisans.substack.com/p/small-is-beautiful-building-tiny)
4. Llama-TinyStories, Nachbau mit Kontextlänge 512 und rund 1 Milliarde Trainingstokens. [huggingface.co/vinothkumarn/Llama-TinyStories](https://huggingface.co/vinothkumarn/Llama-TinyStories)
5. *Bilinear MLPs enable weight-based mechanistic interpretability* (2024), Anhang G.2 (TinyStories-Aufbau mit Vokabular 4.096 und Kontextlänge 256). [arXiv:2410.08417](https://arxiv.org/abs/2410.08417)
6. TinyStories, Diskussion zum Dateiformat. [huggingface.co/datasets/roneneldan/TinyStories/discussions/2](https://huggingface.co/datasets/roneneldan/TinyStories/discussions/2)
7. Datensatz TinyStoriesInstruct. [huggingface.co/datasets/roneneldan/TinyStoriesInstruct](https://huggingface.co/datasets/roneneldan/TinyStoriesInstruct)
8. TinyStories, Diskussion zum Aufbau des Instruct-Formats. [huggingface.co/datasets/roneneldan/TinyStories/discussions/11](https://huggingface.co/datasets/roneneldan/TinyStories/discussions/11)
