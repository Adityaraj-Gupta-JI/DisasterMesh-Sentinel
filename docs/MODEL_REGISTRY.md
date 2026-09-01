# Model Registry

Query the live registry at `GET /v1/models`. It reports what is *actually* loaded, not
what is aspirational.

| Task | Mock (default) | Real adapter | Flag | Weights downloaded |
|---|---|---|---|---|
| transcribe | `whisper-mock` 1.0.0 | `openai/whisper-small` | `DMS_AI_ENABLE_WHISPER` | no |
| triage | `dms-rule-triage` 1.0.0 | `xlm-roberta-base` | `DMS_AI_ENABLE_TRIAGE` | no |
| entities | `dms-rule-entities` 1.0.0 | `microsoft/mdeberta-v3-base` | `DMS_AI_ENABLE_ENTITIES` | no |
| embed | `multilingual-e5-mock` 1.0.0 | `intfloat/multilingual-e5-large` | `DMS_AI_ENABLE_EMBEDDINGS` | no |
| translate | `nllb-mock` 1.0.0 | `facebook/nllb-200-distilled-600M` | `DMS_AI_ENABLE_TRANSLATION` | no |
| summarize | `summary-mock` 1.0.0 | Llama/Qwen | not wired | no |

## Versioning rules

- Every inference response carries `model.name`, `model.version`, `model.mode`, and an
  `input_hash`, and those are stored with the incident.
- A model change is a version bump. Outputs from different versions are never silently
  compared.
- `/ready` reports `degraded` when a real model is enabled but not loaded, so callers
  fall back to rules rather than waiting.

## Adding a real model

1. Implement the adapter behind the existing interface in `protocol/dms/ai/`.
2. Register it in `ai-service/app/registry.py` with a version.
3. Keep the rule engine reachable as the fallback — it is what runs on a phone.
4. Add fixtures in all three languages, including a code-switched case.
5. Record the trade-off in `docs/DECISIONS.md`. Heavy model dependencies are a
   human-approval gate.
