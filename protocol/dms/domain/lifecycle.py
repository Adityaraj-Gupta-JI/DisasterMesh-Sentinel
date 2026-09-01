"""Incident and dispatch lifecycle rules.

Only transitions declared here are legal. Every accepted transition emits an audit
event; expiry never erases an incident or its history.
"""

from __future__ import annotations

from datetime import datetime

from .enums import DispatchStatus, Permission, Role
from .enums import IncidentStatus as S
from .errors import AuthorizationError, LifecycleError
from .models import ROLE_PERMISSIONS, Incident

INCIDENT_TRANSITIONS: dict[S, frozenset[S]] = {
    S.DRAFT: frozenset({S.QUEUED, S.CANCELLED}),
    S.QUEUED: frozenset({S.RELAYED, S.RECEIVED, S.EXPIRED, S.CANCELLED}),
    S.RELAYED: frozenset({S.RELAYED, S.RECEIVED, S.EXPIRED, S.CANCELLED}),
    S.RECEIVED: frozenset({S.ACKNOWLEDGED, S.EXPIRED, S.CANCELLED}),
    S.ACKNOWLEDGED: frozenset({S.DISPATCH_REQUESTED, S.RESOLVED, S.EXPIRED, S.CANCELLED}),
    S.DISPATCH_REQUESTED: frozenset({S.DISPATCHED, S.RESOLVED, S.CANCELLED}),
    S.DISPATCHED: frozenset({S.EN_ROUTE, S.RESOLVED, S.CANCELLED}),
    S.EN_ROUTE: frozenset({S.ARRIVED, S.RESOLVED, S.CANCELLED}),
    S.ARRIVED: frozenset({S.RESOLVED, S.CANCELLED}),
    S.RESOLVED: frozenset(),
    S.EXPIRED: frozenset({S.ACKNOWLEDGED, S.RESOLVED}),
    S.CANCELLED: frozenset(),
}

#: Transitions that require a specific permission from the acting role.
TRANSITION_PERMISSIONS: dict[S, Permission] = {
    S.RESOLVED: Permission.CLOSE_INCIDENT,
    S.DISPATCH_REQUESTED: Permission.ASSIGN_RESOURCE,
    S.DISPATCHED: Permission.ASSIGN_RESOURCE,
}

DISPATCH_TRANSITIONS: dict[DispatchStatus, frozenset[DispatchStatus]] = {
    DispatchStatus.RECOMMENDED: frozenset({DispatchStatus.ASSIGNED, DispatchStatus.CANCELLED}),
    DispatchStatus.ASSIGNED: frozenset({DispatchStatus.ACKNOWLEDGED, DispatchStatus.CANCELLED}),
    DispatchStatus.ACKNOWLEDGED: frozenset({DispatchStatus.EN_ROUTE, DispatchStatus.CANCELLED}),
    DispatchStatus.EN_ROUTE: frozenset({DispatchStatus.ARRIVED, DispatchStatus.CANCELLED}),
    DispatchStatus.ARRIVED: frozenset({DispatchStatus.COMPLETED, DispatchStatus.CANCELLED}),
    DispatchStatus.COMPLETED: frozenset(),
    DispatchStatus.CANCELLED: frozenset(),
}


def can_transition(current: S, target: S) -> bool:
    return target in INCIDENT_TRANSITIONS.get(current, frozenset())


def check_authorized(target: S, role: Role) -> None:
    """Raise if ``role`` may not drive an incident into ``target``."""
    needed = TRANSITION_PERMISSIONS.get(target)
    if needed and needed not in ROLE_PERMISSIONS.get(role, frozenset()):
        raise AuthorizationError(
            f"role {role.value} lacks {needed.value} required for {target.value}"
        )


def transition(
    incident: Incident, target: S, *, role: Role, now: datetime, idempotent: bool = True
) -> bool:
    """Move ``incident`` to ``target``.

    Returns True when the state changed, False when the incident was already in
    ``target`` and ``idempotent`` is set (duplicate delivery must not be an error).
    Raises LifecycleError on an illegal transition.
    """
    if incident.status is target:
        if idempotent:
            return False
        raise LifecycleError(f"incident already {target.value}")
    if not can_transition(incident.status, target):
        raise LifecycleError(f"illegal transition {incident.status.value} -> {target.value}")
    check_authorized(target, role)
    incident.status = target
    incident.touch(now)
    return True


def dispatch_transition(
    current: DispatchStatus, target: DispatchStatus, *, idempotent: bool = True
) -> bool:
    if current is target:
        if idempotent:
            return False
        raise LifecycleError(f"dispatch already {target.value}")
    if target not in DISPATCH_TRANSITIONS.get(current, frozenset()):
        raise LifecycleError(f"illegal dispatch transition {current.value} -> {target.value}")
    return True
