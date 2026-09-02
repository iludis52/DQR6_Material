# Tutorial: Progressive Disclosure – Prinzipien & Best Practices 2026

## 1. Was ist Progressive Disclosure?
**Progressive Disclosure** ist ein Designprinzip, bei dem Informationen, Funktionen oder Kontext erst dann offengelegt werden, wenn der Nutzer (oder ein KI-System) sie in der jeweiligen Situation auch wirklich benötigt. 

Das Hauptziel dieses Ansatzes ist die **Reduzierung der kognitiven Belastung (Cognitive Load)**. Anstatt ein System von Anfang an mit allen verfügbaren Optionen oder Daten zu überladen, wird eine Hierarchie geschaffen: Das Wesentliche ist sofort sichtbar, das Komplexe bleibt im Hintergrund verborgen und wird auf Abruf (*On-Demand*) bereitgestellt.

---

## 2. Progressive Disclosure im UX/UI-Design (Die Ursprünge)
Ursprünglich 1995 von Jakob Nielsen für Software-Interfaces definiert, ist dieses Prinzip heute ein Eckpfeiler guten Designs.

### Die drei Hauptkategorien
1. **Sequentiell (Schritt-für-Schritt):** Komplexe Aufgaben werden in überschaubare Phasen unterteilt. (Beispiel: Ein mehrstufiger Checkout-Prozess im E-Commerce).
2. **Konditional (Bedingt):** Elemente bleiben verborgen, bis der Nutzer sie explizit anfordert. (Beispiel: "Erweiterte Einstellungen"-Akkordeons oder Dropdown-Menüs).
3. **Kontextuell:** Zusätzliche Informationen erscheinen nur basierend auf vorherigen Eingaben. (Beispiel: Versandoptionen werden erst angezeigt, nachdem das Lieferland ausgewählt wurde).

### UX Best Practices
* **Informationshierarchien bilden:** Priorisieren Sie gnadenlos. Was muss *sofort* sichtbar sein? Was kann auf den zweiten Klick verschoben werden?
* **Sichtbare Trigger setzen:** Nutzer müssen intuitiv erkennen, dass mehr Informationen verfügbar sind (z. B. durch "Mehr anzeigen"-Buttons oder klare Icons).
* **Vertrauen durch Einfachheit:** Eine aufgeräumte, initial minimalistische Oberfläche wirkt einladend und reduziert Fehlerquoten.

---

## 3. Der Paradigmenwechsel: Progressive Disclosure für KI-Agenten
Im Jahr 2026 hat sich Progressive Disclosure zur wichtigsten Architektur-Regel für das **Context Engineering** bei Large Language Models (LLMs) und autonomen KI-Agenten entwickelt.

### Das Problem: "Context Rot" (Kontextverfall)
Obwohl moderne KIs riesige Kontextfenster (Millionen von Token) verarbeiten können, führt das simple "Hineinstopfen" aller Dokumente, Werkzeuge und Anweisungen in den initialen Prompt zu massiven Problemen:
* **Verdünnte Aufmerksamkeit:** Wichtige Kernanweisungen gehen in der Masse an Text unter.
* **Widersprüche:** Hunderte geladene Fähigkeiten (Skills) stören sich gegenseitig.
* **Hohe Kosten & Latenz:** Jede Anfrage verbraucht unnötig viele Token.
* **Eingeschränkte Nachvollziehbarkeit:** Bei Fehlern lässt sich kaum feststellen, welcher Teil des gigantischen Prompts den Agenten verwirrt hat.

### Die moderne 3-Ebenen-KI-Architektur
Führende KI-Entwickler (wie Anthropic) empfehlen eine strikte Architektur der schrittweisen Offenlegung für Agenten:

1. **Ebene 1: Metadaten (Index-First Loading)**
   Beim Start erhält der Agent nur einen extrem schlanken Index. Er sieht lediglich die *Namen und kurzen Beschreibungen* der verfügbaren Werkzeuge oder Dokumente (z. B. `[Tool: get_invoice_by_id - Ruft Rechnungsdetails ab]`).
2. **Ebene 2: Instruktionen auf Abruf (Triggering)**
   Entscheidet der Agent, dass er "get_invoice_by_id" benötigt, lädt das System erst jetzt die spezifische `SKILL.md`-Datei, die der KI genau erklärt, wie dieses Werkzeug syntaktisch zu benutzen ist.
