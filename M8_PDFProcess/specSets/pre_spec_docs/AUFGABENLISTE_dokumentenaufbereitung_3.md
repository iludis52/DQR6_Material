# Dokumentenaufbereitung — Aufgabenliste

**Stand:** 07.09.2026
**Geltung:** Dieses Dokument steht für sich. Es setzt kein Vorwissen voraus und
verweist auf keine früheren Fassungen. Weiterentwickelt wird es in
Review-Schleifen an diesem Text, nicht durch Nachträge.

---

## 1. Ziel

Eine Pipeline, die beliebige PDF-Dokumente so aufbereitet, dass das Ergebnis für
Menschen lesbar und allgemein weiterverarbeitbar ist.

„Lesbar" heißt: Ein Mensch, der das erzeugte Markdown liest, erkennt Struktur,
Text, Tabellen, Abbildungen und Fundstellen ohne Rückgriff auf das Original.
„Weiterverarbeitbar" heißt: Das Ergebnis liegt in einem verbreiteten,
dokumentierten Format vor, sodass ein Abnehmer, dessen Anforderungen heute noch
nicht bekannt sind, es ohne Sonderwissen über diese Pipeline verwenden kann.

Der Prüfstein ist das erzeugte Artefakt. Was im Markdown fehlt oder falsch
steht, ist ein Mangel.

---

## 2. Randbedingungen

Diese Punkte stehen nicht zur Abwägung. Sie gelten für jede Aufgabe unten.

| | Randbedingung | Grund |
|---|---|---|
| R1 | **Seitengrenzen werden nirgends aufgehoben.** Was auf einer Seite steht, bleibt dort | Jede Aussage im Ergebnis muss rückwärts einer Seite des Originals zurechenbar bleiben. Ein Element, das zwei Seiten überspannt, verliert diese Zurechenbarkeit für jeden Abnehmer, der nur die erste Seitenangabe liest |
| R2 | **Standardtreue vor Eigenbau.** Native Mechanismen des kanonischen Formats vor eigenen Konstruktionen, dokumentierte Erweiterungspunkte vor Eingriffen | Die späteren Abnehmer sind unbekannt. Was nicht vorhersehbar ist, wird durch Standardkonformität aufgefangen |
| R3 | **Deterministisches und Generatives bleiben getrennt.** Regelbasierte Schritte enthalten keine Modellaufrufe, Modellschritte treffen keine Strukturentscheidungen | Nur so bleibt der prüfbare Teil prüfbar |
| R4 | **Kein stilles Zurechtrücken.** Zweifelhafte Eingaben und zweifelhafte Ergebnisse werden gemeldet, nicht repariert | Ein Fehler, der sich selbst behebt, wiederholt sich unbemerkt |
| R5 | **Laufzeitumgebung:** Python 3.12, lokal betriebene Modelle über LM Studio (OpenAI-kompatibel, Port 1234). Kein Docker, kein WSL, kein vLLM. Zwei Arbeitsmaschinen: Windows mit 40 GB VRAM, Mac M4 Pro mit 24 GB | Das Material wird an Studierende ausgegeben; jede zusätzliche Installationsstufe ist nicht betreubar |
| R6 | **Ein Notebook steuert, die Module werden importiert.** Keine `.py` wird direkt gestartet | Das Arbeitsverzeichnis hängt sonst am Werkzeug: Der Jupyter-Kernel startet im Ordner der Datei, eine IDE startet im Workspace-Ordner |

---

## 3. Ausgangspunkt

Die Pipeline läuft in Stufen. Jede Stufe schreibt ihr Ergebnis, bevor die
nächste beginnt.

| Stufe | Inhalt | Modell |
|---|---|---|
| 1 | Layout-Erkennung: Seitenbild → verortete, typisierte, geordnete Blöcke | ONNX-Detektor (PP-DocLayoutV3) |
| 2 | Erkennung: Blöcke zusammenführen, Ausschnitte schneiden, Text füllen | PaddleOCR-VL-1.5 über LM Studio |
| 4a | Kanonisches Dokument: Entdopplung, Gliederungsebenen, Tabellen, Provenienz → `DoclingDocument` | keins |

Zwischenergebnisse liegen als ein Seitenbefund je Seite. Das kanonische Dokument
wird nach JSON und Markdown ausgegeben.

