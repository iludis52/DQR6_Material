from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .lekt_checkpoint import CheckpointState, atomic_write_text, load_checkpoint, save_checkpoint
from .lekt_config import AppConfig, ThresholdPolicy, read_source_text
from .lekt_kontext import (
    ContextBudgetError,
    ContextWindow,
    build_context_window,
    estimate_tokens,
    partition_target_ids,
)
from .lekt_llm import LMStudioOpenAIClient
from .lekt_manifest import build_manifest
from .lekt_markdown import parse_markdown
from .lekt_patches import PatchError, apply_edits
from .lekt_pfade import resolve_document_paths
from .lekt_policy import ApplyStatus, decision_for_edit
from .lekt_prompts import SkillBundle, build_system_prompt, build_user_prompt, load_skill_bundle
from .lekt_review import ReviewEntry, ReviewReport, render_review
from .lekt_schema import EditProposal, Operation
from .lekt_schutz import inventory_protected, validate_protected
from .lekt_validierung import MarkdownValidationError, validate_markdown_structure, validate_markdown_table


TEXT_TYPES = {"heading", "paragraph", "list", "math"}
STRUCTURE_TYPES = {"heading", "paragraph", "list"}


_MINIMAL_BUNDLE = SkillBundle(
    skill="Du korrigierst OCR-erzeugtes Markdown konservativ und erfindest keine Inhalte.",
    policy="Bei Unsicherheit verwende unresolved. Liefere ausschließlich strukturierte Edits.",
    version="embedded-minimal",
)


def _messages(window: ContextWindow, pass_name: str, bundle: SkillBundle | None = None) -> list[dict[str, str]]:
    active_bundle = bundle or _MINIMAL_BUNDLE
    return [
        {"role": "system", "content": build_system_prompt(active_bundle, pass_name)},
        {"role": "user", "content": build_user_prompt(window)},
    ]


def _messages_token_estimate(messages: list[dict[str, str]]) -> int:
    # Technical budget only; no semantic inference is based on this estimate.
    return sum(estimate_tokens(m.get("content", "")) + 8 for m in messages)


def _fit_windows(
    blocks,
    target_ids: list[str],
    *,
    bundle: SkillBundle | None,
    pass_name: str,
    overlap: int,
    max_input_tokens: int,
    target_chunk_tokens: int,
) -> list[ContextWindow]:
    if max_input_tokens <= 0:
        raise ContextBudgetError("max_input_tokens must be > 0")

    initial_batches = partition_target_ids(
        blocks,
        target_ids,
        max_target_tokens=min(target_chunk_tokens, max_input_tokens),
    )
    windows: list[ContextWindow] = []

    def add_batch(batch: list[str]) -> None:
        current_overlap = max(0, overlap)
        while True:
            window = build_context_window(blocks, batch, overlap=current_overlap)
            if _messages_token_estimate(_messages(window, pass_name, bundle)) <= max_input_tokens:
                windows.append(window)
                return
            if current_overlap > 0:
                current_overlap -= 1
                continue
            if len(batch) > 1:
                mid = len(batch) // 2
                add_batch(batch[:mid])
                add_batch(batch[mid:])
                return
            block_id = batch[0]
            raise ContextBudgetError(
                f"Single target block {block_id} exceeds the configured input budget "
                f"({max_input_tokens} estimated tokens)."
            )

    for batch in initial_batches:
        add_batch(batch)
    return windows


def _entry(
    edit: EditProposal,
    status: str,
    cls: str,
    result: str | None = None,
    original: str | None = None,
) -> ReviewEntry:
    return ReviewEntry(
        edit_id=edit.edit_id,
        target_ids=list(edit.target_ids),
        category=edit.category.value,
        operation=edit.operation.value,
        original=original,
        result=result if result is not None else edit.replacement_text,
        confidence_score=edit.confidence_score,
        confidence_class=cls,
        reason=edit.reason,
        status=status,
    )



def _invalid_response_entry(invalid, target_blocks: dict[str, object] | None = None) -> ReviewEntry:
    raw = invalid.raw if isinstance(invalid.raw, dict) else {}
    target_ids = [x for x in raw.get("target_ids", []) if isinstance(x, str)]
    original = None
    if target_blocks and target_ids:
        block = target_blocks.get(target_ids[0])
        original = getattr(block, "raw_text", None) if block is not None else None

    category = raw.get("category") if isinstance(raw.get("category"), str) else "unklar"
    operation = raw.get("operation") if isinstance(raw.get("operation"), str) else "invalid"
    replacement = raw.get("replacement_text") if isinstance(raw.get("replacement_text"), str) else None
    confidence = raw.get("confidence_score")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))

    raw_reason = raw.get("reason") if isinstance(raw.get("reason"), str) else ""
    reason = f"Ungültiger LLM-Edit: {invalid.error}"
    if raw_reason:
        reason += f" | Modellbegründung: {raw_reason[:180]}"

    return ReviewEntry(
        edit_id=f"invalid_{invalid.index:02d}",
        target_ids=target_ids,
        category=category,
        operation=operation,
        original=original,
        result=replacement,
        confidence_score=confidence,
        confidence_class="n/a",
        reason=reason,
        status="invalid",
    )

