"""Image attachment bytes + audio transcription → text incident flow.

These cover the additive media features without touching the existing text path:
inline image bytes are stored, verified, and served; audio transcribes to text and
files through the normal incident pipeline; and bad input is rejected cleanly.
"""

from __future__ import annotations

import base64
import hashlib

AUTH = {"Authorization": "Bearer dev-coordinator-key"}

# A 1x1 PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _make_incident(client) -> str:
    r = client.post(
        "/v1/incidents",
        json={"source_node_id": "test", "original_text": "Fire near the school", "priority_class": "P2"},
        headers=AUTH,
    )
    return r.json()["id"]


def test_image_bytes_are_stored_verified_and_served(client) -> None:
    iid = _make_incident(client)
    sha = hashlib.sha256(PNG).hexdigest()
    r = client.post(
        f"/v1/incidents/{iid}/attachments",
        json={
            "file_name": "scene.png",
            "mime_type": "image/png",
            "size_bytes": len(PNG),
            "sha256": sha,
            "kind": "IMAGE",
            "data_base64": base64.b64encode(PNG).decode(),
        },
        headers=AUTH,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["has_content"] is True
    att_id = body["id"]

    # The detail view reports it as renderable image content.
    detail = client.get(f"/v1/incidents/{iid}", headers=AUTH).json()
    att = detail["attachments"][0]
    assert att["kind"] == "IMAGE" and att["has_content"] is True and att["verified"] is True

    # The bytes come back intact, with the right content type.
    content = client.get(f"/v1/incidents/{iid}/attachments/{att_id}/content", headers=AUTH)
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/png")
    assert content.content == PNG


def test_hash_mismatch_is_rejected(client) -> None:
    iid = _make_incident(client)
    r = client.post(
        f"/v1/incidents/{iid}/attachments",
        json={
            "file_name": "scene.png",
            "mime_type": "image/png",
            "size_bytes": len(PNG),
            "sha256": "0" * 64,  # wrong digest
            "data_base64": base64.b64encode(PNG).decode(),
        },
        headers=AUTH,
    )
    assert r.status_code == 422
    assert r.json()["error"] == "hash_mismatch"


def test_metadata_only_attachment_still_works_and_has_no_content(client) -> None:
    # The pre-existing behaviour: register metadata, no bytes.
    iid = _make_incident(client)
    sha = hashlib.sha256(PNG).hexdigest()
    r = client.post(
        f"/v1/incidents/{iid}/attachments",
        json={"file_name": "x.png", "mime_type": "image/png", "size_bytes": len(PNG), "sha256": sha},
        headers=AUTH,
    )
    assert r.status_code == 201 and r.json()["has_content"] is False
    att_id = r.json()["id"]
    assert client.get(f"/v1/incidents/{iid}/attachments/{att_id}/content", headers=AUTH).status_code == 404


def test_audio_transcribes_then_files_as_normal_incident(client) -> None:
    # The 'HI' marker maps to a Hindi fixture transcript in the mock STT.
    audio = b"HI" + b"\x00" * 64
    tr = client.post(
        "/v1/transcribe",
        json={"audio_base64": base64.b64encode(audio).decode(), "mime_type": "audio/wav"},
        headers=AUTH,
    )
    assert tr.status_code == 200
    text = tr.json()["text"]
    assert text  # non-empty transcript

    # The transcribed text becomes an ordinary incident with a real priority.
    comp = client.post("/v1/compose", json={"text": text}, headers=AUTH)
    assert comp.status_code == 201
    inc_id = comp.json()["id"]
    detail = client.get(f"/v1/incidents/{inc_id}", headers=AUTH).json()
    assert detail["incident"]["original_text"] == text
    assert detail["incident"]["priority_class"] in {"P0", "P1", "P2", "P3"}


def test_compose_classifies_priority_like_a_device(client) -> None:
    comp = client.post(
        "/v1/compose",
        json={"text": "Three people trapped under collapsed building near Market Road"},
        headers=AUTH,
    )
    assert comp.status_code == 201
    detail = client.get(f"/v1/incidents/{comp.json()['id']}", headers=AUTH).json()
    assert detail["incident"]["priority_class"] == "P0"


def test_invalid_base64_audio_is_rejected(client) -> None:
    r = client.post(
        "/v1/transcribe",
        json={"audio_base64": "not base64!!!", "mime_type": "audio/wav"},
        headers=AUTH,
    )
    assert r.status_code == 400
