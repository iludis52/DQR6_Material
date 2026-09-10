from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .lekt_config import ThresholdPolicy
from .lekt_schema import EditProposal, Operation


class ConfidenceClass(str, Enum):
    HIGH = "hoch"
    MEDIUM = "mittel"
    LOW = "niedrig"


class ApplyStatus(str, Enum):
    APPLY = "apply"
    REVIEW = "review"
    REJECT = "reject"
    UNRESOLVED = "unresolved"


STRUCTURAL_OPERATIONS = {
    Operation.DELETE_DUPLICATE,
    Operation.MERGE_BLOCKS,
    Operation.MOVE_TEXT_BLOCK,
    Operation.REPLACE_TABLE,
    Operation.MOVE_CAPTION,
}


@dataclass(frozen=True)
class PolicyDecision:
    status: ApplyStatus
    confidence_class: ConfidenceClass


def confidence_class(score: float, policy: ThresholdPolicy, *, structural: bool) -> ConfidenceClass:
    high = policy.structural_high_threshold if structural else policy.text_high_threshold
    medium = policy.structural_medium_threshold if structural else policy.text_medium_threshold
    if score >= high:
        return ConfidenceClass.HIGH
    if score >= medium:
        return ConfidenceClass.MEDIUM
    return ConfidenceClass.LOW


def decision_for_edit(edit: EditProposal, policy: ThresholdPolicy) -> PolicyDecision:
    structural = edit.operation in STRUCTURAL_OPERATIONS
    cls = confidence_class(edit.confidence_score, policy, structural=structural)

    if edit.operation is Operation.UNRESOLVED:
        return PolicyDecision(ApplyStatus.UNRESOLVED, cls)
    if cls is ConfidenceClass.HIGH:
        return PolicyDecision(ApplyStatus.APPLY, cls)
    if cls is ConfidenceClass.MEDIUM:
        return PolicyDecision(ApplyStatus.REVIEW, cls)
    return PolicyDecision(ApplyStatus.REJECT, cls)
