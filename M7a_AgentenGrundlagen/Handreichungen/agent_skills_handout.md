# Agent Skills bauen

**HANDOUT · KI-AGENTEN**  
**Überarbeitete Fassung · Stand: 11. September 2026**

Teil A und B führen einmal durch den Bau eines vollständigen Skills. Teil C ist als Nachschlagewerk für den Alltag gedacht.

Die Beispiele orientieren sich am **offenen Agent-Skills-Format**. Konkrete Laufzeitumgebungen können zusätzliche Felder, andere Berechtigungsmodelle oder abweichende Aktivierungsmechanismen besitzen. Die konkrete Modell-API ist deshalb bewusst nicht Bestandteil dieses Handouts. [1][2]

## Geltungskennzeichnung

Technische Aussagen werden dort gekennzeichnet, wo die Unterscheidung wichtig ist:

- **[S] Spezifikation** – vom offenen Agent-Skills-Format festgelegt.
- **[K] Konvention** – verbreitet, aber nicht zwingend.
- **[E] Empfehlung** – fachlich begründete Best Practice.
- **[B] Beobachtung** – empirischer Befund; nicht automatisch verallgemeinerbar.
- **[P] Plattformabhängig** – hängt von Agent, Runtime oder Berechtigungsmodell ab.

---

# Teil A · Was ist ein Skill?

## 1. Ein Skill bündelt spezialisiertes Wissen und Arbeitsabläufe

Ein Agent Skill ist ein wiederverwendbares Paket aus **Anweisungen, spezialisiertem Kontext und optionalen Ressourcen**, das einem Agenten bei einer bestimmten Aufgabe hilft. Typisch sind prozedurales Wissen, domänenspezifische Regeln, Beispiele, Referenzen oder Hilfsskripte. [1][2]

Das durchgehende Beispiel dieses Hefts ist der Bau eines Prüfungsbogens nach hausinternen Vorgaben.

Das Modell kennt allgemeine Prinzipien zum Erstellen von Prüfungsaufgaben. Es kennt aber nicht automatisch Ihre lokalen Regeln – etwa:

- jede Aufgabe beginnt mit einer Situationsbeschreibung,
- jede Aufgabe wird einer Handlungskompetenz zugeordnet,
- Lösungshinweise stehen auf einem eigenen Blatt.

Genau solche **lokalen, nicht offensichtlichen Vorgaben** sind gute Kandidaten für einen Skill. [3]

**Faustregel [E]:** Schreiben Sie nicht ausführlich in den Skill, was ein leistungsfähiges Modell ohnehin zuverlässig beherrscht. Nutzen Sie den knappen Kontext für projektspezifische Regeln, Abläufe, Randfälle und Werkzeuge. [3]

### Abgrenzung zu benachbarten Mechanismen

| Mechanismus | Primäre Funktion | Typischer Einsatz |
|---|---|---|
| System-/Agent-Instruktionen | übergreifende Regeln | gelten dauerhaft oder sitzungsweit |
| Agent Skill | wiederverwendbare Arbeitsanleitung + spezialisierter Kontext | wird bei einer passenden Aufgabe aktiviert |
| Retrieval / RAG | relevante Informationen aus einem größeren Bestand auswählen | Fakten oder Dokumentausschnitte nachladen |
| MCP | standardisierte Schnittstelle für Tools, Ressourcen und Prompts | externe Fähigkeiten und Daten anbinden |

MCP ist damit nicht nur „Zugriff auf ein fremdes System“: MCP-Server können **Tools, Resources und Prompts** bereitstellen. [5]

Die Grenzen sind bewusst nicht hart. Ein Skill kann Referenzmaterial enthalten, ein Retrieval-System kann Arbeitsanweisungen liefern und ein MCP-Server kann Kontextressourcen anbieten. Die Tabelle beschreibt die **primäre Funktion**, nicht eine exklusive Zuordnung.

---

## 2. Aufbau eines Skills

Ein Skill ist ein Verzeichnis mit mindestens einer Datei namens `SKILL.md`. [S] Die Datei enthält YAML-Frontmatter und danach Markdown-Anweisungen. [1]

```text
pruefungsaufgaben-erstellen/
├── SKILL.md
├── references/      # optional
├── scripts/         # optional
└── assets/          # optional
```

Im offenen Format sind `name` und `description` Pflichtfelder. [S] Weitere Felder wie `license`, `compatibility` oder `metadata` sind optional; einzelne Clients können zusätzliche Felder unterstützen. [1]

