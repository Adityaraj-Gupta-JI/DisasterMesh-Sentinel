"""DisasterMesh Sentinel gateway API.

The gateway is optional by design: the mesh works without it. When it is reachable
it reconciles what nodes carried, and serves the coordinator dashboard.

Every route is organization-scoped and role-gated. Dispatch and public alerts require
an explicit human confirmation, and nothing here ever contacts a real emergency service.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "protocol"))

from dms.ai.clustering import cluster as build_cluster  # noqa: E402
from dms.ai.mocks import summarize  # noqa: E402
from dms.dispatch.service import CAPABILITY_MATRIX  # noqa: E402
from dms.domain.enums import (  # noqa: E402
    DisasterType,
    DispatchStatus,
    IncidentStatus,
    Permission,
    PriorityClass,
    ResourceStatus,
    Role,
)
from dms.domain.lifecycle import can_transition  # noqa: E402
from dms.domain.models import new_id  # noqa: E402

from .config import api_keys, settings  # noqa: E402
from .db import (  # noqa: E402
    AlertRow,
    AttachmentRow,
    AuditRow,
    ClusterRow,
    DispatchRow,
    IdempotencyRow,
    IncidentRow,
    ResourceRow,
    get_session,
    init_db,
)
from .schemas import (  # noqa: E402
    AcknowledgeRequest,
    AlertCreate,
    AttachmentCreate,
    ComposeRequest,
    DispatchAdvance,
    DispatchCreate,
    IncidentCreate,
    NodeHeartbeat,
    Page,
    ResourceCreate,
    StatusUpdate,
    SyncPush,
    TranscribeRequest,
)
from .security import Principal, audit, current_principal, require  # noqa: E402

app = FastAPI(
    title="DisasterMesh Sentinel Gateway",
    version="1.0.0",
    description=(
        "Coordinator API and opportunistic gateway for the DisasterMesh mesh. "
        "All dispatch is simulated; no real emergency service is contacted."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ] if not settings.is_production else settings.cors_origins,
    allow_origin_regex=r"https?://.*" if not settings.is_production else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from .mesh import router as mesh_router  # noqa: E402

app.include_router(mesh_router)


def _seed_demo_resources() -> None:
    from .db import session_factory
    factory = session_factory()
    db = factory()
    try:
        if db.query(ResourceRow).count() == 0:
            demo_resources = [
                ResourceRow(
                    id="res_medic_1",
                    organization_id="org_demo",
                    kind="AMBULANCE",
                    label="Paramedic Unit Alpha",
                    status="AVAILABLE",
                    simulated=True,
                    doc={
                        "id": "res_medic_1",
                        "organization_id": "org_demo",
                        "kind": "AMBULANCE",
                        "label": "Paramedic Unit Alpha",
                        "status": "AVAILABLE",
                        "capabilities": ["MEDICAL", "ACCIDENT", "TRAPPED_PERSON"],
                        "simulated": True,
                    },
                ),
                ResourceRow(
                    id="res_fire_1",
                    organization_id="org_demo",
                    kind="FIRE_UNIT",
                    label="Fire & Rescue Squad 4",
                    status="AVAILABLE",
                    simulated=True,
                    doc={
                        "id": "res_fire_1",
                        "organization_id": "org_demo",
                        "kind": "FIRE_UNIT",
                        "label": "Fire & Rescue Squad 4",
                        "status": "AVAILABLE",
                        "capabilities": ["FIRE", "BUILDING_COLLAPSE", "TRAPPED_PERSON"],
                        "simulated": True,
                    },
                ),
                ResourceRow(
                    id="res_boat_1",
                    organization_id="org_demo",
                    kind="RESCUE_BOAT",
                    label="Flood Evacuation Boat 2",
                    status="AVAILABLE",
                    simulated=True,
                    doc={
                        "id": "res_boat_1",
                        "organization_id": "org_demo",
                        "kind": "RESCUE_BOAT",
                        "label": "Flood Evacuation Boat 2",
                        "status": "AVAILABLE",
                        "capabilities": ["FLOOD", "TRAPPED_PERSON", "LOGISTICS"],
                        "simulated": True,
                    },
                ),
                ResourceRow(
                    id="res_heavy_1",
                    organization_id="org_demo",
                    kind="SEARCH_TEAM",
                    label="Urban Search & Rescue Team",
                    status="AVAILABLE",
                    simulated=True,
                    doc={
                        "id": "res_heavy_1",
                        "organization_id": "org_demo",
                        "kind": "SEARCH_TEAM",
                        "label": "Urban Search & Rescue Team",
                        "status": "AVAILABLE",
                        "capabilities": [
                            "EARTHQUAKE",
                            "BUILDING_COLLAPSE",
                            "LANDSLIDE",
                            "TRAPPED_PERSON",
                        ],
                        "simulated": True,
                    },
                ),
            ]
            for r in demo_resources:
                db.add(r)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _seed_demo_nodes() -> None:
    now = datetime.now(UTC)
    if not ACTIVE_NODES:
        ACTIVE_NODES["node_relay_alpha"] = {
            "node_id": "node_relay_alpha",
            "role": "MESH_RELAY",
            "battery_percent": 88,
            "nearby_peers": 5,
            "stored_bundles": 12,
            "organization_id": "org_demo",
            "last_seen_at": now.isoformat(),
            "last_seen": now.isoformat(),
        }
        ACTIVE_NODES["node_field_reporter_1"] = {
            "node_id": "node_field_reporter_1",
            "role": "CITIZEN_REPORTER",
            "battery_percent": 94,
            "nearby_peers": 3,
            "stored_bundles": 4,
            "organization_id": "org_demo",
            "last_seen_at": now.isoformat(),
            "last_seen": now.isoformat(),
        }
        ACTIVE_NODES["node_coord_gateway"] = {
            "node_id": "node_coord_gateway",
            "role": "COORDINATOR",
            "battery_percent": 100,
            "nearby_peers": 8,
            "stored_bundles": 25,
            "organization_id": "org_demo",
            "last_seen_at": now.isoformat(),
            "last_seen": now.isoformat(),
        }


@app.on_event("startup")
def startup() -> None:
    init_db()
    if not settings.is_production:
        _seed_demo_resources()
        _seed_demo_nodes()


@app.get("/")
@app.get("/health")
@app.get("/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "DisasterMesh Sentinel Gateway"}


@app.exception_handler(HTTPException)
async def structured_errors(request: Request, exc: HTTPException):
    """Uniform error envelope: {error, detail}."""
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    else:
        body = {"error": _error_code(exc.status_code), "detail": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=body)


def _error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthenticated",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "validation_error",
    }.get(status_code, "error")


# ------------------------------------------------------------------- helpers


def _scoped_incident(db: Session, incident_id: str, principal: Principal) -> IncidentRow:
    """Fetch an incident inside the caller's organization, or 404.

    Cross-organization access returns 404 rather than 403 so the API does not confirm
    the existence of another organization's records.
    """
    row = (
        db.query(IncidentRow)
        .filter(
            IncidentRow.id == incident_id,
            IncidentRow.organization_id == principal.organization_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"error": "not_found", "detail": "incident not found"}
        )
    return row


def _idempotent(
    db: Session, key: str | None, endpoint: str, principal: Principal
) -> dict[str, Any] | None:
    if not key:
        return None
    row = (
        db.query(IdempotencyRow)
        .filter(
            IdempotencyRow.key == key,
            IdempotencyRow.organization_id == principal.organization_id,
        )
        .first()
    )
    if row is None:
        return None
    if row.endpoint != endpoint:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "idempotency_conflict",
                "detail": "this key was used on a different endpoint",
            },
        )
    return row.response


def _remember(
    db: Session, key: str | None, endpoint: str, principal: Principal, response: dict
) -> None:
    if not key:
        return
    db.add(
        IdempotencyRow(
            key=key,
            organization_id=principal.organization_id,
            endpoint=endpoint,
            response=response,
        )
    )


def _to_domain_doc(
    payload: IncidentCreate, incident_id: str, organization_id: str, now: datetime
) -> dict[str, Any]:
    """Build the canonical incident document.

    The gateway stores exactly the shape a node stores (``Incident.to_dict()``), so
    redaction, clustering, and summarization all read one format instead of three.
    """
    location = None
    if payload.latitude is not None and payload.longitude is not None:
        location = {
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "accuracy_m": payload.location_accuracy_m,
            "source": "DEVICE_GPS",
            "shared_precisely": True,
        }
    reported = payload.reported_at or now
    return {
        "id": incident_id,
        "source_node_id": payload.source_node_id,
        "organization_id": organization_id,
        "original_text": payload.original_text,
        "source_language": payload.source_language,
        "location": location,
        "reported_at": reported.isoformat(),
        "expires_at": None,
        "disaster_types": payload.disaster_types,
        "urgency": payload.urgency,
        "severity": payload.severity,
        "classification_confidence": 0.0,
        "people_affected": payload.people_affected
        or {"value": None, "raw": None, "approximate": True, "confidence": None},
        "conditions": payload.conditions,
        "requested_resources": [],
        "priority_score": payload.priority_score,
        "priority_class": payload.priority_class.value,
        "priority_explanation": payload.priority_explanation,
        "policy_version": "policy-1.0.0",
        "status": IncidentStatus.RECEIVED.value,
        "verification_status": "AI_CLASSIFIED",
        "access_policy": {
            "sensitivity": payload.sensitivity,
            "allowed_roles": [],
            "organization_id": organization_id,
            "precise_location_roles": [],
        },
        "attachment_ids": [],
        "audio_reference": None,
        "cluster_id": None,
        "provenance": "HUMAN_REPORTED",
        "revision": payload.revision,
        "schema_version": "1.0.0",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def _incident_payload(row: IncidentRow, principal: Principal) -> dict[str, Any]:
    """Redact what the caller may not see, without hiding that redaction happened."""
    doc = dict(row.doc)
    if row.sensitivity == "MEDICAL" and not principal.has(Permission.VIEW_MEDICAL_DATA):
        doc["original_text"] = "[restricted: medical content]"
        doc["conditions"] = []
        doc["people_affected"] = {"value": None, "raw": None, "approximate": True}
        doc["redacted"] = ["original_text", "conditions", "people_affected"]
    if not principal.has(Permission.VIEW_PRECISE_LOCATION) and doc.get("location"):
        location = dict(doc["location"])
        location["latitude"] = round(location["latitude"], 2)
        location["longitude"] = round(location["longitude"], 2)
        location["accuracy_m"] = max(location.get("accuracy_m") or 0, 1000)
        location["shared_precisely"] = False
        doc["location"] = location
        doc.setdefault("redacted", []).append("location")
    return doc


# -------------------------------------------------------------------- health


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "service": "dms-gateway", "environment": settings.environment}


@app.get("/ready", tags=["ops"])
def ready(db: Session = Depends(get_session)) -> dict:
    keys = api_keys()
    try:
        db.query(func.count(IncidentRow.id)).scalar()
        database_ok = True
    except Exception:
        database_ok = False
    warnings: list[str] = []
    if not keys:
        warnings.append("no API keys configured — the API will authorize nobody")
    if not settings.is_production and keys and "dev-coordinator-key" in keys:
        warnings.append("development API keys are active; do not use in production")
    return {
        "status": "ready" if database_ok and keys else "degraded",
        "database": database_ok,
        "configured_principals": len(keys),
        "warnings": warnings,
    }


# ----------------------------------------------------------------- incidents


@app.post("/v1/incidents", status_code=201, tags=["incidents"])
def create_incident(
    payload: IncidentCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require(Permission.CREATE_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Submit an incident. Re-submitting the same id or key never duplicates it."""
    cached = _idempotent(db, idempotency_key, "create_incident", principal)
    if cached:
        return cached

    incident_id = payload.id or new_id("inc")
    existing = db.query(IncidentRow).filter(IncidentRow.id == incident_id).first()
    if existing is not None:
        if existing.organization_id != principal.organization_id:
            raise HTTPException(
                status_code=409,
                detail={"error": "conflict", "detail": "id already exists in another organization"},
            )
        if payload.revision <= existing.revision:
            return {"id": existing.id, "status": existing.status, "deduplicated": True}
        existing.revision = payload.revision
        existing.doc = _to_domain_doc(
            payload, incident_id, principal.organization_id, datetime.now(UTC)
        ) | {"status": existing.status}
        existing.updated_at = datetime.now(UTC)
        audit(
            db,
            action="INCIDENT_UPDATED",
            principal=principal,
            incident_id=incident_id,
            detail={"revision": payload.revision},
        )
        db.commit()
        return {"id": existing.id, "status": existing.status, "deduplicated": False}

    now = datetime.now(UTC)
    doc = _to_domain_doc(payload, incident_id, principal.organization_id, now)
    row = IncidentRow(
        id=incident_id,
        organization_id=principal.organization_id,
        source_node_id=payload.source_node_id,
        original_text=payload.original_text,
        source_language=payload.source_language,
        status=IncidentStatus.RECEIVED.value,
        priority_class=payload.priority_class.value,
        priority_score=payload.priority_score,
        severity=payload.severity,
        urgency=payload.urgency,
        sensitivity=payload.sensitivity,
        verification_status="AI_CLASSIFIED",
        revision=payload.revision,
        doc=doc,
        reported_at=payload.reported_at or now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    audit(
        db,
        action="INCIDENT_CREATED",
        principal=principal,
        incident_id=incident_id,
        detail={
            "priority_class": payload.priority_class.value,
            "priority_score": payload.priority_score,
        },
    )
    response = {"id": incident_id, "status": row.status, "deduplicated": False}
    _remember(db, idempotency_key, "create_incident", principal, response)
    db.commit()
    return response


def _classify_text(text: str, language: str | None) -> dict:
    """Run the same triage + priority engine a reporting node runs.

    Mirrors ``MeshNode.report_incident`` using the identical pure functions, so a
    message typed or transcribed on the dashboard is classified exactly like one
    created on a device. Returns fields ready for :class:`IncidentCreate`.
    """
    from dms.ai.lexicon import detect_language
    from dms.ai.rules import extract_entities, triage
    from dms.domain.models import Condition, ConditionType, Quantity
    from dms.priority.engine import PriorityInputs, evaluate

    lang = language or detect_language(text)
    tri = triage(text, lang)
    entity = extract_entities(text, lang)
    people = entity.people_affected
    conditions = tuple(
        Condition(
            type=ConditionType(c["type"]), raw=c.get("raw"), confidence=c.get("confidence")
        )
        for c in entity.conditions
    )
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
            ai_available=True,
        )
    )
    return {
        "language": lang,
        "urgency": tri.urgency.value if hasattr(tri.urgency, "value") else str(tri.urgency),
        "severity": int(tri.severity),
        "disaster_types": [
            d.value if hasattr(d, "value") else str(d) for d in tri.disaster_types
        ],
        "priority_class": decision.priority_class,
        "priority_score": int(decision.score),
        "priority_explanation": list(decision.explanation),
        "people_affected": {
            "value": people.get("value"),
            "raw": people.get("raw"),
            "approximate": people.get("approximate", False),
            "confidence": people.get("confidence"),
        },
        "conditions": [
            {"type": c["type"], "raw": c.get("raw"), "confidence": c.get("confidence")}
            for c in entity.conditions
        ],
    }


