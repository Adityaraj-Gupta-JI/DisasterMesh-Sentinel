# AI Service

FastAPI, port 8001. `make run-ai`. OpenAPI at `/docs`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness — the process is up |
| GET | `/ready` | Readiness — are the configured models loaded |
| GET | `/v1/models` | Versioned registry |
| POST | `/v1/triage` | Urgency, disaster types, severity, safety flags |
| POST | `/v1/entities` | People count, conditions, resources, hazards, raw spans |
| POST | `/v1/transcribe` | Multilingual transcription from base64 audio |
| POST | `/v1/embed` | Batch embeddings (max 32) |
| POST | `/v1/translate` | Machine translation, marked as such |
| POST | `/v1/summarize` | Cluster summary that never invents counts |

`/health` and `/ready` answer different questions on purpose: a service that is up but
has no model loaded must tell its callers to fall back rather than pretend to be ready.

## Contract

Every successful response carries `model` (name, version, mode, loaded) and
`input_hash`. Every failure is `{"error": "<code>", "detail": "<message>"}` with codes
such as `unsupported_media_type`, `audio_too_long`, `empty_audio`, `invalid_base64`,
`unsupported_language_pair`, `empty_cluster`.

Triage and summarize responses additionally carry an `advisory` field —
`recommendation_only_not_a_dispatch` and `human review required; no dispatch authority`
— because the caller is a machine and the guarantee should be machine-readable too.

## Limits

Text 8,000 characters. Audio 16 MB. Embedding batch 32. Cluster 100 incidents.
Request timeout 10 s by default.

## Logging

Request id, path, status, and elapsed milliseconds. Never payload content, unless
`DMS_AI_LOG_PAYLOADS=true` is set deliberately for debugging.
