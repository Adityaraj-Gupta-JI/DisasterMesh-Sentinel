/**
 * Live multi-hop mesh view — Spider/Web spatial environment.
 *
 * Node shapes encode role visually: circle = reporter, square = relay,
 * diamond = coordinator. All simulation logic is preserved from the original.
 * Edge styles: solid healthy, dashed degraded (liveHop strands).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type MeshEvent, type MeshMetrics, type MeshTopology } from "../lib/api";

const POLL_MS = 700;
const HOP_FLASH_MS = 1400;

type Roleish = string;

/** Colour by role — same as original, matches CSS tokens */
function roleColor(role: Roleish): string {
  if (role === "CITIZEN_REPORTER") return "#d97e28";    // --p1 amber
  if (role === "EVENT_COORDINATOR") return "#1e8f57";   // --ok green
  return "#2b7dd4";                                      // --p2 mesh blue (relays)
}

/** Node shape by role — the Spider/Web identity visual */
function NodeShape({
  cx,
  cy,
  role,
  isActive,
  isDelivered,
}: {
  cx: number;
  cy: number;
  role: Roleish;
  isActive: boolean;
  isDelivered: boolean;
}) {
  const color = roleColor(role);
  const glowColor = isDelivered ? "#1e8f57" : isActive ? color : "transparent";
  const strokeColor = isDelivered ? "#1e8f57" : "rgba(255,255,255,0.12)";

  // Halo ring for active/delivered nodes
  const halo = (isActive || isDelivered) && (
    <circle cx={cx} cy={cy} r={18} fill={color} opacity={0.12} />
  );

  if (role === "CITIZEN_REPORTER") {
    // Circle — reporters
    return (
      <g>
        {halo}
        {glowColor !== "transparent" && (
          <circle cx={cx} cy={cy} r={14} fill={glowColor} opacity={0.08} />
        )}
        <circle
          cx={cx} cy={cy} r={9}
          fill={color}
          stroke={strokeColor}
          strokeWidth={isDelivered ? 2.5 : 1.5}
        />
      </g>
    );
  }

  if (role === "EVENT_COORDINATOR") {
    // Diamond — coordinator (the centre of the web)
    const s = 10;
    return (
      <g>
        {halo}
        {glowColor !== "transparent" && (
          <circle cx={cx} cy={cy} r={16} fill={glowColor} opacity={0.10} />
        )}
        <polygon
          points={`${cx},${cy - s} ${cx + s},${cy} ${cx},${cy + s} ${cx - s},${cy}`}
          fill={color}
          stroke={strokeColor}
          strokeWidth={isDelivered ? 2 : 1.5}
        />
      </g>
    );
  }

  // Square — relay nodes
  const s = 7;
  return (
    <g>
      {halo}
      {glowColor !== "transparent" && (
        <circle cx={cx} cy={cy} r={14} fill={glowColor} opacity={0.08} />
      )}
      <rect
        x={cx - s} y={cy - s}
        width={s * 2} height={s * 2}
        fill={color}
        stroke={strokeColor}
        strokeWidth={isDelivered ? 2 : 1.5}
        rx={1}
      />
    </g>
  );
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

  useEffect(() => {
    let cancelled = false;
    api.getMeshLatest().then((s) => {
      if (cancelled || !s.run_id) return;
      setRunId(s.run_id);
      if (s.topology) setTopology(s.topology);
      setSinceSeq(-1);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 120);
    return () => clearInterval(id);
  }, []);

  const applyEvents = useCallback((events: MeshEvent[]) => {
    if (events.length === 0) return;
    const newHops: Hop[] = [];
    for (const e of events) {
      if (e.type === "hop" && e.from_node && e.to_node) {
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
    if (events.data.events.length) setSinceSeq(events.data.latest_seq);
    if (events.data.metrics) setMetrics(events.data.metrics);
  }, [events.data, applyEvents]);

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
      {/* Controls bar */}
      <div className="mesh-controls">
        <div className="mesh-controls-left">
          <span className="mesh-controls-title">LIVE MESH</span>
          {runId && (
            <span className="mesh-controls-sub">
              run <code style={{ fontFamily: "var(--font-mono)", color: "var(--mesh)" }}>
                {runId.slice(0, 12)}
              </code>
              {events.data?.done ? " · complete" : " · live"}
            </span>
          )}
        </div>

        <label>
          Topology
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
          Nodes
          <input
            type="number"
            min={2}
            max={30}
            value={form.nodes}
            onChange={(e) => setForm((f) => ({ ...f, nodes: Number(e.target.value) }))}
            style={{ width: 52 }}
          />
        </label>

        <button
          className="mesh-run-btn"
          onClick={start}
          disabled={starting}
        >
          {starting ? "Starting…" : "▶ Run simulation"}
        </button>
      </div>

      {/* Canvas + metrics */}
      <div className="mesh-body">
        <MeshCanvas
          topology={topology}
          liveHops={liveHops}
          delivered={delivered}
          now={now}
        />
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
        <p className="empty">No run yet. Pick a topology and press "Run simulation".</p>
      </div>
    );
  }

  const W = 680;
  const H = 500;
  const pad = 52;
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

  // Active edges (edges touched by live hops)
  const activeEdgeSet = new Set<string>();
  for (const h of liveHops) {
    activeEdgeSet.add(`${h.from}-${h.to}`);
    activeEdgeSet.add(`${h.to}-${h.from}`);
  }

  return (
    <svg
      className="mesh-canvas"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="mesh topology"
    >
      {/* Faint background web-fiber crosshatch */}
      <defs>
        <pattern id="webgrid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
          <path
            d={`M0,0 L40,40 M40,0 L0,40 M20,0 L20,40 M0,20 L40,20`}
            stroke="rgba(43,125,212,0.06)"
            strokeWidth="0.5"
            fill="none"
          />
        </pattern>
        {/* Glowing packet filter */}
        <filter id="packet-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* Edge active glow */}
        <filter id="edge-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Background web grid */}
      <rect width={W} height={H} fill="url(#webgrid)" opacity="1" />

      {/* Edges — spider web strands */}
      {topology.edges.map((e, i) => {
        const a = pos.get(e.a);
        const b = pos.get(e.b);
        if (!a || !b) return null;
        const isActiveEdge = activeEdgeSet.has(`${e.a}-${e.b}`) || activeEdgeSet.has(`${e.b}-${e.a}`);
        return (
          <line
            key={i}
            x1={a.x} y1={a.y}
            x2={b.x} y2={b.y}
            stroke={isActiveEdge ? "rgba(43,125,212,0.65)" : "rgba(255,255,255,0.10)"}
            strokeWidth={isActiveEdge ? 1.5 : 1}
            filter={isActiveEdge ? "url(#edge-glow)" : undefined}
          />
        );
      })}

      {/* Travelling packets — interpolate from → to */}
      {liveHops.map((h) => {
        const a = pos.get(h.from);
        const b = pos.get(h.to);
        if (!a || !b) return null;
        const t = Math.min(1, (now - h.at) / 900);
        const cx = a.x + (b.x - a.x) * t;
        const cy = a.y + (b.y - a.y) * t;
        return (
          <g key={h.key} filter="url(#packet-glow)">
            <circle cx={cx} cy={cy} r={5} fill="#fbbf24" />
          </g>
        );
      })}

      {/* Nodes — spider web junction points */}
      {topology.nodes.map((n) => {
        const p = pos.get(n.id)!;
        const isDelivered = delivered.has(n.id);
        const isActive = active.has(n.id);
        return (
          <g key={n.id}>
            <NodeShape
              cx={p.x}
              cy={p.y}
              role={n.role}
              isActive={isActive}
              isDelivered={isDelivered}
            />
            <text
              x={p.x}
              y={p.y - 18}
              textAnchor="middle"
              className="mesh-label"
            >
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
        {topology ? `${topology.nodes.length} nodes · ${topology.edges.length} links` : "No run"}
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
        <span>
          <i className="legend-circle" style={{ background: roleColor("CITIZEN_REPORTER") }} />
          Reporter
        </span>
        <span>
          <i className="legend-square" style={{ background: roleColor("VOLUNTEER_RELAY") }} />
          Relay
        </span>
        <span>
          <i className="legend-circle" style={{ background: roleColor("EVENT_COORDINATOR") }} />
          Coordinator
        </span>
      </div>
    </aside>
  );
}
