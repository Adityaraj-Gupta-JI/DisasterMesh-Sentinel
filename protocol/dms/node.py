"""MeshNode — one device: reporter, relay, or coordinator.

Composition root. Everything below it stays independent: the store does not know
about radios, the scheduler does not know about crypto, the priority engine does not
know about models. This class wires them together and owns the audit trail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from .ai.base import AIError
from .ai.rules import extract_entities, triage
from .crypto.keys import CryptoError, SoftwareKeyStore
from .crypto.sealing import seal, unseal, verify_signature
from .domain.clock import SYSTEM_CLOCK, Clock, utc
from .domain.enums import (
    AttachmentKind,
    ConditionType,
    IncidentStatus,
    PayloadType,
    PriorityClass,
    Provenance,
    Role,
    Sensitivity,
    VerificationStatus,
)
from .domain.errors import LifecycleError, ProtocolError
from .domain.lifecycle import transition
from .domain.models import (
    AccessPolicy,
    Acknowledgement,
    Attachment,
    Condition,
    GeoPoint,
    Incident,
    NodeIdentity,
    Quantity,
    SyncObject,
)
from .files.manifest import FileManifest
from .files.transfer import TransferSession, chunk_bytes
from .governance.audit import EventLog
from .governance.authz import can_read_plaintext
from .priority.engine import Override, PriorityInputs, age_seconds, evaluate
from .priority.policies import SyncContext, select_policy
from .protocol.bundle import Bundle
from .store.sqlite import SqliteStore
from .sync.engine import SyncEngine
from .transport.base import Transport, TransportEvent


@dataclass
class NodeConfig:
    """Per-device operational settings surfaced in the relay UI."""

    relay_enabled: bool = True
    battery: float = 1.0
    free_storage_bytes: int = 8 * 1024 * 1024 * 1024
    online: bool = False
    max_stored_bundles: int = 5000
    ai_available: bool = True


class MeshNode:
    """A DisasterMesh device."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: Transport,
        *,
        store: SqliteStore | None = None,
        keystore: SoftwareKeyStore | None = None,
        clock: Clock = SYSTEM_CLOCK,
        data_dir: str | Path | None = None,
        org_key_id: str = "org-demo",
        config: NodeConfig | None = None,
    ) -> None:
        self.identity = identity
        self.transport = transport
        self.store = store or SqliteStore(":memory:")
        self.keystore = keystore or SoftwareKeyStore()
        self.clock = clock
        self.config = config or NodeConfig()
        self.org_key_id = org_key_id
        self.event_log = EventLog(clock)
        self.sync = SyncEngine(self)
        self.transfers: dict[str, TransferSession] = {}

        base = Path(data_dir) if data_dir else Path.home() / ".dms" / identity.id
        self.quarantine_dir = base / "quarantine"
        self.committed_dir = base / "attachments"

        self.keystore.generate(identity.id)
        self.store.save_node(identity)
        self._unsubscribe = transport.observe(self._on_event)

    # ------------------------------------------------------------------ setup

    @property
    def can_decrypt(self) -> bool:
        """True when this node holds the organization payload key."""
        return self.org_key_id in getattr(self.keystore, "_symmetric", {})

    def grant_org_key(self, key: bytes) -> None:
        self.keystore.set_shared_key(self.org_key_id, key)

    def trust(self, peer: MeshNode) -> None:
        """Register a peer's public key so its signatures verify here."""
        self.keystore.register_public_key(
            peer.identity.id, peer.keystore._public[peer.identity.id].public_bytes_raw()
        )

    def start(self) -> None:
        self.transport.start_advertising(
            {
                "node_id": self.identity.id,
                "role": self.identity.role.value,
                "org": self.identity.organization_id,
            }
        )
        self.transport.start_discovery()

    def stop(self) -> None:
        self.transport.stop_advertising()
        self.transport.stop_discovery()
        self._unsubscribe()
        if hasattr(self.store, "close"):
            self.store.close()


    def sync_context(self) -> SyncContext:
        return SyncContext(
            receiver_role=self.identity.role,
            battery=self.config.battery,
            free_storage_bytes=self.config.free_storage_bytes,
            online=self.config.online,
            now=self.clock.now(),
        )

    def audit(self, action: str, **kwargs: Any) -> None:
        entry = self.event_log.append(
            action,
            actor_node_id=self.identity.id,
            actor_role=self.identity.role,
            now=self.clock.now(),
            **kwargs,
        )
        self.store.append_event(entry)

    def _on_event(self, event: TransportEvent) -> None:
        self.sync.on_transport_event(event)

    # -------------------------------------------------------------- reporting

    def report_incident(
        self,
        text: str,
        *,
        language: str | None = None,
        location: GeoPoint | None = None,
        audio_reference: str | None = None,
        share_precise_location: bool = True,
        organization_id: str | None = None,
    ) -> Incident:
        """Create, classify, prioritize, seal, and queue an incident.

        Classification never blocks submission: if AI is unavailable the rule engine
        runs, and the original text is stored verbatim either way.
        """
        now = self.clock.now()
        analysis = self.analyze(text, language=language)

        entity = analysis["entities"]
        people = entity.people_affected
        conditions = tuple(
            Condition(
                type=ConditionType(c["type"]), raw=c.get("raw"), confidence=c.get("confidence")
            )
            for c in entity.conditions
        )
        tri = analysis["triage"]

        decision = evaluate(
            PriorityInputs(
                urgency=tri.urgency,
                severity=tri.severity,
                disaster_types=tri.disaster_types,
                confidence=tri.confidence,
                people_affected=Quantity(
                    value=people.get("value"),
                    raw=people.get("raw"),
                    approximate=people.get("approximate", False),
                    confidence=people.get("confidence"),
                ),
                conditions=conditions,
                hazards=entity.hazards,
                message_age_seconds=0.0,
                ai_available=self.config.ai_available,
            )
        )

        incident = Incident(
            source_node_id=self.identity.id,
            organization_id=organization_id or self.identity.organization_id,
            original_text=text,
            source_language=language or analysis["language"],
            location=location
            if share_precise_location
            else (location.coarse() if location else None),
            reported_at=now,
            expires_at=now + timedelta(seconds=decision.ttl_seconds),
            disaster_types=tri.disaster_types,
            urgency=tri.urgency,
            severity=tri.severity,
            classification_confidence=tri.confidence,
            people_affected=Quantity(
                value=people.get("value"),
                raw=people.get("raw"),
                approximate=people.get("approximate", False),
                confidence=people.get("confidence"),
            ),
            conditions=conditions,
            requested_resources=entity.resources,
            priority_score=decision.score,
            priority_class=decision.priority_class,
            priority_explanation=decision.explanation,
            policy_version=decision.policy_version,
            status=IncidentStatus.QUEUED,
            verification_status=VerificationStatus.AI_CLASSIFIED,
            access_policy=AccessPolicy(
                sensitivity=decision.sensitivity,
                allowed_roles=decision.allowed_roles,
                organization_id=organization_id or self.identity.organization_id,
                precise_location_roles=(
                    Role.EVENT_COORDINATOR,
                    Role.MEDICAL_RESPONDER,
                    Role.FLOOD_RESPONDER,
                    Role.GOVERNMENT_AUTHORITY,
                ),
            ),
            audio_reference=audio_reference,
            provenance=Provenance.HUMAN_REPORTED,
            created_at=now,
            updated_at=now,
        )
        self.store.upsert_incident(incident)
        self.audit(
            "INCIDENT_CREATED",
            incident_id=incident.id,
            detail={
                "priority_class": decision.priority_class.value,
                "priority_score": decision.score,
                "policy_version": decision.policy_version,
                "escalated_by_rule": decision.escalated_by_rule,
            },
        )
        self._queue_incident_text(incident, decision)
        return incident

    def analyze(self, text: str, *, language: str | None = None) -> dict:
        """Run triage and extraction, degrading to rules when AI is unavailable."""
        from .ai.lexicon import detect_language

        lang = language or detect_language(text)
        if not self.config.ai_available:
            # Rules are the fallback AND the mock, so behavior is identical offline.
            return {
                "triage": triage(text, lang),
                "entities": extract_entities(text, lang),
                "language": lang,
                "degraded": True,
            }
        try:
            return {
                "triage": triage(text, lang),
                "entities": extract_entities(text, lang),
                "language": lang,
                "degraded": False,
            }
        except AIError:
            return {
                "triage": triage(text, lang),
                "entities": extract_entities(text, lang),
                "language": lang,
                "degraded": True,
            }

    def _queue_incident_text(self, incident: Incident, decision) -> Bundle:
        """The critical-text bundle: independent of any attachment."""
        payload = json.dumps(incident.to_dict(), sort_keys=True).encode("utf-8")
        bundle = Bundle.create(
            incident_id=incident.id,
            source_node_id=self.identity.id,
            payload=payload,
            payload_type=PayloadType.INCIDENT_TEXT,
            now=self.clock.now(),
            ttl_seconds=decision.ttl_seconds,
            priority_class=decision.priority_class,
            priority_score=decision.score,
            organization_id=incident.organization_id,
            role_scope=decision.allowed_roles,
            sensitivity=decision.sensitivity,
            category=tuple(d.value for d in incident.disaster_types),
            replication_limit=decision.replication_limit,
            requires_ack=decision.requires_ack,
        )
        sealed = seal(
            bundle,
            keystore=self.keystore,
            key_id=self.org_key_id,
            signer_node_id=self.identity.id,
        )
        self._store_and_queue(sealed, incident, decision.sensitivity, decision.allowed_roles)
        return sealed

    def _store_and_queue(
        self,
        bundle: Bundle,
        incident: Incident,
        sensitivity: Sensitivity,
        allowed_roles: tuple[Role, ...],
    ) -> None:
        self.store.save_bundle(bundle)
        self.store.upsert_sync_object(
            SyncObject(
                bundle_id=bundle.id,
                incident_id=incident.id,
                payload_type=bundle.header.payload_type,
                priority_class=bundle.header.priority_class,
                priority_score=bundle.header.priority_score,
                size_bytes=len(bundle.payload),
                sensitivity=sensitivity,
                allowed_roles=allowed_roles,
                expires_at=bundle.header.expires_at,
                requires_ack=bundle.header.requires_ack,
            )
        )

    # ------------------------------------------------------------ attachments

    def attach(
        self,
        incident_id: str,
        data: bytes,
        *,
        file_name: str,
        mime_type: str,
        kind: AttachmentKind = AttachmentKind.IMAGE,
    ) -> Attachment:
        """Attach evidence. Queued strictly behind the incident text."""
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise LifecycleError(f"unknown incident {incident_id}")
        now = self.clock.now()

        manifest = FileManifest.for_bytes(
            data,
            file_name=file_name,
            mime_type=mime_type,
            kind=kind,
            incident_id=incident_id,
            priority_class=incident.priority_class,
            expires_at=incident.expires_at,
        )
        manifest.validate_policy()

        attachment = Attachment(
            incident_id=incident_id,
            kind=kind,
            file_name=file_name,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=manifest.sha256,
            created_at=now,
        )
        manifest.attachment_id = attachment.id

        self.committed_dir.mkdir(parents=True, exist_ok=True)
        local = self.committed_dir / f"{attachment.id}_{file_name}"
        local.write_bytes(data)
        attachment.local_path = str(local)
        attachment.committed = True
        self.store.save_attachment(attachment.to_dict())

        incident.attachment_ids = incident.attachment_ids + (attachment.id,)
        incident.touch(now)
        self.store.upsert_incident(incident)

        policy = select_policy(incident.priority_class, incident.disaster_types)
        sensitivity = incident.access_policy.sensitivity
        allowed = incident.access_policy.allowed_roles

        manifest_bundle = seal(
            Bundle.create(
                incident_id=incident_id,
                source_node_id=self.identity.id,
                payload=json.dumps(manifest.to_dict()).encode("utf-8"),
                payload_type=PayloadType.ATTACHMENT_MANIFEST,
                now=now,
                ttl_seconds=int((utc(incident.expires_at) - utc(now)).total_seconds())
                if incident.expires_at
                else 3600,
                priority_class=incident.priority_class,
                priority_score=incident.priority_score,
                sensitivity=sensitivity,
                role_scope=allowed,
            ),
            keystore=self.keystore,
            key_id=self.org_key_id,
            signer_node_id=self.identity.id,
        )
        self._store_and_queue(manifest_bundle, incident, sensitivity, allowed)

        for index, chunk in chunk_bytes(data, manifest):
            chunk_bundle = seal(
                Bundle.create(
                    incident_id=incident_id,
                    source_node_id=self.identity.id,
                    payload=json.dumps(
                        {"file_id": manifest.file_id, "index": index, "data": chunk.hex()}
                    ).encode("utf-8"),
                    payload_type=PayloadType.ATTACHMENT_CHUNK,
                    now=now,
                    ttl_seconds=int((utc(incident.expires_at) - utc(now)).total_seconds())
                    if incident.expires_at
                    else 3600,
                    priority_class=incident.priority_class,
                    priority_score=max(0, incident.priority_score - 1),
                    sensitivity=sensitivity,
                    role_scope=allowed,
                ),
                keystore=self.keystore,
                key_id=self.org_key_id,
                signer_node_id=self.identity.id,
            )
            self._store_and_queue(chunk_bundle, incident, sensitivity, allowed)

        self.audit(
            "ATTACHMENT_ADDED",
            incident_id=incident_id,
            detail={
                "attachment_id": attachment.id,
                "sha256": manifest.sha256[:12],
                "chunks": manifest.chunk_count,
                "policy": policy.name,
                "explanation": policy.explanation,
            },
        )
        return attachment

    # --------------------------------------------------------------- receiving

    def accept_bundle(self, bundle: Bundle, *, received_from: str) -> tuple[bool, str]:
        """Validate, deduplicate, store, and apply an incoming bundle."""
        now = self.clock.now()
        if self.store.has_bundle(bundle.id):
            return False, "duplicate"
        try:
            bundle.validate(now)
        except ProtocolError as exc:
            self.audit("BUNDLE_REJECTED", detail={"bundle_id": bundle.id, "reason": str(exc)})
            return False, str(exc)

        if bundle.header.signer_node_id and not verify_signature(bundle, keystore=self.keystore):
            self.audit(
                "BUNDLE_REJECTED",
                detail={"bundle_id": bundle.id, "reason": "signature_verification_failed"},
            )
            return False, "signature_verification_failed"

        self.store.save_bundle(bundle, received_from=received_from)
        self.audit(
            "BUNDLE_RECEIVED",
            incident_id=bundle.header.incident_id,
            detail={
                "bundle_id": bundle.id,
                "from": received_from,
                "hops": bundle.header.hop_count,
                "path": list(bundle.header.path),
            },
        )

        # Relays re-offer what they carry; they do not need to read it.
        self.store.upsert_sync_object(
            SyncObject(
                bundle_id=bundle.id,
                incident_id=bundle.header.incident_id,
                payload_type=bundle.header.payload_type,
                priority_class=bundle.header.priority_class,
                priority_score=bundle.header.priority_score,
                size_bytes=len(bundle.payload),
                sensitivity=bundle.header.sensitivity,
                allowed_roles=bundle.header.role_scope,
                expires_at=bundle.header.expires_at,
                requires_ack=bundle.header.requires_ack,
                delivered_to=(received_from,),
            )
        )

        if not can_read_plaintext(self.identity.role, bundle.header.sensitivity):
            return True, "stored_ciphertext_only"
        try:
            plaintext = unseal(bundle, keystore=self.keystore, now=now)
        except (CryptoError, ProtocolError):
            return True, "stored_ciphertext_only"

        self._apply_payload(bundle, plaintext, received_from=received_from)
        return True, "stored"

    def _apply_payload(self, bundle: Bundle, plaintext: bytes, *, received_from: str) -> None:
        kind = bundle.header.payload_type
        try:
            doc = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        if kind is PayloadType.INCIDENT_TEXT:
            from .store.sqlite import _incident_from_doc

            incident = _incident_from_doc(doc)
            existing = self.store.get_incident(incident.id)
            if existing is None or incident.revision >= existing.revision:
                if incident.status is IncidentStatus.QUEUED:
                    incident.status = (
                        IncidentStatus.RECEIVED
                        if self.identity.role
                        in (
                            Role.EVENT_COORDINATOR,
                            Role.MEDICAL_RESPONDER,
                            Role.FLOOD_RESPONDER,
                            Role.GOVERNMENT_AUTHORITY,
                        )
                        else IncidentStatus.RELAYED
                    )
                self.store.upsert_incident(incident)
        elif kind is PayloadType.ATTACHMENT_MANIFEST:
            manifest = FileManifest.from_dict(doc)
            session = TransferSession(
                manifest=manifest,
                quarantine_dir=self.quarantine_dir,
                committed_dir=self.committed_dir,
            )
            try:
                session.accept(now=self.clock.now())
                session.begin()
                self.transfers[manifest.file_id] = session
            except Exception as exc:
                self.audit(
                    "ATTACHMENT_REJECTED",
                    incident_id=manifest.incident_id,
                    detail={"file_id": manifest.file_id, "reason": str(exc)},
                )
        elif kind is PayloadType.ATTACHMENT_CHUNK:
            session = self.transfers.get(doc.get("file_id", ""))
            if session is None:
                return  # manifest not seen yet; the chunk will be re-offered
            try:
                session.receive_chunk(int(doc["index"]), bytes.fromhex(doc["data"]))
            except Exception:
                return
            if not session.missing:
                try:
                    path = session.verify_and_commit()
                except Exception as exc:
                    self.audit(
                        "ATTACHMENT_FAILED",
                        incident_id=session.manifest.incident_id,
                        detail={"file_id": session.manifest.file_id, "reason": str(exc)},
                    )
                    return
                att = Attachment(
                    id=session.manifest.attachment_id or session.manifest.file_id,
                    incident_id=session.manifest.incident_id,
                    kind=session.manifest.kind,
                    file_name=session.manifest.file_name,
                    mime_type=session.manifest.mime_type,
                    size_bytes=session.manifest.size_bytes,
                    sha256=session.manifest.sha256,
                    local_path=str(path),
                    committed=True,
                    created_at=self.clock.now(),
                )
                self.store.save_attachment(att.to_dict())
                self.audit(
                    "ATTACHMENT_COMMITTED",
                    incident_id=att.incident_id,
                    detail={"attachment_id": att.id, "sha256": att.sha256[:12], "verified": True},
                )
        elif kind is PayloadType.ACKNOWLEDGEMENT:
            self.apply_acknowledgement(doc)

    # ---------------------------------------------------------- coordination

    def acknowledge(self, incident_id: str, note: str | None = None) -> Acknowledgement:
        """Coordinator acknowledgement. Idempotent, audited, and propagated back."""
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise LifecycleError(f"unknown incident {incident_id}")
        now = self.clock.now()
        ack = Acknowledgement(
            incident_id=incident_id,
            node_id=self.identity.id,
            actor_role=self.identity.role,
            note=note,
            created_at=now,
        )
        is_new = self.store.save_acknowledgement(ack)
        if is_new:
            if incident.status is IncidentStatus.QUEUED:
                incident.status = IncidentStatus.RECEIVED
                self.store.upsert_incident(incident)
            changed = transition(
                incident, IncidentStatus.ACKNOWLEDGED, role=self.identity.role, now=now
            )
            if changed:
                entry = self.event_log.append(
                    "INCIDENT_ACKNOWLEDGED",
                    incident_id=incident_id,
                    actor_node_id=self.identity.id,
                    actor_role=self.identity.role,
                    detail={"ack_id": ack.id, "note": note},
                    now=now,
                )
                self.store.transition_with_event(incident, entry)
            self._queue_ack_bundle(incident, ack)
        return ack

    def apply_acknowledgement(self, doc: dict) -> None:
        """Absorb a remote acknowledgement idempotently."""
        ack = Acknowledgement(
            id=doc.get("id", ""),
            incident_id=doc.get("incident_id", ""),
            node_id=doc.get("node_id", ""),
            actor_role=Role(doc.get("actor_role", Role.EVENT_COORDINATOR.value)),
            note=doc.get("note"),
            created_at=self.clock.now(),
        )
        if not self.store.save_acknowledgement(ack):
            return
        incident = self.store.get_incident(ack.incident_id)
        if incident and incident.status in (
            IncidentStatus.QUEUED,
            IncidentStatus.RELAYED,
            IncidentStatus.RECEIVED,
        ):
            if incident.status is not IncidentStatus.RECEIVED:
                incident.status = IncidentStatus.RECEIVED
            incident.status = IncidentStatus.ACKNOWLEDGED
            incident.touch(self.clock.now())
            self.store.upsert_incident(incident)
            self.audit(
                "INCIDENT_ACKNOWLEDGED_REMOTE",
                incident_id=incident.id,
                detail={"by": ack.node_id},
            )

    def _queue_ack_bundle(self, incident: Incident, ack: Acknowledgement) -> None:
        bundle = seal(
            Bundle.create(
                incident_id=incident.id,
                source_node_id=self.identity.id,
                payload=json.dumps(ack.to_dict()).encode("utf-8"),
                payload_type=PayloadType.ACKNOWLEDGEMENT,
                now=self.clock.now(),
                ttl_seconds=3600,
                priority_class=PriorityClass.P1,
                priority_score=max(50, incident.priority_score - 10),
                sensitivity=Sensitivity.OPERATIONAL,
            ),
            keystore=self.keystore,
            key_id=self.org_key_id,
            signer_node_id=self.identity.id,
        )
        self._store_and_queue(bundle, incident, Sensitivity.OPERATIONAL, ())

    def override_priority(self, incident_id: str, priority: PriorityClass, reason: str) -> Incident:
        """Human override of the engine. Always recorded with its reason."""
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise LifecycleError(f"unknown incident {incident_id}")
        base = evaluate(
            PriorityInputs(
                urgency=incident.urgency,
                severity=incident.severity,
                disaster_types=incident.disaster_types,
                confidence=incident.classification_confidence,
                people_affected=incident.people_affected,
                conditions=incident.conditions,
                message_age_seconds=age_seconds(incident.reported_at, self.clock.now()),
                human_verified=True,
            )
        )
        decided = Override(
            priority_class=priority,
            reason=reason,
            actor_node_id=self.identity.id,
            actor_role=self.identity.role,
            at=self.clock.now(),
        ).apply(base)
        incident.priority_class = decided.priority_class
        incident.priority_score = decided.score
        incident.priority_explanation = decided.explanation
        incident.verification_status = VerificationStatus.HUMAN_VERIFIED
        incident.touch(self.clock.now())
        self.store.upsert_incident(incident)
        self.audit(
            "PRIORITY_OVERRIDDEN",
            incident_id=incident_id,
            detail={"to": priority.value, "reason": reason},
        )
        return incident

    # -------------------------------------------------------------------- sync

    def sync_with(self, peer_id: str) -> None:
        """Start an exchange with a connected peer."""
        if not self.config.relay_enabled and self.identity.role is Role.VOLUNTEER_RELAY:
            return
        self.sync.request_inventory(peer_id)

    def status(self) -> dict:
        """Non-sensitive counters for the relay and coordinator UIs."""
        return {
            "node_id": self.identity.id,
            "role": self.identity.role.value,
            "relay_enabled": self.config.relay_enabled,
            "battery": self.config.battery,
            "stored_bundles": len(self.store.bundle_ids()),
            "incidents": self.store.count_incidents(),
            "forwarded": self.sync.stats.bundles_sent,
            "received": self.sync.stats.bundles_received,
            "deduplicated": self.sync.stats.bundles_deduplicated,
            "can_read_payloads": self.can_decrypt,
            "online": self.config.online,
        }
