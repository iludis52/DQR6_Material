# Übergabe-Prompt: SDD-Schema für LangGraph-Agenten (Fortsetzung)

> **Verwendung:** Diesen Text als erste Nachricht in einen neuen Chat
> einfügen. Zusätzlich die fünf Artefakt-Dateien anhängen (siehe
> Abschnitt "Mitgegebene Dateien") — dieser Prompt beschreibt den Stand
> und die Entscheidungen, die Dateien enthalten die Substanz.

---

## Projektkontext

Ich bin Dozent und bilde berufstätige Studenten (DQR4/5-Niveau) darin
aus, LangGraph-Agenten für Kunden selbstständig zu entwickeln. Es
existiert bereits ein Lehrskript, das LangGraph als **erweiterten
Zustandsautomaten** (FSM-Formalismus) vermittelt, sowie ein separater
SDD-Kurs (Meta-Prompt-Interview → spec.md → Review durch zweites LLM →
plan.md → tasks.md → Tests → Implementierung gegen Tests). Als
Referenzbeispiel dient ein real laufender Dataviz-Agent (zwei LLMs:
Analyst + Qualitätsprüfer, datengetrieben geladene Analyse-Skills als
Markdown mit {platzhaltern}, Reflection-Loop mit JSON-Bewertung).

**Ziel:** Ein generisches, wiederverwendbares SDD-Vorgehensmodell
speziell für die Entwicklung von LangGraph-Agenten — der Student soll
den Zyklus von rohen Kundennotizen bis zum abgenommenen Agenten
selbstständig durchlaufen können. Strategischer Hintergrund: Junioren
werden kaum noch eingestellt; die Ausbildung verlagert ihre Wertschöpfung
auf Spezifikation, Planung und Qualitätssicherung.

## Das entwickelte Modell (Stand: abgeschlossen konzipiert)

Sechs Phasen, drei getrennte LLM-Rollen (Interviewer / Prüfer /
Implementierer), Student als Regisseur und Kunden-Proxy:

- **Phase 0 · Dekomposition:** Meta-Prompt Modus A interviewt entlang
  Trennkriterien (Trigger/Lebenszyklen, geteilter State, Batch vs.
  interaktiv, persistente Artefakte) → `prozess.md` mit Teilgraphen,
  Kontrakten (Artefakt-Schnittstellen, z.B. RAG-Index) und
  Entwicklungsreihenfolge. Wird nie übersprungen.
- **Phase 1 · Spec-Interview (pro Teilgraph):** Modus B, Reihenfolge:
  Beispiel-Durchläufe zuerst (Spec by Example, mind. 1 Fehlerfall) →
  Knoten → State (Pflicht-Reducer-Spalte) → Router (Pflicht-Default) →
  Terminierung (Pflichttabelle: Zähler-Feld + Maximum + Abbruch-Router)
  → Skill-Kontrakte (Trigger + Platzhalter-Inventar) → Mermaid +
  Gegenprobe (Beispiele am Diagramm entlanglaufen). Lücken als
  `[OFFEN: ...]`, nie stille Annahmen.
- **Phase 2 · Review:** Frische LLM-Instanz, Checkliste mit 4 Kategorien
  (Vollständigkeit / bidirektionale Konsistenz-Querverweise /
  Ablauf-Simulation / Terminierung inkl. selbstständiger Zyklen-Suche).
  Befunde gehen als Rückfragen ins Interview zurück, der Prüfer
  korrigiert nie selbst. JSON-Antwortformat mit Freigabe-Flag.
- **Phase 3 · Plan:** Fixe Standardreihenfolge: State → Router →
  Graph-Gerüst mit Dummy-Knoten → Strukturtests grün (**Meilenstein:
  Topologie eingefroren**) → Daten-Knoten → LLM-Knoten → Skills → Evals
  → Abnahme. Der Automat läuft vollständig, bevor ein LLM-Call existiert.
- **Phase 4 · Tests zuerst:** Zweiteilung Tests vs. Evals ist tragend:
  Deterministisch (pytest): Graph-Introspektion, Router-Units,
  Terminierungstest (Fake-LLM will Loop nie verlassen → Zähler greift),
  recursion_limit-Test, Skill-Platzhalter. Statistisch (Evals):
  LLM-as-Judge + Rubrik, n≥5, nie einzelne asserts auf LLM-Output.
