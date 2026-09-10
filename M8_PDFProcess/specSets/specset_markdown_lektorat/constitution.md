# Constitution: Markdown-Lektorat für OCR-Dokumente

**Version:** 1.0  
**Status:** Verbindlich  
**Datum:** 2026-09-08  
**Geltungsbereich:** Modul zur LLM-gestützten Korrektur OCR-erzeugter Markdown-Dokumente

---

## Präambel

Diese Constitution definiert die verbindlichen Entwicklungs- und Qualitätsregeln für das Modul zur Nachbearbeitung OCR-erzeugter Markdown-Dokumente.

Sie steht über `spec.md`, `plan.md`, `tasks.md` und der Implementierung.

Alle nachgelagerten Artefakte und Codeänderungen müssen mit diesen Regeln vereinbar sein.

Die Constitution enthält bewusst nur dauerhafte Projektprinzipien und keine flüchtigen Implementierungsdetails.

---

# I. Spec als Source of Truth

## I.1 Verbindlichkeit

`spec.md` definiert das fachlich gewünschte Verhalten des Moduls.

`plan.md` beschreibt die technische Umsetzung.

`tasks.md` zerlegt diese Umsetzung in ausführbare und testbare Arbeitsschritte.

Die Implementierung folgt `tasks.md`, darf aber weder `spec.md` noch diese Constitution verletzen.

## I.2 Keine stillschweigende Anforderungsänderung

Während der Implementierung dürfen Anforderungen nicht implizit umgedeutet, abgeschwächt oder erweitert werden.

Wird festgestellt, dass eine Anforderung:

- unvollständig,
- widersprüchlich,
- technisch ungeeignet oder
- aufgrund realer Dokumente unzutreffend

ist, wird die Implementierung nicht durch eine verdeckte Sonderlösung angepasst.

Stattdessen beginnt ein Living-Spec-Zyklus.

---

# II. Test First

## II.1 Red-Green-Prinzip

Implementierbare Anforderungen werden, soweit technisch sinnvoll, testgetrieben entwickelt.

Für jede relevante Funktion gilt grundsätzlich:

1. erwartetes Verhalten als Test definieren;
2. Test ausführen;
3. erwarteten Fehlerzustand (`RED`) bestätigen;
4. minimale Implementierung erstellen;
5. Test erneut ausführen;
6. erfolgreichen Zustand (`GREEN`) herstellen;
7. bei Bedarf refaktorieren, ohne das Verhalten zu verändern.

## II.2 Tests vor Implementierung

Produktionscode soll nicht geschrieben werden, bevor der zugehörige automatisierte Test oder Contract-Test existiert.

Ausnahmen sind nur zulässig für:

- explorative Prototypen, die nicht in den Produktionscode übernommen werden;
- rein manuelle Human-in-the-loop-Evaluierungen;
- technische Sachverhalte, die vernünftigerweise nicht automatisiert testbar sind.

## II.3 Regression

Jeder behobene Fehler, der reproduzierbar automatisiert getestet werden kann, erhält einen Regressionstest.

Ein bereits behobener Fehler darf dadurch nicht unbemerkt wieder auftreten.

---

# III. Quelltreue vor Verbesserung

## III.1 Primäres Ziel

Das System restauriert und korrigiert vorhandenen Dokumentinhalt.

Es erzeugt keinen neuen Inhalt.

## III.2 Keine fachliche Modernisierung

Historische, technische oder sprachliche Aussagen der Quelle dürfen nicht allein deshalb geändert werden, weil heutiges Wissen oder heutiger Sprachgebrauch davon abweicht.

## III.3 Keine stilistische Überarbeitung

Ein bereits plausibler Text darf nicht nur aus stilistischen Gründen umformuliert werden.

## III.4 Unsicherheit vor Erfindung

Kann der ursprüngliche Inhalt nicht ausreichend sicher rekonstruiert werden, bleibt der vorhandene Inhalt unverändert.

Ein explizites `unresolved` ist einer plausibel klingenden, aber nicht belegbaren Rekonstruktion vorzuziehen.

---

# IV. Geschützte Elemente sind unverletzliche Invarianten

## IV.1 Bildreferenzen

Vorhandene Markdown-Bildreferenzen dürfen weder verändert noch verschoben werden.

## IV.2 Seitenumbrüche

Vorhandene Seitenumbruchmarker dürfen weder verändert, entfernt noch in ihrer Reihenfolge verändert werden.

## IV.3 Integritätsverletzung

Eine Verletzung geschützter Elemente ist ein harter Fehler.

Ein Lauf mit verletzten Invarianten darf nicht als erfolgreich finalisiert werden.

---

# V. Klare Trennung zwischen LLM und Python

## V.1 LLM-Verantwortung

