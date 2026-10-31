from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]


class OperatingPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    provider: Literal["synthetic", "auraface", "sface"]
    state: Literal["uncalibrated", "provisional", "validated"]
    acceptance: float = Field(ge=-1, le=1)
    margin: float = Field(ge=0, le=2)
    consistency: float = Field(ge=-1, le=1)
    enrollment_count: Literal[1, 3, 5]
    detector_score: float = Field(gt=0, lt=1)
    detector_max_side: int = Field(ge=320, le=8192)
    min_face_px: int = Field(ge=1)
    min_blur: float = Field(ge=0)
    note: str

    @property
    def fingerprint(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["local"] = "local"
    host: Literal["127.0.0.1", "localhost", "::1"] = "127.0.0.1"
    data_dir: Path = ROOT / "var"
    config_path: Path = ROOT / "configs/synthetic.json"
    registry_path: Path = ROOT / "configs/models.json"
    max_bytes: int = 25 * 1024 * 1024
    max_pixels: int = 40_000_000
    lease_seconds: float = 30
    max_attempts: int = 3
    origins: tuple[str, ...] = ("http://127.0.0.1:5177", "http://localhost:5177")

    @model_validator(mode="after")
    def private_store(self):
        self.data_dir = self.data_dir.resolve()
        if self.data_dir in {ROOT, ROOT / "web"} or ROOT / "web" in self.data_dir.parents:
            raise ValueError("Private data must be outside web/ and the source root")
        if self.lease_seconds <= 0 or self.max_attempts < 1:
            raise ValueError("Invalid worker bounds")
        if not set(self.origins).issubset({"http://127.0.0.1:5177", "http://localhost:5177"}):
            raise ValueError("Only the local browser origins are supported")
        return self

    @classmethod
    def environment(cls):
        fields = {key: os.environ[env] for key, env in {
            "data_dir": "FACE_DATA_DIR", "config_path": "FACE_CONFIG",
            "registry_path": "FACE_MODELS", "mode": "FACE_MODE", "host": "FACE_HOST",
        }.items() if env in os.environ}
        return cls(**fields)

    def operating_point(self):
        return OperatingPoint.model_validate_json(self.config_path.read_text())


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
