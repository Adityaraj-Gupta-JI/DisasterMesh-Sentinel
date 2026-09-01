"""Resumable, hash-verified file transfer.

Bytes land in a quarantine directory and are only promoted into permanent storage
after the whole-file digest matches. Promotion is an atomic rename, so a partially
written file can never be mistaken for evidence. Nothing received is ever executed.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..domain.enums import TransferState
from ..domain.errors import TransferError
from .manifest import FileManifest

#: Legal transitions of the transfer state machine.
TRANSFER_TRANSITIONS: dict[TransferState, frozenset[TransferState]] = {
    TransferState.OFFERED: frozenset(
        {TransferState.ACCEPTED, TransferState.FAILED, TransferState.EXPIRED}
    ),
    TransferState.ACCEPTED: frozenset(
        {TransferState.TRANSFERRING, TransferState.FAILED, TransferState.EXPIRED}
    ),
    TransferState.TRANSFERRING: frozenset(
        {
            TransferState.PAUSED,
            TransferState.INTERRUPTED,
            TransferState.VERIFYING,
            TransferState.FAILED,
            TransferState.EXPIRED,
        }
    ),
    TransferState.PAUSED: frozenset(
        {TransferState.TRANSFERRING, TransferState.FAILED, TransferState.EXPIRED}
    ),
    TransferState.INTERRUPTED: frozenset(
        {TransferState.TRANSFERRING, TransferState.FAILED, TransferState.EXPIRED}
    ),
    TransferState.VERIFYING: frozenset({TransferState.COMMITTED, TransferState.FAILED}),
    TransferState.COMMITTED: frozenset(),
    TransferState.FAILED: frozenset({TransferState.TRANSFERRING}),
    TransferState.EXPIRED: frozenset(),
}


@dataclass
class TransferSession:
    """Receiver-side state for one incoming file."""

    manifest: FileManifest
    quarantine_dir: Path
    committed_dir: Path
    state: TransferState = TransferState.OFFERED
    received_chunks: dict[int, bytes] = field(default_factory=dict)
    bytes_received: int = 0
    failure_reason: str | None = None
    committed_path: Path | None = None

    # ------------------------------------------------------------ state machine

    def _transition(self, target: TransferState) -> None:
        if target not in TRANSFER_TRANSITIONS.get(self.state, frozenset()):
            raise TransferError(f"illegal transfer transition {self.state.value} -> {target.value}")
        self.state = target

    def accept(self, *, now: datetime) -> None:
        """Validate policy and expiry before agreeing to receive anything."""
        if self.manifest.is_expired(now):
            self._transition(TransferState.EXPIRED)
            raise TransferError("attachment expired before transfer started")
        self.manifest.validate_policy()
        self._transition(TransferState.ACCEPTED)

    def begin(self) -> None:
        if self.state is TransferState.ACCEPTED:
            self._transition(TransferState.TRANSFERRING)
        elif self.state in (TransferState.INTERRUPTED, TransferState.PAUSED, TransferState.FAILED):
            self._transition(TransferState.TRANSFERRING)

    def pause(self) -> None:
        self._transition(TransferState.PAUSED)

    def interrupt(self, reason: str = "link_lost") -> None:
        """Keep every verified chunk so the transfer can resume where it stopped."""
        self.failure_reason = reason
        self._transition(TransferState.INTERRUPTED)

    # ----------------------------------------------------------------- chunks

    @property
    def missing(self) -> list[int]:
        return self.manifest.missing_chunks(set(self.received_chunks))

    @property
    def progress(self) -> float:
        if not self.manifest.size_bytes:
            return 0.0
        return min(1.0, self.bytes_received / self.manifest.size_bytes)

    def receive_chunk(self, index: int, data: bytes, *, expected_sha256: str | None = None) -> None:
        """Store one chunk. A per-chunk digest mismatch rejects only that chunk."""
        if self.state is not TransferState.TRANSFERRING:
            raise TransferError(f"cannot receive a chunk while {self.state.value}")
        start, end = self.manifest.chunk_range(index)
        if len(data) != end - start:
            raise TransferError(f"chunk {index} size {len(data)} != expected {end - start}")
        if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise TransferError(f"chunk {index} digest mismatch — discarded")
        if index not in self.received_chunks:
            self.bytes_received += len(data)
        self.received_chunks[index] = data

    # ------------------------------------------------------------- completion

    def assembled(self) -> bytes:
        if self.missing:
            raise TransferError(f"cannot assemble: {len(self.missing)} chunk(s) missing")
        return b"".join(self.received_chunks[i] for i in range(self.manifest.chunk_count))

    def verify_and_commit(self) -> Path:
        """Verify the whole-file digest in quarantine, then atomically promote it."""
        self._transition(TransferState.VERIFYING)
        try:
            data = self.assembled()
        except TransferError:
            self.state = TransferState.FAILED
            self.failure_reason = "incomplete"
            raise

        digest = hashlib.sha256(data).hexdigest()
        if digest != self.manifest.sha256:
            self.state = TransferState.FAILED
            self.failure_reason = "hash_mismatch"
            raise TransferError(
                f"file digest mismatch: expected {self.manifest.sha256[:12]}…, "
                f"got {digest[:12]}… — refusing to commit"
            )

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.committed_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.quarantine_dir / f"{self.manifest.file_id}.part"
        tmp.write_bytes(data)
        os.chmod(tmp, 0o600)  # never executable

        final = self.committed_dir / f"{self.manifest.file_id}_{self.manifest.file_name}"
        os.replace(tmp, final)  # atomic within a filesystem
        os.chmod(final, 0o600)

        self.committed_path = final
        self.manifest.state = TransferState.COMMITTED
        self._transition(TransferState.COMMITTED)
        return final


def chunk_bytes(data: bytes, manifest: FileManifest) -> list[tuple[int, bytes]]:
    """Split a payload into (index, chunk) pairs matching a manifest."""
    return [(i, data[slice(*manifest.chunk_range(i))]) for i in range(manifest.chunk_count)]
