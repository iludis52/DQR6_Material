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

## 2. Die Ausgangsannahme: unbrauchbare Eingaben sind der Normalfall

Diese Annahme trägt die gesamte Bauform und begründet die Randbedingungen
darunter.

Über die Qualität eines eingehenden PDF lässt sich nichts voraussetzen. Der Fall,
für den gebaut wird, ist nicht das saubere born-digital-Dokument, sondern:

- eine 1-Bit-Bitmap ohne Graustufen,
- schief eingezogen, mit ungleichmäßiger Helligkeit über die Fläche,
- ein Textlayer, der nur teilweise vorhanden und dort, wo er existiert,
  fehlerhaft ist,
- Textbestandteile, die als Vektorgrafik gesetzt sind und in keiner Textebene
  auftauchen.

Daraus folgt unmittelbar:

1. **Die Bildebene ist die einzige verlässliche Quelle.** Ein Verfahren, das die
   Textebene des PDF auswertet oder gegen sie abgleicht, prüft an einem Zeugen,
   der genau dann schweigt oder lügt, wenn es darauf ankommt.
2. **Layout wird detektiert, nicht ausgelesen.** Die Struktur entsteht aus einem
   Modell, das auf Seitenbildern arbeitet, weil im schlechten Fall nichts anderes
   da ist.
3. **Eine Triage nach dem Muster „Textebene vorhanden, also born-digital" ist
   ausgeschlossen.** Sie beantwortet die Frage, ob Text da ist, nicht die Frage,
   ob er stimmt.

---

## 3. Randbedingungen

Diese Punkte stehen nicht zur Abwägung. Sie gelten für jede Aufgabe unten.

| | Randbedingung | Grund |
|---|---|---|
| R1 | **Seitengrenzen werden nirgends aufgehoben.** Was auf einer Seite steht, bleibt dort | Jede Aussage im Ergebnis muss rückwärts einer Seite des Originals zurechenbar bleiben. Ein Element über zwei Seiten verliert diese Zurechenbarkeit für jeden Abnehmer, der nur die erste Seitenangabe liest |
| R2 | **Standardtreue vor Eigenbau.** Native Mechanismen des kanonischen Formats vor eigenen Konstruktionen, dokumentierte Erweiterungspunkte vor Eingriffen | Die späteren Abnehmer sind unbekannt. Was nicht vorhersehbar ist, wird durch Standardkonformität aufgefangen |
| R3 | **Konsequent schrittweise.** Jede Stufe liest ein abgelegtes Ergebnis und schreibt ein neues. Keine Stufe greift in die Ausgabe der vorigen ein, keine zwei Stufen werden zusammengelegt | Ein Zwischenstand, der auf der Platte liegt, ist prüfbar, wiederholbar und einzeln austauschbar. Zusammengelegte Schritte sind es nicht |
| R4 | **Deterministisches und Generatives bleiben getrennt.** Regelbasierte Stufen enthalten keine Modellaufrufe, Modellstufen treffen keine Strukturentscheidungen | Nur so bleibt der prüfbare Teil prüfbar |
| R5 | **Kein stilles Zurechtrücken.** Zweifelhafte Eingaben und zweifelhafte Ergebnisse werden gemeldet, nicht repariert | Ein Fehler, der sich selbst behebt, wiederholt sich unbemerkt |
| R6 | **Laufzeitumgebung:** Python 3.12, lokal betriebene Modelle über LM Studio (OpenAI-kompatibel, Port 1234). Kein Docker, kein WSL, kein vLLM. Zwei Arbeitsmaschinen: Windows mit 40 GB VRAM, Mac M4 Pro mit 24 GB | Das Material wird an Studierende ausgegeben; jede zusätzliche Installationsstufe ist nicht betreubar |
| R7 | **Ein Notebook steuert, die Module werden importiert.** Keine `.py` wird direkt gestartet | Das Arbeitsverzeichnis hängt sonst am Werkzeug: Der Jupyter-Kernel startet im Ordner der Datei, eine IDE im Workspace-Ordner |

---

## 4. Ausgangspunkt

