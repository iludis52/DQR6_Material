# Leitfaden für die Unterrichtsstunde: Agent Skills

## Ziel der Stunde

Die Lernenden sollen **Agent Skills als Architekturbaustein einordnen können**. Im Mittelpunkt steht nicht das Dateiformat an sich, sondern die Frage:

> **Welches Problem lösen Agent Skills – und wann sind sie gegenüber System-Prompt, RAG, LangGraph oder Tools die passendere Lösung?**

Am Ende der Stunde sollen die Lernenden erklären können,

- was ein Agent Skill grundsätzlich ist,
- wie `name`, `description` und `SKILL.md` zusammenspielen,
- was mit **Progressive Disclosure** gemeint ist,
- wie sich Skills von RAG und expliziter LangGraph-Orchestrierung unterscheiden,
- warum deterministische Prüfschritte besser in Code als in freie Modellgenerierung gehören.

---

## Grundidee der Vermittlung

Die Stunde folgt dem Prinzip:

**Problem erleben → Mechanismus einführen → Architektur einordnen → Transfer leisten**

Die Lernenden kennen bereits RAG und LangGraph. Dieses Vorwissen wird bewusst genutzt.

Die zentrale Leitfrage lautet:

> **Wann brauche ich Wissen, wann einen Ablauf, wann einen Kontrollfluss und wann ein Tool?**

Als vereinfachtes mentales Modell:

- **System-/Agent-Instruktionen:** Was soll immer gelten?
- **RAG:** Welche Information brauche ich jetzt?
- **LangGraph:** Welcher Kontrollfluss soll explizit modelliert werden?
- **Agent Skill:** Welche wiederverwendbare Arbeitsweise bzw. welcher spezialisierte Kontext soll bei einer passenden Aufgabe verfügbar werden?
- **Tool/Skript:** Welche Operation soll deterministisch ausgeführt oder geprüft werden?

---

## Möglicher Stundenverlauf

### 1. Einstieg: Warum reicht ein normales Modell nicht?

Mit einer einfachen Anfrage starten, z. B.:

> „Ich brauche etwas, das mich wach macht.“

Zunächst ohne Skill beantworten lassen.

Danach die hausinternen Regeln des Kaffee-Skills zeigen, etwa:

- Mengen nur in Gramm,
- genau drei Schritte,
- Temperatur mit Toleranz,
- definierte Schlusszeile.

Leitfrage an die Gruppe:

> **Woher sollte das Modell diese Regeln kennen?**

Ziel: Der Bedarf für einen Skill entsteht aus einem konkreten Problem.

---

### 2. Einen Skill sichtbar machen

Die `SKILL.md` des Kaffee-Beispiels zeigen.

Dabei drei Ebenen unterscheiden:

- `name` → Identität des Skills
- `description` → **Wann** ist der Skill relevant?
- Markdown-Inhalt → **Wie** soll die Aufgabe ausgeführt werden?

Merksatz:

> **`description` entscheidet über Relevanz, der Skill-Inhalt über die Ausführung.**

An dieser Stelle noch nicht zu viele Spezifikationsdetails behandeln.

---

### 3. Progressive Disclosure erklären

Nun den zweiten Skill, z. B. Tee, ergänzen.

Frage:

> **Muss der Agent immer den vollständigen Inhalt aller Skills kennen?**

Darauf aufbauend das Prinzip erklären:

1. Metadaten aller Skills stehen für die Auswahl bereit.
2. Erst bei passender Anfrage wird der vollständige Skill geladen.
3. Weitere Ressourcen wie `scripts/` oder `references/` werden nur bei Bedarf genutzt.

Das Notebook macht diesen Ablauf sichtbar:

```text
Nutzeranfrage
    ↓
Katalog aus name + description
    ↓
passenden Skill auswählen
    ↓
SKILL.md laden
    ↓
Aufgabe mit den zusätzlichen Anweisungen bearbeiten
```

Wichtig: Die modellbasierte Auswahl im Notebook ist eine **didaktische Simulation**. Die konkrete Aktivierungslogik hängt von der jeweiligen Runtime ab.

---

### 4. Anschluss an vorhandenes Vorwissen

