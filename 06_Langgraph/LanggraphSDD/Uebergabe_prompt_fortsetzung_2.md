# Übergabe-Prompt: SDD-Schema für LangGraph-Agenten (Fortsetzung II)

> **Verwendung:** Diesen Text als erste Nachricht in einen neuen Chat
> einfügen. Zusätzlich die Artefakt-Dateien anhängen (siehe Abschnitt
> "Mitgegebene Dateien") — dieser Prompt beschreibt Stand und
> Entscheidungen, die Dateien enthalten die Substanz.

---

## Projektkontext

Ich bin Dozent und bilde berufstätige Studenten (DQR4/5) darin aus,
LangGraph-Agenten für Kunden selbstständig zu entwickeln. LangGraph
wird als erweiterter Zustandsautomat (FSM-Formalismus) vermittelt.
Strategischer Hintergrund: Wertschöpfung verlagert sich auf
Spezifikation, Planung und Qualitätssicherung. **Wichtige
Umgebungsbedingung (neu als Designconstraint anerkannt):** Die
Werkzeugkette muss auf lokalen Mittelklasse-Modellen laufen (Kimi,
GLM, via LM Studio, ~256k Kontext, Reasoning oft low) — nicht nur
auf Frontier-Modellen.

## Das Modell (Stand: umgesetzt, teilvalidiert)

Sechs Phasen, drei LLM-Rollen (Interviewer / Prüfer / Implementierer),
Student als Regisseur und Kunden-Proxy:

- **Phase 0 · Dekomposition** (eigene Datei): Interview entlang
  Trennkriterien → `prozess.md` mit Teilgraphen, Kontrakten,
  Entwicklungsreihenfolge. Endet mit Selbstprüfung "steht alles drin?
  Der Spec-Interviewer kennt dieses Gespräch nicht."
- **Phase 1 · Spec-Interview** (eigene Datei, frische Sitzung pro
  Teilgraph): Schritt 0 Kontrakt-Aufnahme aus prozess.md, dann
  Beispiele → Knoten → State (Reducer-Pflicht) → Router (Default-
  Pflicht) → Terminierung (Zähler+Maximum+Abbruch) → Skills →
  Mermaid+Gegenprobe. Kontraktänderungsbedarf wird als
  `[OFFEN: Kontrakt X — Rückspiel nach prozess.md]` markiert.
- **Phase 2 · Review, dreistufig:**
  **2a Spec-Lint** (Python, dependency-frei): prüft die spec.md als
  Textdokument — Pflichtabschnitte, leere Zellen, Beispielzahl,
  Nicht-Ziele, recursion_limit, Knoten-Abgleich Mermaid↔Inventar,
  Router-Ziele (best effort), **Zyklensuche per DFS** inkl.
  Widerspruchsprüfung gegen Terminierungstabelle. Druckt bei
  befundfreiem Lauf einen fertigen **Prüfauftrag** (prüfen/entfällt
  je Pass). Ehrlich statt gnädig: Unparsebares = WARN, nie stilles OK.
  **2b spec-review** llm lädt den lint-report und analysiert die spec.md. es wird 
  eine prüf-json-datei erstellt.
  **2c spec-review-interview** die prüf-json-datei wird gelesen und stück für
  stück abgearbeitet.
- **Phase 3 · Plan** / **Phase 4 · Tests zuerst** / **Phase 5 ·
  Implementierung:** unverändert (Standardreihenfolge T1–T9, Topologie-
  Einfrieren nach T4, Tests-vs-Evals-Zweiteilung, Konventions-Skill).

**Drei Prüfebenen (Merksatz):** Lint prüft das Dokument (braucht nur
spec.md) · Strukturtests den Code (brauchen Graph-Gerüst) · Evals die
Qualität (brauchen den fertigen Agenten).

## Getroffene Entscheidungen (nicht neu verhandeln)

Frühere Entscheidungen 1–6 gelten fort (Terminierungspflicht als
Formularzwang; HITL außerhalb; MemorySaver-Standard; Spec by Example
verpflichtend; Pflichtstrukturen im Prompt eingebettet; Einordnung
SDD generisch vs. FSM-Instanziierung als Eigenleistung). Neu:

7. **Phase 0 und 1 getrennt** (je eine Datei, 1:1 Phase↔Datei). Die
   prozess.md ist der Kontrakt zwischen den Sitzungen; fehlt der
   Phase-1-Sitzung Wissen, ist das ein Befund gegen die prozess.md.
   Gesprächsregeln bewusst wortgleich dupliziert (Wartungskommentar).
8. **Regie/Baustein-Trennung (zentrale Architekturregel):** Alles
   Bedingte, Verweisende, Routende steht in Regie-Teilen, die NIE in
   eine LLM-Sitzung wandern. LLM-Bausteine sind flach. Redaktionsregel:
   *Jede Baustein-Zeile muss ohne Blick in eine andere Datei und ohne
   Fallunterscheidung befolgbar sein.* Bedingungen löst der Regisseur
   vorab auf; entfallende ⚙-Punkte werden **physisch gestrichen**,
   nie konditional übersprungen. Hintergrund: Mittelklasse-Modelle
   verlieren sich bei unaufgelösten Querbezügen in ergebnisloser
   Dauersimulation (zweimal real beobachtet).
