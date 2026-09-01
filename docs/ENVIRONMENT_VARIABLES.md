# Environment Variables

Template in [`.env.example`](../.env.example). `.env` is git-ignored; never commit real values.

## Gateway

| Variable | Default | Notes |
|---|---|---|
| `DMS_ENV` | `development` | `production` makes the API fail closed with no keys |
| `DMS_DATABASE_URL` | `sqlite:///./dms_gateway.db` | PostgreSQL supported by the ORM, untested |
| `DMS_CORS_ORIGINS` | `http://localhost:5173` | Explicit allow-list; never `*` |
| `DMS_MAX_UPLOAD_BYTES` | `8388608` | 8 MB attachment cap |
| `DMS_API_KEYS` | *(unset)* | `key:user:ROLE:org`, comma separated |

With `DMS_ENV=production` and no `DMS_API_KEYS`, the API authorizes **nobody**. That is
deliberate: an emergency system that silently falls back to development credentials is
worse than one that refuses to start.

## AI service

| Variable | Default | Notes |
|---|---|---|
| `DMS_AI_MODE` | `mock` | Label reported by `/health` |
| `DMS_AI_TIMEOUT_S` | `10` | Per-request budget |
| `DMS_AI_LOG_PAYLOADS` | `false` | Keep false; true logs report content |
| `DMS_AI_ENABLE_WHISPER` | `false` | Real transcription |
| `DMS_AI_ENABLE_TRIAGE` | `false` | Real classifier |
| `DMS_AI_ENABLE_ENTITIES` | `false` | Real NER |
| `DMS_AI_ENABLE_EMBEDDINGS` | `false` | Real embeddings |
| `DMS_AI_ENABLE_TRANSLATION` | `false` | Real translation |
| `DMS_AI_*_CKPT` | see `.env.example` | Checkpoint identifiers |

Enabling any real model is a human-approval gate: the weights are large and none has
been downloaded or evaluated here.

## Dashboard

| Variable | Default |
|---|---|
| `VITE_API_URL` | `http://localhost:8000` |
| `VITE_API_KEY` | `dev-coordinator-key` |
