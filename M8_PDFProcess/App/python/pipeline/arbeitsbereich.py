"""Automatische Ordnerverwaltung: anlegen, befüllen, ernten, zurücksetzen.

Ablauf eines Auftrags:

    neuer_auftrag(pdfs)  ->  data/ leeren, Struktur anlegen, PDFs nach data/raw
    (Stufen 1–3 laufen)
    ernten_und_zuruecksetzen()  ->  Endprodukte nach ergebnisse/<BUCH>_<Zeit>/,
                                    erst danach data/ leeren

Zurückgesetzt wird nach der Ernte nur, wenn jede Ernte gelang. Bricht ein
Lauf ab (LM Studio weg, Rechner schläft), bleiben Befunde und Checkpoints
liegen und der nächste Lauf setzt dort wieder auf.

Gelöscht wird ausschließlich unterhalb von `pfade.WURZEL` (<Projekt>/data).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pfade
from bild_optimierung.bild_kontext import BILD_RE


# ------------------------------------------------------------ Struktur

def anlegen() -> list[Path]:
    for ordner in pfade.ARBEITSORDNER:
        ordner.mkdir(parents=True, exist_ok=True)
    return list(pfade.ARBEITSORDNER)


def _sicher_unter_data(pfad: Path) -> Path:
    pfad = pfad.resolve()
    wurzel = pfade.WURZEL.resolve()
    if wurzel.name != "data" or wurzel.parent != pfade.PROJEKT.resolve():
        raise RuntimeError(f"Unerwartete Datenwurzel {wurzel} – Abbruch, nichts gelöscht.")
    if pfad != wurzel and wurzel not in pfad.parents:
        raise RuntimeError(f"{pfad} liegt nicht unter {wurzel} – Abbruch, nichts gelöscht.")
    return pfad


def zuruecksetzen() -> None:
    """data/ vollständig leeren und die leere Struktur neu anlegen."""
    wurzel = _sicher_unter_data(pfade.WURZEL)
    if wurzel.exists():
        for eintrag in wurzel.iterdir():
            if eintrag.is_dir() and not eintrag.is_symlink():
                shutil.rmtree(eintrag)
            else:
                eintrag.unlink()
    anlegen()


def pdfs_uebernehmen(dateien: list[Path | str]) -> list[str]:
    """PDFs nach data/raw kopieren. Unzulässige Namen werden beim Kopieren
    ersetzt (die Quelle bleibt unberührt) und gemeldet."""
    anlegen()
    meldungen: list[str] = []
    for datei in map(Path, dateien):
        if datei.suffix.lower() != ".pdf":
            meldungen.append(f"{datei.name}: kein PDF – übergangen.")
            continue
        stamm = pfade.ersatzname(datei.stem)
        ziel = pfade.RAW / f"{stamm}.pdf"
        if ziel.exists():
            meldungen.append(f"{datei.name}: {ziel.name} liegt schon in data/raw – übergangen.")
            continue
        shutil.copy2(datei, ziel)
        if stamm != datei.stem:
            meldungen.append(f"{datei.name}: als {ziel.name} übernommen (Namensregel).")
        else:
            meldungen.append(f"{datei.name}: übernommen.")
    return meldungen


def neuer_auftrag(dateien: list[Path | str]) -> list[str]:
    zuruecksetzen()
    return ["Arbeitsbereich zurückgesetzt."] + pdfs_uebernehmen(dateien)


# ------------------------------------------------------------ Status

def buecher() -> list[str]:
    if not pfade.RAW.is_dir():
        return []
    return sorted(p.stem for p in pfade.RAW.iterdir()
                  if p.is_file() and p.suffix.lower() == ".pdf")


def lektorat_zustand(buch: str) -> str:
    """'fehlt' | 'unterbrochen' | 'veraltet' | 'fertig'.

    Ein abgeschlossenes Lektorat bleibt 'fertig', auch wenn die Bildstufe
    danach die Bildverweise in <BUCH>.md umgeschrieben hat. Erzeugt Stufe 1
    das Markdown neu, verwirft `steuerung.stufe1` das Lektorat ohnehin.
    """
    cp = pfade.lektorat_ordner(buch) / "checkpoint.json"
    korr = pfade.dokument_korr_md(buch)
    if not cp.is_file():
        return "fertig" if korr.is_file() else "fehlt"
    try:
        state = json.loads(cp.read_text(encoding="utf-8"))
    except Exception:
        return "unterbrochen"
    if state.get("status") == "completed" and korr.is_file():
        return "fertig"
    md = pfade.dokument_md(buch)
    if md.is_file():
        from hashlib import sha256
        if sha256(md.read_text(encoding="utf-8").encode("utf-8")).hexdigest() != state.get("source_sha256"):
            return "veraltet"
    return "unterbrochen"


def abgeleitetes_verwerfen(buch: str) -> list[str]:
    """Alles, was aus <BUCH>.md abgeleitet ist: Lektorat und Bildstufe."""
    weg = []
    for p in (pfade.dokument_korr_md(buch), pfade.dokument_review_md(buch),
              pfade.bild_manifest(buch, "json"), pfade.bild_manifest(buch, "csv")):
        if p.is_file():
            p.unlink()
            weg.append(p.name)
    lekt = pfade.lektorat_ordner(buch)
    if lekt.is_dir():
        shutil.rmtree(_sicher_unter_data(lekt))
        weg.append(f"{lekt.name}/ (Lektorat-Checkpoint)")
    return weg


@dataclass
class BuchStatus:
    buch: str
    seiten: int | None
    befunde: int
    erkannt: int
    kanonisch: bool
    lektorat: str
    bilder: str

    def zeile(self) -> list:
        return [self.buch, self.seiten, f"{self.erkannt}/{self.seiten or '?'}",
                "ja" if self.kanonisch else "nein", self.lektorat, self.bilder]


STATUS_SPALTEN = ["Dokument", "Seiten", "OCR fertig", "JSON/MD", "Lektorat", "Bilder"]


def status() -> list[BuchStatus]:
    from schema import Stufe, ist_fertig
    import stapel
    ergebnis = []
    for buch in buecher():
        try:
            seiten = stapel.seitenzahl(pfade.quelle(buch))
        except Exception:
            seiten = None
        befund_dateien = sorted(pfade.befund_ordner(buch).glob("*.json")) \
            if pfade.befund_ordner(buch).is_dir() else []
        erkannt = sum(ist_fertig(p, Stufe.ERKANNT) for p in befund_dateien)
        manifest = pfade.bild_manifest(buch)
        if manifest.is_file():
            try:
                assets = json.loads(manifest.read_text(encoding="utf-8")).get("assets", [])
                fehler = sum(a.get("status") == "ERROR" for a in assets)
                bilder = f"{len(assets)} verarbeitet" + (f", {fehler} Fehler" if fehler else "")
            except Exception:
                bilder = "Manifest unlesbar"
        else:
            bilder = "offen"
        ergebnis.append(BuchStatus(
            buch=buch, seiten=seiten, befunde=len(befund_dateien), erkannt=erkannt,
            kanonisch=pfade.dokument_json(buch).is_file() and pfade.dokument_md(buch).is_file(),
            lektorat=lektorat_zustand(buch), bilder=bilder))
    return ergebnis


def ist_erntereif(buch: str) -> tuple[bool, list[str]]:
    gruende = []
    if not pfade.dokument_json(buch).is_file():
        gruende.append("kein Docling-JSON (Stufe 1 unvollständig)")
    if lektorat_zustand(buch) != "fertig":
        gruende.append(f"Lektorat {lektorat_zustand(buch)}")
    if not pfade.bild_manifest(buch).is_file():
        gruende.append("Bildstufe nicht gelaufen")
    return not gruende, gruende


# ------------------------------------------------------------ Ernte

@dataclass
class Ernte:
    buch: str
    ziel: Path | None = None
    dateien: list[str] = field(default_factory=list)
    probleme: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.ziel is not None and not self.probleme


def ernten(buch: str, ziel_wurzel: Path | None = None, *, trotzdem: bool = False) -> Ernte:
    """<BUCH>_korr.md, <BUCH>.json und <BUCH>_artifacts/ nach
    `<ziel_wurzel>/<BUCH>_<JJJJ-MM-TT_HHMM>/` kopieren und die Bildverweise prüfen.

    `trotzdem=True` erntet auch ein nicht erntereifes Dokument (dann ggf. mit
    der unlektorierten Fassung); die Gründe stehen in `probleme`.
    """
    ernte = Ernte(buch=buch)
    reif, gruende = ist_erntereif(buch)
    if not reif and not trotzdem:
        ernte.probleme = [f"nicht erntereif: {g}" for g in gruende]
        return ernte

    korr, js = pfade.dokument_korr_md(buch), pfade.dokument_json(buch)
    md = korr if korr.is_file() else pfade.dokument_md(buch)
    if not md.is_file() or not js.is_file():
        ernte.probleme.append("Markdown oder JSON fehlt – nichts geerntet.")
        return ernte
    if md != korr:
        ernte.probleme.append(f"kein {korr.name} – unlektorierte Fassung geerntet.")

    ziel_wurzel = ziel_wurzel or pfade.ERGEBNISSE
    stempel = datetime.now().strftime("%Y-%m-%d_%H%M")
    ziel = ziel_wurzel / f"{buch}_{stempel}"
    n = 2
    while ziel.exists():
        ziel = ziel_wurzel / f"{buch}_{stempel}_{n}"
        n += 1
    ziel.mkdir(parents=True)

    shutil.copy2(md, ziel / md.name)
    shutil.copy2(js, ziel / js.name)
    ernte.dateien += [md.name, js.name]
    artefakte = pfade.artefakt_ordner(buch)
    if artefakte.is_dir():
        shutil.copytree(artefakte, ziel / artefakte.name)
        ernte.dateien.append(artefakte.name + "/")

    # Jeder Bildverweis im geernteten Markdown muss im Ernteordner auflösen.
    text = (ziel / md.name).read_text(encoding="utf-8")
    for m in BILD_RE.finditer(text):
        if not (ziel / m.group("path")).is_file():
            ernte.probleme.append(f"Bildverweis ohne Datei: {m.group('path')}")
    ernte.ziel = ziel
    return ernte


def ernten_und_zuruecksetzen(ziel_wurzel: Path | None = None, *,
                             trotzdem: bool = False) -> tuple[list[Ernte], bool]:
    """Alle Dokumente ernten; nur wenn jede Ernte fehlerfrei war, zurücksetzen."""
    ernten_liste = [ernten(b, ziel_wurzel, trotzdem=trotzdem) for b in buecher()]
    alles_gut = bool(ernten_liste) and all(e.ziel is not None for e in ernten_liste) and (
        trotzdem or all(e.ok for e in ernten_liste))
    if alles_gut:
        zuruecksetzen()
    return ernten_liste, alles_gut


def fruehere_ernten(ziel_wurzel: Path | None = None) -> list[Path]:
    ziel_wurzel = ziel_wurzel or pfade.ERGEBNISSE
    if not ziel_wurzel.is_dir():
        return []
    return sorted((p for p in ziel_wurzel.iterdir() if p.is_dir()), reverse=True)
