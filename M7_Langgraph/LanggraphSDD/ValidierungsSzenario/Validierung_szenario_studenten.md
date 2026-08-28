# Validierungsdurchlauf: „Wartungs-Assistent Brandt & Söhne"

> **Einordnung:** Ihr testet heute nicht (nur) einen LangGraph-Agenten —
> ihr testet die **Werkzeugkette selbst**. Das SDD-Schema (Meta-Prompt,
> Review-Checkliste, Plan-Vorlage, Test-Vorlage, Konventions-Skill) ist
> ein Produkt wie jedes andere: Es hat eine Spezifikation (seine
> Pflichtstrukturen), es hat Tests (die Review-Checkliste) — und es
> braucht einen Validierungsdurchlauf mit realen Eingaben, bevor man
> ihm vertraut. Diesen Durchlauf führt ihr durch.

## Zwei Lernziele — zwei Rollen

| Rolle | Ihr prüft | Ergebnis |
|---|---|---|
| **Anwender** | Könnt ihr mit der Werkzeugkette aus rohen Kundennotizen eine freigegebene Spec entwickeln? | `prozess.md`, `spec.md`, Review-JSON |
| **Prozess-Entwickler** | Wo trägt die Werkzeugkette, wo hakt sie? Welche Lücke im *Prozess* hat welchen Fehler im *Ergebnis* verursacht? | Prozess-Befundliste mit Änderungsvorschlägen |

Die zweite Rolle ist die eigentliche Pointe: Ein Entwicklungsprozess wird
genauso entwickelt wie ein Agent — Spec, Test, Durchlauf, Befund,
Iteration. Wer nur die erste Rolle spielt, hat die halbe Übung gemacht.

---

## Setup (vor dem Start)

Ihr braucht **drei getrennte LLM-Sitzungen** — Trennung ist Pflicht,
nicht Kosmetik:

1. **Interviewer-Sitzung:** `Phase0_1_meta_prompt_langgraph.md` als
   System-Prompt bzw. erste Nachricht.
2. **Prüfer-Sitzung:** bleibt leer, bis eure `spec.md` fertig ist.
   Dann `Phase2_review_checkliste.md` + `spec.md` + `prozess.md`
   hineingeben. Der Prüfer darf die Interview-Historie **nie** sehen.
3. **Ihr selbst** seid Regisseur und Kunden-Proxy. Ihr tippt die
   Kundenantworten — nach den Spielregeln unten.

Zeitrahmen als Orientierung: Phase 0 ca. 20 min, Phase 1 ca. 60–75 min,
Phase 2 + Rückspiel der Befunde ca. 30 min, Beobachtungsprotokoll läuft
nebenher. Phasen 3–5 sind heute optional (siehe Ausbaustufe am Ende).

## Spielregeln für den Kunden-Proxy

1. Ihr antwortet **nur** mit Wissen aus den Gesprächsnotizen (Teil A)
   und dem Kundengedächtnis (Teil B). Teil B gebt ihr erst preis, wenn
   die passende Frage kommt — nicht vorauseilend.
2. Für Themen auf der „Weiß-der-Kunde-nicht"-Liste (Teil C) antwortet
   ihr genau so: „Weiß ich nicht" / „Das müsst ihr mir sagen." Ob daraus
   ein `[OFFEN: ...]` wird oder eine stille Annahme, ist einer der
   spannendsten Messpunkte des Durchlaufs.
3. Der Kunde ist kein Informatiker. Er sagt nicht „State-Feld" oder
   „Reducer". Wenn der Interviewer Fachbegriffe unübersetzt auf euch
   ablädt, ist **das ein Prozess-Befund** — notieren.
4. Ihr helft dem Interviewer nicht. Wenn er eine Pflichtfrage vergisst,
   stellt ihr sie nicht für ihn. Ihr protokolliert die Lücke.

---

## Teil A — Gesprächsnotizen Erstgespräch (roh)

*So bekommt ihr sie vom Vertrieb. Genau diesen Block gebt ihr dem
Interviewer als Startmaterial.*

