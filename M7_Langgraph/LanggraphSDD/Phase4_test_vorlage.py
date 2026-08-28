# Test-Vorlage für LangGraph-Agenten (Phase 4)
#
# Verwendung: Kopieren, Platzhalter <IN_SPITZEN_KLAMMERN> aus der spec.md
# ersetzen, auf tests/test_struktur.py, test_router.py, test_terminierung.py,
# test_skills.py aufteilen (oder als eine Datei lassen).
#
# Diese Tests werden VOR der Knoten-Implementierung geschrieben. Sie laufen
# bereits gegen das Graph-Gerüst mit Dummy-Knoten (Task 3 der Plan-Vorlage)
# und bleiben unverändert, wenn die echten Knoten einziehen.
#
# Merksatz Tests vs. Evals: Alles hier ist DETERMINISTISCH testbar
# (Struktur, Router, Terminierung, Skills). Die QUALITÄT von LLM-Ausgaben
# wird nicht hier, sondern über Evals gemessen (LLM-as-Judge + Rubrik).

import re
from pathlib import Path

import pytest

from agent.graph import graph                 # kompilierter Graph
from agent.state import MAX_ITERATIONEN       # <ggf. Namen anpassen>
from agent.router import route_qualitaet      # <alle Router importieren>
from agent.skills import lade_skill

# =====================================================================
# 1. STRUKTURTESTS — der Graph entspricht der Spec (Abschnitte 4, 5, 8)
# =====================================================================

# Aus spec.md Abschnitt 4 übertragen:
ERWARTETE_KNOTEN = {
    "<knoten_1>",
    "<knoten_2>",
    "<knoten_3>",
}

# Aus spec.md Abschnitt 5 übertragen (Quelle, Ziel):
ERWARTETE_KANTEN = {
    ("__start__", "<knoten_1>"),
    ("<knoten_1>", "<knoten_2>"),
    # conditional edges erscheinen als Kanten zu allen möglichen Zielen:
    ("<knoten_2>", "<knoten_3>"),
    ("<knoten_2>", "__end__"),
}


def test_alle_spec_knoten_existieren():
    """Jeder Knoten aus Spec Abschnitt 4 ist im Graphen registriert."""
    vorhandene = set(graph.get_graph().nodes.keys())
    fehlend = ERWARTETE_KNOTEN - vorhandene
    assert not fehlend, f"Knoten aus der Spec fehlen im Graphen: {fehlend}"


def test_keine_unbekannten_knoten():
    """Der Graph enthält keine Knoten, die die Spec nicht kennt."""
    vorhandene = set(graph.get_graph().nodes.keys())
    extra = vorhandene - ERWARTETE_KNOTEN - {"__start__", "__end__"}
    assert not extra, f"Knoten ohne Spec-Grundlage: {extra}"


def test_kanten_entsprechen_spec():
    """Kantenmenge des Graphen == Kantenmenge aus Spec Abschnitt 5/8."""
    vorhandene = {(e.source, e.target) for e in graph.get_graph().edges}
    assert vorhandene == ERWARTETE_KANTEN, (
        f"fehlend: {ERWARTETE_KANTEN - vorhandene}, "
        f"überzählig: {vorhandene - ERWARTETE_KANTEN}"
    )


def test_akkumulierende_felder_haben_reducer():
    """Felder mit 'akkumulieren' in Spec Abschnitt 3 tragen Annotated."""
    from typing import get_type_hints, get_origin
    from agent.state import AgentState

    AKKUMULIERENDE_FELDER = {"<feld_a>", "<feld_b>"}   # aus Spec Abschn. 3
    hints = get_type_hints(AgentState, include_extras=True)
    for feld in AKKUMULIERENDE_FELDER:
        assert feld in hints, f"State-Feld '{feld}' fehlt"
        metadata = getattr(hints[feld], "__metadata__", None)
        assert metadata, (
            f"'{feld}' ist laut Spec akkumulierend, "
            f"hat aber keinen Annotated-Reducer"
        )


# =====================================================================
# 2. ROUTER-TESTS — pure functions, mit konstruierten States (Abschn. 5)
# =====================================================================
# Pro Router: ein parametrisierter Test, ein Fall pro Zeile der
# Fallunterscheidung in der Spec — INKLUSIVE Default-Fall.

@pytest.mark.parametrize(
    "state, erwartete_kante",
    [
        # <Fall 1 aus der Spec — Bedingung erfüllt>
        ({"iterationen": 0, "bewertung": {"completeness": 0.5}}, "verbessern"),
        # <Fall 2 — Qualität erreicht>
        ({"iterationen": 1, "bewertung": {"completeness": 0.9}}, "fertig"),
        # Terminierung schlägt alles (Zähler am Maximum, Qualität schlecht):
        ({"iterationen": MAX_ITERATIONEN,
          "bewertung": {"completeness": 0.0}}, "fertig"),
        # <Default-Fall — keiner der obigen trifft zu>
    ],
)
def test_route_qualitaet(state, erwartete_kante):
    assert route_qualitaet(state) == erwartete_kante


