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
  cluster_id: z.string().nullable().optional(),
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
  kind: z.string().default("IMAGE"),
  has_content: z.boolean().default(false),
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

export const NoteSchema = z.object({
  id: z.string(),
  incident_id: z.string(),
  author_user_id: z.string().nullable().optional(),
  text: z.string(),
  source: z.enum(["text", "voice"]),
  audio_attachment_id: z.string().nullable().optional(),
  created_at: z.string(),
});
export type IncidentNote = z.infer<typeof NoteSchema>;

export const IncidentDetailSchema = z.object({
  incident: IncidentSchema,
  status: z.string(),
  attachments: z.array(AttachmentSchema),
  dispatch: z.array(DispatchSchema),
  notes: z.array(NoteSchema).default([]),
});
export type IncidentDetail = z.infer<typeof IncidentDetailSchema>;

export const ClusterSchema = z.object({
  id: z.string(),
  incident_ids: z.array(z.string()),
  decision: z.string(),
  similarity: z.number(),
  provisional: z.boolean(),
  human_reviewed: z.boolean(),
  rationale: z.array(z.string()).default([]),
});
export type IncidentCluster = z.infer<typeof ClusterSchema>;

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

// --- Live mesh (multi-hop simulation view) ------------------------------------

export const MeshNodeSchema = z.object({
  id: z.string(),
  role: z.string(),
  x: z.number(),
  y: z.number(),
});
export const MeshEdgeSchema = z.object({ a: z.string(), b: z.string() });
export const MeshTopologySchema = z.object({
  name: z.string().default("mesh"),
  nodes: z.array(MeshNodeSchema).default([]),
  edges: z.array(MeshEdgeSchema).default([]),
});
export type MeshTopology = z.infer<typeof MeshTopologySchema>;

export const MeshEventSchema = z.object({
  seq: z.number(),
  round: z.number().default(0),
  type: z.string(),
  from_node: z.string().nullable().optional(),
  to_node: z.string().nullable().optional(),
  bundle_id: z.string().nullable().optional(),
  incident_id: z.string().nullable().optional(),
  hop: z.number().nullable().optional(),
  path: z.array(z.string()).default([]),
  ts: z.number().default(0),
});
export type MeshEvent = z.infer<typeof MeshEventSchema>;

export const MeshMetricsSchema = z
  .object({
    delivered: z.number(),
    expected: z.number(),
    delivery_ratio: z.number(),
    avg_hops: z.number(),
    max_hops: z.number(),
    bundles_transferred: z.number(),
    duplicates_suppressed: z.number(),
    rounds: z.number(),
  })
  .partial();
export type MeshMetrics = z.infer<typeof MeshMetricsSchema>;

export const MeshRunSummarySchema = z.object({
  run_id: z.string().nullable(),
  topology: MeshTopologySchema.optional(),
  metrics: MeshMetricsSchema.default({}),
  done: z.boolean().default(false),
  latest_seq: z.number().default(-1),
});
export type MeshRunSummary = z.infer<typeof MeshRunSummarySchema>;

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
  getMeshLatest: () =>
    request("/v1/mesh/runs/latest", MeshRunSummarySchema).catch(
      () => ({ run_id: null, metrics: {}, done: false, latest_seq: -1 }) as MeshRunSummary,
    ),
  getMeshEvents: (runId: string, since: number) =>
    request(
      `/v1/mesh/runs/${runId}/events?since=${since}`,
      z.object({
        events: z.array(MeshEventSchema),
        latest_seq: z.number(),
        done: z.boolean(),
        metrics: MeshMetricsSchema.default({}),
      }),
    ),
  startMeshSimulation: (body: {
    topology: string;
    nodes?: number;
    width?: number;
    height?: number;
    radius?: number;
    step_delay?: number;
  }) =>
    request(`/v1/mesh/simulate`, z.object({ run_id: z.string() }), {
      method: "POST",
      body: JSON.stringify(body),
    }),
  dispatch: (incidentId: string, resourceId: string, reason: string) =>
    request(
      `/v1/dispatch?confirm=true`,
      z.object({ id: z.string(), status: z.string(), simulated: z.boolean() }),
      {
        method: "POST",
        body: JSON.stringify({ incident_id: incidentId, resource_id: resourceId, reason }),
      },
    ),
  addNote: (incidentId: string, text: string, source: "text" | "voice", audioAttachmentId?: string) =>
    request(`/v1/incidents/${incidentId}/notes`, NoteSchema, {
      method: "POST",
      body: JSON.stringify({ text, source, audio_attachment_id: audioAttachmentId ?? null }),
    }),
  listClusters: () =>
    request("/v1/clusters", z.object({ items: z.array(ClusterSchema) })).catch(() => ({
      items: [] as IncidentCluster[],
    })),
  splitCluster: (clusterId: string, incidentId: string) =>
    request(`/v1/clusters/${clusterId}/split`, ClusterSchema, {
      method: "POST",
      body: JSON.stringify({ incident_id: incidentId }),
    }),
};

// --- Media: attachment bytes, and audio → text → incident ---------------------

/**
 * Fetch an attachment's bytes as an object URL the browser can render.
 *
 * The content endpoint is auth-scoped, and an <img src> cannot carry the bearer
 * token, so we fetch with the header and hand back a blob URL. The caller must
 * URL.revokeObjectURL it when the element unmounts.
 */
async function fetchAttachmentObjectUrl(incidentId: string, attachmentId: string): Promise<string> {
  const response = await fetch(
    `${API_URL}/v1/incidents/${incidentId}/attachments/${attachmentId}/content`,
    { headers: { Authorization: `Bearer ${API_KEY}` } },
  );
  if (!response.ok) {
    throw new ApiError("content_error", `attachment content ${response.status}`, response.status);
  }
  return URL.createObjectURL(await response.blob());
}

export const TranscriptSchema = z.object({
  text: z.string(),
  language: z.string().default("und"),
  low_quality: z.boolean().default(false),
  confidence: z.number().nullable().optional(),
});
export type Transcript = z.infer<typeof TranscriptSchema>;

export const media = {
  fetchAttachmentObjectUrl,
  transcribe: (audioBase64: string, mimeType: string, durationS?: number) =>
    request("/v1/transcribe", TranscriptSchema, {
      method: "POST",
      body: JSON.stringify({
        audio_base64: audioBase64,
        mime_type: mimeType,
        duration_s: durationS ?? null,
      }),
    }),
  compose: (text: string, location?: { latitude: number; longitude: number }) =>
    request(
      "/v1/compose",
      z.object({ id: z.string(), status: z.string(), deduplicated: z.boolean().default(false) }),
      {
        method: "POST",
        body: JSON.stringify({
          text,
          latitude: location?.latitude ?? null,
          longitude: location?.longitude ?? null,
        }),
      },
    ),
  uploadAttachment: (
    incidentId: string,
    file: {
      file_name: string;
      mime_type: string;
      size_bytes: number;
      sha256: string;
      kind: string;
      data_base64: string;
    },
  ) =>
    request(
      `/v1/incidents/${incidentId}/attachments`,
      z.object({ id: z.string(), has_content: z.boolean().default(false) }),
      { method: "POST", body: JSON.stringify(file) },
    ),
};

/** SHA-256 of a byte array as lowercase hex, using the Web Crypto API. */
export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Base64 of an ArrayBuffer, chunked so large files don't blow the call stack. */
export function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

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
