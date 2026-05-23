import sys
from pathlib import Path

import yaml

from .models import TermConfig, PresetsConfig


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"[ERROR] 配置文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_term_config(config_dir: Path, config_file: str = "term.yaml") -> TermConfig:
    path = config_dir / config_file
    data = _load_yaml(path)
    return TermConfig(**data)


def load_presets_config(config_dir: Path, config_file: str = "presets.yaml") -> PresetsConfig:
    path = config_dir / config_file
    data = _load_yaml(path)
    return PresetsConfig(**data)


def build_evaluation_url(term: TermConfig, semester: str | None = None) -> str:
    sem = semester or term.semester
    return f"{term.app_base_url}{term.evaluation_route}?semester={sem}"