### Minimaler Skill

```python
from pathlib import Path

ordner = Path("skills/pruefungsaufgaben-erstellen")
ordner.mkdir(parents=True, exist_ok=True)

skill = """---
name: pruefungsaufgaben-erstellen
description: Erstellt Prüfungsaufgaben nach den hausinternen Vorgaben. Verwenden bei Anfragen zu Prüfungsaufgaben, Klausuren, Aufgabenbögen, Musterlösungen oder Punkterastern. Nicht verwenden für Übungsblätter ohne Bewertung oder reine Begriffserklärungen.
---

# Prüfungsaufgaben erstellen

## Ablauf
1. DQR-Niveau erfragen, falls nicht genannt. Nicht schätzen.
2. Jeder Aufgabe eine Situationsbeschreibung voranstellen.
3. Jede Aufgabe genau einer Handlungskompetenz zuordnen.
4. Lösungshinweise auf ein eigenes Blatt setzen.
"""

(ordner / "SKILL.md").write_text(skill, encoding="utf-8")
```

Die frühere Formulierung „IHK-konform“ wird hier bewusst nicht verwendet: Aus hausinternen Regeln allein lässt sich keine allgemeine IHK-Konformität ableiten.

### Progressive Disclosure

Skills sind für eine gestufte Bereitstellung ausgelegt: [1][2]

1. **Discovery:** Name und Beschreibung machen den Skill auffindbar.
2. **Activation:** Bei passender Aufgabe werden die vollständigen Anweisungen der `SKILL.md` geladen.
3. **Execution:** Referenzen, Assets oder Skripte werden bei Bedarf genutzt.

So bleibt der anfängliche Kontext klein. Das offene Format nennt als Orientierung etwa 50–100 Token Metadaten pro Skill und empfiehlt, die eigentliche `SKILL.md` unter ungefähr 5.000 Token bzw. 500 Zeilen zu halten. [1][2]

---

## 3. Wie das Laden funktioniert

Wichtig ist die Trennung zwischen **Standard und Runtime**:

Der offene Standard beschreibt Discovery, Activation und Execution. **Wie** eine konkrete Laufzeitumgebung entscheidet, dass ein Skill relevant ist, ist ein Implementierungsdetail. [2]

Ein zusätzlicher, separater Modellaufruf zur Skill-Auswahl ist daher **keine Anforderung des Standards**. Er kann als didaktische Simulation verwendet werden, darf aber nicht mit der internen Architektur einer beliebigen Runtime gleichgesetzt werden.

### Ebene 1 – Katalog

Schematisch kann ein Client die Metadaten aller Skills einlesen:

```python
from pathlib import Path
import yaml

katalog = []

for datei in Path("skills").glob("*/SKILL.md"):
    text = datei.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    meta = yaml.safe_load(frontmatter)
    katalog.append((meta["name"], meta["description"]))

print(katalog)
```

Das zeigt das Prinzip der Discovery – nicht die interne Implementierung eines bestimmten Produkts.

### Ebene 2 – Aktivierung

Die Runtime macht dem Agenten die verfügbaren Skills anhand ihrer Metadaten bekannt. Passt die Aufgabe zu einem Skill, wird dessen `SKILL.md` geladen. Die konkrete Auswahl kann je nach Client durch Modellentscheidung, expliziten Aufruf oder andere Logik erfolgen. [2][P]

### Ebene 3 – Zusatzmaterial

Referenzdateien werden erst in den Kontext geladen, wenn sie benötigt werden. Große Mengen vorsorglich zu laden widersprechen dem Gedanken der Progressive Disclosure. [1][3]

Skripte können von einer Runtime ausgeführt werden, **ohne dass ihr vollständiger Quelltext vorher in den Modellkontext geladen wird**. Dann belegt vor allem das Ergebnis der Ausführung Kontext. Ob und wann ein Agent den Quelltext zusätzlich liest, hängt von Aufgabe und Runtime ab. [1][P]

---

# Teil B · Einen Skill bauen

## Schritt 1 – Aufgabe zunächst ohne Skill erledigen

Bearbeiten Sie die Zielaufgabe zunächst ohne Skill. Protokollieren Sie anschließend die Korrekturen, die nötig waren.

Beispiel:

```text
- Situationsbeschreibung fehlt
- Handlungskompetenz nicht zugeordnet
- Lösungshinweis stand unter der Aufgabe
```

