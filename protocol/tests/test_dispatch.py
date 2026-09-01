"""Simulated dispatch workflow."""

from __future__ import annotations

from datetime import timedelta

import pytest
from dms.dispatch.service import DispatchService, default_resources
from dms.domain.enums import (
    DisasterType,
    DispatchStatus,
    IncidentStatus,
    PriorityClass,
    ResourceKind,
    ResourceStatus,
    Role,
)
from dms.domain.errors import AuthorizationError, DomainError, LifecycleError
from dms.domain.models import Incident, Resource
from dms.governance.audit import EventLog
from dms.store.sqlite import SqliteStore


@pytest.fixture
def service(clock):
    store = SqliteStore(":memory:")
    svc = DispatchService(store, EventLog(clock), clock)
    for resource in default_resources():
        svc.register_resource(resource)
    return svc


@pytest.fixture
def collapse(service) -> Incident:
    inc = Incident(
        source_node_id="A",
        original_text="Three trapped under collapse",
        disaster_types=(DisasterType.BUILDING_COLLAPSE, DisasterType.TRAPPED_PERSON),
        priority_class=PriorityClass.P0,
        priority_score=90,
        status=IncidentStatus.ACKNOWLEDGED,
    )
    service.store.upsert_incident(inc)
    return inc


def test_recommendations_match_capability(service, collapse):
    kinds = {r.resource.kind for r in service.recommend(collapse, limit=5)}
    assert ResourceKind.SEARCH_TEAM in kinds
    assert ResourceKind.RESCUE_BOAT not in kinds, "a boat cannot work a collapse"


def test_every_recommendation_states_its_reason(service, collapse):
    assert all(r.reason and r.score > 0 for r in service.recommend(collapse))


def test_flood_recommends_a_boat(service):
    flood = Incident(
        source_node_id="A",
        original_text="Water rising fast",
        disaster_types=(DisasterType.FLOOD,),
        priority_class=PriorityClass.P1,
    )
    assert ResourceKind.RESCUE_BOAT in {r.resource.kind for r in service.recommend(flood)}


def test_creating_an_order_does_not_dispatch(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="capability match")
    assert order.status is DispatchStatus.RECOMMENDED
    assert order.authorized_by_node_id is None


def test_dispatch_requires_an_authorized_role(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    with pytest.raises(AuthorizationError, match="ASSIGN_RESOURCE"):
        service.authorize(order, collapse, actor_node_id="X", actor_role=Role.CITIZEN_REPORTER)
    assert service.store.list_dispatch(collapse.id)[0]["status"] == "RECOMMENDED"


def test_authorized_dispatch_assigns_and_marks_the_resource(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    assert order.status is DispatchStatus.ASSIGNED and order.simulated
    resource = next(r for r in service.store.list_resources() if r["id"] == "res_search_1")
    assert resource["status"] == ResourceStatus.ASSIGNED.value
    assert service.store.get_incident(collapse.id).status is IncidentStatus.DISPATCH_REQUESTED


def test_incompatible_resource_cannot_be_assigned(service, collapse):
    order = service.create_order(collapse, "res_boat_1", reason="operator error")
    with pytest.raises(DomainError, match="not capable"):
        service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)


def test_unavailable_resource_cannot_be_assigned(service, collapse):
    unavailable = Resource(
        id="res_x",
        kind=ResourceKind.SEARCH_TEAM,
        label="Off duty",
        status=ResourceStatus.UNAVAILABLE,
        capabilities=(DisasterType.BUILDING_COLLAPSE,),
    )
    service.register_resource(unavailable)
    order = service.create_order(collapse, "res_x", reason="match")
    with pytest.raises(DomainError, match="unavailable"):
        service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)


def test_duplicate_authorization_is_rejected(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    with pytest.raises(LifecycleError):
        service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)


def test_status_progression_and_completion_frees_the_resource(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    for state in (
        DispatchStatus.ACKNOWLEDGED,
        DispatchStatus.EN_ROUTE,
        DispatchStatus.ARRIVED,
        DispatchStatus.COMPLETED,
    ):
        service.advance(order, state)
    assert order.status is DispatchStatus.COMPLETED
    resource = next(r for r in service.store.list_resources() if r["id"] == "res_search_1")
    assert resource["status"] == ResourceStatus.AVAILABLE.value


def test_duplicate_status_update_is_idempotent(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    service.advance(order, DispatchStatus.ACKNOWLEDGED)
    service.advance(order, DispatchStatus.ACKNOWLEDGED)
    assert order.status is DispatchStatus.ACKNOWLEDGED


def test_illegal_status_jump_is_rejected(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    with pytest.raises(LifecycleError):
        service.advance(order, DispatchStatus.ARRIVED)


def test_reassignment_keeps_the_original_in_the_audit_trail(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="first choice")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    replacement = service.reassign(
        order,
        collapse,
        "res_med_1",
        actor_node_id="C",
        actor_role=Role.EVENT_COORDINATOR,
        reason="closer unit",
    )
    orders = service.store.list_dispatch(collapse.id)
    assert len(orders) == 2
    assert {o["status"] for o in orders} == {"CANCELLED", "ASSIGNED"}
    assert replacement.resource_id == "res_med_1"


def test_cancellation_frees_the_resource(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    service.cancel(order, "false alarm")
    resource = next(r for r in service.store.list_resources() if r["id"] == "res_search_1")
    assert resource["status"] == ResourceStatus.AVAILABLE.value


def test_stale_resources_are_flagged(service, clock):
    assert service.mark_stale(clock.now() + timedelta(hours=2)) > 0
    assert any(r["status"] == "STALE" for r in service.store.list_resources())


def test_real_resources_are_refused(service):
    with pytest.raises(DomainError, match="simulated"):
        service.register_resource(
            Resource(id="real_999", kind=ResourceKind.AMBULANCE, label="Real 108", simulated=False)
        )


def test_every_dispatch_transition_is_logged(service, collapse):
    order = service.create_order(collapse, "res_search_1", reason="match")
    service.authorize(order, collapse, actor_node_id="C", actor_role=Role.EVENT_COORDINATOR)
    service.advance(order, DispatchStatus.ACKNOWLEDGED)
    actions = [e["action"] for e in service.store.events(collapse.id)]
    assert actions == ["DISPATCH_RECOMMENDED", "DISPATCH_AUTHORIZED", "DISPATCH_ACKNOWLEDGED"]
    assert all(e["detail"]["simulated"] for e in service.store.events(collapse.id))
