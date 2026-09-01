import { useEffect, useMemo, useRef, useState } from "react";

type NodeId = "reporter" | "relay-west" | "relay-north" | "relay-east" | "coordinator";
type ScenarioId =
  | "healthy"
  | "relay-failure"
  | "media-resume"
  | "priority-first"
  | "congestion-avoidance"
  | "store-carry-forward"
  | "relay-rejoin-dedup";

type MeshNode = {
  id: NodeId;
  label: string;
  role: string;
  x: number;
  y: number;
};

type Link = { from: NodeId; to: NodeId };

type Scenario = {
  id: ScenarioId;
  name: string;
  summary: string;
  duration: number;
  failureStep?: number;
};

type ScenarioStage = {
  at: number;
  label: string;
  detail: string;
};

const NODES: MeshNode[] = [
  { id: "reporter", label: "Reporter A", role: "origin", x: 10, y: 51 },
  { id: "relay-west", label: "Relay B", role: "primary relay", x: 32, y: 27 },
  { id: "relay-north", label: "Relay D", role: "alternate relay", x: 35, y: 76 },
  { id: "relay-east", label: "Relay E", role: "bridge relay", x: 63, y: 74 },
  { id: "coordinator", label: "Command C", role: "destination", x: 88, y: 45 },
];

const LINKS: Link[] = [
  { from: "reporter", to: "relay-west" },
  { from: "relay-west", to: "coordinator" },
  { from: "reporter", to: "relay-north" },
  { from: "relay-north", to: "relay-east" },
  { from: "relay-east", to: "coordinator" },
  { from: "relay-west", to: "relay-east" },
];

export const SCENARIOS: Scenario[] = [
  {
    id: "healthy",
    name: "Healthy multihop",
    summary: "A critical report crosses two relays and reaches command without Internet.",
    duration: 10,
  },
  {
    id: "relay-failure",
    name: "Relay failure + reroute",
    summary: "The primary relay drops out. Inventory exchange finds a second route and resumes delivery.",
    duration: 14,
    failureStep: 4,
  },
  {
    id: "media-resume",
    name: "Interrupted media",
    summary: "A six-chunk image resumes from the first missing chunk after contact returns.",
    duration: 14,
  },
  {
    id: "priority-first",
    name: "P0 text beats media",
    summary: "Critical text moves first while routine media remains queued behind it.",
    duration: 12,
  },
  {
    id: "congestion-avoidance",
    name: "Congestion avoidance",
    summary: "Relay B is available but overloaded, so media moves through the quieter alternate path.",
    duration: 13,
    failureStep: 3,
  },
  {
    id: "store-carry-forward",
    name: "Store-carry-forward",
    summary: "No full path exists at first. A relay keeps chunks locally until Command C returns in range.",
    duration: 16,
    failureStep: 5,
  },
  {
    id: "relay-rejoin-dedup",
    name: "Relay rejoins + dedup",
    summary: "A recovered relay offers old chunks, but Command C only accepts unseen packet IDs.",
    duration: 15,
    failureStep: 7,
  },
];