Diese Korrekturen zeigen, welches Wissen oder welche Arbeitsregel dem Agenten tatsächlich gefehlt hat.

## Schritt 2 – Testfälle vor dem Feinschliff formulieren

Ein Skill kann auf zwei Ebenen scheitern:

- **Aktivierungstest:** Greift er bei passenden Anfragen und bleibt er bei ähnlichen, aber unpassenden Anfragen inaktiv?
- **Ergebnistest:** Entspricht das Resultat den fachlichen und formalen Anforderungen?

Verwenden Sie realistische positive Fälle und bewusst ähnliche **Near-Misses** als negative Fälle. Aktuelle Best Practices empfehlen, Aktivierungsqualität und Ergebnisqualität getrennt zu evaluieren. [4]

Beispiel:

```python
soll_greifen = [
    "Ich brauche eine Klausur zu neuronalen Netzen.",
    "Erstelle einen Aufgabenbogen für die Abschlussprüfung.",
    "Bitte eine Musterlösung zum Thema Overfitting.",
]

soll_schweigen = [
    "Erstelle ein Übungsblatt ohne Bewertung.",
    "Erklär mir Overfitting.",
    "Schreib eine Mail wegen der Prüfungstermine.",
]
```

## Schritt 3 – Beschreibung trennscharf formulieren

Die `description` muss beschreiben,

1. **was** der Skill tut und
2. **wann** er eingesetzt werden soll. [S]

Eine gute Beschreibung ist knapp, nennt typische Nutzerabsichten und relevante Begriffe und grenzt nahe Fehlanwendungen ab. [1][4]

Nicht die Lautstärke der Formulierung ist entscheidend, sondern ihre **Trennschärfe**. Eine zu breite Beschreibung erzeugt Fehlaktivierungen; eine zu enge Beschreibung verpasst passende Fälle. [4]

## Schritt 4 – Haupttext: lokales Wissen statt Lehrbuch

Nehmen Sie vor allem auf, was der Agent ohne den Skill nicht wissen kann oder nicht zuverlässig einhält:

- lokale Regeln und Konventionen,
- verbindliche Abläufe,
- notwendige Randfälle,
- konkrete Werkzeuge und Pfade,
- gewünschte Ausgabeformate.

Lange Grundlagenerklärungen verbrauchen Kontext und können wichtige Anweisungen verdecken. [3]

Fehlende Voraussetzungen sollten explizit behandelt werden:

```text
Fehlt das DQR-Niveau, nachfragen statt schätzen.
```

Ein Modell darf beim Formulieren eines Skill-Entwurfs helfen. Entscheidend ist, dass der fachliche Inhalt **aus überprüften Anforderungen und realen Korrekturen** stammt und anschließend redigiert und getestet wird.

## Schritt 5 – Deterministische Schritte auslagern

Für **wiederkehrende, exakt prüfbare Operationen** sind Skripte oder andere deterministische Werkzeuge oft geeigneter als freie Modellgenerierung. [3]

Typische Kandidaten:

- Summen prüfen,
- Dateien umbenennen,
- Formate validieren,
- strukturierte Daten transformieren.

Urteilsabhängige oder sprachlich offene Aufgaben bleiben beim Modell.

Beispiel:

```python
import json
import sys

with open(sys.argv[1], encoding="utf-8") as datei:
    aufgaben = json.load(datei)

summe = sum(aufgabe["punkte"] for aufgabe in aufgaben)
print("Punktesumme:", summe)

if summe != 100:
    print("FEHLER: erwartet werden 100 Punkte.")

for aufgabe in aufgaben:
    if "kompetenz" not in aufgabe:
        print("FEHLER: Aufgabe", aufgabe["nr"], "ohne Handlungskompetenz.")
```

Skripte sollen ihre Abhängigkeiten dokumentieren, verständliche Fehlermeldungen liefern und Randfälle möglichst kontrolliert behandeln. [1]

## Schritt 6 – Selten benötigtes Material auslagern

Referenzdateien erhalten einen **konkreten Pfad und einen konkreten Anlass**:

```text
Bei DQR-Niveau 6 zuerst references/dqr-niveaus.md lesen.
```

Empfohlen wird, Verweise von der `SKILL.md` aus möglichst nur eine Ebene tief zu halten. Lange Referenzdateien sollten gut gegliedert sein; bei umfangreichen Dateien hilft ein Inhaltsverzeichnis. [1][3]

---

## Grenzen des Ansatzes

