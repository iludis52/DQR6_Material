# CLAUDE.md

Projektanweisungen für agentische Arbeit in diesem Repository. Diese Datei wird
bei jedem Start gelesen und gilt für die gesamte Sitzung.

## Worum es geht

Eine Pipeline, die beliebige PDF-Dokumente in ein strukturiertes, für Menschen
lesbares und allgemein weiterverarbeitbares Ergebnis überführt. Kanonisches
Zielformat ist `DoclingDocument`; daraus werden Markdown und weitere Fassungen
abgeleitet.

Das Projekt dient zugleich als Lehrbeispiel. Die Entstehungsgeschichte ist Teil
des Ergebnisses: Änderungen an Spezifikation und Plan werden mitversioniert, nicht
nachträglich glattgezogen.

## Die drei Dokumente

| Datei | Inhalt | Wann maßgeblich |
|---|---|---|
| `spec.md` | rein fachlich: Anforderungen `SR-nn`, Invarianten `INV-n`, Abnahmekriterien `AK-n` | Was gebaut wird. Wird nicht durch Code geändert |
| `plan.md` | Technikstack, Modulschnitt, Ablage, geprüftes Bibliotheksverhalten | Wie gebaut wird |
| `tasks.md` | Aufgaben `T0`–`T10` der laufenden Etappe, je mit Prüfung und Abnahme | In welcher Reihenfolge |

Lies alle drei, bevor du Code änderst. Ein Widerspruch zwischen Code und
Dokument ist ein Befund, kein Anlass zum stillen Anpassen: Melde ihn.

## Invarianten

Verletzt eine Änderung eine dieser Regeln, ist sie unabhängig von ihrer sonstigen
Güte falsch.

1. **Seitengrenzen werden nicht aufgehoben.** Jedes Element bleibt einer Seite des
   Quelldokuments zugeordnet.
2. **Jede Stufe liest ein abgelegtes Ergebnis und schreibt ein neues.** Keine Stufe
   verändert die Ausgabe einer vorigen. Keine zwei Stufen werden zusammengelegt.
3. **Regelgebundenes und Modellgestütztes bleiben getrennt.** Ein regelgebundener
   Schritt ruft kein Modell auf, ein Modellschritt trifft keine Strukturentscheidung.
4. **Kein stilles Zurechtrücken.** Zweifelhafte Eingaben und Ergebnisse werden
   gemeldet, nicht repariert. Kein automatisches Umbenennen, kein stillschweigender
   Ersatzwert, kein `except: pass`.
5. **Das Quelldokument unter `data/raw/` wird nie verändert.**

## Harte Projektregeln

- **Pfade entstehen ausschließlich in `pfade.py`.** Kein anderes Modul und kein
  Notebook bildet einen Pfad oder trägt ein Verzeichnisliteral. Diese Regel wird
  durch einen Test überwacht; umgehe ihn nicht, sondern erweitere `pfade.py`.
- **`.py`-Dateien werden nie direkt gestartet.** Einstiegspunkt ist das
  Steuerungsnotebook, die Module werden importiert. Grund: Das Arbeitsverzeichnis
  hängt sonst am Werkzeug. Schlage keine Änderung an der IDE-Konfiguration vor.
- **`docling-core` ist auf eine geprüfte Fassung gepinnt.** Die Aussagen in
  `plan.md` Abschnitt 2 gelten für genau diese Fassung. Hebe die Bindung nicht an,
  ohne die dortigen Punkte erneut praktisch zu prüfen.
- **Deutsch durchgängig:** Bezeichner, Kommentare, Docstrings, Meldungen,
  Commit-Nachrichten.
- Kommentare begründen, warum etwas so ist, und wiederholen nicht, was der Code
  ohnehin sagt.

## Bibliotheksfallen, an denen der naheliegende Weg der falsche ist

Praktisch geprüft. Ausführlich in `plan.md` Abschnitt 2.

- `save_as_markdown(image_mode=REFERENCED)` **benennt Bilder um.** Markdown wird
  deshalb über `export_to_markdown` beziehungsweise den eigenen Serializer erzeugt
  und selbst geschrieben.
- `save_as_json` hat **`EMBEDDED` als Vorgabe** und schreibt sonst jedes Bild als
  base64 ins JSON. Immer `image_mode=PLACEHOLDER` übergeben.
- Seitenumbruchmarken entstehen nur, wenn `page_break_placeholder` **nicht `None`**
  ist. Der Wert selbst ist gleichgültig, weil der eigene Serializer ihn ersetzt.
- Der Markdown-Serializer berücksichtigt vorgabegemäß **nur `BODY`**. Wir geben
  `layers={BODY, NOTES}` an, sonst fällt die Marginalspalte lautlos aus der Ausgabe.
- `TextItem` lässt nur 14 der 31 `DocItemLabel` zu. Zulässigkeit aus dem Modell
  auslesen, nicht erinnern.
- `add_page()` zählt ab 1, PyMuPDF ab 0.

## Arbeitsweise

- **Eine Aufgabe je Auftrag.** Arbeite `T0`, dann `T1`, und so fort. Nimm dir nicht
  mehrere Aufgaben auf einmal vor, auch wenn sie klein wirken.
- **Prüfung vor Umsetzung.** Schreibe zuerst die in der Aufgabe genannte Prüfung,
  lass sie fehlschlagen, und baue dann den Code, der sie besteht. Eine Prüfung, die
  eine fertige Implementierung bestätigt, ist wertlos.
- **`T0` zuerst und vollständig.** Der Prüfbestand ist die Grundlage aller weiteren
  Abnahmen. Ohne ihn ist die Etappe formal grün und inhaltlich nichts wert.
- **Checkpoint-Commit nach jeder Aufgabe**, mit der Aufgabennummer in der Nachricht.
- Für die laufende Etappe werden weder das ONNX-Modell noch LM Studio gebraucht.
  Detektor und Erkenner werden als Argument übergeben und im Test durch Attrappen
  ersetzt.
- Ist eine Aufgabe unterbestimmt, frage nach, statt eine Annahme zu treffen und
  weiterzubauen.

## Ausdrücklich nicht zu tun

- Zerlegung in Abschnitte, Einbettung, Suchindex, Retrieval-Messung. Das gehört zu
  den Abnehmern des Ergebnisses, nicht in dieses Projekt.
- Die Textebene des PDF als Quelle oder als Gegenprobe verwenden. Es ist mit
  Dokumenten zu rechnen, deren Textebene fehlt oder falsch ist; dann ist ein
  Abgleich gegen sie schlimmer als keiner.
- Eine Fallunterscheidung nach dem Vorhandensein einer Textebene einbauen.
- Absätze über Seitengrenzen zusammenfassen.
- Docker, WSL, vLLM oder PaddlePaddle einführen.
- Aufgaben späterer Etappen vorziehen. `tasks.md` nennt am Ende, was nicht
  dazugehört.

## Umgebung

Python 3.12. Zwei Arbeitsmaschinen: Windows mit Dual-GPU (40 GB VRAM) und ein
Mac M4 Pro mit 24 GB. Lokale Modelle laufen über LM Studio auf Port 1234 über die
OpenAI-kompatible Schnittstelle. Ausführungsanbieter für ONNX werden gegen die
tatsächlich verfügbaren gefiltert; fest verdrahtetes CUDA scheitert auf dem Mac.
