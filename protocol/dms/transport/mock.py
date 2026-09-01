"""In-memory mock transport.

A deterministic stand-in for Nearby Connections: no radios, no threads, no clock.
Tests drive it with ``pump()``. It can drop links, throttle file chunks, and
interrupt transfers mid-flight so resume logic is exercised without hardware.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import (
    MAX_FILE_BYTES,
    ConnectionState,
    PayloadKind,
    PeerInfo,
    Transport,
    TransportError,
    TransportEvent,
    TransportEventType,
)


@dataclass
class _Delivery:
    payload_id: str
    sender: str
    receiver: str
    kind: PayloadKind
    data: bytes
    file_name: str | None = None
    offset: int = 0
    cancelled: bool = False

    @property
    def complete(self) -> bool:
        return self.offset >= len(self.data)


@dataclass
class MockRadio:
    """The shared medium. Owns which nodes can see and reach each other."""

    chunk_bytes: int = 64 * 1024
    nodes: dict[str, MockTransport] = field(default_factory=dict)
    links: set[tuple[str, str]] = field(default_factory=set)
    queue: list[_Delivery] = field(default_factory=list)
    delivered: list[_Delivery] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    # ------------------------------------------------------------ topology

    def register(self, transport: MockTransport) -> None:
        self.nodes[transport.node_id] = transport

    def link(self, a: str, b: str) -> None:
        """Put two nodes in range of each other."""
        self.links.add((a, b))
        self.links.add((b, a))
        for src, dst in ((a, b), (b, a)):
            node = self.nodes.get(src)
            peer = self.nodes.get(dst)
            if node and peer and node._discovering:
                node._discover(peer)

    def unlink(self, a: str, b: str) -> None:
        """Move two nodes out of range; in-flight transfers are interrupted."""
        self.links.discard((a, b))
        self.links.discard((b, a))
        for node_id, other in ((a, b), (b, a)):
            node = self.nodes.get(node_id)
            if node:
                node._peer_lost(other)
        for delivery in list(self.queue):
            if {delivery.sender, delivery.receiver} == {a, b}:
                delivery.cancelled = True
                sender = self.nodes.get(delivery.sender)
                if sender:
                    sender._emit(
                        TransportEvent(
                            type=TransportEventType.PAYLOAD_FAILED,
                            payload_id=delivery.payload_id,
                            bytes_transferred=delivery.offset,
                            total_bytes=len(delivery.data),
                            error="link_lost",
                        )
                    )
                self.queue.remove(delivery)

    def in_range(self, a: str, b: str) -> bool:
        return (a, b) in self.links

    def next_id(self) -> str:
        return f"pl_{next(self._ids)}"

    # ------------------------------------------------------------ delivery

    def enqueue(self, delivery: _Delivery) -> None:
        self.queue.append(delivery)

    def pump(self, max_steps: int | None = None) -> int:
        """Advance queued transfers. Returns the number of chunks moved.

        Bytes payloads land whole (control messages are small); file payloads move a
        chunk at a time so progress and interruption are observable.
        """
        moved = 0
        steps = 0
        while self.queue and (max_steps is None or steps < max_steps):
            steps += 1
            delivery = self.queue[0]
            if delivery.cancelled:
                self.queue.pop(0)
                continue
            if not self.in_range(delivery.sender, delivery.receiver):
                delivery.cancelled = True
                self.queue.pop(0)
                continue
            receiver = self.nodes.get(delivery.receiver)
            sender = self.nodes.get(delivery.sender)
            if receiver is None or sender is None:
                self.queue.pop(0)
                continue

            if delivery.kind is PayloadKind.BYTES:
                delivery.offset = len(delivery.data)
            else:
                delivery.offset = min(len(delivery.data), delivery.offset + self.chunk_bytes)
                sender._emit(
                    TransportEvent(
                        type=TransportEventType.PAYLOAD_PROGRESS,
                        payload_id=delivery.payload_id,
                        kind=delivery.kind,
                        bytes_transferred=delivery.offset,
                        total_bytes=len(delivery.data),
                    )
                )
            moved += 1

            if delivery.complete:
                self.queue.pop(0)
                self.delivered.append(delivery)
                peer = PeerInfo(
                    endpoint_id=delivery.sender,
                    node_id=delivery.sender,
                    metadata=sender.advertised_metadata,
                )
                receiver._emit(
                    TransportEvent(
                        type=TransportEventType.PAYLOAD_RECEIVED,
                        peer=peer,
                        payload_id=delivery.payload_id,
                        kind=delivery.kind,
                        data=delivery.data,
                        file_path=delivery.file_name,
                        bytes_transferred=len(delivery.data),
                        total_bytes=len(delivery.data),
                    )
                )
        return moved

    def drain(self, limit: int = 10_000) -> int:
        """Pump until the medium is idle. Guards against a runaway loop."""
        total = 0
        for _ in range(limit):
            moved = self.pump(max_steps=1)
            if moved == 0 and not self.queue:
                break
            total += moved
        return total


class MockTransport(Transport):
    """Transport implementation backed by :class:`MockRadio`."""

    def __init__(self, node_id: str, radio: MockRadio) -> None:
        super().__init__(node_id)
        self.radio = radio
        self.advertised_metadata: dict[str, Any] = {}
        self._advertising = False
        self._discovering = False
        self._states: dict[str, ConnectionState] = {}
        self._auto_accept = True
        radio.register(self)

    # ------------------------------------------------------------ advertising

    def start_advertising(self, metadata: dict[str, Any] | None = None) -> None:
        self._advertising = True
        self.advertised_metadata = dict(metadata or {})
        for peer_id in [n for n in self.radio.nodes if n != self.node_id]:
            if self.radio.in_range(self.node_id, peer_id):
                peer = self.radio.nodes[peer_id]
                if peer._discovering:
                    peer._discover(self)

    def stop_advertising(self) -> None:
        self._advertising = False

    def start_discovery(self) -> None:
        self._discovering = True
        for peer_id, peer in self.radio.nodes.items():
            if peer_id != self.node_id and self.radio.in_range(self.node_id, peer_id):
                if peer._advertising:
                    self._discover(peer)

    def stop_discovery(self) -> None:
        self._discovering = False

    def _discover(self, peer: MockTransport) -> None:
        if not peer._advertising or not self._discovering:
            return
        self._states.setdefault(peer.node_id, ConnectionState.DISCOVERED)
        self._emit(
            TransportEvent(
                type=TransportEventType.PEER_DISCOVERED,
                peer=PeerInfo(
                    endpoint_id=peer.node_id,
                    node_id=peer.node_id,
                    display_name=peer.node_id,
                    metadata=peer.advertised_metadata,
                ),
            )
        )

    def _peer_lost(self, peer_id: str) -> None:
        if peer_id in self._states:
            self._states[peer_id] = ConnectionState.DISCONNECTED
            self._emit(
                TransportEvent(
                    type=TransportEventType.PEER_LOST,
                    peer=PeerInfo(endpoint_id=peer_id, node_id=peer_id),
                )
            )

    # ------------------------------------------------------------ connections

    def set_auto_accept(self, value: bool) -> None:
        """Mirror of the Nearby connection-acceptance policy callback."""
        self._auto_accept = value

    def request_connection(self, endpoint_id: str, timeout_s: float = 30.0) -> None:
        if not self.radio.in_range(self.node_id, endpoint_id):
            self._emit(TransportEvent(type=TransportEventType.ERROR, error="peer_out_of_range"))
            return
        peer = self.radio.nodes.get(endpoint_id)
        if peer is None:
            self._emit(TransportEvent(type=TransportEventType.ERROR, error="unknown_peer"))
            return
        self._states[endpoint_id] = ConnectionState.REQUESTED
        peer._emit(
            TransportEvent(
                type=TransportEventType.CONNECTION_REQUESTED,
                peer=PeerInfo(
                    endpoint_id=self.node_id,
                    node_id=self.node_id,
                    metadata=self.advertised_metadata,
                ),
            )
        )
        if peer._auto_accept:
            peer.accept_connection(self.node_id)

    def accept_connection(self, endpoint_id: str) -> None:
        peer = self.radio.nodes.get(endpoint_id)
        if peer is None:
            raise TransportError(f"unknown peer {endpoint_id}")
        self._states[endpoint_id] = ConnectionState.CONNECTED
        peer._states[self.node_id] = ConnectionState.CONNECTED
        for node, other in ((self, peer), (peer, self)):
            node._emit(
                TransportEvent(
                    type=TransportEventType.CONNECTED,
                    peer=PeerInfo(
                        endpoint_id=other.node_id,
                        node_id=other.node_id,
                        metadata=other.advertised_metadata,
                    ),
                )
            )

    def reject_connection(self, endpoint_id: str, reason: str = "policy") -> None:
        self._states[endpoint_id] = ConnectionState.REJECTED
        peer = self.radio.nodes.get(endpoint_id)
        if peer:
            peer._states[self.node_id] = ConnectionState.REJECTED
            peer._emit(
                TransportEvent(
                    type=TransportEventType.DISCONNECTED,
                    peer=PeerInfo(endpoint_id=self.node_id, node_id=self.node_id),
                    error=reason,
                )
            )

    def disconnect(self, endpoint_id: str) -> None:
        self._states[endpoint_id] = ConnectionState.DISCONNECTED
        peer = self.radio.nodes.get(endpoint_id)
        if peer:
            peer._states[self.node_id] = ConnectionState.DISCONNECTED
            peer._emit(
                TransportEvent(
                    type=TransportEventType.DISCONNECTED,
                    peer=PeerInfo(endpoint_id=self.node_id, node_id=self.node_id),
                )
            )

    def connection_state(self, endpoint_id: str) -> ConnectionState:
        return self._states.get(endpoint_id, ConnectionState.DISCONNECTED)

    # --------------------------------------------------------------- payloads

    def _require_connected(self, endpoint_id: str) -> None:
        if self.connection_state(endpoint_id) is not ConnectionState.CONNECTED:
            raise TransportError(f"not connected to {endpoint_id}")

    def send_bytes(self, endpoint_id: str, data: bytes) -> str:
        self._require_connected(endpoint_id)
        payload_id = self.radio.next_id()
        self.radio.enqueue(
            _Delivery(
                payload_id=payload_id,
                sender=self.node_id,
                receiver=endpoint_id,
                kind=PayloadKind.BYTES,
                data=data,
            )
        )
        return payload_id

    def send_file(self, endpoint_id: str, path: str, timeout_s: float = 120.0) -> str:
        self._require_connected(endpoint_id)
        data = Path(path).read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise TransportError(f"file {len(data)}B exceeds transport limit {MAX_FILE_BYTES}B")
        payload_id = self.radio.next_id()
        self.radio.enqueue(
            _Delivery(
                payload_id=payload_id,
                sender=self.node_id,
                receiver=endpoint_id,
                kind=PayloadKind.FILE,
                data=data,
                file_name=Path(path).name,
            )
        )
        return payload_id

    def send_stream(self, endpoint_id: str, chunks: Iterable[bytes]) -> str:
        self._require_connected(endpoint_id)
        payload_id = self.radio.next_id()
        self.radio.enqueue(
            _Delivery(
                payload_id=payload_id,
                sender=self.node_id,
                receiver=endpoint_id,
                kind=PayloadKind.STREAM,
                data=b"".join(chunks),
            )
        )
        return payload_id

    def cancel_payload(self, payload_id: str) -> None:
        for delivery in self.radio.queue:
            if delivery.payload_id == payload_id:
                delivery.cancelled = True
                self._emit(
                    TransportEvent(
                        type=TransportEventType.PAYLOAD_FAILED,
                        payload_id=payload_id,
                        bytes_transferred=delivery.offset,
                        total_bytes=len(delivery.data),
                        error="cancelled",
                    )
                )
                return
