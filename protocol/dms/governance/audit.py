"""Tamper-evident append-only event ledger.

Each entry hashes its own content plus the previous entry hash, so any edit or
deletion inside the chain is detectable by ``verify``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from ..domain.clock import SYSTEM_CLOCK, Clock
from ..domain.enums import Role
from ..domain.models import EventLogEntry
from ..protocol.bundle import canonical_json, sha256_hex

GENESIS = "0" * 64


class EventLog:
    """In-memory ledger. The store layer persists entries in the same order."""

    def __init__(self, clock: Clock = SYSTEM_CLOCK) -> None:
        self._entries: list[EventLogEntry] = []
        self._clock = clock

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> tuple[EventLogEntry, ...]:
        return tuple(self._entries)

    @property
    def head(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS

    def append(
        self,
        action: str,
        *,
        incident_id: str | None = None,
        actor_node_id: str | None = None,
        actor_role: Role | None = None,
        detail: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> EventLogEntry:
        when = now or self._clock.now()
        entry = EventLogEntry(
            incident_id=incident_id,
            actor_node_id=actor_node_id,
            actor_role=actor_role,
            action=action,
            detail=detail or {},
            prev_hash=self.head,
            created_at=when,
        )
        entry.entry_hash = self._hash(entry)
        self._entries.append(entry)
        return entry

    @staticmethod
    def _hash(entry: EventLogEntry) -> str:
        payload = {
            "id": entry.id,
            "incident_id": entry.incident_id,
            "actor_node_id": entry.actor_node_id,
            "actor_role": entry.actor_role.value if entry.actor_role else None,
            "action": entry.action,
            "detail": entry.detail,
            "prev_hash": entry.prev_hash,
            "created_at": entry.created_at.isoformat(),
        }
        return sha256_hex(canonical_json(payload))

    def verify(self, entries: Iterable[EventLogEntry] | None = None) -> bool:
        """True when the chain is intact from genesis to head."""
        prev = GENESIS
        for entry in entries if entries is not None else self._entries:
            if entry.prev_hash != prev:
                return False
            if entry.entry_hash != self._hash(entry):
                return False
            prev = entry.entry_hash
        return True

    def for_incident(self, incident_id: str) -> tuple[EventLogEntry, ...]:
        return tuple(e for e in self._entries if e.incident_id == incident_id)
