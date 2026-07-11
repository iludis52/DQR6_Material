#!/usr/bin/env python3
# Phase2a_spec_lint.py — Deterministischer Spec-Lint für LangGraph-Specs
#
# Verwendung:  python Phase2a_spec_lint.py spec.md
#
# Prüft die mechanischen Punkte der Review-Checkliste (⚙-Markierung),
# BEVOR die LLM-Prüf-Pässe laufen: A1, A2, A5, A6, A7, B4 (best effort),
# B6 (Knoten-Abgleich) und D1 (Zyklensuche im Mermaid-Diagramm).
#
# Grundsatz: Der Lint ist ehrlich statt gnädig — was er nicht sicher
# parsen kann, meldet er als WARN ("manuell prüfen"), niemals als
# stilles OK. Exit-Code 1, sobald mindestens ein BEFUND vorliegt.
#
# Einordnung ("es gibt doch noch keinen Code?"): Dieses Skript ist
# WERKZEUG-Code, nicht Projekt-Code. Es importiert nichts aus dem
# Projekt und braucht keinen Agenten — Prüfobjekt ist die spec.md
# als Textdokument (Überschriften, Tabellen, Mermaid). Es ist damit
# das zweite projektunabhängige Artefakt der Werkzeugkette, neben
# dem Konventions-Skill. Abgrenzung: Lint (Phase 2a) prüft das
# Dokument; Strukturtests (Phase 4) prüfen später den Code gegen die
# Spec; Evals prüfen zuletzt die Qualität gegen die Rubrik.

import re
import sys
import json  # <-- NEU
from pathlib import Path

# ---------------------------------------------------------------------
# Hilfsstrukturen
# ---------------------------------------------------------------------

ERGEBNISSE: list[tuple[str, str, str]] = []   # (Stufe, Prüfpunkt, Text)

def melde(stufe: str, punkt: str, text: str) -> None:
    ERGEBNISSE.append((stufe, punkt, text))

PFLICHTABSCHNITTE = {
    1: "Zweck", 2: "Beispiel-Durchläufe", 3: "State-Schema",
    4: "Knoten-Inventar", 5: "Kanten & Router", 6: "Terminierung",
    7: "Skills", 8: "Graph", 9: "Nicht-Ziele", 10: "Offene Punkte",
}

def abschnitte_zerlegen(text: str) -> dict[int, str]:
    """Zerlegt die Spec an '## <n>.'-Überschriften in nummerierte Teile."""
    teile: dict[int, str] = {}
    treffer = list(re.finditer(r"^##\s*(\d+)\.\s*(.*)$", text, re.MULTILINE))
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(text)
        teile[int(m.group(1))] = text[m.end():ende]
    return teile

def tabellen_zeilen(abschnitt: str) -> list[list[str]]:
    """Extrahiert Markdown-Tabellenzeilen (ohne Kopf- und Trennzeile)."""
    zeilen = []
    for zeile in abschnitt.splitlines():
        z = zeile.strip()
        if not (z.startswith("|") and z.endswith("|")):
            continue
        zellen = [c.strip() for c in z.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in zellen):
            continue                     # Trennzeile |---|---|
        zeilen.append(zellen)
    return zeilen[1:] if zeilen else []  # erste Zeile = Kopf

# ---------------------------------------------------------------------
# A-Prüfungen (Vollständigkeit)
# ---------------------------------------------------------------------

def pruefe_a1(teile: dict[int, str]) -> None:
    fehlend = [f"{n}. {t}" for n, t in PFLICHTABSCHNITTE.items() if n not in teile]
    if fehlend:
        melde("BEFUND", "A1", f"Pflichtabschnitte fehlen: {', '.join(fehlend)}")
    else:
        melde("OK", "A1", "alle 10 Pflichtabschnitte vorhanden")