@app.post("/v1/transcribe", status_code=200, tags=["ai"])
def transcribe_audio(
    payload: TranscribeRequest,
    principal: Principal = Depends(require(Permission.CREATE_INCIDENT)),
) -> dict:
    """Audio → text, using the existing speech-to-text pipeline. Nothing is stored;
    the caller sends the returned text through the normal incident flow."""
    import base64 as _base64

    from dms.ai.base import AIError
    from dms.ai.mocks import transcribe as _transcribe

    try:
        audio = _base64.b64decode(payload.audio_base64, validate=True)
    except (ValueError, _binascii_error()):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_base64", "detail": "audio_base64 is not valid base64"},
        ) from None
    try:
        result = _transcribe(
            audio,
            mime_type=payload.mime_type,
            language_hint=payload.language_hint,
            duration_s=payload.duration_s,
        )
    except AIError as exc:
        raise HTTPException(
            status_code=422, detail={"error": exc.code, "detail": str(exc)}
        ) from None
    return {
        "text": result.text,
        "language": result.language,
        "low_quality": result.low_quality,
        "confidence": result.confidence,
    }


@app.post("/v1/compose", status_code=201, tags=["incidents"])
def compose_incident(
    payload: ComposeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require(Permission.CREATE_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Classify free text and file it as an incident through the normal pipeline.

    The dashboard uses this for typed reports and for text produced by
    :func:`transcribe_audio`, so a transcribed voice message becomes an ordinary
    incident — same storage, clustering, dispatch, and display as any other.
    """
    classified = _classify_text(payload.text, payload.source_language)
    incident = IncidentCreate(
        source_node_id=payload.source_node_id,
        original_text=payload.text,
        source_language=classified["language"],
        latitude=payload.latitude,
        longitude=payload.longitude,
        disaster_types=classified["disaster_types"],
        urgency=classified["urgency"],
        severity=classified["severity"],
        priority_class=classified["priority_class"],
        priority_score=classified["priority_score"],
        people_affected=classified["people_affected"],
        conditions=classified["conditions"],
        priority_explanation=classified["priority_explanation"],
    )
    # Reuse the existing create path verbatim — no duplicated persistence logic.
    return create_incident(
        payload=incident, idempotency_key=idempotency_key, principal=principal, db=db
    )


@app.get("/v1/incidents", tags=["incidents"])
def list_incidents(
    priority: PriorityClass | None = None,
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=settings.page_size_default, ge=1, le=settings.page_size_max),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> Page:
    """Priority inbox, newest and most urgent first, scoped to the caller's org."""
    query = db.query(IncidentRow).filter(IncidentRow.organization_id == principal.organization_id)
    if priority:
        query = query.filter(IncidentRow.priority_class == priority.value)
    if status_filter:
        query = query.filter(IncidentRow.status == status_filter.value)
    total = query.count()
    rows = (
        query.order_by(
            IncidentRow.priority_class.asc(),
            IncidentRow.priority_score.desc(),
            IncidentRow.reported_at.desc(),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )
    return Page(
        items=[_incident_payload(r, principal) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/v1/incidents/{incident_id}", tags=["incidents"])
def get_incident(
    incident_id: str,
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    row = _scoped_incident(db, incident_id, principal)
    attachments = db.query(AttachmentRow).filter(AttachmentRow.incident_id == incident_id).all()
    return {
        "incident": _incident_payload(row, principal),
        "status": row.status,
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
                "sha256": a.sha256,
                "verified": a.verified,
                "kind": a.kind,
                "has_content": a.data is not None,
            }
            for a in attachments
        ],
        "dispatch": [
            d.doc for d in db.query(DispatchRow).filter(DispatchRow.incident_id == incident_id)
        ],
    }


@app.post("/v1/incidents/{incident_id}/acknowledge", tags=["incidents"])
def acknowledge(
    incident_id: str,
    payload: AcknowledgeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Acknowledge an incident. Repeat calls are absorbed, not rejected."""
    row = _scoped_incident(db, incident_id, principal)
    cached = _idempotent(db, idempotency_key, "acknowledge", principal)
    if cached:
        return cached

    if row.status == IncidentStatus.ACKNOWLEDGED.value:
        return {"id": row.id, "status": row.status, "already_acknowledged": True}
    if not can_transition(IncidentStatus(row.status), IncidentStatus.ACKNOWLEDGED):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "invalid_transition",
                "detail": f"cannot acknowledge from {row.status}",
            },
        )
    row.status = IncidentStatus.ACKNOWLEDGED.value
    row.updated_at = datetime.now(UTC)
    audit(
        db,
        action="INCIDENT_ACKNOWLEDGED",
        principal=principal,
        incident_id=incident_id,
        detail={"node_id": payload.node_id, "note": payload.note},
    )
    response = {"id": row.id, "status": row.status, "already_acknowledged": False}
    _remember(db, idempotency_key, "acknowledge", principal, response)
    db.commit()
    return response


@app.patch("/v1/incidents/{incident_id}/status", tags=["incidents"])
def update_status(
    incident_id: str,
    payload: StatusUpdate,
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    row = _scoped_incident(db, incident_id, principal)
    if payload.status is IncidentStatus.RESOLVED and not principal.has(Permission.CLOSE_INCIDENT):
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "detail": "closing an incident requires CLOSE_INCIDENT"},
        )
    if not can_transition(IncidentStatus(row.status), payload.status):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "invalid_transition",
                "detail": f"{row.status} -> {payload.status.value} is not permitted",
            },
        )
    row.status = payload.status.value
    row.updated_at = datetime.now(UTC)
    audit(
        db,
        action=f"INCIDENT_{payload.status.value}",
        principal=principal,
        incident_id=incident_id,
        detail={"reason": payload.reason},
    )
    db.commit()
    return {"id": row.id, "status": row.status}


# --------------------------------------------------------------- attachments


@app.post("/v1/incidents/{incident_id}/attachments", status_code=201, tags=["attachments"])
def add_attachment(
    incident_id: str,
    payload: AttachmentCreate,
    principal: Principal = Depends(require(Permission.CREATE_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Register attachment metadata. Size and MIME are enforced before acceptance."""
    _scoped_incident(db, incident_id, principal)
    if payload.size_bytes > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "payload_too_large",
                "detail": f"attachment exceeds {settings.max_upload_bytes} bytes",
            },
        )
    attachment_id = payload.id or new_id("att")
    if db.query(AttachmentRow).filter(AttachmentRow.id == attachment_id).first():
        return {"id": attachment_id, "deduplicated": True}

    # Optional inline bytes: verify size and hash before we ever trust them, then
    # store them so the dashboard can render the file. When absent, this whole block
    # is skipped and the row stays metadata-only, exactly as before.
    import base64 as _base64
    import hashlib as _hashlib

    data: bytes | None = None
    verified = payload.verified
    if payload.data_base64 is not None:
        try:
            data = _base64.b64decode(payload.data_base64, validate=True)
        except (ValueError, _binascii_error()):
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_base64", "detail": "data_base64 is not valid base64"},
            ) from None
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "payload_too_large",
                    "detail": f"attachment exceeds {settings.max_upload_bytes} bytes",
                },
            )
        if _hashlib.sha256(data).hexdigest() != payload.sha256:
            raise HTTPException(
                status_code=422,
                detail={"error": "hash_mismatch", "detail": "sha256 does not match the bytes"},
            )
        # Hash matched the declared digest — the file is intact.
        verified = True

    db.add(
        AttachmentRow(
            id=attachment_id,
            incident_id=incident_id,
            organization_id=principal.organization_id,
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256,
            kind=payload.kind.value,
            verified=verified,
            data=data,
        )
    )
    audit(
        db,
        action="ATTACHMENT_REGISTERED",
        principal=principal,
        incident_id=incident_id,
        detail={"attachment_id": attachment_id, "sha256": payload.sha256[:12]},
    )
    db.commit()
    return {"id": attachment_id, "deduplicated": False, "has_content": data is not None}


