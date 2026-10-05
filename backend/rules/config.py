"""Load and validate rules/config.yaml."""

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt, model_validator

CONFIG_PATH = Path(__file__).parent / "config.yaml"


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sbp_drop_threshold: PositiveInt
    recurrence_min: PositiveInt
    recurrence_window: PositiveInt
    note_deadline_hours: PositiveInt
    gain_threshold_kg: PositiveFloat
    access_recurrence_min: PositiveInt
    access_recurrence_window: PositiveInt
    review_sla_hours: PositiveInt
    # sha256 of the config file; set by load_config, stored on every Flag.
    version: str = "unversioned"

    @model_validator(mode="after")
    def _min_fits_window(self) -> "RulesConfig":
        if self.recurrence_min > self.recurrence_window or self.access_recurrence_min > self.access_recurrence_window:
            raise ValueError("a recurrence minimum cannot exceed its window")
        return self


def load_config(path: Path = CONFIG_PATH) -> RulesConfig:
    raw = path.read_bytes()
    return RulesConfig(**yaml.safe_load(raw), version=hashlib.sha256(raw).hexdigest()[:16])