def test_router_ist_seiteneffektfrei():
    """Router verändern den State nicht (pure function)."""
    state = {"iterationen": 0, "bewertung": {"completeness": 0.5}}
    kopie = {"iterationen": 0, "bewertung": {"completeness": 0.5}}
    route_qualitaet(state)
    assert state == kopie, "Router hat den State mutiert"


# =====================================================================
# 3. TERMINIERUNGSTEST — das Verbranntes-Geld-Szenario (Abschnitt 6)
# =====================================================================
# Ein Fake-LLM, das den Loop absichtlich NIE verlassen will (liefert
# immer schlechte Qualität). Der Test beweist: der Zähler greift und
# der Graph endet trotzdem — in höchstens MAX Iterationen.

def test_loop_terminiert_trotz_boesartigem_llm(monkeypatch):
    aufrufe = {"n": 0}

    def fake_llm_aufruf(*args, **kwargs):
        aufrufe["n"] += 1
        # <an das echte Antwortformat anpassen — hier: Judge-JSON,
        #  das immer 'ungenügend' meldet>
        return '{"completeness": 0.0, "depth": 0.0, "missing": [], "strengths": []}'

    # <Pfad an die eigene LLM-Aufruf-Funktion anpassen:>
    monkeypatch.setattr("agent.knoten.llm_aufruf", fake_llm_aufruf)

    config = {"configurable": {"thread_id": "test-terminierung"},
              "recursion_limit": 50}
    result = graph.invoke(<MINIMALE_GUELTIGE_EINGABE>, config)

    assert result["iterationen"] <= MAX_ITERATIONEN, (
        f"Loop lief {result['iterationen']}x, Maximum ist {MAX_ITERATIONEN}"
    )


def test_recursion_limit_als_zweites_netz():
    """Auch wenn der Zähler versagt (hier: sabotiert), fängt LangGraph
    den Graphen über das recursion_limit ab, statt endlos zu laufen."""
    from langgraph.errors import GraphRecursionError

    config = {"configurable": {"thread_id": "test-limit"},
              "recursion_limit": 5}
    # <Eingabe konstruieren, die den Loop erzwingt, z.B. Zähler auf -999:>
    with pytest.raises(GraphRecursionError):
        graph.invoke(<EINGABE_MIT_SABOTIERTEM_ZAEHLER>, config)


# =====================================================================
# 4. SKILL-TESTS — Platzhalter-Kontrakte (Abschnitt 7)
# =====================================================================

SKILLS_DIR = Path("skills")

# Aus spec.md Abschnitt 7: Skill-Name -> erwartete Platzhalter
SKILL_KONTRAKTE = {
    "<skill_1>": {"<var_a>", "<var_b>"},
    "<skill_2>": {"<var_c>"},
}


@pytest.mark.parametrize("skill_name, erwartete_vars",
                         SKILL_KONTRAKTE.items())
def test_skill_platzhalter_vollstaendig(skill_name, erwartete_vars):
    """Skill-Datei existiert und enthält exakt die Platzhalter der Spec."""
    pfad = SKILLS_DIR / f"{skill_name}.md"
    assert pfad.exists(), f"Skill-Datei fehlt: {pfad}"
    text = pfad.read_text(encoding="utf-8")
    gefunden = set(re.findall(r"\{([a-z_]+)\}", text))
    assert gefunden == erwartete_vars, (
        f"{skill_name}: fehlend {erwartete_vars - gefunden}, "
        f"unbekannt {gefunden - erwartete_vars}"
    )


def test_lade_skill_meldet_fehlende_variable():
    """Fehlende Platzhalter-Werte werden laut, nicht stillschweigend leer."""
    with pytest.raises(KeyError):
        lade_skill("<skill_1>")   # ohne Variablen aufgerufen


# =====================================================================
# EVAL-RUBRIK (KEIN TEST — Vorlage für die spätere Qualitätsmessung)
# =====================================================================
# Nach der Implementierung: Golden-Eingaben definieren und die Ausgaben
# per LLM-as-Judge gegen eine Rubrik bewerten (analog Spec-Abschnitt 2).
# Kriterien und Schwellen aus der Spec ableiten, z.B.:
#   - vollstaendigkeit >= 0.8 auf allen Golden-Eingaben (Median, n=5)
#   - erkenntnistiefe >= 0.7
# Evals laufen wiederholt (Nichtdeterminismus!) und werden statistisch
# bewertet — niemals als einzelnes assert.
