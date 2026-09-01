/**
 * Coordinator dashboard.
 *
 * Three columns: queue, incident, actions. Operational alerts sit above everything;
 * there are no decorative charts, no map before the incident detail, and no autoplay.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ActionPanel } from "./components/ActionPanel";
import { ComposePanel } from "./components/ComposePanel";
import { IncidentDetailPanel } from "./components/IncidentDetail";
import { IncidentQueue } from "./components/IncidentQueue";
import { MeshSimulation } from "./components/MeshSimulation";
import { MeshView } from "./components/MeshView";
import { ApiError, api, type PriorityClass } from "./lib/api";

const REFRESH_MS = 5000;

function CommandInbox() {
  const [filter, setFilter] = useState<PriorityClass | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNodesModal, setShowNodesModal] = useState(false);
  const [view, setView] = useState<"inbox" | "mesh" | "report">("inbox");
  const queryClient = useQueryClient();

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

  const offline = incidents.error instanceof ApiError && incidents.error.code === "offline";
  const stale = incidents.isStale && incidents.isFetching === false && offline;
  const items = incidents.data?.items ?? [];

  // Auto-select top incident if none selected
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

  const nodeList = nodes.data?.items ?? [];
  const totalNearbyPeers = nodeList.reduce((sum, n) => sum + (n.nearby_peers ?? 0), 0);
  const totalConnectedPeople =
    stats.data?.connected_people ?? (nodeList.length + totalNearbyPeers);

  return (
    <div className="app">
      <header className="topbar">
        <h1>DisasterMesh Sentinel — {view === "inbox" ? "Command Inbox" : "Live Mesh"}</h1>
        <div className="view-toggle" role="tablist">
          <button
            role="tab"
            aria-selected={view === "inbox"}
            className={view === "inbox" ? "active" : ""}
            onClick={() => setView("inbox")}
          >
            Inbox
          </button>
          <button
            role="tab"
            aria-selected={view === "mesh"}
            className={view === "mesh" ? "active" : ""}
            onClick={() => setView("mesh")}
          >
            Mesh
          </button>
          <button
            role="tab"
            aria-selected={view === "report"}
            className={view === "report" ? "active" : ""}
            onClick={() => setView("report")}
          >
            Report
          </button>
        </div>
        <div className="spacer" />
        <div className="counters">
          <span className="urgent">
            Unacknowledged P0 <strong>{stats.data?.unacknowledged_p0 ?? "—"}</strong>
          </span>
          <span>
            Incidents <strong>{stats.data?.incidents ?? "—"}</strong>
          </span>
          <button
            onClick={() => setShowNodesModal(true)}
            title="Click to view detailed node telemetry and connected people"
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              color: "inherit",
              borderRadius: "4px",
              padding: "4px 8px",
              cursor: "pointer",
            }}
          >
            People Connected: <strong>{totalConnectedPeople}</strong> ({nodeList.length} Nodes, {totalNearbyPeers} Peers)
          </button>
          <span>
            Dispatch orders <strong>{stats.data?.dispatch_orders ?? "—"}</strong>
          </span>
          <button
            onClick={invalidate}
            title="Refresh now"
            style={{
              padding: "4px 10px",
              fontSize: "13px",
              cursor: "pointer",
              borderRadius: "4px",
            }}
          >
            ↻ Refresh
          </button>
        </div>
      </header>

      {offline && (
        <div className="banner offline" role="status">
          Gateway unreachable. Showing the last data received{stale ? " (stale)" : ""}. The mesh
          keeps working without it.
        </div>
      )}
      {(stats.data?.unacknowledged_p0 ?? 0) > 0 && (
        <div className="banner" role="alert">
          {stats.data?.unacknowledged_p0} critical incident(s) awaiting acknowledgement.
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
            />
          )}
        </div>

        <div className="column detail">
          {!selectedId ? (
            <p className="empty">Select an incident from the queue.</p>
          ) : detail.isLoading ? (
            <p className="empty">Loading incident…</p>
          ) : detail.error ? (
            <p className="error">{(detail.error as Error).message}</p>
          ) : detail.data ? (
            <IncidentDetailPanel detail={detail.data} />
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
            <p className="empty">No incident selected.</p>
          )}
          {dispatch.error && <p className="error">{(dispatch.error as Error).message}</p>}
          {acknowledge.error && <p className="error">{(acknowledge.error as Error).message}</p>}
        </div>
      </div>
      )}

      {showNodesModal && (
        <div className="nodes-modal-overlay" onClick={() => setShowNodesModal(false)}>
          <div className="nodes-modal" onClick={(e) => e.stopPropagation()}>
            <div className="nodes-modal-header">
              <h2>Connected Mesh Nodes & Live Telemetry</h2>
              <button onClick={() => setShowNodesModal(false)}>✕</button>
            </div>
            <div className="nodes-modal-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
                <div style={{ background: "var(--surface-raised)", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
                  <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--text-dim)", display: "block" }}>Total Connected People</span>
                  <strong style={{ fontSize: "20px", color: "var(--ok)" }}>{totalConnectedPeople}</strong>
                </div>
                <div style={{ background: "var(--surface-raised)", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
                  <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--text-dim)", display: "block" }}>Active Mobile Nodes</span>
                  <strong style={{ fontSize: "20px" }}>{nodeList.length}</strong>
                </div>
                <div style={{ background: "var(--surface-raised)", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
                  <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--text-dim)", display: "block" }}>Direct Mesh Peers</span>
                  <strong style={{ fontSize: "20px" }}>{totalNearbyPeers}</strong>
                </div>
              </div>

              {nodeList.length === 0 ? (
                <p className="empty">No mobile nodes currently reporting heartbeat.</p>
              ) : (
                <table className="nodes-table">
                  <thead>
                    <tr>
                      <th>Node ID</th>
                      <th>Role</th>
                      <th>Battery</th>
                      <th>Peers</th>
                      <th>Queued Bundles</th>
                      <th>Last Heartbeat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nodeList.map((node) => {
                      const bat = node.battery_percent;
                      const batClass =
                        bat > 50 ? "battery-high" : bat > 20 ? "battery-med" : "battery-low";
                      return (
                        <tr key={node.node_id}>
                          <td>
                            <code>{node.node_id}</code>
                          </td>
                          <td>{node.role.replace("_", " ")}</td>
                          <td>
                            <span className={`battery-badge ${batClass}`}>
                              🔋 {bat}%
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
                <h4>📡 Port Forwarding & Phone Connectivity Options:</h4>
                <p>
                  <strong>1. USB Port Forwarding (Recommended for USB physical phones):</strong>
                  <br />
                  Run: <code>adb reverse tcp:8000 tcp:8000</code>
                  <br />
                  In App, set URL to: <code>http://127.0.0.1:8000</code>
                </p>
                <p>
                  <strong>2. Public Cloud Tunnel (Connect from any network / cellular):</strong>
                  <br />
                  Run: <code>npx localtunnel --port 8000</code> or <code>cloudflared tunnel --url http://localhost:8000</code>
                  <br />
                  In App, enter the public HTTPS URL.
                </p>
                <p>
                  <strong>3. Same Wi-Fi Network:</strong>
                  <br />
                  In App, enter your PC's IP: <code>http://&lt;your-pc-ip&gt;:8000</code>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<"inbox" | "simulation">("simulation");

  return (
    <div className="app-shell">
      <nav className="view-nav" aria-label="Primary views">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">DM</span>
          <span><strong>DisasterMesh</strong><small>Sentinel</small></span>
        </div>
        <div className="view-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={view === "inbox"}
            onClick={() => setView("inbox")}
          >
            Command inbox
          </button>
          <button
            role="tab"
            aria-selected={view === "simulation"}
            onClick={() => setView("simulation")}
          >
            Mesh simulation
          </button>
        </div>
        <span className="prototype-label">Offline prototype</span>
      </nav>
      {view === "inbox" ? <CommandInbox /> : <MeshSimulation />}
    </div>
  );
}
