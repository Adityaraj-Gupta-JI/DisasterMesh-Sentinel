"""Role, organization, and sensitivity checks.

One function decides every read: ``can_receive``. The sync engine, the inventory
exchange, and the backend all route through it, so an authorization rule cannot be
enforced in one place and forgotten in another.
"""

from __future__ import annotations

from datetime import datetime

from ..domain.enums import Permission, Role, Sensitivity
from ..domain.errors import AuthorizationError
from ..domain.models import ROLE_PERMISSIONS, NodeIdentity, SyncObject


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_permission(role: Role, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise AuthorizationError(f"role {role.value} lacks {permission.value}")


def sensitivity_permitted(role: Role, sensitivity: Sensitivity) -> bool:
    if sensitivity is Sensitivity.MEDICAL:
        return has_permission(role, Permission.VIEW_MEDICAL_DATA)
    if sensitivity is Sensitivity.OPERATIONAL:
        return has_permission(role, Permission.VIEW_INCIDENT) or has_permission(
            role, Permission.FORWARD_BUNDLE
        )
    return True


def can_receive(obj: SyncObject, receiver: NodeIdentity, *, now: datetime) -> tuple[bool, str]:
    """Decide whether ``receiver`` may be offered ``obj``, with a recorded reason.

    A relay may carry ciphertext it cannot read: FORWARD_BUNDLE is sufficient to be
    offered an object, but never grants plaintext access (see crypto.sealing).
    """
    if not receiver.is_active(now):
        return False, "receiver_revoked_or_expired"
    if obj.allowed_roles and receiver.role not in obj.allowed_roles:
        return False, "role_not_in_allowed_roles"
    if (
        obj.sensitivity is Sensitivity.MEDICAL
        and receiver.role is not Role.VOLUNTEER_RELAY
        and not has_permission(receiver.role, Permission.VIEW_MEDICAL_DATA)
    ):
        return False, "medical_content_requires_clearance"
    if not sensitivity_permitted(receiver.role, obj.sensitivity) and not has_permission(
        receiver.role, Permission.FORWARD_BUNDLE
    ):
        return False, "sensitivity_not_permitted"
    return True, "authorized"


def can_read_plaintext(role: Role, sensitivity: Sensitivity) -> bool:
    """Carrying is not reading. A relay never reads above PUBLIC."""
    if role is Role.VOLUNTEER_RELAY:
        return sensitivity is Sensitivity.PUBLIC
    return sensitivity_permitted(role, sensitivity)
