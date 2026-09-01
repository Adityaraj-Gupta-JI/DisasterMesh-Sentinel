"""Local persistence.

SQLite here; Room on Android. Same tables, same indexes, same invariants:
  * writes are idempotent — a duplicate bundle or acknowledgement is a no-op;
  * a lifecycle change and its audit entry commit in one transaction, or neither does;
  * binary attachments live on disk, only metadata and digests live in the database;
  * observers get change notifications (the Flow analog for the UI layer).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.clock import utc
from ..domain.enums import (
    IncidentStatus,
    PayloadType,
    PriorityClass,
    Role,
    Sensitivity,
)
from ..domain.models import (
    Acknowledgement,
    DispatchOrder,
    EventLogEntry,
    Incident,
    NodeIdentity,
    Resource,
    SyncObject,
)
from ..protocol.bundle import Bundle

SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS node_identity (
            id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL,
            organization_id TEXT, revoked INTEGER NOT NULL DEFAULT 0,
            credential_expires_at TEXT, created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY, source_node_id TEXT NOT NULL, organization_id TEXT,
            original_text TEXT NOT NULL, source_language TEXT NOT NULL,
            status TEXT NOT NULL, priority_class TEXT NOT NULL, priority_score INTEGER NOT NULL,
            severity INTEGER NOT NULL, urgency TEXT NOT NULL, verification_status TEXT NOT NULL,
            sensitivity TEXT NOT NULL, expires_at TEXT, reported_at TEXT NOT NULL,
            revision INTEGER NOT NULL, doc TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
        CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents(priority_class, priority_score DESC);
        CREATE INDEX IF NOT EXISTS idx_incidents_expiry ON incidents(expires_at);

        CREATE TABLE IF NOT EXISTS classifications (
            id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, doc TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_classifications_incident ON classifications(incident_id);

        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, doc TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_entities_incident ON entities(incident_id);

        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, kind TEXT NOT NULL,
            file_name TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL, local_path TEXT, committed INTEGER NOT NULL DEFAULT 0,
            doc TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_attachments_incident ON attachments(incident_id);

        CREATE TABLE IF NOT EXISTS bundles (
            bundle_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, payload_type TEXT NOT NULL,
            priority_class TEXT NOT NULL, priority_score INTEGER NOT NULL,
            expires_at TEXT NOT NULL, hop_count INTEGER NOT NULL, wire BLOB NOT NULL,
            received_from TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bundles_incident ON bundles(incident_id);
        CREATE INDEX IF NOT EXISTS idx_bundles_expiry ON bundles(expires_at);

        CREATE TABLE IF NOT EXISTS sync_objects (
            id TEXT PRIMARY KEY, bundle_id TEXT NOT NULL UNIQUE, incident_id TEXT NOT NULL,
            payload_type TEXT NOT NULL, priority_class TEXT NOT NULL, priority_score INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL, sensitivity TEXT NOT NULL, allowed_roles TEXT NOT NULL,
            expires_at TEXT, requires_ack INTEGER NOT NULL DEFAULT 0,
            delivered_to TEXT NOT NULL DEFAULT '[]', attempts INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_sync_priority ON sync_objects(priority_class, priority_score DESC);
        CREATE INDEX IF NOT EXISTS idx_sync_expiry ON sync_objects(expires_at);

        CREATE TABLE IF NOT EXISTS acknowledgements (
            id TEXT PRIMARY KEY, dedup_key TEXT NOT NULL UNIQUE, incident_id TEXT NOT NULL,
            node_id TEXT NOT NULL, actor_role TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ack_incident ON acknowledgements(incident_id);

        CREATE TABLE IF NOT EXISTS resources (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL, status TEXT NOT NULL,
            organization_id TEXT, doc TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dispatch_orders (
            id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, resource_id TEXT NOT NULL,
            status TEXT NOT NULL, doc TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_dispatch_incident ON dispatch_orders(incident_id);

        CREATE TABLE IF NOT EXISTS event_log (
            id TEXT PRIMARY KEY, seq INTEGER, incident_id TEXT, actor_node_id TEXT,
            actor_role TEXT, action TEXT NOT NULL, detail TEXT NOT NULL,
            prev_hash TEXT, entry_hash TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_event_incident ON event_log(incident_id);

        CREATE TABLE IF NOT EXISTS transfer_sessions (
            file_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, attachment_id TEXT NOT NULL,
            state TEXT NOT NULL, manifest TEXT NOT NULL, received_chunks TEXT NOT NULL DEFAULT '[]',
            bytes_received INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
        );
        """,
    ),
]