### Aktivierung bleibt evaluierungsbedürftig

Auch bei einer guten Beschreibung kann ein Agent einen Skill zu früh, zu spät oder gar nicht aktivieren. Deshalb sind positive und negative Aktivierungstests wichtiger als vermeintliche Faustzahlen. [4]

### Keine allgemeine „30-Skills-Grenze“

Eine feste Obergrenze lässt sich aus dem Standard nicht ableiten. Mit der Zahl und Länge der Skill-Beschreibungen wächst der Katalog; wie viele Skills praktisch gut funktionieren, hängt von Runtime, Modell, Überschneidung der Beschreibungen und Evaluationsqualität ab. [1][2][P]

### Zusätzliche Indirektion

Bei einem falschen Ergebnis kommen mehrere Fehlerquellen infrage: Anfrage, Aktivierung, `SKILL.md`, Referenzmaterial, Skript oder Tool. Skills machen wiederkehrende Abläufe reproduzierbarer, erhöhen aber zugleich den Diagnoseaufwand.

**Faustregel [E]:** Ein Skill lohnt sich besonders, wenn eine Aufgabe wiederkehrt, lokale Regeln enthält oder von mehreren Personen bzw. Agenten konsistent ausgeführt werden soll.

---

## Sicherheit: Skills als Lieferketten-Abhängigkeit behandeln

Welche Rechte ein Skill tatsächlich besitzt, bestimmt **nicht das Dateiformat allein**, sondern die Runtime und deren Berechtigungs- und Isolationsmodell. [P]

Trotzdem gilt: Ein fremder Skill kann natürliche Sprache, Skripte, Binärdateien, Referenzen und externe Abhängigkeiten kombinieren. Er sollte daher wie eine **nicht vertrauenswürdige Software-Abhängigkeit** geprüft werden. [6][7]

### Aktuelle Befunde

Eine Snyk-Untersuchung vom Februar 2026 analysierte 3.984 öffentlich verfügbare Skills aus zwei Marktplätzen. 36,82 % wiesen mindestens ein Sicherheitsproblem auf, 13,4 % mindestens ein kritisches; 76 bösartige Payloads wurden manuell bestätigt. Diese Zahlen beschreiben den untersuchten öffentlichen Korpus und sind **keine allgemeine Fehlerquote für alle Skills**. [6]

Trail of Bits zeigte im Juni 2026, dass sich mehrere öffentliche Skill-Scanner umgehen ließen. Drei der vier demonstrierten Angriffe wurden in weniger als einer Stunde entwickelt; der Prompt-Injection-basierte vierte Angriff benötigte mehrere Stunden. Die zentrale Schlussfolgerung: Scanner sind hilfreich, ersetzen aber keine Vertrauens- und Lieferkettenkontrollen. [7]

Das OWASP-Projekt **Agentic Skills Top 10** befindet sich weiterhin in aktiver Entwicklung. Der veröffentlichte Zeitplan sieht einen v1.0 Release Candidate im Q3 2026 und die v1.0-Veröffentlichung im Q4 2026 vor. [8]

### Prüfliste für fremde Skills

- Herkunft und Version prüfen; keine beweglichen, ungeprüften Quellen verwenden.
- `SKILL.md`, Referenztexte und Skripte prüfen.
- Netzwerkzugriffe, Shell-Aufrufe und Dateizugriffe begründen lassen.
- Zugangsdaten nicht im Skill speichern.
- Nach dem Least-Privilege-Prinzip nur benötigte Tools und Rechte freigeben.
- Unbekannte Skills zunächst isoliert testen.
- Automatische Scanner als zusätzliche Hilfe, nicht als alleinige Vertrauensentscheidung verwenden.
- In Organisationen eine kuratierte, versionierte Sammlung freigegebener Skills pflegen. [7][8]

---

# Teil C · Täglicher Gebrauch

## 1. Abnahmecheckliste

Vor der Weitergabe eines eigenen Skills:

- Sagt die Beschreibung klar, **was** der Skill tut und **wann** er greift?
- Wurden passende Anfragen und Near-Misses getestet?
- Enthält der Haupttext überwiegend Wissen und Regeln, die der Agent sonst nicht zuverlässig kennt?
- Ist festgelegt, was bei fehlenden Angaben geschieht?
- Sind wiederkehrende, exakt prüfbare Schritte sinnvoll automatisiert?
- Sind Skriptabhängigkeiten und Fehlerfälle dokumentiert?
- Haben Referenzen einen konkreten Pfad und Anlass?
- Ist festgelegt, wer den Skill pflegt und wann er erneut geprüft wird?

