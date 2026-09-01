# Gateway API

FastAPI, OpenAPI at `/docs` when running. All routes require
`Authorization: Bearer <key>` and are scoped to the caller's organisation.

## Conventions

- **Errors** are always `{"error": "<code>", "detail": "<message>"}`.
- **Idempotency** — send `Idempotency-Key` on POST; the first response is replayed.
  Reusing a key on a different endpoint returns 409.
- **Pagination** — `limit` (max 200) and `offset`; responses carry `total`.
- **Redaction** — responses list what was withheld in a `redacted` array rather than
  silently omitting fields.

## Endpoints

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/health` | none | liveness |
| GET | `/ready` | none | database + configured principals + warnings |
| POST | `/v1/incidents` | CREATE_INCIDENT | idempotent by id and by key |
| GET | `/v1/incidents` | VIEW_INCIDENT | filter by `priority`, `status` |
| GET | `/v1/incidents/{id}` | VIEW_INCIDENT | incident + attachments + dispatch |
| POST | `/v1/incidents/{id}/acknowledge` | VIEW_INCIDENT | repeat calls absorbed |
| PATCH | `/v1/incidents/{id}/status` | VIEW_INCIDENT (+CLOSE_INCIDENT to resolve) | validates the transition |
| POST | `/v1/incidents/{id}/attachments` | CREATE_INCIDENT | MIME + size enforced |
| GET | `/v1/incidents/{id}/recommendations` | VIEW_INCIDENT | capability-matched, with reasons |
| POST | `/v1/clusters/rebuild` | VIEW_INCIDENT | provisional clusters only |
| GET | `/v1/clusters` | VIEW_INCIDENT | |
| POST | `/v1/clusters/{id}/split` | VIEW_INCIDENT | human split; nothing is deleted |
| POST | `/v1/clusters/{id}/summary` | VIEW_INCIDENT | never invents counts |
| POST | `/v1/resources` | ASSIGN_RESOURCE | `simulated: true` is the only representable value |
| GET | `/v1/resources` | VIEW_INCIDENT | |
| POST | `/v1/dispatch?confirm=true` | ASSIGN_RESOURCE | **400 without `confirm=true`** |
| PATCH | `/v1/dispatch/{id}` | authenticated | validates the transition |
| POST | `/v1/alerts` | PUBLISH_ALERT | requires `confirm: true` in the body |
| POST | `/v1/sync/push` | CREATE_INCIDENT | batch upload, idempotent |
| GET | `/v1/sync/pull` | VIEW_INCIDENT | `since` cursor |
| GET | `/v1/audit` | EXPORT_AUDIT | hash-chained entries |
| GET | `/v1/stats` | VIEW_INCIDENT | dashboard counters |

## Development keys

`dev-reporter-key` · `dev-relay-key` · `dev-coordinator-key` · `dev-medic-key` ·
`dev-authority-key` · `dev-other-org-key` (a second organisation, for isolation tests).

These are active only when `DMS_API_KEYS` is unset and `DMS_ENV` is not production.
In production with no keys configured, the API authorizes nobody — by design.

## Example

```bash
curl -s localhost:8000/v1/incidents \
  -H "Authorization: Bearer dev-reporter-key" \
  -H "Idempotency-Key: demo-1" \
  -H "Content-Type: application/json" \
  -d '{"source_node_id":"node_a",
       "original_text":"Three people trapped under collapsed building",
       "disaster_types":["BUILDING_COLLAPSE","TRAPPED_PERSON"],
       "urgency":"CRITICAL","severity":90,
       "priority_class":"P0","priority_score":90,
       "sensitivity":"MEDICAL","people_affected":{"value":3,"raw":"Three people"}}'
```