3. **Ebene 3: Tiefe Referenzen (Reference on Demand)**
   Die tatsächlichen Zieldaten (z. B. die API-Antwort der Rechnungsdatenbank oder ein langes PDF-Dokument) werden erst ganz am Ende in den Kontext geladen – und sofort wieder verworfen, sobald die Teilaufgabe erledigt ist.

---

## 4. Fortschrittliche Konzepte der KI-Architektur (Stand 2026)

### A. Agentic RAG vs. Klassisches RAG
Klassische Retrieval-Augmented Generation (RAG) zerhackt Dokumente willkürlich und wirft der KI blind Text-Schnipsel (Chunks) vor. 
Modernes Progressive Disclosure nutzt den **"Search -> Outline -> Read"** (Suchen -> Gliedern -> Lesen) Ansatz:
* Die KI sucht nach einem Dokument.
* Das System gibt zunächst nur das **Inhaltsverzeichnis (Outline)** zurück.
* Die KI entscheidet selbstständig, ob sie das ganze Dokument lesen will, oder ob sie gezielt nur Kapitel 3 in ihren Kontext laden möchte. 

### B. Die "Coherence Cascade" (Die Kohärenz-Kaskade)
Eine der neuesten Erkenntnisse im Prompting: LLMs haben einen inhärenten Drang, "Wissenslücken" zu schließen.
* **Schlecht (Front-Loading):** *"Hier ist die 50-seitige API-Dokumentation. Beachte sie."*
* **Gut (Progressive Disclosure):** *"Es existieren 12 validierte Muster für diese API, die Fehler verhindern. Siehe [referenz.md]."*
Der zweite Ansatz erzeugt eine messbare Wissenslücke. Der Agent lädt das Dokument aktiv und gezielt *nur dann*, wenn er an den Punkt kommt, wo er die Muster schreiben muss.

### C. Isolierte Sub-Agenten
Anstatt einem Master-Agenten 50 Tools zu geben, baut man modulare Sub-Agenten. Ein Billing-Agent erhält nur Abrechnungstools, ein Scheduling-Agent nur Kalendertools. Wenn der Hauptagent delegiert, wird der Kontext strikt isoliert. Studien zeigen, dass dies die Qualität der KI-Schlussfolgerungen um bis zu 90 % verbessern kann.

---

## 5. Checkliste: Best Practices für die Praxis

**Für UI/UX-Designer:**
- [ ] Zeigt der erste Bildschirm *nur* die Informationen, die für den unmittelbar nächsten Klick zwingend nötig sind?
- [ ] Sind weiterführende Optionen logisch gruppiert und durch klare Buttons/Akkordeons erreichbar?

**Für KI- & Software-Entwickler:**
- [ ] **Token-Effizienz prüfen:** Hat mein KI-Agent in seinem Basis-Systemprompt nur Metadaten und Indizes, statt seitenweise Tool-Erklärungen?
- [ ] **Typisierte Schemata nutzen (z.B. Pydantic):** Werkzeuge sollten enge, spezifische Aufgaben haben (`suche_nach_ID`) statt gefährlich breit zu sein (`führe_SQL_aus`).
- [ ] **Lebenszyklus des Kontexts:** Werden geladene Referenzdokumente wieder aus dem Kontextfenster des Agenten gelöscht, wenn er sich dem nächsten Arbeitsschritt zuwendet?
- [ ] **Autonomie dem Agenten überlassen:** Bei sehr kurzen Dokumenten (z. B. unter 500 Wörtern) sollte ein Metadaten-Flag (`brief: true`) dem Agenten signalisieren, dass er die Inhaltsverzeichnis-Ebene überspringen und direkt den Volltext lesen darf.

## Fazit
Ob in der Gestaltung von Benutzeroberflächen für Menschen oder im Prompt-Engineering für Künstliche Intelligenz – die goldene Regel des Progressive Disclosure lautet stets: **"Relevanz schlägt Quantität."** Wer Systeme so baut, dass sie Wissen und Funktionen nur im exakten Moment des Bedarfs offenlegen, erschafft effizientere, fehlerresistentere und kostengünstigere Lösungen.
