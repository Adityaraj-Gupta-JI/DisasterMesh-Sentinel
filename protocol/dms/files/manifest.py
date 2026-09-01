"""Attachment manifests and chunk accounting.

The manifest always travels before the content, so a receiver knows the size, type,
and digest it is committing to before a single byte of payload arrives.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..domain.clock import utc
from ..domain.enums import AttachmentKind, PriorityClass, TransferState
from ..domain.errors import TransferError
from ..domain.models import new_id

DEFAULT_CHUNK_BYTES = 64 * 1024
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024

ALLOWED_MIME: dict[AttachmentKind, frozenset[str]] = {
    AttachmentKind.IMAGE: frozenset({"image/jpeg", "image/png", "image/webp"}),
    AttachmentKind.AUDIO: frozenset(
        {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/ogg"}
    ),
    AttachmentKind.DOCUMENT: frozenset({"application/pdf", "text/plain"}),
}

#: Never executable, never a script, never an archive that could hide one.
FORBIDDEN_MIME = frozenset(
    {
        "application/x-executable",
        "application/x-msdownload",
        "application/x-sh",
        "application/vnd.microsoft.portable-executable",
        "text/x-shellscript",
        "application/zip",
        "application/x-tar",
    }
)


@dataclass
class FileManifest:
    """Everything a receiver needs to accept, verify, and resume one file."""

    file_id: str = field(default_factory=lambda: new_id("file"))
    bundle_id: str = ""
    incident_id: str = ""
    attachment_id: str = ""
    file_name: str = "evidence.bin"
    mime_type: str = "application/octet-stream"
    kind: AttachmentKind = AttachmentKind.IMAGE
    size_bytes: int = 0
    sha256: str = ""
    chunk_bytes: int = DEFAULT_CHUNK_BYTES
    chunk_count: int = 0
    chunk_bundle_ids: tuple[str, ...] = ()
    available_ranges: tuple[tuple[int, int], ...] = ()
    priority_class: PriorityClass = PriorityClass.P2
    expires_at: datetime | None = None
    encryption: dict[str, Any] = field(default_factory=dict)
    state: TransferState = TransferState.OFFERED

    def __post_init__(self) -> None:
        if self.chunk_count == 0 and self.size_bytes:
            self.chunk_count = math.ceil(self.size_bytes / self.chunk_bytes)

    # ------------------------------------------------------------- validation

    def validate_policy(self) -> None:
        """Reject anything outside size and MIME policy before transfer begins."""
        if self.size_bytes <= 0:
            raise TransferError("attachment is empty")
        if self.size_bytes > MAX_ATTACHMENT_BYTES:
            raise TransferError(
                f"attachment {self.size_bytes}B exceeds policy limit {MAX_ATTACHMENT_BYTES}B"
            )
        if self.mime_type in FORBIDDEN_MIME:
            raise TransferError(f"forbidden MIME type {self.mime_type}")
        allowed = ALLOWED_MIME.get(self.kind, frozenset())
        if self.mime_type not in allowed:
            raise TransferError(f"MIME {self.mime_type} not permitted for {self.kind.value}")
        if len(self.sha256) != 64:
            raise TransferError("manifest requires a SHA-256 digest")
        if self.chunk_bundle_ids and len(self.chunk_bundle_ids) != self.chunk_count:
            raise TransferError("chunk bundle id count must match chunk count")

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and utc(self.expires_at) <= utc(now)

    # ------------------------------------------------------------------ chunks

    def chunk_range(self, index: int) -> tuple[int, int]:
        if not 0 <= index < self.chunk_count:
            raise TransferError(f"chunk index {index} out of range")
        start = index * self.chunk_bytes
        return start, min(start + self.chunk_bytes, self.size_bytes)

    def missing_chunks(self, have: set[int]) -> list[int]:
        return [i for i in range(self.chunk_count) if i not in have]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "bundle_id": self.bundle_id,
            "incident_id": self.incident_id,
            "attachment_id": self.attachment_id,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "kind": self.kind.value,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "chunk_bytes": self.chunk_bytes,
            "chunk_count": self.chunk_count,
            "chunk_bundle_ids": list(self.chunk_bundle_ids),
            "available_ranges": [list(r) for r in self.available_ranges],
            "priority_class": self.priority_class.value,
            "expires_at": utc(self.expires_at).isoformat() if self.expires_at else None,
            "encryption": self.encryption,
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileManifest:
        return cls(
            file_id=d["file_id"],
            bundle_id=d.get("bundle_id", ""),
            incident_id=d.get("incident_id", ""),
            attachment_id=d.get("attachment_id", ""),
            file_name=d.get("file_name", "evidence.bin"),
            mime_type=d.get("mime_type", "application/octet-stream"),
            kind=AttachmentKind(d.get("kind", "IMAGE")),
            size_bytes=int(d.get("size_bytes", 0)),
            sha256=d.get("sha256", ""),
            chunk_bytes=int(d.get("chunk_bytes", DEFAULT_CHUNK_BYTES)),
            chunk_count=int(d.get("chunk_count", 0)),
            chunk_bundle_ids=tuple(d.get("chunk_bundle_ids", [])),
            available_ranges=tuple(tuple(r) for r in d.get("available_ranges", [])),
            priority_class=PriorityClass(d.get("priority_class", "P2")),
            expires_at=(datetime.fromisoformat(d["expires_at"]) if d.get("expires_at") else None),
            encryption=d.get("encryption", {}) or {},
            state=TransferState(d.get("state", "OFFERED")),
        )

    @classmethod
    def for_bytes(
        cls, data: bytes, *, file_name: str, mime_type: str, kind: AttachmentKind, **kwargs: Any
    ) -> FileManifest:
        return cls(
            file_name=file_name,
            mime_type=mime_type,
            kind=kind,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            **kwargs,
        )
