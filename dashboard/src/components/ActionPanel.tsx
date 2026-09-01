/** Coordinator actions: acknowledge, then explicitly confirm a simulated dispatch. */
import { useState } from "react";
import type { IncidentDetail, Recommendation } from "../lib/api";

export function ActionPanel({
  detail,
  recommendations,
  onAcknowledge,
  onDispatch,
  busy,
}: {
  detail: IncidentDetail;
  recommendations: Recommendation[];
  onAcknowledge: () => void;
  onDispatch: (resourceId: string, reason: string) => void;
  busy: boolean;
}) {
  const [pending, setPending] = useState<Recommendation | null>(null);
  const acknowledged = [
    "ACKNOWLEDGED", "DISPATCH_REQUESTED", "DISPATCHED", "EN_ROUTE", "ARRIVED", "RESOLVED",
  ].includes(detail.status);

  return (
    <div>
      <h2>Command Actions</h2>
      <div className="actions">
        {/* Acknowledge — dominant action */}
        <button
          className="ack-tile"
          onClick={onAcknowledge}
          disabled={busy || acknowledged}
        >
          <span className="ack-check">{acknowledged ? "✓" : "○"}</span>
          <span>
            {acknowledged ? "ACKNOWLEDGED" : "ACKNOWLEDGE INCIDENT"}
            <span
              className="ack-sub"
              style={{ display: "block" }}
            >
              Human confirmation required
            </span>
          </span>
        </button>

        {/* Resource recommendations */}
        <section className="section" style={{ marginTop: "var(--s4)" }}>
          <h3>Recommended Resources</h3>
          {recommendations.length === 0 ? (
            <p className="empty">Scanning mesh — no capable resource currently available</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {recommendations.map((option) => (
                <div className="recommendation" key={option.resource_id}>
                  <div className="kind-tag">{option.kind.replace(/_/g, " ")}</div>
                  <strong>{option.label}</strong>
                  <p className="reason">{option.reason}</p>
                  <button
                    onClick={() => setPending(option)}
                    disabled={busy || !acknowledged}
                  >
                    Dispatch {option.kind.replace(/_/g, " ").toLowerCase()}…
                  </button>
                  {!acknowledged && (
                    <p className="simulated-note">Acknowledge the incident first.</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Dispatch confirm sheet */}
        {pending && (
          <div className="confirm-box" role="dialog" aria-label="Confirm dispatch">
            <p>
              Dispatch <strong>{pending.label}</strong> to this incident?
              This is a <strong>simulated</strong> assignment —
              no real emergency service is contacted.
            </p>
            <div style={{ display: "flex", gap: "var(--s2)" }}>
              <button
                className="button-danger"
                onClick={() => {
                  onDispatch(pending.resource_id, pending.reason);
                  setPending(null);
                }}
                disabled={busy}
              >
                Confirm dispatch
              </button>
              <button onClick={() => setPending(null)}>Cancel</button>
            </div>
          </div>
        )}

        <p className="simulated-note">
          All dispatch is simulated and recorded in the audit log.
          Public alerts require government-authority credentials.
        </p>
      </div>
    </div>
  );
}