Die Pipeline läuft in Stufen. Jede schreibt ihr Ergebnis, bevor die nächste
beginnt (R3).

| Stufe | Inhalt | Modell | Zustand |
|---|---|---|---|
| 1 | Layout-Erkennung: Seitenbild → verortete, typisierte, geordnete Blöcke | ONNX-Detektor (PP-DocLayoutV3) | läuft |
| 2 | Erkennung: Blöcke zusammenführen, Ausschnitte schneiden, Text füllen | PaddleOCR-VL-1.5 über LM Studio | läuft |
| 4a | Kanonisches Dokument: Entdopplung, Gliederungsebenen, Tabellen, Provenienz → `DoclingDocument` | keins | läuft |
| 5 | Sprachliche Konsolidierung des fertigen Dokuments | größeres lokales LLM | zu bauen (P2) |

Zwischenergebnisse liegen als ein Seitenbefund je Seite. Das kanonische Dokument
wird nach JSON und Markdown ausgegeben.

Was heute trägt: Fließtext, Überschriftenhierarchie, Tabellen, Formatierungen.
Was fehlt und diese Etappe bestimmt: Abbildungen erscheinen im Markdown nicht,
Seitenangaben fehlen dort, und der Lauf ist auf ein einzelnes fest benanntes
Dokument zugeschnitten.

---

## 5. Technische Grundlagen

Gegen die installierte Fassung `docling-core 2.95.0` **praktisch erprobt**, nicht
angenommen. Bindend für Abschnitt P1.

| Sachverhalt | Folge |
|---|---|
| `export_to_markdown()` verwendet standardmäßig `ImageRefMode.PLACEHOLDER` | Ohne ausdrückliches `image_mode=REFERENCED` erscheint jede Abbildung als `<!-- image -->`, auch wenn ein gültiger Bildverweis am Element hängt |
| `export_to_markdown(image_mode=REFERENCED)` gibt die am Element hinterlegte URI **unverändert** aus | Eigene, sprechende Dateinamen und relative Pfade überstehen den Export unversehrt. Erprobt: `![Image](Buch_artifacts/Buch_0000_03_image.png)` |
| `save_as_markdown(..., image_mode=REFERENCED)` dagegen kopiert die Bilder um und benennt sie in `image_<lfd:06>_<hexhash>.png` | Dieser Weg wird **nicht** benutzt. Markdown wird über `export_to_markdown` erzeugt und selbst geschrieben |
| `save_as_json` hat `EMBEDDED` als Standard | **Falle:** ohne ausdrückliches `image_mode=PLACEHOLDER` landet jede Abbildung als base64 im JSON. Mit `PLACEHOLDER` bleibt die relative URI stehen und die Datei schlank. Erprobt |
| `ImageRef.pil_image` lädt eine `Path`- oder `file://`-URI beim Zugriff nach | Ein PNG auf der Platte ist für die Bibliothek ein vollwertiges Bild; es muss nicht in den Speicher gezogen werden |
| Der Serializer erzeugt intern die Marke `#_#_DOCLING_DOC_PAGE_BREAK_{vorher}_{nachher}_#_#` und ersetzt sie in `MarkdownDocSerializer.serialize_doc` durch einen konstanten Platzhalter | Die Seitenzahlen sind vorhanden und gehen an genau dieser Stelle verloren. Eine Unterklasse mit überschriebenem `serialize_doc` holt sie zurück — acht Zeilen, der vorgesehene Erweiterungspunkt. Erprobt |
| `prov[].page_no` steht an jedem Element, `pages` am Dokument | Im JSON ist die Seitenangabe bereits vollständig |
| `DocumentOrigin(mimetype, binary_hash, filename, uri)` ist der Standardplatz für die Quellidentität | Trägt den Originalnamen durch jede Weitergabe, unabhängig von Ordnerkonventionen |
| `MarkdownTableSerializer` wertet `image_mode` nicht aus | Tabellen als Bild sind nicht darstellbar. Ohne Belang, solange Tabellen als OTSL vorliegen |
| `save_as_html`, `save_as_doctags`, `save_as_yaml` stehen bereit | Weitere Ausgabeformate kosten je eine Zeile, sobald das Dokument stimmt |

