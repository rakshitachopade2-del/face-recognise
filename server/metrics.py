"""Person-photo metrics. Unadjudicated predictions are unresolved, never implicit negatives."""
from collections import Counter

import numpy as np

from server.evaluation import Label


def link(row):
    return row["wedding_id"], row["person_id"], row["canonical_photo_id"]


def ratio(a, b):
    return a / b if b else None


def score(labels, delivered, enrolled, previews=(), evidence=(), rejections=()):
    labels = [Label.model_validate(row).model_dump() for row in labels]
    known, truth, recognisable = set(), set(), set()
    seen = {}
    for row in labels:
        key = link(row)
        if key in seen and seen[key] != row:
            raise ValueError("conflicting_duplicate_label")
        if key in seen:
            raise ValueError("duplicate_label")
        seen[key] = row
        if row["annotation_status"] not in {"adjudicated", "source_verified"} or row["present"] is None:
            continue
        known.add(key)
        if row["present"]:
            truth.add(key)
            if row["recognisable"]:
                recognisable.add(key)
    roster = {(p["wedding_id"], p["person_id"]) for p in enrolled}
    if any(k[:2] not in roster for k in truth | {link(d) for d in delivered}):
        raise ValueError("label_or_delivery_outside_evaluated_enrollment_roster")
    raw = {link(d) for d in delivered}
    adjudicated = raw & known
    correct, wrong = adjudicated & truth, adjudicated - truth
    guests = []
    for person in sorted(roster):
        y = {k for k in truth if k[:2] == person}
        d = {k for k in adjudicated if k[:2] == person}
        tp = len(y & d)
        guests.append({"wedding_id": person[0], "person_id": person[1], "true_links": len(y),
                       "delivered_links": len(d), "correct": tp, "wrong": len(d - y),
                       "precision": None if any(k[:2] == person for k in raw - known) else ratio(tp, len(d)),
                       "recall": None if any(k[:2] == person for k in set(seen) - known) else ratio(tp, len(y)),
                       "empty": not any(k[:2] == person for k in raw)})
    def aggregate(field):
        values = [p[field] for p in guests if p[field] is not None]
        return {"mean": float(np.mean(values)) if values else None,
                "median": float(np.median(values)) if values else None,
                "p10": float(np.quantile(values, .1)) if values else None,
                "worst": min(values) if values else None, "defined_guests": len(values)}
    burst = Counter((d["wedding_id"], d.get("release_batch"))
                    for d in {link(d): d for d in delivered}.values() if link(d) in wrong)
    preview_set = {link(d) for d in previews}
    corrected = raw - {link(d) for d in rejections}
    return {
        "unit": "unique wedding/person/canonical-photo link",
        "micro": {"true_links": len(truth), "delivered_links": len(raw), "adjudicated_deliveries": len(adjudicated),
                  "correct": len(correct), "wrong": len(wrong),
                  "precision": None if raw - known else ratio(len(correct), len(raw)),
                  "adjudicated_only_precision": ratio(len(correct), len(adjudicated)),
                  "recall": None if set(seen) - known else ratio(len(correct), len(truth)),
                  "known_truth_only_recall": ratio(len(correct), len(truth)), "missed": len(truth - raw), "recognisable_support": len(recognisable),
                  "recognisable_recall": None if any(r["present"] is None or (r["present"] is True and r["recognisable"] is None) for r in labels) else ratio(len(raw & recognisable), len(recognisable))},
        "unresolved_deliveries": len(raw - known), "unresolved_label_rows": sum(
            r["annotation_status"] not in {"adjudicated", "source_verified"} or r["present"] is None for r in labels),
        "macro_precision": aggregate("precision"), "macro_recall": aggregate("recall"), "per_guest": guests,
        "empty_gallery_coverage": ratio(sum(g["empty"] for g in guests), len(guests)),
        "affected_guests": len({k[:2] for k in wrong}), "events_with_wrong_links": len({k[0] for k in wrong}),
        "maximum_wrong_release_burst": None if any(not d.get("release_batch") for d in delivered) else max(burst.values(), default=0),
        "previews": {"exposures": len(previews), "unique_links": len(preview_set),
                     "wrong_known_links": len((preview_set & known) - truth), "unresolved": len(preview_set - known)},
        "evidence": {"correct": sum(e.get("correct") is True for e in evidence),
                     "wrong": sum(e.get("correct") is False for e in evidence),
                     "unresolved": sum(e.get("correct") is None for e in evidence)},
        "operator_corrected": {"delivered_links": len(corrected), "wrong_known_links": len((corrected & known) - truth),
                               "note": "Separate from automatic metrics; rejection never erases original errors."},
        "uncertainty": "NOT ESTIMATED: event/identity-aware resampling requires sufficient independent support",
        "open_set_identification_errors": "NOT MEASURED unless evidence-face identities are independently annotated",
        "detector_recall": None, "subgroups": "INCONCLUSIVE", "recognition_accuracy_claim": False,
    }


def validate_splits(rows):
    seen = {}
    for row in rows:
        if row["split"] not in {"development", "calibration", "test"}:
            raise ValueError("unknown_split")
        # Person IDs must be global pseudonyms to reveal identity overlap across weddings.
        for kind in ("person_id", "capture_group_id"):
            value = row.get(kind)
            if not value:
                continue
            key = kind, value
            if key in seen and seen[key] != row["split"]:
                raise ValueError("split_leakage_" + kind)
            seen[key] = row["split"]
