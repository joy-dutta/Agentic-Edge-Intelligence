from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ExperimentConfig:
    root: Path
    raw: dict[str, Any]

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw[name]
        if not isinstance(value, dict):
            raise TypeError(f"Configuration section {name!r} is not a mapping")
        return value

    def resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


def load_config(path: str | Path = "configs/experiment.yaml") -> ExperimentConfig:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise TypeError("Experiment configuration must be a mapping")
    return ExperimentConfig(root=config_path.parent.parent, raw=raw)

