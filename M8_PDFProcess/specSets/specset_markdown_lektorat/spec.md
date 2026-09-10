# Spezifikation: LLM-gestützte Korrektur OCR-erzeugter Markdown-Dokumente

**Status:** Final  
**Version:** 1.0  
**Datum:** 2026-09-08  
**Dokumenttyp:** Produktspezifikation / SDD-Spezifikation  
**Geltungsbereich:** Nachbearbeitung eines aus OCR-/Layouterkennung erzeugten Markdown-Destillats  
**Primärer Input:** `.md`  
**Primärer Output:** `<ursprungsname>_korr.md`  
**Review-Artefakt:** `<ursprungsname>_review.md`

---

## 1. Zweck

Das System soll Markdown-Dokumente nachbearbeiten, die von einer vorgelagerten OCR- und Dokumentlayout-Pipeline erzeugt wurden.

Die vorgelagerte Pipeline, insbesondere PDF-Verarbeitung, PP-DocLayout, PaddleOCR und Docling-Konvertierung, ist ausdrücklich **nicht Bestandteil dieses Moduls**.

Das Modul arbeitet in Version 1 vollständig unabhängig auf dem bereits erzeugten Markdown-Destillat.

Ziele sind:

1. OCR-bedingte Textfehler zu korrigieren;
2. Rechtschreibung und Grammatik zu korrigieren, sofern die beabsichtigte Formulierung mit ausreichender Sicherheit ableitbar ist;
3. fehlerhafte Markdown-Strukturen zu erkennen und gegebenenfalls zu reparieren;
4. Markdown-Tabellen auf syntaktische und strukturelle Konsistenz zu prüfen und gegebenenfalls zu reparieren;
5. OCR- oder layoutbedingte Duplikate und Fragmentierungen zu erkennen;
6. fehlerhafte Lesereihenfolgen dort zu korrigieren, wo das LLM eine ausreichend sichere Rekonstruktion vornehmen kann;
7. Bild- und Tabellenbeschriftungen zu erkennen und bei ausreichend sicherer Zuordnung strukturell korrekt anzuordnen;
8. geschützte Dokumentelemente unverändert zu erhalten;
9. unsichere Fälle unverändert zu lassen und nachvollziehbar in einem Markdown-Reviewbericht zu dokumentieren.

Das System ist ein **Dokument-Restaurierungs- und Korrekturwerkzeug**. Es ist kein System zur stilistischen Neufassung, inhaltlichen Modernisierung oder fachlichen Aktualisierung.

---

## 2. Systemgrenze

### 2.1 Bestandteil des Systems

Bestandteil sind:

- Laden einer bestehenden Markdown-Datei;
- strukturelle Analyse des Markdown-Dokuments;
- Aufteilung in geeignete Verarbeitungseinheiten;
- Kommunikation mit einem lokal in LM Studio bereitgestellten LLM;
- strukturierte Entgegennahme von LLM-Entscheidungen;
- formale Validierung der Modellantwort;
- kontrollierte Anwendung zulässiger Änderungen;
- Integritätsprüfung geschützter Elemente;
- Speicherung der korrigierten Markdown-Datei;
- Erstellung eines Markdown-Reviewberichts.

### 2.2 Nicht Bestandteil des Systems

Nicht Bestandteil sind:

- OCR;
- PDF-Rasterung;
- PP-DocLayout;
- PaddleOCR;
- erneute Docling-Konvertierung;
- erneute Layouterkennung am Original-PDF;
- zwingende Verwendung der vorhandenen Docling-JSON-Datei;
- zwingende Analyse der extrahierten Bilddateien;
- fachliches Fact-Checking;
- Aktualisierung historischer oder technischer Aussagen.

---

## 3. Grundprinzipien

### GP-001 — Quelltreue vor sprachlicher Eleganz

Die rekonstruierbare Bedeutung der Quelle hat Vorrang vor stilistischer Verbesserung.

### GP-002 — Erhaltung vor Rekonstruktion

Ist eine Korrektur nicht ausreichend sicher, bleibt der Quelltext unverändert.

### GP-003 — Keine freie Neugenerierung des Gesamtdokuments

Das LLM darf nicht die vollständige Markdown-Datei frei neu erzeugen.

Es liefert ausschließlich strukturierte Entscheidungen bzw. Edit-Vorschläge auf identifizierbare Dokumentbereiche.

### GP-004 — LLM als semantische Entscheidungsinstanz

Semantische und layoutlogische Entscheidungen werden vom LLM getroffen.

Dies betrifft insbesondere:

- Textrekonstruktion;
- Lesereihenfolge;
- Duplikaterkennung;
- Zuordnung von Abbildungsbeschriftungen;
- Zuordnung von Tabellenbeschriftungen;
- strukturelle Rekonstruktion beschädigter Tabellen.

### GP-005 — Python als formale Sicherheitsinstanz

Deterministischer Programmcode prüft ausschließlich formale, technische und integritätsbezogene Bedingungen.

Python darf keine eigene semantische oder layoutlogische Entscheidung gegen oder anstelle des LLM treffen.

### GP-006 — Unsicherheit ist ein gültiges Ergebnis

Das System muss ausdrücklich zulassen, dass ein Fall als `unresolved` eingestuft wird.

### GP-007 — Nachvollziehbarkeit

Jede automatisch angewendete Änderung muss im Reviewbericht nachvollziehbar dokumentiert werden.

### GP-008 — Validierung vor Finalisierung

Keine Änderung darf ungeprüft in das finale Ergebnis übernommen werden.

---

## 4. Eingabe und Ausgabe

### FR-001 — Eingabeformat

Das System akzeptiert eine Markdown-Datei als primären Input.

Beispiel:

`RegenEnergie.md`

### FR-002 — Quelldatei bleibt unverändert

Die Eingabedatei darf niemals überschrieben werden.

### FR-003 — Ausgabe-Dateiname

Für:

`<name>.md`

wird erzeugt:

`<name>_korr.md`

Beispiel:

`RegenEnergie.md` → `RegenEnergie_korr.md`

### FR-004 — Review-Dateiname

Zusätzlich wird erzeugt:

`<name>_review.md`

Beispiel:

`RegenEnergie.md` → `RegenEnergie_review.md`

### FR-005 — Ausgabeort

Standardmäßig werden beide Dateien im Verzeichnis der Eingabedatei gespeichert.

