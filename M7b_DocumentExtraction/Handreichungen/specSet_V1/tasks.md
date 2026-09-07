# tasks.md — Etappe P0: Eingang und Ablage

**Stand:** 07.09.2026
**Bezug:** `spec.md` (Anforderungen SR, Invarianten INV), `plan.md` (Umsetzung).
Beide werden hier nicht wiederholt, sondern zitiert.
**Umfang:** ausschließlich P0. Bilder, Seitenangaben und Konsolidierung sind
Gegenstand eigener Etappen und werden hier ausdrücklich nicht angefasst.

---

## 1. Betrieb dieser Etappe

- **Etappenlauf:** Die Aufgaben werden in der angegebenen Reihenfolge abgearbeitet.
  Nach jeder Aufgabe ein Checkpoint-Commit mit der Aufgabennummer in der Nachricht.
- **Test vor Umsetzung:** Jede Aufgabe nennt zuerst die Prüfung, dann die
  Umsetzung. Die Prüfung wird geschrieben, läuft rot, und erst danach entsteht der
  Code, der sie grün macht.
- **Keine Modelle nötig:** Alle Aufgaben dieser Etappe sind Pfad-, Prüf- und
  Ablauflogik. Weder das ONNX-Modell noch LM Studio werden gebraucht; der
  Stufenlauf nimmt Detektor und Erkenner als Argument entgegen und lässt sich
  durch Attrappen ersetzen.
- **Status:** ⬜ offen · 🟨 in Arbeit · ✅ abgenommen

| # | Aufgabe | Status |
|---|---|---|
| T0 | Prüfstand | ⬜ |
| T1 | `pfade.py` — Ableitung | ⬜ |
| T2 | `pfade.py` — Namensregelwerk | ⬜ |
| T3 | `schema.py` — Ausschnitt trägt nur den Dateinamen | ⬜ |
| T4 | Bestehende Module auf `pfade` umstellen | ⬜ |
| T5 | `lauf.py` — Erfassung und Eingangsprüfung | ⬜ |
| T6 | `lauf.py` — Schleife über die Dokumente | ⬜ |
| T7 | `lauf.py` — Wiederaufsetzen auf Dokumentebene | ⬜ |
| T8 | `kanonisch.py` — Herkunft und neuer Ausgabeort | ⬜ |
| T9 | Steuerungsnotebook | ⬜ |
| T10 | Etappenabnahme am echten Bestand | ⬜ |

---

## T0 — Prüfstand

**Ziel:** Ein Prüfbestand, der die Fehlerfälle enthält, statt sie sich vorzustellen.

**Umsetzung**

`probelauf_p0.py` legt unter einem temporären Verzeichnis an:

| Datei | Zweck |
|---|---|
| `Lehrbuch.pdf` | gültig, 3 Seiten |
| `zweites_buch.pdf` | gültig, 2 Seiten |
| `Buch mit Leerzeichen.pdf` | unzulässiger Zeichenvorrat |
| `Ökonomie.pdf` | Nicht-ASCII |
| `-fuehrender_strich.pdf` | unzulässiges erstes Zeichen |
| `<49 Zeichen langer Stamm>.pdf` | Längengrenze |
| `Lehrbuch.PDF` | Kollision mit `Lehrbuch.pdf` bei Groß-/Kleinschreibung |
| `CON.pdf` | reservierter Name |
| `geschuetzt.pdf` | mit Kennwort gespeichert |
| `leer.pdf` | null Seiten |
| `kaputt.pdf` | Textdatei mit PDF-Endung |

Dazu zwei Attrappen: ein Detektor, der einen Befund mit zwei Blöcken je Seite
liefert, und ein Erkenner, der Text einträgt, ohne eine Schnittstelle
anzusprechen. Beide bekommen einen Schalter, der eine bestimmte Seite oder ein
bestimmtes Dokument scheitern lässt.

**Fertig, wenn** der Bestand mit einem Aufruf entsteht und wieder verschwindet,
und ein Durchlauf mit den Attrappen ohne Modell und ohne Netz durchläuft.

---

## T1 — `pfade.py`, Ableitung

**Bezug:** plan.md 4.1 und 4.2, SR-21

**Prüfung**

- Jede Funktion liefert für denselben Dokumentnamen denselben Pfad, und alle
  Pfade liegen unterhalb von `data/`.
- `bildname` liefert für Zwischenbestand und Ergebnisbestand **denselben** Namen.
- `artefakt_relativ` ist relativ und beginnt mit `<dok>_artifacts/`.
- `dokument_json(dok)` und `dokument_json(dok, konsolidiert=True)` liegen im
  selben Verzeichnis und unterscheiden sich nur im Suffix `_k`.
- Ein Pfad, der aus `dokument_ordner` und `artefakt_relativ` zusammengesetzt wird,
  ist derselbe wie `artefakt`. Diese Prüfung ist die wichtigste der Aufgabe: Sie
  hält die relative URI und den Schreibort dauerhaft zusammen.

**Umsetzung**

