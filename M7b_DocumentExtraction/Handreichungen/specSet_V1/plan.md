# plan.md — Dokumentenaufbereitung

**Stand:** 07.09.2026
**Art:** technische Umsetzungsplanung. Bezugsdokument ist die `spec.md`; deren
Anforderungen (SR) und Invarianten (INV) werden hier nicht wiederholt, sondern
umgesetzt. Die Reihenfolge der Arbeit steht in der `tasks.md`.

---

## 1. Technikstack

| | |
|---|---|
| Sprache | Python 3.12 |
| Kanonisches Format | `DoclingDocument` aus **docling-core ≥ 2.95** |
| PDF-Zugriff, Rendern | PyMuPDF |
| Layout-Erkennung | ONNX-Export `phungpx/PP-DocLayoutV3-ONNX` über `onnxruntime`, CPU |
| Texterkennung | PaddleOCR-VL-1.5 über LM Studio, OpenAI-kompatibel, Port 1234 |
| Sprachliche Konsolidierung | Gemma 4 12B oder Qwen3.8 27B über dieselbe Schnittstelle |
| Bildoperationen | OpenCV (headless), NumPy, Pillow |
| Datenmodell Arbeitsformat | pydantic |

Randbedingungen: kein Docker, kein WSL, kein vLLM, kein PaddlePaddle. Zwei
Arbeitsmaschinen (Windows mit 40 GB VRAM, Mac M4 Pro mit 24 GB). Der
Einstiegspunkt ist ein Steuerungsnotebook; `.py`-Dateien werden ausschließlich
importiert, nie direkt gestartet, weil sonst das Arbeitsverzeichnis am Werkzeug
hängt.

### Warum `DoclingDocument`

Es bringt die benötigten Bausteine nativ mit: Inhaltsschichten für getrennte
Lesestörme, einen Parser für das Tabellenvokabular OTSL, Provenienz als Liste von
`(Seite, Rechteck, Zeichenspanne)`, ein veröffentlichtes JSON-Schema und
Anbindung an die verbreiteten Weiterverarbeitungswerkzeuge. Die geprüften
Alternativen scheiden aus: METS/ALTO zielt auf die Rekonstruktion des
Erscheinungsbilds und kennt weder Tabelle noch Formel als Datenstruktur; TEI ist
ohne Anbindung an die Werkzeuglandschaft; JATS/BITS ist Verlagswelt.

---

## 2. Verhalten der Bibliothek — geprüft, nicht angenommen

Gegen `docling-core 2.95.0` praktisch erprobt. Diese Tabelle ist der Kern des
Plans: An drei Stellen ist der naheliegende Weg der falsche.

| Sachverhalt | Konsequenz |
|---|---|
| `export_to_markdown()` verwendet standardmäßig `ImageRefMode.PLACEHOLDER` | Ohne ausdrückliches `REFERENCED` erscheint jede Abbildung als `<!-- image -->`, auch bei gültigem Bildverweis |
| `export_to_markdown(image_mode=REFERENCED)` gibt die am Element hinterlegte URI **unverändert** aus | Eigene, sprechende Namen und relative Pfade überstehen den Export unversehrt |
| **`save_as_markdown(..., image_mode=REFERENCED)` kopiert die Bilder um und benennt in `image_<lfd:06>_<hexhash>.png`** | Dieser Weg wird **nicht** benutzt (SR-20) |
| **`save_as_json` hat `EMBEDDED` als Standard** | Ohne ausdrückliches `PLACEHOLDER` landet jede Abbildung als base64 im JSON. Mit `PLACEHOLDER` bleibt die relative URI stehen |
| `ImageRef.pil_image` lädt eine `Path`-URI beim Zugriff nach | Ein PNG auf der Platte ist ein vollwertiges Bild; nichts muss in den Speicher gezogen werden |
| Der Serializer erzeugt intern `#_#_DOCLING_DOC_PAGE_BREAK_{vorher}_{nachher}_#_#` und ersetzt die Marke in `MarkdownDocSerializer.serialize_doc` durch einen konstanten Platzhalter | Die Seitenzahlen sind da und gehen genau dort verloren. Unterklasse mit überschriebenem `serialize_doc` holt sie zurück |
| Die Marken entstehen nur, wenn `page_break_placeholder` **nicht `None`** ist (`requires_page_break()`) | Der Wert ist gleichgültig, weil unsere Unterklasse ihn ersetzt — gesetzt sein muss er trotzdem |
| `TextItem` lässt nur 14 der 31 `DocItemLabel` zu | Zulässigkeit aus dem Modell auslesen, nicht erinnern; sonst schlägt die Validierung mitten im Dokument fehl |
| `add_page()` zählt ab 1, PyMuPDF ab 0 | Umrechnung an genau einer Stelle |
| `MarkdownTableSerializer` wertet `image_mode` nicht aus | Tabellen als Bild nicht darstellbar; ohne Belang, solange Tabellen als OTSL vorliegen |
| Öffnen plus `page_count`, `needs_pass`, `is_encrypted` kostet gemessen 0,25 ms bei 222 Seiten | Die technische Eingangsprüfung (SR-05) ist gegenüber der Verarbeitung kostenlos |

