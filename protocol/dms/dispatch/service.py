"""Resource-aware dispatch simulation.

Every order in this system is simulated. No real emergency service is ever contacted.
An AI recommendation is only ever a *recommendation*: an order does not leave
RECOMMENDED without an authorized human confirming it, and every transition is logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..domain.clock import utc
from ..domain.enums import (
    DisasterType,
    DispatchStatus,
    IncidentStatus,
    Permission,
    ResourceKind,
    ResourceStatus,
    Role,
)
from ..domain.errors import DomainError
from ..domain.lifecycle import dispatch_transition
from ..domain.models import DispatchOrder, Incident, Resource
from ..governance.authz import require_permission

#: Which resource kinds are competent for which disaster types.
CAPABILITY_MATRIX: dict[ResourceKind, frozenset[DisasterType]] = {
    ResourceKind.AMBULANCE: frozenset(
        {DisasterType.MEDICAL, DisasterType.ACCIDENT, DisasterType.TRAPPED_PERSON}
    ),
    ResourceKind.MEDICAL_TEAM: frozenset(
        {
            DisasterType.MEDICAL,
            DisasterType.EARTHQUAKE,
            DisasterType.BUILDING_COLLAPSE,
            DisasterType.ACCIDENT,
        }
    ),
    ResourceKind.RESCUE_BOAT: frozenset({DisasterType.FLOOD}),
    ResourceKind.FIRE_UNIT: frozenset({DisasterType.FIRE}),
    ResourceKind.SEARCH_TEAM: frozenset(
        {
            DisasterType.BUILDING_COLLAPSE,
            DisasterType.LANDSLIDE,
            DisasterType.EARTHQUAKE,
            DisasterType.MISSING_PERSON,
            DisasterType.TRAPPED_PERSON,
        }
    ),
    ResourceKind.SHELTER: frozenset(
        {DisasterType.FLOOD, DisasterType.LOGISTICS, DisasterType.OTHER}
    ),
    ResourceKind.SUPPLY_TRUCK: frozenset({DisasterType.LOGISTICS, DisasterType.OTHER}),
}

STALE_AFTER = timedelta(minutes=30)


@dataclass(frozen=True)
class Recommendation:
    """A suggestion with its reason. Never an action."""

    resource: Resource
    reason: str
    score: int


class DispatchService:
    """Simulated dispatch workflow bound to one node's store."""

    def __init__(self, store, event_log, clock) -> None:
        self.store = store
        self.event_log = event_log
        self.clock = clock

    # ------------------------------------------------------------ resources

    def register_resource(self, resource: Resource) -> Resource:
        """Register a simulated resource. Registration counts as a check-in, so
        last_seen_at comes from the node clock rather than a construction-time default."""
        if not resource.simulated:
            raise DomainError("this prototype only registers simulated resources")
        resource.last_seen_at = self.clock.now()
        self.store.save_resource(resource)
        return resource

    def _resources(self) -> list[Resource]:
        from ..domain.models import GeoPoint

        out = []
        for doc in self.store.list_resources():
            loc = doc.get("location")
            out.append(
                Resource(
                    id=doc["id"],
                    kind=ResourceKind(doc["kind"]),
                    label=doc["label"],
                    organization_id=doc.get("organization_id"),
                    status=ResourceStatus(doc["status"]),
                    location=GeoPoint(**loc) if loc else None,
                    capabilities=tuple(DisasterType(c) for c in doc.get("capabilities", [])),
                    simulated=doc.get("simulated", True),
                    last_seen_at=datetime.fromisoformat(doc["last_seen_at"]),
                )
            )
        return out

    def mark_stale(self, now: datetime | None = None) -> int:
        """Flag resources whose last check-in is too old to trust."""
        when = now or self.clock.now()
        count = 0
        for resource in self._resources():
            if (
                resource.status is ResourceStatus.AVAILABLE
                and utc(when) - utc(resource.last_seen_at) > STALE_AFTER
            ):
                resource.status = ResourceStatus.STALE
                self.store.save_resource(resource)
                count += 1
        return count

    # ------------------------------------------------------- recommendation

    def recommend(self, incident: Incident, *, limit: int = 3) -> list[Recommendation]:
        """Rank capable, available resources. Explains every suggestion."""
        wanted = set(incident.disaster_types)
        out: list[Recommendation] = []
        for resource in self._resources():
            capable = CAPABILITY_MATRIX.get(resource.kind, frozenset())
            overlap = wanted & (set(resource.capabilities) or capable)
            if not overlap:
                continue
            if resource.status is not ResourceStatus.AVAILABLE:
                continue
            score = 50 + 10 * len(overlap) + (10 if incident.priority_class.rank == 0 else 0)
            reason = (
                f"{resource.kind.value} matches {', '.join(sorted(t.value for t in overlap))}"
                f"; status {resource.status.value}"
            )
            out.append(Recommendation(resource=resource, reason=reason, score=score))
        out.sort(key=lambda r: -r.score)
        return out[:limit]

    # ------------------------------------------------------------- dispatch

    def create_order(self, incident: Incident, resource_id: str, *, reason: str) -> DispatchOrder:
        """Record a recommendation. Creating one dispatches nothing."""
        order = DispatchOrder(
            incident_id=incident.id,
            resource_id=resource_id,
            status=DispatchStatus.RECOMMENDED,
            recommended_reason=reason,
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.store.save_dispatch(order)
        self._log(order, "DISPATCH_RECOMMENDED", {"reason": reason})
        return order

    def authorize(
        self, order: DispatchOrder, incident: Incident, *, actor_node_id: str, actor_role: Role
    ) -> DispatchOrder:
        """The human gate. Without this call nothing is ever assigned."""
        require_permission(actor_role, Permission.ASSIGN_RESOURCE)

        resource = next((r for r in self._resources() if r.id == order.resource_id), None)
        if resource is None:
            raise DomainError(f"unknown resource {order.resource_id}")
        if resource.status is ResourceStatus.UNAVAILABLE:
            raise DomainError(f"resource {resource.label} is unavailable")
        capable = set(resource.capabilities) or CAPABILITY_MATRIX.get(resource.kind, frozenset())
        if not (set(incident.disaster_types) & capable):
            raise DomainError(
                f"{resource.kind.value} is not capable of "
                f"{', '.join(t.value for t in incident.disaster_types)}"
            )

        dispatch_transition(order.status, DispatchStatus.ASSIGNED, idempotent=False)
        order.status = DispatchStatus.ASSIGNED
        order.authorized_by_node_id = actor_node_id
        order.authorized_by_role = actor_role
        order.updated_at = self.clock.now()
        self.store.save_dispatch(order)

        resource.status = ResourceStatus.ASSIGNED
        self.store.save_resource(resource)

        if incident.status is IncidentStatus.ACKNOWLEDGED:
            incident.status = IncidentStatus.DISPATCH_REQUESTED
            incident.touch(self.clock.now())
            self.store.upsert_incident(incident)

        self._log(
            order,
            "DISPATCH_AUTHORIZED",
            {"by": actor_node_id, "role": actor_role.value, "simulated": True},
        )
        return order

    def advance(self, order: DispatchOrder, target: DispatchStatus) -> DispatchOrder:
        """Responder-driven progress. Duplicate updates are absorbed."""
        if order.status is target:
            return order
        dispatch_transition(order.status, target)
        order.status = target
        order.updated_at = self.clock.now()
        self.store.save_dispatch(order)
        self._log(order, f"DISPATCH_{target.value}", {})
        if target is DispatchStatus.COMPLETED:
            resource = next((r for r in self._resources() if r.id == order.resource_id), None)
            if resource:
                resource.status = ResourceStatus.AVAILABLE
                self.store.save_resource(resource)
        return order

    def cancel(self, order: DispatchOrder, reason: str) -> DispatchOrder:
        dispatch_transition(order.status, DispatchStatus.CANCELLED)
        order.status = DispatchStatus.CANCELLED
        order.updated_at = self.clock.now()
        self.store.save_dispatch(order)
        resource = next((r for r in self._resources() if r.id == order.resource_id), None)
        if resource and resource.status is ResourceStatus.ASSIGNED:
            resource.status = ResourceStatus.AVAILABLE
            self.store.save_resource(resource)
        self._log(order, "DISPATCH_CANCELLED", {"reason": reason})
        return order

    def reassign(
        self,
        order: DispatchOrder,
        incident: Incident,
        new_resource_id: str,
        *,
        actor_node_id: str,
        actor_role: Role,
        reason: str,
    ) -> DispatchOrder:
        """Cancel and re-authorize. The original order stays in the audit trail."""
        self.cancel(order, f"reassigned: {reason}")
        replacement = self.create_order(incident, new_resource_id, reason=reason)
        return self.authorize(
            replacement, incident, actor_node_id=actor_node_id, actor_role=actor_role
        )

    def _log(self, order: DispatchOrder, action: str, detail: dict) -> None:
        entry = self.event_log.append(
            action,
            incident_id=order.incident_id,
            detail={
                "order_id": order.id,
                "resource_id": order.resource_id,
                "status": order.status.value,
                "simulated": True,
            }
            | detail,
            now=self.clock.now(),
        )
        self.store.append_event(entry)


def default_resources(organization_id: str = "org_demo") -> list[Resource]:
    """A small simulated fleet for the demo and the tests."""
    return [
        Resource(
            id="res_amb_1",
            kind=ResourceKind.AMBULANCE,
            label="Ambulance 1",
            organization_id=organization_id,
        ),
        Resource(
            id="res_boat_1",
            kind=ResourceKind.RESCUE_BOAT,
            label="Rescue Boat 1",
            organization_id=organization_id,
        ),
        Resource(
            id="res_fire_1",
            kind=ResourceKind.FIRE_UNIT,
            label="Fire Unit 1",
            organization_id=organization_id,
        ),
        Resource(
            id="res_med_1",
            kind=ResourceKind.MEDICAL_TEAM,
            label="Medical Team 1",
            organization_id=organization_id,
        ),
        Resource(
            id="res_search_1",
            kind=ResourceKind.SEARCH_TEAM,
            label="Search Team 1",
            organization_id=organization_id,
        ),
        Resource(
            id="res_shelter_1",
            kind=ResourceKind.SHELTER,
            label="Shelter North",
            organization_id=organization_id,
        ),
        Resource(
            id="res_truck_1",
            kind=ResourceKind.SUPPLY_TRUCK,
            label="Supply Truck 1",
            organization_id=organization_id,
        ),
    ]
