/**
 * Gateway client.
 *
 * Every response is parsed through a Zod schema before it reaches the UI: a field the
 * server stopped sending must fail loudly here rather than render as "undefined" on a
 * coordinator's screen during an incident.
 */
import { z } from "zod";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "dev-coordinator-key";

export const PriorityClass = z.enum(["P0", "P1", "P2", "P3"]);
export type PriorityClass = z.infer<typeof PriorityClass>;

export const LocationSchema = z.object({
  latitude: z.number(),
  longitude: z.number(),
  accuracy_m: z.number().nullable().optional(),
  shared_precisely: z.boolean().default(true),
});

export const QuantitySchema = z.object({
  value: z.number().nullable(),
  raw: z.string().nullable().optional(),
  approximate: z.boolean().default(false),
  confidence: z.number().nullable().optional(),
});

export const IncidentSchema = z.object({
  id: z.string(),
  organization_id: z.string().nullable().optional(),
  source_node_id: z.string(),
  original_text: z.string(),
  source_language: z.string().default("und"),
  location: LocationSchema.nullable().optional(),
  disaster_types: z.array(z.string()).default([]),
  urgency: z.string().default("UNKNOWN"),
  severity: z.number().default(0),
  classification_confidence: z.number().default(0),
  people_affected: QuantitySchema.default({ value: null, approximate: true }),
  conditions: z.array(z.object({ type: z.string(), raw: z.string().nullable().optional() })).default([]),
  priority_class: PriorityClass.default("P3"),
  priority_score: z.number().default(0),
  priority_explanation: z.array(z.string()).default([]),
  status: z.string().default("RECEIVED"),
  verification_status: z.string().default("UNVERIFIED"),
  reported_at: z.string(),
  updated_at: z.string(),
  redacted: z.array(z.string()).optional(),
});
export type Incident = z.infer<typeof IncidentSchema>;

export const PageSchema = z.object({
  items: z.array(IncidentSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
});

export const AttachmentSchema = z.object({
  id: z.string(),
  file_name: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  sha256: z.string(),
  verified: z.boolean(),
});

export const DispatchSchema = z.object({
  id: z.string(),
  incident_id: z.string(),
  resource_id: z.string(),
  status: z.string(),
  recommended_reason: z.string().optional().default(""),
  simulated: z.boolean().default(true),
  authorized_by: z.string().nullable().optional(),
});
export type DispatchOrder = z.infer<typeof DispatchSchema>;

export const IncidentDetailSchema = z.object({
  incident: IncidentSchema,
  status: z.string(),
  attachments: z.array(AttachmentSchema),
  dispatch: z.array(DispatchSchema),
});
export type IncidentDetail = z.infer<typeof IncidentDetailSchema>;

export const RecommendationSchema = z.object({
  resource_id: z.string(),
  kind: z.string(),
  label: z.string(),
  score: z.number(),
  reason: z.string(),
});
export type Recommendation = z.infer<typeof RecommendationSchema>;

export const StatsSchema = z.object({
  incidents: z.number(),
  by_priority: z.record(z.string(), z.number()).default({}),
  by_status: z.record(z.string(), z.number()).default({}),
  resources: z.number().default(0),
  dispatch_orders: z.number().default(0),
  unacknowledged_p0: z.number().default(0),
  connected_nodes: z.number().default(0),
  connected_people: z.number().default(0),
});
export type Stats = z.infer<typeof StatsSchema>;

export const NodeSchema = z.object({
  node_id: z.string(),
  role: z.string().default("CITIZEN_REPORTER"),
  battery_percent: z.number().default(100),
  nearby_peers: z.number().default(0),
  stored_bundles: z.number().default(0),
  organization_id: z.string().nullable().optional(),
  last_seen: z.string().nullable().optional(),
  last_seen_at: z.string().nullable().optional(),
});
export type NodeInfo = z.infer<typeof NodeSchema>;

export class ApiError extends Error {
  constructor(readonly code: string, message: string, readonly status: number) {
    super(message);
  }
}

/**
 * Fetch and validate. The generic is inferred from the schema's *output* type, so a
 * field with a Zod default is required downstream rather than leaking `undefined`
 * into a component.
 */
async function request<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  init?: RequestInit,
): Promise<z.infer<S>> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch (cause) {
    // The gateway is optional by design; the UI must say so rather than hang.
    throw new ApiError("offline", "gateway unreachable — showing last known data", 0);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(body.error ?? "error", body.detail ?? response.statusText, response.status);
  }
  return schema.parse(body);
}

export const api = {
  listIncidents: (priority?: PriorityClass) =>
    request(`/v1/incidents${priority ? `?priority=${priority}` : ""}`, PageSchema),
  getIncident: (id: string) => request(`/v1/incidents/${id}`, IncidentDetailSchema),
  stats: () => request("/v1/stats", StatsSchema),
  listNodes: () =>
    request("/v1/nodes", z.object({ items: z.array(NodeSchema) })).catch(() => ({ items: [] })),
  recommendations: (id: string) =>
    request(
      `/v1/incidents/${id}/recommendations`,
      z.object({ items: z.array(RecommendationSchema), advisory: z.string() }),
    ),
  acknowledge: (id: string, note?: string) =>
    request(
      `/v1/incidents/${id}/acknowledge`,
      z.object({ id: z.string(), status: z.string(), already_acknowledged: z.boolean() }),
      {
        method: "POST",
        headers: { "Idempotency-Key": `ack-${id}` },
        body: JSON.stringify({ node_id: "dashboard", note }),
      },
    ),
  dispatch: (incidentId: string, resourceId: string, reason: string) =>
    request(
      `/v1/dispatch?confirm=true`,
      z.object({ id: z.string(), status: z.string(), simulated: z.boolean() }),
      {
        method: "POST",
        body: JSON.stringify({ incident_id: incidentId, resource_id: resourceId, reason }),
      },
    ),
};

/** Human-readable label for a priority. Colour is never the only signal. */
export function priorityLabel(priority: PriorityClass): string {
  return {
    P0: "P0 Critical",
    P1: "P1 Urgent",
    P2: "P2 Operational",
    P3: "P3 Routine",
  }[priority];
}

export function peopleLabel(quantity: Incident["people_affected"]): string {
  if (quantity.value === null || quantity.value === undefined) {
    return quantity.raw ? `Unknown ("${quantity.raw}")` : "Unknown";
  }
  return `${quantity.value}`;
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