Ein alternativer Ausgabeordner darf konfigurierbar sein.

### FR-006 — Zeichencodierung

Die Ausgabe muss Unicode-sicher erfolgen.

Die konkrete Kodierungsstrategie wird in `plan.md` festgelegt.

---

## 5. Geschützte Dokumentelemente

### FR-010 — Bildreferenzen

Alle vorhandenen Markdown-Bildreferenzen sind geschützte Elemente.

Beispiel:

```md
![Image](RegenEnergie_artifacts/RegenEnergie_0005_07_image.png)
```

Die vollständige Bildreferenz muss literal unverändert erhalten bleiben.

Dies umfasst insbesondere:

- Markdown-Syntax;
- Alt-Text;
- Pfad;
- Dateiname;
- Dateiendung.

### FR-011 — Position von Bildreferenzen

Bildreferenzen werden in Version 1 **nicht verschoben**.

Auch dann, wenn eine fehlerhafte Lesereihenfolge vermutet wird, bleibt die Bildreferenz an ihrer ursprünglichen Position.

Eine Caption darf dagegen bei ausreichend sicherer LLM-Zuordnung relativ zur unveränderten Bildreferenz verschoben werden.

### FR-012 — Seitenumbrüche

Vorhandene Seitenumbruchmarker sind unveränderlich.

Beispiel:

```md
<!-- Seitenumbruch -->
```

Sie dürfen weder gelöscht, verändert noch neu formuliert werden.

### FR-013 — Position und Reihenfolge der Seitenumbrüche

Seitenumbruchmarker müssen in derselben Reihenfolge und an derselben logischen Dokumentgrenze erhalten bleiben.

### FR-014 — Integritätsprüfung

Vor erfolgreicher Finalisierung muss geprüft werden, dass:

- jede Bildreferenz der Quelle im Ergebnis vorhanden ist;
- jede Bildreferenz literal unverändert ist;
- jede Bildreferenz in derselben Reihenfolge vorkommt;
- jeder Seitenumbruchmarker vorhanden ist;
- jeder Seitenumbruchmarker literal unverändert ist;
- die Reihenfolge der Seitenumbruchmarker erhalten ist.

Ein Verstoß führt zu einem Validierungsfehler.

---

## 6. Textkorrektur

### FR-020 — Rechtschreibung

Offensichtliche OCR- und Rechtschreibfehler dürfen korrigiert werden.

Zulässige Fehlerklassen umfassen unter anderem:

- fehlende Zeichen;
- überzählige Zeichen;
- OCR-Zeichenverwechslungen;
- Umlaut-/Diakritika-Fehler;
- falsche Worttrennung;
- falsche Wortzusammenziehung;
- fehlerhafte Leerzeichen;
- fehlerhafte Satzzeichen.

### FR-021 — Grammatik

Grammatikalische Fehler dürfen korrigiert werden, wenn die intendierte grammatische Konstruktion ausreichend sicher rekonstruiert werden kann.

### FR-022 — Silbentrennungsartefakte

Durch Zeilenumbruch entstandene Worttrennungen dürfen repariert werden.

Beispiel:

```text
Energie-
versorgung
```

kann zu:

```text
Energieversorgung
```

werden, sofern der Bindestrich erkennbar kein lexikalischer Bestandteil ist.

### FR-023 — Fragmentrekonstruktion

Durch OCR, Spaltenlayout oder fehlerhafte Lesereihenfolge fragmentierte Sätze oder Absätze dürfen zusammengeführt werden, wenn das LLM die Rekonstruktion mit ausreichender Konfidenz bewertet.

### FR-024 — Semantische Erhaltung

Eine Korrektur darf die erkennbare fachliche Aussage des Ausgangstextes nicht verändern.

### FR-025 — Keine stilistische Modernisierung

Ein semantisch und grammatikalisch plausibler Originalsatz darf nicht allein deshalb geändert werden, weil das Modell eine elegantere, modernere oder knappere Formulierung bevorzugt.

### FR-026 — Keine externe Faktenkorrektur

Das System darf historische Werte, Gesetze, technische Angaben oder Terminologie nicht anhand heutigen Wissens aktualisieren.

Eine Änderung ist nur zulässig, wenn ein OCR-/Konvertierungsfehler rekonstruiert wird.

### FR-027 — Sprachwechsel als OCR-Indiz

Unerwartete fremdsprachige Fragmente innerhalb eines ansonsten konsistent deutschsprachigen Abschnitts dürfen als mögliches OCR-/Layout-Artefakt bewertet werden.

Sie dürfen nur dann ersetzt werden, wenn die ursprüngliche Aussage mit ausreichender Sicherheit rekonstruierbar ist.

---

## 7. Fehler- und Änderungsklassen

Jeder LLM-Vorschlag muss genau einer primären Fehlerklasse zugeordnet werden können.

Mindestens unterstützt werden:

- `orthografie`
- `grammatik`
- `ocr_zeichenfehler`
- `worttrennung`
- `satzfragment`
- `duplikat`
- `lesereihenfolge`
- `markdown`
- `tabelle`
- `abbildungsbeschriftung`
- `tabellenbeschriftung`
- `unklar`

Zusätzliche Klassen dürfen in `plan.md` vorgesehen werden, sofern sie rückwärtskompatibel sind.

---

## 8. Unsicherheit und Konfidenz

### FR-030 — Numerischer Konfidenz-Score

Jede semantisch relevante LLM-Entscheidung muss einen numerischen Konfidenz-Score im Bereich `[0.0, 1.0]` enthalten.

Der Score ist eine **Selbsteinschätzung des Modells**.

Er darf nicht als statistisch kalibrierte Wahrscheinlichkeit interpretiert werden.

### FR-031 — Diskrete Konfidenzklassen

Der numerische Rohscore wird durch deterministischen Programmcode in eine der folgenden Klassen abgebildet:

- `hoch`
- `mittel`
- `niedrig`

Das LLM selbst entscheidet nicht über die Klasse.

### FR-032 — Modellabhängige Kalibrierung

Die Grenzwerte zwischen den Klassen werden nicht willkürlich in dieser Spezifikation festgeschrieben.

Sie müssen anhand eines projektspezifischen Regressionstest-Korpus empirisch bestimmt werden.

Die Kalibrierung darf sich je nach eingesetztem Modell unterscheiden.

### FR-033 — Keine semantische Python-Nachbewertung