---

## 3. Modulschnitt

Flach neben dem Steuerungsnotebook, kein Paketordner. Neu sind vier Module, die
übrigen werden angepasst.

| Modul | Rolle | interne Abhängigkeiten |
|---|---|---|
| `schema.py` | Arbeitsformat, Koordinatenrahmen, Klassenabbildung, Ablage eines Befunds | keine |
| **`pfade.py`** *(neu)* | **Einzige Stelle, die aus einem Dokumentnamen Pfade ableitet.** Dazu das Namensregelwerk | keine |
| `layout.py` | Stufe 1 | schema |
| `erkennung.py` | Stufe 2 | schema, pfade |
| `stapel.py` | Stufenlauf über die Seiten **eines** Dokuments | schema, pfade |
| `kanonisch.py` | Stufe 4a | schema, pfade |
| **`konsolidierung.py`** *(neu)* | Stufe 5 | schema, pfade |
| **`lauf.py`** *(neu)* | Erfassung, Eingangsprüfung, Arbeitsliste, Schleife über **mehrere** Dokumente | pfade, stapel, kanonisch, konsolidierung |
| `sichtung.py` | Auswertung, verändert nichts | schema, pfade |

`schema.py` und `pfade.py` haben keine interne Abhängigkeit; alles andere hängt an
ihnen. Die schweren Abhängigkeiten (`onnxruntime`, `requests`, `docling-core`)
werden erst beim tatsächlichen Bedarf importiert, damit ein reiner Stufe-2-Lauf
ohne `onnxruntime` auskommt.

---

## 4. Ablage und Pfadableitung

### 4.1 Verzeichnisse

```
data/
├── raw/<dok>.pdf
├── interim/
│   ├── befunde/<dok>/<seite:04d>.json
│   ├── ausschnitte/<dok>/<dok>_<seite:04d>_<block:02d>_<klasse>.png
│   └── kontrolle/<dok>_<seite:04d>.png
└── processed/<dok>/
    ├── <dok>.json
    ├── <dok>.md
    ├── <dok>_k.json
    ├── <dok>_k.md
    └── <dok>_artifacts/<dok>_<seite:04d>_<block:02d>_<klasse>.png
```

Der Ordner je Dokument unterhalb von `processed` ist die Voraussetzung dafür,
dass **eine** relative Bild-URI gleichzeitig aus dem JSON und aus dem Markdown
auflöst (SR-21). Die konsolidierte Fassung liegt im selben Ordner und teilt sich
den Bildbestand, ohne eine Datei zu verdoppeln.

### 4.2 `pfade.py`

