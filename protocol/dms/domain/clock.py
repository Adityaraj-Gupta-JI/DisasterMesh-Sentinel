"""Time source.

Every module takes a Clock instead of calling the wall clock directly, so TTL and
expiry behavior is deterministic under test (CLAUDE.md: tests use fake time).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class Clock:
    """Real UTC clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """Manually advanced clock for deterministic tests and simulation."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float = 0, **kwargs: float) -> datetime:
        self._now = self._now + timedelta(seconds=seconds, **kwargs)
        return self._now

    def set(self, when: datetime) -> None:
        self._now = when


SYSTEM_CLOCK = Clock()


def utc(dt: datetime) -> datetime:
    """Normalize any datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