Modul nach plan.md 4.2. Keine Abhängigkeit außer `pathlib`. Keine Funktion legt
ein Verzeichnis an; das Anlegen bleibt Sache des Schreibenden.

**Fertig, wenn** alle Prüfungen grün sind und das Modul ohne weitere Importe lädt.

---

## T2 — `pfade.py`, Namensregelwerk

**Bezug:** plan.md 5.1, SR-02 bis SR-04, INV-4

**Prüfung**

- Jede Datei des Prüfbestands aus T0 wird mit dem erwarteten Grund beanstandet
  oder durchgelassen. Je Regel mindestens ein Fall.
- Die Kollisionsprüfung meldet `Lehrbuch.pdf` und `Lehrbuch.PDF` gemeinsam, nicht
  einzeln.
- `ersatzname` liefert für jeden beanstandeten Namen einen Vorschlag, der die
  eigene Prüfung besteht.
- **Ein Nachweis, dass nichts umbenannt wird:** Nach dem Prüflauf sind die
  Dateinamen im Bestand unverändert.
- Die Konstante `MAX_STAMM` trägt die Herleitung als Kommentar, und der längste
  aus ihr gebildete Pfad bleibt unter 260 Zeichen. Diese Prüfung rechnet die
  Grenze nach, statt die Zahl zu glauben.

**Umsetzung**

`name_pruefen`, `ersatzname`, `namen_pruefen` nach plan.md 5.1.

**Fertig, wenn** alle Fälle des Prüfbestands den erwarteten Befund liefern.

---

## T3 — `schema.py`, Ausschnitt trägt nur den Dateinamen

**Bezug:** plan.md 4.3

**Prüfung**

- Ein Befund, dessen `ausschnitt` einen Dateinamen trägt, wird geschrieben,
  gelesen und ist unverändert.
- Ein Befund mit einem Pfad im Feld wird beim Laden beanstandet, nicht klaglos
  übernommen (INV-4).

**Umsetzung**

Feldbeschreibung und Wächter in `Block`. Kein Wanderungspfad für alte Befunde:
Der Bestand wird in T10 neu erzeugt.

**Fertig, wenn** beide Prüfungen grün sind.

---

## T4 — Bestehende Module auf `pfade` umstellen

**Bezug:** plan.md 3 und 4.2

**Prüfung**

- Eine Suche über `stapel.py`, `erkennung.py`, `kanonisch.py` und `sichtung.py`
  findet keine Pfadkonstante und kein zusammengesetztes Verzeichnisliteral mehr.
  Diese Prüfung läuft als Test mit, nicht als Sichtkontrolle.
- Ein Stufenlauf mit den Attrappen aus T0 legt seine Ergebnisse an den Orten aus
  plan.md 4.1 ab und an keinem anderen.

**Umsetzung**

Konstanten entfernen, Aufrufe auf `pfade` umstellen. Die Signaturen behalten ihre
Wurzelargumente, damit sie im Test umgelenkt werden können; die Vorgabewerte
kommen aus `pfade`.

**Fertig, wenn** kein Modul außer `pfade` einen Pfad bildet.

---

## T5 — `lauf.py`, Erfassung und Eingangsprüfung

**Bezug:** plan.md 5.2 und 5.3, SR-01, SR-05

**Prüfung**

- Die Erfassung findet die PDF-Dateien des Prüfbestands, steigt nicht in
  Unterordner ab und liefert eine stabile Reihenfolge.
- `geschuetzt.pdf`, `leer.pdf` und `kaputt.pdf` werden je mit eigenem Grund
  beanstandet.
- **Alle** Beanstandungen erscheinen in **einer** Meldung; der Aufruf hält danach
  an. Ein Bestand mit fünf schlechten Dateien erzeugt fünf Zeilen und einen Halt,
  nicht fünf Läufe.
- Bei offener Beanstandung wurde kein Verzeichnis angelegt und keine Datei
  geschrieben.
- Die Prüfung eines Bestands aus zwölf Dateien bleibt deutlich unter einer
  Sekunde.

**Umsetzung**

`erfassen`, `pruefen` nach plan.md 6. Die technische Prüfung fasst keine
Seiteninhalte an.

**Fertig, wenn** der Prüfbestand vollständig und in einem Durchgang beanstandet wird.

---

## T6 — `lauf.py`, Schleife über die Dokumente

**Bezug:** plan.md 6, SR-06, SR-07

**Prüfung**

- Ein Bestand aus zwei gültigen Dokumenten läuft in einem Aufruf durch; beide
  Ergebnisbestände liegen vor.
- Lässt die Attrappe das erste Dokument scheitern, wird der Fehler vermerkt, das
  Dokument übersprungen und das zweite dennoch verarbeitet.
- Detektor und Erkenner werden **einmal** erzeugt und über beide Dokumente
  weitergereicht. Nachweis: Die Attrappe zählt ihre Erzeugungen.
- Der Laufbericht nennt je Dokument Zustand, Dauer und Fehlertext.

**Umsetzung**

