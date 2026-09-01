/** Status badges. Every badge pairs its colour with a word. */
import type { Incident, PriorityClass } from "../lib/api";
import { priorityLabel } from "../lib/api";

export function PriorityBadge({ priority }: { priority: PriorityClass }) {
  return (
    <span className={`badge ${priority.toLowerCase()}`} title={`Priority ${priority}`}>
      {priorityLabel(priority)}
    </span>
  );
}

/**
 * Verification state. An outlined badge means unverified; a solid one means a human
 * confirmed it. The distinction between AI-classified and human-verified is never
 * left to colour alone.
 */
export function VerificationBadge({ status }: { status: string }) {
  if (status === "HUMAN_VERIFIED") {
    return <span className="badge solid-ok">Human verified</span>;
  }
  if (status === "AI_CLASSIFIED") {
    return <span className="badge ai">AI suggestion</span>;
  }
  return <span className="badge outline">Unverified</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const acknowledged = ["ACKNOWLEDGED", "DISPATCH_REQUESTED", "DISPATCHED", "EN_ROUTE",
                        "ARRIVED", "RESOLVED"].includes(status);
  return (
    <span className={`badge ${acknowledged ? "solid-ok" : "outline"}`}>
      {status.replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

export function LanguageBadge({ incident }: { incident: Incident }) {
  const names: Record<string, string> = { en: "English", hi: "Hindi", ta: "Tamil", und: "Unknown" };
  return (
    <span className="badge outline" title="Language the report was written in">
      {names[incident.source_language] ?? incident.source_language}
    </span>
  );
}
