/**
 * Renders an attachment as what it actually is — an image the coordinator can see,
 * or audio they can play — instead of a metadata row that reads as a tiny box.
 *
 * The bytes are auth-scoped, so we fetch them with the bearer token and hand the
 * element a blob URL (revoked on unmount). When no bytes were stored (a mesh
 * transfer that carried only metadata, or a still-arriving file), we fall back to
 * the original filename/hash/size row — the pre-existing behaviour, unchanged.
 */
import { useEffect, useState } from "react";

import { ApiError, media, type IncidentDetail } from "../lib/api";

type Attachment = IncidentDetail["attachments"][number];

export function AttachmentMedia({
  incidentId,
  file,
}: {
  incidentId: string;
  file: Attachment;
}) {
  const isImage = file.kind === "IMAGE" || file.mime_type.startsWith("image/");
  const isAudio = file.kind === "AUDIO" || file.mime_type.startsWith("audio/");
  const renderable = file.has_content && (isImage || isAudio);

  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(renderable);

  useEffect(() => {
    if (!renderable) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setError(null);
    media
      .fetchAttachmentObjectUrl(incidentId, file.id)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u);
          return;
        }
        objectUrl = u;
        setUrl(u);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "could not load media");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [incidentId, file.id, renderable]);

  return (
    <div className="evidence-item">
      <div className="evidence-row">
        <span>{file.file_name}</span>
        <span className={`badge ${file.verified ? "solid-ok" : "outline"}`}>
          {file.verified ? "hash verified" : "transfer pending"}
        </span>
        <code>{file.sha256.slice(0, 12)}…</code>
        <span>{(file.size_bytes / 1024).toFixed(0)} KB</span>
      </div>

      {renderable && loading && <p className="empty">Loading {isAudio ? "audio" : "image"}…</p>}
      {renderable && error && <p className="error">{error}</p>}

      {isImage && url && (
        <a href={url} target="_blank" rel="noreferrer" className="evidence-image-link">
          <img className="evidence-image" src={url} alt={file.file_name} />
        </a>
      )}
      {isAudio && url && (
        <audio className="evidence-audio" controls src={url}>
          Your browser cannot play this audio.
        </audio>
      )}

      {!file.has_content && (
        <p className="evidence-note">
          Bytes not received yet — text and metadata arrive before media.
        </p>
      )}
    </div>
  );
}
