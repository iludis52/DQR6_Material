from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Operation(str, Enum):
    REPLACE_TEXT = "replace_text"
    DELETE_DUPLICATE = "delete_duplicate"
    MERGE_BLOCKS = "merge_blocks"
    MOVE_TEXT_BLOCK = "move_text_block"
    REPLACE_TABLE = "replace_table"
    MOVE_CAPTION = "move_caption"
    UNRESOLVED = "unresolved"


class ErrorCategory(str, Enum):
    ORTHOGRAFIE = "orthografie"
    GRAMMATIK = "grammatik"
    OCR_ZEICHENFEHLER = "ocr_zeichenfehler"
    WORTTRENNUNG = "worttrennung"
    SATZFRAGMENT = "satzfragment"
    DUPLIKAT = "duplikat"
    LESEREIHENFOLGE = "lesereihenfolge"
    MARKDOWN = "markdown"
    TABELLE = "tabelle"
    ABBILDUNGSBESCHRIFTUNG = "abbildungsbeschriftung"
    TABELLENBESCHRIFTUNG = "tabellenbeschriftung"
    UNKLAR = "unklar"


class EditProposal(StrictModel):
    """Compact wire object produced by the LLM.

    Technical metadata (edit id, original/source text) is deliberately derived in
    Python. Keeping it out of the constrained generation reduces output size and
    prevents the model from reproducing long source blocks needlessly.
    """

    target_ids: list[str] = Field(min_length=1, max_length=4)
    category: ErrorCategory
    operation: Operation
    replacement_text: str | None = None
    destination_id: str | None = Field(default=None, max_length=64)
    placement: Literal["before", "after"] | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=300)

    @property
    def edit_id(self) -> str:
        # Stable technical id without asking the model to invent one.
        payload = self.model_dump_json(exclude_none=True)
        return "edit_" + sha256(payload.encode("utf-8")).hexdigest()[:16]

    @model_validator(mode="after")
    def validate_protocol_contract(self) -> "EditProposal":
        op = self.operation

        if op is Operation.UNRESOLVED:
            if self.replacement_text is not None:
                raise ValueError("unresolved must not contain replacement_text")
            if self.destination_id is not None or self.placement is not None:
                raise ValueError("unresolved must not contain move fields")
            return self

        if op in {Operation.REPLACE_TEXT, Operation.REPLACE_TABLE}:
            if self.replacement_text is None:
                raise ValueError(f"{op.value} requires replacement_text")

        if op is Operation.MERGE_BLOCKS:
            if len(self.target_ids) < 2:
                raise ValueError("merge_blocks requires at least two target_ids")
            if self.replacement_text is None:
                raise ValueError("merge_blocks requires replacement_text")

        if op is Operation.DELETE_DUPLICATE:
            if len(self.target_ids) != 1:
                raise ValueError("delete_duplicate requires exactly one target_id")
            if self.replacement_text is not None:
                raise ValueError("delete_duplicate must not contain replacement_text")

        if op in {Operation.MOVE_TEXT_BLOCK, Operation.MOVE_CAPTION}:
            if len(self.target_ids) != 1:
                raise ValueError(f"{op.value} requires exactly one target_id")
            if self.destination_id is None:
                raise ValueError(f"{op.value} requires destination_id")
            if self.replacement_text is not None:
                raise ValueError(f"{op.value} must not contain replacement_text")

        if op not in {Operation.MOVE_TEXT_BLOCK, Operation.MOVE_CAPTION}:
            if self.destination_id is not None or self.placement is not None:
                raise ValueError(f"{op.value} must not contain move fields")

        return self


@dataclass(frozen=True)
class InvalidEdit:
    index: int
    raw: dict
    error: str


class AnalysisResponse(StrictModel):
    edits: list[EditProposal] = Field(default_factory=list, max_length=32)
    _invalid_edits: list[InvalidEdit] = PrivateAttr(default_factory=list)

    @property
    def invalid_edits(self) -> tuple[InvalidEdit, ...]:
        return tuple(self._invalid_edits)
