"""Shared exact baseline used by worker and evaluation; scores are not probabilities."""
from dataclasses import dataclass

import numpy as np

from server.providers import ProviderError, unit


@dataclass
class Decision:
    candidate: str | None
    generation: int | None
    score: float | None
    margin: float | None
    accepted: bool
    reason: str


def decide(vector, namespace, enrollments, op):
    if vector is None:
        return Decision(None, None, None, None, False, "unusable_face")
    compatible = [e for e in enrollments if e["namespace"] == namespace]
    if not compatible:
        return Decision(None, None, None, None, False, "no_compatible_enrollment")
    # One aggregated reference per distinct identity; never compare reference frames as separate guests.
    scores = []
    face = unit(vector)
    for start in range(0, len(compatible), 256):
        chunk = compatible[start:start + 256]
        matrix = np.stack([unit(e["vector"]) for e in chunk])
        if matrix.shape[1] != face.size:
            raise ProviderError("embedding_dimension_mismatch")
        scores.extend((float(score), e) for score, e in zip(matrix @ face, chunk))
    scores.sort(key=lambda item: (-item[0], item[1]["participant_id"]))
    best, guest = scores[0]
    margin = best - scores[1][0] if len(scores) > 1 else None
    reason = "accepted"
    if best < op.acceptance:
        reason = "below_acceptance"
    elif margin is not None and (margin <= 1e-7 or margin < op.margin):
        reason = "ambiguous"
    return Decision(guest["participant_id"], guest["generation"], best, margin,
                    reason == "accepted", reason)


def aggregate(vectors, op):
    if len(vectors) != op.enrollment_count:
        raise ProviderError(f"supply_exactly_{op.enrollment_count}_references")
    matrix = np.stack([unit(v) for v in vectors])
    if len(matrix) > 1 and np.min((matrix @ matrix.T)[np.triu_indices(len(matrix), 1)]) < op.consistency:
        raise ProviderError("inconsistent_references_retry_with_same_participant")
    return unit(matrix.mean(axis=0))