const STAGES: Record<ScenarioId, ScenarioStage[]> = {
  healthy: [
    { at: 0, label: "Discover", detail: "Reporter A finds Relay B and Relay E nearby." },
    { at: 2, label: "Manifest", detail: "Command receives the image manifest before chunks." },
    { at: 5, label: "Forward", detail: "Chunks move hop by hop with inventory checks." },
    { at: 10, label: "Verify", detail: "Command C verifies the final SHA-256 digest." },
  ],
  "relay-failure": [
    { at: 0, label: "Primary path", detail: "Traffic starts on A -> B -> C." },
    { at: 4, label: "Failure", detail: "Relay B stops sending heartbeats." },
    { at: 5, label: "Reroute", detail: "The mesh switches to A -> D -> E -> C." },
    { at: 14, label: "Complete", detail: "Only missing chunks continue on the new path." },
  ],
  "media-resume": [
    { at: 0, label: "Start image", detail: "Six media chunks are announced." },
    { at: 5, label: "Interrupted", detail: "Contact drops after three chunks arrive." },
    { at: 8, label: "Resume", detail: "Command asks for chunks 4, 5, and 6 only." },
    { at: 14, label: "Verified", detail: "The image commits after digest verification." },
  ],
  "priority-first": [
    { at: 0, label: "P0 text", detail: "Critical text is scheduled before media." },
    { at: 5, label: "Media window", detail: "Image chunks start after the urgent report clears." },
    { at: 8, label: "Inventory", detail: "Relays skip chunks the destination already has." },
    { at: 12, label: "Done", detail: "Text and image arrive without priority inversion." },
  ],
  "congestion-avoidance": [
    { at: 0, label: "Fast path", detail: "Relay B is initially the shortest route." },
    { at: 3, label: "Congested", detail: "Queue delay rises on Relay B." },
    { at: 4, label: "Shift path", detail: "Traffic moves to the lower-loss alternate route." },
    { at: 13, label: "Complete", detail: "Delivery finishes without treating B as offline." },
  ],
  "store-carry-forward": [
    { at: 0, label: "Partial contact", detail: "Reporter A can only reach Relay D." },
    { at: 5, label: "Store", detail: "Relay D keeps chunk IDs while Command C is unreachable." },
    { at: 9, label: "Contact restored", detail: "Relay D forwards stored chunks through Relay E." },
    { at: 16, label: "Committed", detail: "Command C verifies and commits the image." },
  ],
  "relay-rejoin-dedup": [
    { at: 0, label: "Alternate path", detail: "The mesh starts on A -> D -> E -> C." },
    { at: 7, label: "Relay rejoins", detail: "Relay B returns with older chunk offers." },
    { at: 8, label: "Dedup", detail: "Command C rejects already-seen packet IDs." },
    { at: 15, label: "Clean finish", detail: "The final route completes with no duplicate sends." },
  ],
};

const byId = new Map(NODES.map((node) => [node.id, node]));

function key(from: NodeId, to: NodeId) {
  return `${from}:${to}`;
}

function routeLinks(route: NodeId[]) {
  return route.slice(0, -1).map((from, index) => key(from, route[index + 1]));
}

function currentStage(scenario: Scenario, step: number) {
  return STAGES[scenario.id].reduce((active, stage) => (step >= stage.at ? stage : active));
}

function routeLabel(route: NodeId[]) {
  return route.map((id) => byId.get(id)!.label.replace("Reporter ", "").replace("Command ", "")).join(" -> ");
}

export function getScenarioState(scenario: Scenario, step: number, forcedFailure = false) {
  const tick = Math.floor(step);
  const failed =
    scenario.id === "relay-failure" &&
    (forcedFailure || tick >= (scenario.failureStep ?? Number.POSITIVE_INFINITY));
  const congested =
    scenario.id === "congestion-avoidance" &&
    (forcedFailure || tick >= (scenario.failureStep ?? Number.POSITIVE_INFINITY));
  const primaryRoute: NodeId[] = ["reporter", "relay-west", "coordinator"];
  const alternateRoute: NodeId[] = ["reporter", "relay-north", "relay-east", "coordinator"];
  const healthyRoute: NodeId[] = ["reporter", "relay-west", "relay-east", "coordinator"];
  const carryRoute: NodeId[] = tick < 9 ? ["reporter", "relay-north"] : alternateRoute;
  const rejoinRoute: NodeId[] = tick < 7 ? alternateRoute : ["reporter", "relay-west", "relay-east", "coordinator"];
  const route =
    scenario.id === "relay-failure"
      ? failed
        ? alternateRoute
        : primaryRoute
      : scenario.id === "congestion-avoidance"
        ? congested
          ? alternateRoute
          : primaryRoute
        : scenario.id === "store-carry-forward"
          ? carryRoute
          : scenario.id === "relay-rejoin-dedup"
            ? rejoinRoute
            : healthyRoute;
  const progress = Math.min(1, step / scenario.duration);

  let chunksReceived = 0;
  let chunksSkipped = 0;
  let duplicatesPrevented = 0;
  if (scenario.id === "media-resume") {
    chunksReceived = tick < 5 ? Math.max(0, tick - 1) : tick < 8 ? 3 : Math.min(6, tick - 5);
    chunksSkipped = tick >= 8 ? 3 : 0;
  } else if (scenario.id === "store-carry-forward") {
    chunksReceived = tick < 9 ? 0 : Math.min(6, tick - 8);
  } else if (scenario.id === "relay-rejoin-dedup") {
    chunksReceived = Math.min(6, Math.max(0, Math.floor(progress * 7)));
    chunksSkipped = tick >= 8 ? Math.min(3, tick - 7) : 0;
    duplicatesPrevented = chunksSkipped;
  } else if (scenario.id === "priority-first") {
    chunksReceived = tick < 5 ? 0 : Math.min(6, tick - 4);
  } else {
    chunksReceived = Math.min(6, Math.max(0, Math.floor(progress * 7)));
  }

  return {
    failed,
    congested,
    route,
    activeLinks: routeLinks(route),
    progress,
    chunksReceived,
    chunksSkipped,
    duplicatesPrevented,
    complete: step >= scenario.duration,
  };
}