def pruefe_a2(teile: dict[int, str]) -> None:
    zeilen = tabellen_zeilen(teile.get(3, ""))
    if not zeilen:
        melde("WARN", "A2", "State-Tabelle nicht parsebar — manuell prüfen")
        return
    befunde = [z[0] for z in zeilen
               if len(z) < 4 or any(not zelle for zelle in z[:3])]
    if befunde:
        melde("BEFUND", "A2", f"leere Zelle(n) bei Feld(ern): {', '.join(befunde)}")
    else:
        melde("OK", "A2", f"{len(zeilen)} State-Felder, keine leere Zelle")

def pruefe_a5(teile: dict[int, str]) -> None:
    n = len(re.findall(r"^###\s*Beispiel", teile.get(2, ""), re.MULTILINE))
    if n < 2:
        melde("BEFUND", "A5", f"nur {n} Beispiel-Durchlauf/-Durchläufe (mind. 2)")
    else:
        melde("OK", "A5", f"{n} Beispiel-Durchläufe (Sonderfall-Eigenschaft "
                          f"prüft Pass A manuell)")

def pruefe_a6(teile: dict[int, str]) -> None:
    inhalt = re.sub(r"\s", "", teile.get(9, ""))
    if not inhalt:
        melde("BEFUND", "A6", "Abschnitt 'Nicht-Ziele' ist leer")
    else:
        melde("OK", "A6", "Nicht-Ziele nicht leer")

def pruefe_a7(text: str) -> None:
    if re.search(r"recursion_limit\D{0,10}\d+", text):
        melde("OK", "A7", "recursion_limit ist beziffert")
    else:
        melde("BEFUND", "A7", "recursion_limit ohne Zahl oder nicht gefunden")

# ---------------------------------------------------------------------
# Mermaid-Auswertung (Basis für B4/B6/D1)
# ---------------------------------------------------------------------

def mermaid_lesen(teile: dict[int, str]) -> tuple[set[str], list[tuple[str, str, str]]]:
    """Liefert (Knotenmenge, Kantenliste (von, nach, label)) aus Abschnitt 8.
    Rauten-Deklarationen `x{...}` gelten als Router-Darstellung und werden
    aus der Knotenmenge ausgenommen (Router sind keine Spec-Knoten)."""
    m = re.search(r"```mermaid(.*?)```", teile.get(8, ""), re.DOTALL)
    if not m:
        return set(), []
    quelltext = m.group(1)
    rauten = set(re.findall(r"(\w+)\{[^}]*\}", quelltext))
    knoten, kanten = set(), []
    kante_re = re.compile(
        r"(\w+)(?:\[[^\]]*\]|\{[^}]*\})?\s*[-.=]+>+\s*(?:\|([^|]*)\|\s*)?(\w+)")
    for zeile in quelltext.splitlines():
        for von, label, nach in kante_re.findall(zeile):
            kanten.append((von, nach, (label or "").strip()))
            knoten.update((von, nach))
    return knoten - rauten, kanten

def pruefe_b6_knoten(teile: dict[int, str],
                     mermaid_knoten: set[str]) -> set[str]:
    zeilen = tabellen_zeilen(teile.get(4, ""))
    spec_knoten = {z[0].strip("`* ") for z in zeilen if z and z[0]}
    if not spec_knoten or not mermaid_knoten:
        melde("WARN", "B6", "Knoten-Inventar oder Mermaid nicht parsebar "
                            "— manuell prüfen")
        return spec_knoten
    pseudo = {"START", "END", "start", "ende", "__start__", "__end__"}
    nur_spec = spec_knoten - mermaid_knoten
    nur_mermaid = mermaid_knoten - spec_knoten - pseudo
    if nur_spec or nur_mermaid:
        melde("BEFUND", "B6",
              f"Knotenmengen ungleich — nur in Abschnitt 4: {nur_spec or '—'}, "
              f"nur im Mermaid: {nur_mermaid or '—'} "
              f"(Kanten-Abgleich bleibt Aufgabe von Pass B)")
    else:
        melde("OK", "B6", f"Knotenmengen identisch ({len(spec_knoten)} Knoten); "
                          f"Kanten-Abgleich bleibt Aufgabe von Pass B")
    return spec_knoten