Kein Modul bildet Pfade selbst. Jede Konstante wie `Path("befunde")` verschwindet
aus `stapel.py`, `kanonisch.py` und `sichtung.py`; das Steuerungsnotebook
definiert keinen zweiten Pfadsatz mehr.

```python
WURZEL   = Path("data")
RAW      = WURZEL / "raw"
INTERIM  = WURZEL / "interim"
PROCESSED= WURZEL / "processed"

def quelle(dok: str) -> Path                     # data/raw/<dok>.pdf
def befund_ordner(dok: str) -> Path
def befund(dok: str, seite: int) -> Path         # .../<seite:04d>.json
def ausschnitt_ordner(dok: str) -> Path
def bildname(dok, seite, block, klasse) -> str   # <dok>_0042_07_image.png
def ausschnitt(dok, seite, block, klasse) -> Path
def dokument_ordner(dok: str) -> Path
def artefakt_ordner(dok: str) -> Path            # .../<dok>_artifacts
def artefakt(dok, seite, block, klasse) -> Path
def artefakt_relativ(dok, seite, block, klasse) -> Path   # <dok>_artifacts/<name>.png
def dokument_json(dok: str, konsolidiert: bool = False) -> Path
def dokument_md(dok: str,  konsolidiert: bool = False) -> Path
def kontrolle(dok: str, seite: int) -> Path
```

`bildname` liefert **denselben** Namen für den Zwischenbestand und den
Ergebnisbestand. Damit ist die Kopie in 4a ein reines Umkopieren ohne Umbenennen,
und ein Mensch findet dieselbe Datei an beiden Orten wieder.

`artefakt_relativ` ist der einzige Weg, eine Bild-URI zu bilden. Sie ist relativ
zum Dokumentordner, weil dort sowohl `<dok>.json` als auch `<dok>.md` liegen.

### 4.3 Änderung am Arbeitsformat

`Block.ausschnitt` trägt künftig **nur den Dateinamen**, nicht mehr einen Pfad
relativ zum Arbeitsverzeichnis. Der Ordner wird über `pfade` hergeleitet. Damit
ist ein Verschieben des Zwischenbestands folgenlos, statt lautlos leere
Bildverweise zu erzeugen.

`Stufe` bekommt einen fünften Wert:

```python
class Stufe(int, Enum):
    LAYOUT       = 1
    ERKANNT      = 2
    KANONISCH    = 4
    KONSOLIDIERT = 5
```

---

## 5. Eingangsprüfung (SR-02 bis SR-05)

### 5.1 Namensregelwerk — in `pfade.py`

Die Regeln gehören zur Pfadableitung, weil sie aus ihr folgen.

| Prüfung | Zulässig |
|---|---|
| Zeichenvorrat | `A–Z`, `a–z`, `0–9`, `-`, `_` |
| Erstes Zeichen | Buchstabe oder Ziffer |
| Länge des Stamms | ≤ `MAX_STAMM` = 48 |
| Endung | genau `.pdf`, kleingeschrieben |
| Eindeutigkeit | keine zwei Stämme, die sich nur in der Groß-/Kleinschreibung unterscheiden |
| Reservierte Namen | nicht `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9` |

**Herleitung von 48:** Der längste abgeleitete Pfad ist
`data/processed/<dok>/<dok>_artifacts/<dok>_0221_11_footer_image.png`. Der Name
steckt dreimal darin, dazu rund 52 feste Zeichen. Bei der Pfadgrenze von 260
Zeichen unter Windows und einem Projektordner von etwa 60 Zeichen bleiben rund
148 Zeichen für die drei Vorkommen. Die Konstante steht mit dieser Rechnung als
Kommentar im Code, damit sie bei geänderter Struktur nachrechenbar bleibt.

```python
MAX_STAMM = 48
def name_pruefen(stamm: str) -> list[str]       # leere Liste = in Ordnung
def ersatzname(stamm: str) -> str               # Vorschlag, wird nie angewandt
def namen_pruefen(pfade: list[Path]) -> dict[Path, list[str]]   # inkl. Kollisionen
```

