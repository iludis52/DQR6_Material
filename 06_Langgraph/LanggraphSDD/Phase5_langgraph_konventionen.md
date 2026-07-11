# Skill: LangGraph-Konventionen

> **Verwendung:** Diese Datei wird dem implementierenden LLM in Phase 5
> zusammen mit `spec.md` und `tasks.md` mitgegeben. Sie ist das einzige
> projektunabhängige Dokument der Werkzeugkette und wird unverändert
> wiederverwendet. Jede Konvention hier hat ein Gegenstück in der
> Test-Vorlage — Abweichungen machen Tests rot.

## 1. State-Schema

- State als `TypedDict`, ein einziges Schema pro Graph, definiert an
  einer Stelle.
- Jedes Feld trägt die Reducer-Entscheidung aus der Spec:

```python
from typing import Annotated, TypedDict
from operator import add
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # überschreiben (Default): kein Annotated
    profil: dict
    # akkumulieren: Annotated mit Reducer
    erkenntnisse: Annotated[list[str], add]
    messages: Annotated[list, add_messages]
    # Terminierung: jeder Zyklus hat seinen Zähler
    iterationen: int
```

- Konstanten für Maxima auf Modulebene, GROSS_GESCHRIEBEN, direkt über
  dem State: `MAX_ITERATIONEN = 3`
- Keine globalen Variablen als Zustandsersatz. Alles, was zwischen
  Knoten fließt, fließt durch den State.

## 2. Knoten

- Signatur immer `def knoten_name(state: AgentState) -> dict:`
- Rückgabe ist ein **partielles** Dict — nur die Felder, die dieser
  Knoten ändert. Nie den ganzen State zurückgeben, nie `state` mutieren.
- Knoten, die in einem Zyklus liegen, inkrementieren ihren Zähler selbst:
  `return {"analyse": ..., "iterationen": state["iterationen"] + 1}`
- Ein Knoten = eine Verantwortung. LLM-Aufruf, Tool-Ausführung und
  Datenverarbeitung nicht im selben Knoten mischen, wenn die Spec sie
  als getrennte Knoten führt.
- LLM-Aufrufe und Tool-Ausführungen in `try/except`; im Fehlerfall ein
  definiertes Fehler-Feld schreiben (z.B. `{"fehler": str(e)}`), damit
  ein Router darauf reagieren kann. Niemals nackt durchreichen.
- JSON aus LLM-Antworten defensiv parsen (Markdown-Fences entfernen,
  `json.JSONDecodeError` abfangen, definierter Fallback).

## 3. Router

- Router sind **pure functions**: State lesen → String zurückgeben.
  Keine LLM-Aufrufe, keine Tool-Aufrufe, keine Schreibzugriffe, kein I/O.
- Rückgabetyp als `Literal` deklarieren — das macht die Fälle maschinen-
  lesbar und testbar:

```python
from typing import Literal

def route_qualitaet(state: AgentState) -> Literal["verbessern", "fertig"]:
    if state["iterationen"] >= MAX_ITERATIONEN:
        return "fertig"                      # Terminierung ZUERST prüfen
    if state["bewertung"]["completeness"] < 0.8:
        return "verbessern"
    return "fertig"                          # expliziter Default
```

- **Reihenfolge im Router:** Abbruchbedingung (Zähler) immer als erste
  Prüfung — sonst kann eine andere Bedingung sie für immer verdecken.
- Der Default-Fall steht als letzte Zeile, nie implizit.

## 4. Graph-Aufbau

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

builder = StateGraph(AgentState)
builder.add_node("analysiere", analysiere)
# ... alle Knoten exakt mit den Namen aus der Spec, Abschnitt 4

builder.add_edge(START, "analysiere")
builder.add_conditional_edges(
    "bewerte",
    route_qualitaet,
    {"verbessern": "analysiere", "fertig": END},  # Keys = Router-Literals
)

graph = builder.compile(checkpointer=MemorySaver())
```

- Knoten- und Kanten-Namen **exakt** wie in der Spec — die Strukturtests
  prüfen namentlich.
- Das Mapping in `add_conditional_edges` deckt jeden Literal-Wert des
  Routers ab, nicht mehr und nicht weniger.
- Immer mit `MemorySaver` kompilieren. Aufrufe mit `thread_id` und
  explizitem `recursion_limit` aus der Spec:

```python
config = {"configurable": {"thread_id": "1"}, "recursion_limit": 25}
result = graph.invoke(eingabe, config)
```

- Debugging-Hinweis (in Code-Kommentar dokumentieren): Verlauf via
  `graph.get_state_history(config)` einsehbar.

## 5. Skills (Prompt-Bausteine)

- Skills liegen als Markdown in `skills/`, ein Skill pro Datei,
  Dateiname = Skill-Name aus der Spec.
- Platzhalter im Format `{variable}`. Befüllung zentral in einer
  Funktion `lade_skill(name: str, **variablen) -> str`, die bei
  fehlendem Platzhalter-Wert eine `KeyError` mit dem Skill-Namen wirft
  (nicht stillschweigend leer lässt).
- Skills werden zur Laufzeit geladen, nie in den Code kopiert — sie
  sind die volatile Schicht und müssen ohne Codeänderung austauschbar
  bleiben.
- Trigger-Logik (welcher Skill wann geladen wird) lebt in einem
  Daten-Knoten, nicht verstreut in Prompts.

## 6. Projektstruktur

```
projekt/
├── spec.md, plan.md, tasks.md
├── agent/
│   ├── state.py        # State + Konstanten
│   ├── knoten.py       # alle Knoten
│   ├── router.py       # alle Router
│   ├── graph.py        # Aufbau + compile
│   └── skills.py       # lade_skill()
├── skills/*.md
└── tests/
    ├── test_struktur.py
    ├── test_router.py
    ├── test_terminierung.py
    └── test_skills.py
```

## 7. Sprache & Stil

- Deutsche Kommentare, deutsche Docstrings, deutsche Skill-Texte,
  deutsche Ausgaben. Code-Bezeichner deutsch, außer LangGraph-Vokabular
  (state, node, router bleiben, wo das Framework sie vorgibt).
- Kein defensives Programmieren über die Spec hinaus: keine Features,
  Konfigurationsoptionen oder Abstraktionen, die die Spec nicht nennt.
  Bei Unklarheit: nachfragen, nicht erfinden.
