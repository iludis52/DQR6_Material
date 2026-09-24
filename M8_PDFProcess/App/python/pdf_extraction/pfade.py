"""Einzige Stelle, die aus einem Dokumentnamen Pfade ableitet (plan.md 4.2).

Kein anderes Modul und kein Notebook bildet einen Pfad oder trägt ein
Verzeichnisliteral (CLAUDE.md, harte Projektregel). Wer einen neuen Ort
braucht, erweitert dieses Modul statt die Regel zu umgehen.

`bildname` liefert für den Zwischenbestand (`ausschnitt`) und den
Ergebnisbestand (`artefakt`) denselben Namen: die Kopie in Stufe 4a ist
damit reines Umkopieren, kein Umbenennen. `artefakt_relativ` ist der
einzige Weg, eine Bild-URI zu bilden – relativ zum Dokumentordner, weil
dort sowohl `<dok>.json` als auch `<dok>.md` liegen (SR-21).

Legt selbst kein Verzeichnis an; das Anlegen bleibt Sache des Schreibenden
(bzw. von `pipeline.arbeitsbereich`, das die ganze Struktur verwaltet).

Alle Pfade hängen am Projekt-Root, abgeleitet aus der Lage dieser Datei
(`<Projekt>/python/pdf_extraction/pfade.py`) – nicht am Arbeitsverzeichnis.
Früher war `WURZEL = Path("data")`; wer ein Modul aus einem anderen Ordner
startete, bekam still eine zweite Ordnerstruktur daneben.
"""

from __future__ import annotations

from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]

WURZEL = PROJEKT / "data"
RAW = WURZEL / "raw"
INTERIM = WURZEL / "interim"
PROCESSED = WURZEL / "processed"

# Wurzeln je Dokument-Unterordner – als eigene Konstanten, damit Module wie
# stapel.py ihr `wurzel`-Argument (T4: bleibt zum Umlenken im Test erhalten)
# mit einem Vorgabewert aus `pfade` versehen können, ohne "befunde" oder
# "ausschnitte" selbst als Literal zu tragen.
BEFUNDE = INTERIM / "befunde"
AUSSCHNITTE = INTERIM / "ausschnitte"
KONTROLLE = INTERIM / "kontrolle"
LEKTORAT = INTERIM / "lektorat"

# Liegt außerhalb von data/, ist aber ebenso ein Pfad, der nur hier gebildet
# werden darf (CLAUDE.md, harte Projektregel) – nicht als Konstante in
# stapel.py, wo bislang das ONNX-Modell für die Layout-Erkennung herkam.
MODELLE = PROJEKT / "models"
ONNX_STANDARD = MODELLE / "pp_doclayoutv3.onnx"

# Geerntete Endprodukte; liegt bewusst außerhalb von data/, weil data/ nach
# jeder Ernte zurückgesetzt wird.
ERGEBNISSE = PROJEKT / "ergebnisse"

# Alle Ordner, die ein frischer Arbeitsbereich braucht.
ARBEITSORDNER = (RAW, BEFUNDE, AUSSCHNITTE, KONTROLLE, LEKTORAT, PROCESSED)


# ------------------------------------------------------------------- Eingang

def quelle(dok: str) -> Path:
    return RAW / f"{dok}.pdf"


# ------------------------------------------------------------- Zwischenbestand

def befund_ordner(dok: str) -> Path:
    return BEFUNDE / dok


def befund(dok: str, seite: int) -> Path:
    return befund_ordner(dok) / f"{seite:04d}.json"


def ausschnitt_ordner(dok: str) -> Path:
    return AUSSCHNITTE / dok


def bildname(dok: str, seite: int, block: int, klasse: str) -> str:
    return f"{dok}_{seite:04d}_{block:02d}_{klasse}.png"


def ausschnitt(dok: str, seite: int, block: int, klasse: str) -> Path:
    return ausschnitt_ordner(dok) / bildname(dok, seite, block, klasse)


def kontrolle(dok: str, seite: int) -> Path:
    return KONTROLLE / f"{dok}_{seite:04d}.png"


def kontrolle_html(dok: str) -> Path:
    """Eigenständiger Layout-Bericht zum Verschicken (einblick_html)."""
    return KONTROLLE / f"{dok}_layout.html"


# --------------------------------------------------------------- Ergebnisbestand

def dokument_ordner(dok: str) -> Path:
    return PROCESSED / dok


def artefakt_ordner(dok: str) -> Path:
    return dokument_ordner(dok) / f"{dok}_artifacts"


def artefakt(dok: str, seite: int, block: int, klasse: str) -> Path:
    return artefakt_ordner(dok) / bildname(dok, seite, block, klasse)


def artefakt_relativ(dok: str, seite: int, block: int, klasse: str) -> Path:
    """Relativ zu `dokument_ordner(dok)` – die einzige Bild-URI im Umlauf."""
    return Path(f"{dok}_artifacts") / bildname(dok, seite, block, klasse)


def dokument_json(dok: str, konsolidiert: bool = False) -> Path:
    suffix = "_k" if konsolidiert else ""
    return dokument_ordner(dok) / f"{dok}{suffix}.json"


def dokument_md(dok: str, konsolidiert: bool = False) -> Path:
    suffix = "_k" if konsolidiert else ""
    return dokument_ordner(dok) / f"{dok}{suffix}.md"


def dokument_korr_md(dok: str) -> Path:
    """Ausgabe des Lektorats (Stufe 2 der Gesamtpipeline).

    Der Name entsteht in `markdown_lektorat.lekt_pfade` aus dem Quellstamm;
    hier nur nachgebildet, damit Bildstufe und Ernte ihn nicht raten müssen.
    """
    return dokument_ordner(dok) / f"{dok}_korr.md"


