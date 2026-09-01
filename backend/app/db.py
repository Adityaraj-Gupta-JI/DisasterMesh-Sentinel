"""Database schema and session management (SQLAlchemy + SQLite/PostgreSQL)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True)
    organization_id = Column(String, index=True, nullable=False)
    source_node_id = Column(String, nullable=False)
    original_text = Column(Text, nullable=False)
    source_language = Column(String, nullable=False, default="und")
    status = Column(String, index=True, nullable=False)
    priority_class = Column(String, index=True, nullable=False)
    priority_score = Column(Integer, index=True, nullable=False, default=0)
    severity = Column(Integer, nullable=False, default=0)
    urgency = Column(String, nullable=False, default="UNKNOWN")
    sensitivity = Column(String, nullable=False, default="OPERATIONAL")
    verification_status = Column(String, nullable=False, default="UNVERIFIED")
    cluster_id = Column(String, index=True, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    doc = Column(JSON, nullable=False)
    reported_at = Column(DateTime, nullable=False, default=_now)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now)


Index(
    "ix_incidents_queue",
    IncidentRow.organization_id,
    IncidentRow.priority_class,
    IncidentRow.priority_score.desc(),
)


class AttachmentRow(Base):
    __tablename__ = "attachments"
    id = Column(String, primary_key=True)
    incident_id = Column(String, ForeignKey("incidents.id"), index=True, nullable=False)
    organization_id = Column(String, index=True, nullable=False)
    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="IMAGE")
    verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)
    # Optional inline bytes so the coordinator dashboard can render the actual image
    # or play the audio. Nullable: existing rows and metadata-only attachments are
    # unaffected, and the mesh transfer path that carries bytes elsewhere is untouched.
    data = Column(LargeBinary, nullable=True)


class ClassificationRow(Base):
    __tablename__ = "classifications"
    id = Column(String, primary_key=True)
    incident_id = Column(String, index=True, nullable=False)
    organization_id = Column(String, index=True, nullable=False)
    doc = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)


class ClusterRow(Base):
    __tablename__ = "clusters"
    id = Column(String, primary_key=True)
    organization_id = Column(String, index=True, nullable=False)
    doc = Column(JSON, nullable=False)
    human_reviewed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)


class ResourceRow(Base):
    __tablename__ = "resources"
    id = Column(String, primary_key=True)
    organization_id = Column(String, index=True, nullable=False)
    kind = Column(String, nullable=False)
    label = Column(String, nullable=False)
    status = Column(String, nullable=False, default="AVAILABLE")
    simulated = Column(Boolean, nullable=False, default=True)
    doc = Column(JSON, nullable=False)
    last_seen_at = Column(DateTime, nullable=False, default=_now)


class DispatchRow(Base):
    __tablename__ = "dispatch_orders"
    id = Column(String, primary_key=True)
    incident_id = Column(String, index=True, nullable=False)
    organization_id = Column(String, index=True, nullable=False)
    resource_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    simulated = Column(Boolean, nullable=False, default=True)
    doc = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now)


class AlertRow(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True)
    organization_id = Column(String, index=True, nullable=False)
    headline = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    authorized_by = Column(String, nullable=False)
    authorized_role = Column(String, nullable=False)
    published = Column(Boolean, nullable=False, default=False)
    doc = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)


class AuditRow(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True)
    organization_id = Column(String, index=True, nullable=False)
    incident_id = Column(String, index=True, nullable=True)
    actor = Column(String, nullable=True)
    actor_role = Column(String, nullable=True)
    action = Column(String, nullable=False)
    detail = Column(JSON, nullable=False, default=dict)
    prev_hash = Column(String, nullable=True)
    entry_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)


class IdempotencyRow(Base):
    """Replay protection: one key, one stored response."""

    __tablename__ = "idempotency_keys"
    key = Column(String, primary_key=True)
    organization_id = Column(String, primary_key=True)
    endpoint = Column(String, nullable=False)
    response = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)


class SyncCursorRow(Base):
    __tablename__ = "sync_cursors"
    node_id = Column(String, primary_key=True)
    organization_id = Column(String, primary_key=True)
    last_seen_bundle = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_now)


_engine = None
_SessionLocal = None


def engine():
    global _engine
    if _engine is None:
        kwargs = {"future": True}
        if settings.database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine(), autoflush=False, future=True)
    return _SessionLocal


def init_db() -> None:
    """Create tables. Never drops or rewrites existing data."""
    eng = engine()
    Base.metadata.create_all(eng)
    _add_missing_columns(eng)


def _add_missing_columns(eng) -> None:
    """Additively backfill columns introduced after a database was first created.

    Only ever issues ``ADD COLUMN`` for a nullable column that is missing, so an
    older database keeps every existing row and value untouched.
    """
    additive = {
        "attachments": {"data": "BLOB"},
    }
    inspector = inspect(eng)
    existing_tables = set(inspector.get_table_names())
    with eng.begin() as conn:
        for table, columns in additive.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl_type in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def reset_engine(url: str) -> None:
    """Point the process at a different database (tests and the demo reset script)."""
    global _engine, _SessionLocal
    settings.database_url = url
    _engine = None
    _SessionLocal = None


def get_session():
    factory = session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
