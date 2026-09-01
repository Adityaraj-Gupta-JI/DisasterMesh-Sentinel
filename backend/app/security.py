"""Authentication, authorization, and the audit ledger for the gateway."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from dms.domain.enums import Permission, Role
from dms.domain.models import ROLE_PERMISSIONS, new_id
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import api_keys
from .db import AuditRow


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Every query is scoped by ``organization_id``."""

    user_id: str
    role: Role
    organization_id: str

    def has(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, frozenset())


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Bearer-token auth. Unknown or missing credentials are rejected, never defaulted."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "detail": "bearer token required"},
        )
    token = authorization.split(" ", 1)[1].strip()
    entry = api_keys().get(token)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "detail": "unknown API key"},
        )
    user_id, role, org = entry
    return Principal(user_id=user_id, role=role, organization_id=org)


def require(permission: Permission):
    """Dependency factory enforcing one permission."""

    def _dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.has(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "detail": f"role {principal.role.value} lacks {permission.value}",
                },
            )
        return principal

    return _dependency


def audit(
    db: Session,
    *,
    action: str,
    principal: Principal,
    incident_id: str | None = None,
    detail: dict | None = None,
) -> AuditRow:
    """Append a hash-chained audit entry scoped to the caller's organization."""
    previous = (
        db.query(AuditRow)
        .filter(AuditRow.organization_id == principal.organization_id)
        .order_by(AuditRow.created_at.desc(), AuditRow.id.desc())
        .first()
    )
    prev_hash = previous.entry_hash if previous else "0" * 64
    row = AuditRow(
        id=new_id("evt"),
        organization_id=principal.organization_id,
        incident_id=incident_id,
        actor=principal.user_id,
        actor_role=principal.role.value,
        action=action,
        detail=detail or {},
        prev_hash=prev_hash,
        created_at=datetime.now(UTC),
    )
    payload = json.dumps(
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "incident_id": row.incident_id,
            "actor": row.actor,
            "actor_role": row.actor_role,
            "action": row.action,
            "detail": row.detail,
            "prev_hash": row.prev_hash,
            "created_at": row.created_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    row.entry_hash = hashlib.sha256(payload.encode()).hexdigest()
    db.add(row)
    return row