Was heute gut trägt: Fließtext, Überschriftenhierarchie, Tabellen und
Formatierungen. Was fehlt und diese Etappe bestimmt: Abbildungen erscheinen im
Markdown nicht, Seitenangaben fehlen dort, und der Lauf ist auf ein einzelnes
fest benanntes Dokument zugeschnitten.

---

## 4. Technische Grundlagen

Gegen die installierte Fassung `docling-core 2.95.0` geprüft. Bindend für
Abschnitt P1.

| Sachverhalt | Folge |
|---|---|
| `export_to_markdown()` verwendet standardmäßig `ImageRefMode.PLACEHOLDER` | Ohne ausdrückliches `image_mode=REFERENCED` erscheint jede Abbildung als `<!-- image -->`, auch wenn ein gültiger Bildverweis am Element hängt |
| `ImageRef.pil_image` lädt eine `Path`- oder `file://`-URI beim Zugriff nach | Ein PNG auf der Platte ist für docling ein vollwertiges Bild; es muss nicht in den Speicher gezogen werden |
| `save_as_markdown(datei, artifacts_dir=None, image_mode=REFERENCED)` legt ohne Angabe `<stamm>_artifacts` neben die Ausgabedatei, schreibt die Bilder dorthin und macht die URIs relativ zur Ausgabedatei | Die gewünschte Bauform ist nativ vorhanden |
| Dabei wird in `image_<lfd:06>_<hexhash>.png` umbenannt | Sprechende Dateinamen überleben diesen Weg nicht (Entscheidung D1) |
| Der Serializer erzeugt intern die Marke `#_#_DOCLING_DOC_PAGE_BREAK_{vorher}_{nachher}_#_#` und ersetzt sie in `MarkdownDocSerializer.serialize_doc` durch einen konstanten Platzhalter | Die Seitenzahlen sind vorhanden und gehen an genau dieser Stelle verloren. Eine Unterklasse mit überschriebenem `serialize_doc` holt sie zurück; das ist der vorgesehene Erweiterungspunkt |
| `prov[].page_no` steht an jedem Element, `pages` am Dokument | Im JSON ist die Seitenangabe bereits vollständig |
| `DocumentOrigin(mimetype, binary_hash, filename, uri)` ist der Standardplatz für die Quellidentität | Trägt den Originalnamen durch jede Weitergabe, unabhängig von Ordnerkonventionen |
| `MarkdownTableSerializer` wertet `image_mode` nicht aus | Tabellen als Bild sind nicht darstellbar. Ohne Belang, solange Tabellen als OTSL vorliegen |
| `save_as_html`, `save_as_doctags`, `save_as_yaml` stehen bereit | Weitere Ausgabeformate kosten je eine Zeile, sobald das Dokument stimmt |

---

## 5. Prioritäten

| Rang | Bündel | Warum hier |
|---|---|---|
| **P0** | Eingang und Ablage | Bestimmt jeden Pfad und jeden Verweis. Später gebaut hieße, P1 zweimal zu bauen |
| **P1** | Vollständige Ausgabe | Der Maßstab des Ziels, unmittelbar am Artefakt sichtbar |
| **P2** | Sprachliche Konsolidierung | Behebt eine Fehlerklasse, die die übrigen Stufen strukturell nicht sehen können |
| **P3** | Randfälle und Feinheiten | Zählen erst, wenn die Mitte steht |

---

## P0 — Eingang und Ablage

### P0.1 — Eingangsprüfung der Dateinamen

> Das System soll die Dateinamen im Eingangsordner vor jeder Verarbeitung
> prüfen und bei einem unbrauchbaren Namen mit einer benennenden Meldung
> anhalten.

Der Dateiname ohne Endung ist der Schlüssel des ganzen Laufs: Er wird zum
Ordnernamen, zum Bestandteil jedes Bilddateinamens und zum Ziel jedes relativen
Verweises im erzeugten Artefakt. Ein Name mit Leerzeichen erzeugt einen
Markdown-Link, der an der ersten Lücke abbricht; ein Name mit Umlauten erzeugt
je nach Dateisystem zwei verschiedene Byte-Folgen für dieselbe Datei.

Geprüft wird **nicht umgeschrieben**. Eine automatische Normalisierung erzeugt
Namen, die im Verzeichnis nicht wiederzufinden sind, und bei ähnlichen Dateien
lautlos eine Kollision. Die Korrektur ist ein Handgriff des Menschen.

**Regelwerk:**

