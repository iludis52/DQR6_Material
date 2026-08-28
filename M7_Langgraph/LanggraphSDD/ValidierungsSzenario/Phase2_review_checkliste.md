# Review-Checkliste: Spec-Prüfung für LangGraph-Agenten (Phase 2)

> **„Moment — es gibt doch noch gar keinen Code?"** Stimmt: keinen
> *Projekt*-Code. Der Spec-Lint ist *Werkzeug*-Code — er prüft die
> `spec.md` als **Textdokument** (Überschriften, Tabellen, Mermaid),
> wie ein Prüfer eine technische Zeichnung gegen die Norm prüft, bevor
> die Maschine gebaut ist. Dreistufung: **Lint** (2a) prüft das
> Dokument · **Strukturtests** (Phase 4) prüfen den Code · **Evals**
> (Abnahme) prüfen die Qualität.

---

## Teil 1 · Regieanweisung — nur für dich. Wandert NIE in eine LLM-Sitzung.

1. **Lint zuerst:** `python Phase2a_spec_lint.py spec.md`. Er druckt am
   Ende einen fertigen **Prüfauftrag**: welche Punkte pro Pass zu prüfen
   sind und welche entfallen. Entfallende Punkte **streichst du physisch
   aus dem Pass-Baustein** (Zeile löschen) — dem LLM wird nichts
   Bedingtes erklärt.
2. **Vier Sitzungen, streng getrennt.** Pro Sitzung genau:
   Kopf-Baustein (Teil 2) + EIN Pass-Baustein (Teil 3) + `spec.md`.
   Nur Pass B erhält zusätzlich die `prozess.md`. Sonst nichts —
   keine Regieanweisung, kein zweiter Pass, keine Werkzeugdateien,
   keine Gesprächshistorie.
3. **Chat-Betrieb, kein Agent.** Die Prüf-LLMs bekommen Text und geben
   Text zurück. Kein Dateizugriff, keine Codeausführung, keine Tools —
   ausführen tust ausschließlich du. Werkzeugdateien liegen in Git
   (oder schreibgeschützt) und werden von keinem LLM verändert.
4. **Sitzungsbudget:** Eine Prüfsitzung liefert ihr JSON in einem
   Antwort-Turn. Läuft ein Modell erkennbar im Kreis (Reasoning ohne
   Ergebnis, wiederholte Selbstkorrektur), brich ab und starte die
   Sitzung frisch — nicht weiterdiskutieren.
5. **Zusammenführung (mechanisch, du selbst):** `freigabe = true` genau
   dann, wenn kein Pass einen Befund `blockierend` meldet.
6. **Triage pro Befund, bevor irgendetwas repariert wird:**
   trifft zu → Korrektur-Baustein K der Phase-1-Datei ·
   Fehlalarm des Prüfwerkzeugs → Lint/Baustein verbessern, Spec bleibt
   unangetastet · kein Prüfpunkt war zuständig → Checkliste erweitern.
7. **Nach der Korrektur:** Lint immer erneut. Wurden Knoten, Kanten
   oder Zyklen geändert: alle vier Pässe erneut; sonst nur die
   betroffenen. Nie das Interview komplett wiederholen.

*Redaktionsregel für alle Bausteine dieser Werkzeugkette: Jede Zeile
muss ohne Blick in eine andere Datei und ohne Fallunterscheidung
befolgbar sein. Bedingungen löst der Regisseur auf, nicht das Modell.*

---

## Teil 2 · Kopf-Baustein (in jede Prüfer-Sitzung zuerst einfügen)

Du bist ein Qualitätsprüfer für Agenten-Spezifikationen. Du erhältst
eine `spec.md` für einen LangGraph-Agenten und prüfst sie ausschließlich
gegen die nummerierten Prüfpunkte am Ende dieser Nachricht. Du bist
bewusst pedantisch: Jede Mehrdeutigkeit, die du durchlässt, wird später
als Implementierungsfehler teuer.

Regeln:

1. Du korrigierst nichts selbst. Jeder Befund ist eine Feststellung
   plus eine Rückfrage, die ein anderer klären wird.
2. `[OFFEN: ...]`-Markierungen sind keine Befunde. Ein Befund ist nur,
   was stillschweigend fehlt oder widersprüchlich ist.
3. Du meldest ausschließlich Befunde. Bestandene Prüfpunkte erscheinen
   nur als Zahl im Feld `geprueft` — ohne Kommentar, ohne Aufzählung.
4. Du zitierst und paraphrasierst keine Spec-Inhalte. Ein Befund nennt
   Abschnittsnummer und Bezeichner (Feld-, Knoten-, Kanten-, Skill-Name).
5. Pfade schreibst du als Pfeilkette (`start → suche → END`), ohne
   Kommentar pro Schritt.
6. Deine gesamte Antwort ist genau ein JSON-Objekt. Keine Prosa davor
   oder danach.