def pruefe_b4(teile: dict[int, str], spec_knoten: set[str],
              kanten: list[tuple[str, str, str]]) -> None:
    """Best effort: Router-Ziele müssen Knoten, END oder Mermaid-Label
    sein. Um Prosa-Pfeile ("… → zurück zu Schritt 2") nicht als Ziele
    einzusammeln, werden nur Listen-/Tabellenzeilen betrachtet und pro
    Zeile nur das LETZTE Pfeilziel gewertet (Muster: Bedingung → Kante).
    Unauflösbare Ziele sind WARN, nicht BEFUND — ob echte Lücke oder
    Prosa-Pfeil, entscheidet die Triage bzw. Pass B (B4 dort mitprüfen)."""
    ziele = []
    for zeile in teile.get(5, "").splitlines():
        z = zeile.strip()
        if not (z.startswith("-") or z.startswith("|")):
            continue                              # nur Listen/Tabellen
        treffer = re.findall(r"(?:→|->)\s*[`'\"]?([\wäöüß_]+)", z)
        if treffer:
            ziele.append(treffer[-1])             # letztes Ziel der Zeile
    if not ziele:
        melde("WARN", "B4", "keine Router-Ziele parsebar — Pass B prüft "
                            "B4 mit")
        return
    labels = {label for _, _, label in kanten if label}
    erlaubt = spec_knoten | labels | {"END", "end", "__end__"}
    unbekannt = sorted({z for z in ziele if z not in erlaubt})
    if unbekannt:
        melde("WARN", "B4", f"Ziel(e) nicht auflösbar: {', '.join(unbekannt)}"
                            f" — echte Lücke oder Prosa-Pfeil? Pass B prüft "
                            f"B4 mit")
    else:
        melde("OK", "B4", f"{len(set(ziele))} Router-Ziele aufgelöst")

# ---------------------------------------------------------------------
# D1 — Zyklensuche (Tiefensuche über die Mermaid-Kanten)
# ---------------------------------------------------------------------

def zyklen_finden(kanten: list[tuple[str, str, str]]) -> list[list[str]]:
    graph: dict[str, list[str]] = {}
    for von, nach, _ in kanten:
        graph.setdefault(von, []).append(nach)
    zyklen, pfad, besucht = [], [], set()

    def dfs(k: str) -> None:
        if k in pfad:                          # Rückkante → Zyklus
            z = pfad[pfad.index(k):] + [k]
            if set(z) not in [set(x) for x in zyklen]:
                zyklen.append(z)
            return
        if k in besucht:
            return
        besucht.add(k)
        pfad.append(k)
        for nach in graph.get(k, []):
            dfs(nach)
        pfad.pop()

    for start in list(graph):
        dfs(start)
    return zyklen

def pruefe_d1(teile: dict[int, str],
              kanten: list[tuple[str, str, str]]) -> None:
    if not kanten:
        melde("WARN", "D1", "kein Mermaid-Diagramm parsebar — manuell prüfen")
        return
    zyklen = zyklen_finden(kanten)
    term_zeilen = tabellen_zeilen(teile.get(6, ""))
    if not zyklen:
        if term_zeilen:
            melde("WARN", "D1",
                  f"Widerspruch: Terminierungstabelle nennt "
                  f"{len(term_zeilen)} Zyklus/Zyklen, im Mermaid ist aber "
                  f"keiner ablaufbar — entweder fehlen Rückkanten im "
                  f"Diagramm (echter Befund) oder die Kantensyntax war "
                  f"nicht parsebar (Werkzeug-Befund). Pass D prüft D1 mit")
        else:
            melde("OK", "D1", "keine Zyklen im Graphen, Terminierungstabelle "
                              "leer — konsistent")
        return
    for z in zyklen:
        melde("INFO", "D1", "Zyklus: " + " → ".join(z))
    if len(term_zeilen) < len(zyklen):
        melde("BEFUND", "D1",
              f"{len(zyklen)} Zyklus/Zyklen im Diagramm, aber nur "
              f"{len(term_zeilen)} Zeile(n) in der Terminierungstabelle — "
              f"Pass D klärt die Zuordnung")
    else:
        melde("OK", "D1", f"{len(zyklen)} Zyklus/Zyklen gefunden, "
                          f"Terminierungstabelle hat {len(term_zeilen)} "
                          f"Zeile(n) — Zuordnung prüft Pass D (D2/D3)")

