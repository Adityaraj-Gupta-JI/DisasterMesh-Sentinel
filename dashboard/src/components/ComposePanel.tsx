/**
 * Report composer — the "sender" side.
 *
 * Text and transcribed audio both go through the existing incident pipeline
 * (`/v1/compose`). Images are attached to the created incident with their bytes.
 * Audio is turned into text by the existing speech-to-text endpoint.
 *
 * This panel is purely additive: it calls existing endpoints and never changes
 * how text messages already flow.
 */
import { useState } from "react";

import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import { ApiError, media, sha256Hex, toBase64 } from "../lib/api";

const ALLOWED_IMAGE = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

type Phase = "idle" | "transcribing" | "sending" | "error" | "done";

export function ComposePanel({ onSent }: { onSent: () => void }) {
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [image, setImage] = useState<{ file: File; url: string } | null>(null);

  const { recording, start: startRecording, stop: stopRecording } = useVoiceRecorder(
    (blob) => { void transcribe(blob); },
    (msg) => { setPhase("error"); setMessage(msg); },
  );

  const reset = () => {
    setText("");
    if (image) URL.revokeObjectURL(image.url);
    setImage(null);
  };

  const pickImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessage(null);
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!ALLOWED_IMAGE.has(file.type)) {
      setPhase("error");
      setMessage(`Unsupported image type: ${file.type || "unknown"}. Use JPEG, PNG, or WebP.`);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setPhase("error");
      setMessage(`Image is ${(file.size / 1_000_000).toFixed(1)} MB; the limit is 8 MB.`);
      return;
    }
    if (image) URL.revokeObjectURL(image.url);
    setImage({ file, url: URL.createObjectURL(file) });
    setPhase("idle");
  };

  const send = async () => {
    if (!text.trim()) {
      setPhase("error");
      setMessage("A report needs some text. Record audio or type a message.");
      return;
    }
    setPhase("sending");
    setMessage(image ? "Filing report and uploading image…" : "Filing report…");
    try {
      const { id } = await media.compose(text.trim());
      if (image) {
        const buffer = await image.file.arrayBuffer();
        await media.uploadAttachment(id, {
          file_name: image.file.name,
          mime_type: image.file.type,
          size_bytes: image.file.size,
          sha256: await sha256Hex(buffer),
          kind: "IMAGE",
          data_base64: toBase64(buffer),
        });
      }
      setPhase("done");
      setMessage("Report filed.");
      reset();
      onSent();
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof ApiError ? e.message : "Could not send the report.");
    }
  };

  const pickAudio = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) await transcribe(file);
  };

  const transcribe = async (blob: Blob) => {
    setPhase("transcribing");
    setMessage("Transcribing audio…");
    try {
      const buffer = await blob.arrayBuffer();
      const result = await media.transcribe(toBase64(buffer), "audio/ogg");
      if (!result.text) {
        setPhase("idle");
        setMessage("Could not make out speech — please type the report.");
        return;
      }
      setText((prev) => (prev ? `${prev} ${result.text}` : result.text));
      setPhase("idle");
      setMessage(`Transcribed (${result.language}). Review, then send.`);
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof ApiError ? e.message : "Transcription failed.");
    }
  };

  const busy = phase === "sending" || phase === "transcribing";

  return (
    <div className="compose">
      {/* Editorial eyebrow + heading */}
      <p className="compose-eyebrow">Field Transmission</p>
      <h2>New Report</h2>
      <p className="compose-hint">
        Type a message, record a voice note (it is transcribed to text), and optionally
        attach a photo. Everything is filed through the normal incident pipeline.
      </p>

      {/* Report text */}
      <textarea
        className="compose-text"
        placeholder="Describe the emergency…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        disabled={busy}
      />

      {/* Action bar */}
      <div className="compose-actions">
        {!recording ? (
          <button
            className="compose-capture-btn"
            onClick={startRecording}
            disabled={busy}
          >
            ● Record voice
          </button>
        ) : (
          <button
            className="compose-capture-btn recording"
            onClick={stopRecording}
          >
            <span style={{
              display: "inline-block",
              width: 8, height: 8, borderRadius: "50%",
              background: "currentColor", marginRight: 4,
            }} />
            RECORDING · Stop
          </button>
        )}

        <label className="compose-file">
          Audio file
          <input type="file" accept="audio/*" onChange={pickAudio} disabled={busy} hidden />
        </label>

        <label className="compose-file">
          {image ? "Change photo" : "Attach photo"}
          <input type="file" accept="image/*" onChange={pickImage} disabled={busy} hidden />
        </label>

        <div className="spacer" style={{ flex: 1 }} />

        <button
          className="compose-send"
          onClick={send}
          disabled={busy}
        >
          {phase === "sending" ? "Transmitting…" : "Transmit Report"}
        </button>
      </div>

      {/* Image preview */}
      {image && (
        <div className="compose-preview">
          <img src={image.url} alt="attachment preview" />
          <button
            className="compose-remove"
            onClick={() => {
              URL.revokeObjectURL(image.url);
              setImage(null);
            }}
          >
            Remove
          </button>
        </div>
      )}

      {/* Transmission state */}
      {phase === "sending" && (
        <div className="compose-transmitting">
          <span className="transmit-dot" />
          TRANSMITTING TO MESH…
        </div>
      )}

      {/* Status message */}
      {message && (
        <p className={phase === "error" ? "error" : "compose-status"}>
          {message}
          {phase === "error" && (
            <button className="compose-retry" onClick={send}>
              Retry
            </button>
          )}
        </p>
      )}
    </div>
  );
}