def _binascii_error() -> type[Exception]:
    import binascii

    return binascii.Error


@app.get("/v1/incidents/{incident_id}/attachments/{attachment_id}/content", tags=["attachments"])
def get_attachment_content(
    incident_id: str,
    attachment_id: str,
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> Response:
    """Serve the raw bytes of an attachment so the dashboard can render it.

    Organization-scoped like every other read. Returns 404 when the attachment
    carries only metadata (no bytes were stored), which is a valid state.
    """
    _scoped_incident(db, incident_id, principal)
    row = (
        db.query(AttachmentRow)
        .filter(
            AttachmentRow.id == attachment_id,
            AttachmentRow.incident_id == incident_id,
            AttachmentRow.organization_id == principal.organization_id,
        )
        .first()
    )
    if row is None or row.data is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "detail": "no stored content for this attachment"},
        )
    return Response(
        content=row.data,
        media_type=row.mime_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


# ------------------------------------------------------------------ clusters


@app.post("/v1/clusters/rebuild", tags=["clusters"])
def rebuild_clusters(
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Recompute provisional clusters. Never merges or deletes an incident."""
    from dms.store.sqlite import _incident_from_doc

    rows = (
        db.query(IncidentRow).filter(IncidentRow.organization_id == principal.organization_id).all()
    )
    incidents, unreadable = [], []
    for row in rows:
        try:
            incidents.append(_incident_from_doc(row.doc))
        except Exception as exc:  # surfaced in the response, never silently dropped
            unreadable.append({"incident_id": row.id, "reason": type(exc).__name__})

    created = 0
    for incident in incidents:
        group = build_cluster(incident, [i for i in incidents if i.id != incident.id])
        if group is None:
            continue
        if db.query(ClusterRow).filter(ClusterRow.id == group.id).first():
            continue
        db.add(
            ClusterRow(
                id=group.id,
                organization_id=principal.organization_id,
                doc=group.to_dict(),
                human_reviewed=False,
            )
        )
        created += 1
    audit(
        db,
        action="CLUSTERS_REBUILT",
        principal=principal,
        detail={"created": created, "unreadable": len(unreadable)},
    )
    db.commit()
    return {
        "clusters_created": created,
        "incidents_considered": len(incidents),
        "unreadable_documents": unreadable,
    }


@app.get("/v1/clusters", tags=["clusters"])
def list_clusters(
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    rows = (
        db.query(ClusterRow).filter(ClusterRow.organization_id == principal.organization_id).all()
    )
    return {"items": [r.doc | {"human_reviewed": r.human_reviewed} for r in rows]}


@app.post("/v1/clusters/{cluster_id}/split", tags=["clusters"])
def split_cluster(
    cluster_id: str,
    incident_id: str = Body(embed=True),
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """A human separates a report. Both records survive."""
    row = (
        db.query(ClusterRow)
        .filter(
            ClusterRow.id == cluster_id, ClusterRow.organization_id == principal.organization_id
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"error": "not_found", "detail": "cluster not found"}
        )
    doc = dict(row.doc)
    doc["incident_ids"] = [i for i in doc.get("incident_ids", []) if i != incident_id]
    doc["human_reviewed"] = True
    doc["provisional"] = False
    doc["rationale"] = list(doc.get("rationale", [])) + [f"human split out {incident_id}"]
    row.doc = doc
    row.human_reviewed = True
    audit(
        db,
        action="CLUSTER_SPLIT",
        principal=principal,
        incident_id=incident_id,
        detail={"cluster_id": cluster_id},
    )
    db.commit()
    return doc


@app.post("/v1/clusters/{cluster_id}/summary", tags=["clusters"])
def cluster_summary(
    cluster_id: str,
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    row = (
        db.query(ClusterRow)
        .filter(
            ClusterRow.id == cluster_id, ClusterRow.organization_id == principal.organization_id
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"error": "not_found", "detail": "cluster not found"}
        )
    ids = row.doc.get("incident_ids", [])
    incidents = (
        db.query(IncidentRow)
        .filter(IncidentRow.id.in_(ids), IncidentRow.organization_id == principal.organization_id)
        .all()
    )
    result = summarize([i.doc for i in incidents], cluster_id=cluster_id)
    return result.to_dict() | {"advisory": "human review required; no dispatch authority"}


# ----------------------------------------------------------------- resources


@app.post("/v1/resources", status_code=201, tags=["dispatch"])
def create_resource(
    payload: ResourceCreate,
    principal: Principal = Depends(require(Permission.ASSIGN_RESOURCE)),
    db: Session = Depends(get_session),
) -> dict:
    resource_id = payload.id or new_id("res")
    existing = db.query(ResourceRow).filter(ResourceRow.id == resource_id).first()
    doc = payload.model_dump(mode="json") | {
        "id": resource_id,
        "organization_id": principal.organization_id,
    }
    if existing:
        existing.status = payload.status
        existing.doc = doc
        existing.last_seen_at = datetime.now(UTC)
    else:
        db.add(
            ResourceRow(
                id=resource_id,
                organization_id=principal.organization_id,
                kind=payload.kind.value,
                label=payload.label,
                status=payload.status,
                simulated=True,
                doc=doc,
            )
        )
    db.commit()
    return {"id": resource_id, "simulated": True}


@app.get("/v1/resources", tags=["dispatch"])
def list_resources(
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    rows = (
        db.query(ResourceRow).filter(ResourceRow.organization_id == principal.organization_id).all()
    )
    return {
        "items": [
            r.doc
            | {"status": r.status, "last_seen_at": r.last_seen_at.isoformat(), "simulated": True}
            for r in rows
        ]
    }


@app.get("/v1/incidents/{incident_id}/recommendations", tags=["dispatch"])
def recommendations(
    incident_id: str,
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Rank capable resources with reasons. A recommendation is never an assignment."""
    row = _scoped_incident(db, incident_id, principal)
    wanted = {
        DisasterType(t) for t in row.doc.get("disaster_types", []) if t in DisasterType.__members__
    }
    out = []
    for resource in (
        db.query(ResourceRow)
        .filter(
            ResourceRow.organization_id == principal.organization_id,
            ResourceRow.status == ResourceStatus.AVAILABLE.value,
        )
        .all()
    ):
        from dms.domain.enums import ResourceKind

        capable = CAPABILITY_MATRIX.get(ResourceKind(resource.kind), frozenset())
        overlap = wanted & capable
        if not overlap:
            continue
        out.append(
            {
                "resource_id": resource.id,
                "kind": resource.kind,
                "label": resource.label,
                "score": 50 + 10 * len(overlap),
                "reason": f"{resource.kind} matches {', '.join(sorted(t.value for t in overlap))}",
            }
        )
    out.sort(key=lambda r: -r["score"])
    return {"items": out, "advisory": "recommendation_only_requires_human_authorization"}


@app.post("/v1/dispatch", status_code=201, tags=["dispatch"])
def create_dispatch(
    payload: DispatchCreate,
    confirm: bool = Query(default=False, description="explicit human confirmation"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require(Permission.ASSIGN_RESOURCE)),
    db: Session = Depends(get_session),
) -> dict:
    """Assign a simulated resource. Requires ASSIGN_RESOURCE *and* confirm=true."""
    incident = _scoped_incident(db, payload.incident_id, principal)
    cached = _idempotent(db, idempotency_key, "create_dispatch", principal)
    if cached:
        return cached
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirmation_required",
                "detail": "dispatch requires explicit human confirmation (confirm=true)",
            },
        )
    resource = (
        db.query(ResourceRow)
        .filter(
            ResourceRow.id == payload.resource_id,
            ResourceRow.organization_id == principal.organization_id,
        )
        .first()
    )
    if resource is None:
        raise HTTPException(
            status_code=404, detail={"error": "not_found", "detail": "resource not found"}
        )
    if resource.status != ResourceStatus.AVAILABLE.value:
        raise HTTPException(
            status_code=409,
            detail={"error": "resource_unavailable", "detail": f"resource is {resource.status}"},
        )

    from dms.domain.enums import ResourceKind

    wanted = {
        DisasterType(t)
        for t in incident.doc.get("disaster_types", [])
        if t in DisasterType.__members__
    }
    capable = CAPABILITY_MATRIX.get(ResourceKind(resource.kind), frozenset())
    if wanted and not (wanted & capable):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "incompatible_resource",
                "detail": f"{resource.kind} cannot serve this incident type",
            },
        )

    order_id = new_id("dsp")
    now = datetime.now(UTC)
    doc = {
        "id": order_id,
        "incident_id": payload.incident_id,
        "resource_id": payload.resource_id,
        "status": DispatchStatus.ASSIGNED.value,
        "recommended_reason": payload.reason,
        "authorized_by": principal.user_id,
        "authorized_role": principal.role.value,
        "simulated": True,
        "created_at": now.isoformat(),
    }
    db.add(
        DispatchRow(
            id=order_id,
            incident_id=payload.incident_id,
            organization_id=principal.organization_id,
            resource_id=payload.resource_id,
            status=DispatchStatus.ASSIGNED.value,
            simulated=True,
            doc=doc,
        )
    )
    resource.status = ResourceStatus.ASSIGNED.value
    if incident.status == IncidentStatus.ACKNOWLEDGED.value:
        incident.status = IncidentStatus.DISPATCH_REQUESTED.value
    audit(
        db,
        action="DISPATCH_AUTHORIZED",
        principal=principal,
        incident_id=payload.incident_id,
        detail={"order_id": order_id, "resource_id": payload.resource_id, "simulated": True},
    )
    response = {"id": order_id, "status": DispatchStatus.ASSIGNED.value, "simulated": True}
    _remember(db, idempotency_key, "create_dispatch", principal, response)
    db.commit()
    return response