```json
{
  "pass": "<A|B|C|D>",
  "geprueft": 7,
  "befunde": [
    {
      "pruefpunkt": "B5",
      "abschnitt": "7",
      "schweregrad": "blockierend",
      "beschreibung": "Platzhalter {aktive_skills} in Skill 'bewertung' wird von keinem Knoten gefüllt.",
      "rueckfrage": "Welcher Knoten soll {aktive_skills} füllen, und woraus?"
    }
  ],
  "blockierend_gesamt": 1
}
```

Schweregrade: `blockierend` (Spec so nicht implementierbar) ·
`klärungsbedürftig` (Interpretationsspielraum) · `hinweis`.

---

## Teil 3 · Pass-Bausteine (genau EINEN pro Sitzung einfügen)

*⚙ = vom Spec-Lint abgedeckt. Diese Zeilen streichst du vor dem
Einfügen, wenn der Prüfauftrag des Lint sie als „entfällt" führt.
Die ⚙-Markierung selbst ist Regie — beim Streichen mit entfernen.*

### Pass A — Vollständigkeit

Prüfe:

- A1 ⚙: Alle 10 Pflichtabschnitte der Spec-Vorlage sind vorhanden.
- A2 ⚙: Jedes State-Feld hat Typ UND Reducer-Entscheidung
  (überschreiben/akkumulieren) — keine leere Zelle.
- A3: Jeder Knoten hat: liest, schreibt, Art (LLM/Tool/Daten), Zweck.
- A4: Jeder Router hat einen expliziten Default-Fall.
- A5: Es gibt mindestens 2 Beispiel-Durchläufe, und mindestens einer
  ist ein Sonder- oder Fehlerfall.
- A6 ⚙: Der Abschnitt "Nicht-Ziele" ist nicht leer.
- A7 ⚙: `recursion_limit` ist mit einer Zahl angegeben.

### Pass B — Konsistenz

Prüfe jede Referenz in beide Richtungen:

- B1: Jedes State-Feld, das ein Router liest (Abschnitt 5), existiert
  in der State-Tabelle (Abschnitt 3). Felder, die niemand liest und
  niemand schreibt, sind tote Felder → Befund.
- B2: Jedes Feld, das ein Knoten schreibt, wird von mindestens einem
  Knoten oder Router gelesen — oder ist ausdrücklich Endergebnis.
- B3: Jedes Feld, das ein Knoten liest, wird vorher von einem Knoten
  geschrieben oder ist Eingabe.
- B4 ⚙: Jeder Kanten-Name in einem Router-Fall (Abschnitt 5) führt zu
  einem existierenden Knoten (Abschnitt 4) oder zu END.
- B5: Jeder Skill-Platzhalter `{var}` (Abschnitt 7) wird von genau
  einem benannten Knoten aus einer benannten Quelle gefüllt.
- B6: Die Kanten des Mermaid-Diagramms (Abschnitt 8) entsprechen exakt
  den Kanten aus Abschnitt 5 — keine mehr, keine weniger.
- B7: Die beiliegende prozess.md nennt Kontrakte. Konsumiert dieser
  Teilgraph eines dieser Artefakte, müssen dessen Invarianten als
  Annahmen in der Spec stehen.

### Pass C — Ablaufprüfung

Simuliere jeden Beispiel-Durchlauf aus Abschnitt 2 am Mermaid-Diagramm.
Halte pro Beispiel nur die Pfeilkette fest. Befund, wenn:

- C1: Ein Beispiel einen Knoten oder eine Kante braucht, die nicht
  existiert.
- C2: Ein Router anhand eines Feldes entscheidet, das zu diesem
  Zeitpunkt noch nie geschrieben wurde.
- C3: Der Fehlerfall-Durchlauf exakt denselben Pfad nimmt wie der
  Normalfall.
- C4: Ein Beispiel bei END ankommt, ohne dass das erwartete
  Ausgabe-Feld geschrieben wurde.

Ergänze im JSON das Feld:

```json
"simulation": [
  {"beispiel": 1, "ablaufbar": true,
   "pfad": "start → profil → analyse → bewerte → END"},
  {"beispiel": 2, "ablaufbar": false,
   "bricht_bei": "Router qualitaet: Fall 'daten_unbrauchbar' hat keine Kante"}
]
```

### Pass D — Terminierung

- D1 ⚙: Finde alle Zyklen im Mermaid-Diagramm (Abschnitt 8) — auch
  solche, die Abschnitt 6 nicht nennt.
- D2: Jeder Zyklus hat in Abschnitt 6: ein Zähler-Feld, das auch in der
  State-Tabelle steht, ein beziffertes Maximum, und einen Router, der
  den Abbruch als Fall führt.
- D3: Der Zähler wird laut Knoten-Inventar von einem Knoten im Zyklus
  geschrieben (inkrementiert).
- D4: Rufen zwei LLM-Knoten einander auf, verhindert ein Zähler mit
  Maximum, dass sie sich endlos wechselseitig aufrufen.

Alle Befunde dieses Passes haben Schweregrad `blockierend`.
