"""Key material, signatures, and authenticated encryption.

Abstractions first: the Android build swaps ``SoftwareKeyStore`` for a Keystore-backed
implementation without touching any caller. Development keys are clearly labelled and
never reused as production keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..domain.errors import DomainError

NONCE_BYTES = 12
KEY_BYTES = 32


class CryptoError(DomainError):
    """Signature verification, decryption, or key lookup failed."""


@dataclass(frozen=True)
class KeyPair:
    node_id: str
    private_bytes: bytes
    public_bytes: bytes
    development_only: bool = True


class Signer(Protocol):
    def sign(self, node_id: str, data: bytes) -> bytes: ...
    def verify(self, node_id: str, data: bytes, signature: bytes) -> bool: ...


class Cipher(Protocol):
    def encrypt(self, key_id: str, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]: ...
    def decrypt(self, key_id: str, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes: ...


class SoftwareKeyStore:
    """In-process Ed25519 + AES-GCM key store.

    Suitable for tests, the simulator, and the backend. On Android the same
    interface is served by the platform Keystore (see docs/SECURITY.md).
    """

    def __init__(self, *, development_only: bool = True) -> None:
        self._signing: dict[str, Ed25519PrivateKey] = {}
        self._public: dict[str, Ed25519PublicKey] = {}
        self._symmetric: dict[str, bytes] = {}
        self._revoked: set[str] = set()
        self._used_nonces: set[tuple[str, bytes]] = set()
        self.development_only = development_only

    # ------------------------------------------------------------------- keys

    def generate(self, node_id: str) -> KeyPair:
        private = Ed25519PrivateKey.generate()
        public = private.public_key()
        self._signing[node_id] = private
        self._public[node_id] = public
        self._symmetric.setdefault(node_id, os.urandom(KEY_BYTES))

        return KeyPair(
            node_id=node_id,
            private_bytes=private.private_bytes_raw(),
            public_bytes=public.public_bytes_raw(),
            development_only=self.development_only,
        )

    def register_public_key(self, node_id: str, public_bytes: bytes) -> None:
        self._public[node_id] = Ed25519PublicKey.from_public_bytes(public_bytes)

    def set_shared_key(self, key_id: str, key: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise CryptoError(f"symmetric key must be {KEY_BYTES} bytes")
        self._symmetric[key_id] = key

    def ensure_shared_key(self, key_id: str) -> bytes:
        if key_id not in self._symmetric:
            self._symmetric[key_id] = os.urandom(KEY_BYTES)
        return self._symmetric[key_id]

    def revoke(self, node_id: str) -> None:
        self._revoked.add(node_id)

    def is_revoked(self, node_id: str) -> bool:
        return node_id in self._revoked

    # -------------------------------------------------------------- signatures

    def sign(self, node_id: str, data: bytes) -> bytes:
        key = self._signing.get(node_id)
        if key is None:
            raise CryptoError(f"no signing key for node {node_id}")
        return key.sign(data)

    def verify(self, node_id: str, data: bytes, signature: bytes) -> bool:
        if self.is_revoked(node_id):
            return False
        public = self._public.get(node_id)
        if public is None:
            return False
        try:
            public.verify(signature, data)
            return True
        except InvalidSignature:
            return False

    # -------------------------------------------------------------- encryption

    def encrypt(self, key_id: str, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
        """Return (nonce, ciphertext). A fresh random nonce every call."""
        key = self.ensure_shared_key(key_id)
        nonce = os.urandom(NONCE_BYTES)
        while (key_id, nonce) in self._used_nonces:  # pragma: no cover - astronomically rare
            nonce = os.urandom(NONCE_BYTES)
        self._used_nonces.add((key_id, nonce))
        return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)

    def decrypt(self, key_id: str, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
        key = self._symmetric.get(key_id)
        if key is None:
            raise CryptoError(f"no decryption key for {key_id}")
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise CryptoError("decryption failed: wrong key or tampered ciphertext") from exc


class NullCipher:
    """Pass-through cipher for tests that assert on plaintext. Never for production."""

    development_only = True

    def encrypt(self, key_id: str, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
        return b"\x00" * NONCE_BYTES, plaintext

    def decrypt(self, key_id: str, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
        return ciphertext
