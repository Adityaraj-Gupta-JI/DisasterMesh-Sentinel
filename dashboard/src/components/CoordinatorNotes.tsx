/**
 * Coordinator follow-up notes — typed, or recorded and transcribed.
 *
 * End to end, no gaps: record -> upload the raw audio as a real attachment
 * (provenance, always kept, regardless of what happens next) -> transcribe
 * -> show the result in an editable box so a human reviews/corrects it ->
 * only on explicit confirm does it become a durable note. If transcription
 * fails, the box is simply empty and the coordinator can type instead — the
 * audio attachment is already saved either way.
 */
import { useState } from "react";

import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import { ApiError, api, media, relativeTime, sha256Hex, toBase64, type IncidentNote } from "../lib/api";

type Phase = "idle" | "uploading" | "transcribing" | "saving" | "error";

export function CoordinatorNotes({
  incidentId,
  notes,
  onAdded,
}: {
  incidentId: string;
  notes: IncidentNote[];
  onAdded: () => void;
}) {
  const [draftText, setDraftText] = useState("");
  const [draftSource, setDraftSource] = useState<"text" | "voice">("text");
  const [audioAttachmentId, setAudioAttachmentId] = useState<string | undefined>(undefined);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [showDraft, setShowDraft] = useState(false);

  const busy = phase === "uploading" || phase === "transcribing" || phase === "saving";

  const handleRecorded = async (blob: Blob) => {
    setShowDraft(true);
    setDraftSource("voice");
    setDraftText("");
    setAudioAttachmentId(undefined);
    setPhase("uploading");
    setMessage("Saving audio…");
    try {
      const buffer = await blob.arrayBuffer();
      // Normalize away codec parameters ("audio/webm;codecs=opus" -> "audio/webm")
      // to match the gateway's exact-match MIME whitelist.
      const mimeType = (blob.type || "audio/webm").split(";")[0];
      const upload = await media.uploadAttachment(incidentId, {
        file_name: `note-${Date.now()}.webm`,
        mime_type: mimeType,
        size_bytes: buffer.byteLength,
        sha256: await sha256Hex(buffer),
        kind: "AUDIO",
        data_base64: toBase64(buffer),
      });
      setAudioAttachmentId(upload.id);

      setPhase("transcribing");
      setMessage("Transcribing…");
      const result = await media.transcribe(toBase64(buffer), "audio/ogg");
      if (!result.text) {
        setPhase("idle");
        setMessage("Could not make out speech — audio saved, type the note instead.");
        return;
      }
      setDraftText(result.text);
      setPhase("idle");
      setMessage(`Transcribed (${result.language}). Review before saving.`);
    } catch (e) {
      setPhase("error");
      setMessage(
        e instanceof ApiError
          ? `Audio saved, but: ${e.message}. You can still type the note.`
          : "Something went wrong — the audio is saved, type the note manually.",
      );
    }
  };

  const { recording, start, stop } = useVoiceRecorder(
    (blob) => void handleRecorded(blob),
    (msg) => {
      setPhase("error");
      setMessage(msg);
    },
  );

  const startText = () => {
    setShowDraft(true);
    setDraftSource("text");
    setDraftText("");
    setAudioAttachmentId(undefined);
    setMessage(null);
    setPhase("idle");
  };

  const save = async () => {
    if (!draftText.trim()) {
      setPhase("error");
      setMessage("The note is empty.");
      return;
    }
    setPhase("saving");
    try {
      await api.addNote(incidentId, draftText.trim(), draftSource, audioAttachmentId);
      setShowDraft(false);
      setDraftText("");
      setAudioAttachmentId(undefined);
      setPhase("idle");
      setMessage(null);
      onAdded();
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof ApiError ? e.message : "Could not save the note.");
    }
  };

  const cancel = () => {
    setShowDraft(false);
    setDraftText("");
    setAudioAttachmentId(undefined);
    setPhase("idle");
    setMessage(null);
  };

  return (
    <section className="section">
      <h3>Coordinator notes</h3>

      {notes.length === 0 && !showDraft && <p className="empty">No follow-up notes yet.</p>}

      {notes.length > 0 && (
        <div className="evidence" style={{ marginBottom: "var(--space-3)" }}>
          {notes.map((note) => (
            <div key={note.id} className="evidence-row" style={{ alignItems: "flex-start", flexDirection: "column" }}>
              <p style={{ margin: 0 }}>{note.text}</p>
              <p className="simulated-note" style={{ marginTop: "4px" }}>
                {note.source === "voice" ? "🎤 voice" : "typed"} · {relativeTime(note.created_at)}
                {note.audio_attachment_id && " · original audio in Evidence"}
              </p>
            </div>
          ))}
        </div>
      )}

      {!showDraft ? (
        <div style={{ display: "flex", gap: "8px" }}>
          {!recording ? (
            <button onClick={start}>🎤 Record note</button>
          ) : (
            <button onClick={stop} className="recording">
              ■ Stop recording
            </button>
          )}
          <button onClick={startText}>+ Type a note</button>
        </div>
      ) : (
        <div>
          <textarea
            className="compose-text"
            placeholder={phase === "transcribing" ? "Transcribing…" : "Note text…"}
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            rows={3}
            disabled={busy}
          />
          <div className="compose-actions">
            <button className="compose-send" onClick={save} disabled={busy || !draftText.trim()}>
              {phase === "saving" ? "Saving…" : "Save note"}
            </button>
            <button onClick={cancel} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {message && <p className={phase === "error" ? "error" : "compose-status"}>{message}</p>}
    </section>
  );
}