function packetPosition(route: NodeId[], progress: number) {
  const segmentCount = route.length - 1;
  const scaled = Math.min(progress * segmentCount, segmentCount - 0.001);
  const segment = Math.floor(scaled);
  const local = scaled - segment;
  const from = byId.get(route[segment])!;
  const to = byId.get(route[segment + 1])!;
  return { x: from.x + (to.x - from.x) * local, y: from.y + (to.y - from.y) * local };
}

function statusText(scenario: Scenario, step: number, failed: boolean, congested: boolean, complete: boolean) {
  if (complete) return "Delivery verified at Command C";
  if (scenario.id === "relay-failure" && failed) return "Relay B offline - route recalculated through D and E";
  if (scenario.id === "congestion-avoidance" && congested) return "Relay B overloaded - traffic shifted to lower-loss route";
  if (scenario.id === "media-resume" && step >= 5 && step < 8) return "Contact lost - three received chunks retained";
  if (scenario.id === "media-resume" && step >= 8) return "Contact restored - requesting only missing chunks";
  if (scenario.id === "priority-first" && step < 5) return "P0 text scheduled ahead of routine image chunks";
  if (scenario.id === "store-carry-forward" && step < 9) return "No end-to-end path - Relay D is carrying stored chunks";
  if (scenario.id === "store-carry-forward" && step >= 9) return "Command C in range - stored chunks flushing forward";
  if (scenario.id === "relay-rejoin-dedup" && step >= 7) return "Relay B rejoined - duplicate packet IDs rejected";
  return "Inventory exchanged - forwarding unseen bundles";
}

