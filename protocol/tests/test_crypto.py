"""Cryptographic protection of bundles."""

from __future__ import annotations

from dataclasses import replace

import pytest
from dms.crypto.keys import CryptoError, SoftwareKeyStore
from dms.crypto.sealing import seal, unseal, verify_signature
from dms.domain.enums import PayloadType
from dms.domain.errors import ProtocolError
from dms.protocol.bundle import Bundle


@pytest.fixture
def keystore() -> SoftwareKeyStore:
    ks = SoftwareKeyStore()
    ks.generate("node_a")
    return ks


@pytest.fixture
def sealed(keystore, now) -> Bundle:
    bundle = Bundle.create(
        incident_id="i1",
        source_node_id="node_a",
        payload=b"medical: patient unconscious",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    )
    return seal(bundle, keystore=keystore, key_id="org1", signer_node_id="node_a")


def test_encrypt_decrypt_round_trip(keystore, sealed, now):
    assert unseal(sealed, keystore=keystore, now=now) == b"medical: patient unconscious"


def test_ciphertext_does_not_contain_plaintext(sealed):
    assert b"unconscious" not in sealed.payload


def test_signature_verifies(keystore, sealed):
    assert verify_signature(sealed, keystore=keystore) is True


def test_tampered_header_fails_signature(keystore, sealed):
    tampered = Bundle(header=replace(sealed.header, priority_score=99), payload=sealed.payload)
    assert verify_signature(tampered, keystore=keystore) is False


def test_tampered_payload_fails_before_decryption(keystore, sealed, now):
    tampered = Bundle(header=sealed.header, payload=b"\x00" * len(sealed.payload))
    with pytest.raises(ProtocolError):
        unseal(tampered, keystore=keystore, now=now)


def test_wrong_key_cannot_decrypt(sealed, now):
    other = SoftwareKeyStore()
    other.generate("node_a")
    other.register_public_key("node_a", b"\x00" * 32)
    other.set_shared_key("org1", b"\x01" * 32)
    with pytest.raises((CryptoError, ProtocolError)):
        unseal(sealed, keystore=other, now=now, require_signature=False)


def test_each_encryption_uses_a_fresh_nonce(keystore):
    nonces = {keystore.encrypt("org1", b"same plaintext")[0] for _ in range(50)}
    assert len(nonces) == 50, "nonce reuse under a single key breaks AES-GCM"


def test_revoked_identity_no_longer_verifies(keystore, sealed):
    keystore.revoke("node_a")
    assert verify_signature(sealed, keystore=keystore) is False


def test_unsigned_bundle_is_rejected_when_signature_required(keystore, now):
    unsigned = Bundle.create(
        incident_id="i1",
        source_node_id="node_a",
        payload=b"x",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    )
    with pytest.raises(ProtocolError, match="signature verification failed"):
        unseal(unsigned, keystore=keystore, now=now)
