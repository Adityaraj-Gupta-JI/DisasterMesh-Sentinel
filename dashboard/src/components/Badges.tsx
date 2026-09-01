/** Status badges. Sharp edges, not pill soup. Color always paired with a word. */
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
 * Verification state. An outlined badge means unverified; solid means human-confirmed.
 * The distinction is never left to colour alone.
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
  const acknowledged = [
    "ACKNOWLEDGED", "DISPATCH_REQUESTED", "DISPATCHED", "EN_ROUTE", "ARRIVED", "RESOLVED",
  ].includes(status);
  return (
    <span className={`badge ${acknowledged ? "solid-ok" : "outline"}`}>
      {status.replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

export function LanguageBadge({ incident }: { incident: Incident }) {
  const names: Record<string, string> = {
    en: "EN", hi: "HI", ta: "TA", und: "UND",
  };
  return (
    <span className="badge outline" title={`Language: ${incident.source_language}`}>
      {names[incident.source_language] ?? incident.source_language.toUpperCase()}
    </span>
  );
}
