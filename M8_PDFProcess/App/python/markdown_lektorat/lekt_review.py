from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReviewEntry:
    edit_id: str
    target_ids: list[str]
    category: str
    operation: str
    original: str | None
    result: str | None
    confidence_score: float
    confidence_class: str
    reason: str
    status: str


@dataclass
class ReviewReport:
    document: str
    model: str
    policy_version: str
    entries: list[ReviewEntry] = field(default_factory=list)
    integrity_ok: bool = False
    validation_notes: list[str] = field(default_factory=list)
    status: str = "UNVOLLSTÄNDIG"
    current_pass: str | None = None
    next_chunk: str | None = None


def _entry_md(e: ReviewEntry) -> str:
    return (
        f"### {e.edit_id}\n\n"
        f"- Ziel: `{', '.join(e.target_ids)}`\n"
        f"- Kategorie: `{e.category}`\n"
        f"- Operation: `{e.operation}`\n"
        f"- Status: `{e.status}`\n"
        f"- Konfidenz: `{e.confidence_score:.3f}` (`{e.confidence_class}`)\n"
        f"- Begründung: {e.reason}\n\n"
        f"**Original**\n\n```text\n{e.original or ''}\n```\n\n"
        f"**Ergebnis/Operation**\n\n```text\n{e.result or ''}\n```\n"
    )


def _section(title: str, entries: list[ReviewEntry]) -> str:
    body = "\n".join(_entry_md(e) for e in entries) if entries else "_Keine._\n"
    return f"## {title}\n\n{body}\n"


def render_review(report: ReviewReport) -> str:
    applied = [e for e in report.entries if e.status == 'applied']
    structural_ops = {'delete_duplicate','merge_blocks','move_text_block','replace_table','move_caption'}
    text = [e for e in applied if e.operation not in structural_ops]
    structural = [e for e in applied if e.operation in structural_ops]
    tables = [e for e in report.entries if e.category in {'tabelle','tabellenbeschriftung'}]
    captions = [e for e in report.entries if e.category in {'abbildungsbeschriftung','tabellenbeschriftung'}]
    review = [e for e in report.entries if e.status == 'review']
    unresolved = [e for e in report.entries if e.status == 'unresolved']
    rejected = [e for e in report.entries if e.status in {'reject','invalid'}]

    parts = [
        f"# Reviewbericht: {report.document}\n",
        "## Laufdaten\n\n"
        f"- Status: `{report.status}`\n"
        f"- Modell: `{report.model}`\n"
        f"- Policy-/Skill-Version: `{report.policy_version}`\n"
        f"- Aktueller Pass: `{report.current_pass or '-'}`\n"
        f"- Nächster Chunk: `{report.next_chunk or '-'}`\n",
        "## Zusammenfassung\n\n"
        f"- Einträge gesamt: {len(report.entries)}\n"
        f"- Automatisch angewendet: {len(applied)}\n"
        f"- Review empfohlen: {len(review)}\n"
        f"- Unresolved: {len(unresolved)}\n",
        _section("Angewendete Textkorrekturen", text),
        _section("Angewendete strukturelle Änderungen", structural),
        _section("Tabellenkorrekturen", tables),
        _section("Caption-Zuordnungen", captions),
        _section("Review empfohlen", review),
        _section("Ungeklärte Stellen", unresolved),
        _section("Verworfene Vorschläge", rejected),
        "## Validierungs- und Integritätsprüfung\n\n"
        f"- Geschützte Elemente: {'OK' if report.integrity_ok else 'FEHLER'}\n"
        + "".join(f"- {n}\n" for n in report.validation_notes),
    ]
    return "\n".join(parts).rstrip() + "\n"
