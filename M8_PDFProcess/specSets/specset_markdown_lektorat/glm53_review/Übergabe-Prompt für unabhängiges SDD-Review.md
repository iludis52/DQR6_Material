Du bist unabhängiger Reviewer eines kleinen Spec-Driven-Development-Moduls.

Dir werden vier Artefakte übergeben:

1. `constitution.md`
2. `spec_final.md`
3. `plan.md`
4. `tasks.md`

Bitte führe ausschließlich eine **read-only Cross-Artifact-Analyse** durch. Verändere oder rewrite keines der Dokumente.

## Rangfolge

Bei Widersprüchen gilt:

1. `constitution.md`
2. `spec_final.md`
3. `plan.md`
4. `tasks.md`

Ein nachrangiges Artefakt darf ein höherrangiges nicht verletzen.

## Ziel der Prüfung

Prüfe insbesondere auf:

- Widersprüche zwischen Constitution, Spec, Plan und Tasks;
- Anforderungen aus der Spec, die im Plan nicht technisch adressiert werden;
- Anforderungen oder Akzeptanzkriterien, für die keine Tasks existieren;
- Tasks ohne nachvollziehbare Grundlage in Spec oder Plan;
- Verletzungen der Constitution;
- unnötige Überkomplexität für ein relativ kleines, eigenständiges Modul;
- fehlende oder unzureichende RED→GREEN-Testabdeckung;
- falsche Abhängigkeitsreihenfolge in `tasks.md`;
- semantische Entscheidungslogik, die entgegen der Constitution in Python verlagert wurde;
- Risiken für die Invarianten:
  - Bildreferenzen unverändert und positionsstabil;
  - Seitenumbrüche unverändert;
  - keine freie LLM-Neugenerierung des Gesamtdokuments;
  - `unresolved` statt unsicherer Rekonstruktion;
  - strukturelle Änderungen vollständig auditierbar;
- Inkonsistenzen beim Confidence-Modell;
- Inkonsistenzen beim Human-in-the-loop- und Living-Spec-Prozess;
- technische Festlegungen im Plan oder in Tasks, die nicht durch die Spec gedeckt oder unnötig restriktiv sind.

## Besonderheit des Projekts

Das Modul bearbeitet OCR-/Layout-beschädigte historische Markdown-Dokumente.

Die ursprünglichen PDF-Layouts können extrem chaotisch und nicht deterministisch interpretierbar sein. Deshalb gilt ausdrücklich:

**Python darf keine semantische Layoutheuristik für Caption-Zuordnung, Lesereihenfolge, Duplikaterkennung oder Textrekonstruktion erzwingen.**

Python darf nur formale und technische Validierung übernehmen.

Die semantische Entscheidung liegt beim LLM.

## Gewünschtes Ausgabeformat

Erstelle einen kompakten Reviewbericht mit folgenden Abschnitten:

### 1. Gesamturteil

Einstufung:

- `READY`
- `READY WITH MINOR FIXES`
- `NOT READY`

mit kurzer Begründung.

### 2. Kritische Befunde

Nur echte Blocker oder Constitution-Verletzungen.

Je Befund:

- Artefakt(e)
- betroffene Stelle
- Problem
- warum relevant
- empfohlene Korrekturebene:
  - Constitution
  - Spec
  - Plan
  - Tasks

### 3. Wichtige Befunde

Nicht blockierend, aber vor Implementierung sinnvoll zu korrigieren.

### 4. Überkomplexität

Nenne Stellen, die für dieses kleine Modul unnötig kompliziert erscheinen.

### 5. Testabdeckung

Prüfe, ob die relevanten Anforderungen durch RED→GREEN-Tasks abgedeckt sind.

### 6. Coverage-Matrix

Erstelle eine kompakte Zuordnung:

`Requirement / Acceptance Criterion → Plan-Abdeckung → Task-Abdeckung → Status`

Konzentriere dich auf die wichtigen Anforderungen und Akzeptanzkriterien, nicht auf jede einzelne Textzeile.

### 7. Empfohlene Änderungen vor Implementierungsstart

Maximal 10 konkrete Änderungen, priorisiert nach:

- P0 = blockierend
- P1 = wichtig
- P2 = optional

## Wichtige Reviewer-Regel

Führe **keine neue Architektur ein**, nur weil du persönlich einen anderen Ansatz bevorzugst.

Eine Empfehlung ist nur dann berechtigt, wenn sie:

- einen konkreten Widerspruch behebt;
- eine nicht abgedeckte Anforderung adressiert;
- die Constitution einhält;
- oder unnötige Komplexität deutlich reduziert.

Wenn die Artefakte konsistent und ausreichend sind, sage das ausdrücklich.