`ersatzname` liefert einen Vorschlag für die Meldung. Er wird an keiner Stelle
selbsttätig verwendet (INV-4).

### 5.2 Technische Prüfung — in `lauf.py`

Öffnen, `is_pdf`, `needs_pass`, `is_encrypted`, `page_count > 0`. Ausschließlich
das; keine Prüfung, die Seiteninhalte anfasst. Eine Integritätsprüfung über alle
Seiten kostet in der Größenordnung eines Layoutlaufs und beantwortet eine Frage,
die Stufe 1 ohnehin seitenweise beantwortet — dort mit Übergehen der Seite statt
mit einem Abbruch am Eingang.

### 5.3 Ablauf

Beide Prüfungen laufen über den **ganzen** Bestand, sammeln alle Beanstandungen
und melden sie gemeinsam. Erst danach wird angehalten. Es wird nichts verarbeitet
und nichts angelegt, solange eine Beanstandung offen ist.

---

## 6. Dokumentenlauf (`lauf.py`, SR-01, SR-06 bis SR-09)

```python
def erfassen(wurzel: Path = pfade.RAW) -> list[Path]
def pruefen(dateien: list[Path]) -> dict[Path, list[str]]
def offene_dokumente(dateien, bis: Stufe) -> list[str]
def verarbeite_alle(bis: Stufe = Stufe.KANONISCH, neu: bool = False,
                    detektor=None, erkenner=None) -> Laufbericht
```

- Erfassung ohne Rekursion, stabil sortiert.
- `verarbeite_alle` prüft zuerst, hält bei Beanstandungen an, und ruft danach je
  Dokument den vorhandenen Stufenlauf auf. Die Seitenlogik in `stapel.py` bleibt
  unangetastet.
- Detektor und Erkenner werden **einmal** erzeugt und über alle Dokumente
  weitergereicht. Der stufenweise Lauf je Dokument bleibt bestehen, damit
  Detektor und Sprachmodell nie gleichzeitig geladen sind.
- Ein gescheitertes Dokument wird vermerkt und übersprungen (SR-07).
- `offene_dokumente` beantwortet das Wiederaufsetzen auf Dokumentebene, ohne zu
  rechnen: ein Dokument gilt als abgeschlossen, wenn seine Zielartefakte
  vorliegen und keine Seite einen Fehler trägt.

---

## 7. Bilder und Ausgabe (SR-15, SR-18 bis SR-22)

### 7.1 Kopie statt Umleitung

Stufe 2 schreibt die Ausschnitte weiterhin in den Zwischenbestand. Stufe 4a
**kopiert** sie in den Artefaktordner.

Der Grund ist die Wiederholbarkeit: Nur so lässt sich `processed/` löschen und in
Sekunden neu erzeugen, ohne die dreiviertel Stunde der Erkennungsstufe zu
wiederholen. Schriebe Stufe 2 direkt an den Zielort, hinge der Ergebnisbestand am
teuersten Schritt der Pipeline. Der Preis ist der doppelte Plattenplatz für die
Ausschnitte — bei 63 PNG je Buch ohne Bedeutung.

Die Kopie ist idempotent (Ziel wird überschrieben) und läuft im selben Durchgang,
in dem das Element angelegt wird.

### 7.2 Bildverweis

```python
ziel = pfade.artefakt(dok, befund.seite, blk.id, blk.pp_label)
shutil.copyfile(pfade.ausschnitt_ordner(dok) / blk.ausschnitt, ziel)
verweis = ImageRef(mimetype="image/png", dpi=PROBE_DPI,
                   size=_bildgroesse(ziel),
                   uri=pfade.artefakt_relativ(dok, befund.seite, blk.id, blk.pp_label))
```

Die Größe kommt aus der Datei, ersatzweise aus der Box. Der Zweig für Diagramme
bekommt denselben Bildverweis; heute wird dort nur die Datenreihe angehängt, was
im Markdown eine Tabelle ohne Diagramm ergibt (SR-19).

