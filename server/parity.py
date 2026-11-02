"""Strict, complete numerical evidence. Not adversarial signed attestation."""
import json
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from server.config import digest_json
from server.identity import CASE_NAMES, checker_identity, sha_file
from server.media import safe_path
from server.reference_pins import verify_sources

CONTROL_NAMES = ('channel_swap', 'landmark_swap', 'omitted_normalization', 'broadcastable_tensor',
                 'nonfinite_embedding', 'missing_case', 'stale_implementation_digest')
WRAPPER_SIZES = {'320x320': (320, 320), '479x321': (479, 321), '176x160': (176, 160)}
TOLERANCES = {'tensor_atol': 1e-4, 'tensor_rtol': 1e-5, 'cosine_min': .99999}
SHA = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{64}$')]
Nonnegative = Annotated[float, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]


class StrictEvidence(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False)


class FileRecord(StrictEvidence):
    path: str
    sha256: SHA


class CaseRecord(FileRecord):
    case_id: str


class Corpus(StrictEvidence):
    schema_version: Literal['independent-nonperson-v3']
    provider: Literal['auraface']
    checker_identity: SHA
    cases: dict[str, CaseRecord]
    sources: dict[str, FileRecord]
    detector_cases: dict[str, CaseRecord]
    scope: str

    @model_validator(mode='after')
    def inventory(self):
        if set(self.cases) != set(CASE_NAMES) or set(self.detector_cases) != set(WRAPPER_SIZES):
            raise ValueError('incomplete_reference_case_inventory')
        records = list(self.cases.values()) + list(self.detector_cases.values())
        if len({r.path for r in records}) != len(records) or len({r.sha256 for r in records}) != len(records):
            raise ValueError('duplicate_reference_case_file')
        for name, entry in self.cases.items():
            if entry.case_id != name or entry.path != f'reference-corpus/{name}.npz':
                raise ValueError('reference_case_identity_mismatch')
        for name, (width, height) in WRAPPER_SIZES.items():
            entry = self.detector_cases[name]
            if entry.case_id != name or entry.path != f'reference-corpus/detector-{width}-{height}.npz':
                raise ValueError('detector_case_identity_mismatch')
        return self


class CaseResult(CaseRecord):
    passed: StrictBool
    tensor_max_abs_error: Nonnegative
    tensor_scaled_error: Nonnegative
    embedding_cosine: Annotated[float, Field(ge=-1.00001, le=1.00001)]
    pixel_max_abs_error: Annotated[int, Field(ge=0, le=255)]
    pixel_elements_different: Annotated[int, Field(ge=0, le=112*112*3)]
    app_raw_norm: Annotated[float, Field(gt=0)]
    reference_raw_norm: Annotated[float, Field(gt=0)]

    @property
    def measured_pass(self):
        # Scaled error is max abs(a-b)/(atol+rtol*abs(reference)), the allclose rule.
        return self.tensor_scaled_error <= 1 and self.embedding_cosine >= TOLERANCES['cosine_min']

    @model_validator(mode='after')
    def coherent(self):
        if self.passed != self.measured_pass:
            raise ValueError('case_summary_contradicts_measurement')
        lower = self.tensor_max_abs_error / (TOLERANCES['tensor_atol'] + TOLERANCES['tensor_rtol'])
        upper = self.tensor_max_abs_error / TOLERANCES['tensor_atol']
        if (self.tensor_scaled_error < lower * (1 - 1e-5)
                or self.tensor_scaled_error > upper * (1 + 1e-5)):
            raise ValueError('tensor_error_measurements_contradict')
        if (self.pixel_elements_different == 0) != (self.pixel_max_abs_error == 0):
            raise ValueError('pixel_measurements_contradict')
        if self.passed and self.tensor_max_abs_error > TOLERANCES['tensor_atol'] + TOLERANCES['tensor_rtol']:
            raise ValueError('tensor_error_exceeds_normalized_range_tolerance')
        return self


class WrapperResult(CaseRecord):
    passed: StrictBool
    actual_shape: list[Count]
    reference_shape: list[Count]
    max_abs_error: Nonnegative

    @property
    def measured_pass(self):
        return self.actual_shape == self.reference_shape and self.max_abs_error == 0

    @model_validator(mode='after')
    def coherent(self):
        for shape in (self.actual_shape, self.reference_shape):
            if len(shape) != 2 or shape[1] not in (5, 15) or (shape[0] > 0 and shape[1] != 15):
                raise ValueError('invalid_wrapper_result_shape')
        if self.passed != self.measured_pass:
            raise ValueError('wrapper_summary_contradicts_measurement')
        return self