- **Phase 5 · Implementierung:** Gegen grüne Strukturtests, mit
  Konventions-Skill im Kontext. Abnahme = Beispiel-Durchläufe der Spec
  gegen den realen Agenten + Kontrakt-Invarianten.

**Befund-Routing (Kernkompetenz):** Strukturtest rot → Implementierung;
Eval unter Schwelle → Skill iterieren (kein Code); Abnahme scheitert
inhaltlich → zurück zu Phase 1. Architekturprinzip: "Stabiles früh,
Volatiles spät" — Graph-Topologie stabil/getestet, Kundeniteration
läuft über Skills (Markdown-Austausch ohne Codeänderung).

## Getroffene Entscheidungen (nicht neu verhandeln)

1. Terminierungspflicht ist Formularzwang (Zähler + Maximum + Abbruch),
   Motivation: reale Fälle von "zwei LLMs kämpfen die ganze Nacht".
2. Human-in-the-Loop: bewusst außerhalb des Modells.
3. MemorySaver-Checkpointer: Standard in den Konventionen (Debugging
   via get_state_history), Interrupts aber nicht.
4. Spec by Example verpflichtend, Beispiele = Kundenabnahme-Grundlage.
5. Pflichtstrukturen von prozess.md/spec.md sind IM Meta-Prompt
   eingebettet (ein Dokument, keine Datei-Jonglage); die Review-
   Checkliste hält sie als Prüfliste gegen.
6. Einordnung: SDD generisch ist etablierte Industriepraxis (Spec Kit,
   Kiro, BMAD, spec-first/anchored/as-source); die FSM-spezifische
   Instanziierung für LangGraph ist Eigenleistung ohne direktes Vorbild.

## Mitgegebene Dateien (die Substanz — bitte anhängen)

1. `meta_prompt_langgraph.md` — Phase 0+1 (Modus A Dekomposition,
   Modus B Spec-Interview, eingebettete Vorlagen, Abschlussprüfung)
2. `review_checkliste.md` — Phase 2 (Prüfer-Prompt, Kategorien A–D,
   JSON-Format, Freigaberegel)
3. `plan_vorlage.md` — Phase 3 (Tasks T1–T9, Befund-Routing, Verbote)
4. `test_vorlage.py` — Phase 4 (pytest-Gerüst mit <PLATZHALTERN>:
   Struktur, Router, Terminierung, Skills, Eval-Rubrik als Kommentar)
5. `langgraph_konventionen.md` — Phase 5 (projektunabhängiger Skill:
   State/Knoten/Router/Graph/Skills-Konventionen, jede mit
   Test-Gegenstück)

## Stilkonventionen dieses Projekts

Deutsch durchgehend (Dokumente, Code-Kommentare, UI). Inkrementelle
Verfeinerung statt Neuschreiben; gezielte Diffs für Zwischenschritte.
Didaktisch-konzeptionell vor defensiv-technisch. Zielgruppe:
berufstätige Studenten, die schnell selbstständig produktiv werden müssen.

## Offene nächste Schritte (hier weitermachen)

1. **Validierungsdurchlauf:** Meta-Prompt mit fiktiven Kundennotizen
   füttern (RAG-Szenario empfohlen — erzwingt die Dekomposition:
   Indexierung vs. Retrieval) und prüfen, wo das Interview ab Turn 3–4
   hakt. Befunde in den Meta-Prompt zurückspielen.
2. **Prozess-Übersichtsblatt** (eine Seite): Zyklus-Diagramm
   (Kundennotizen → Phase 0 → [pro Teilgraph: 1→2→3→4→5] → Abnahme,
   Rückpfeil Review→Interview, Schleife "nächster Teilgraph") plus
   Kurzlegende und Befund-Routing-Tabelle.
3. Optional später: Musterlösung durch Rückwärts-Rekonstruktion des
   Dataviz-Agenten; Ausbaustufe Subgraphen/HITL.
