/** Contract tests for the dashboard's parsing and formatting layer. */
import { describe, expect, it } from "vitest";

import {
  IncidentSchema, PageSchema, peopleLabel, priorityLabel, relativeTime,
} from "../lib/api";

const INCIDENT = {
  id: "inc_1",
  source_node_id: "A",
  original_text: "Three people trapped under collapsed building",
  source_language: "en",
  disaster_types: ["BUILDING_COLLAPSE"],
  urgency: "CRITICAL",
  severity: 90,
  classification_confidence: 0.8,
  people_affected: { value: 3, raw: "Three people", approximate: false },
  conditions: [{ type: "TRAPPED", raw: "trapped" }],
  priority_class: "P0",
  priority_score: 90,
  priority_explanation: ["urgency CRITICAL → base 60"],
  status: "RECEIVED",
  verification_status: "AI_CLASSIFIED",
  reported_at: "2026-01-01T00:00:00+00:00",
  updated_at: "2026-01-01T00:00:00+00:00",
};

describe("schema validation", () => {
  it("parses a well-formed incident", () => {
    const parsed = IncidentSchema.parse(INCIDENT);
    expect(parsed.priority_class).toBe("P0");
    expect(parsed.people_affected.value).toBe(3);
  });

  it("rejects an unknown priority class rather than rendering it", () => {
    expect(() => IncidentSchema.parse({ ...INCIDENT, priority_class: "P9" })).toThrow();
  });

  it("rejects a missing required field", () => {
    const { original_text, ...incomplete } = INCIDENT;
    expect(() => IncidentSchema.parse(incomplete)).toThrow();
  });

  it("accepts an unknown people count", () => {
    const parsed = IncidentSchema.parse({
      ...INCIDENT,
      people_affected: { value: null, raw: "several", approximate: true },
    });
    expect(parsed.people_affected.value).toBeNull();
  });

  it("parses a page envelope", () => {
    const page = PageSchema.parse({ items: [INCIDENT], total: 1, limit: 50, offset: 0 });
    expect(page.items).toHaveLength(1);
  });
});

describe("display helpers", () => {
  it("gives every priority a text label, not just a colour", () => {
    expect(priorityLabel("P0")).toBe("P0 Critical");
    expect(priorityLabel("P1")).toBe("P1 Urgent");
    expect(priorityLabel("P3")).toBe("P3 Routine");
  });

  it("never renders an unknown count as zero", () => {
    expect(peopleLabel({ value: null, raw: "several", approximate: true })).toContain("Unknown");
    expect(peopleLabel({ value: null, raw: null, approximate: true })).toBe("Unknown");
    expect(peopleLabel({ value: 3, raw: "Three", approximate: false })).toBe("3");
  });

  it("formats relative time", () => {
    const now = new Date("2026-01-01T01:00:00Z");
    expect(relativeTime("2026-01-01T00:59:30Z", now)).toBe("30s ago");
    expect(relativeTime("2026-01-01T00:30:00Z", now)).toBe("30m ago");
    expect(relativeTime("2025-12-31T23:00:00Z", now)).toBe("2h ago");
  });
});