Die Lernenden sollen Agent Skills jetzt in bekannte Konzepte einordnen.

Leitfragen:

- Wann wäre ein **RAG-System** sinnvoller als ein Skill?
- Wann sollte ein Ablauf explizit in **LangGraph** modelliert werden?
- Wann reicht ein guter **System-Prompt**?
- Wann ist ein Skill sinnvoll, weil lokale Regeln oder wiederkehrende Arbeitsweisen gebündelt werden sollen?

Hilfreiche Kurzform:

| Mechanismus | Kernfrage |
|---|---|
| System Prompt | Was gilt immer? |
| RAG | Welche Information brauche ich? |
| LangGraph | Welcher Kontrollfluss ist nötig? |
| Skill | Welche Arbeitsweise soll bei Bedarf verfügbar sein? |
| Tool | Was soll deterministisch ausgeführt werden? |

---

### 5. Aktivierung testen

Nun nicht nur offensichtliche Fälle testen, sondern auch Grenzfälle:

- „Ich möchte Filterkaffee.“
- „Ich brauche etwas, das mich wach macht.“
- „Erkläre mir die Wirkung von Koffein.“

Vor jedem Lauf kurz abstimmen lassen:

> **Welcher Skill sollte greifen – und warum?**

Dadurch wird sichtbar, dass die `description` nicht nur Dokumentation ist, sondern für die Aktivierung relevant sein kann.

---

### 6. Deterministisch vs. probabilistisch

Anschließend die einfache Prüffunktion verwenden.

Frage:

> **Welche Regeln sollte das Modell beurteilen – und welche können wir exakt prüfen?**

Beispiele:

- „Punktesumme = 100“ → deterministisch
- „genau drei Schritte“ → deterministisch
- „sprachlich angemessen“ → urteilsabhängig

Merksatz:

> **Das Modell formuliert und bewertet offene Aufgaben; deterministische Werkzeuge prüfen eindeutig entscheidbare Regeln.**

---

### 7. Vertiefung: Tool-Use

Im erweiterten Notebook wird die Prüflogik in ein Skript unter `scripts/` ausgelagert.

Damit entsteht die dritte Ebene:

```text
Skill aktivieren
    ↓
Modell erzeugt Ergebnis
    ↓
Skill-Skript wird ausgeführt
    ↓
deterministisches Prüfergebnis
```

Wichtig hervorheben:

> Ein Skill kann Anweisungen und ausführbare Ressourcen bündeln.

Ebenso klarstellen:

> Das Skript im Skill ist nicht automatisch dasselbe wie standardisiertes Function Calling. Wie Tools ausgeführt werden, hängt von der Runtime ab.

---

## Transferphase

Nach dem Kaffee-/Tee-Beispiel auf das realistischere Prüfungsbeispiel aus dem Handout wechseln.

Mögliche Aufgabe:

> „Welche Bestandteile eines Prüfungsprozesses gehören in den Skill, welche in ein Skript, welche eventuell in RAG und welche in einen expliziten LangGraph-Workflow?“

Ziel ist nicht mehr das Nachbauen des Beispiels, sondern eine **Architekturentscheidung**.

---

## Abschlussfrage

Zum Ende der Stunde eine kurze Entscheidungsfrage stellen:

> **Wann würden Sie für eine neue Aufgabe einen Agent Skill bauen – und wann ausdrücklich nicht?**

Eine gute Antwort sollte mindestens berücksichtigen:

- wiederkehrende Aufgabe,
- lokale oder domänenspezifische Regeln,
- bedingte Aktivierung,
- Abgrenzung zu RAG,
- Abgrenzung zu expliziter Workflow-Orchestrierung,
- mögliche deterministische Teilaufgaben.

---

## Didaktischer Kern

Die Stunde sollte nicht als „Einführung in `SKILL.md`“ gerahmt werden, sondern als:

> **Einführung in eine weitere Form der Agent-Orchestrierung und Kontextbereitstellung.**

Die technische Struktur ist Mittel zum Zweck. Entscheidend ist, dass die Lernenden begründet entscheiden können, **wann ein Skill architektonisch sinnvoll ist**.