def dokument_review_md(dok: str) -> Path:
    return dokument_ordner(dok) / f"{dok}_review.md"


def lektorat_ordner(dok: str) -> Path:
    """Checkpoint und Laufmanifeste des Lektorats."""
    return LEKTORAT / dok


def bild_manifest(dok: str, endung: str = "json") -> Path:
    return dokument_ordner(dok) / f"{dok}.image-optimization.{endung}"


# ---------------------------------------------------------- Namensregelwerk

# A-Z, a-z, 0-9, -, _ — als Literal statt über das Modul `string`, damit
# dieses Modul keine Abhängigkeit außer `pathlib` bekommt (T1).
_BUCHSTABEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ZIFFERN = "0123456789"
ZEICHENVORRAT = set(_BUCHSTABEN + _ZIFFERN + "-_")
_ERSTES_ZEICHEN_ERLAUBT = set(_BUCHSTABEN + _ZIFFERN)

RESERVIERTE_NAMEN = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# Herleitung (plan.md 5.1): Der längste abgeleitete Pfad ist
# data/processed/<dok>/<dok>_artifacts/<dok>_0221_11_footer_image.png.
# <dok> steckt darin dreimal, dazu rund 52 feste Zeichen. Bei der
# Pfadgrenze von 260 Zeichen unter Windows und einem Projektordner von
# rund 60 Zeichen bleiben rund 148 Zeichen für die drei Vorkommen, also
# rund 49 Zeichen je Vorkommen. Auf 48 abgerundet als Sicherheitsspanne;
# test_pfade_namen.py rechnet das mit der tatsächlich längsten Klasse nach.
MAX_STAMM = 48


def name_pruefen(stamm: str) -> list[str]:
    """Prüft nur den Stamm (ohne Endung) gegen plan.md 5.1.

    Leere Liste heißt: in Ordnung. Mehrere Verstöße können gleichzeitig
    zutreffen, etwa ein zu langer Stamm mit unzulässigen Zeichen.
    """
    if not stamm:
        return ["Stamm ist leer."]

    befunde: list[str] = []

    unzulaessig = sorted({z for z in stamm if z not in ZEICHENVORRAT})
    if unzulaessig:
        befunde.append(
            f"Enthält unzulässige Zeichen ({', '.join(map(repr, unzulaessig))}). "
            "Zulässig sind A-Z, a-z, 0-9, - und _.")

    if stamm[0] not in _ERSTES_ZEICHEN_ERLAUBT:
        befunde.append(f"Erstes Zeichen {stamm[0]!r} ist weder Buchstabe noch Ziffer.")

    if len(stamm) > MAX_STAMM:
        befunde.append(
            f"Stamm ist {len(stamm)} Zeichen lang, erlaubt sind höchstens {MAX_STAMM}.")

    if stamm.upper() in RESERVIERTE_NAMEN:
        befunde.append(f"{stamm!r} ist unter Windows ein reservierter Name.")

    return befunde


_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}


def ersatzname(stamm: str) -> str:
    """Vorschlag für einen beanstandeten Stamm. Wird nirgends automatisch
    angewandt (INV-4) – nur zur Meldung an den Menschen (SR-03).

    Löst nur, was `name_pruefen` an diesem Stamm allein beanstanden kann.
    Eine Kollision mit einem anderen Namen im Bestand lässt sich ohne
    dessen Namen nicht auflösen und bleibt hier unangetastet.
    """
    if not name_pruefen(stamm):
        return stamm

    lesbar = "".join(_UMLAUTE.get(z, z) for z in stamm)
    ersetzt = "".join(z if z in ZEICHENVORRAT else "_" for z in lesbar)
    if not ersetzt or ersetzt[0] not in _ERSTES_ZEICHEN_ERLAUBT:
        ersetzt = "d" + ersetzt
    ersetzt = ersetzt[:MAX_STAMM]
    if ersetzt.upper() in RESERVIERTE_NAMEN:
        ersetzt = (ersetzt + "_dok")[:MAX_STAMM]
    return ersetzt


def namen_pruefen(pfade: list[Path]) -> dict[Path, list[str]]:
    """Namensregelwerk über einen ganzen Bestand: je Datei `name_pruefen`
    auf den Stamm, dazu Endung und Eindeutigkeit über alle Dateien hinweg
    (SR-02 bis SR-04). Nur beanstandete Pfade erscheinen im Ergebnis.

    Die Kollisionsprüfung läuft über den ganzen Bestand in einem Zug: zwei
    Stämme, die sich nur in der Groß-/Kleinschreibung unterscheiden, werden
    beide beanstandet und nennen sich gegenseitig – nicht jeder für sich.
    """
    gruppen: dict[str, list[Path]] = {}
    for pfad in pfade:
        gruppen.setdefault(pfad.stem.casefold(), []).append(pfad)

    ergebnis: dict[Path, list[str]] = {}
    for pfad in pfade:
        befunde = list(name_pruefen(pfad.stem))

        if pfad.suffix != ".pdf":
            befunde.append(
                f"Endung {pfad.suffix!r} ist nicht zulässig; erwartet wird genau '.pdf'.")

        gruppe = gruppen[pfad.stem.casefold()]
        if len(gruppe) > 1:
            andere = sorted(p.name for p in gruppe if p != pfad)
            befunde.append(
                "Stamm kollidiert bei Groß-/Kleinschreibung mit: " + ", ".join(andere))

        if befunde:
            ergebnis[pfad] = befunde

    return ergebnis
