import { describe, expect, it } from "vitest";

import { getScenarioState, SCENARIOS } from "../components/MeshSimulation";

describe("mesh simulation scenarios", () => {
  it("reroutes around the failed primary relay", () => {
    const scenario = SCENARIOS.find((item) => item.id === "relay-failure")!;
    const before = getScenarioState(scenario, 2);
    const after = getScenarioState(scenario, 5);

    expect(before.route).toEqual(["reporter", "relay-west", "coordinator"]);
    expect(after.failed).toBe(true);
    expect(after.route).toEqual(["reporter", "relay-north", "relay-east", "coordinator"]);
    expect(after.route).not.toContain("relay-west");
  });

  it("retains destination inventory and skips received media chunks", () => {
    const scenario = SCENARIOS.find((item) => item.id === "media-resume")!;
    const interrupted = getScenarioState(scenario, 6);
    const resumed = getScenarioState(scenario, 9);

    expect(interrupted.chunksReceived).toBe(3);
    expect(resumed.chunksReceived).toBe(4);
    expect(resumed.chunksSkipped).toBe(3);
  });

  it("avoids an overloaded relay without marking it offline", () => {
    const scenario = SCENARIOS.find((item) => item.id === "congestion-avoidance")!;
    const before = getScenarioState(scenario, 2);
    const after = getScenarioState(scenario, 4);

    expect(before.route).toEqual(["reporter", "relay-west", "coordinator"]);
    expect(after.congested).toBe(true);
    expect(after.failed).toBe(false);
    expect(after.route).toEqual(["reporter", "relay-north", "relay-east", "coordinator"]);
  });

  it("holds carried chunks until the destination is reachable", () => {
    const scenario = SCENARIOS.find((item) => item.id === "store-carry-forward")!;
    const isolated = getScenarioState(scenario, 7);
    const restored = getScenarioState(scenario, 10);

    expect(isolated.route).toEqual(["reporter", "relay-north"]);
    expect(isolated.chunksReceived).toBe(0);
    expect(restored.route).toEqual(["reporter", "relay-north", "relay-east", "coordinator"]);
    expect(restored.chunksReceived).toBe(2);
  });

  it("counts duplicate offers blocked after a relay rejoins", () => {
    const scenario = SCENARIOS.find((item) => item.id === "relay-rejoin-dedup")!;
    const rejoined = getScenarioState(scenario, 10);

    expect(rejoined.route).toEqual(["reporter", "relay-west", "relay-east", "coordinator"]);
    expect(rejoined.chunksSkipped).toBe(3);
    expect(rejoined.duplicatesPrevented).toBe(3);
  });
});