Das LLM ist die semantische und layoutlogische Entscheidungsinstanz.

Dazu gehören insbesondere:

- Rekonstruktion beschädigten Textes;
- Lesereihenfolge;
- Erkennung echter Duplikate;
- Zuordnung von Abbildungsbeschriftungen;
- Zuordnung von Tabellenbeschriftungen;
- semantische Rekonstruktion beschädigter Tabellen.

## V.2 Python-Verantwortung

Python übernimmt formale und technische Aufgaben.

Dazu gehören insbesondere:

- Schema-Validierung;
- Datentypprüfung;
- Source-Match;
- erlaubte Operationsarten;
- Integritätsprüfung;
- Dateizugriff;
- Anwendung freigegebener Edits;
- formale Markdown- und Tabellenprüfung.

## V.3 Kein semantischer Determinismus in Python

Python darf keine eigene semantische Layoutentscheidung erzwingen.

Insbesondere dürfen keine deterministischen Heuristiken verwendet werden, die aus:

- Abstand,
- Seitenposition,
- Blockreihenfolge,
- Caption-Nummerierung,
- Zeilenanzahl oder
- ähnlichen Layoutmerkmalen

selbständig eine inhaltliche Zuordnung ableiten.

Solche Informationen dürfen dem LLM als Kontext bereitgestellt werden.

Die eigentliche semantische Entscheidung bleibt beim LLM.

---

# VI. Keine freie LLM-Neugenerierung des Dokuments

## VI.1 Strukturierte Entscheidungen

Das LLM darf nicht die vollständige Markdown-Datei frei neu schreiben.

Es liefert ausschließlich strukturierte, maschinenlesbare Entscheidungen oder Edit-Vorschläge.

## VI.2 Kontrollierte Anwendung

Nur explizit erlaubte Operationen dürfen durch Python ausgeführt werden.

Unbekannte oder ungültige Operationen werden verworfen.

## VI.3 Kein direkter Dateizugriff des LLM

Das LLM erhält keine Schreibverantwortung für Quelle oder Zielartefakte.

---

# VII. Auditierbarkeit

## VII.1 Nachvollziehbare Änderungen

Jede automatisch angewendete strukturelle Änderung muss nachvollziehbar dokumentiert werden.

## VII.2 Review-Artefakt

Der menschlich lesbare Reviewbericht ist ein verbindliches Ausgabe-Artefakt.

Er dokumentiert mindestens:

- angewendete Änderungen;
- strukturelle Änderungen;
- Konfidenz;
- ungeklärte Fälle;
- verworfene Vorschläge;
- Integritätsstatus.

## VII.3 Sauberes Ergebnisdokument

Reviewinformationen und LLM-Metadaten werden standardmäßig nicht in das korrigierte Markdown-Dokument eingebettet.

---

# VIII. Konfidenz ist kein Wahrheitsbeweis

## VIII.1 Modellscore

Ein vom LLM ausgegebener Konfidenz-Score ist eine Modellaussage und keine automatisch kalibrierte Wahrscheinlichkeit.

## VIII.2 Empirische Kalibrierung

Schwellenwerte für automatische Änderungen müssen anhand des projektspezifischen Regressionstest-Korpus bestimmt werden.

## VIII.3 Strukturelle Änderungen

Für strukturelle Änderungen gelten konservativere Schwellen als für einfache Textkorrekturen.

## VIII.4 `unresolved`

Das Modell muss ausdrücklich die Möglichkeit besitzen, sich einer Entscheidung zu enthalten.

---

# IX. Minimaler und modularer Code

## IX.1 Kleine Komponente

Dieses Modul ist Teil eines größeren Projekts.

Die Implementierung soll deshalb so einfach wie möglich und nur so komplex wie nötig sein.

## IX.2 Keine unnötige Infrastruktur

Es werden keine zusätzlichen Frameworks, Abstraktionsschichten oder Dienste eingeführt, wenn sie keinen klaren Nutzen für:

- Testbarkeit,
- Sicherheit,
- Wartbarkeit oder
- Wiederverwendbarkeit

bringen.

## IX.3 Notebook als Steuerung

Das Jupyter-Notebook darf die Pipeline steuern und Ergebnisse sichtbar machen.

Wiederverwendbare Fachlogik gehört jedoch in testbare Python-Module und nicht ausschließlich in Notebook-Zellen.

---

# X. Recherche vor Architekturänderungen

## X.1 Aktueller Stand der Technik

Architekturentscheidungen, neue Bibliotheken, neue Modellstrategien oder grundlegende Änderungen des LLM-Workflows werden vor ihrer Übernahme gegen aktuelle Primärquellen und belastbare Best Practices geprüft.

## X.2 Entwicklererfahrung vor unbelegter Modellannahme

