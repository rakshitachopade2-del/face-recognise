"""Compare local adapter output with independently captured upstream-reference tensors.

NPZ fields: rgb (uint8 HWC), landmarks (5,2), tensor (1,3,112,112), embedding (D,).
Reference generation must be independent of server.providers; see docs/MODELS.md.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from server.config import Settings
from server.media import atomic_write
from server.providers import RealProvider, unit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-source", required=True, help="Exact upstream runtime revision / command used")
    parser.add_argument("--authorization", required=True, help="Permission record for reference image or synthetic pattern")
    args = parser.parse_args()
    settings = Settings.environment()
    op = settings.operating_point()
    if op.provider == "synthetic":
        parser.error("Set FACE_CONFIG to an approved real provider configuration")
    provider = RealProvider(settings, op, require_parity=False)
    with np.load(args.reference, allow_pickle=False) as reference:
        tensor = provider.preprocess(reference["rgb"], reference["landmarks"])
        embedding = provider.embed(tensor)
        tensor_error = float(np.max(np.abs(tensor - reference["tensor"])))
        cosine = float(embedding @ unit(reference["embedding"]))
        passed = bool(np.allclose(tensor, reference["tensor"], atol=1e-4, rtol=1e-5) and cosine >= .99999)
    receipt = {"status": "passed" if passed else "failed", "model_identity": provider.model_identity,
               "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
               "reference_source": args.reference_source, "authorization": args.authorization,
               "tensor_max_abs_error": tensor_error, "embedding_cosine": cosine,
               "tolerances": {"tensor_atol": 1e-4, "tensor_rtol": 1e-5, "embedding_cosine_min": .99999},
               "scope": "preprocessing/runtime parity only; not recognition accuracy or legal clearance"}
    atomic_write(settings.data_dir, str(provider.parity_path.relative_to(settings.data_dir)), json.dumps(receipt, indent=2).encode())
    print(json.dumps({k: receipt[k] for k in ("status", "tensor_max_abs_error", "embedding_cosine")}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
