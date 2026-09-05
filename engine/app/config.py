from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "CVENGINE"
API_HOST = os.environ.get("CVENGINE_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("CVENGINE_PORT", "8765"))
OLLAMA_DEFAULT = os.environ.get("CVENGINE_OLLAMA_URL", "http://127.0.0.1:11434")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skills_path() -> Path:
    override = os.environ.get("CVENGINE_SKILLS")
    if override:
        return Path(override)
    return repo_root() / "skills" / "ontology.json"


def data_dir() -> Path:
    override = os.environ.get("CVENGINE_DATA_DIR")
    if override:
        path = Path(override)
    else:
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    (path / "exports").mkdir(exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "cvengine.db"


def exports_dir() -> Path:
    path = data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path