Python darf den vom LLM gelieferten semantischen Score nicht durch heuristische Layoutregeln ersetzen oder überschreiben.

Insbesondere unzulässig sind automatische semantische Scores auf Basis von:

- Zeilenabstand;
- Anzahl dazwischenliegender Blöcke;
- Nähe;
- Nummerierung;
- Seitenposition;
- vermuteter Leserichtung.

Solche Informationen dürfen Bestandteil des dem LLM bereitgestellten Kontexts sein, aber nicht als eigenständige semantische Entscheidungslogik in Python wirken.

### FR-034 — Explizites `unresolved`

Das LLM muss ausdrücklich `unresolved` als Entscheidung wählen können.

`unresolved` bedeutet:

> Auf Basis der verfügbaren Informationen ist keine ausreichend eindeutige Korrektur oder Zuordnung möglich.

### FR-035 — Konfidenz bei `unresolved`

Auch `unresolved` erhält einen Konfidenz-Score.

Eine hohe Konfidenz für `unresolved` bedeutet, dass das Modell die Mehrdeutigkeit selbst mit hoher Sicherheit erkannt hat.

### FR-036 — Ungeklärte Stellen

Bei `unresolved`:

- bleibt der betreffende Inhalt im korrigierten Markdown unverändert;
- wird keine strukturelle Änderung durchgeführt;
- wird der Fall im Markdown-Reviewbericht dokumentiert.

---

## 9. Änderungsrisikoklassen

### Klasse A — unveränderlich

Niemals verändern:

- Bildreferenzen;
- Seitenumbruchmarker.

### Klasse B — konservative Textkorrektur

Grundsätzlich automatisch anwendbar, sofern die später kalibrierte Mindestkonfidenz erreicht wird:

- Rechtschreibung;
- Grammatik;
- OCR-Zeichenfehler;
- Worttrennung;
- Interpunktion;
- eindeutige einfache Markdown-Syntaxfehler.

### Klasse C — strukturelle Korrektur

Nur bei einer hierfür gesondert festgelegten, konservativen Mindestkonfidenz automatisch anwendbar:

- Zusammenführung fragmentierter Sätze;
- Entfernung von OCR-Duplikaten;
- Neuordnung von Textfragmenten;
- Reparatur beschädigter Tabellen;
- Verschiebung von Abbildungsbeschriftungen;
- Verschiebung von Tabellenbeschriftungen.

### Klasse D — ungeklärt

Nicht verändern:

- semantisch mehrdeutige OCR-Fragmente;
- unklare Lesereihenfolge;
- mehrdeutige Caption-Zuordnung;
- mehrdeutige Tabellenstruktur;
- widersprüchliche Quellfragmente.

---

## 10. Duplikate und Lesereihenfolge

### FR-040 — Duplikaterkennung

Das LLM soll mögliche OCR-/Layout-bedingte Duplikate erkennen.

### FR-041 — Entfernung von Duplikaten

Text darf nur dann automatisch entfernt werden, wenn das LLM mit der für strukturelle Änderungen erforderlichen Mindestkonfidenz entscheidet, dass derselbe Quellinhalt mehrfach erkannt wurde.

### FR-042 — Beabsichtigte Wiederholungen

Inhaltlich beabsichtigte Wiederholungen dürfen nicht allein aufgrund textlicher Ähnlichkeit entfernt werden.

### FR-043 — Verschobene Fragmente

Das LLM darf erkennen, dass Textfragmente durch Spaltenlayout oder komplexe Seitengestaltung in einer fehlerhaften Reihenfolge stehen.

### FR-044 — Neuordnung

Eine Neuordnung darf nur erfolgen, wenn die für strukturelle Änderungen erforderliche Mindestkonfidenz erreicht wird.

Andernfalls bleibt die Reihenfolge unverändert.

---

## 11. Markdown-Struktur

### FR-050 — Markdown-Konsistenz

Das Ergebnisdokument muss weiterhin als Markdown verarbeitbar sein.

### FR-051 — Überschriften

Bestehende Überschriftenebenen sollen grundsätzlich erhalten bleiben.

Offensichtliche OCR-/Konvertierungsfehler in der Markdown-Überschriftensyntax dürfen korrigiert werden.

### FR-052 — Listen

Beschädigte Listen dürfen normalisiert werden, wenn das LLM die intendierte Struktur ausreichend sicher rekonstruiert.

### FR-053 — Formeln

Vorhandenes mathematisches Markup wird konservativ behandelt.

Mathematische Umformulierungen aus stilistischen Gründen sind unzulässig.

### FR-054 — HTML-Kommentare

Vorhandene HTML-Kommentare werden grundsätzlich als strukturell relevant behandelt.

Geschützte Kommentare, insbesondere Seitenumbrüche, dürfen nicht verändert werden.

### FR-055 — Minimale Veränderung

Markdown-Formatierungen, die bereits syntaktisch plausibel sind, sollen nicht lediglich aus ästhetischen oder Formatierungspräferenzen neu geschrieben werden.

---

## 12. Tabellen

### FR-060 — Tabellenerkennung

Vorhandene Markdown-Tabellen sollen als eigene Verarbeitungseinheiten erkannt werden.

### FR-061 — Zu prüfende Tabellenprobleme

Mindestens berücksichtigt werden:

- fehlende oder beschädigte Trennerzeile;
- inkonsistente Spaltenzahl;
- beschädigte `|`-Trennzeichen;
- fragmentierte Zeilen;
- verschobene Zellinhalte;
- OCR-bedingte Zeilenverdopplungen;
- vermischte Tabellen- und Fließtextbestandteile.

### FR-062 — Semantische Tabellenreparatur

Die Rekonstruktion der intendierten Tabellenstruktur ist eine LLM-Entscheidung.

Python darf nur prüfen, ob eine vorgeschlagene Zieltabelle formal als Markdown-Tabelle interpretierbar ist.

### FR-063 — Zellinhalt

Zellinhalte unterliegen denselben konservativen Textkorrekturregeln wie Fließtext.

Fehlende Werte dürfen nicht erfunden werden.

### FR-064 — Mehrdeutige Tabellenstruktur

Kann das LLM die Tabellenstruktur nicht mit ausreichender Konfidenz rekonstruieren:

- bleibt die Quellrepräsentation unverändert;
- wird der Fall im Reviewbericht dokumentiert.

---

## 13. Abbildungen und Abbildungsbeschriftungen