export function MeshSimulation() {
  const [scenarioId, setScenarioId] = useState<ScenarioId>("relay-failure");
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [forcedFailure, setForcedFailure] = useState(false);
  const animationFrame = useRef<number>();
  const lastFrame = useRef<number>();

  const scenario = SCENARIOS.find((item) => item.id === scenarioId)!;
  const displayStep = Math.floor(step);
  const state = useMemo(
    () => getScenarioState(scenario, step, forcedFailure),
    [scenario, step, forcedFailure],
  );
  const stage = currentStage(scenario, displayStep);
  const stages = STAGES[scenario.id];

  useEffect(() => {
    if (!playing) {
      lastFrame.current = undefined;
      return;
    }

    const animate = (time: number) => {
      if (lastFrame.current === undefined) lastFrame.current = time;
      const elapsed = (time - lastFrame.current) / 1000;
      lastFrame.current = time;
      setStep((current) => {
        if (current >= scenario.duration) {
          setPlaying(false);
          return current;
        }
        return Math.min(scenario.duration, current + elapsed * 1.65);
      });
      animationFrame.current = window.requestAnimationFrame(animate);
    };

    animationFrame.current = window.requestAnimationFrame(animate);
    return () => {
      if (animationFrame.current !== undefined) window.cancelAnimationFrame(animationFrame.current);
    };
  }, [playing, scenario.duration]);

  const selectScenario = (next: ScenarioId) => {
    setScenarioId(next);
    setStep(0);
    setForcedFailure(false);
    setPlaying(false);
  };

  const reset = () => {
    setStep(0);
    setForcedFailure(false);
    setPlaying(false);
  };

  const packet = packetPosition(state.route, state.progress);
  const activeLinkSet = new Set(state.activeLinks);
  const deliveryPercent = Math.round(state.progress * 100);

  return (
    <main className="mesh-sim">
      <aside className="scenario-rail" aria-label="Simulation scenarios">
        <div className="rail-heading">
          <span className="eyebrow">Demo control</span>
          <h2>Mesh scenarios</h2>
        </div>
        <div className="scenario-list">
          {SCENARIOS.map((item, index) => (
            <button
              key={item.id}
              className="scenario-option"
              aria-pressed={scenario.id === item.id}
              onClick={() => selectScenario(item.id)}
            >
              <span className="scenario-index">0{index + 1}</span>
              <span>
                <strong>{item.name}</strong>
                <small>{item.summary}</small>
              </span>
            </button>
          ))}
        </div>
        <div className="demo-note">
          <span className="status-dot" /> Deterministic visual simulation
          <p>No real emergency service or radio is contacted.</p>
        </div>
      </aside>

      <section className="simulation-workspace">
        <header className="simulation-header">
          <div>
            <span className="eyebrow">Scenario {String(SCENARIOS.indexOf(scenario) + 1).padStart(2, "0")}</span>
            <h2>{scenario.name}</h2>
            <p>{scenario.summary}</p>
          </div>
          <div className="simulation-controls" aria-label="Playback controls">
            <button
              className="control-primary"
              onClick={() => {
                if (state.complete) {
                  setStep(0);
                  setForcedFailure(false);
                  setPlaying(true);
                  return;
                }
                setPlaying((value) => !value);
              }}
            >
              {playing ? "Pause" : state.complete ? "Replay" : "Run"}
            </button>
            <button onClick={reset}>Reset</button>
            {(scenario.id === "relay-failure" || scenario.id === "congestion-avoidance") && (
              <button
                className="failure-control"
                disabled={state.failed || state.congested}
                onClick={() => {
                  setForcedFailure(true);
                  setPlaying(true);
                }}
              >
                {scenario.id === "relay-failure" ? "Fail Relay B" : "Load Relay B"}
              </button>
            )}
          </div>
        </header>

        <div className="simulation-grid">
          <section className="mesh-map" aria-label="Animated mesh topology">
            <div className="map-status" role="status">
              <span className={`status-dot ${state.failed ? "danger" : state.congested ? "warning" : ""}`} />
              {statusText(scenario, displayStep, state.failed, state.congested, state.complete)}
            </div>
            <div className="route-banner">
              <span>{stage.label}</span>
              <strong>{routeLabel(state.route)}</strong>
            </div>
            <svg viewBox="0 0 100 100" role="img" aria-label="Reporter, relay, and coordinator node routes">
              <defs>
                <filter id="packet-glow" x="-100%" y="-100%" width="300%" height="300%">
                  <feGaussianBlur stdDeviation="1.2" result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
              </defs>
              {LINKS.map((link) => {
                const from = byId.get(link.from)!;
                const to = byId.get(link.to)!;
                const active = activeLinkSet.has(key(link.from, link.to));
                return active ? (
                  <line
                    key={`${key(link.from, link.to)}:halo`}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    className="mesh-link-halo"
                  />
                ) : null;
              })}
              {LINKS.map((link) => {
                const from = byId.get(link.from)!;
                const to = byId.get(link.to)!;
                const active = activeLinkSet.has(key(link.from, link.to));
                const failedLink = state.failed && (link.from === "relay-west" || link.to === "relay-west");
                const congestedLink = state.congested && (link.from === "relay-west" || link.to === "relay-west");
                return (
                  <line
                    key={key(link.from, link.to)}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    className={`mesh-link ${active ? "active" : ""} ${failedLink ? "failed" : ""} ${congestedLink ? "congested" : ""}`}
                  />
                );
              })}
              {!state.complete && step > 0.05 && (
                <g className="route-packet" filter="url(#packet-glow)">
                  <circle cx={packet.x} cy={packet.y} r="2.1" />
                  <circle className="packet-core" cx={packet.x} cy={packet.y} r="0.85" />
                </g>
              )}
              {NODES.map((node) => {
                const failed = state.failed && node.id === "relay-west";
                const congested = state.congested && node.id === "relay-west";
                const destination = node.id === "coordinator";
                const active = state.route.includes(node.id);
                return (
                  <g key={node.id} className={`mesh-node ${active ? "active" : ""} ${failed ? "failed" : ""} ${congested ? "congested" : ""}`}>
                    <circle cx={node.x} cy={node.y} r="5.5" />
                    <circle className="node-core" cx={node.x} cy={node.y} r="2" />
                    {failed && <path d={`M ${node.x - 2} ${node.y - 2} L ${node.x + 2} ${node.y + 2} M ${node.x + 2} ${node.y - 2} L ${node.x - 2} ${node.y + 2}`} />}
                    <text x={node.x} y={node.y + (destination ? 10 : 9)} textAnchor="middle">{node.label}</text>
                    <text className="node-role" x={node.x} y={node.y + (destination ? 13 : 12)} textAnchor="middle">{failed ? "OFFLINE" : congested ? "OVERLOADED" : node.role}</text>
                  </g>
                );
              })}
            </svg>
            <div className="map-legend" aria-label="Topology legend">
              <span><i className="legend-line active" /> Active route</span>
              <span><i className="legend-line" /> Available contact</span>
              <span><i className="legend-line congested" /> Congested route</span>
              <span><i className="legend-line failed" /> Failed route</span>
            </div>
          </section>

          <aside className="transfer-panel">
            <section className="transfer-section phase-card">
              <div className="section-title-row">
                <div>
                  <span className="eyebrow">Current stage</span>
                  <h3>{stage.label}</h3>
                </div>
                <span className="transfer-state">00:{String(displayStep).padStart(2, "0")}</span>
              </div>
              <p>{stage.detail}</p>
              <div className="stage-track" aria-label="Scenario stages">
                {stages.map((item) => (
                  <span
                    key={item.at}
                    className={displayStep >= item.at ? "done" : ""}
                    title={`${item.label} at 00:${String(item.at).padStart(2, "0")}`}
                  />
                ))}
              </div>
            </section>

            <div className="metric-strip">
              <div><span>Hop count</span><strong>{state.route.length - 1}</strong></div>
              <div><span>Delivery</span><strong>{deliveryPercent}%</strong></div>
              <div><span>Dupes blocked</span><strong>{state.duplicatesPrevented}</strong></div>
            </div>

            <section className="transfer-section">
              <div className="section-title-row">
                <div>
                  <span className="eyebrow">Destination inventory</span>
                  <h3>Media bundle IMG-7F2A</h3>
                </div>
                <span className={`transfer-state ${state.complete ? "complete" : ""}`}>
                  {state.complete ? "Verified" : "In transit"}
                </span>
              </div>
              <div className="chunk-grid" aria-label={`${state.chunksReceived} of 6 chunks received`}>
                {Array.from({ length: 6 }, (_, index) => {
                  const received = index < state.chunksReceived;
                  return (
                    <div className={`chunk ${received ? "received" : ""}`} key={index}>
                      <span>{index + 1}</span>
                      <small>{received ? "held" : "needed"}</small>
                    </div>
                  );
                })}
              </div>
              <div className="inventory-summary">
                <span><strong>{state.chunksReceived}/6</strong> at destination</span>
                <span><strong>{state.chunksSkipped}</strong> redundant sends skipped</span>
              </div>
            </section>

            <section className="transfer-section event-log">
              <span className="eyebrow">Protocol events</span>
              <ol>
                <li className={displayStep >= 1 ? "done" : ""}><time>00:01</time> Manifest announced</li>
                <li className={displayStep >= 2 ? "done" : ""}><time>00:02</time> Inventory compared</li>
                {scenario.id === "relay-failure" && (
                  <>
                    <li className={state.failed ? "failed" : ""}><time>00:04</time> Relay B heartbeat lost</li>
                    <li className={state.failed ? "done" : ""}><time>00:05</time> Alternate route selected</li>
                  </>
                )}
                {scenario.id === "media-resume" && (
                  <li className={displayStep >= 8 ? "done" : ""}><time>00:08</time> Missing chunk request: 4, 5, 6</li>
                )}
                {scenario.id === "congestion-avoidance" && (
                  <>
                    <li className={state.congested ? "failed" : ""}><time>00:03</time> Relay B queue delay detected</li>
                    <li className={state.congested ? "done" : ""}><time>00:04</time> Lower-loss path selected</li>
                  </>
                )}
                {scenario.id === "store-carry-forward" && (
                  <>
                    <li className={displayStep >= 5 ? "done" : ""}><time>00:05</time> Relay D stores six chunk IDs</li>
                    <li className={displayStep >= 9 ? "done" : ""}><time>00:09</time> Command C contact restored</li>
                  </>
                )}
                {scenario.id === "relay-rejoin-dedup" && (
                  <>
                    <li className={displayStep >= 7 ? "done" : ""}><time>00:07</time> Relay B rejoins mesh</li>
                    <li className={displayStep >= 8 ? "done" : ""}><time>00:08</time> Duplicate packet IDs rejected</li>
                  </>
                )}
                <li className={state.complete ? "done" : ""}><time>00:{scenario.duration}</time> SHA-256 verified and committed</li>
              </ol>
            </section>
          </aside>
        </div>

        <div className="timeline-control">
          <span>00:00</span>
          <input
            type="range"
            min="0"
            max={scenario.duration}
            step="0.1"
            value={step}
            onChange={(event) => {
              setStep(Number(event.target.value));
              setPlaying(false);
            }}
            aria-label="Simulation timeline"
          />
          <span>00:{scenario.duration}</span>
        </div>
      </section>
    </main>
  );
}