```
Erstgespräch Brandt & Söhne Sondermaschinenbau GmbH, GF Herr Brandt
~80 MA, Servicetechniker im Außendienst (12 Leute)

Problem: Techniker rufen dauernd im Büro an, um Sachen aus den
Wartungshandbüchern zu erfragen. Doku liegt auf dem Firmenserver:
PDF-Handbücher (teils >300 Seiten), Serviceberichte als Word-Dateien,
dazu ein Ordner "Altbestand" mit gescannten PDFs.

Wunsch O-Ton: "So ein ChatGPT für unsere Doku." Techniker stellt
Frage vom Handy, bekommt Antwort MIT Quellenangabe — welches
Handbuch, welche Seite. Quellenangabe ist Pflicht ("Haftung!").

Neue Dokumente kommen laufend dazu (jeder abgeschlossene Auftrag =
neuer Servicebericht). "Das soll dann einfach nachts aktualisiert
werden. Tagsüber darf nix langsamer werden."

Antworten: "Wenn er nichts findet, soll er das ehrlich sagen und
nicht rumfantasieren." Auf die Frage, ob das System bei unklaren
Fragen nachhaken soll, erst: "Nachfragen wäre gut." Fünf Minuten
später: "Andererseits — die Jungs haben Handschuhe an, die wollen
nicht groß tippen."

Qualität: Herr Brandt erzählt von einem Bekannten, bei dem ein
Chatbot ein Drehmoment falsch angegeben hat. "Es muss irgendeine
Kontrolle geben, dass die Antwort stimmt, bevor sie rausgeht."
Wie die aussehen soll: "Das müsst ihr wissen, ihr seid die Experten."

Ton: "Kurz und knackig, Technikerdeutsch." Später im Gespräch: das
Ding soll irgendwann auch der Vertrieb nutzen, "die brauchen es
ausführlicher, mit ganzen Sätzen". Evtl. auch auf Englisch für die
Kollegen im Werk Tschechien — "mal sehen".

"Und wenn das läuft, soll das Ding vielleicht auch gleich die
Ersatzteilnummern aus dem ERP raussuchen." (irgendwann)

Harte Grenze: keine Cloud. "Unsere Doku geht nirgendwo hin."
Es steht ein Server im Keller.
```

## Teil B — Kundengedächtnis (nur auf passende Frage preisgeben)

- **Mengen:** ca. 1.200 PDF-Handbücher, 40–60 neue Serviceberichte pro
  Monat, Altbestand ca. 200 gescannte PDFs.
- **Nutzer:** 12 Techniker sofort; Vertrieb (5 Personen) „in Stufe 2".
- **Zur Kontrolle vor der Antwort:** Wenn man nachbohrt, was passieren
  soll, falls die Kontrolle die Antwort für zweifelhaft hält:
  „Dann lieber ehrlich sagen: *Bitte im Büro anrufen.* Eine falsche
  Antwort ist schlimmer als keine."
- **Zum Nichts-gefunden-Fall:** Auf Nachfrage kommt die Idee:
  „Der könnte es doch mit anderen Worten nochmal probieren, bevor er
  aufgibt, oder?" — Wie oft? „Keine Ahnung, ihr seid die Experten."
- **Zum Widerspruch Nachfragen/Handschuhe:** Wenn der Interviewer den
  Widerspruch **benennt**, entscheidet Herr Brandt: „Dann lieber ohne
  Rückfragen. Eine Antwort pro Frage." Wenn der Interviewer den
  Widerspruch nicht benennt, bleibt der Kunde bei beiden Aussagen.
- **Zur Quellenangabe:** Seitenzahl reicht nicht bei den
  Word-Serviceberichten (die haben keine stabilen Seiten) — da soll
  Datum + Auftragsnummer genannt werden. Das fällt dem Kunden aber
  erst ein, wenn konkret nach den Serviceberichten gefragt wird.

## Teil C — Weiß der Kunde nicht (darf nur als `[OFFEN]` enden)

