# spec.md — Dokumentenaufbereitung

**Stand:** 07.09.2026
**Art:** fachliche Spezifikation. Kein Technikstack, keine Bibliotheken, kein
Code. Wie etwas umgesetzt wird, steht in der `plan.md`; in welcher Reihenfolge,
in der `tasks.md`.

---

## 1. Zweck

Ein Verfahren, das beliebige PDF-Dokumente so aufbereitet, dass das Ergebnis für
Menschen lesbar und für unbekannte Abnehmer weiterverarbeitbar ist.

**Lesbar** heißt: Wer die erzeugte Ausgabefassung liest, erkennt Gliederung,
Fließtext, Tabellen, Abbildungen und Fundstellen, ohne das Original danebenlegen
zu müssen.

**Weiterverarbeitbar** heißt: Das Ergebnis liegt in einer verbreiteten,
dokumentierten Form vor, sodass ein Abnehmer, dessen Anforderungen heute nicht
bekannt sind, es ohne Sonderwissen über dieses Verfahren verwenden kann.

---

## 2. Ausgangsannahme

Über die Qualität eines eingehenden Dokuments lässt sich nichts voraussetzen. Der
maßgebliche Fall ist nicht das saubere, digital gesetzte Dokument, sondern eine
einfarbige Rasterabbildung, schief eingezogen, mit ungleichmäßiger Helligkeit,
mit einer Textebene, die nur stellenweise vorhanden und dort fehlerhaft ist, und
mit Textbestandteilen, die als Grafik gesetzt sind und in keiner Textebene
auftauchen.

Daraus folgt fachlich: **Die Bildebene der Seite ist die einzige Quelle, auf die
sich das Verfahren stützen darf.** Eine vorhandene Textebene ist kein Zeuge,
weder als Quelle noch als Gegenprobe, weil sie genau in den Fällen versagt, in
denen ihre Aussage etwas wert wäre.

---

## 3. Begriffe

| Begriff | Bedeutung |
|---|---|
| **Quelldokument** | Eine PDF-Datei im Eingangsbestand |
| **Block** | Ein zusammenhängender, verorteter und typisierter Bereich einer Seite: Absatz, Überschrift, Tabelle, Abbildung, Fußnote und dergleichen |
| **Ergebnisdokument** | Die strukturierte Fassung eines Quelldokuments, aus der alle Ausgabefassungen abgeleitet werden |
| **Ausgabefassung** | Eine aus dem Ergebnisdokument abgeleitete, für Menschen lesbare Darstellung |
| **Konsolidierte Fassung** | Ein Ergebnisdokument, dessen Sprache nachbearbeitet wurde |
| **Fundstelle** | Quelldokument, Seite und Bereich, aus dem ein Element stammt |
| **Stufe** | Ein abgeschlossener Verarbeitungsschritt mit abgelegtem Ergebnis |

---

## 4. Fachliche Invarianten

Gelten für jede Anforderung. Eine Umsetzung, die eine davon verletzt, ist
unabhängig von ihrer sonstigen Güte abzulehnen.

| # | Invariante | Begründung |
|---|---|---|
| **INV-1** | Seitengrenzen werden nicht aufgehoben. Was auf einer Seite des Quelldokuments steht, bleibt einem Element dieser Seite zugeordnet | Sonst verliert jeder Abnehmer, der nur die erste Seitenangabe eines Elements auswertet, die Zurechenbarkeit lautlos |
| **INV-2** | Jede Stufe liest ein abgelegtes Ergebnis und schreibt ein neues. Keine Stufe verändert die Ausgabe einer vorigen | Nur ein abgelegter Zwischenstand ist prüfbar, wiederholbar und einzeln austauschbar |
| **INV-3** | Regelgebundene und modellgestützte Schritte bleiben getrennt. Ein regelgebundener Schritt trifft keine Modellentscheidung, ein modellgestützter keine Strukturentscheidung | Nur so bleibt der prüfbare Teil prüfbar |
| **INV-4** | Zweifelhafte Eingaben und zweifelhafte Ergebnisse werden gemeldet, nicht stillschweigend behoben | Ein Fehler, der sich selbst behebt, wiederholt sich unbemerkt |
| **INV-5** | Das Quelldokument wird nie verändert | Der Rückweg zum Original muss unversehrt bleiben |

---

## 5. Anforderungen

### 5.1 Eingang