| Prüfung | Zulässig | Warum |
|---|---|---|
| Zeichenvorrat | `A–Z`, `a–z`, `0–9`, `-`, `_` | Leerzeichen brechen Markdown-Links, Klammern beenden sie, Nicht-ASCII wird zwischen Dateisystemen unterschiedlich kodiert |
| Erstes Zeichen | Buchstabe oder Ziffer | Ein führender Punkt oder Bindestrich wird von Werkzeugen als Option oder als verborgene Datei gelesen |
| Länge des Stamms | höchstens 48 Zeichen | siehe Rechnung unten |
| Endung | genau `.pdf`, kleingeschrieben | |
| Eindeutigkeit | keine zwei Stämme, die sich nur in der Groß-/Kleinschreibung unterscheiden | Windows und macOS unterscheiden sie nicht; ein Lauf würde ein Ergebnis überschreiben |
| Reservierte Namen | nicht `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9` | unter Windows nicht als Dateiname belegbar |

**Zur Länge:** Der längste abgeleitete Pfad ist
`data/processed/<dok>/<dok>_artifacts/<dok>_0221_11_footer_image.png`. Der Name
steckt dreimal darin, dazu rund 52 feste Zeichen. Bei einer Pfadgrenze von 260
Zeichen unter Windows und einem Projektordner von etwa 60 Zeichen bleiben rund
148 Zeichen für die drei Vorkommen, also 48 je Name. Die Zahl ist damit
begründet und nicht gesetzt.

**Verhalten:** Die Prüfung läuft über die **ganze** Liste und meldet **alle**
Beanstandungen auf einmal, mit Dateiname, Grund und einem Vorschlag für einen
zulässigen Namen. Erst danach hält sie an. Eine Prüfung, die beim ersten Fehler
abbricht, zwingt bei zehn Dateien zu zehn Durchläufen.

### P0.2 — Mehrere Dokumente in einem Lauf

> Das System soll die PDF-Dateien im Eingangsordner erfassen, als Arbeitsliste
> führen und nacheinander vollständig verarbeiten.

- Erfassung ohne Rekursion in Unterordner, stabil sortiert.
- Eine Schleife über die Liste; die Stufenlogik je Dokument bleibt unverändert.
- Fortschritt und Fehler werden je Dokument geführt. Ein gescheitertes Dokument
  beendet den Lauf nicht, sondern wird vermerkt und übersprungen.

### P0.3 — Der Dokumentname trägt durch

> Der geprüfte Dateiname ohne Endung soll durchgängiger Schlüssel sein: in
> Ordnernamen, in Dateinamen der Zwischenergebnisse und in den Verweisen des
> erzeugten Artefakts.

Nach P0.1 ist der Name bereits zulässig, eine Umformung entfällt.

### P0.4 — Das Dokument trägt seine Herkunft

> Das kanonische Dokument soll die Quelldatei benennen: Dateiname, MIME-Typ und
> Binärhash.

Damit ordnet ein Abnehmer ein Artefakt seiner Quelle zu, ohne die
Ordnerkonvention dieser Pipeline zu kennen. Der Binärhash unterscheidet zudem
zwei Auflagen unter gleichem Namen.

### P0.5 — Eine Ablagekonvention

```
data/
├── raw/<dok>.pdf                       Quelle, wird nie überschrieben
├── interim/
│   ├── befunde/<dok>/<seite:04d>.json  ein Befund je Seite
│   ├── ausschnitte/<dok>/…png          Bildblöcke aus Stufe 2
│   └── kontrolle/                      Overlay-Bilder zur Sichtprüfung
└── processed/<dok>/
    ├── <dok>.json                      kanonisches Dokument
    ├── <dok>.md                        abgeleitete Ausgabe
    └── <dok>_artifacts/…png            Abbildungen des Artefakts
```

Der Ordner **je Dokument** unterhalb von `processed` ist keine Ordnungsliebe:
Eine relative Bild-URI löst nur dann gleichzeitig aus dem JSON und aus dem
Markdown auf, wenn beide im selben Verzeichnis liegen. Andernfalls braucht
dasselbe Bild zwei verschiedene URIs.

Pfade werden an einer Stelle festgelegt und von dort bezogen. Ein zweiter
Pfadsatz im Steuerungsnotebook ist ausgeschlossen.

### P0.6 — Wiederaufsetzen auf Dokumentebene

> Bricht ein Lauf ab, soll das System beim Wiederaufsetzen abgeschlossene
> Dokumente überspringen, ohne jede Seitendatei einzeln zu öffnen.

