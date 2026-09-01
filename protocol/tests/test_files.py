"""Resumable, verified attachment transfer."""

from __future__ import annotations

from datetime import timedelta

import pytest
from dms.domain.enums import AttachmentKind, TransferState
from dms.domain.errors import TransferError
from dms.files.manifest import MAX_ATTACHMENT_BYTES, FileManifest
from dms.files.transfer import TransferSession, chunk_bytes

IMAGE = b"\xff\xd8\xff" + b"pixels" * 40_000


@pytest.fixture
def manifest() -> FileManifest:
    return FileManifest.for_bytes(
        IMAGE,
        file_name="flood.jpg",
        mime_type="image/jpeg",
        kind=AttachmentKind.IMAGE,
        chunk_bytes=64 * 1024,
    )


@pytest.fixture
def session(manifest, tmp_path) -> TransferSession:
    return TransferSession(
        manifest=manifest, quarantine_dir=tmp_path / "q", committed_dir=tmp_path / "c"
    )


def test_successful_image_transfer_commits(session, manifest, now, tmp_path):
    session.accept(now=now)
    session.begin()
    for index, chunk in chunk_bytes(IMAGE, manifest):
        session.receive_chunk(index, chunk)
    path = session.verify_and_commit()
    assert path.read_bytes() == IMAGE
    assert session.state is TransferState.COMMITTED
    assert not list((tmp_path / "q").glob("*.part")), "quarantine must be left clean"


def test_interrupted_transfer_resumes_from_missing_chunks(session, manifest, now):
    session.accept(now=now)
    session.begin()
    chunks = chunk_bytes(IMAGE, manifest)
    for index, chunk in chunks[:2]:
        session.receive_chunk(index, chunk)
    session.interrupt("link_lost")
    assert session.state is TransferState.INTERRUPTED
    assert session.missing == list(range(2, manifest.chunk_count))
    assert 0 < session.progress < 1.0

    session.begin()
    for index, chunk in chunks[2:]:
        session.receive_chunk(index, chunk)
    assert session.verify_and_commit().read_bytes() == IMAGE


def test_hash_mismatch_never_commits(session, manifest, now, tmp_path):
    session.accept(now=now)
    session.begin()
    for index, chunk in chunk_bytes(IMAGE, manifest):
        session.receive_chunk(index, b"\x00" * len(chunk) if index == 1 else chunk)
    with pytest.raises(TransferError, match="digest mismatch"):
        session.verify_and_commit()
    assert session.state is TransferState.FAILED
    assert list((tmp_path / "c").glob("*")) == [], "nothing may reach permanent storage"


def test_corrupted_chunk_is_rejected_on_arrival(session, manifest, now):
    import hashlib

    session.accept(now=now)
    session.begin()
    index, chunk = chunk_bytes(IMAGE, manifest)[0]
    good = hashlib.sha256(chunk).hexdigest()
    with pytest.raises(TransferError, match="chunk 0 digest mismatch"):
        session.receive_chunk(index, b"\xff" * len(chunk), expected_sha256=good)


def test_wrong_size_chunk_is_rejected(session, manifest, now):
    session.accept(now=now)
    session.begin()
    with pytest.raises(TransferError, match="size"):
        session.receive_chunk(0, b"short")


def test_incomplete_transfer_cannot_commit(session, manifest, now):
    session.accept(now=now)
    session.begin()
    index, chunk = chunk_bytes(IMAGE, manifest)[0]
    session.receive_chunk(index, chunk)
    with pytest.raises(TransferError, match="missing"):
        session.verify_and_commit()


def test_expired_attachment_is_not_accepted(manifest, tmp_path, now):
    manifest.expires_at = now - timedelta(seconds=1)
    session = TransferSession(
        manifest=manifest, quarantine_dir=tmp_path / "q", committed_dir=tmp_path / "c"
    )
    with pytest.raises(TransferError, match="expired"):
        session.accept(now=now)
    assert session.state is TransferState.EXPIRED


def test_file_larger_than_policy_limit_is_refused(tmp_path, now):
    oversized = FileManifest(
        file_name="huge.jpg",
        mime_type="image/jpeg",
        kind=AttachmentKind.IMAGE,
        size_bytes=MAX_ATTACHMENT_BYTES + 1,
        sha256="a" * 64,
    )
    session = TransferSession(
        manifest=oversized, quarantine_dir=tmp_path / "q", committed_dir=tmp_path / "c"
    )
    with pytest.raises(TransferError, match="exceeds policy limit"):
        session.accept(now=now)


@pytest.mark.parametrize(
    "mime", ["application/x-sh", "application/x-msdownload", "application/zip"]
)
def test_executable_and_archive_types_are_forbidden(mime, tmp_path, now):
    m = FileManifest(
        file_name="payload",
        mime_type=mime,
        kind=AttachmentKind.DOCUMENT,
        size_bytes=10,
        sha256="b" * 64,
    )
    session = TransferSession(
        manifest=m, quarantine_dir=tmp_path / "q", committed_dir=tmp_path / "c"
    )
    with pytest.raises(TransferError, match="forbidden|not permitted"):
        session.accept(now=now)


def test_mime_must_match_declared_kind(tmp_path, now):
    m = FileManifest(
        file_name="a.jpg",
        mime_type="audio/wav",
        kind=AttachmentKind.IMAGE,
        size_bytes=10,
        sha256="c" * 64,
    )
    session = TransferSession(
        manifest=m, quarantine_dir=tmp_path / "q", committed_dir=tmp_path / "c"
    )
    with pytest.raises(TransferError, match="not permitted for IMAGE"):
        session.accept(now=now)


def test_committed_file_is_not_executable(session, manifest, now):
    session.accept(now=now)
    session.begin()
    for index, chunk in chunk_bytes(IMAGE, manifest):
        session.receive_chunk(index, chunk)
    path = session.verify_and_commit()
    assert path.stat().st_mode & 0o111 == 0, "received files must never be executable"


def test_manifest_round_trips_through_json(manifest):
    assert FileManifest.from_dict(manifest.to_dict()).sha256 == manifest.sha256


def test_illegal_transfer_transition_is_rejected(session, now):
    with pytest.raises(TransferError, match="illegal transfer transition"):
        session.verify_and_commit()  # OFFERED -> VERIFYING is not allowed
