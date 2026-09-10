from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from .lekt_kontext import ContextWindow


class PromptConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class SkillBundle:
    skill: str
    policy: str
    version: str


def load_skill_bundle(directory: str | Path) -> SkillBundle:
    d = Path(directory)
    skill_p, policy_p = d / 'SKILL.md', d / 'POLICY.md'
    if not skill_p.is_file() or not policy_p.is_file():
        raise PromptConfigError(f"Missing SKILL.md or POLICY.md in {d}")
    skill = skill_p.read_text(encoding='utf-8')
    policy = policy_p.read_text(encoding='utf-8')
    version = 'unknown'
    for line in skill.splitlines():
        if line.lower().startswith('version:'):
            version = line.split(':', 1)[1].strip()
            break
    return SkillBundle(skill, policy, version)


_OUTPUT_PROTOCOL = """
AUSGABEPROTOKOLL (verbindlich):
Die Antwort ist genau ein JSON-Objekt mit dem Feld \"edits\". Jeder Eintrag in \"edits\" hat nur diese Felder:
- target_ids: 1 bis 4 Block-IDs aus TARGET
- category: eine der vorgegebenen Fehlerkategorien
- operation: replace_text | delete_duplicate | merge_blocks | move_text_block | replace_table | move_caption | unresolved
- replacement_text: bei replace_text, replace_table oder merge_blocks ZWINGEND und vollständig; sonst null/auslassen
- destination_id: nur bei move_text_block oder move_caption
- placement: nur bei move_text_block oder move_caption; \"before\" oder \"after\"
- confidence_score: Zahl zwischen 0 und 1
- reason: kurze Begründung, höchstens wenige Sätze

Nicht ausgeben: analysis_id, edit_id, decision, source_text, candidate_ids, keep_unchanged.
Unveränderte TARGET-Blöcke erzeugen keinen Eintrag.
Bei replace_text, replace_table oder merge_blocks MUSST du replacement_text mit dem vollständigen Ergebnis liefern. Wenn du keinen sicheren replacement_text liefern kannst: operation=unresolved und kein replacement_text.
""".strip()


def build_system_prompt(bundle: SkillBundle, pass_name: str) -> str:
    return (
        f"{bundle.skill}\n\n{bundle.policy}\n\n"
        f"Pass: {pass_name}\nVersion: {bundle.version}\n\n"
        f"{_OUTPUT_PROTOCOL}\n"
    )


def build_user_prompt(window: ContextWindow) -> str:
    rendered_blocks = []
    for b in window.blocks:
        role = "TARGET" if b.editable else "CONTEXT"
        rendered_blocks.append(
            f"[{role} | {b.block_id} | {b.block_type}]\n{b.raw_text}"
        )
    return (
        "Die Reihenfolge der folgenden Blöcke entspricht der Dokumentreihenfolge. "
        "Nur mit TARGET markierte Blöcke dürfen verändert werden; CONTEXT-Blöcke dienen ausschließlich als Kontext. "
        "Gib ausschließlich tatsächliche Änderungen und echte unresolved-Fälle zurück. "
        "Unveränderte Blöcke werden ausgelassen. Halte Begründungen kurz.\n\n"
        "DOCUMENT_WINDOW\n" + "\n\n".join(rendered_blocks)
    )