Ein Skill ist gelungen, wenn er den gewünschten Ablauf **wiederholbar und überprüfbar** unterstützt – nicht bloß, wenn er einmal ein gutes Ergebnis erzeugt.

## 2. Entscheidungshilfen

| Frage | Eher A | Eher B |
|---|---|---|
| Skript oder Modell? | Skript: wiederkehrend und exakt prüfbar | Modell: Urteilsvermögen oder offene Sprache nötig |
| Skill oder Prompt? | Skill: wiederkehrend, lokale Regeln, mehrere Nutzer | Prompt: einmalig oder selten |
| Haupttext oder Referenz? | Haupttext: fast immer benötigt | Referenz: nur unter einer klaren Bedingung |
| Ausführen oder lesen? | Ausführen: nur Ergebnis nötig | Lesen: Logik selbst muss verstanden oder geprüft werden |

## 3. Feste Grenzen des offenen Formats

| Feld / Größe | Grenze |
|---|---|
| Dateiname | `SKILL.md` |
| `name` | 1–64 Zeichen; `a-z`, Ziffern und Bindestriche; kein Bindestrich am Anfang/Ende; keine doppelten Bindestriche; entspricht dem Verzeichnisnamen |
| `description` | 1–1024 Zeichen; beschreibt **was** der Skill tut und **wann** er eingesetzt wird |
| Haupttext | Empfehlung: unter ca. 5.000 Token bzw. 500 Zeilen |
| Referenzen | relative Pfade vom Skill-Root; tiefe Verweisketten vermeiden |

Optionale Standardfelder sind unter anderem `license`, `compatibility` und `metadata`. Ein Feld zur Vorabfreigabe von Tools ist im Standard als experimentell gekennzeichnet; die tatsächliche Unterstützung und Bedeutung von Berechtigungsfeldern ist runtimeabhängig. [1][P]

## 4. Übung

Wählen Sie eine wiederkehrende Aufgabe mit eigenen Regeln.

1. Formulieren Sie eine Beschreibung: Was tut der Skill, wann soll er greifen?
2. Notieren Sie drei Eigenheiten Ihres Vorgehens, die ein Außenstehender nicht erraten könnte.
3. Markieren Sie einen wiederkehrenden, exakt prüfbaren Schritt, der sich für ein Skript eignet.
4. Schreiben Sie passende Testanfragen und bewusst ähnliche Near-Misses.
5. Legen Sie fest, was bei fehlenden Angaben geschehen soll.
6. Testen Sie Aktivierung und Ergebnis getrennt und schärfen Sie den Skill anhand der Fehler nach.

### Zusatzaufgabe zur Geltungskennzeichnung

Nehmen Sie eine Anleitung zu Agent Skills und markieren Sie technische Aussagen als **S, K, E, B oder P**. Prüfen Sie anschließend, welche Aussagen tatsächlich durch Spezifikation, dokumentierte Best Practice oder empirische Evidenz abgesichert sind.

---

# Quellen und Stand

**Stand der fachlichen Prüfung: 11. September 2026.**  
Spezifikationen, Best Practices und insbesondere Sicherheitszahlen können sich kurzfristig ändern.

[1] Agent Skills – Specification:  
https://agentskills.io/specification

[2] Agent Skills – Client implementation / Progressive Disclosure:  
https://agentskills.io/client-implementation/adding-skills-support

[3] Agent Skills – Best practices for skill creators:  
https://agentskills.io/skill-creation/best-practices

[4] Agent Skills – Optimizing skill descriptions:  
https://agentskills.io/skill-creation/optimizing-descriptions

[5] Model Context Protocol – Server primitives / Tools, Resources, Prompts:  
https://modelcontextprotocol.io/specification/2025-06-18/server/index  
Aktueller Protokollstand 2026-07-28: https://blog.modelcontextprotocol.io/posts/2026-07-28/

[6] Snyk – ToxicSkills, 5. Februar 2026:  
https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/

[7] Trail of Bits – The sorry state of skill distribution, 3. Juni 2026:  
https://blog.trailofbits.com/2026/06/03/the-sorry-state-of-skill-distribution/

[8] OWASP – Agentic Skills Top 10, Projektstatus und Zeitplan:  
https://owasp.org/www-project-agentic-skills-top-10/
