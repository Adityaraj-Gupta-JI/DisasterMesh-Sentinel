"""Shared fixtures. Every test uses fake time, fake transport, and fake AI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from dms.domain.clock import FixedClock  # noqa: E402
from dms.sim.harness import build_demo_mesh  # noqa: E402


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def now(clock: FixedClock):
    return clock.now()


@pytest.fixture
def mesh(tmp_path: Path):
    """Reporter A, relay B (no key), coordinator C, all mutually trusted."""
    return build_demo_mesh(tmp_path)