class SqliteStore:
    """Local database for one node."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            "PRAGMA journal_mode=WAL" if self.path != ":memory:" else "PRAGMA synchronous=OFF"
        )
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._observers: list[Callable[[str], None]] = []
        self.migrate()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------- migrations

    def migrate(self) -> int:
        cur = self._conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = cur.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        current = row["v"] or 0
        for version, script in MIGRATIONS:
            if version > current:
                cur.executescript(script)
                cur.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                current = version
        self._conn.commit()
        return current

    @property
    def schema_version(self) -> int:
        row = self._conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return row["v"] or 0

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------ observation

    def observe(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """Subscribe to table-change notifications (the Flow analog for the UI)."""
        self._observers.append(callback)
        return lambda: self._observers.remove(callback) if callback in self._observers else None

    def _notify(self, table: str) -> None:
        for cb in list(self._observers):
            try:
                cb(table)
            except Exception:
                pass  # an observer must never break a write

    # -------------------------------------------------------------- identity

    def save_node(self, node: NodeIdentity) -> None:
        self._conn.execute(
            """INSERT INTO node_identity (id, display_name, role, organization_id, revoked,
                   credential_expires_at, created_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,
                   role=excluded.role, revoked=excluded.revoked""",
            (
                node.id,
                node.display_name,
                node.role.value,
                node.organization_id,
                int(node.revoked),
                utc(node.credential_expires_at).isoformat() if node.credential_expires_at else None,
                utc(node.created_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("node_identity")

    def get_node(self, node_id: str) -> NodeIdentity | None:
        row = self._conn.execute("SELECT * FROM node_identity WHERE id=?", (node_id,)).fetchone()
        if row is None:
            return None
        return NodeIdentity(
            id=row["id"],
            display_name=row["display_name"],
            role=Role(row["role"]),
            organization_id=row["organization_id"],
            revoked=bool(row["revoked"]),
            credential_expires_at=(
                datetime.fromisoformat(row["credential_expires_at"])
                if row["credential_expires_at"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ------------------------------------------------------------- incidents

    def upsert_incident(self, incident: Incident) -> None:
        """Idempotent by id; a lower revision never overwrites a higher one."""
        existing = self.get_incident(incident.id)
        if existing and existing.revision > incident.revision:
            return
        self._conn.execute(
            """INSERT INTO incidents (id, source_node_id, organization_id, original_text,
                   source_language, status, priority_class, priority_score, severity, urgency,
                   verification_status, sensitivity, expires_at, reported_at, revision, doc,
                   created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                   priority_class=excluded.priority_class, priority_score=excluded.priority_score,
                   severity=excluded.severity, urgency=excluded.urgency,
                   verification_status=excluded.verification_status,
                   sensitivity=excluded.sensitivity, expires_at=excluded.expires_at,
                   revision=excluded.revision, doc=excluded.doc, updated_at=excluded.updated_at""",
            (
                incident.id,
                incident.source_node_id,
                incident.organization_id,
                incident.original_text,
                incident.source_language,
                incident.status.value,
                incident.priority_class.value,
                incident.priority_score,
                incident.severity,
                incident.urgency.value,
                incident.verification_status.value,
                incident.access_policy.sensitivity.value,
                utc(incident.expires_at).isoformat() if incident.expires_at else None,
                utc(incident.reported_at).isoformat(),
                incident.revision,
                json.dumps(incident.to_dict()),
                utc(incident.created_at).isoformat(),
                utc(incident.updated_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("incidents")

    def get_incident(self, incident_id: str) -> Incident | None:
        row = self._conn.execute("SELECT doc FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return _incident_from_doc(json.loads(row["doc"])) if row else None

    def list_incidents(
        self,
        *,
        status: IncidentStatus | None = None,
        priority: PriorityClass | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Incident]:
        sql = "SELECT doc FROM incidents WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status.value)
        if priority:
            sql += " AND priority_class=?"
            params.append(priority.value)
        sql += (
            " ORDER BY priority_class ASC, priority_score DESC, reported_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        return [_incident_from_doc(json.loads(r["doc"])) for r in rows]

    def count_incidents(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS c FROM incidents").fetchone()["c"]

    # --------------------------------------------------------------- bundles

    def has_bundle(self, bundle_id: str) -> bool:
        return (
            self._conn.execute("SELECT 1 FROM bundles WHERE bundle_id=?", (bundle_id,)).fetchone()
            is not None
        )

    def save_bundle(self, bundle: Bundle, *, received_from: str | None = None) -> bool:
        """Store a bundle. Returns False when it was already present (dedup)."""
        if self.has_bundle(bundle.id):
            return False
        h = bundle.header
        self._conn.execute(
            """INSERT OR IGNORE INTO bundles (bundle_id, incident_id, payload_type,
                   priority_class, priority_score, expires_at, hop_count, wire, received_from,
                   created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                h.bundle_id,
                h.incident_id,
                h.payload_type.value,
                h.priority_class.value,
                h.priority_score,
                utc(h.expires_at).isoformat(),
                h.hop_count,
                bundle.to_wire(),
                received_from,
                utc(h.created_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("bundles")
        return True

    def get_bundle(self, bundle_id: str) -> Bundle | None:
        row = self._conn.execute(
            "SELECT wire FROM bundles WHERE bundle_id=?", (bundle_id,)
        ).fetchone()
        return Bundle.from_wire(row["wire"]) if row else None

    def bundles_for_incident(
        self, incident_id: str, payload_type: PayloadType | None = None
    ) -> list[Bundle]:
        """Stored bundles for one incident, optionally narrowed by payload type."""
        sql = "SELECT wire FROM bundles WHERE incident_id=?"
        params: list[Any] = [incident_id]
        if payload_type is not None:
            sql += " AND payload_type=?"
            params.append(payload_type.value)
        sql += " ORDER BY rowid"
        rows = self._conn.execute(sql, params).fetchall()
        return [Bundle.from_wire(r["wire"]) for r in rows]

    def bundle_ids(self) -> list[str]:
        return [r["bundle_id"] for r in self._conn.execute("SELECT bundle_id FROM bundles")]

    def expired_bundles(self, now: datetime) -> list[str]:
        rows = self._conn.execute(
            "SELECT bundle_id FROM bundles WHERE expires_at <= ?", (utc(now).isoformat(),)
        ).fetchall()
        return [r["bundle_id"] for r in rows]

    # ---------------------------------------------------------- sync objects

    def upsert_sync_object(self, obj: SyncObject) -> None:
        self._conn.execute(
            """INSERT INTO sync_objects (id, bundle_id, incident_id, payload_type,
                   priority_class, priority_score, size_bytes, sensitivity, allowed_roles,
                   expires_at, requires_ack, delivered_to, attempts)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(bundle_id) DO UPDATE SET delivered_to=excluded.delivered_to,
                   attempts=excluded.attempts, priority_class=excluded.priority_class,
                   priority_score=excluded.priority_score""",
            (
                obj.id,
                obj.bundle_id,
                obj.incident_id,
                obj.payload_type.value,
                obj.priority_class.value,
                obj.priority_score,
                obj.size_bytes,
                obj.sensitivity.value,
                json.dumps([r.value for r in obj.allowed_roles]),
                utc(obj.expires_at).isoformat() if obj.expires_at else None,
                int(obj.requires_ack),
                json.dumps(list(obj.delivered_to)),
                obj.attempts,
            ),
        )
        self._conn.commit()
        self._notify("sync_objects")

    def pending_sync_objects(self, now: datetime | None = None) -> list[SyncObject]:
        """Highest-priority unexpired objects first."""
        sql = "SELECT * FROM sync_objects"
        params: list[Any] = []
        if now is not None:
            sql += " WHERE (expires_at IS NULL OR expires_at > ?)"
            params.append(utc(now).isoformat())
        sql += " ORDER BY priority_class ASC, priority_score DESC"
        return [_sync_from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def mark_delivered(self, bundle_id: str, receiver_id: str) -> None:
        row = self._conn.execute(
            "SELECT delivered_to FROM sync_objects WHERE bundle_id=?", (bundle_id,)
        ).fetchone()
        if row is None:
            return
        delivered = set(json.loads(row["delivered_to"]))
        delivered.add(receiver_id)
        self._conn.execute(
            "UPDATE sync_objects SET delivered_to=?, attempts=attempts+1 WHERE bundle_id=?",
            (json.dumps(sorted(delivered)), bundle_id),
        )
        self._conn.commit()
        self._notify("sync_objects")

    # ------------------------------------------------------ acks / dispatch

    def save_acknowledgement(self, ack: Acknowledgement) -> bool:
        """Idempotent: a repeat acknowledgement by the same node is absorbed."""
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO acknowledgements
               (id, dedup_key, incident_id, node_id, actor_role, note, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                ack.id,
                ack.dedup_key,
                ack.incident_id,
                ack.node_id,
                ack.actor_role.value,
                ack.note,
                utc(ack.created_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("acknowledgements")
        return cur.rowcount > 0

    def acknowledgements_for(self, incident_id: str) -> list[Acknowledgement]:
        rows = self._conn.execute(
            "SELECT * FROM acknowledgements WHERE incident_id=? ORDER BY created_at", (incident_id,)
        ).fetchall()
        return [
            Acknowledgement(
                id=r["id"],
                incident_id=r["incident_id"],
                node_id=r["node_id"],
                actor_role=Role(r["actor_role"]),
                note=r["note"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def save_resource(self, resource: Resource) -> None:
        self._conn.execute(
            """INSERT INTO resources (id, kind, label, status, organization_id, doc, last_seen_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status, doc=excluded.doc,
                   last_seen_at=excluded.last_seen_at""",
            (
                resource.id,
                resource.kind.value,
                resource.label,
                resource.status.value,
                resource.organization_id,
                json.dumps(resource.to_dict()),
                utc(resource.last_seen_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("resources")

    def list_resources(self) -> list[dict]:
        return [json.loads(r["doc"]) for r in self._conn.execute("SELECT doc FROM resources")]

    def save_dispatch(self, order: DispatchOrder) -> None:
        self._conn.execute(
            """INSERT INTO dispatch_orders (id, incident_id, resource_id, status, doc,
                   created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status, doc=excluded.doc,
                   updated_at=excluded.updated_at""",
            (
                order.id,
                order.incident_id,
                order.resource_id,
                order.status.value,
                json.dumps(order.to_dict()),
                utc(order.created_at).isoformat(),
                utc(order.updated_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("dispatch_orders")

    def list_dispatch(self, incident_id: str | None = None) -> list[dict]:
        if incident_id:
            rows = self._conn.execute(
                "SELECT doc FROM dispatch_orders WHERE incident_id=?", (incident_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT doc FROM dispatch_orders").fetchall()
        return [json.loads(r["doc"]) for r in rows]

    # ------------------------------------------------------------ event log

    def append_event(self, entry: EventLogEntry) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO event_log (id, incident_id, actor_node_id, actor_role,
                   action, detail, prev_hash, entry_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                entry.id,
                entry.incident_id,
                entry.actor_node_id,
                entry.actor_role.value if entry.actor_role else None,
                entry.action,
                json.dumps(entry.detail),
                entry.prev_hash,
                entry.entry_hash,
                utc(entry.created_at).isoformat(),
            ),
        )
        self._conn.commit()
        self._notify("event_log")

    def transition_with_event(self, incident: Incident, entry: EventLogEntry) -> None:
        """Persist a lifecycle change and its audit entry atomically."""
        try:
            self._conn.execute("BEGIN")
            self._conn.execute(
                "UPDATE incidents SET status=?, revision=?, doc=?, updated_at=? WHERE id=?",
                (
                    incident.status.value,
                    incident.revision,
                    json.dumps(incident.to_dict()),
                    utc(incident.updated_at).isoformat(),
                    incident.id,
                ),
            )
            self._conn.execute(
                """INSERT OR IGNORE INTO event_log (id, incident_id, actor_node_id, actor_role,
                       action, detail, prev_hash, entry_hash, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    entry.id,
                    entry.incident_id,
                    entry.actor_node_id,
                    entry.actor_role.value if entry.actor_role else None,
                    entry.action,
                    json.dumps(entry.detail),
                    entry.prev_hash,
                    entry.entry_hash,
                    utc(entry.created_at).isoformat(),
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        self._notify("incidents")
        self._notify("event_log")

    def events(self, incident_id: str | None = None) -> list[dict]:
        if incident_id:
            rows = self._conn.execute(
                "SELECT * FROM event_log WHERE incident_id=? ORDER BY rowid", (incident_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM event_log ORDER BY rowid").fetchall()
        return [dict(r) | {"detail": json.loads(r["detail"])} for r in rows]

    # ------------------------------------------------------------ attachments

    def save_attachment(self, doc: dict) -> None:
        self._conn.execute(
            """INSERT INTO attachments (id, incident_id, kind, file_name, mime_type,
                   size_bytes, sha256, local_path, committed, doc, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET committed=excluded.committed,
                   local_path=excluded.local_path, doc=excluded.doc""",
            (
                doc["id"],
                doc["incident_id"],
                doc["kind"],
                doc["file_name"],
                doc["mime_type"],
                doc["size_bytes"],
                doc["sha256"],
                doc.get("local_path"),
                int(doc.get("committed", False)),
                json.dumps(doc),
                doc["created_at"],
            ),
        )
        self._conn.commit()
        self._notify("attachments")

    def attachments_for(self, incident_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT doc FROM attachments WHERE incident_id=?", (incident_id,)
        ).fetchall()
        return [json.loads(r["doc"]) for r in rows]


def _incident_from_doc(doc: dict) -> Incident:
    """Rebuild an Incident from its stored JSON document."""
    from ..domain.enums import (
        ConditionType,
        DisasterType,
        Provenance,
        Urgency,
        VerificationStatus,
    )
    from ..domain.models import AccessPolicy, Condition, GeoPoint, Quantity

    loc = doc.get("location")
    people = doc.get("people_affected") or {}
    ap = doc.get("access_policy") or {}
    return Incident(
        id=doc["id"],
        source_node_id=doc["source_node_id"],
        organization_id=doc.get("organization_id"),
        original_text=doc["original_text"],
        source_language=doc.get("source_language", "und"),
        location=GeoPoint(**loc) if loc else None,
        reported_at=datetime.fromisoformat(doc["reported_at"]),
        expires_at=datetime.fromisoformat(doc["expires_at"]) if doc.get("expires_at") else None,
        disaster_types=tuple(DisasterType(d) for d in doc.get("disaster_types", [])),
        urgency=Urgency(doc.get("urgency", "UNKNOWN")),
        severity=doc.get("severity", 0),
        classification_confidence=doc.get("classification_confidence", 0.0),
        people_affected=Quantity(
            value=people.get("value"),
            raw=people.get("raw"),
            approximate=people.get("approximate", False),
            confidence=people.get("confidence"),
        ),
        conditions=tuple(
            Condition(
                type=ConditionType(c["type"]),
                raw=c.get("raw"),
                confidence=c.get("confidence"),
                provenance=Provenance(c.get("provenance", "MACHINE_GENERATED")),
            )
            for c in doc.get("conditions", [])
        ),
        requested_resources=tuple(doc.get("requested_resources", [])),
        priority_score=doc.get("priority_score", 0),
        priority_class=PriorityClass(doc.get("priority_class", "P3")),
        priority_explanation=tuple(doc.get("priority_explanation", [])),
        policy_version=doc.get("policy_version", "policy-1.0.0"),
        status=IncidentStatus(doc.get("status", "DRAFT")),
        verification_status=VerificationStatus(doc.get("verification_status", "UNVERIFIED")),
        access_policy=AccessPolicy(
            sensitivity=Sensitivity(ap.get("sensitivity", "OPERATIONAL")),
            allowed_roles=tuple(Role(r) for r in ap.get("allowed_roles", [])),
            organization_id=ap.get("organization_id"),
            precise_location_roles=tuple(Role(r) for r in ap.get("precise_location_roles", [])),
        ),
        attachment_ids=tuple(doc.get("attachment_ids", [])),
        audio_reference=doc.get("audio_reference"),
        cluster_id=doc.get("cluster_id"),
        provenance=Provenance(doc.get("provenance", "HUMAN_REPORTED")),
        revision=doc.get("revision", 1),
        schema_version=doc.get("schema_version", "1.0.0"),
        created_at=datetime.fromisoformat(doc["created_at"]),
        updated_at=datetime.fromisoformat(doc["updated_at"]),
    )


def _sync_from_row(row: sqlite3.Row) -> SyncObject:
    return SyncObject(
        id=row["id"],
        bundle_id=row["bundle_id"],
        incident_id=row["incident_id"],
        payload_type=PayloadType(row["payload_type"]),
        priority_class=PriorityClass(row["priority_class"]),
        priority_score=row["priority_score"],
        size_bytes=row["size_bytes"],
        sensitivity=Sensitivity(row["sensitivity"]),
        allowed_roles=tuple(Role(r) for r in json.loads(row["allowed_roles"])),
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        requires_ack=bool(row["requires_ack"]),
        delivered_to=tuple(json.loads(row["delivered_to"])),
        attempts=row["attempts"],
    )
