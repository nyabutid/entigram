from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


LIFECYCLE_PROPOSED = "proposed"
LIFECYCLE_REVIEWED = "reviewed"
LIFECYCLE_VERIFIED = "verified"
LIFECYCLE_DEPRECATED = "deprecated"
LIFECYCLE_REJECTED = "rejected"

TRUSTED_LIFECYCLE_STATUSES = {LIFECYCLE_REVIEWED, LIFECYCLE_VERIFIED}
UNTRUSTED_LIFECYCLE_STATUSES = {
    LIFECYCLE_PROPOSED,
    LIFECYCLE_DEPRECATED,
    LIFECYCLE_REJECTED,
}

EVIDENCE_SCHEMA_MATCH = "schema_match"
EVIDENCE_SAMPLE_DATA_MATCH = "sample_data_match"
EVIDENCE_HUMAN_REVIEW = "human_review"
EVIDENCE_INTEGRATION_TEST = "integration_test"
EVIDENCE_RUNTIME_OBSERVATION = "runtime_observation"
EVIDENCE_IMPORTED_ALIGNMENT = "imported_alignment"

TRUSTED_EVIDENCE_TYPES = {
    EVIDENCE_HUMAN_REVIEW,
    EVIDENCE_INTEGRATION_TEST,
    EVIDENCE_SAMPLE_DATA_MATCH,
}


@dataclass(frozen=True)
class GroundingDecision:
    allowed: bool
    reason: str


def normalize_lifecycle_status(status: Optional[str]) -> str:
    if not status:
        return LIFECYCLE_PROPOSED
    status = status.strip().lower()
    allowed = TRUSTED_LIFECYCLE_STATUSES | UNTRUSTED_LIFECYCLE_STATUSES
    return status if status in allowed else LIFECYCLE_PROPOSED


def is_trusted_alignment(
    alignment: Dict[str, Any],
    *,
    minimum_confidence: float = 0.8,
    require_evidence: bool = True,
) -> GroundingDecision:
    lifecycle_status = normalize_lifecycle_status(
        alignment.get("lifecycle_status") or alignment.get("status")
    )
    if lifecycle_status not in TRUSTED_LIFECYCLE_STATUSES:
        return GroundingDecision(False, f"lifecycle status is {lifecycle_status}")

    if not bool(alignment.get("verified")):
        return GroundingDecision(False, "alignment is not verified")

    confidence = float(alignment.get("confidence") or 0.0)
    if confidence < minimum_confidence:
        return GroundingDecision(False, f"confidence {confidence:.2f} is below {minimum_confidence:.2f}")

    evidence_type = alignment.get("evidence_type")
    if require_evidence and evidence_type not in TRUSTED_EVIDENCE_TYPES:
        return GroundingDecision(False, f"evidence type {evidence_type!r} is not trusted")

    return GroundingDecision(True, "verified ontology alignment")


def trusted_alignments(
    alignments: Iterable[Dict[str, Any]],
    *,
    minimum_confidence: float = 0.8,
    require_evidence: bool = True,
) -> list:
    return [
        alignment
        for alignment in alignments
        if is_trusted_alignment(
            alignment,
            minimum_confidence=minimum_confidence,
            require_evidence=require_evidence,
        ).allowed
    ]
