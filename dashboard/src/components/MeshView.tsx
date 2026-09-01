/**
 * Live multi-hop mesh view.
 *
 * Polls the gateway for a simulation run's event stream and folds it into a picture:
 * nodes as circles, links as lines, and a packet that travels edge-by-edge as the
 * report hops toward the coordinator. Nothing here computes routing — it only renders
 * the events the simulator already produced, the same stream the terminal view reads.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type MeshEvent, type MeshMetrics, type MeshTopology } from "../lib/api";

const POLL_MS = 700;
const HOP_FLASH_MS = 1400;

type Roleish = string;

function roleColor(role: Roleish): string {
  if (role === "CITIZEN_REPORTER") return "#f59e0b";
  if (role === "EVENT_COORDINATOR") return "#22c55e";
  return "#60a5fa"; // relays and everyone else
}

interface Hop {
  key: string;
  from: string;
  to: string;
  at: number;
}

export function MeshView() {
  const [runId, setRunId] = useState<string | null>(null);
  const [sinceSeq, setSinceSeq] = useState(-1);
  const [topology, setTopology] = useState<MeshTopology | null>(null);
  const [metrics, setMetrics] = useState<MeshMetrics>({});
  const [activeHops, setActiveHops] = useState<Hop[]>([]);
  const [delivered, setDelivered] = useState<Set<string>>(new Set());
  const [starting, setStarting] = useState(false);
  const [form, setForm] = useState({ topology: "chain", nodes: 6 });
  const [now, setNow] = useState(Date.now());

  // Adopt the latest run on mount so a run started from the terminal shows up.
  useEffect(() => {
    let cancelled = false;
    api.getMeshLatest().then((s) => {
      if (cancelled || !s.run_id) return;
      setRunId(s.run_id);
      if (s.topology) setTopology(s.topology);
      setSinceSeq(-1);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // A light clock so hop flashes fade even between event polls.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 120);
    return () => clearInterval(id);
  }, []);

  const applyEvents = useCallback((events: MeshEvent[]) => {
    if (events.length === 0) return;
    const newHops: Hop[] = [];
    for (const e of events) {
      if (e.type === "node_added" || e.type === "link_up") {
        // topology already carried via the run summary; ignore here
      } else if (e.type === "hop" && e.from_node && e.to_node) {
        newHops.push({ key: `${e.seq}`, from: e.from_node, to: e.to_node, at: Date.now() });
      } else if (e.type === "delivered" && e.to_node) {
        setDelivered((prev) => new Set(prev).add(e.to_node!));
      }
    }
    if (newHops.length) setActiveHops((prev) => [...prev, ...newHops]);
  }, []);

  const events = useQuery({
    queryKey: ["mesh-events", runId, sinceSeq],
    queryFn: () => api.getMeshEvents(runId!, sinceSeq),
    enabled: Boolean(runId),
    refetchInterval: (q) => (q.state.data?.done ? false : POLL_MS),
  });

  useEffect(() => {
    if (!events.data) return;
    applyEvents(events.data.events);
    if (events.data.events.length) {
      setSinceSeq(events.data.latest_seq);
    }
    if (events.data.metrics) setMetrics(events.data.metrics);
  }, [events.data, applyEvents]);

  // Drop hop flashes once they have faded.
  const liveHops = useMemo(
    () => activeHops.filter((h) => now - h.at < HOP_FLASH_MS),
    [activeHops, now],
  );

  const start = async () => {
    setStarting(true);
    setDelivered(new Set());
    setActiveHops([]);
    setMetrics({});
    try {
      const { run_id } = await api.startMeshSimulation({
        topology: form.topology,
        nodes: form.nodes,
        step_delay: 0.5,
      });
      const summary = await api.getMeshLatest();
      setRunId(run_id);
      if (summary.topology) setTopology(summary.topology);
      setSinceSeq(-1);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="mesh-view">
      <div className="mesh-controls">
        <label>
          Topology&nbsp;
          <select
            value={form.topology}
            onChange={(e) => setForm((f) => ({ ...f, topology: e.target.value }))}
          >
            <option value="chain">Chain (line)</option>
            <option value="grid">Grid</option>
            <option value="geometric">Random scatter</option>
          </select>
        </label>
        <label>
          Nodes&nbsp;
          <input
            type="number"
            min={2}
            max={30}
            value={form.nodes}
            onChange={(e) => setForm((f) => ({ ...f, nodes: Number(e.target.value) }))}
            style={{ width: 60 }}
          />
        </label>
        <button onClick={start} disabled={starting}>
          {starting ? "Starting…" : "▶ Run simulation"}
        </button>
        {runId && (
          <span className="mesh-runid">
            run <code>{runId.slice(0, 12)}</code>
            {events.data?.done ? " · complete" : " · live"}
          </span>
        )}
      </div>

      <div className="mesh-body">
        <MeshCanvas topology={topology} liveHops={liveHops} delivered={delivered} now={now} />
        <MeshMetricsPanel metrics={metrics} topology={topology} />
      </div>
    </div>
  );
}

function MeshCanvas({
  topology,
  liveHops,
  delivered,
  now,
}: {
  topology: MeshTopology | null;
  liveHops: Hop[];
  delivered: Set<string>;
  now: number;
}) {
  if (!topology || topology.nodes.length === 0) {
    return (
      <div className="mesh-canvas empty">
        <p className="empty">No run yet. Pick a topology and press “Run simulation”.</p>
      </div>
    );
  }

  const W = 640;
  const H = 460;
  const pad = 48;
  const xs = topology.nodes.map((n) => n.x);
  const ys = topology.nodes.map((n) => n.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const sx = (x: number) =>
    pad + (maxX === minX ? (W - 2 * pad) / 2 : ((x - minX) / (maxX - minX)) * (W - 2 * pad));
  const sy = (y: number) =>
    pad + (maxY === minY ? (H - 2 * pad) / 2 : ((y - minY) / (maxY - minY)) * (H - 2 * pad));

  const pos = new Map(topology.nodes.map((n) => [n.id, { x: sx(n.x), y: sy(n.y) }]));
  const active = new Set<string>();
  for (const h of liveHops) {
    active.add(h.to);
    active.add(h.from);
  }

  return (
    <svg className="mesh-canvas" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="mesh topology">
      {topology.edges.map((e, i) => {
        const a = pos.get(e.a);
        const b = pos.get(e.b);
        if (!a || !b) return null;
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="var(--border)"
            strokeWidth={1.5}
          />
        );
      })}

      {/* Travelling packets: interpolate from → to over the flash window. */}
      {liveHops.map((h) => {
        const a = pos.get(h.from);
        const b = pos.get(h.to);
        if (!a || !b) return null;
        const t = Math.min(1, (now - h.at) / 900);
        const cx = a.x + (b.x - a.x) * t;
        const cy = a.y + (b.y - a.y) * t;
        return (
          <g key={h.key}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#f59e0b" strokeWidth={2.5} opacity={0.5} />
            <circle cx={cx} cy={cy} r={6} fill="#fbbf24" className="mesh-packet" />
          </g>
        );
      })}

      {topology.nodes.map((n) => {
        const p = pos.get(n.id)!;
        const isDelivered = delivered.has(n.id);
        const isActive = active.has(n.id);
        return (
          <g key={n.id}>
            {(isActive || isDelivered) && (
              <circle cx={p.x} cy={p.y} r={18} fill={roleColor(n.role)} opacity={0.18} />
            )}
            <circle
              cx={p.x}
              cy={p.y}
              r={11}
              fill={roleColor(n.role)}
              stroke={isDelivered ? "#22c55e" : "var(--surface, #111)"}
              strokeWidth={isDelivered ? 3 : 2}
            />
            <text x={p.x} y={p.y - 16} textAnchor="middle" className="mesh-label">
              {n.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function MeshMetricsPanel({
  metrics,
  topology,
}: {
  metrics: MeshMetrics;
  topology: MeshTopology | null;
}) {
  const rows: [string, string][] = [
    ["Delivery ratio", metrics.delivery_ratio != null ? `${Math.round(metrics.delivery_ratio * 100)}%` : "—"],
    ["Delivered", `${metrics.delivered ?? "—"} / ${metrics.expected ?? "—"}`],
    ["Avg hops", `${metrics.avg_hops ?? "—"}`],
    ["Max hops", `${metrics.max_hops ?? "—"}`],
    ["Bundles moved", `${metrics.bundles_transferred ?? "—"}`],
    ["Duplicates suppressed", `${metrics.duplicates_suppressed ?? "—"}`],
    ["Rounds", `${metrics.rounds ?? "—"}`],
  ];
  return (
    <aside className="mesh-metrics">
      <h3>{topology?.name ?? "Mesh"}</h3>
      <p className="mesh-sub">
        {topology ? `${topology.nodes.length} nodes · ${topology.edges.length} links` : ""}
      </p>
      <dl>
        {rows.map(([k, v]) => (
          <div key={k} className="mesh-metric-row">
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mesh-legend">
        <span><i style={{ background: roleColor("CITIZEN_REPORTER") }} /> Reporter</span>
        <span><i style={{ background: roleColor("VOLUNTEER_RELAY") }} /> Relay</span>
        <span><i style={{ background: roleColor("EVENT_COORDINATOR") }} /> Coordinator</span>
      </div>
    </aside>
  );
}
