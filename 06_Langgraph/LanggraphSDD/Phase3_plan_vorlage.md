# Plan-Vorlage: Standardreihenfolge für LangGraph-Agenten (Phase 3)

> **Verwendung:** Pro Teilgraph einmal ausfüllen. Die Reihenfolge der
> Blöcke ist fix und wird nicht umgestellt — sie ist die LangGraph-
> Übersetzung von "Stabiles früh, Volatiles spät". Jeder Task nennt
> seinen Spec-Abschnitt als Quelle und sein Fertig-Kriterium.
> Ein Task gilt erst als erledigt, wenn sein Kriterium maschinell
> oder per Sichtprüfung bestätigt ist.

## Teilgraph: <Name>    Spec: <spec.md-Pfad>    Datum: <...>

---

### Block A — Fundament (stabil, deterministisch)

- [ ] **T1 · State-Schema** — Quelle: Spec Abschnitt 3
      `agent/state.py`: TypedDict, alle Felder mit Reducer-Annotation
      laut Spec, Zähler-Felder, Konstanten (MAX_*).
      *Fertig, wenn:* Import läuft; jedes akkumulierende Feld trägt
      `Annotated`.

- [ ] **T2 · Router** — Quelle: Spec Abschnitt 5 + 6
      `agent/router.py`: alle Router als pure functions, Rückgabetyp
      `Literal`, Abbruchbedingung als erste Prüfung, expliziter Default.
      *Fertig, wenn:* Router-Unit-Tests aus der Test-Vorlage grün
      (Tests dürfen für diesen Block schon vorgezogen werden).

- [ ] **T3 · Graph-Gerüst mit Dummy-Knoten** — Quelle: Spec Abschnitt 4, 8
      `agent/graph.py`: alle Knoten als Dummies registriert (schreiben
      plausible Platzhalter-Werte in ihre Spec-Felder, kein LLM),
      alle Kanten, `compile(checkpointer=MemorySaver())`.
      *Fertig, wenn:* Der Graph mit einer Minimal-Eingabe von START bis
      END durchläuft — der Automat lebt, bevor ein LLM existiert.

### Block B — Sicherheitsnetz

- [ ] **T4 · Strukturtests grün** — Quelle: Test-Vorlage Teil 1–3
      Test-Vorlage kopieren, Platzhalter aus der Spec füllen
      (ERWARTETE_KNOTEN, ERWARTETE_KANTEN, Router-Fälle, Terminierung).
      *Fertig, wenn:* Struktur-, Router- und Terminierungstests grün
      gegen das Dummy-Gerüst. **Meilenstein: Ab hier ist die Topologie
      eingefroren.** Jede spätere Topologie-Änderung beginnt bei der
      Spec, nicht im Code.

### Block C — Innenleben (volatiler)

- [ ] **T5 · Daten-Knoten** — Quelle: Spec Abschnitt 4 (Art: Daten)
      Dummies der reinen Datenverarbeitungs-Knoten durch echte Logik
      ersetzen (Profil-Erstellung, Parsing, Dateizugriffe).
      *Fertig, wenn:* Strukturtests weiterhin grün; Knoten-Outputs
      stichprobenhaft geprüft.

- [ ] **T6 · LLM-Knoten** — Quelle: Spec Abschnitt 4 (Art: LLM/Tool)
      Echte LLM-/Tool-Aufrufe, try/except, defensives JSON-Parsing,
      Fehler-Felder laut Konventions-Skill.
      *Fertig, wenn:* Alle Tests grün; ein manueller Komplett-Durchlauf
      mit echter Eingabe erreicht END.

### Block D — Volatile Schicht

- [ ] **T7 · Skills** — Quelle: Spec Abschnitt 7
      `skills/*.md` anlegen, `lade_skill()` inkl. KeyError-Verhalten,
      Trigger-Logik im zuständigen Daten-Knoten.
      *Fertig, wenn:* Skill-Tests (Test-Vorlage Teil 4) grün.

### Block E — Qualität & Abnahme

- [ ] **T8 · Evals** — Quelle: Spec Abschnitt 2 + Eval-Rubrik
      Golden-Eingaben festlegen (mind. die Beispiel-Durchläufe der
      Spec), LLM-as-Judge-Rubrik instanziieren, Schwellen beziffern,
      mehrfach laufen lassen (n ≥ 5), statistisch auswerten.
      *Fertig, wenn:* Schwellen erreicht ODER Befund dokumentiert und
      korrekt geroutet (siehe Kasten unten).

- [ ] **T9 · Abnahme** — Quelle: Spec Abschnitt 2
      Alle Beispiel-Durchläufe gegen den realen Agenten fahren;
      bei Teilgraph-Ketten zusätzlich: Kontrakt-Invarianten aus der
      prozess.md gegen das reale Artefakt prüfen.
      *Fertig, wenn:* Kunde/Dozent hat die Durchläufe gesehen und
      bestätigt.

---

## Befund-Routing (bei jedem roten Ergebnis zuerst fragen: welche Ebene?)

| Befund | Ebene | Rückweg |
|---|---|---|
| Strukturtest rot | Implementierung | Block A/C reparieren |
| Router-Test rot | Implementierung oder Spec-Fall vergessen | Router fixen; fehlt ein Fall → Spec (Phase 1) |
| Eval unter Schwelle | Skill zu schwach | Skill iterieren (T7) — kein Codeeingriff |
| Abnahme scheitert inhaltlich | Spec falsch | zurück zu Phase 1, neues Beispiel, Kette neu durchlaufen |

## Verbote

- Kein Task aus Block C/D beginnen, bevor T4 grün ist.
- Keine Topologie-Änderung "mal eben im Code" — Topologie-Änderungen
  laufen immer über Spec → Review → Strukturtests anpassen.
- Kein Eval-Befund durch Aufweichen der Schwelle "lösen".