def _evaluate_response(
    response,
    policy: ThresholdPolicy,
    *,
    allowed_target_ids: set[str],
    target_blocks: dict[str, object] | None = None,
    table_mode: bool = False,
) -> tuple[list[EditProposal], list[ReviewEntry]]:
    entries: list[ReviewEntry] = [
        _invalid_response_entry(invalid, target_blocks)
        for invalid in getattr(response, "invalid_edits", ())
    ]
    to_apply: list[EditProposal] = []

    for edit in response.edits:
        original = None
        if target_blocks and edit.target_ids:
            block = target_blocks.get(edit.target_ids[0])
            original = getattr(block, "raw_text", None) if block is not None else None

        # Ersatz identisch mit dem Original ("Keine Fehler gefunden"): kein Edit,
        # sondern Rauschen – sonst stünde es im Review als angewendete Korrektur.
        if (edit.operation in {Operation.REPLACE_TEXT, Operation.REPLACE_TABLE}
                and original is not None and len(edit.target_ids) == 1
                and (edit.replacement_text or "").strip() == original.strip()):
            continue

        if not set(edit.target_ids).issubset(allowed_target_ids):
            entries.append(_entry(edit, "invalid", "n/a", "target outside editable window", original=original))
            continue

        pd = decision_for_edit(edit, policy)
        cls = pd.confidence_class.value
        if pd.status is ApplyStatus.UNRESOLVED:
            entries.append(_entry(edit, "unresolved", cls, original=original))
            continue
        if pd.status is ApplyStatus.REVIEW:
            entries.append(_entry(edit, "review", cls, original=original))
            continue
        if pd.status is ApplyStatus.REJECT:
            entries.append(_entry(edit, "reject", cls, original=original))
            continue

        if table_mode and edit.operation is Operation.REPLACE_TABLE:
            try:
                validate_markdown_table(edit.replacement_text or "")
            except MarkdownValidationError as exc:
                entries.append(_entry(edit, "invalid", cls, str(exc), original=original))
                continue

        to_apply.append(edit)
        result = edit.replacement_text
        if edit.operation in {Operation.MOVE_CAPTION, Operation.MOVE_TEXT_BLOCK}:
            result = f"{edit.operation.value} -> {edit.destination_id} ({edit.placement or 'after'})"
        elif edit.operation is Operation.DELETE_DUPLICATE:
            result = "delete_duplicate"
        entries.append(_entry(edit, "applied", cls, result, original=original))

    return to_apply, entries


# --- Öffentliche Orchestrierung ---------------------------------------------

@dataclass(frozen=True)
class CorrectionResult:
    corrected_path: Path
    review_path: Path
    manifest_path: Path
    entries: tuple[ReviewEntry, ...]
    status: str


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parent / 'skills' / 'markdown_lektorat'


def _checkpoint_dir(source: Path) -> Path:
    parts = source.parts
    try:
        idx = parts.index('processed')
    except ValueError:
        return source.parent / '.lektorat'
    if idx > 0:
        data_root = Path(*parts[:idx])
        return data_root / 'interim' / 'lektorat' / source.stem
    return source.parent / '.lektorat'


def _technical_run_dir(source: Path, run_id: str) -> Path:
    return _checkpoint_dir(source) / 'runs' / run_id