### FR-070 — Abbildungsinventar

Jede Markdown-Bildreferenz wird intern als eigenes Element mit stabiler Verarbeitungs-ID erfasst.

Diese ID wird standardmäßig nicht in das Ergebnis-Markdown geschrieben.

### FR-071 — Caption-Kandidaten

Textpassagen, die als Abbildungsbeschriftungen infrage kommen, sollen erkannt werden.

Typische sprachliche Formen können unter anderem sein:

- `Abb.`;
- `Abbildung`;
- Abbildungsnummern;
- nummerierte Unterabbildungen;
- beschreibende Textzeilen in unmittelbarem oder mittelbarem Umfeld einer Bildreferenz.

Diese Muster sind Hinweise für das LLM, keine deterministischen Zuordnungsregeln.

### FR-072 — Alleinige LLM-Zuordnung

Ob eine Caption zu einer Bildreferenz gehört, entscheidet ausschließlich das LLM anhand des verfügbaren Dokumentkontexts.

Python darf keine eigene Caption-Bild-Zuordnung erzeugen.

### FR-073 — Verfügbarer Kontext

Dem LLM dürfen zur Entscheidung unter anderem bereitgestellt werden:

- lokale Textnachbarschaft;
- umgebende Überschriften;
- Seitenumbruchmarker;
- Reihenfolge benachbarter Bilder;
- erkennbare Abbildungsnummerierung;
- Referenzen im Fließtext;
- konkurrierende Caption-Kandidaten;
- benachbarte Tabellen oder andere strukturelle Elemente.

Diese Informationen sind **Kontext**, keine deterministische Bewertungsmatrix.

### FR-074 — Caption-Verschiebung

Wenn das LLM eine Caption einer Bildreferenz mit ausreichender, für strukturelle Änderungen kalibrierter Konfidenz zuordnet, darf die Caption so verschoben werden, dass die Zuordnung im Markdown eindeutig wird.

Die Bildreferenz selbst bleibt an ihrer ursprünglichen Position.

### FR-075 — Keine Bildinhaltserkennung in Version 1

Der tatsächliche Inhalt der Bilddatei wird in Version 1 nicht zur Caption-Zuordnung analysiert.

### FR-076 — Mehrdeutige Caption-Zuordnung

Bei `unresolved` oder nicht ausreichender Konfidenz:

- wird keine Caption verschoben;
- bleibt der vorhandene Markdown-Inhalt unverändert;
- wird die Mehrdeutigkeit im Reviewbericht dokumentiert.

### FR-077 — Mehrere Bilder / mehrteilige Captions

Das System muss zulassen, dass:

- eine Caption mehrere unmittelbar zusammengehörige Bilder beschreibt;
- eine Caption Unterabbildungen enthält;
- mehrere Caption-Kandidaten konkurrieren;
- mehrere Bilder ohne eindeutig rekonstruierbare Beschriftung auftreten.

Es darf keine künstliche 1:1-Beziehung erzwungen werden.

---

## 14. Tabellenbeschriftungen

### FR-080 — Caption-Kandidaten

Textpassagen mit Formen wie:

- `Tabelle`;
- `Tab.`;
- Tabellennummern;
- beschreibenden Tabellenüberschriften oder -unterschriften

dürfen als Kandidaten betrachtet werden.

### FR-081 — Alleinige LLM-Zuordnung

Die Zuordnung einer Tabellenbeschriftung zu einer Tabelle ist eine semantische LLM-Entscheidung.

Python darf keine eigene semantische Zuordnung anhand von Distanz- oder Nummerierungsheuristiken treffen.

### FR-082 — Caption-Verschiebung

Wird eine Zuordnung mit ausreichender struktureller Mindestkonfidenz getroffen, darf die Beschriftung an die zugehörige Tabelle herangerückt werden.

### FR-083 — Mehrdeutigkeit

Bei `unresolved` oder nicht ausreichender Konfidenz bleibt die bestehende Anordnung unverändert und wird im Reviewbericht dokumentiert.

---

## 15. LLM-Vertrag

### FR-090 — Kein direkter Dateizugriff

Das LLM darf Quelle und Zieldatei nicht direkt schreiben oder verändern.

### FR-091 — Strukturierte Ausgabe

Das LLM muss maschinenlesbare Änderungsvorschläge liefern, die einem vordefinierten Schema entsprechen.

### FR-092 — Keine freie Markdown-Rückgabe als Primärergebnis

Eine frei generierte Gesamtfassung des Dokuments darf nicht unmittelbar als Ergebnisdatei verwendet werden.

### FR-093 — Zielreferenz

Jede Änderung muss sich auf deterministisch identifizierbare Quellbereiche oder Block-IDs beziehen.

### FR-094 — Source-Match

Vor Anwendung einer Änderung muss technisch geprüft werden, dass sich der adressierte Quellbereich seit der Analyse nicht verändert hat.

### FR-095 — Mindestfelder eines Vorschlags

Ein strukturierter Vorschlag muss mindestens enthalten:

- Ziel-ID bzw. Ziel-IDs;
- Fehler-/Änderungskategorie;
- Entscheidungsart;
- vorgeschlagene Änderung oder Operation;
- numerischen Konfidenz-Score;
- kurze Begründung.

### FR-096 — Entscheidungszustände

Mindestens folgende Zustände müssen möglich sein:

- Änderung anwenden;
- unverändert lassen;
- `unresolved`.

Weitere operationsspezifische Zustände dürfen im Schema vorgesehen werden.

### FR-097 — Whitelist

Nur explizit definierte Änderungsoperationen dürfen vom Python-Code ausgeführt werden.

Unbekannte Operationen werden verworfen.

### FR-098 — Schemaerzwungene Antwort

Sofern das gewählte Modell und LM Studio dies unterstützen, muss die Antwort über Structured Output / JSON Schema erzwungen werden.

Die konkrete Schema- und Pydantic-Definition gehört in `plan.md`.

### FR-099 — Schemaerfüllung ist keine semantische Validierung

Eine formal gültige Modellantwort gilt nicht automatisch als inhaltlich korrekt.

Die inhaltliche Vertrauensentscheidung wird über Modellkonfidenz, Kalibrierung und die für die jeweilige Änderungsklasse definierte Anwendungspolitik gesteuert.

---

## 16. Zuständigkeit von Python

Python darf deterministisch prüfen:

- Schema-Gültigkeit;
- Datentypen;
- Vorhandensein referenzierter Block-IDs;
- Source-Match;
- Bereichsgrenzen;
- erlaubte Operationstypen;
- Erhalt geschützter Elemente;
- Vollständigkeit der Verarbeitung;
- formale Markdown-Struktur;
- formale Tabellenstruktur nach einer Änderung;
- korrekte Dateinamen und Dateiausgabe.

Python darf **nicht** eigenständig entscheiden:

- welche Caption semantisch zu welchem Bild gehört;
- welche Tabellenbeschriftung semantisch zu welcher Tabelle gehört;
- welche Lesereihenfolge in einem chaotischen Layout „menschlich richtig“ ist;
- ob zwei ähnliche Passagen inhaltlich echte Duplikate sind;
- wie ein semantisch beschädigter Satz rekonstruiert werden soll;
- welche Tabellenzelle semantisch zu welcher Spalte gehört.

---

## 17. Verarbeitungsphasen

Die logische Verarbeitung umfasst mindestens:

1. Laden der Quelldatei;
2. Ermitteln und Sichern geschützter Elemente;
3. strukturelle Analyse des Markdown-Dokuments;
4. Vergabe stabiler interner Block-IDs;
5. Bildung geeigneter Verarbeitungseinheiten;
6. LLM-gestützte Textkorrektur;
7. LLM-gestützte strukturelle Analyse;
8. Validierung der strukturierten Modellantwort;
9. Mapping des Roh-Konfidenz-Scores auf die kalibrierte Klasse;
10. Entscheidung gemäß Änderungsklasse und Konfidenzpolicy;
11. kontrollierte Anwendung freigegebener Änderungen;
12. erneute formale Markdown-/Tabellenprüfung;
13. Integritätsprüfung geschützter Elemente;
14. Erzeugung von `<name>_korr.md`;
15. Erzeugung von `<name>_review.md`.

Diese Spezifikation legt noch keine konkrete Python-Klassen-, Modul- oder Notebook-Struktur fest.

---

## 18. Kontextstrategie

### FR-100 — Ausreichender Kontext

Jede LLM-Entscheidung muss ausreichend umgebenden Kontext erhalten, um die Aufgabe sinnvoll beurteilen zu können.

### FR-101 — Überlappende Verarbeitung

Verarbeitungseinheiten dürfen sich kontextuell überlappen.

Ziel ist, dass Absatz-, Satz-, Tabellen- oder Caption-Beziehungen nicht durch künstliche Chunk-Grenzen verloren gehen.

### FR-102 — Aufgabenspezifische Kontextbreite

Unterschiedliche Aufgaben dürfen unterschiedliche Kontextgrößen verwenden.

Strukturelle Aufgaben benötigen typischerweise mehr Kontext als reine Rechtschreibkorrekturen.

### FR-103 — Gesamtdatei nicht zwingend ein Prompt

Das System darf nicht voraussetzen, dass das gesamte Dokument in einer einzigen Modellanfrage verarbeitet wird.

### FR-104 — Kontextverlust vermeiden

Chunking darf keine geschützten Elemente, Tabellen oder zusammengehörige Strukturblöcke technisch zerschneiden, sofern dies vermeidbar ist.

---

## 19. Anwendungspolitik der Konfidenz

### FR-110 — Getrennte Schwellen nach Risikoklasse

Textkorrekturen und strukturelle Änderungen dürfen unterschiedliche Mindestschwellen besitzen.

### FR-111 — Strukturelle Änderungen konservativer

Für strukturelle Änderungen muss die automatische Anwendung konservativer kalibriert sein als für einfache orthografische Korrekturen.

### FR-112 — Schwellenwerte aus Evaluation

Konkrete numerische Grenzwerte werden erst nach Evaluation der Kandidatenmodelle auf dem projektspezifischen Regressionstest-Korpus festgelegt.

### FR-113 — Mittlere Konfidenz

Änderungen mit mittlerer Konfidenz werden standardmäßig nicht automatisch angewendet und im Reviewbericht ausgewiesen.

### FR-114 — Niedrige Konfidenz

Änderungen mit niedriger Konfidenz werden nicht angewendet.

### FR-115 — `unresolved`

`unresolved` führt grundsätzlich zu keiner Änderung am korrigierten Markdown.

---

## 20. Validierung

### FR-120 — Validierungsgate

Die Ergebnisdatei darf erst nach erfolgreicher formaler Validierung finalisiert werden.

### FR-121 — Geschützte Elemente

Alle geschützten Elemente werden gegen die Quelle geprüft.

### FR-122 — Markdown-Struktur

Durch Änderungen entstandene formale Markdown-Fehler müssen erkannt werden.

### FR-123 — Tabellen

Nach einer Tabellenänderung wird mindestens geprüft:

- Parsebarkeit;
- konsistente Spaltenzahl;
- gültige Trennerstruktur.

Diese Prüfung bewertet nicht die semantische Richtigkeit der rekonstruierten Zellzuordnung.

### FR-124 — Keine stille Reparatur durch Validatoren

Ein Validator darf keine semantisch relevanten Änderungen stillschweigend selbst durchführen.

### FR-125 — Nicht-stille Fehler

Validierungsfehler müssen sichtbar protokolliert werden.

Ein fehlgeschlagener Lauf darf nicht als erfolgreich ausgegeben werden.

---

## 21. Markdown-Reviewbericht

### FR-130 — Format

Das primäre Audit- und Review-Artefakt ist Markdown.

Dateiname:

`<name>_review.md`

### FR-131 — Ziel

Der Reviewbericht soll einem Menschen ermöglichen, nachvollziehen zu können:

- was geändert wurde;
- warum es geändert wurde;
- mit welcher Modellkonfidenz;
- welche Fälle nicht geändert wurden;
- welche strukturellen Entscheidungen getroffen wurden.

### FR-132 — Mindeststruktur

Der Bericht muss mindestens enthalten:

1. Laufübersicht;
2. verwendetes Modell;
3. Policy-/Skill-Version;
4. angewendete Textkorrekturen;
5. angewendete strukturelle Änderungen;
6. ungeklärte Fälle;
7. nicht angewendete Vorschläge mittlerer/niedriger Konfidenz;
8. Validierungsstatus;
9. Integritätsstatus der geschützten Elemente.

### FR-133 — Eintrag je Änderung

