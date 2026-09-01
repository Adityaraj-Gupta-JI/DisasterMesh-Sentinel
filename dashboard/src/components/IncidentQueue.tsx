/** Priority inbox. P0 is dominant without making the screen chaotic. */
import type { Incident, PriorityClass } from "../lib/api";
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
}: {
  incidents: Incident[];
  selectedId: string | null;
  filter: PriorityClass | "ALL";
  onFilter: (value: PriorityClass | "ALL") => void;
  onSelect: (id: string) => void;
}) {
  return (
    <div>
      <h2>Queue</h2>
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
        <p className="empty">No incidents match this filter.</p>
      ) : (
        <div className="queue">
          {incidents.map((incident) => (
            <button
              key={incident.id}
              className={`card ${incident.priority_class.toLowerCase()}`}
              aria-current={selectedId === incident.id}
              onClick={() => onSelect(incident.id)}
            >
              <div className="card-head">
                <PriorityBadge priority={incident.priority_class} />
                <VerificationBadge status={incident.verification_status} />
              </div>
              <p className="card-summary">{incident.original_text}</p>
              <div className="card-meta">
                <span>{incident.disaster_types.join(", ") || "unclassified"}</span>
                <span>People: {peopleLabel(incident.people_affected)}</span>
                <span>{relativeTime(incident.reported_at)}</span>
                <StatusBadge status={incident.status} />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
