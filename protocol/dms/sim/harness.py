"""Deterministic three-node harness: reporter → relay → coordinator.

Used by the integration tests, the simulator, and the demo script so all three
exercise exactly the same wiring.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..crypto.keys import SoftwareKeyStore
from ..domain.clock import FixedClock
from ..domain.enums import Role
from ..domain.models import NodeIdentity
from ..node import MeshNode, NodeConfig
from ..store.sqlite import SqliteStore
from ..transport.mock import MockRadio, MockTransport

ORG_KEY_ID = "org-demo"


@dataclass
class Mesh:
    """A small mesh plus the shared radio and clock driving it."""

    radio: MockRadio
    clock: FixedClock
    nodes: dict[str, MeshNode] = field(default_factory=dict)

    def add(
        self,
        node_id: str,
        role: Role,
        *,
        data_dir: Path,
        org_key: bytes | None = None,
        organization_id: str = "org_demo",
        config: NodeConfig | None = None,
    ) -> MeshNode:
        data_dir.mkdir(parents=True, exist_ok=True)
        keystore = SoftwareKeyStore()
        identity = NodeIdentity(
            id=node_id, display_name=node_id, role=role, organization_id=organization_id
        )
        node = MeshNode(
            identity,
            MockTransport(node_id, self.radio),
            store=SqliteStore(str(data_dir / f"{node_id}.db")),
            keystore=keystore,
            clock=self.clock,
            data_dir=data_dir / node_id,
            org_key_id=ORG_KEY_ID,
            config=config or NodeConfig(),
        )
        if org_key is not None:
            node.grant_org_key(org_key)
        self.nodes[node_id] = node
        node.start()
        return node

    def trust_all(self) -> None:
        """Every node learns every other node's public key."""
        for a in self.nodes.values():
            for b in self.nodes.values():
                if a is not b:
                    a.trust(b)

    def connect(self, a: str, b: str) -> None:
        self.radio.link(a, b)
        self.nodes[a].transport.request_connection(b)
        self.radio.drain()

    def disconnect(self, a: str, b: str) -> None:
        self.nodes[a].transport.disconnect(b)
        self.radio.unlink(a, b)

    def exchange(self, initiator: str, peer: str, rounds: int = 6) -> None:
        """Run inventory exchange to quiescence.

        Several rounds because a relay only re-offers a bundle after it has
        received it, so multi-hop delivery needs more than one pass.
        """
        for _ in range(rounds):
            self.nodes[initiator].sync_with(peer)
            self.radio.drain()

    def stop(self) -> None:
        """Close storage and stop nodes cleanly."""
        for node in self.nodes.values():
            node.stop()



def build_demo_mesh(data_dir: Path, *, relay_holds_key: bool = False) -> Mesh:
    """Reporter A, relay B, coordinator C.

    The relay deliberately does NOT get the organization key: it carries ciphertext
    and routing metadata, and cannot read what it forwards.
    """
    org_key = os.urandom(32)
    mesh = Mesh(radio=MockRadio(), clock=FixedClock())
    mesh.add("A", Role.CITIZEN_REPORTER, data_dir=data_dir, org_key=org_key)
    mesh.add(
        "B",
        Role.VOLUNTEER_RELAY,
        data_dir=data_dir,
        org_key=org_key if relay_holds_key else None,
    )
    mesh.add("C", Role.EVENT_COORDINATOR, data_dir=data_dir, org_key=org_key)
    mesh.trust_all()
    return mesh
