/**
 * Coordinator dashboard.
 *
 * Layout: left command rail + right content pane.
 * Three content views: queue, incident, actions (inbox) | mesh | field report.
 * Operational alerts sit above everything.
 * All API calls, mutations, WebSocket logic, and business rules are unchanged.
 */
import { Suspense, lazy, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ActionPanel } from "./components/ActionPanel";
import { BootSequence } from "./components/BootSequence";
import { ComposePanel } from "./components/ComposePanel";
import { IncidentDetailPanel } from "./components/IncidentDetail";
import { IncidentQueue } from "./components/IncidentQueue";
import { MeshView } from "./components/MeshView";
import { useIncidentSocket } from "./hooks/useIncidentSocket";
import { useLocalStorageState } from "./hooks/useLocalStorageState";
import { ApiError, api, relativeTime, type PriorityClass } from "./lib/api";

const StormBackground = lazy(() =>
  import("./components/StormBackground").then((m) => ({ default: m.StormBackground })),
);

const REFRESH_MS = 20000;

function HudTile({
  label,
  value,
  tone,
  onClick,
  title,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "danger" | "ok";
  onClick?: () => void;
  title?: string;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      className={`hud-tile${tone ? ` hud-tile-${tone}` : ""}`}
      onClick={onClick}
      title={title}
    >
      <span className="hud-tile-label">{label}</span>
      <span className="hud-tile-value">{value}</span>
    </Tag>
  );
}

