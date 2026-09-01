"""Emergency Sync Engine — the wire conversation between two nodes.

Exchange, in order:

    A --INVENTORY_REQUEST(digest_A)--> B
    A <--INVENTORY_RESPONSE(digest_B) + BUNDLE_OFFER(metadata)-- B
    A --BUNDLE_ACCEPT(ids A lacks)--> B
    A <--BUNDLE_DATA(frames, hop+1)-- B
    A --BUNDLE_RECEIPT(stored/rejected)--> B
    A --BUNDLE_OFFER(what B lacks)--> B          (the reverse direction)

Offers carry metadata only. What gets offered is decided by the scheduler, so
authorization and the text-before-media rule are enforced in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..domain.errors import ProtocolError
from ..domain.models import NodeIdentity
from ..protocol.bundle import Bundle
from ..protocol.inventory import (
    BundleOffer,
    ControlMessage,
    ExactDigest,
    MessageType,
)
from ..transport.base import TransportEvent, TransportEventType
from .scheduler import SchedulerResult, SyncScheduler

if TYPE_CHECKING:  # pragma: no cover
    from ..node import MeshNode

BUNDLE_FRAME_PREFIX = b"BNDL"


@dataclass
class SyncStats:
    """Observable counters for the relay UI and the simulator."""

    offers_sent: int = 0
    offers_received: int = 0
    bundles_sent: int = 0
    bundles_received: int = 0
    bundles_deduplicated: int = 0
    bundles_rejected: int = 0
    receipts: int = 0
    reject_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "offers_sent": self.offers_sent,
            "offers_received": self.offers_received,
            "bundles_sent": self.bundles_sent,
            "bundles_received": self.bundles_received,
            "bundles_deduplicated": self.bundles_deduplicated,
            "bundles_rejected": self.bundles_rejected,
            "receipts": self.receipts,
            "reject_reasons": list(self.reject_reasons),
        }


class SyncEngine:
    """Drives the exchange for one node."""

    def __init__(self, node: MeshNode, scheduler: SyncScheduler | None = None) -> None:
        self.node = node
        self.scheduler = scheduler or SyncScheduler()
        self.stats = SyncStats()
        self.last_selection: SchedulerResult | None = None
        self._peer_roles: dict[str, NodeIdentity] = {}

    # ------------------------------------------------------------- initiation

    def request_inventory(self, peer_id: str) -> None:
        """Open an exchange by telling the peer what we already hold."""
        msg = ControlMessage(
            type=MessageType.INVENTORY_REQUEST,
            node_id=self.node.identity.id,
            role=self.node.identity.role,
            body={
                "digest": ExactDigest(frozenset(self.node.store.bundle_ids())).to_dict(),
                "organization_id": self.node.identity.organization_id,
            },
        )
        self.node.transport.send_bytes(peer_id, msg.encode())

    # ---------------------------------------------------------- event handling

    def on_transport_event(self, event: TransportEvent) -> None:
        """Normalized transport events in; protocol replies out. Never raises."""
        try:
            if event.type is TransportEventType.PAYLOAD_RECEIVED and event.data:
                if ControlMessage.is_control(event.data):
                    self._handle_control(ControlMessage.decode(event.data))
                elif event.data.startswith(BUNDLE_FRAME_PREFIX):
                    self._handle_bundle_frame(
                        event.data[len(BUNDLE_FRAME_PREFIX) :],
                        sender=event.peer.node_id if event.peer else "unknown",
                    )
                else:
                    self.stats.bundles_rejected += 1
                    self.stats.reject_reasons.append("unknown_payload_type")
        except ProtocolError as exc:
            self.stats.bundles_rejected += 1
            self.stats.reject_reasons.append(str(exc))
        except Exception as exc:  # transport failures must not crash the node
            self.stats.reject_reasons.append(f"unhandled:{exc}")

    def _peer_identity(self, msg: ControlMessage) -> NodeIdentity:
        identity = self._peer_roles.get(msg.node_id)
        if identity is None:
            identity = NodeIdentity(
                id=msg.node_id,
                role=msg.role,
                organization_id=msg.body.get("organization_id"),
            )
            self._peer_roles[msg.node_id] = identity
        return identity

    def _handle_control(self, msg: ControlMessage) -> None:
        peer = self._peer_identity(msg)
        if msg.type == MessageType.INVENTORY_REQUEST:
            self._on_inventory_request(msg, peer)
        elif msg.type == MessageType.INVENTORY_RESPONSE:
            self._on_inventory_response(msg, peer)
        elif msg.type == MessageType.BUNDLE_OFFER:
            self._on_offer(msg, peer)
        elif msg.type == MessageType.BUNDLE_ACCEPT:
            self._on_accept(msg, peer)
        elif msg.type == MessageType.BUNDLE_RECEIPT:
            self.stats.receipts += 1
            for bundle_id in msg.body.get("stored", []):
                self.node.store.mark_delivered(bundle_id, msg.node_id)
        elif msg.type == MessageType.BUNDLE_REJECT:
            self.stats.reject_reasons.append(msg.body.get("reason", "peer_rejected"))

    # -------------------------------------------------------------- responder

    def _select_for(self, peer: NodeIdentity, exclude: set[str]) -> SchedulerResult:
        now = self.node.clock.now()
        objects = [
            o for o in self.node.store.pending_sync_objects(now) if o.bundle_id not in exclude
        ]
        result = self.scheduler.select(
            objects, receiver=peer, now=now, context=self.node.sync_context()
        )
        self.last_selection = result
        return result

    def _offers_from(self, result: SchedulerResult) -> list[dict]:
        offers = []
        for obj in result.selected:
            offers.append(
                BundleOffer(
                    bundle_id=obj.bundle_id,
                    incident_id=obj.incident_id,
                    payload_type=obj.payload_type,
                    priority_class=obj.priority_class,
                    priority_score=obj.priority_score,
                    size_bytes=obj.size_bytes,
                    sensitivity=obj.sensitivity,
                    expires_at=obj.expires_at.isoformat() if obj.expires_at else "",
                    requires_ack=obj.requires_ack,
                ).to_dict()
            )
        return offers

    def _on_inventory_request(self, msg: ControlMessage, peer: NodeIdentity) -> None:
        theirs = ExactDigest.from_dict(msg.body["digest"])
        result = self._select_for(peer, exclude=set(theirs.bundle_ids))
        offers = self._offers_from(result)
        self.stats.offers_sent += len(offers)
        reply = ControlMessage(
            type=MessageType.INVENTORY_RESPONSE,
            node_id=self.node.identity.id,
            role=self.node.identity.role,
            body={
                "digest": ExactDigest(frozenset(self.node.store.bundle_ids())).to_dict(),
                "offers": offers,
                "organization_id": self.node.identity.organization_id,
            },
        )
        self.node.transport.send_bytes(msg.node_id, reply.encode())

    def _on_accept(self, msg: ControlMessage, peer: NodeIdentity) -> None:
        """Send the accepted bundles, each advanced by one hop."""
        for bundle_id in msg.body.get("bundle_ids", []):
            bundle = self.node.store.get_bundle(bundle_id)
            if bundle is None:
                continue
            now = self.node.clock.now()
            forwardable, reason = bundle.can_forward(now)
            if not forwardable:
                self.node.transport.send_bytes(
                    msg.node_id,
                    ControlMessage(
                        type=MessageType.BUNDLE_REJECT,
                        node_id=self.node.identity.id,
                        role=self.node.identity.role,
                        body={"bundle_id": bundle_id, "reason": reason},
                    ).encode(),
                )
                continue
            forwarded = bundle.forwarded(msg.node_id, now)
            self.node.transport.send_bytes(msg.node_id, BUNDLE_FRAME_PREFIX + forwarded.to_wire())
            self.stats.bundles_sent += 1
            # Delivery is recorded when the receipt arrives, never on send: a
            # transfer cut off mid-flight must be re-offered on the next contact.
            self.node.audit(
                "BUNDLE_FORWARDED",
                incident_id=bundle.header.incident_id,
                detail={
                    "bundle_id": bundle_id,
                    "to": msg.node_id,
                    "hop_count": forwarded.header.hop_count,
                },
            )

    # -------------------------------------------------------------- initiator

    def _on_inventory_response(self, msg: ControlMessage, peer: NodeIdentity) -> None:
        offers = [BundleOffer.from_dict(o) for o in msg.body.get("offers", [])]
        self.stats.offers_received += len(offers)
        wanted = self._accept_list(offers)
        if wanted:
            self.node.transport.send_bytes(
                msg.node_id,
                ControlMessage(
                    type=MessageType.BUNDLE_ACCEPT,
                    node_id=self.node.identity.id,
                    role=self.node.identity.role,
                    body={"bundle_ids": wanted},
                ).encode(),
            )
        # Reverse direction: offer the peer what its digest shows it lacks.
        theirs = ExactDigest.from_dict(msg.body["digest"])
        result = self._select_for(peer, exclude=set(theirs.bundle_ids))
        offers_out = self._offers_from(result)
        if offers_out:
            self.stats.offers_sent += len(offers_out)
            self.node.transport.send_bytes(
                msg.node_id,
                ControlMessage(
                    type=MessageType.BUNDLE_OFFER,
                    node_id=self.node.identity.id,
                    role=self.node.identity.role,
                    body={"offers": offers_out},
                ).encode(),
            )

    def _on_offer(self, msg: ControlMessage, peer: NodeIdentity) -> None:
        offers = [BundleOffer.from_dict(o) for o in msg.body.get("offers", [])]
        self.stats.offers_received += len(offers)
        wanted = self._accept_list(offers)
        if wanted:
            self.node.transport.send_bytes(
                msg.node_id,
                ControlMessage(
                    type=MessageType.BUNDLE_ACCEPT,
                    node_id=self.node.identity.id,
                    role=self.node.identity.role,
                    body={"bundle_ids": wanted},
                ).encode(),
            )

    def _accept_list(self, offers: list[BundleOffer]) -> list[str]:
        """Accept only what we lack, ordered so text arrives before media."""
        from .scheduler import PAYLOAD_ORDER

        candidates = [o for o in offers if not self.node.store.has_bundle(o.bundle_id)]
        candidates.sort(
            key=lambda o: (
                o.priority_class.rank,
                PAYLOAD_ORDER.get(o.payload_type, 9),
                -o.priority_score,
                o.size_bytes,
            )
        )
        return [o.bundle_id for o in candidates]

    # ----------------------------------------------------------- bundle frames

    def _handle_bundle_frame(self, wire: bytes, *, sender: str) -> None:
        bundle = Bundle.from_wire(wire)
        stored, reason = self.node.accept_bundle(bundle, received_from=sender)
        if stored:
            self.stats.bundles_received += 1
        elif reason == "duplicate":
            self.stats.bundles_deduplicated += 1
        else:
            self.stats.bundles_rejected += 1
            self.stats.reject_reasons.append(reason)
        self.node.transport.send_bytes(
            sender,
            ControlMessage(
                type=MessageType.BUNDLE_RECEIPT,
                node_id=self.node.identity.id,
                role=self.node.identity.role,
                body={
                    "stored": [bundle.id] if stored else [],
                    "rejected": [] if stored else [{"bundle_id": bundle.id, "reason": reason}],
                },
            ).encode(),
        )