### 7.3 Seitenangabe

```python
class SeitenSerializer(MarkdownDocSerializer):
    def serialize_doc(self, *, parts, **kw):
        res = "\n\n".join(p.text for p in parts if p.text)
        for voll, _, nach in self._get_page_breaks(text=res):
            res = res.replace(voll, f'<!-- Seite {nach} --><a id="seite-{nach}"></a>')
        return create_ser_result(text=res, span_source=parts)
```

Aufruf mit `MarkdownParams(image_mode=REFERENCED, page_break_placeholder="<!-- pb -->")`.
Der Platzhalterwert ist gleichgültig, darf aber nicht `None` sein, sonst werden
keine Marken erzeugt. Erprobtes Ergebnis:

```
![Image](Buch_artifacts/Buch_0000_03_image.png)

<!-- Seite 2 --><a id="seite-2"></a>
```

### 7.4 Inhaltsschichten der Ausgabefassung

Die Ströme werden auf Inhaltsschichten abgebildet: Haupttext und Apparat nach
`BODY`, Marginalien nach `NOTES`, Kopf- und Fußzeilen nach `FURNITURE`. Der
Serializer berücksichtigt standardmäßig **nur `BODY`**.

Für die Ausgabefassung gilt:

```python
MarkdownParams(layers={ContentLayer.BODY, ContentLayer.NOTES}, …)
```

`FURNITURE` bleibt ausgeschlossen (SR-15). `NOTES` wird eingeschlossen, weil eine
Marginalspalte in Lehrbüchern Definitionen und Merksätze trägt; mit der Vorgabe
fielen sie unbemerkt aus der lesbaren Ausgabe. Erprobt: derselbe Text erscheint
mit `{BODY}` nicht und mit `{BODY, NOTES}` an seiner Stelle, während die
Kopfzeile in beiden Fällen draußen bleibt.

Im JSON ist unabhängig davon alles enthalten; die Schicht steht dort an jedem
Element und bleibt für Abnehmer auswertbar.

### 7.5 Schreiben

```python
dok.save_as_json(pfade.dokument_json(name), image_mode=ImageRefMode.PLACEHOLDER)
pfade.dokument_md(name).write_text(markdown, encoding="utf-8")
```

`save_as_markdown` wird nicht verwendet (siehe Abschnitt 2).

---

## 8. Konsolidierung (`konsolidierung.py`, Stufe 5, SR-24 bis SR-28)

### 8.1 Ablauf

Liest `<dok>.json`, schreibt `<dok>_k.json` und `<dok>_k.md`. Stufe 4a bleibt
unberührt (INV-2). Der Bildbestand wird nicht angefasst; `<dok>_k.md` verweist auf
denselben Artefaktordner.

Eingabeeinheit ist **eine Seite je Aufruf**. Je Seite werden die Textelemente in
Dokumentreihenfolge eingesammelt und als nummerierte Liste übergeben; das Modell
gibt dieselbe Liste in derselben Länge und Reihenfolge zurück.

```python
def seite_konsolidieren(elemente: list[str], modell) -> list[str]
def dokument_konsolidieren(dok: str, modell) -> tuple[DoclingDocument, Bericht]
```

Aufruf mit `temperature=0` (SR-28).

### 8.2 Wächter

Ein Sprachmodell, das eine Liste umbauen soll, ist die wahrscheinlichste
Fehlerquelle der ganzen Stufe. Deshalb wird die Rückgabe geprüft, bevor sie
übernommen wird:

| Prüfung | Verhalten bei Verstoß |
|---|---|
| Anzahl der Elemente unverändert | Seite unverändert übernehmen, Warnung |
| Antwort ist gültiges JSON in der vereinbarten Form | dasselbe |
| Längenänderung eines Elements innerhalb einer Schranke (Vorschlag: ±25 %) | betroffenes Element unverändert übernehmen, Warnung |
| Ziffernfolgen des Elements unverändert | dasselbe (SR-27) |

