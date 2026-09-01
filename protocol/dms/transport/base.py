"""Transport abstraction.

Nothing above this layer knows what a radio is. Nearby Connections, a socket, or the
in-memory mock all present the same normalized events, so the sync engine is tested
without hardware and the Android adapter is swapped in without touching sync logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

DEFAULT_CONNECT_TIMEOUT_S = 30.0
DEFAULT_TRANSFER_TIMEOUT_S = 120.0
MAX_FILE_BYTES = 32 * 1024 * 1024


class ConnectionState(str, Enum):
    DISCOVERED = "DISCOVERED"
    REQUESTED = "REQUESTED"
    CONNECTED = "CONNECTED"
    REJECTED = "REJECTED"
    DISCONNECTED = "DISCONNECTED"
    FAILED = "FAILED"


class PayloadKind(str, Enum):
    BYTES = "BYTES"
    FILE = "FILE"
    STREAM = "STREAM"


class TransportEventType(str, Enum):
    PEER_DISCOVERED = "PEER_DISCOVERED"
    PEER_LOST = "PEER_LOST"
    CONNECTION_REQUESTED = "CONNECTION_REQUESTED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    PAYLOAD_RECEIVED = "PAYLOAD_RECEIVED"
    PAYLOAD_PROGRESS = "PAYLOAD_PROGRESS"
    PAYLOAD_FAILED = "PAYLOAD_FAILED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class PeerInfo:
    """A discovered device. ``metadata`` carries advertised role, never content."""

    endpoint_id: str
    node_id: str
    display_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportEvent:
    type: TransportEventType
    peer: PeerInfo | None = None
    payload_id: str | None = None
    kind: PayloadKind | None = None
    data: bytes | None = None
    file_path: str | None = None
    bytes_transferred: int = 0
    total_bytes: int = 0
    error: str | None = None


Listener = Callable[[TransportEvent], None]


class TransportError(Exception):
    """A transport operation failed. Never allowed to crash the app."""


class Transport(ABC):
    """Normalized device-to-device transport."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self._listeners: list[Listener] = []

    # -------------------------------------------------------------- observation

    def observe(self, listener: Listener) -> Callable[[], None]:
        """Register a listener; returns an unsubscribe callable."""
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsubscribe

    def _emit(self, event: TransportEvent) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception as exc:  # a bad listener must not kill the radio
                self._on_listener_error(exc, event)

    def _on_listener_error(self, exc: Exception, event: TransportEvent) -> None:
        self._listeners_errors.append((exc, event)) if hasattr(self, "_listeners_errors") else None

    # ------------------------------------------------------------- advertising

    @abstractmethod
    def start_advertising(self, metadata: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    def stop_advertising(self) -> None: ...

    @abstractmethod
    def start_discovery(self) -> None: ...

    @abstractmethod
    def stop_discovery(self) -> None: ...

    # -------------------------------------------------------------- connections

    @abstractmethod
    def request_connection(
        self, endpoint_id: str, timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S
    ) -> None: ...

    @abstractmethod
    def accept_connection(self, endpoint_id: str) -> None: ...

    @abstractmethod
    def reject_connection(self, endpoint_id: str, reason: str = "policy") -> None: ...

    @abstractmethod
    def disconnect(self, endpoint_id: str) -> None: ...

    @abstractmethod
    def connection_state(self, endpoint_id: str) -> ConnectionState: ...

    # ----------------------------------------------------------------- payloads

    @abstractmethod
    def send_bytes(self, endpoint_id: str, data: bytes) -> str: ...

    @abstractmethod
    def send_file(
        self, endpoint_id: str, path: str, timeout_s: float = DEFAULT_TRANSFER_TIMEOUT_S
    ) -> str: ...

    @abstractmethod
    def send_stream(self, endpoint_id: str, chunks: Any) -> str: ...

    @abstractmethod
    def cancel_payload(self, payload_id: str) -> None: ...

    def close(self) -> None:
        """Release radios and listeners. Safe to call twice."""
        self._listeners.clear()
