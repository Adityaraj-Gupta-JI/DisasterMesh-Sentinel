"""Sealing a bundle: sign the header, encrypt the payload, verify on receipt.

Application-level protection is applied regardless of transport security, because a
relay is untrusted by design: it carries ciphertext and routing metadata only.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from ..domain.errors import ProtocolError
from ..protocol.bundle import Bundle, canonical_json, sha256_hex
from .keys import SoftwareKeyStore


def seal(bundle: Bundle, *, keystore: SoftwareKeyStore, key_id: str, signer_node_id: str) -> Bundle:
    """Encrypt the payload, then sign the header that commits to the ciphertext."""
    nonce, ciphertext = keystore.encrypt(key_id, bundle.payload, aad=bundle.id.encode())
    header = replace(
        bundle.header,
        payload_size=len(ciphertext),
        payload_hash=sha256_hex(ciphertext),
        encryption={
            "alg": "AES-256-GCM",
            "key_id": key_id,
            "nonce": nonce.hex(),
            "aad": "bundle_id",
        },
    )
    signature = keystore.sign(signer_node_id, canonical_json(header.signable()))
    header = replace(header, signature=signature.hex(), signer_node_id=signer_node_id)
    return Bundle(header=header, payload=ciphertext)


def verify_signature(bundle: Bundle, *, keystore: SoftwareKeyStore) -> bool:
    """True when the header signature matches a known, unrevoked signer."""
    header = bundle.header
    if not header.signature or not header.signer_node_id:
        return False
    try:
        signature = bytes.fromhex(header.signature)
    except ValueError:
        return False
    return keystore.verify(header.signer_node_id, canonical_json(header.signable()), signature)


def unseal(
    bundle: Bundle, *, keystore: SoftwareKeyStore, now: datetime, require_signature: bool = True
) -> bytes:
    """Validate, check the signature, then decrypt. Fails closed at every step."""
    bundle.validate(now)
    if require_signature and not verify_signature(bundle, keystore=keystore):
        raise ProtocolError(f"signature verification failed for bundle {bundle.id}")
    enc = bundle.header.encryption
    if not enc:
        return bundle.payload
    if enc.get("alg") != "AES-256-GCM":
        raise ProtocolError(f"unsupported encryption algorithm {enc.get('alg')!r}")
    try:
        nonce = bytes.fromhex(enc["nonce"])
    except (KeyError, ValueError) as exc:
        raise ProtocolError("missing or malformed nonce") from exc
    return keystore.decrypt(enc["key_id"], nonce, bundle.payload, aad=bundle.id.encode())
