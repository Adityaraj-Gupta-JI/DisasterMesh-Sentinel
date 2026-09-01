"""Backend fixtures: an isolated in-memory database per test."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "protocol"))
sys.path.insert(0, str(ROOT / "backend"))

from app import db as db_module  # noqa: E402


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_module.reset_engine(f"sqlite:///{tmp_path / 'test.db'}")
    from app.main import app

    db_module.init_db()
    return TestClient(app)