---

## 6. Prioritäten

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
Markdown-Link, der an der ersten Lücke abbricht; ein Name mit Umlauten erzeugt je
nach Dateisystem zwei verschiedene Byte-Folgen für dieselbe Datei.

Geprüft wird, **nicht umgeschrieben** (R5). Eine automatische Normalisierung
erzeugt Namen, die im Verzeichnis nicht wiederzufinden sind, und bei ähnlichen
Dateien lautlos eine Kollision. Die Korrektur ist ein Handgriff des Menschen.

**Regelwerk:**

| Prüfung | Zulässig | Warum |
|---|---|---|
| Zeichenvorrat | `A–Z`, `a–z`, `0–9`, `-`, `_` | Leerzeichen brechen Markdown-Links, Klammern beenden sie, Nicht-ASCII wird zwischen Dateisystemen unterschiedlich kodiert |
| Erstes Zeichen | Buchstabe oder Ziffer | Ein führender Punkt oder Bindestrich wird von Werkzeugen als verborgene Datei oder als Option gelesen |
| Länge des Stamms | höchstens 48 Zeichen | siehe Rechnung unten |
| Endung | genau `.pdf`, kleingeschrieben | |
| Eindeutigkeit | keine zwei Stämme, die sich nur in der Groß-/Kleinschreibung unterscheiden | Windows und macOS unterscheiden sie nicht; ein Lauf überschriebe das Ergebnis des anderen |
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

### P0.2 — Technische Prüfung der Eingangsdateien

> Das System soll im selben Durchgang prüfen, ob jede Datei überhaupt zu
> verarbeiten ist, und andernfalls mit derselben Meldung anhalten.

Geprüft wird ausschließlich, was **ohne Zugriff auf Seiteninhalte** zu haben ist:

| Prüfung | Anlass |
|---|---|
| Datei lässt sich öffnen und ist ein PDF | beschädigte oder falsch benannte Dateien |
| nicht passwortgeschützt (`needs_pass`, `is_encrypted`) | ein geschütztes Dokument scheitert sonst erst beim Rendern |
| Seitenzahl größer null | leere Container aus Scan-Software |

**Kosten:** gemessen 0,25 ms für ein Dokument mit 222 Seiten. Es wird nur der
Seitenbaum gelesen, keine Seite gerendert. Damit ist die Prüfung gegenüber der
Verarbeitung, die je Dokument dreiviertel Stunden braucht, kostenlos.

**Nicht enthalten:** eine Integritätsprüfung, die jede Seite anfasst. Sie kostet
in der Größenordnung eines Layoutlaufs und beantwortet eine Frage, die spätestens
Stufe 1 ohnehin seitenweise beantwortet — dort mit dem eingebauten Übergehen
gescheiterter Seiten statt mit einem Abbruch am Eingang.

### P0.3 — Mehrere Dokumente in einem Lauf

> Das System soll die PDF-Dateien im Eingangsordner erfassen, als Arbeitsliste
> führen und nacheinander vollständig verarbeiten.

- Erfassung ohne Rekursion in Unterordner, stabil sortiert.
- Eine Schleife über die Liste; die Stufenlogik je Dokument bleibt unverändert.
- Fortschritt und Fehler werden je Dokument geführt. Ein gescheitertes Dokument
  beendet den Lauf nicht, sondern wird vermerkt und übersprungen.

### P0.4 — Der Dokumentname trägt durch

> Der geprüfte Dateiname ohne Endung soll durchgängiger Schlüssel sein: in
> Ordnernamen, in Dateinamen der Zwischenergebnisse und in den Verweisen des
> erzeugten Artefakts.

Nach P0.1 ist der Name bereits zulässig; eine Umformung entfällt.

### P0.5 — Das Dokument trägt seine Herkunft

> Das kanonische Dokument soll die Quelldatei benennen: Dateiname, MIME-Typ und
> Binärhash.

