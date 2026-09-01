"""Shared request headers and payloads for backend tests."""

from __future__ import annotations


def auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


COORDINATOR = auth("dev-coordinator-key")
REPORTER = auth("dev-reporter-key")
RELAY = auth("dev-relay-key")
MEDIC = auth("dev-medic-key")
AUTHORITY = auth("dev-authority-key")
OTHER_ORG = auth("dev-other-org-key")

CRITICAL = {
    "source_node_id": "node_a",
    "original_text": "Three people trapped under collapsed building",
    "source_language": "en",
    "disaster_types": ["BUILDING_COLLAPSE", "TRAPPED_PERSON"],
    "urgency": "CRITICAL",
    "severity": 90,
    "priority_class": "P0",
    "priority_score": 90,
    "sensitivity": "MEDICAL",
    "people_affected": {"value": 3, "raw": "Three people"},
    "latitude": 12.971598,
    "longitude": 77.594566,
}