9. **Triage vor jedem Rückweg:** Befund trifft zu → Baustein K ·
   Fehlalarm des Prüfwerkzeugs → Werkzeug verbessern, Spec unangetastet
   · kein Prüfpunkt zuständig → Checkliste erweitern. Rückweg heißt
   nie Interview-Neudurchlauf.
10. **Betriebsregeln (nach Agent-Havarie):** Interviewer/Prüfer laufen
    als Chat (Text rein/raus), ausführen tut nur der Student.
    Werkzeugdateien liegen in Git und sind für alle LLM-Rollen
    unantastbar (Reward-Hacking-Gefahr: Kimi hat den Lint eigenmächtig
    modifiziert und lief in gegenseitige Abhängigkeiten, 725k Tokens).
    Sitzungsbudget: Kreisläufe abbrechen und frisch starten, nicht
    weiterdiskutieren — der Prozess braucht seine eigene Terminierung,
    der Student ist sein Abbruch-Router.
11. Nach Korrekturen: Lint immer erneut; LLM-Pässe nur soweit
    betroffen, bei Topologie-Änderung alle vier.

## Validierungsstand

Erster Realdurchlauf (Kimi 2.x): Lint lief, meldete B4-Beifang aus
Prosa-Pfeilen (behoben: nur Listen-/Tabellenzeilen, letztes Ziel pro
Zeile, unauflösbar = WARN) und einen D1-Widerspruch (Terminierungs-
tabelle nennt Zyklen, Mermaid-Parse fand keine — **ungeklärt:** echte
fehlende Rückkanten oder Parserlücke; Abschnitt 5 + Mermaid der realen
Spec noch nicht gesichtet). Zweite Havarie: agentischer Lauf ohne
Rollentrennung → Entscheidungen 8/10.

## Mitgegebene Dateien

1. `Phase0_meta_prompt_dekomposition.md`
2. `Phase1_meta_prompt_spec_interview.md`
3. `Phase2_review_checkliste.md` (Teil 1 Regie / Teil 2 Kopf-Baustein /
   Teil 3 Pass-Bausteine A–D)
4. `Phase2a_spec_lint.py` (getestet: 3 Szenarien, Regressionslauf grün)
5. `Phase2b_review_checkliste.md`
6. `Phase2c_review_intervies.md`
7. `Phase3_plan_vorlage.md` (unverändert alt)
8. `Phase4_test_vorlage.py` (unverändert alt)
9. `Phase5_langgraph_konventionen.md` (unverändert alt)
10. `sdd_langgraph_gesamtzyklus.svg` (Übersichtsblatt: Zyklus mit 2a/2b
   und beiden Rückpfeilen, Dateilegende, Befund-Routing, Prüfebenen)

## Stilkonventionen

Deutsch durchgehend. Inkrementelle Verfeinerung statt Neuschreiben,
gezielte Diffs. Didaktisch-konzeptionell vor defensiv-technisch.
Werkzeug-Code ohne Abhängigkeiten, ehrlich statt gnädig. Havarien sind
Lehrmaterial, nicht Peinlichkeiten — der Prozess wird mit denselben
Mitteln repariert, die er lehrt (Dekomposition, Kontrakte,
Terminierung, Formularzwang).

## Offene nächste Schritte (hier weitermachen)

1. **Regie/Baustein-Schnitt nachziehen** in Phase-0-Datei (Kopf
   verweist noch auf den Phase-1-Prompt) und Plan-Vorlage (mild
   betroffen); Phase-4/5-Dateien auf Verstöße gegen die
   Redaktionsregel sichten.
2. **Handout & Spiegel aktualisieren:** Studenten-Handout
   Durchlauf-Schritt 3 (Lint + vier Prüfer-Sitzungen statt einer;
   Betriebsregeln ins Setup). Dozentenspiegel: Sollbruchstelle 2
   (durch Schritt 0/Rückspiel adressiert) und 3 (D1 → Skript)
   markieren; beide Havarien als Debrief-Fallbeispiele ergänzen
   ("Durchgerutscht"-Befunde der Werkzeugkette selbst).
3. **D1-Fall klären:** Abschnitt 5 + Mermaid der realen Spec sichten →
   fehlende Rückkanten (echter Befund) oder Parserlücke
   (Werkzeug-Befund, Lint härten).
4. **Studenten-Validierungsdurchlauf** durchführen, Befundlisten
   auswerten, Diffs in die Artefakte zurückspielen.
5. Optional später: Musterlösung durch Rückwärts-Rekonstruktion des
   Dataviz-Agenten; Ausbaustufe Subgraphen/HITL.