export default function App() {
  const [filter, setFilter] = useState<PriorityClass | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNodesModal, setShowNodesModal] = useState(false);
  const [view, setView] = useState<"inbox" | "mesh" | "report">("inbox");
  const [stormEnabled, setStormEnabled] = useLocalStorageState("dms.stormBackground", true);
  const queryClient = useQueryClient();
  useIncidentSocket(queryClient);

  const incidents = useQuery({
    queryKey: ["incidents", filter],
    queryFn: () => api.listIncidents(filter === "ALL" ? undefined : filter),
    refetchInterval: REFRESH_MS,
    retry: 1,
  });

  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: REFRESH_MS,
    retry: 1,
  });

  const nodes = useQuery({
    queryKey: ["nodes"],
    queryFn: api.listNodes,
    refetchInterval: REFRESH_MS,
    retry: 1,
  });

  const detail = useQuery({
    queryKey: ["incident", selectedId],
    queryFn: () => api.getIncident(selectedId!),
    enabled: Boolean(selectedId),
    refetchInterval: REFRESH_MS,
  });

  const recommendations = useQuery({
    queryKey: ["recommendations", selectedId],
    queryFn: () => api.recommendations(selectedId!),
    enabled: Boolean(selectedId),
    refetchInterval: REFRESH_MS,
  });

  const clusters = useQuery({
    queryKey: ["clusters"],
    queryFn: api.listClusters,
    refetchInterval: REFRESH_MS,
    retry: 1,
  });
  const [openClusterId, setOpenClusterId] = useState<string | null>(null);

  const offline = incidents.error instanceof ApiError && incidents.error.code === "offline";
  const stale = incidents.isStale && incidents.isFetching === false && offline;
  const items = incidents.data?.items ?? [];

  useEffect(() => {
    if (!selectedId && items.length > 0) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["incidents"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["incident", selectedId] });
    queryClient.invalidateQueries({ queryKey: ["nodes"] });
    queryClient.invalidateQueries({ queryKey: ["recommendations", selectedId] });
    queryClient.invalidateQueries({ queryKey: ["clusters"] });
  };

  const acknowledge = useMutation({
    mutationFn: () => api.acknowledge(selectedId!),
    onSuccess: invalidate,
  });

  const dispatch = useMutation({
    mutationFn: ({ resourceId, reason }: { resourceId: string; reason: string }) =>
      api.dispatch(selectedId!, resourceId, reason),
    onSuccess: invalidate,
  });

  const splitCluster = useMutation({
    mutationFn: (incidentId: string) => api.splitCluster(openClusterId!, incidentId),
    onSuccess: invalidate,
  });

  const nodeList = nodes.data?.items ?? [];
  const totalNearbyPeers = nodeList.reduce((sum, n) => sum + (n.nearby_peers ?? 0), 0);
  const totalConnectedPeople =
    stats.data?.connected_people ?? (nodeList.length + totalNearbyPeers);

  const p0Count = stats.data?.unacknowledged_p0 ?? 0;

  return (
    <div className="app">
      <BootSequence />
      <Suspense fallback={null}>
        <StormBackground enabled={stormEnabled} />
      </Suspense>

      {/* ── LEFT COMMAND RAIL ── */}
      <aside className="command-rail">
        <div className="brand">
          <div className="brand-mark">
            <img
              src="/app_logo.png"
              alt="DisasterMesh Logo"
              style={{ width: 28, height: 28, borderRadius: 6, objectFit: "contain" }}
            />
            <span className="brand-title">
              DISASTER<br />MESH
            </span>
          </div>
          <span className="brand-sub">Sentinel · Command</span>
        </div>

        {/* System status */}
        <span className={`system-status${offline ? " degraded" : ""}`}>
          <span className="status-dot" aria-hidden="true" />
          {offline ? "SYSTEM DEGRADED" : "SYSTEM ONLINE"}
        </span>

        {/* Navigation */}
        <nav className="rail-nav" role="tablist">
          {(["inbox", "mesh", "report"] as const).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              className={`rail-nav-btn${view === v ? " active" : ""}`}
              onClick={() => setView(v)}
            >
              <span className="rail-nav-indicator" />
              {v === "inbox" ? "Command" : v === "mesh" ? "Mesh" : "Report"}
            </button>
          ))}
        </nav>

        {/* HUD — compact stats */}
        <div className="rail-hud">
          <HudTile
            label="P0 UNACK'D"
            value={stats.data?.unacknowledged_p0 ?? "—"}
            sub=""
            tone={p0Count > 0 ? "danger" : undefined}
          />
          <HudTile label="ACTIVE" value={stats.data?.incidents ?? "—"} sub="" />
          <HudTile
            label="NETWORK"
            value={totalConnectedPeople}
            sub=""
            onClick={() => setShowNodesModal(true)}
            title="View node telemetry"
          />
          <HudTile label="DISPATCHED" value={stats.data?.dispatch_orders ?? "—"} sub="" />
        </div>

        {/* Controls */}
        <div className="rail-controls">
          <button
            className={`icon-toggle${stormEnabled ? " active" : ""}`}
            onClick={() => setStormEnabled((v) => !v)}
            title="Toggle storm background"
            aria-pressed={stormEnabled}
          >
            ⛈ {stormEnabled ? "ON" : "OFF"}
          </button>
          <button className="icon-toggle" onClick={invalidate} title="Refresh now">
            ↻
          </button>
        </div>
      </aside>

      {/* ── MAIN CONTENT ── */}
      <main className="main-content">
        {/* Banners */}
        {offline && (
          <div className="banner offline" role="status">
            Gateway unreachable — last data shown{stale ? " (stale)" : ""}. Mesh keeps working.
          </div>
        )}
        {p0Count > 0 && (
          <div className="banner" role="alert">
            {p0Count} critical P0 incident{p0Count > 1 ? "s" : ""} awaiting acknowledgement
          </div>
        )}

        {view === "mesh" && <MeshView />}

        {view === "report" && (
          <ComposePanel
            onSent={() => {
              invalidate();
              setView("inbox");
            }}
          />
        )}

        {view === "inbox" && (
          <div className="columns">
            <div className="column">
              {incidents.isLoading ? (
                <p className="empty">Loading queue…</p>
              ) : incidents.error && !offline ? (
                <p className="error">{(incidents.error as Error).message}</p>
              ) : (
                <IncidentQueue
                  incidents={items}
                  selectedId={selectedId}
                  filter={filter}
                  onFilter={setFilter}
                  onSelect={setSelectedId}
                  clusters={clusters.data?.items ?? []}
                  onOpenCluster={setOpenClusterId}
                />
              )}
            </div>

            <div className="column detail">
              {!selectedId ? (
                <p className="empty">Select an incident from the queue</p>
              ) : detail.isLoading ? (
                <p className="empty">Loading incident…</p>
              ) : detail.error ? (
                <p className="error">{(detail.error as Error).message}</p>
              ) : detail.data ? (
                <IncidentDetailPanel detail={detail.data} onNotesChanged={invalidate} />
              ) : null}
            </div>

            <div className="column">
              {detail.data ? (
                <ActionPanel
                  detail={detail.data}
                  recommendations={recommendations.data?.items ?? []}
                  busy={acknowledge.isPending || dispatch.isPending}
                  onAcknowledge={() => acknowledge.mutate()}
                  onDispatch={(resourceId, reason) => dispatch.mutate({ resourceId, reason })}
                />
              ) : (
                <p className="empty">No incident selected</p>
              )}
              {dispatch.error && <p className="error">{(dispatch.error as Error).message}</p>}
              {acknowledge.error && <p className="error">{(acknowledge.error as Error).message}</p>}
            </div>
          </div>
        )}
      </main>

      {/* ── NODE TELEMETRY MODAL ── */}
      {showNodesModal && (
        <div className="nodes-modal-overlay" onClick={() => setShowNodesModal(false)}>
          <div className="nodes-modal" onClick={(e) => e.stopPropagation()}>
            <div className="nodes-modal-header">
              <h2>MESH NODE TELEMETRY</h2>
              <button onClick={() => setShowNodesModal(false)} aria-label="Close">✕</button>
            </div>
            <div className="nodes-modal-body">
              <div className="node-stats-grid">
                <div className="node-stat">
                  <span className="node-stat-label">Connected People</span>
                  <span className="node-stat-value ok">{totalConnectedPeople}</span>
                </div>
                <div className="node-stat">
                  <span className="node-stat-label">Active Nodes</span>
                  <span className="node-stat-value">{nodeList.length}</span>
                </div>
                <div className="node-stat">
                  <span className="node-stat-label">Mesh Peers</span>
                  <span className="node-stat-value">{totalNearbyPeers}</span>
                </div>
              </div>

              {nodeList.length === 0 ? (
                <p className="empty">No mobile nodes currently reporting heartbeat</p>
              ) : (
                <table className="nodes-table">
                  <thead>
                    <tr>
                      <th>Node ID</th>
                      <th>Role</th>
                      <th>Battery</th>
                      <th>Peers</th>
                      <th>Queued</th>
                      <th>Last Seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nodeList.map((node) => {
                      const bat = node.battery_percent;
                      const batClass =
                        bat > 50 ? "battery-high" : bat > 20 ? "battery-med" : "battery-low";
                      return (
                        <tr key={node.node_id}>
                          <td><code>{node.node_id}</code></td>
                          <td>{node.role.replace("_", " ")}</td>
                          <td>
                            <span className={`battery-badge ${batClass}`}>
                              {bat}%
                            </span>
                          </td>
                          <td>{node.nearby_peers}</td>
                          <td>{node.stored_bundles}</td>
                          <td>
                            {node.last_seen
                              ? new Date(node.last_seen).toLocaleTimeString()
                              : "Just now"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}

              <div className="tunnel-helper">
                <h4>📡 Phone Connectivity</h4>
                <p>
                  <strong>USB (ADB):</strong>{" "}
                  <code>adb reverse tcp:8000 tcp:8000</code> → set app URL to{" "}
                  <code>http://127.0.0.1:8000</code>
                </p>
                <p>
                  <strong>Public tunnel:</strong>{" "}
                  <code>npx localtunnel --port 8000</code> or{" "}
                  <code>cloudflared tunnel --url http://localhost:8000</code>
                </p>
                <p>
                  <strong>Same Wi-Fi:</strong>{" "}
                  <code>http://&lt;your-pc-ip&gt;:8000</code>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── CLUSTER MODAL ── */}
      {openClusterId && (() => {
        const activeCluster = (clusters.data?.items ?? []).find((c) => c.id === openClusterId);
        if (!activeCluster) return null;
        const members = items.filter((i) => activeCluster.incident_ids.includes(i.id));
        return (
          <div className="nodes-modal-overlay" onClick={() => setOpenClusterId(null)}>
            <div className="nodes-modal" onClick={(e) => e.stopPropagation()}>
              <div className="nodes-modal-header">
                <h2>POSSIBLE DUPLICATE REPORTS</h2>
                <button onClick={() => setOpenClusterId(null)} aria-label="Close">✕</button>
              </div>
              <div className="nodes-modal-body">
                <p className="simulated-note" style={{ marginBottom: "var(--s4)" }}>
                  Grouped by similarity (text, location, timing) — never merged automatically.
                  Confirm they are the same event, or split out any that are not.
                </p>
                {members.map((incident) => (
                  <div key={incident.id} className="recommendation" style={{ marginBottom: "var(--s3)" }}>
                    <PriorityBadgeInline priority={incident.priority_class} />
                    <p style={{ margin: "var(--s2) 0 var(--s1)", fontSize: "13px" }}>
                      {incident.original_text}
                    </p>
                    <p className="simulated-note">
                      from {incident.source_node_id} · {relativeTime(incident.reported_at)}
                    </p>
                    <button
                      onClick={() => splitCluster.mutate(incident.id)}
                      disabled={splitCluster.isPending}
                      style={{ marginTop: "var(--s2)" }}
                    >
                      Split — not the same event
                    </button>
                  </div>
                ))}
                {splitCluster.error && (
                  <p className="error">{(splitCluster.error as Error).message}</p>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

function PriorityBadgeInline({ priority }: { priority: string }) {
  return <span className={`badge ${priority.toLowerCase()}`}>{priority}</span>;
}
