/** Priority inbox. Dense operational list rows — no card soup. */
import { useEffect, useRef, useState } from "react";

import type { Incident, IncidentCluster, PriorityClass } from "../lib/api";
import { peopleLabel, relativeTime } from "../lib/api";
import { PriorityBadge, StatusBadge, VerificationBadge } from "./Badges";

const FILTERS: Array<{ label: string; value: PriorityClass | "ALL" }> = [
  { label: "All", value: "ALL" },
  { label: "P0", value: "P0" },
  { label: "P1", value: "P1" },
  { label: "P2", value: "P2" },
  { label: "P3", value: "P3" },
];

export function IncidentQueue({
  incidents,
  selectedId,
  filter,
  onFilter,
  onSelect,
  clusters = [],
  onOpenCluster,
}: {
  incidents: Incident[];
  selectedId: string | null;
  filter: PriorityClass | "ALL";
  onFilter: (value: PriorityClass | "ALL") => void;
  onSelect: (id: string) => void;
  clusters?: IncidentCluster[];
  onOpenCluster?: (clusterId: string) => void;
}) {
  // New-arrival entrance animation
  const seenIds = useRef<Set<string>>(new Set(incidents.map((i) => i.id)));
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set());
  useEffect(() => {
    const incoming = incidents.filter((i) => !seenIds.current.has(i.id)).map((i) => i.id);
    if (incoming.length > 0) {
      setFreshIds(new Set(incoming));
      incoming.forEach((id) => seenIds.current.add(id));
      const t = setTimeout(() => setFreshIds(new Set()), 900);
      return () => clearTimeout(t);
    }
  }, [incidents]);

  const clusterById = new Map(clusters.map((c) => [c.id, c]));

  return (
    <div>
      <div className="feed-head">
        <h2>Live Incident Feed</h2>
        <span className="feed-live">
          <span className="status-dot" aria-hidden="true" />
          LIVE
        </span>
      </div>
      <p className="feed-count">{incidents.length} ACTIVE</p>

      <div className="filters" role="group" aria-label="Filter by priority">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            aria-pressed={filter === option.value}
            onClick={() => onFilter(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {incidents.length === 0 ? (
        <p className="empty">No incidents match this filter</p>
      ) : (
        <div className="queue">
          {incidents.map((incident) => {
            const cluster = incident.cluster_id ? clusterById.get(incident.cluster_id) : undefined;
            const isFresh = freshIds.has(incident.id);
            const isSelected = selectedId === incident.id;
            return (
              <button
                key={incident.id}
                className={`incident-row${isFresh ? " card-enter" : ""}`}
                aria-current={isSelected}
                onClick={() => onSelect(incident.id)}
              >
                {/* Priority accent edge */}
                <span
                  className={`row-accent ${incident.priority_class.toLowerCase()}`}
                  aria-hidden="true"
                />

                <div className="row-body">
                  {/* Badge row */}
                  <div className="row-badges">
                    <PriorityBadge priority={incident.priority_class} />
                    <VerificationBadge status={incident.verification_status} />
                    {cluster && cluster.incident_ids.length > 1 && (
                      <span
                        className="badge outline cluster-badge"
                        title="Possibly duplicate reports — human review required"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenCluster?.(cluster.id);
                        }}
                      >
                        ⧉ {cluster.incident_ids.length} similar
                      </span>
                    )}
                  </div>

                  {/* Incident title text — dominant */}
                  <p className="row-title">{incident.original_text}</p>

                  {/* Metadata strip */}
                  <div className="row-meta">
                    <span>{incident.disaster_types.join(", ") || "unclassified"}</span>
                    <span>·</span>
                    <span>{peopleLabel(incident.people_affected)}</span>
                    <span>·</span>
                    <StatusBadge status={incident.status} />
                  </div>
                </div>

                <span className="row-time">{relativeTime(incident.reported_at)}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