- Ob die gescannten Altbestand-PDFs maschinenlesbar sind (OCR-Frage).
- Ob Englisch wirklich kommt und wann.
- Ab welcher Güte eine Antwort „gut genug" ist (keine Zahl nennbar).
- Was für ein Server im Keller steht (GPU? RAM? „Da müsste ich die
  IT fragen").

---

## Durchlauf-Auftrag

1. **Phase 0:** Notizen (Teil A) in die Interviewer-Sitzung geben,
   Interview führen bis `prozess.md` steht.
2. **Phase 1:** Einen Teilgraphen wählen (Empfehlung: den nachgelagerten,
   interaktiven — er ist der interessantere), Interview bis `spec.md`.
3. **Phase 2:** `spec.md` + `prozess.md` in die frische Prüfer-Sitzung.
   JSON-Befunde zurück in die Interviewer-Sitzung spielen, Spec
   nachschärfen, erneut prüfen lassen — bis `freigabe: true`.
4. Parallel durchgehend: **Beobachtungsprotokoll** führen (unten).

**Ausbaustufe** (zweite Sitzung oder Hausaufgabe): Phase 3 (Plan-Vorlage
ausfüllen) und Phase 4 (Test-Vorlage instanziieren — Platzhalter aus
eurer Spec). Spätestens hier zeigt sich, ob eure Spec präzise genug war:
Jede Zelle, die ihr in der Test-Vorlage nicht füllen könnt, ist ein
rückwirkender Spec-Befund.

---

## Beobachtungsprotokoll (die Prozess-Entwickler-Rolle)

Führt es **während** des Durchlaufs, nicht aus der Erinnerung. Pro
Auffälligkeit eine Zeile:

| # | Phase/Turn | Was ist passiert? | Befund-Typ | Betroffenes Artefakt |
|---|---|---|---|---|

**Befund-Typen** (analog zum Befund-Routing des Agenten-Prozesses —
die Symmetrie ist Absicht):

- **Leitfaden-Lücke:** Der Interviewer hat etwas Wichtiges nie gefragt,
  und keine Pflichtstruktur hat ihn gezwungen. → Meta-Prompt ändern.
- **Formularzwang griff:** Eine Pflichtstruktur (Reducer-Spalte,
  Terminierungstabelle, Nicht-Ziele, ...) hat eine Lücke sichtbar
  gemacht, die sonst durchgerutscht wäre. → Positivbefund, dokumentieren
  — das ist der Existenzbeweis für Formularzwang.
- **Prüfer fand's:** Interview hat's übersehen, Phase 2 hat's gefangen.
  → Prozess funktioniert; prüfen, ob der Meta-Prompt es *früher* hätte
  fangen können (billiger).
- **Durchgerutscht:** Eine stille Annahme oder ein Widerspruch hat es
  bis in die freigegebene Spec geschafft. → Schwerster Befund: Welcher
  Checklisten-Punkt hätte greifen müssen? Fehlt einer? → Review-
  Checkliste ändern.
- **Rollenbruch:** Der Prüfer hat selbst korrigiert statt gefragt; der
  Interviewer hat Annahmen erfunden statt `[OFFEN]` zu markieren; ein
  LLM ist aus seiner Rolle gefallen. → Prompt-Härtung.
- **Reibung:** Es ging weiter, aber zäh (Fragenkataloge trotz
  Eine-Frage-Regel, unübersetzter Jargon beim Kunden, Endlos-Spiegeln).
  → Gesprächsregeln nachschärfen.

**Abgabe:** `prozess.md`, finale `spec.md`, letztes Review-JSON,
Beobachtungsprotokoll — plus für jeden Befund vom Typ „Leitfaden-Lücke"
oder „Durchgerutscht" einen **konkreten Änderungsvorschlag als Diff**
am betroffenen Artefakt (welcher Absatz, welche neue Formulierung).
„Der Prompt sollte besser sein" ist kein Befund; „Modus B Schritt 4
braucht die Zusatzfrage X, weil im Turn 7 Y passierte" ist einer.

## Leitfragen für die Nachbesprechung

1. Welche eurer Befunde hätte eine *Spec des Prozesses* verhindert —
   und welche findet man prinzipiell nur durch einen Durchlauf?
2. Der Agenten-Prozess trennt Tests (deterministisch) von Evals
   (statistisch). Was ist beim *Prozess selbst* das Gegenstück zu
   Tests, was zu Evals?
3. „Stabiles früh, Volatiles spät" — was ist an der Werkzeugkette
   selbst der stabile Teil, was der volatile?