Dokumentierte Praxiserfahrungen, offizielle Dokumentation und reproduzierbare Projektergebnisse haben Vorrang vor unbelegten Annahmen.

## X.3 Projektbezug

Eine allgemein empfohlene Best Practice wird nicht automatisch übernommen, wenn sie für die realen OCR-/Layoutbedingungen dieses Projekts ungeeignet ist.

---

# XI. Reproduzierbarkeit

## XI.1 Laufparameter

Modell, Quantisierung, relevante Inferenzparameter und Policy-/Skill-Version müssen für evaluierte Läufe nachvollziehbar sein.

## XI.2 Modellvergleich

Modelle werden anhand desselben projektspezifischen Testkorpus verglichen.

Allgemeine Benchmarks ersetzen keine projektspezifische Evaluation.

## XI.3 Änderungen am LLM-Stack

Änderungen an:

- Modell,
- Quantisierung,
- Prompt,
- Skill,
- Response-Schema,
- Kontextstrategie oder
- wesentlichen Inferenzparametern

müssen gegen die Regressionstests überprüfbar sein.

---

# XII. Human-in-the-loop als Abschluss-Gate

## XII.1 Verpflichtende reale Prüfung

Nach erfolgreichem automatisiertem Testdurchlauf erfolgt eine Human-in-the-loop-Prüfung an repräsentativen realen OCR-Dokumenten.

## XII.2 Fehlerklassen

Gefundene Fehler sollen mindestens einer der folgenden Kategorien zugeordnet werden:

- fehlende Korrektur;
- falsche Korrektur;
- Halluzination;
- falsche strukturelle Verschiebung;
- falsche Duplikaterkennung;
- falsche Caption-Zuordnung;
- unzureichendes `unresolved`;
- problematische Konfidenzbewertung;
- Integritätsproblem.

## XII.3 Kein stilles Nachpatchen

Ein im Human-in-the-loop entdeckter systematischer Fehler wird nicht durch eine ad-hoc-Sonderregel im Code behoben.

Zuerst wird geprüft, ob:

- die Spezifikation,
- der Implementierungsplan oder
- nur die konkrete Implementierung

geändert werden muss.

---

# XIII. Living-Spec-Prozess

## XIII.1 Auslöser

Ein neuer Living-Spec-Zyklus beginnt insbesondere, wenn Human-in-the-loop oder Regressionstests zeigen, dass:

- eine Anforderung fehlt;
- eine bestehende Anforderung ungeeignet ist;
- eine Annahme über reale Dokumente falsch war;
- neue relevante Fehlerklassen auftreten.

## XIII.2 Änderungsreihenfolge

Wenn die fachliche Anforderung betroffen ist:

```text
constitution.md, falls Grundprinzip betroffen
        ↓
spec.md
        ↓
plan.md
        ↓
tasks.md
        ↓
Tests
        ↓
Implementierung
        ↓
Human-in-the-loop
```

Ist nur die technische Umsetzung betroffen, wird `spec.md` nicht unnötig verändert.

## XIII.3 Constitution-Änderungen

Die Constitution wird nur geändert, wenn sich ein dauerhaftes Projektprinzip ändert.

Sie wird nicht für einzelne Implementierungsdetails angepasst.

---

# XIV. Definition of Compliance

Eine Implementierung gilt nur dann als constitution-konform, wenn:

1. keine geschützten Elemente verletzt werden;
2. relevante Anforderungen testbar umgesetzt sind;
3. der TDD-Prozess eingehalten wird;
4. semantische Entscheidungen nicht heimlich in Python-Heuristiken verlagert werden;
5. das LLM keine freie Gesamtdokument-Neugenerierung übernimmt;
6. ungeklärte Fälle unverändert bleiben können;
7. strukturelle Änderungen auditierbar sind;
8. Regressionstests erfolgreich sind;
9. der Human-in-the-loop-Abschluss durchgeführt wurde;
10. gefundene systematische Abweichungen über den Living-Spec-Prozess behandelt werden.

---

# XV. Rangfolge der Artefakte

Bei Widersprüchen gilt folgende Priorität:

```text
1. constitution.md
2. spec.md
3. plan.md
4. tasks.md
5. Implementierung
```

Ein nachrangiges Artefakt darf ein höherrangiges nicht stillschweigend überschreiben.

---

# XVI. Referenz zum Entwicklungsprozess

Der für dieses Modul bewusst schlank gehaltene SDD-Prozess lautet:

```text
constitution
    ↓
spec
    ↓
plan
    ↓
tasks
    ↓
Test First / Implementierung
    ↓
Human-in-the-loop
    ↓
gegebenenfalls Living-Spec-Zyklus
```

Zusätzliche Prozessartefakte werden nur eingeführt, wenn die tatsächliche Projektkomplexität sie rechtfertigt.