Das seitenweise Wiederaufsetzen besteht bereits; es fehlt der Blick von oben.

---

## P1 — Die Ausgabe vollständig machen

### P1.1 — Abbildungen erscheinen an ihrer Stelle

> Das System soll jede erkannte Abbildung im kanonischen Dokument und in der
> Markdown-Ausgabe an ihrer Fundstelle als auflösbaren Verweis führen.

Der Kern ist die ausdrückliche Angabe des Bildmodus. Der Aufwand steckt in der
Namens- und Pfadfrage (D1) und darin, dass Bild- und Textausgabe denselben
Bezugspunkt brauchen (P0.5).

### P1.2 — Der Bildordner liegt neben dem Dokument, die Verweise sind relativ

> Verweise auf Abbildungen sollen relativ zum Dokument stehen, damit das
> Dokumentverzeichnis als Ganzes verschiebbar bleibt.

Absolute Pfade wären der bequemere und der falsche Weg: Ein Artefakt, das nur
auf dem erzeugenden Rechner auflöst, ist kein Austauschformat.

### P1.3 — Diagramme tragen ebenfalls ein Bild

Ein Diagramm wird derzeit nur mit seiner Datenreihe angelegt, ohne Bildverweis.
Im Markdown ergibt das eine Tabelle ohne Diagramm. Derselbe Handgriff wie P1.1.

### P1.4 — Seitenangabe im Markdown

> Die Ausgabe soll an jedem Seitenwechsel die Seite des Quelldokuments nennen.

Eine Unterklasse des Markdown-Serializers mit überschriebenem `serialize_doc`,
die die Seitenzahlen aus der Umbruchmarke in die Ausgabe schreibt. Form noch
offen (D3). Im JSON ist nichts zu tun.

### P1.5 — Weitere Ausgabeformate

Eine HTML-Fassung mit denselben Bildern kostet eine Zeile und macht Layouttreue
schneller beurteilbar als das Markdown. Sinnvoll erst nach P1.1.

---

## P2 — Sprachliche Konsolidierung

### P2.1 — Ein stärkeres Modell räumt auf, nachvollziehbar

> Das System soll das erzeugte Dokument einem größeren lokal betriebenen
> Sprachmodell vorlegen, das Schreib- und Grammatikfehler sowie sprachliche
> Brüche beseitigt, und jede Änderung ausweisen.

**Warum es diese Stufe braucht:** Das Erkennungsmodell arbeitet zeichenweise und
prüft nicht auf sprachliche Wohlgeformtheit. Die dabei entstehenden Fehler sind
aus der Pipeline heraus unsichtbar, weil keine Instanz widerspricht. Ein Modell
mit Sprachverständnis ist diese Instanz.

**Randbedingungen:**

- Seitengrenzen und Provenienz jedes Elements bleiben unverändert (R1).
- Kein stilles Umschreiben (R4): Jede Änderung wird als Paar (vorher, nachher)
  festgehalten, prüfbar und rücknehmbar.
- Der Eingriff bleibt auf Sprache begrenzt. Keine Umstrukturierung, keine
  Ergänzung von Inhalt, keine Änderung von Zahlen, Formeln oder Tabellendaten.
- Deterministischer Aufruf (`temperature=0`).

**Offen:** Modell (Gemma 4 12B, Qwen3.8 27B), Eingabeeinheit (Element, Seite,
Kapitel) und die Einordnung in die Stufenfolge (D4).

---

## P3 — Randfälle und Feinheiten

Nachrangig. Diese Punkte sind Details am Rand eines Artefakts, dessen Mitte
zuerst stehen muss.

| # | Punkt |
|---|---|
| P3.1 | Wächter gegen unplausible Überschriften: Ein als Überschrift erkannter Block über einer Zeichengrenze wird als Text abgelegt und gemeldet |
| P3.2 | Bild- und Tabellenunterschriften den zugehörigen Objekten zuordnen. Braucht ein Bildmodell, weil die Platzierung eine Gestaltungsentscheidung des jeweiligen Buchs ist und sich nicht in Schwellen fassen lässt |
| P3.3 | Kästen ohne eigene Klasse („Definition", „Für die Praxis") über Vektorobjekte der PDF-Ebene als Region nachweisen |
| P3.4 | Eingezogene Zwischentitel, die fett am Absatzanfang stehen und keine eigene Region bilden |
| P3.5 | Verschachtelung: ein Kasten mit inneren Spalten |
| P3.6 | Abgesetzte Formeln dem einführenden Absatz zuordnen. Sinnvoll erst an einem formelreichen Dokument beurteilbar |
| P3.7 | Wiederholungsschleifen des Erkennungsmodells erkennen und melden |
| P3.8 | Durchsatz: Verzicht auf Modellaufrufe für Kopf- und Fußzeilen (rund 15 % der Blöcke), parallele Anfragen. Wird zur Frage, sobald ein Stapel statt eines Dokuments läuft |