Nicht übergeben werden Tabellen, Formeln und Datenreihen. Sie sind vom Eingriff
ausgenommen (SR-27) und bleiben aus der Eingabe heraus.

### 8.3 Nachweis

Der Nachweis ist der Vergleich der beiden Fassungen (SR-25). Ein zusätzliches
Änderungsprotokoll wird nicht geführt: Es ließe sich jederzeit aus dem Vergleich
herstellen und wäre eine zweite Wahrheit, die auseinanderlaufen kann.

---

## 9. Nachweistabelle

| Anforderung | Ort der Umsetzung |
|---|---|
| SR-01, SR-06, SR-07 | `lauf.erfassen`, `lauf.verarbeite_alle` |
| SR-02 bis SR-04 | `pfade.name_pruefen`, `pfade.namen_pruefen`, `lauf.pruefen` |
| SR-05 | `lauf.pruefen` (technischer Teil) |
| SR-08, SR-10 | `stapel.stufe1_lauf`, `stapel.stufe2_lauf` (vorhanden) |
| SR-09 | `schema.ist_fertig` (Seite), `lauf.offene_dokumente` (Dokument) |
| SR-11, SR-13 | `kanonisch.nach_docling` (vorhanden) |
| SR-12 | `DocumentOrigin` in `kanonisch.nach_docling` |
| SR-14, SR-29 | `kanonisch.provenienz` (vorhanden) |
| SR-15 | Abbildung Strom → Inhaltsschicht, Abschnitt 7.4 |
| SR-16, SR-17, SR-30 | `kanonisch.entdoppeln`, Berichtsfelder (vorhanden) |
| SR-18, SR-22 | `SeitenSerializer`, Abschnitt 7.3 und 7.4 |
| SR-19 bis SR-21 | Abschnitt 7.1 und 7.2, `pfade.artefakt_relativ` |
| SR-23 | ein Codepfad für alle Dokumente; belegt durch das zweite Dokument |
| SR-24 bis SR-28 | `konsolidierung.py`, Abschnitt 8 |

---

## 10. Bekannte Fallen

Jede bereits einmal getreten. Kein erneuter Beleg nötig.

| Falle | Symptom | Gegenmittel |
|---|---|---|
| Falscher ONNX-Export | `KeyError` auf `order_logits`, oder ein einzelner `(300,7)`-Tensor | Vertragstest beim Öffnen der Sitzung |
| Fest verdrahtete Ausführungsanbieter | Ausnahme beim Öffnen auf dem Mac | Gegen `get_available_providers()` filtern |
| Fehlende `mmproj`-Datei | HTTP 400, „model does not support images" | Beide GGUF-Dateien im selben Ordner |
| Falsches Modell in LM Studio geladen | HTTP 400 auf jeder Seite | Modell-ID setzen, nicht das erste geladene nehmen |
| `raise_for_status()` verwirft den Antwortkörper | 400 ohne Begründung | Fehlertext aus der Antwort lesen |
| Token-Deckel schneidet still ab | Ausgabe liest sich flüssig, hört früher auf | `finish_reason == "length"` auswerten und als Warnung ablegen |
| Fester Ausschnittsrand | Nachbartext im Ergebnis | Rand proportional zur Boxhöhe, beidseitig gedeckelt |
| `float32`-Sättigung der Kantenkonfidenz | alle Werte 1,0 | Im Logit-Raum rechnen |
| Unzulässiges `DocItemLabel` | Validierungsfehler mitten im Dokument | Zulässigkeit aus dem Modell auslesen |
| Doppelte Formeldelimiter | `$$$…$$$` im Markdown | Vor dem Anlegen abstreifen |
| `Path.glob` auf fehlendem Ordner | leere Liste, kein Fehler | Vorhandensein des Ordners getrennt prüfen |
| Arbeitsverzeichnis | Ordner landen eine Ebene zu hoch | Notebook steuert; Abschnitt 0 meldet, statt zu korrigieren |