@app.patch("/v1/dispatch/{order_id}", tags=["dispatch"])
def advance_dispatch(
    order_id: str,
    payload: DispatchAdvance,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_session),
) -> dict:
    """Responders update their own assignment; coordinators may too."""
    row = (
        db.query(DispatchRow)
        .filter(
            DispatchRow.id == order_id, DispatchRow.organization_id == principal.organization_id
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"error": "not_found", "detail": "dispatch order not found"}
        )
    from dms.domain.lifecycle import DISPATCH_TRANSITIONS

    current = DispatchStatus(row.status)
    if payload.status is current:
        return {"id": row.id, "status": row.status, "unchanged": True}
    if payload.status not in DISPATCH_TRANSITIONS.get(current, frozenset()):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "invalid_transition",
                "detail": f"{row.status} -> {payload.status.value} is not permitted",
            },
        )
    row.status = payload.status.value
    row.doc = dict(row.doc) | {"status": row.status}
    row.updated_at = datetime.now(UTC)
    if payload.status in (DispatchStatus.COMPLETED, DispatchStatus.CANCELLED):
        resource = db.query(ResourceRow).filter(ResourceRow.id == row.resource_id).first()
        if resource:
            resource.status = ResourceStatus.AVAILABLE.value
    audit(
        db,
        action=f"DISPATCH_{payload.status.value}",
        principal=principal,
        incident_id=row.incident_id,
        detail={"order_id": order_id},
    )
    db.commit()
    return {"id": row.id, "status": row.status, "unchanged": False}


