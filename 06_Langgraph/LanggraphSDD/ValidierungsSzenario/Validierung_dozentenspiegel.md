# Dozentenspiegel: Validierungsdurchlauf „Brandt & Söhne"

> **Nicht an Studenten ausgeben.** Das Handout enthält bewusst keine
> Zuordnung Falle → erwarteter Fangmechanismus — die Studenten sollen
> selbst beurteilen, welcher Teil der Werkzeugkette gegriffen hat.
> Dieses Blatt ist die Auswertungsgrundlage.

## 1. Fallen-Inventar

Jede Falle ist so platziert, dass genau **ein** Mechanismus der
Werkzeugkette sie fangen *sollte*. Der Durchlauf misst, ob er es tut.

| # | Falle (im Szenario) | Soll-Fang | Typischer Fehlgriff |
|---|---|---|---|
| 1 | Nächtliche Aktualisierung vs. Frage-Antwort pro Anfrage | Modus A, Trennkriterien Trigger/Lebenszyklen + Batch/interaktiv → **zwei Teilgraphen** | Ein einziger Graph „mit Indexierungs-Knoten vorne" |
| 2 | Der Index als persistentes Artefakt | Modus A: **Kontrakt** in prozess.md (Format, Speicherort, Metadaten, Invarianten) | Index wird erwähnt, aber nie als Schnittstelle spezifiziert |
| 3 | Quellenangabe-Pflicht (Handbuch + Seite; Serviceberichte: Datum + Auftragsnr.) | Kontrakt-Invariante: Pflicht-Metadaten pro Chunk folgen aus der Zitierpflicht — **phasenübergreifender Schluss** von Phase-1-Anforderung auf Phase-0-Kontrakt; B7 prüft die Übernahme | Zitierpflicht landet nur in der Retrieval-Spec, Index-Kontrakt kennt keine Seitenzahl/Auftragsnr. → fällt frühestens bei der Integration auf |
| 4 | „Kontrolle, dass die Antwort stimmt" | Modus B Schritt 5: Reflection-Loop → **Zyklus 1** in Terminierungstabelle (Zähler + Maximum + Abbruch-Router); Ausweg „Bitte im Büro anrufen" als Abbruch-Kante | Loop ohne Zähler; oder Prüf-Knoten ohne Rückkante (dann ist die „Kontrolle" nur behauptet — C3) |
| 5 | „Mit anderen Worten nochmal probieren" (steckt nur im Kundengedächtnis) | Kommt nur ans Licht, wenn der Nichts-gefunden-Fall aktiv ausgefragt wird → **Zyklus 2** (Retry-Umformulierung). Übersieht das Interview ihn, muss D1 (selbstständige Zyklensuche des Prüfers) ihn finden | Zweiter Zyklus fehlt in Abschnitt 6; oder er existiert im Mermaid, D1 wird aber vom Prüfer nicht ernsthaft ausgeführt |
| 6 | „Wie oft probieren?" — „Ihr seid die Experten" | Terminierungspflicht verlangt eine **Zahl**: Der Interviewer muss einen Wert vorschlagen und bestätigen lassen (nicht `[OFFEN]` — Terminierung ist nicht offenlassbar) | Interviewer akzeptiert „weiß nicht" und lässt das Maximum offen; oder erfindet still eine Zahl ohne Rückbestätigung |
| 7 | Widerspruch Nachfragen vs. Handschuhe | Gesprächsregel 3 (nichts erfinden) + Spiegeln: Widerspruch **benennen** → Kunde entscheidet (siehe Kundengedächtnis). Zusatzpointe: HITL ist bewusst außerhalb des Modells — „ohne Rückfragen" ist auch die prozesskonforme Lösung | Interviewer wählt still eine der beiden Aussagen; oder baut einen Rückfrage-Knoten, den das Vorgehensmodell gar nicht trägt |
| 8 | Techniker- vs. Vertriebs-Ton | Modus B Schritt 6: **Skill** (z.B. `skills/tonalitaet_<zielgruppe>.md`), Trigger konfigurationsabhängig, Platzhalter-Inventar | Tonalität wird in den Knoten-Prompt „reingeschrieben" → Volatilität im stabilen Teil; oder Skill ohne Trigger-Bedingung (B5-Befund) |
| 9 | Gescannter Altbestand | Teil C → muss als `[OFFEN: OCR-Fähigkeit Altbestand]` in prozess.md/spec.md stehen | Stille Annahme („wir OCRen einfach") — wenn sie die Freigabe übersteht: schwerster Befund-Typ „Durchgerutscht"; Regel 2 der Checkliste schützt umgekehrt legitime `[OFFEN]`-Marker |
| 10 | Englisch „mal sehen" | `[OFFEN]` oder Nicht-Ziel mit Datum — beides vertretbar, Hauptsache explizit | Taucht nirgends auf |
| 11 | ERP-Ersatzteile „irgendwann" | **Nicht-Ziele** (A6 erzwingt, dass der Abschnitt nicht leer ist) | Wandert als Knoten oder `[OFFEN]` in die Spec statt in Nicht-Ziele |
| 12 | „Ehrlich sagen, wenn nichts gefunden" | Pflicht-Sonderfall bei Spec by Example (Schritt 1) + Router-Default (A4) + C3 (Fehlerpfad ≠ Normalpfad) | Beide Beispiel-Durchläufe sind Normalfälle (A5-Verstoß); oder Fehlerfall nimmt im Diagramm denselben Pfad wie der Normalfall |
| 13 | Zwei-LLM-Konstellation Antworter + Prüfer | D4: wechselseitiger Endlos-Aufruf ausgeschlossen? (Zähler von Zyklus 1 deckt das ab) | D4 wird abgenickt, ohne den konkreten Zähler zu benennen |
| 14 | „Keine Cloud, Server im Keller" | Randbedingung in prozess.md; Hardware-Details → `[OFFEN]` (Teil C) | Wird als irrelevant verworfen — bei lokalem LLM-Betrieb ist es aber abnahmerelevant |

## 2. Soll-Skizze (Erwartungskorridor, keine Musterlösung)

**prozess.md:** Zwei Teilgraphen — *Indexierung* (Trigger: nächtlich,
Batch) und *Auskunft* (Trigger: pro Anfrage, interaktiv). Kontrakt
„Doku-Index": pro Chunk mindestens Quelldatei, Dokumenttyp
(Handbuch/Servicebericht), Seitenzahl **oder** Datum+Auftragsnummer,
Embedding. Entwicklungsreihenfolge: Indexierung zuerst. Offene Punkte:
mindestens OCR-Altbestand, Englisch, Server-Hardware.

**spec.md (Auskunft-Teilgraph), Kernpunkte:**

- Beispiel-Durchläufe: 1 Normalfall (Frage → Fundstellen → Antwort mit
  Quelle), mindestens 1 Sonderfall (nichts gefunden → Umformulieren →
  wieder nichts → ehrliche Absage) und idealerweise der
  Qualitäts-Fehlfall (Prüfer lehnt zweimal ab → „Bitte im Büro anrufen").
- Zwei Zyklen in der Terminierungstabelle: Qualitäts-Loop
  (z.B. `MAX_VERBESSERUNGEN = 2`) und Retry-Loop
  (z.B. `MAX_SUCHVERSUCHE = 2`), je eigenes Zähler-Feld, Abbruch als
  erste Prüfung im jeweiligen Router, `recursion_limit` beziffert.
- Skills: mindestens Tonalität (Trigger: Konfiguration/Nutzergruppe,
  Platzhalter z.B. `{frage}`, `{fundstellen}`), ggf. Zitierformat je
  Dokumenttyp als zweiter Skill.
- Nicht-Ziele: ERP-Anbindung, Rückfragen an den Nutzer (HITL),
  ggf. Englisch.

Abweichungen vom Korridor sind kein Fehler per se — entscheidend ist,
ob sie **explizit** entschieden wurden (Spec/`[OFFEN]`/Nicht-Ziel) oder
still passiert sind.

## 3. Bekannte Sollbruchstellen der Werkzeugkette

Stellen, an denen der Durchlauf voraussichtlich *echte* Prozess-Befunde
produziert — das ist erwünscht, nicht peinlich; es ist der Lerninhalt:

1. **Vorschlagsrecht des Interviewers:** Regel 3 („keine Annahmen
   erfinden") kollidiert mit Falle 6 („ihr seid die Experten"). Der
   Meta-Prompt sagt nicht explizit, dass der Interviewer Werte
   *vorschlagen und bestätigen lassen* darf. Erwartbarer
   Studentenbefund: Zusatz in den Gesprächsregeln.
2. **Phasenübergreifende Rückkopplung:** Falle 3 erzeugt Wissen in
   Phase 1, das den Kontrakt aus Phase 0 ändern müsste. Der Meta-Prompt
   beschreibt den Rückweg spec.md → prozess.md nicht ausdrücklich
   (B7 prüft nur die Leserichtung). Guter Befund: Update-Regel für
   Kontrakte definieren.
3. **D1 in der Praxis:** Ob ein Prüfer-LLM Zyklen wirklich selbstständig
   im Mermaid findet, ist modellabhängig — hier zeigt sich der
   Unterschied zwischen „steht in der Checkliste" und „wird verlässlich
   ausgeführt". Diskussionsanschluss: Was davon gehört eher in einen
   deterministischen Test (Graph-Introspektion, Phase 4) statt in ein
   LLM-Review?

## 4. Auswertungsraster für die Befundlisten

Ein Prozess-Befund zählt als vollwertig, wenn er vier Dinge nennt:
**Beleg** (Phase/Turn, Zitat), **Typ** (aus dem Protokoll-Schema),
**Artefakt** (welche der fünf Dateien) und **Diff** (konkrete
Textänderung). Faustregel für die Bewertung: 3–4 vollwertige Befunde
pro Gruppe sind ein sehr guter Durchlauf; zehn vage Beobachtungen ohne
Diff sind keiner.

## 5. Debrief-Bogen (Meta-Lernziel)

1. Sammelrunde: Welche Fallen wurden von welchem Mechanismus gefangen —
   Formularzwang, Prüfer, oder gar nicht? (Tafelbild: Fallen-Nr. ×
   Fangebene; Inventar aus Abschnitt 1 auflösen.)
2. Warum ist „Durchgerutscht" teurer als „Prüfer fand's", und
   „Prüfer fand's" teurer als „Formularzwang griff"? (Kostenkurve von
   Fehlern über Phasen — dasselbe Argument wie beim Agenten selbst.)
3. Übertragung: Die Werkzeugkette hat Spec (Pflichtstrukturen), Tests
   (Checkliste), Durchlauf (heute) und Befund-Routing (Protokoll-Typen).
   Was fehlt ihr noch zum vollständigen SDD-Zyklus über sich selbst —
   und wer spielt bei einem Prozess den „Kunden"?
4. Abschluss an Sollbruchstelle 3: Wo ist die Grenze dessen, was man
   einem LLM-Prüfer überlassen sollte, und was man deterministisch
   testen muss? (Brücke zur Tests-vs.-Evals-Zweiteilung aus Phase 4.)
