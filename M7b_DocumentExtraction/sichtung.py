"""Sichtung: was steht nach Stufe 2 tatsächlich in den Befunden?

Liest ausschließlich. Beantwortet die Fragen, an denen der Zuschnitt von
Stufe 4a hängt – Tabellen, Bilder, überlappende Detektionen, Überschriften –
mit Zahlen aus dem eigenen Korpus statt mit Vermutungen.

Aufruf:
    python sichtung.py                     # befunde/, alle Bücher
    python sichtung.py befunde Buch        # nur ein Buch
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from schema import SeitenBefund, Strom, Stufe, befund_laden

ENTHALTEN_SCHWELLE = 0.9      # ab hier gilt eine Box als in einer anderen liegend


def befunde_lesen(wurzel: Path, buch: str | None = None) -> list[SeitenBefund]:
    ordner = (wurzel / buch) if buch else wurzel
    dateien = sorted(ordner.rglob("*.json"))
    if not dateien:
        raise FileNotFoundError(f"Keine Befunde unter {ordner}")
    befunde, kaputt = [], []
    for p in dateien:
        try:
            befunde.append(befund_laden(p))
        except Exception as e:
            kaputt.append((p.name, f"{type(e).__name__}: {e}"))
    if kaputt:
        print(f"! {len(kaputt)} Datei(en) nicht lesbar:")
        for name, fehler in kaputt[:5]:
            print(f"    {name}  {fehler}")
    return befunde


def _balken(zaehler: Counter, gesamt: int, breite: int = 28) -> None:
    if not zaehler:
        print("    –")
        return
    hoechst = max(zaehler.values())
    for name, n in zaehler.most_common():
        anteil = n / gesamt * 100 if gesamt else 0
        block = "█" * max(1, round(n / hoechst * breite))
        print(f"    {str(name):22s} {n:6d}  {anteil:5.1f}%  {block}")


def sichten(befunde: list[SeitenBefund]) -> None:
    seiten = len(befunde)
    bloecke = [b for bf in befunde for b in bf.bloecke]
    print("=" * 72)
    print(f"{seiten} Seiten, {len(bloecke)} Blöcke, "
          f"{len(bloecke)/max(1,seiten):.1f} je Seite")

    # --- Stand und Laufzeit -------------------------------------------------
    stufen = Counter(bf.stufe.name for bf in befunde)
    fehlerhaft = [bf for bf in befunde if bf.fehler]
    print(f"Stände: {dict(stufen)}   mit Fehler: {len(fehlerhaft)}")
    for bf in fehlerhaft[:5]:
        print(f"    S{bf.seite:4d}  {bf.fehler}")

    for stufe in (Stufe.LAYOUT, Stufe.ERKANNT):
        zeiten = [sp.dauer_s for bf in befunde for sp in bf.spuren
                  if sp.stufe is stufe]
        if zeiten:
            zeiten_s = sorted(zeiten)
            print(f"Stufe {stufe.value}: {sum(zeiten):7.1f} s gesamt, "
                  f"Median {zeiten_s[len(zeiten_s)//2]:5.2f} s, "
                  f"Maximum {zeiten_s[-1]:5.2f} s")
    modelle = {sp.modell for bf in befunde for sp in bf.spuren}
    print(f"Modelle: {sorted(modelle)}")

    # --- Klassen und Ströme -------------------------------------------------
    print("\n--- Klassen (bestimmt, welche Zweige 4a wirklich braucht)")
    _balken(Counter(b.pp_label for b in bloecke), len(bloecke))
    print("\n--- Ströme")
    _balken(Counter(b.strom.value for b in bloecke), len(bloecke))

    # --- Text ---------------------------------------------------------------
    print("\n--- Textformate")
    _balken(Counter(b.text_format or ("bild" if b.ausschnitt else "leer")
                    for b in bloecke), len(bloecke))

    ohne_text = [b for b in bloecke if b.text is None and b.ausschnitt is None]
    leer = [b for b in bloecke if b.text is not None and not b.text.strip()]
    print(f"\n    ohne Text und ohne Ausschnitt: {len(ohne_text)}")
    print(f"    leerer Text:                   {len(leer)}")
    laengen = sorted(len(b.text) for b in bloecke if b.text)
    if laengen:
        print(f"    Textlänge: Median {laengen[len(laengen)//2]}, "
              f"kürzeste {laengen[0]}, längste {laengen[-1]}, "
              f"unter 120 Zeichen: {sum(1 for l in laengen if l < 120)}")

    # --- A11: OTSL wirklich parsebar? --------------------------------------
    otsl = [b for b in bloecke if b.text_format == "otsl" and b.text]
    print(f"\n--- A11: {len(otsl)} OTSL-Blöcke")
    if otsl:
        try:
            from docling_core.types.doc.utils import parse_otsl_table_content
            ok, misslungen, zellen = 0, [], []
            for b in otsl:
                try:
                    daten = parse_otsl_table_content(b.text)
                    ok += 1
                    zellen.append((daten.num_rows, daten.num_cols))
                except Exception as e:
                    misslungen.append((b.id, f"{type(e).__name__}: {e}"))
            print(f"    parsebar: {ok}   misslungen: {len(misslungen)}")
            for bid, fehler in misslungen[:5]:
                print(f"      #{bid}  {fehler}")
            if zellen:
                print(f"    Zeilen x Spalten: Median "
                      f"{sorted(z[0] for z in zellen)[len(zellen)//2]} x "
                      f"{sorted(z[1] for z in zellen)[len(zellen)//2]}")
        except ImportError:
            print("    docling-core nicht installiert – übersprungen.")
        ohne_marken = [b for b in otsl if "<fcel>" not in b.text
                       and "<ecel>" not in b.text]
        print(f"    ohne OTSL-Marken (A11-Fallbackfall): {len(ohne_marken)}")

    # --- A14: Bildblöcke ----------------------------------------------------
    bilder = [b for b in bloecke if b.ausschnitt]
    seiten_mit_bild = len({(bf.seite) for bf in befunde
                           for b in bf.bloecke if b.ausschnitt})
    print(f"\n--- A14: {len(bilder)} Bildblöcke auf {seiten_mit_bild} Seiten")
    _balken(Counter(b.pp_label for b in bilder), max(1, len(bilder)))

    # --- F3: überlappende Detektionen --------------------------------------
    paare, seiten_mit_paar = [], set()
    for bf in befunde:
        for a in bf.bloecke:
            for c in bf.bloecke:
                if a.id >= c.id:
                    continue
                try:
                    innen = max(a.bbox.enthalten_in(c.bbox),
                                c.bbox.enthalten_in(a.bbox))
                except ValueError:
                    continue
                if innen >= ENTHALTEN_SCHWELLE:
                    paare.append((a.pp_label, c.pp_label))
                    seiten_mit_paar.add(bf.seite)
    print(f"\n--- F3: {len(paare)} ineinanderliegende Paare "
          f"(≥{ENTHALTEN_SCHWELLE:.0%}) auf {len(seiten_mit_paar)} von "
          f"{seiten} Seiten")
    _balken(Counter(" in ".join(sorted(p)) for p in paare), max(1, len(paare)))

    # --- B8: Überschriften --------------------------------------------------
    ueberschriften = Counter()
    ohne = 0
    for bf in befunde:
        n = sum(1 for b in bf.bloecke
                if b.pp_label in ("doc_title", "paragraph_title"))
        ueberschriften[n] += 1
        if n == 0:
            ohne += 1
    print(f"\n--- B8: {ohne} von {seiten} Seiten ohne jede Überschrift")
    print(f"    Überschriften je Seite: "
          f"{dict(sorted(ueberschriften.items()))}")

    # --- Hauptstrom ---------------------------------------------------------
    leer_haupt = [bf.seite for bf in befunde if not bf.lesefolge(Strom.HAUPT)]
    print(f"\n--- {len(leer_haupt)} Seiten ohne Hauptstrom"
          + (f": {leer_haupt[:15]}" if leer_haupt else ""))

    # --- Warnungen ----------------------------------------------------------
    def art(w: str) -> str:
        w = w.split(": ", 1)[-1] if w.startswith("#") else w
        for muster in ("zusammengeführt", "Tabelle ohne OTSL-Marken",
                       "Formel ohne erkennbare Delimiter", "Leere Antwort",
                       "Keine Detektion", "ohne Maskenkopf"):
            if muster in w:
                return muster
        return w[:60]

    warnungen = [w for bf in befunde for w in bf.warnungen]
    print(f"\n--- {len(warnungen)} Warnungen")
    _balken(Counter(art(w) for w in warnungen), max(1, len(warnungen)))


if __name__ == "__main__":
    wurzel = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("befunde")
    buch = sys.argv[2] if len(sys.argv) > 2 else None
    sichten(befunde_lesen(wurzel, buch))