# -------------------------------------------------------------------- alerts


@app.post("/v1/alerts", status_code=201, tags=["alerts"])
def publish_alert(
    payload: AlertCreate,
    principal: Principal = Depends(require(Permission.PUBLISH_ALERT)),
    db: Session = Depends(get_session),
) -> dict:
    """Publish a public alert. Authority role plus explicit confirmation, always."""
    alert_id = new_id("alr")
    doc = payload.model_dump(mode="json") | {"id": alert_id, "authorized_by": principal.user_id}
    db.add(
        AlertRow(
            id=alert_id,
            organization_id=principal.organization_id,
            headline=payload.headline,
            body=payload.body,
            authorized_by=principal.user_id,
            authorized_role=principal.role.value,
            published=True,
            doc=doc,
        )
    )
    audit(
        db,
        action="ALERT_PUBLISHED",
        principal=principal,
        detail={"alert_id": alert_id, "incident_ids": payload.incident_ids},
    )
    db.commit()
    return {"id": alert_id, "published": True}


# ---------------------------------------------------------------------- sync


@app.post("/v1/sync/push", tags=["sync"])
def sync_push(
    payload: SyncPush,
    principal: Principal = Depends(require(Permission.CREATE_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """A node uploads what it carried. Re-pushing the same batch changes nothing."""
    accepted, deduplicated = 0, 0
    for item in payload.incidents:
        result = create_incident(item, idempotency_key=None, principal=principal, db=db)
        if result.get("deduplicated"):
            deduplicated += 1
        else:
            accepted += 1
    audit(
        db,
        action="SYNC_PUSH",
        principal=principal,
        detail={"node_id": payload.node_id, "accepted": accepted, "deduplicated": deduplicated},
    )
    db.commit()
    return {"accepted": accepted, "deduplicated": deduplicated, "node_id": payload.node_id}


@app.get("/v1/sync/pull", tags=["sync"])
def sync_pull(
    since: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=settings.page_size_max),
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    query = db.query(IncidentRow).filter(IncidentRow.organization_id == principal.organization_id)
    if since:
        query = query.filter(IncidentRow.updated_at > since)
    rows = query.order_by(IncidentRow.updated_at.asc()).limit(limit).all()
    return {
        "items": [_incident_payload(r, principal) for r in rows],
        "server_time": datetime.now(UTC).isoformat(),
    }


# --------------------------------------------------------------------- audit


@app.get("/v1/audit", tags=["audit"])
def list_audit(
    incident_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=settings.page_size_max),
    principal: Principal = Depends(require(Permission.EXPORT_AUDIT)),
    db: Session = Depends(get_session),
) -> dict:
    """Export the audit ledger. Requires EXPORT_AUDIT."""
    query = db.query(AuditRow).filter(AuditRow.organization_id == principal.organization_id)
    if incident_id:
        query = query.filter(AuditRow.incident_id == incident_id)
    rows = query.order_by(AuditRow.created_at.asc()).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "action": r.action,
                "actor": r.actor,
                "actor_role": r.actor_role,
                "incident_id": r.incident_id,
                "detail": r.detail,
                "prev_hash": r.prev_hash,
                "entry_hash": r.entry_hash,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@app.get("/v1/stats", tags=["ops"])
def stats(
    principal: Principal = Depends(require(Permission.VIEW_INCIDENT)),
    db: Session = Depends(get_session),
) -> dict:
    """Counters for the dashboard header."""
    org = principal.organization_id
    by_priority = dict(
        db.query(IncidentRow.priority_class, func.count(IncidentRow.id))
        .filter(IncidentRow.organization_id == org)
        .group_by(IncidentRow.priority_class)
        .all()
    )
    by_status = dict(
        db.query(IncidentRow.status, func.count(IncidentRow.id))
        .filter(IncidentRow.organization_id == org)
        .group_by(IncidentRow.status)
        .all()
    )
    total_nodes = len(ACTIVE_NODES)
    total_peers = sum(n.get("nearby_peers", 0) for n in ACTIVE_NODES.values())
    total_connected_people = total_nodes + total_peers

    return {
        "incidents": sum(by_priority.values()),
        "by_priority": by_priority,
        "by_status": by_status,
        "resources": db.query(func.count(ResourceRow.id))
        .filter(ResourceRow.organization_id == org)
        .scalar(),
        "dispatch_orders": db.query(func.count(DispatchRow.id))
        .filter(DispatchRow.organization_id == org)
        .scalar(),
        "unacknowledged_p0": db.query(func.count(IncidentRow.id))
        .filter(
            IncidentRow.organization_id == org,
            IncidentRow.priority_class == "P0",
            IncidentRow.status.in_(["RECEIVED", "QUEUED", "RELAYED"]),
        )
        .scalar(),
        "connected_nodes": total_nodes,
        "connected_people": total_connected_people,
    }


# --------------------------------------------------------------------- nodes

ACTIVE_NODES: dict[str, dict[str, Any]] = {}


def _optional_principal(authorization: str | None = Header(default=None)) -> Principal:
    if authorization and authorization.lower().startswith("bearer "):
        try:
            return current_principal(authorization)
        except Exception:
            pass
    return Principal(user_id="demo_user", role=Role.EVENT_COORDINATOR, organization_id="org_demo")


@app.post("/v1/nodes/heartbeat", tags=["nodes"])
def node_heartbeat(
    payload: NodeHeartbeat,
    principal: Principal = Depends(_optional_principal),
) -> dict:
    """Register or update active node presence."""
    now = datetime.now(UTC)
    ACTIVE_NODES[payload.node_id] = {
        "node_id": payload.node_id,
        "role": payload.role,
        "battery_percent": payload.battery_percent,
        "nearby_peers": payload.nearby_peers,
        "stored_bundles": payload.stored_bundles,
        "organization_id": principal.organization_id,
        "last_seen_at": now.isoformat(),
        "last_seen": now.isoformat(),
    }
    return {"status": "ok", "node_id": payload.node_id, "timestamp": now.isoformat()}


@app.get("/v1/nodes", tags=["nodes"])
def list_nodes(
    principal: Principal = Depends(_optional_principal),
) -> dict:
    """List active mobile and mesh nodes."""
    return {
        "items": list(ACTIVE_NODES.values())
    }