class Receipt(StrictEvidence):
    schema_version: Literal['independent-nonperson-v3']
    provider: Literal['auraface']
    status: Literal['passed', 'failed']
    model_identity: SHA
    checker_identity: SHA
    corpus_digest: SHA
    cases: dict[str, CaseResult]
    negative_controls: dict[str, StrictBool]
    negative_controls_passed: StrictBool
    detector_wrappers: dict[str, WrapperResult]
    detector_wrapper_passed: StrictBool
    tolerances: dict[str, float]
    scope: str

    @model_validator(mode='after')
    def complete(self):
        if (set(self.cases) != set(CASE_NAMES) or set(self.negative_controls) != set(CONTROL_NAMES)
                or set(self.detector_wrappers) != set(WRAPPER_SIZES) or self.tolerances != TOLERANCES):
            raise ValueError('incomplete_receipt_or_changed_tolerances')
        controls_pass = all(self.negative_controls.values())
        wrappers_pass = all(w.measured_pass for w in self.detector_wrappers.values())
        passed = controls_pass and wrappers_pass and all(c.measured_pass for c in self.cases.values())
        if (self.negative_controls_passed != controls_pass or self.detector_wrapper_passed != wrappers_pass
                or (self.status == 'passed') != passed):
            raise ValueError('receipt_summary_contradicts_results')
        return self


def validate_case(case):
    expected = {'landmarks': ((5, 2), np.dtype('float32')),
                'crop': ((112, 112, 3), np.dtype('uint8')),
                'tensor': ((1, 3, 112, 112), np.dtype('float32')),
                'embedding': ((512,), np.dtype('float32')),
                'raw_embedding': ((512,), np.dtype('float32'))}
    rgb = case['rgb']
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 1:
        raise ValueError('invalid_reference_rgb')
    for name, (shape, dtype) in expected.items():
        value = case[name]
        if value.shape != shape or value.dtype != dtype or not np.isfinite(value).all():
            raise ValueError('invalid_reference_' + name)
    if (np.linalg.norm(case['raw_embedding']) <= 1e-8
            or not np.isclose(np.linalg.norm(case['embedding']), 1, atol=1e-5)
            or np.max(np.abs(case['tensor'])) > 1.00001):
        raise ValueError('invalid_reference_norm_or_normalization')


def validate_corpus(root, manifest):
    corpus = Corpus.model_validate(manifest)
    if corpus.checker_identity != checker_identity():
        raise ValueError('stale_reference_generator_or_checker')
    pins = verify_sources(root)
    if set(corpus.sources) != set(pins):
        raise ValueError('missing_or_unexpected_reference_source')
    for name, pin in pins.items():
        entry = corpus.sources[name]
        if entry.path != 'reference-code/' + name or entry.sha256 != pin['sha256']:
            raise ValueError('reference_source_pin_mismatch:' + name)
    for records in (corpus.cases, corpus.detector_cases):
        for name, entry in records.items():
            path = safe_path(root, entry.path)
            if sha_file(path) != entry.sha256:
                raise ValueError('reference_corpus_changed')
            with np.load(path, allow_pickle=False) as case:
                if case['case_id'].shape != () or case['case_id'].item() != name:
                    raise ValueError('reference_file_identity_mismatch')
                if records is corpus.cases:
                    validate_case(case)
                else:
                    width, height = WRAPPER_SIZES[name]
                    rows, bgr = case['rows'], case['bgr']
                    if (bgr.dtype != np.uint8 or bgr.shape != (height, width, 3) or rows.ndim != 2
                            or rows.shape[1] not in (5, 15) or rows.dtype.kind != 'f' or not np.isfinite(rows).all()):
                        raise ValueError('invalid_detector_reference')
    return digest_json(corpus.model_dump())


def validate_payload(receipt, manifest, model_identity, corpus_digest):
    """Pure contract check, also usable before atomically publishing a receipt."""
    value = Receipt.model_validate(receipt)
    corpus = Corpus.model_validate(manifest)
    if (value.model_identity != model_identity or value.checker_identity != checker_identity()
            or value.corpus_digest != corpus_digest or value.status != 'passed'):
        raise ValueError('stale_or_failed_parity_receipt')
    for results, records in ((value.cases, corpus.cases), (value.detector_wrappers, corpus.detector_cases)):
        for name, result in results.items():
            entry = records[name]
            if (result.case_id, result.path, result.sha256) != (entry.case_id, entry.path, entry.sha256):
                raise ValueError('receipt_case_not_bound_to_corpus')
    return value.model_dump()


def validate_receipt(root, path, model_identity):
    if not path.is_file():
        raise ValueError('preprocessing_parity_not_run')
    manifest = json.loads(safe_path(root, 'reference-corpus/manifest.json').read_text())
    digest = validate_corpus(root, manifest)
    return validate_payload(json.loads(path.read_text()), manifest, model_identity, digest)