Für eine Änderung sollen mindestens dokumentiert werden:

- Ziel-ID oder Position;
- Kategorie;
- Originalausschnitt;
- korrigierter Ausschnitt bzw. Operation;
- Konfidenz-Score;
- abgeleitete Konfidenzklasse;
- kurze Modellbegründung.

### FR-134 — Strukturelle Änderungen

Jede automatisch angewendete strukturelle Änderung muss im Reviewbericht erscheinen.

### FR-135 — Ungeklärte Stellen

Ungeklärte Stellen bleiben im korrigierten Markdown unverändert und werden ausschließlich im Reviewbericht erläutert.

### FR-136 — Keine Audit-Kommentare im Ergebnistext

Das korrigierte Markdown darf standardmäßig keine künstlichen Review-Kommentare, Warnmarker oder LLM-Metadaten enthalten.

---

## 22. Fehlerverhalten

### FR-140 — LM Studio nicht erreichbar

Ist der konfigurierte LM-Studio-Endpunkt nicht erreichbar:

- bleibt die Quelldatei unverändert;
- wird kein unvollständiges Ergebnis als erfolgreich finalisiert;
- wird ein eindeutiger Fehler ausgegeben.

### FR-141 — Ungültige strukturierte Antwort

Eine Modellantwort, die nicht dem erwarteten Schema entspricht, darf keine Dokumentänderung auslösen.

### FR-142 — Unbekannte Operation

Eine unbekannte oder nicht erlaubte Operation wird verworfen und im Review-/Fehlerkontext protokolliert.

### FR-143 — Teilverarbeitung

Ein abgebrochener oder unvollständiger Lauf muss als solcher erkannt werden.

### FR-144 — Integritätsverletzung

Wird ein geschütztes Element verändert oder verloren, darf keine erfolgreiche Finalisierung erfolgen.

---

## 23. Modellunabhängigkeit

### FR-150 — Konfigurierbares Modell

Das konkrete Modell muss konfigurierbar sein.

Die Verarbeitungslogik darf nicht fest an eine einzelne Modell-ID gekoppelt sein.

### FR-151 — LM Studio

Version 1 unterstützt lokal bereitgestellte Modelle über LM Studio.

### FR-152 — Evaluationskandidaten

Für die erste Evaluation sind insbesondere vorgesehen:

- **Gemma 4 12B Unified**
- **Qwen3.8-27B**

Diese Einträge definieren Evaluationskandidaten und keine dauerhafte technische Abhängigkeit.

### FR-153 — Modellvergleich

Die Auswahl des Produktionsmodells erfolgt anhand des projektspezifischen Regressionstest-Korpus.

Allgemeine Benchmarks allein sind nicht ausreichend.

### FR-154 — Zu evaluierende Fähigkeiten

Mindestens zu prüfen sind:

- deutsche OCR-Korrektur;
- konservative semantische Rekonstruktion;
- Befolgung restriktiver Edit-Regeln;
- Structured Output;
- Umgang mit langen Kontexten;
- Tabellenrekonstruktion;
- Caption-/Bild-Zuordnung aus Textkontext;
- Caption-/Tabellen-Zuordnung;
- Erkennung von Mehrdeutigkeit;
- sinnvolles `unresolved`-Verhalten;
- Stabilität der Konfidenz-Scores;
- Reproduzierbarkeit bei gleichen Inferenzparametern.

---

## 24. Regressionstest-Korpus

### FR-160 — Festes Testkorpus

Vor Festlegung eines Produktionsmodells muss ein kleines, versioniertes Regressionstest-Korpus erstellt werden.

### FR-161 — Repräsentative Fehlerklassen

Das Korpus enthält mindestens Fälle für:

- fehlerfreien deutschen Fließtext;
- leichte OCR-Fehler;
- schwere OCR-Fehler;
- Silbentrennung;
- fehlerhafte Wortzusammenziehung;
- vermischte Spalten;
- Duplikate;
- fragmentierte Sätze;
- Markdown-Tabellen;
- beschädigte Tabellen;
- Abbildungsbeschriftungen;
- Tabellenbeschriftungen;
- Seitenumbrüche;
- mehrere konkurrierende Caption-Kandidaten;
- mehrere Bilder mit gemeinsamer Caption;
- absichtlich nicht eindeutig lösbare Fälle.

### FR-162 — Erwartungsdefinition je Testfall

Jeder Testfall soll enthalten:

- Input;
- geschützte Elemente;
- erlaubte Änderungen;
- verbotene Änderungen;
- erwartetes Ergebnis, sofern eindeutig;
- erwartetes `unresolved`, sofern nicht eindeutig.

### FR-163 — Kalibrierung

Das gleiche Korpus wird verwendet, um das Mapping von numerischen LLM-Konfidenz-Scores auf die Klassen `hoch`, `mittel` und `niedrig` empirisch zu kalibrieren.

### FR-164 — Modellabhängige Schwellen

Für unterschiedliche Modelle dürfen unterschiedliche Scoregrenzen entstehen.

### FR-165 — Regression

Änderungen an:

- Modell;
- Quantisierung;
- Prompt;
- Skill;
- Schema;
- Inferenzparametern;
- Chunking-/Kontextstrategie

müssen gegen das Regressionstest-Korpus prüfbar sein.

---

## 25. Qualitätsprioritäten

Das System optimiert in folgender Reihenfolge:

1. keine Zerstörung von Quellinformation;
2. vollständiger Erhalt geschützter Elemente;
3. keine erfundenen Inhalte;
4. semantische Quelltreue;
5. korrektes Erkennen von Unsicherheit;
6. korrekte Rekonstruktion von OCR-Fehlern;
7. korrekte Lesereihenfolge;
8. korrekte Markdown-Struktur;
9. korrekte Tabellenstruktur;
10. korrekte Caption-Zuordnung;
11. Rechtschreibung und Grammatik;
12. stilistische Konsistenz.

Ein niedriger priorisiertes Ziel darf ein höher priorisiertes Ziel nicht verletzen.

---

## 26. Akzeptanzkriterien

### AC-001 — Quelle unverändert

Nach einem Lauf ist die Eingabedatei unverändert.

### AC-002 — Korrekte Ausgabedatei

`beispiel.md` erzeugt standardmäßig:

`beispiel_korr.md`

### AC-003 — Review-Datei

`beispiel.md` erzeugt standardmäßig:

`beispiel_review.md`

### AC-004 — Bildreferenzen literal erhalten

Jede Bildreferenz der Quelle ist im Ergebnis literal unverändert vorhanden.

### AC-005 — Bildreferenzen nicht verschoben

Die Reihenfolge und Position der Bildreferenzen relativ zu den geschützten Seitenstrukturen bleibt erhalten.

### AC-006 — Seitenumbrüche erhalten

Jeder Seitenumbruchmarker ist literal unverändert und in derselben Reihenfolge vorhanden.

### AC-007 — Kein LLM-Dateischreiben

Das LLM besitzt keinen direkten Schreibpfad auf Quelle oder Zielartefakt.

### AC-008 — Schemafehler blockiert Änderung

Eine ungültige LLM-Antwort kann keine Änderung am Ergebnis auslösen.

### AC-009 — Eindeutiger OCR-Fehler

Ein definierter Testfall mit eindeutigem OCR-Fehler wird erwartungsgemäß korrigiert.

### AC-010 — Mehrdeutiger OCR-Fehler

Ein absichtlich mehrdeutiger beschädigter Text wird nicht frei rekonstruiert.

### AC-011 — `unresolved`

Ein absichtlich nicht eindeutig lösbarer Fall kann explizit als `unresolved` ausgegeben werden.

### AC-012 — Reparierbare Tabelle

Eine eindeutig rekonstruierbare beschädigte Tabelle kann korrigiert werden, ohne vorhandene Information zu erfinden.

### AC-013 — Mehrdeutige Tabelle

Eine nicht eindeutig rekonstruierbare Tabelle bleibt unverändert und erscheint im Reviewbericht.

### AC-014 — Eindeutige Abbildungsbeschriftung

Eine mit hoher kalibrierter Konfidenz zugeordnete Caption kann relativ zur unveränderten Bildreferenz korrekt positioniert werden.

### AC-015 — Mehrdeutige Abbildungsbeschriftung

Bei nicht ausreichender Konfidenz oder `unresolved` wird keine Caption-Verschiebung vorgenommen.

### AC-016 — Tabellenbeschriftung

Eine ausreichend sicher zugeordnete Tabellenbeschriftung kann an die zugehörige Tabelle herangerückt werden.

### AC-017 — Reviewvollständigkeit

Jede automatisch angewendete strukturelle Änderung wird im Reviewbericht dokumentiert.

### AC-018 — Ungeklärter Inhalt unverändert

Ein ungeklärter Quellabschnitt bleibt im korrigierten Markdown unverändert.

### AC-019 — Integritätsfehler blockiert Finalisierung

Ein Verlust oder eine Veränderung eines geschützten Elements verhindert die erfolgreiche Finalisierung.

### AC-020 — Keine semantische Python-Heuristik

Für Caption-Zuordnung, Lesereihenfolge, Duplikaterkennung oder Textrekonstruktion existiert keine Python-Heuristik, die eigenständig eine semantische Entscheidung erzwingt.

---

## 27. Skill-/Policy-Anforderungen

### FR-170 — Externe Korrekturpolicy

Die inhaltlichen Regeln für das LLM sollen außerhalb des Notebook-Fließcodes versionierbar sein.

### FR-171 — Skill-Inhalt

Der Skill bzw. die Policy soll mindestens enthalten:

- Rolle und Ziel des Modells;
- Priorität der Quelltreue;
- erlaubte Änderungen;
- verbotene Änderungen;
- Umgang mit geschützten Elementen;
- Definition von `unresolved`;
- Regeln zur Confidence-Selbsteinschätzung;
- Umgang mit Tabellen;
- Umgang mit Captions;
- Beispiele für zulässige und unzulässige Rekonstruktionen;
- Verpflichtung zur strukturierten Antwort.

### FR-172 — Versionsangabe

Die verwendete Skill-/Policy-Version muss im Reviewbericht dokumentiert werden.

---

## 28. Forschungs- und Architekturleitplanken

Für `plan.md` sind folgende, durch aktuelle Dokumentation gestützte Leitplanken zu berücksichtigen:

1. LM Studio unterstützt schemaerzwungene strukturierte JSON-Ausgaben über JSON Schema.
2. Schemaerfüllung stellt Formtreue sicher, nicht semantische Korrektheit.
3. Die Anwendung von Edits soll deterministisch durch Python erfolgen.
4. Das LLM soll keine direkte Dateischreibverantwortung erhalten.
5. Das System soll modellunabhängig bleiben.
6. Die Modelleignung und die Konfidenzschwellen sollen anhand des projektspezifischen Testkorpus bestimmt werden.
7. Zusätzliche Provenienz- und Layoutinformationen können später als Kontext für das LLM ergänzt werden, ohne die Kernarchitektur von Version 1 zu verändern.

---

## 29. Optionale spätere Erweiterungen

### EX-001 — Docling-JSON als optionale Evidenzquelle

Eine spätere Version darf zusätzlich die vorhandene Docling-JSON-Datei einlesen.

Sie kann dem LLM ergänzende Informationen bereitstellen, beispielsweise:

- Seitennummer;
- Bounding Box;
- Character Span;
- erkannte Elementtypen;
- Provenienz;
- Picture-/Table-Strukturen.

Diese Daten dienen als zusätzlicher Kontext für das LLM.

Sie begründen keine eigenständige semantische Python-Heuristik.

### EX-002 — Multimodale Bildanalyse

Eine spätere Version darf Bilddateien zusätzlich einem multimodalen Modell bereitstellen.

Dies kann insbesondere bei Caption-Zuordnung hilfreich sein.

Die Funktion muss explizit aktiviert werden und gehört nicht zu Version 1.

### EX-003 — Original-PDF als zusätzliche Evidenz

Eine spätere Erweiterung darf das Original-PDF oder daraus gerenderte Seitenbilder zusätzlich verwenden.

Das Markdown bleibt das primäre zu korrigierende Artefakt.

### EX-004 — Human-in-the-loop

Eine spätere Version darf mittlere oder ungeklärte Fälle interaktiv zur Bestätigung vorlegen.

### EX-005 — Maschinenlesbares Auditformat

Zusätzlich zum verpflichtenden Markdown-Reviewbericht kann später optional JSON oder JSONL als maschinenlesbares Auditformat erzeugt werden.

---

## 30. Bewusst akzeptierte Restrisiken