def _atomic_write_utf8(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def _sha256_text(text: str) -> str:
    return sha256(text.encode('utf-8')).hexdigest()


def _review_from_state(
    *, source_stem: str, model: str, bundle: SkillBundle,
    entries: list[ReviewEntry], status: str, current_pass: str | None,
    next_chunk_index: int | None, integrity_ok: bool,
) -> str:
    next_chunk = None
    if current_pass is not None and next_chunk_index is not None:
        next_chunk = f"{current_pass}:{next_chunk_index:04d}"
    report = ReviewReport(
        document=source_stem,
        model=model,
        policy_version=bundle.version,
        entries=entries,
        integrity_ok=integrity_ok,
        validation_notes=[
            'Zwischenergebnis nach jedem erfolgreichen Chunk atomar gespeichert',
            'Protected-Element-Invarianten geprüft',
        ],
        status=status,
        current_pass=current_pass,
        next_chunk=next_chunk,
    )
    return render_review(report)


def _serialize_edits(edits: list[EditProposal]) -> list[dict]:
    return [e.model_dump(mode='json') for e in edits]


def _deserialize_edits(items: list[dict]) -> list[EditProposal]:
    return [EditProposal.model_validate(item) for item in items]


def _serialize_entries(entries: list[ReviewEntry]) -> list[dict]:
    return [asdict(e) for e in entries]


def _deserialize_entries(items: list[dict]) -> list[ReviewEntry]:
    return [ReviewEntry(**item) for item in items]


def _pass_definition(config: AppConfig):
    return [
        ('text', TEXT_TYPES, config.processing.text_chunk_tokens, config.processing.overlap_blocks, False),
        ('table', {'table'}, config.processing.table_chunk_tokens, config.processing.overlap_blocks, True),
        ('structure', STRUCTURE_TYPES, config.processing.structure_chunk_tokens, max(4, config.processing.overlap_blocks), False),
        ('caption', {'paragraph', 'table'}, config.processing.caption_chunk_tokens, max(5, config.processing.overlap_blocks), False),
    ]


def _windows_for_pass(
    source: str, *, pass_name: str, target_types: set[str], bundle: SkillBundle,
    overlap: int, max_input_tokens: int, target_chunk_tokens: int,
):
    doc = parse_markdown(source)
    target_ids = [b.block_id for b in doc.blocks if b.block_type in target_types]
    if not target_ids:
        return doc, []
    windows = _fit_windows(
        doc.blocks,
        target_ids,
        bundle=bundle,
        pass_name=pass_name,
        overlap=overlap,
        max_input_tokens=max_input_tokens,
        target_chunk_tokens=target_chunk_tokens,
    )
    return doc, windows


def _candidate_from_edits(
    base_source: str, base_blocks, edits: list[EditProposal], original_inventory,
) -> str:
    if not edits:
        candidate = base_source
    else:
        candidate = apply_edits(base_source, base_blocks, edits)
    validate_protected(original_inventory, candidate)
    validate_markdown_structure(candidate)
    return candidate


def correct_markdown(
    config: AppConfig,
    *,
    client=None,
    skill_dir: str | Path | None = None,
    fortschritt: Callable[[str], None] | None = None,
    modellwechsel_erlauben: bool = False,
) -> CorrectionResult:
    """Lektoriert `config.input.document_path` in vier Pässen.

    `fortschritt` erhält je Chunk eine kurze Statuszeile (z. B. für eine
    Oberfläche); ohne Angabe läuft alles still wie bisher.
    """
    melde = fortschritt or (lambda _zeile: None)
    source_path = config.input.document_path
    checkpoint_dir = _checkpoint_dir(source_path)
    checkpoint_path = checkpoint_dir / 'checkpoint.json'
    pass_base_path = checkpoint_dir / 'pass_base.md'
    resume_available = config.processing.resume and checkpoint_path.is_file()

    # Existing outputs are allowed only when they belong to a resumable run.
    paths = resolve_document_paths(
        source_path,
        output_dir=config.output.output_dir,
        overwrite=(config.output.overwrite or resume_available),
    )
    source = read_source_text(config.input)
    source_hash = _sha256_text(source)
    original_inventory = inventory_protected(source)

    bundle = load_skill_bundle(skill_dir or _default_skill_dir())
    llm = client or LMStudioOpenAIClient(config.lm, retry_count=config.processing.retry_count)
    llm.preflight()
    policy = config.confidence.for_model(config.lm.model)

    max_input_tokens = (
        config.processing.max_context_tokens
        - config.lm.max_output_tokens
        - config.processing.context_reserve_tokens
    )
    if max_input_tokens <= 0:
        raise ValueError(
            'Context budget invalid: max_context_tokens must exceed '
            'max_output_tokens + context_reserve_tokens'
        )

    pass_defs = _pass_definition(config)
    pass_names = [p[0] for p in pass_defs]

    if resume_available:
        state = load_checkpoint(checkpoint_path)
        if state.source_sha256 != source_hash:
            raise RuntimeError('Checkpoint does not belong to the current source file')
        if state.model != config.lm.model and modellwechsel_erlauben and state.status != 'completed':
            # Etwa: LM Studio abgestürzt, weiter mit DeepInfra. Bereits
            # festgeschriebene Chunks bleiben, der Rest läuft mit dem neuen Modell.
            melde(f"Modellwechsel bei Wiederaufnahme: {state.model} -> {config.lm.model}")
            state.model = config.lm.model
        if state.model != config.lm.model:
            raise RuntimeError(
                f"Checkpoint model mismatch: {state.model!r} != {config.lm.model!r}. "
                'Finish/restart the old run or remove its checkpoint deliberately.'
            )
        if state.status == 'completed':
            if not paths.corrected.is_file() or not paths.review.is_file():
                raise RuntimeError('Completed checkpoint exists but output artifacts are missing')
            run_dir = checkpoint_dir / 'runs'
            manifests = sorted(run_dir.glob('*/manifest.json')) if run_dir.exists() else []
            manifest_path = manifests[-1] if manifests else checkpoint_path
            return CorrectionResult(paths.corrected, paths.review, manifest_path, tuple(_deserialize_entries(state.entries)), 'ok')
        if not pass_base_path.is_file():
            raise RuntimeError('Resume checkpoint exists but pass_base artifact is missing')
        # Scheitert schon der erste Chunk, wurde _korr.md nie geschrieben. Das
        # ist kein Hindernis: der Stand wird unten aus pass_base + gespeicherten
        # Edits rekonstruiert und gegen den Checkpoint-Hash geprüft. Früher
        # machte genau dieser Fall den Checkpoint dauerhaft unbrauchbar.
        if paths.corrected.is_file():
            current = paths.corrected.read_text(encoding='utf-8')
            if state.current_corrected_sha256 and _sha256_text(current) != state.current_corrected_sha256:
                raise RuntimeError('Corrected artifact differs from checkpoint; refusing unsafe resume')
        else:
            current = pass_base_path.read_text(encoding='utf-8')
        all_entries = _deserialize_entries(state.entries)
        current_pass = state.current_pass
        if current_pass not in pass_names:
            raise RuntimeError(f'Unknown pass in checkpoint: {current_pass}')
        start_pass_index = pass_names.index(current_pass)
    else:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        current = source
        all_entries: list[ReviewEntry] = []
        current_pass = pass_names[0]
        start_pass_index = 0
        _atomic_write_utf8(pass_base_path, current)
        state = CheckpointState(
            source_sha256=source_hash,
            model=config.lm.model,
            current_pass=current_pass,
            next_chunk_index=0,
            completed_chunk_ids=[],
            current_corrected_sha256=_sha256_text(current),
            status='running',
            entries=[],
            applied_edits=[],
        )
        save_checkpoint(checkpoint_path, state)

    pass_status: dict[str, str] = {name: ('ok' if i < start_pass_index else 'pending') for i, name in enumerate(pass_names)}

    for pass_index in range(start_pass_index, len(pass_defs)):
        name, target_types, chunk_tokens, overlap, table_mode = pass_defs[pass_index]

        if state.current_pass != name:
            state.current_pass = name
            state.next_chunk_index = 0
            state.applied_edits = []
            _atomic_write_utf8(pass_base_path, current)
            save_checkpoint(checkpoint_path, state)

        base_source = pass_base_path.read_text(encoding='utf-8')
        base_doc, windows = _windows_for_pass(
            base_source,
            pass_name=name,
            target_types=target_types,
            bundle=bundle,
            overlap=overlap,
            max_input_tokens=max_input_tokens,
            target_chunk_tokens=chunk_tokens,
        )
        cumulative_edits = _deserialize_edits(state.applied_edits)

        # Reconstruct the exact last committed state from the frozen pass base.
        current = _candidate_from_edits(base_source, base_doc.blocks, cumulative_edits, original_inventory)
        if state.current_corrected_sha256 and _sha256_text(current) != state.current_corrected_sha256:
            raise RuntimeError('Checkpoint edit state does not reconstruct the persisted corrected document')

        melde(f"Pass {name}: {len(windows)} Chunks, ab Chunk {state.next_chunk_index + 1}")
        for chunk_index in range(state.next_chunk_index, len(windows)):
            window = windows[chunk_index]
            chunk_id = f'{name}:{chunk_index:04d}'
            melde(f"  {name} {chunk_index + 1}/{len(windows)}")
            try:
                response = llm.analyze(_messages(window, name, bundle))
                edits, entries = _evaluate_response(
                    response,
                    policy,
                    allowed_target_ids=set(window.target_ids),
                    target_blocks={b.block_id: b for b in base_doc.blocks},
                    table_mode=table_mode,
                )

                proposed_cumulative = cumulative_edits + edits
                try:
                    candidate = _candidate_from_edits(
                        base_source, base_doc.blocks, proposed_cumulative, original_inventory
                    )
                    cumulative_edits = proposed_cumulative
                except (PatchError, MarkdownValidationError, RuntimeError) as exc:
                    # The LLM call itself completed. Preserve source and audit the invalid edits,
                    # then advance to avoid an endless retry loop on the same formal failure.
                    for e in entries:
                        if e.status == 'applied':
                            e.status = 'invalid'
                            e.result = str(exc)
                    candidate = current

                all_entries.extend(entries)
                current = candidate
                state.status = 'running'
                state.next_chunk_index = chunk_index + 1
                state.completed_chunk_ids.append(chunk_id)
                state.current_corrected_sha256 = _sha256_text(current)
                state.entries = _serialize_entries(all_entries)
                state.applied_edits = _serialize_edits(cumulative_edits)

                # Commit order: content -> human review -> machine checkpoint (commit marker).
                _atomic_write_utf8(paths.corrected, current)
                _atomic_write_utf8(
                    paths.review,
                    _review_from_state(
                        source_stem=paths.source.stem,
                        model=config.lm.model,
                        bundle=bundle,
                        entries=all_entries,
                        status='UNVOLLSTÄNDIG',
                        current_pass=name,
                        next_chunk_index=state.next_chunk_index,
                        integrity_ok=True,
                    ),
                )
                save_checkpoint(checkpoint_path, state)
            except Exception:
                state.status = 'failed'
                state.current_corrected_sha256 = _sha256_text(current)
                state.entries = _serialize_entries(all_entries)
                state.applied_edits = _serialize_edits(cumulative_edits)
                if paths.corrected.exists():
                    _atomic_write_utf8(
                        paths.review,
                        _review_from_state(
                            source_stem=paths.source.stem,
                            model=config.lm.model,
                            bundle=bundle,
                            entries=all_entries,
                            status='UNVOLLSTÄNDIG',
                            current_pass=name,
                            next_chunk_index=chunk_index,
                            integrity_ok=True,
                        ),
                    )
                save_checkpoint(checkpoint_path, state)
                raise

        pass_status[name] = 'ok'

        # Prepare a stable frozen source for the next pass.
        if pass_index + 1 < len(pass_defs):
            next_name = pass_defs[pass_index + 1][0]
            _atomic_write_utf8(pass_base_path, current)
            state.current_pass = next_name
            state.next_chunk_index = 0
            state.applied_edits = []
            state.current_corrected_sha256 = _sha256_text(current)
            state.status = 'running'
            save_checkpoint(checkpoint_path, state)

    # Final hard gates.
    validate_protected(original_inventory, current)
    validate_markdown_structure(current)
    if _sha256_text(read_source_text(config.input)) != source_hash:
        raise RuntimeError('Source file changed during processing')

    _atomic_write_utf8(paths.corrected, current)
    _atomic_write_utf8(
        paths.review,
        _review_from_state(
            source_stem=paths.source.stem,
            model=config.lm.model,
            bundle=bundle,
            entries=all_entries,
            status='ABGESCHLOSSEN',
            current_pass=None,
            next_chunk_index=None,
            integrity_ok=True,
        ),
    )

    state.status = 'completed'
    state.next_chunk_index = 0
    state.applied_edits = []
    state.current_corrected_sha256 = _sha256_text(current)
    state.entries = _serialize_entries(all_entries)
    save_checkpoint(checkpoint_path, state)

    run_id = uuid4().hex
    run_dir = _technical_run_dir(paths.source, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        input_path=paths.source,
        model=config.lm.model,
        base_url=config.lm.base_url,
        inference_parameters={
            'temperature': config.lm.temperature,
            'max_output_tokens': config.lm.max_output_tokens,
            'max_context_tokens': config.processing.max_context_tokens,
            'context_reserve_tokens': config.processing.context_reserve_tokens,
            'text_chunk_tokens': config.processing.text_chunk_tokens,
            'table_chunk_tokens': config.processing.table_chunk_tokens,
            'structure_chunk_tokens': config.processing.structure_chunk_tokens,
            'caption_chunk_tokens': config.processing.caption_chunk_tokens,
            'resume': config.processing.resume,
        },
        skill_version=bundle.version,
        pass_status=pass_status,
        output_hashes={
            'corrected': sha256(paths.corrected.read_bytes()).hexdigest(),
            'review': sha256(paths.review.read_bytes()).hexdigest(),
        },
        run_id=run_id,
    )
    manifest_path = run_dir / 'manifest.json'
    _atomic_write_utf8(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

    return CorrectionResult(
        corrected_path=paths.corrected,
        review_path=paths.review,
        manifest_path=manifest_path,
        entries=tuple(all_entries),
        status='ok',
    )