Damit ordnet ein Abnehmer ein Artefakt seiner Quelle zu, ohne die
Ordnerkonvention dieser Pipeline zu kennen. Der Binärhash unterscheidet zudem
zwei Fassungen unter gleichem Namen.

### P0.6 — Eine Ablagekonvention

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
    ├── <dok>_k.json                    sprachlich konsolidierte Fassung (P2)
    ├── <dok>_k.md                      dieselbe als Markdown
    └── <dok>_artifacts/…png            Abbildungen, von beiden Fassungen genutzt
```

Der Ordner **je Dokument** unterhalb von `processed` ist keine Ordnungsliebe:
Eine relative Bild-URI löst nur dann gleichzeitig aus dem JSON und aus dem
Markdown auf, wenn beide im selben Verzeichnis liegen. Der Nebeneffekt ist
willkommen: Die konsolidierte Fassung liegt im selben Ordner und greift auf
denselben Bildbestand zu, ohne dass eine einzige Datei verdoppelt wird.

Pfade werden an einer Stelle festgelegt und von dort bezogen. Ein zweiter
Pfadsatz im Steuerungsnotebook ist ausgeschlossen.

### P0.7 — Wiederaufsetzen auf Dokumentebene

> Bricht ein Lauf ab, soll das System beim Wiederaufsetzen abgeschlossene
> Dokumente überspringen, ohne jede Seitendatei einzeln zu öffnen.

Das seitenweise Wiederaufsetzen besteht bereits; es fehlt der Blick von oben.

### P0.8 — Vorhandene Zwischenergebnisse neu erzeugen

Nach dem Ablageumbau werden Befunde und Ausschnitte neu erzeugt, nicht
umgeschrieben. Bildverweise stehen relativ in den Befunden; ein unvollständiger
Umzug ergäbe leere Verweise ohne jede Fehlermeldung. Ein Wanderungsskript wäre
zudem einmaliger Code für einen einmaligen Zweck.

---

## P1 — Die Ausgabe vollständig machen

### P1.1 — Abbildungen erscheinen an ihrer Stelle

> Das System soll jede erkannte Abbildung im kanonischen Dokument und in der
> Markdown-Ausgabe an ihrer Fundstelle als auflösbaren Verweis führen.

Ablauf, vollständig automatisch und ohne manuellen Anteil:

1. Der Bildausschnitt wird beim Anlegen des kanonischen Dokuments unter dem Namen
   `<dok>_<seite:04d>_<block:02d>_<klasse>.png` nach `<dok>_artifacts/` geschrieben.
2. Am Element wird ein Bildverweis mit der **relativen** URI
   `<dok>_artifacts/<name>.png` gesetzt.
3. Markdown entsteht über `export_to_markdown(image_mode=REFERENCED)`; die Datei
   wird selbst geschrieben. Der Weg über `save_as_markdown` scheidet aus, weil er
   umbenennt.
4. JSON entsteht über `save_as_json(image_mode=PLACEHOLDER)`, damit die URI stehen
   bleibt und keine base64-Daten hineinlaufen.

Der Name ist so gewählt, dass er im Verzeichnis für einen Menschen lesbar ist,
eindeutig bleibt und die Seitenzuordnung mitführt.

### P1.2 — Der Bildordner liegt neben dem Dokument, die Verweise sind relativ

> Verweise auf Abbildungen sollen relativ zum Dokument stehen, damit das
> Dokumentverzeichnis als Ganzes verschiebbar bleibt.

Absolute Pfade wären der bequemere und der falsche Weg: Ein Artefakt, das nur auf
dem erzeugenden Rechner auflöst, ist kein Austauschformat.

### P1.3 — Diagramme tragen ebenfalls ein Bild

Ein Diagramm wird derzeit nur mit seiner Datenreihe angelegt, ohne Bildverweis.
Im Markdown ergibt das eine Tabelle ohne Diagramm. Derselbe Handgriff wie P1.1.

### P1.4 — Seitenangabe im Markdown

> Die Ausgabe soll an jedem Seitenwechsel die Seite des Quelldokuments nennen.

Ausgegeben wird an der Umbruchstelle:

```
<!-- Seite 42 --><a id="seite-42"></a>
```

Der Kommentar stört das Lesen nicht und ist maschinell auswertbar, der Anker
macht die Seite verlinkbar. Umgesetzt als Unterklasse des Markdown-Serializers
mit überschriebenem `serialize_doc`, die die Zahlen aus der Umbruchmarke
übernimmt. Im JSON ist nichts zu tun.

### P1.5 — Weitere Ausgabeformate

Eine HTML-Fassung mit denselben Bildern kostet eine Zeile und macht Layouttreue
schneller beurteilbar als das Markdown. Sinnvoll erst nach P1.1.

---

## P2 — Sprachliche Konsolidierung (Stufe 5)

### P2.1 — Ein stärkeres Modell räumt auf, in einer eigenen Stufe

> Das System soll das fertige kanonische Dokument einem größeren lokal
> betriebenen Sprachmodell vorlegen, das Schreib-, Grammatik- und
> Konsistenzfehler beseitigt, und das Ergebnis als eigene Fassung neben dem
> Original ablegen.

**Warum es diese Stufe braucht:** Das Erkennungsmodell arbeitet zeichenweise und
prüft nicht auf sprachliche Wohlgeformtheit. Die dabei entstehenden Fehler sind
aus der Pipeline heraus unsichtbar, weil ihr keine Instanz widerspricht, die
Sprache versteht. Ein größeres Modell ist diese Instanz.

**Bauform:**

- Eine eigene Stufe nach 4a (R3). Sie liest `<dok>.json` und schreibt
  `<dok>_k.json` sowie `<dok>_k.md`. In Stufe 4a wird nichts geändert.
- Das Suffix `_k` kennzeichnet, dass ein Sprachmodell daran gearbeitet hat.
- **Beide Fassungen bleiben nebeneinander liegen.** Der Vergleich der zwei
  Dokumente ist der Nachweis darüber, was das Modell getan hat; ein zusätzliches
  Änderungsprotokoll ist dafür nicht nötig, weil es sich jederzeit aus dem
  Vergleich herstellen lässt.
- Der Bildbestand wird nicht verdoppelt: `<dok>_k.md` verweist auf denselben
  Ordner `<dok>_artifacts/`.

**Eingabeeinheit: eine Seite je Aufruf.** Ein einzelnes Element ist häufig ein
halber Satz, dem der Zusammenhang für eine Grammatikentscheidung fehlt. Ein
ganzes Kapitel überschreitet, was zuverlässig in einem Durchgang bearbeitet wird,
und macht die Rückzuordnung der Antwort zu den Ursprungselementen fehleranfällig.
Die Seite ist zugleich die Einheit, in der alles andere ohnehin abgelegt ist, und
sie hält R1 ohne Zusatzaufwand ein.

Trägt der seitenweise Zuschnitt in der Praxis nicht, ist das keine Fehlplanung,
sondern der Anlass für eine Verbesserungsschleife an dieser Stufe: Der Zuschnitt
wird angepasst und erneut an einem Dokument erprobt, dessen Fehler bekannt sind.
Die Stufe ist dafür eigens so gebaut, dass sie nichts als ihre eigene Ausgabe
verändert und deshalb beliebig oft neu laufen kann.

**Grenzen des Eingriffs:**

- Seitengrenzen und Provenienz jedes Elements bleiben unverändert (R1). Die
  Struktur des Dokuments bleibt unverändert: keine Elemente entfernt, keine
  hinzugefügt, keine umgeordnet.
- Der Eingriff bleibt auf Sprache begrenzt. Keine Ergänzung von Inhalt, keine
  Änderung von Zahlen, Formeln oder Tabellendaten.
- Deterministischer Aufruf (`temperature=0`).

**Kandidaten:** Gemma 4 12B, Qwen3.8 27B. Beide laufen lokal in LM Studio.

---

## P3 — Randfälle und Feinheiten

Nachrangig. Details am Rand eines Artefakts, dessen Mitte zuerst stehen muss.

| # | Punkt |
|---|---|
| P3.1 | Wächter gegen unplausible Überschriften: Ein als Überschrift erkannter Block über einer Zeichengrenze wird als Text abgelegt und gemeldet |
| P3.2 | Bild- und Tabellenunterschriften den zugehörigen Objekten zuordnen. Braucht ein Bildmodell, weil die Platzierung eine Gestaltungsentscheidung des jeweiligen Dokuments ist und sich nicht in Schwellen fassen lässt |
| P3.3 | Kästen ohne eigene Klasse („Definition", „Für die Praxis") als Region nachweisen |
| P3.4 | Eingezogene Zwischentitel, die fett am Absatzanfang stehen und keine eigene Region bilden |
| P3.5 | Verschachtelung: ein Kasten mit inneren Spalten |
| P3.6 | Abgesetzte Formeln dem einführenden Absatz zuordnen. Sinnvoll erst an einem formelreichen Dokument beurteilbar |
| P3.7 | Wiederholungsschleifen des Erkennungsmodells erkennen und melden |
| P3.8 | Durchsatz: Verzicht auf Modellaufrufe für Kopf- und Fußzeilen (rund 15 % der Blöcke), parallele Anfragen. Wird zur Frage, sobald ein Stapel statt eines Dokuments läuft |
| P3.9 | Vorverarbeitung schwieriger Scans: Schieflage ausgleichen, Helligkeit vereinheitlichen. Erst zu bewerten, wenn ein Dokument dieser Art die Pipeline sichtbar überfordert |

---

## 7. Abgrenzung

Nicht Gegenstand dieser Arbeit. Steht hier, damit es nicht unversehens
hineinwächst.

| Nicht enthalten | Grund |
|---|---|
| Chunking, Vektorindex, Retrieval-Messung | Ergibt sich aus einem vollständigen Artefakt und wird mit den Werkzeugen des Ökosystems gegen das fertige Dokument gemacht, nicht in dieser Pipeline |
| Verankerung gegen eine zweite Quelle, Kennzeichnung unbestätigter Elemente | Es gibt keine zweite verlässliche Quelle. Die Textebene des PDF ist genau in den Fällen unbrauchbar, in denen eine Bestätigung etwas wert wäre (Abschnitt 2) |
| Triage nach vorhandener Textebene | dieselbe Begründung |
| Zusammenfassen eines Absatzes über eine Seitengrenze hinweg | R1 |
| Rückführung einer Formel an ihre Stelle im laufenden Satz | R1; die Position im erkannten Text ist zudem nicht bekannt |
| Beschreibung von Bildinhalten, Typisierung von Kästen durch ein Modell | Setzt P1 und P2 voraus |

---

## 8. Arbeitsweise

Alle Entscheidungen dieser Liste sind getroffen. Was sich in der Umsetzung als
untragfähig erweist, wird nicht durch einen Nachtrag geflickt, sondern führt zu
einer Verbesserungsschleife: Der betroffene Punkt wird in diesem Dokument neu
entschieden und die Stufe erneut erprobt.

Die Bauform ist darauf ausgelegt. Weil jede Stufe ein abgelegtes Ergebnis liest
und ein neues schreibt (R3), lässt sich jede einzeln wiederholen, austauschen und
gegen ihr eigenes voriges Ergebnis vergleichen, ohne die übrigen anzufassen.

---

## 9. Reihenfolge

1. **P0** bauen: Eingangsprüfung (Name und Datei), Dokumentenlauf, Ablage, Herkunft.
2. **Ein Dokument durchlaufen lassen** und die Ablage am Ergebnis prüfen.
3. **P1** bauen: Bilder, Diagrammbilder, Seitenangaben. Prüfstein ist das Markdown.
4. **Ein zweites, andersartiges Dokument** durchlaufen lassen, möglichst eines aus
   der schlechten Sorte nach Abschnitt 2. Erst dann ist die Behauptung, die
   Pipeline sei dokumentunabhängig, belegt und nicht nur beabsichtigt.
5. **P2** bauen: die Konsolidierungsstufe, an einem Dokument, dessen Fehler bekannt sind.
6. **P3** in der Reihenfolge, in der die Artefakte es verlangen.