### RR-001 — Hochkonfident falsche LLM-Entscheidung

Ein LLM kann eine falsche semantische Entscheidung mit hoher Konfidenz treffen.

Dieses Risiko kann durch formale Python-Prüfungen nicht vollständig ausgeschlossen werden.

Gegenmaßnahmen sind:

- projektspezifische Kalibrierung;
- konservative Schwellenwerte;
- explizites `unresolved`;
- Regressionstests;
- vollständige Protokollierung struktureller Änderungen;
- Vergleich mehrerer Modelle.

### RR-002 — Fehlende Bildinhaltsinformation

Version 1 entscheidet Caption-Zuordnungen ohne tatsächliche Betrachtung des Bildinhalts.

Dadurch können Fälle prinzipiell unentscheidbar bleiben.

Solche Fälle müssen unverändert bleiben.

### RR-003 — Informationsverlust der vorgelagerten Pipeline

Das Markdown-Destillat kann Informationen verloren haben, die im PDF oder im Docling-JSON noch vorhanden sind.

Version 1 versucht nicht, nicht vorhandene Evidenz zu erfinden.

---

## 31. Definition of Done für Version 1 der Spezifikation

Die Spezifikation gilt als abgeschlossen, wenn:

- Input und Output eindeutig definiert sind;
- geschützte Elemente eindeutig definiert sind;
- Bildreferenzen als positionsstabil festgelegt sind;
- ungeklärte Stellen im korrigierten Markdown unverändert bleiben;
- der Markdown-Reviewbericht als verbindliches Audit-Artefakt festgelegt ist;
- die semantische Entscheidungsverantwortung des LLM klar von der formalen Prüfverantwortung des Python-Codes getrennt ist;
- das Confidence-Modell spezifiziert ist;
- `unresolved` spezifiziert ist;
- Akzeptanzkriterien testbar sind;
- das Regressionstest-Korpus konzeptionell definiert ist;
- keine offenen Spezifikationsentscheidungen für Version 1 verbleiben.

**Status dieser Bedingungen:** erfüllt.

---

## 32. Recherchegrundlage

Stand der Recherche: 2026-09-08.

### LM Studio — Structured Output

LM Studio dokumentiert schemaerzwungene strukturierte Ausgaben über JSON Schema für den OpenAI-kompatiblen `/v1/chat/completions`-Endpunkt.

Quelle:  
https://lmstudio.ai/docs/developer/openai-compat/structured-output

### LM Studio — Entwicklerdokumentation

LM Studio stellt lokale API-Endpunkte und Werkzeuge zur programmatischen Modellnutzung bereit.

Quelle:  
https://lmstudio.ai/docs/developer

### Docling — Provenienz und Bounding Boxes

Das Docling-Dokumentmodell enthält für extrahierte Elemente Provenienzangaben mit Seitennummer, Bounding Box und Character Span.

Quelle:  
https://docling-project.github.io/docling/reference/docling_document/

### GROBID — Figuren, Tabellen und Referenzmarker

GROBID behandelt Figuren, Tabellen, Captions und Verweise als eigene logische Dokumentstrukturen und zeigt damit den Stellenwert von Layout-/Strukturkontext für Dokumentrekonstruktion.

Quelle:  
https://grobid.readthedocs.io/en/latest/training/fulltext/

### Gemma 4 12B Unified

Google dokumentiert Gemma 4 12B Unified als Modell der Gemma-4-Familie.

Quellen:  
https://ai.google.dev/gemma/docs/releases  
https://ai.google.dev/gemma/docs/core/model_card_4

### Qwen3.8-27B

Qwen dokumentiert `Qwen/Qwen3.8-27B` als offizielles Modell der Qwen3.8-Familie.

Quelle:  
https://github.com/QwenLM/Qwen3.8

---

## 33. Übergang zu `plan.md`

Die technische Umsetzung wird in `plan.md` spezifiziert.

Dort sind insbesondere festzulegen:

- Notebook- und Modulstruktur;
- Python-Paketstruktur;
- LM-Studio-API-Anbindung;
- OpenAI-kompatibler Client versus LM-Studio-SDK;
- Pydantic-/JSON-Schema;
- interne Blockrepräsentation;
- Edit-Operationsschema;
- Chunking- und Kontextstrategie;
- Retry-/Fehlerstrategie;
- Konfidenzkalibrierung;
- Regressionstest-Aufbau;
- Markdown-Parser und Validierung;
- Aufbau des Skills bzw. der Policy-Dateien;
- Reviewbericht-Generator;
- Modellbenchmark für Gemma 4 12B Unified und Qwen3.8-27B;
- konkrete Inferenzparameter;
- Logging und Reproduzierbarkeit.


---

## Ergänzung v1.1 — Resumierbare Chunk-Verarbeitung

### FR-180 — Persistenz nach jedem Chunk
Nach jedem erfolgreich analysierten, validierten und angewendeten Chunk müssen das korrigierte Markdown und der Reviewbericht atomar aktualisiert werden.

### FR-181 — Maschinenlesbarer Checkpoint
Der Laufzustand muss in `data/interim/lektorat/<dok>/checkpoint.json` persistiert werden. Er enthält mindestens Quell-Hash, Modell, aktuellen Pass, nächsten Chunk, abgeschlossene Chunk-IDs, Hash des korrigierten Zwischenstands, Status sowie die für den aktuellen Pass bereits freigegebenen Edits.

### FR-182 — Wiederaufnahme
Ein unterbrochener Lauf muss beim ersten noch nicht erfolgreich abgeschlossenen Chunk fortgesetzt werden können. Die Wiederaufnahme darf nur erfolgen, wenn Quell-Hash, Modell und persistierter Zwischenstand zum Checkpoint passen.

### FR-183 — Stabiler Pass-Ausgang
Innerhalb eines Verarbeitungspasses werden alle Chunk-Entscheidungen gegen einen eingefrorenen Pass-Ausgang erzeugt. Nach jedem erfolgreichen Chunk werden die bis dahin freigegebenen Edits erneut auf diesen Ausgang angewandt. Erst der nächste Pass erhält den neuen korrigierten Stand als Ausgang.

### FR-184 — Kompakte LLM-Ausgabe
Das LLM soll ausschließlich tatsächliche Änderungen und echte `unresolved`-Fälle zurückgeben. Unveränderte Blöcke müssen nicht einzeln als `keep_unchanged` ausgegeben werden.