**SR-01** Das System soll den Eingangsbestand vor jeder Verarbeitung vollständig
erfassen und als Arbeitsliste führen.

**SR-02** Wenn der Name eines Quelldokuments sich nicht ohne Verlust in
Verzeichnisnamen, abgeleitete Dateinamen und Verweise des Ergebnisdokuments
übernehmen lässt, soll das System die Verarbeitung nicht beginnen und den Namen
beanstanden.

**SR-03** Wenn ein Name beanstandet wird, soll das System den Grund und einen
zulässigen Ersatznamen nennen, den Namen aber nicht selbst ändern.

**SR-04** Das System soll alle Beanstandungen eines Durchgangs gemeinsam melden,
bevor es anhält.

**SR-05** Wenn ein Quelldokument nicht zu öffnen, zugangsgeschützt oder ohne
Seiten ist, soll das System dies vor Beginn der Verarbeitung feststellen und
melden.

### 5.2 Durchlauf

**SR-06** Das System soll die Quelldokumente der Arbeitsliste nacheinander
vollständig verarbeiten.

**SR-07** Wenn die Verarbeitung eines Quelldokuments fehlschlägt, soll das System
den Fehler festhalten, das Dokument überspringen und mit dem nächsten fortfahren.

**SR-08** Wenn die Verarbeitung einer Seite fehlschlägt, soll das System den
Fehler der Seite beifügen, die Seite überspringen und mit der nächsten
fortfahren.

**SR-09** Wenn ein Durchlauf abgebrochen und erneut gestartet wird, soll das
System bereits abgeschlossene Quelldokumente und Seiten überspringen.

**SR-10** Das System soll je Seite die verbrauchte Zeit und die verwendete
Modellfassung festhalten.

### 5.3 Ergebnisdokument

**SR-11** Das System soll je Quelldokument genau ein Ergebnisdokument erzeugen.

**SR-12** Das Ergebnisdokument soll sein Quelldokument benennen, und zwar so,
dass die Zuordnung ohne Kenntnis der Verzeichnisordnung gelingt und zwei
Fassungen gleichen Namens unterscheidbar bleiben.

**SR-13** Das System soll die Lesereihenfolge über alle Seiten hinweg fortführen.

**SR-14** Das System soll jedem Element seine Fundstelle mitgeben.

**SR-15** Das System soll wiederkehrende Seitenbestandteile ohne inhaltlichen
Beitrag — Kopfzeile, Fußzeile, Seitenzahl — vom Lesefluss ausnehmen, ohne sie zu
verwerfen.

**SR-16** Wenn zwei Erkennungen denselben Gegenstand beschreiben, soll das System
eine davon übernehmen und die Verwerfung melden.

**SR-17** Wenn eine Tabelle nicht in eine strukturierte Form zu überführen ist,
soll das System die erkannte Ausgabe unverändert erhalten und die Seite als
prüfbedürftig kennzeichnen.

### 5.4 Ausgabefassung

**SR-18** Das System soll aus dem Ergebnisdokument eine für Menschen lesbare
Ausgabefassung ableiten. Diese Fassung wird nie von Hand gepflegt.

**SR-19** Das System soll jede Abbildung des Quelldokuments in der Ausgabefassung
an ihrer Fundstelle als auflösbaren Verweis führen.

**SR-20** Das System soll die Abbildungen so ablegen und benennen, dass ein
Mensch im Ablageverzeichnis erkennt, aus welchem Dokument und welcher Seite eine
Abbildung stammt.

**SR-21** Das System soll die Verweise auf Abbildungen so bilden, dass das
Ergebnis samt Abbildungen als Ganzes an einen anderen Ort verschoben werden kann,
ohne dass ein Verweis bricht.

**SR-22** Das System soll in der Ausgabefassung an jedem Seitenwechsel die Seite
des Quelldokuments angeben.

**SR-23** Das System soll für alle Quelldokumente dieselbe Gliederungslogik
anwenden.

### 5.5 Sprachliche Konsolidierung

**SR-24** Das System soll das Ergebnisdokument sprachlich nachbearbeiten lassen
und dabei Schreib-, Grammatik- und Konsistenzfehler beseitigen, die bei der
Texterkennung entstanden sind.

**SR-25** Die konsolidierte Fassung soll neben dem unbearbeiteten
Ergebnisdokument bestehen bleiben und als bearbeitet erkennbar sein, sodass ein
Mensch beide Fassungen vergleichen kann.