`verarbeite_alle` nach plan.md 6. Die Seitenlogik in `stapel.py` wird nicht
angefasst.

**Fertig, wenn** ein gescheitertes Dokument den Lauf nachweislich nicht beendet.

---

## T7 — `lauf.py`, Wiederaufsetzen auf Dokumentebene

**Bezug:** plan.md 6, SR-09

**Prüfung**

- Ein zweiter Lauf über einen fertigen Bestand verarbeitet nichts und meldet
  beide Dokumente als abgeschlossen.
- Wird eine Seitendatei eines Dokuments gelöscht, gilt nur dieses Dokument als
  offen; das andere bleibt unberührt.
- Ein Dokument, dessen Seite einen Fehler trägt, gilt als offen und wird erneut
  versucht.
- `offene_dokumente` öffnet nachweislich nicht jede Seitendatei. Nachweis über
  einen Zähler auf der Ladefunktion.

**Umsetzung**

`offene_dokumente` nach plan.md 6.

**Fertig, wenn** alle vier Prüfungen grün sind.

---

## T8 — `kanonisch.py`, Herkunft und neuer Ausgabeort

**Bezug:** plan.md 4.1, SR-11, SR-12

**Prüfung**

- Das Ergebnisdokument trägt Dateiname, MIME-Typ und Binärhash des Quelldokuments.
- Zwei Quelldateien gleichen Namens mit unterschiedlichem Inhalt ergeben
  unterschiedliche Hashes.
- JSON und Markdown liegen unter `data/processed/<dok>/`, nicht mehr in getrennten
  Sammelordnern.
- Ein zweiter Aufruf über denselben Bestand überschreibt und erzeugt kein zweites
  Ergebnis daneben.

**Umsetzung**

`DocumentOrigin` beim Anlegen setzen, Ausgabeorte aus `pfade`. Bilder,
Seitenangaben und Inhaltsschichten bleiben unverändert — sie sind Gegenstand der
nächsten Etappe.

**Fertig, wenn** die Herkunft im JSON steht und beide Ausgaben am neuen Ort liegen.

---

## T9 — Steuerungsnotebook

**Bezug:** plan.md 3 und 4.2, INV-4

**Prüfung**

- Im Notebook steht kein Pfadliteral mehr; alle Pfade kommen aus `pfade`.
- Abschnitt 0 meldet Arbeitsverzeichnis, Vorhandensein der Verzeichnisse und ein
  etwaiges Abweichen, ohne etwas richtigzustellen.
- Ein Durchlauf von oben nach unten in einem frischen Kernel läuft ohne
  Handgriff durch.

**Umsetzung**

Der doppelte Pfadsatz entfällt. Neue Abschnitte für Eingangsprüfung und
Dokumentenlauf. `mkdir` durchgängig mit `parents=True`.

**Fertig, wenn** ein frischer Kernel das Notebook ohne Eingriff durchläuft.

---

## T10 — Etappenabnahme am echten Bestand

**Bezug:** spec.md AK-1 bis AK-4, plan.md 7.1

**Vorbereitung:** `data/interim` und `data/processed` werden gelöscht und neu
erzeugt. Ein Wanderungspfad für alte Zwischenergebnisse wird nicht gebaut.

**Abnahme — von Hand, am Artefakt:**

1. Ein Bestand aus mindestens zwei echten PDF-Dokumenten läuft in einem Aufruf
   durch. **(AK-3)**
2. Eine absichtlich falsch benannte Datei wird abgelehnt; die Meldung nennt Grund
   und Ersatzvorschlag; nichts wurde verarbeitet, nichts umbenannt. **(AK-1)**
3. Ein zugangsgeschütztes und ein leeres Dokument werden vor Verarbeitungsbeginn
   beanstandet. **(AK-2)**
4. Der Lauf wird mitten in der Erkennung abgebrochen und neu gestartet; keine
   abgeschlossene Seite wird wiederholt. **(AK-4)**
5. Die Verzeichnisstruktur entspricht plan.md 4.1, mit einem eigenen Ordner je
   Dokument unterhalb von `processed`.
6. `data/processed` wird gelöscht und aus dem Zwischenbestand allein in Sekunden
   neu erzeugt, ohne die Erkennungsstufe erneut zu starten. Das ist der Nachweis
   für die Kopierentscheidung aus plan.md 7.1, auch wenn die Kopie selbst erst in
   der nächsten Etappe gebaut wird.

**Fertig, wenn** alle sechs Punkte sitzen und die Statusspalte oben durchgehend
auf ✅ steht.

---

## 2. Nicht in dieser Etappe

Steht hier, damit es nicht hineinwächst.

| Punkt | Etappe |
|---|---|
| Kopie der Ausschnitte, Bildverweise, Diagrammbilder | P1 |
| Seitenangabe im Markdown, eigener Serializer | P1 |
| Inhaltsschichten der Ausgabefassung | P1 |
| Konsolidierungsstufe, fünfter Wert im Stufen-Enum | P2 |
| Sämtliche Randfälle der Erkennung | P3 |