---

## 6. Abgrenzung

Nicht Gegenstand dieser Arbeit. Steht hier, damit es nicht unversehens
hineinwächst.

| Nicht enthalten | Grund |
|---|---|
| Chunking, Vektorindex, Retrieval-Messung | Ergibt sich aus einem vollständigen Artefakt und wird mit den Werkzeugen des Ökosystems gegen das fertige Dokument gemacht, nicht in dieser Pipeline |
| Zusammenfassen eines Absatzes über eine Seitengrenze hinweg | R1 |
| Rückführung einer Formel an ihre Stelle im laufenden Satz | R1; die Position im erkannten Text ist zudem nicht bekannt |
| Beschreibung von Bildinhalten, Typisierung von Kästen durch ein Modell | Setzt P1 und P2 voraus |

---

## 7. Offene Entscheidungen

| # | Entscheidung | Vorschlag |
|---|---|---|
| **D1** | **Bildnamen.** Der Standardweg benennt beim Export in `image_<lfd>_<hash>.png` um. Alternativ schreiben wir die Bilder mit sprechenden Namen selbst in den Artefaktordner und setzen die URI relativ | Eigene Namen nach `<dok>_<seite:04d>_<block:02d>_<klasse>.png`. Im Ordner für einen Menschen lesbar, eindeutig, und die Seitenzuordnung steht im Namen. Preis: Wir schreiben die Datei selbst, statt es der Bibliothek zu überlassen |
| **D2** | **Form der Seitenangabe im Markdown:** unsichtbarer Kommentar `<!-- Seite 42 -->`, sichtbare Trennlinie, oder HTML-Anker `<a id="seite-42"></a>` | Kommentar und Anker zusammen. Der Kommentar stört das Lesen nicht, der Anker macht Verweise möglich |
| **D3** | **Vorhandene Zwischenergebnisse:** nach dem Ablageumbau umschreiben oder neu erzeugen | Neu erzeugen. Ein Wanderungsskript ist einmaliger Code für einen einmaligen Zweck, und Bildverweise stehen relativ in den Befunden — ein unvollständiger Umzug ergibt leere Verweise ohne Fehlermeldung |
| **D4** | **Wo die sprachliche Konsolidierung ansetzt:** an den Seitenbefunden vor dem kanonischen Dokument, oder am fertigen Dokument danach | Zu besprechen. Am Befund bliebe die Provenienz trivial; am Dokument hätte das Modell den Textzusammenhang, den Grammatik voraussetzt. Bei der zweiten Lösung braucht es eine Regel, wie eine Änderung auf das Ursprungselement zurückgeschrieben wird |
| **D5** | **Verankerung:** Soll jedes Element ausweisen, ob eine zweite unabhängige Quelle es bestätigt, und andernfalls als unbestätigt gelten? | Zu besprechen. Der naheliegende zweite Zeuge, die Textebene des PDF, ist bei Scans mit fehlerhafter Texterkennung selbst unzuverlässig. Möglicherweise übernimmt P2.1 diese Rolle besser |

---

## 8. Reihenfolge

1. **D1 bis D3 entscheiden.** Ohne sie schreibt P1 Pfade fest, die P0 wieder aufbricht.
2. **P0** bauen: Eingangsprüfung, Dokumentenlauf, Ablage, Herkunft.
3. **Ein Dokument durchlaufen lassen** und die Ablage am Ergebnis prüfen.
4. **P1** bauen: Bilder, Diagrammbilder, Seitenangaben. Prüfstein ist das Markdown.
5. **Ein zweites, andersartiges Dokument** durchlaufen lassen. Erst dann ist die
   Behauptung, die Pipeline sei dokumentunabhängig, belegt und nicht nur beabsichtigt.
6. **D4 entscheiden**, dann **P2**.
7. **P3** in der Reihenfolge, in der die Artefakte es verlangen.