**SR-26** Solange die Konsolidierung läuft, sollen Gliederung, Reihenfolge,
Bestand und Fundstellen der Elemente unverändert bleiben.

**SR-27** Das System soll bei der Konsolidierung keinen Inhalt ergänzen und keine
Zahlen, Formeln oder Tabellendaten verändern.

**SR-28** Das System soll die Konsolidierung so ausführen, dass ein zweiter Lauf
über dieselbe Eingabe dasselbe Ergebnis liefert.

### 5.6 Nachvollziehbarkeit

**SR-29** Das System soll für jede Aussage im Ergebnis den Rückweg zur Fundstelle
im Quelldokument offenhalten.

**SR-30** Wenn das System eine Entscheidung trifft, die auch anders ausfallen
könnte — eine Verwerfung, eine Zuordnung, eine unvollständige Erkennung —, soll
es diese Entscheidung im Ergebnis vermerken.

---

## 6. Abgrenzung

Ausdrücklich nicht Gegenstand.

| Nicht enthalten | Begründung |
|---|---|
| Zerlegung in Abschnitte, Einbettung, Suchindex, Messung der Trefferqualität | Ergibt sich aus einem vollständigen Ergebnisdokument und gehört zu dessen Abnehmern, nicht zu diesem Verfahren |
| Bestätigung eines Elements durch eine zweite Quelle, Kennzeichnung unbestätigter Elemente | Es gibt keine zweite verlässliche Quelle (Abschnitt 2) |
| Fallunterscheidung nach dem Vorhandensein einer Textebene | dieselbe Begründung |
| Zusammenfassen eines Absatzes über eine Seitengrenze hinweg | INV-1 |
| Rückführung einer im Fließtext stehenden Formel an ihre genaue Stelle im Satz | INV-1; die Position im erkannten Text ist nicht bestimmbar |
| Beschreibung von Bildinhalten, Typisierung von Kästen ohne eigene Klasse, Zuordnung von Bildunterschriften | Setzt die Anforderungen aus 5.4 und 5.5 voraus und ist ohne Bildverständnis nicht eindeutig lösbar |

---

## 7. Abnahmekriterien

Prüfbar an den erzeugten Artefakten, ohne Kenntnis der Umsetzung.

| # | Kriterium | Deckt ab |
|---|---|---|
| **AK-1** | Ein Quelldokument mit unzulässigem Namen wird abgelehnt; die Meldung nennt Grund und Ersatzvorschlag; es wurde nichts verarbeitet und nichts umbenannt | SR-02 bis SR-04 |
| **AK-2** | Ein zugangsgeschütztes und ein leeres Quelldokument werden vor Verarbeitungsbeginn beanstandet | SR-05 |
| **AK-3** | Ein Eingangsbestand aus mehreren Dokumenten läuft in einem Durchgang durch; ein absichtlich beschädigtes darunter beendet den Durchgang nicht | SR-06, SR-07 |
| **AK-4** | Ein abgebrochener und neu gestarteter Durchgang wiederholt keine abgeschlossene Seite | SR-09 |
| **AK-5** | Die Ausgabefassung eines Lehrbuchs liest sich an einer Kapitelgrenze flüssig; die Gliederungsebenen stimmen | SR-13, SR-23 |
| **AK-6** | Jede Abbildung des Quelldokuments erscheint in der Ausgabefassung an ihrer Stelle und wird beim Betrachten angezeigt | SR-19 |
| **AK-7** | Das Ergebnisverzeichnis wird samt Abbildungen an einen anderen Ort verschoben; keine Abbildung bricht | SR-21 |
| **AK-8** | Zu einer beliebigen Stelle der Ausgabefassung lässt sich die Seite des Quelldokuments benennen und dort wiederfinden | SR-14, SR-22, SR-29 |
| **AK-9** | Die konsolidierte Fassung liegt neben dem Original; ein Vergleich zeigt ausschließlich sprachliche Änderungen, keine strukturellen | SR-25 bis SR-27 |
| **AK-10** | Ein zweiter Konsolidierungslauf über dieselbe Eingabe liefert eine deckungsgleiche Ausgabe | SR-28 |
| **AK-11** | Ein zweites, andersartiges Quelldokument durchläuft dasselbe Verfahren ohne dokumentabhängige Eingriffe | SR-23 |
