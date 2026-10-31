"""Reproduce illustrative arithmetic; no network, photos, or measured benchmarks."""
import json
from decimal import Decimal as D


def scenario(photos: int, faces: int, guests: int) -> dict:
    references = 3 * guests
    a_calls = photos + references
    b_calls = photos + references + guests + faces
    op_rate, live_rate, vector_month_rate = D("0.001"), D("0.015"), D("0.00001")
    a_ops, b_ops = D(a_calls) * op_rate, D(b_calls) * op_rate
    liveness = D(guests) * live_rate
    gallery_retention = D(faces * 12) * vector_month_rate
    b_retention = D((faces + references + guests) * 12) * vector_month_rate
    a_total = a_ops + liveness + gallery_retention
    b_total = b_ops + liveness + b_retention
    return {
        "inputs": {"photos": photos, "faces": faces, "guests": guests,
                   "references_per_guest": 3, "months": 12},
        "group1_calls": {"completed_album_A": a_calls, "incremental_B": b_calls},
        "illustrative_USD": {
            "A_recognition": str(a_ops), "B_recognition": str(b_ops),
            "liveness_one_attempt": str(liveness),
            "gallery_retention": str(gallery_retention),
            "B_all_vector_retention": str(b_retention),
            "A_partial_total": str(a_total), "B_partial_total": str(b_total),
            "ten_weddings_A_recognition_plus_liveness": str(10 * (a_ops + liveness)),
            "ten_weddings_B_recognition_plus_liveness": str(10 * (b_ops + liveness)),
        },
        "hypothetical_INR_sensitivity": {
            str(fx): {"A_partial": str(a_total * fx), "B_partial": str(b_total * fx)}
            for fx in (D(90), D(100))
        },
        "repeated_A_searches_72_batches": references * 72,
        "float32_512d_vector_MiB": faces * 512 * 4 / (1024 ** 2),
    }


if __name__ == "__main__":
    print(json.dumps({
        "status": "ILLUSTRATIVE ARITHMETIC ONLY; NOT MEASURED; NOT A MUMBAI QUOTE",
        "rate_source": "https://aws.amazon.com/rekognition/pricing/",
        "rate_context": "Published examples; liveness example explicitly US East. Reverify target region.",
        "FX_context": "90 and 100 INR/USD are hypothetical sensitivity inputs, not current FX.",
        "excluded": ["tax", "ordinary media", "shared infrastructure", "retries", "tiling"],
        "reference": scenario(5000, 20000, 300),
        "large": scenario(15000, 60000, 1000),
    }, indent=2))
