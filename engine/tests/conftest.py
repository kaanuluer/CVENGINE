from __future__ import annotations

import pytest

from app.database import reset_engine


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CVENGINE_DATA_DIR", str(tmp_path / "cvengine-data"))
    reset_engine()
    yield
    reset_engine()
