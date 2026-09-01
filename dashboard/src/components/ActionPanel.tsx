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
  const acknowledged = ["ACKNOWLEDGED", "DISPATCH_REQUESTED", "DISPATCHED", "EN_ROUTE",
                        "ARRIVED", "RESOLVED"].includes(detail.status);

  return (
    <div>
      <h2>Actions</h2>
      <div className="actions">
        <button
          className={acknowledged ? "" : "button-primary"}
          onClick={onAcknowledge}
          disabled={busy || acknowledged}
        >
          {acknowledged ? "Acknowledged" : "Acknowledge incident"}
        </button>

        <section className="section" style={{ marginTop: "16px" }}>
          <h3>Recommended resources</h3>
          {recommendations.length === 0 ? (
            <p className="empty">No capable resource is available.</p>
          ) : (
            recommendations.map((option) => (
              <div className="recommendation" key={option.resource_id}>
                <strong>{option.label}</strong>
                <p className="reason">{option.reason}</p>
                <button onClick={() => setPending(option)} disabled={busy || !acknowledged}>
                  Dispatch {option.kind.replace(/_/g, " ").toLowerCase()}…
                </button>
                {!acknowledged && (
                  <p className="simulated-note">Acknowledge the incident first.</p>
                )}
              </div>
            ))
          )}
        </section>

        {pending && (
          <div className="confirm-box" role="dialog" aria-label="Confirm dispatch">
            <p>
              Dispatch <strong>{pending.label}</strong> to this incident? This is a
              <strong> simulated </strong>
              assignment — no real emergency service is contacted.
            </p>
            <div style={{ display: "flex", gap: "8px" }}>
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
          All dispatch in this prototype is simulated and recorded in the audit log.
          Public alerts require a separate government-authority credential.
        </p>
      </div>
    </div>
  );
}
