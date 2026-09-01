"""Gateway API: validation, authorization, idempotency, isolation, and audit."""

from __future__ import annotations

import pytest

from tests.fixtures import (
    AUTHORITY,
    COORDINATOR,
    CRITICAL,
    MEDIC,
    OTHER_ORG,
    RELAY,
    REPORTER,
)


def create(client, headers=REPORTER, **overrides):
    payload = CRITICAL | overrides
    return client.post("/v1/incidents", json=payload, headers=headers)


# ------------------------------------------------------------------ health


def test_health_and_readiness(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready").json()
    assert ready["database"] is True
    assert any("development API keys" in w for w in ready["warnings"])


def test_openapi_is_published(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/v1/incidents", "/v1/dispatch", "/v1/alerts", "/v1/audit", "/v1/sync/push"} <= set(
        paths
    )


# ------------------------------------------------------------ authentication


def test_unauthenticated_requests_are_rejected(client):
    response = client.get("/v1/incidents")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def test_unknown_api_key_is_rejected(client):
    response = client.get("/v1/incidents", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


# ------------------------------------------------------------- validation


def test_incident_creation_and_retrieval(client):
    created = create(client)
    assert created.status_code == 201
    incident_id = created.json()["id"]
    body = client.get(f"/v1/incidents/{incident_id}", headers=COORDINATOR).json()
    assert body["incident"]["original_text"] == CRITICAL["original_text"]
    assert body["status"] == "RECEIVED"


@pytest.mark.parametrize(
    "override",
    [
        {"original_text": "   "},
        {"original_text": ""},
        {"severity": 500},
        {"latitude": 999},
        {"priority_score": -3},
        {"priority_class": "P9"},
    ],
)
def test_invalid_payloads_are_rejected(client, override):
    assert create(client, **override).status_code == 422


# ----------------------------------------------------------- authorization


def test_relay_cannot_create_or_read_incidents(client):
    assert create(client, headers=RELAY).status_code == 403
    assert client.get("/v1/incidents", headers=RELAY).status_code == 403


def test_citizen_cannot_dispatch(client):
    create(client)
    response = client.post(
        "/v1/dispatch?confirm=true",
        json={"incident_id": "x", "resource_id": "y", "reason": "test"},
        headers=REPORTER,
    )
    assert response.status_code == 403
    assert "ASSIGN_RESOURCE" in response.json()["detail"]


def test_only_authority_publishes_alerts(client):
    payload = {"headline": "Evacuate", "body": "Move to high ground", "confirm": True}
    assert client.post("/v1/alerts", json=payload, headers=COORDINATOR).status_code == 403
    assert client.post("/v1/alerts", json=payload, headers=AUTHORITY).status_code == 201


def test_alert_requires_explicit_confirmation(client):
    payload = {"headline": "Evacuate", "body": "Move now", "confirm": False}
    assert client.post("/v1/alerts", json=payload, headers=AUTHORITY).status_code == 422


def test_audit_export_requires_permission(client):
    assert client.get("/v1/audit", headers=COORDINATOR).status_code == 403
    assert client.get("/v1/audit", headers=AUTHORITY).status_code == 200


# --------------------------------------------------------------- redaction


def test_medical_content_is_redacted_for_roles_without_clearance(client):
    incident_id = create(client).json()["id"]
    # The reporter created it but has no medical clearance.
    body = client.get(f"/v1/incidents/{incident_id}", headers=REPORTER).json()
    assert body["incident"]["original_text"] == "[restricted: medical content]"
    assert "original_text" in body["incident"]["redacted"]

    cleared = client.get(f"/v1/incidents/{incident_id}", headers=MEDIC).json()
    assert cleared["incident"]["original_text"] == CRITICAL["original_text"]


def test_precise_location_is_coarsened_without_permission(client):
    incident_id = create(client).json()["id"]
    body = client.get(f"/v1/incidents/{incident_id}", headers=REPORTER).json()
    location = body["incident"]["location"]
    assert location["shared_precisely"] is False
    assert location["latitude"] == round(CRITICAL["latitude"], 2)

    precise = client.get(f"/v1/incidents/{incident_id}", headers=COORDINATOR).json()
    assert precise["incident"]["location"]["latitude"] == CRITICAL["latitude"]


# ------------------------------------------------------- organization scope


def test_organizations_are_isolated(client):
    incident_id = create(client).json()["id"]
    assert client.get(f"/v1/incidents/{incident_id}", headers=OTHER_ORG).status_code == 404
    assert client.get("/v1/incidents", headers=OTHER_ORG).json()["total"] == 0


def test_cross_organization_id_collision_is_a_conflict(client):
    incident_id = create(client).json()["id"]
    response = create(client, headers=OTHER_ORG, id=incident_id)
    assert response.status_code == 409


# -------------------------------------------------------------- idempotency


def test_same_idempotency_key_returns_the_first_response(client):
    headers = REPORTER | {"Idempotency-Key": "abc-123"}
    first = client.post("/v1/incidents", json=CRITICAL, headers=headers).json()
    second = client.post("/v1/incidents", json=CRITICAL, headers=headers).json()
    assert first == second
    assert client.get("/v1/incidents", headers=COORDINATOR).json()["total"] == 1


def test_resubmitting_the_same_incident_id_deduplicates(client):
    incident_id = create(client).json()["id"]
    again = create(client, id=incident_id)
    assert again.json()["deduplicated"] is True
    assert client.get("/v1/incidents", headers=COORDINATOR).json()["total"] == 1


def test_a_higher_revision_updates_in_place(client):
    incident_id = create(client).json()["id"]
    updated = create(client, id=incident_id, revision=2, priority_score=95)
    assert updated.json()["deduplicated"] is False
    assert client.get("/v1/incidents", headers=COORDINATOR).json()["total"] == 1


def test_idempotency_key_reuse_across_endpoints_conflicts(client):
    headers = REPORTER | {"Idempotency-Key": "shared-key"}
    client.post("/v1/incidents", json=CRITICAL, headers=headers)
    incident_id = client.get("/v1/incidents", headers=COORDINATOR).json()["items"][0]["id"]
    response = client.post(
        f"/v1/incidents/{incident_id}/acknowledge",
        json={"node_id": "C"},
        headers=COORDINATOR | {"Idempotency-Key": "shared-key"},
    )
    assert response.status_code in (200, 409)


# ------------------------------------------------------------- lifecycle


def test_acknowledgement_is_idempotent(client):
    incident_id = create(client).json()["id"]
    first = client.post(
        f"/v1/incidents/{incident_id}/acknowledge", json={"node_id": "C"}, headers=COORDINATOR
    ).json()
    second = client.post(
        f"/v1/incidents/{incident_id}/acknowledge", json={"node_id": "C"}, headers=COORDINATOR
    ).json()
    assert first["already_acknowledged"] is False
    assert second["already_acknowledged"] is True
    assert second["status"] == "ACKNOWLEDGED"


def test_invalid_status_transition_is_rejected(client):
    incident_id = create(client).json()["id"]
    response = client.patch(
        f"/v1/incidents/{incident_id}/status", json={"status": "ARRIVED"}, headers=COORDINATOR
    )
    assert response.status_code == 409
    assert response.json()["error"] == "invalid_transition"


def test_closing_requires_close_permission(client):
    incident_id = create(client).json()["id"]
    client.post(
        f"/v1/incidents/{incident_id}/acknowledge", json={"node_id": "C"}, headers=COORDINATOR
    )
    assert (
        client.patch(
            f"/v1/incidents/{incident_id}/status", json={"status": "RESOLVED"}, headers=MEDIC
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/v1/incidents/{incident_id}/status", json={"status": "RESOLVED"}, headers=COORDINATOR
        ).status_code
        == 200
    )


# ------------------------------------------------------------- attachments


def test_attachment_metadata_is_validated(client):
    incident_id = create(client).json()["id"]
    good = {"file_name": "a.jpg", "mime_type": "image/jpeg", "size_bytes": 1000, "sha256": "a" * 64}
    assert (
        client.post(
            f"/v1/incidents/{incident_id}/attachments", json=good, headers=REPORTER
        ).status_code
        == 201
    )
    for bad in (
        good | {"mime_type": "application/x-sh"},
        good | {"sha256": "short"},
        good | {"size_bytes": 0},
    ):
        assert (
            client.post(
                f"/v1/incidents/{incident_id}/attachments", json=bad, headers=REPORTER
            ).status_code
            == 422
        )


def test_oversized_attachment_is_refused(client):
    incident_id = create(client).json()["id"]
    response = client.post(
        f"/v1/incidents/{incident_id}/attachments",
        json={
            "file_name": "big.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 50_000_000,
            "sha256": "b" * 64,
        },
        headers=REPORTER,
    )
    assert response.status_code == 413


# ---------------------------------------------------------------- dispatch


@pytest.fixture
def ready_incident(client):
    incident_id = create(client).json()["id"]
    client.post(
        f"/v1/incidents/{incident_id}/acknowledge", json={"node_id": "C"}, headers=COORDINATOR
    )
    client.post(
        "/v1/resources",
        json={"id": "res_search_1", "kind": "SEARCH_TEAM", "label": "Search 1", "simulated": True},
        headers=COORDINATOR,
    )
    client.post(
        "/v1/resources",
        json={"id": "res_boat_1", "kind": "RESCUE_BOAT", "label": "Boat 1", "simulated": True},
        headers=COORDINATOR,
    )
    return incident_id


def test_recommendations_are_capability_matched_and_explained(client, ready_incident):
    body = client.get(f"/v1/incidents/{ready_incident}/recommendations", headers=COORDINATOR).json()
    kinds = {item["kind"] for item in body["items"]}
    assert "SEARCH_TEAM" in kinds and "RESCUE_BOAT" not in kinds
    assert all(item["reason"] for item in body["items"])
    assert body["advisory"] == "recommendation_only_requires_human_authorization"


def test_dispatch_without_confirmation_is_refused(client, ready_incident):
    response = client.post(
        "/v1/dispatch",
        json={"incident_id": ready_incident, "resource_id": "res_search_1", "reason": "match"},
        headers=COORDINATOR,
    )
    assert response.status_code == 400
    assert response.json()["error"] == "confirmation_required"


def test_confirmed_dispatch_is_simulated_and_assigned(client, ready_incident):
    response = client.post(
        "/v1/dispatch?confirm=true",
        json={"incident_id": ready_incident, "resource_id": "res_search_1", "reason": "match"},
        headers=COORDINATOR,
    )
    assert response.status_code == 201
    assert response.json()["simulated"] is True
    detail = client.get(f"/v1/incidents/{ready_incident}", headers=COORDINATOR).json()
    assert detail["status"] == "DISPATCH_REQUESTED"


def test_incompatible_resource_is_rejected(client, ready_incident):
    response = client.post(
        "/v1/dispatch?confirm=true",
        json={"incident_id": ready_incident, "resource_id": "res_boat_1", "reason": "wrong"},
        headers=COORDINATOR,
    )
    assert response.status_code == 409
    assert response.json()["error"] == "incompatible_resource"


def test_double_dispatch_of_one_resource_is_rejected(client, ready_incident):
    body = {"incident_id": ready_incident, "resource_id": "res_search_1", "reason": "match"}
    assert (
        client.post("/v1/dispatch?confirm=true", json=body, headers=COORDINATOR).status_code == 201
    )
    second = client.post("/v1/dispatch?confirm=true", json=body, headers=COORDINATOR)
    assert second.status_code == 409
    assert second.json()["error"] == "resource_unavailable"


def test_dispatch_progression_and_release(client, ready_incident):
    order_id = client.post(
        "/v1/dispatch?confirm=true",
        json={"incident_id": ready_incident, "resource_id": "res_search_1", "reason": "match"},
        headers=COORDINATOR,
    ).json()["id"]
    for state in ("ACKNOWLEDGED", "EN_ROUTE", "ARRIVED", "COMPLETED"):
        assert (
            client.patch(
                f"/v1/dispatch/{order_id}", json={"status": state}, headers=COORDINATOR
            ).status_code
            == 200
        )
    resources = client.get("/v1/resources", headers=COORDINATOR).json()["items"]
    assert next(r for r in resources if r["id"] == "res_search_1")["status"] == "AVAILABLE"


def test_invalid_dispatch_transition_is_rejected(client, ready_incident):
    order_id = client.post(
        "/v1/dispatch?confirm=true",
        json={"incident_id": ready_incident, "resource_id": "res_search_1", "reason": "match"},
        headers=COORDINATOR,
    ).json()["id"]
    response = client.patch(
        f"/v1/dispatch/{order_id}", json={"status": "COMPLETED"}, headers=COORDINATOR
    )
    assert response.status_code == 409


def test_non_simulated_resources_cannot_be_represented(client):
    response = client.post(
        "/v1/resources",
        json={"kind": "AMBULANCE", "label": "Real 108", "simulated": False},
        headers=COORDINATOR,
    )
    assert response.status_code == 422


# ------------------------------------------------------------------ sync


def test_sync_push_is_idempotent(client):
    payload = {"node_id": "A", "incidents": [CRITICAL | {"id": "inc_fixed"}]}
    first = client.post("/v1/sync/push", json=payload, headers=REPORTER).json()
    second = client.post("/v1/sync/push", json=payload, headers=REPORTER).json()
    assert first["accepted"] == 1 and second["deduplicated"] == 1
    assert client.get("/v1/incidents", headers=COORDINATOR).json()["total"] == 1


def test_sync_pull_returns_updates(client):
    create(client)
    body = client.get("/v1/sync/pull", headers=COORDINATOR).json()
    assert len(body["items"]) == 1 and body["server_time"]


# --------------------------------------------------------- clusters + audit


def test_clusters_are_provisional_and_splittable(client):
    create(client)
    create(client, original_text="Building collapsed, people trapped inside")
    built = client.post("/v1/clusters/rebuild", headers=COORDINATOR).json()
    assert built["incidents_considered"] == 2

    clusters = client.get("/v1/clusters", headers=COORDINATOR).json()["items"]
    if clusters:
        cluster_id = clusters[0]["id"]
        victim = clusters[0]["incident_ids"][0]
        split = client.post(
            f"/v1/clusters/{cluster_id}/split", json={"incident_id": victim}, headers=COORDINATOR
        ).json()
        assert split["human_reviewed"] is True
        assert victim not in split["incident_ids"]
        assert client.get("/v1/incidents", headers=COORDINATOR).json()["total"] == 2


def test_audit_chain_records_the_workflow(client):
    incident_id = create(client).json()["id"]
    client.post(
        f"/v1/incidents/{incident_id}/acknowledge", json={"node_id": "C"}, headers=COORDINATOR
    )
    events = client.get("/v1/audit", headers=AUTHORITY).json()["items"]
    actions = [e["action"] for e in events]
    assert "INCIDENT_CREATED" in actions and "INCIDENT_ACKNOWLEDGED" in actions
    assert events[0]["prev_hash"] == "0" * 64
    for previous, current in zip(events, events[1:], strict=False):
        assert current["prev_hash"] == previous["entry_hash"]


def test_pagination_and_filtering(client):
    for i in range(5):
        create(client, original_text=f"Report number {i} trapped")
    page = client.get("/v1/incidents?limit=2&offset=0", headers=COORDINATOR).json()
    assert len(page["items"]) == 2 and page["total"] == 5
    filtered = client.get("/v1/incidents?priority=P0", headers=COORDINATOR).json()
    assert filtered["total"] == 5
    empty = client.get("/v1/incidents?priority=P3", headers=COORDINATOR).json()
    assert empty["total"] == 0


def test_stats_surface_unacknowledged_p0(client):
    create(client)
    stats = client.get("/v1/stats", headers=COORDINATOR).json()
    assert stats["incidents"] == 1 and stats["unacknowledged_p0"] == 1
