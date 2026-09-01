"""Domain-level errors. Every one is a rejection, never a silent downgrade."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all DisasterMesh domain failures."""


class ValidationError(DomainError):
    """A model violated an invariant and must not be persisted or transmitted."""


class LifecycleError(DomainError):
    """An illegal incident or dispatch state transition was attempted."""


class ProtocolError(DomainError):
    """A DMBP bundle is malformed, corrupted, expired, or of an unknown version."""


class AuthorizationError(DomainError):
    """The actor lacks the permission required for this action."""


class TransferError(DomainError):
    """A file transfer failed verification or exceeded a policy limit."""