# ---------------------------------------------------------------------
# Hauptlauf
# ---------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 2:
        print("Verwendung: python Phase2a_spec_lint.py <spec.md>")
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    teile = abschnitte_zerlegen(text)

    pruefe_a1(teile)
    pruefe_a2(teile)
    pruefe_a5(teile)
    pruefe_a6(teile)
    pruefe_a7(text)
    mermaid_knoten, kanten = mermaid_lesen(teile)
    spec_knoten = pruefe_b6_knoten(teile, mermaid_knoten)
    pruefe_b4(teile, spec_knoten, kanten)
    pruefe_d1(teile, kanten)

    breite = max(len(p) for _, p, _ in ERGEBNISSE)
    print(f"\nSpec-Lint: {sys.argv[1]}\n" + "─" * 60)
    for stufe, punkt, txt in ERGEBNISSE:
        print(f"[{stufe:6}] {punkt:<{breite}}  {txt}")
    n_befund = sum(1 for s, _, _ in ERGEBNISSE if s == "BEFUND")
    n_warn = sum(1 for s, _, _ in ERGEBNISSE if s == "WARN")
    print("─" * 60)
    print(f"Ergebnis: {n_befund} Befund(e), {n_warn} manuell zu prüfen. "
          + ("→ Triage, dann Korrektur-Modus (Phase 1)."
             if n_befund else "→ LLM-Pässe können starten."))

# ... (vorheriger Code der main()) ...
    
    # Fertig aufgelöster Prüfauftrag 
    if n_befund == 0:
        stufe_je_punkt: dict[str, str] = {}
        rang = {"OK": 0, "WARN": 1, "BEFUND": 2}
        for stufe, punkt, _ in ERGEBNISSE:
            if stufe in rang and rang[stufe] >= rang.get(
                    stufe_je_punkt.get(punkt, "OK"), 0):
                stufe_je_punkt[punkt] = stufe
        paesse = {
            "A": (["A3", "A4", "A5"], ["A1", "A2", "A6", "A7"]),
            "B": (["B1", "B2", "B3", "B5", "B6", "B7"], ["B4"]),
            "C": (["C1", "C2", "C3", "C4"], []),
            "D": (["D2", "D3", "D4"], ["D1"]),
        }
        
        # --- NEU: JSON-Report für den LLM-Agenten erstellen ---
        report = {
            "linter_status": "erfolgreich" if n_warn == 0 else "mit_warnungen",
            "anzahl_warnungen": n_warn,
            "manuell_zu_pruefen_durch_llm": [{"punkt": p, "meldung": t} for s, p, t in ERGEBNISSE if s == "WARN"],
            "llm_pruefauftrag": {
                "zu_pruefen": [],
                "entfaellt": []
            }
        }

        print("\nPrüfauftrag:")
        for name, (immer, zahnrad) in paesse.items():
            pruefen = list(immer)
            entfaellt = []
            for p in zahnrad:
                (entfaellt if stufe_je_punkt.get(p) == "OK"
                 else pruefen).append(p)
            
            # Für die Konsolenausgabe
            zeile = f"  Pass {name}: prüfen {', '.join(sorted(pruefen))}"
            if entfaellt:
                zeile += f"  ·  entfaellt {', '.join(sorted(entfaellt))}"
            print(zeile)
            
            # Für das JSON
            report["llm_pruefauftrag"]["zu_pruefen"].extend(pruefen)
            report["llm_pruefauftrag"]["entfaellt"].extend(entfaellt)

        # In Datei schreiben
        report_pfad = Path("lint_report.json")
        report_pfad.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[+] Linter-Ergebnis für Agenten gespeichert unter: {report_pfad}")
        # --------------------------------------------------------

    return 1 if n_befund else 0

if __name__ == "__main__":
    sys.exit(main())
