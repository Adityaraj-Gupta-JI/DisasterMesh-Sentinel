"""Sinks that carry the multi-hop event stream off the box.

:class:`ListSink` (in :mod:`multihop`) keeps events in memory. :class:`HttpSink`
streams them to the gateway so the coordinator dashboard can watch a live run
started from a terminal. It batches — one POST per flush, not per hop — and never
raises into the simulation: a mesh that would deliver offline must not be broken
by a gateway that isn't there.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .multihop import MeshEvent


class HttpSink:
    """Streams events to ``{gateway}/v1/mesh``. Creates the run on first use."""

    def __init__(
        self,
        gateway: str,
        topology_snapshot: dict,
        *,
        api_key: str | None = None,
        batch: int = 1,
        timeout: float = 5.0,
    ) -> None:
        self.gateway = gateway.rstrip("/")
        self.api_key = api_key
        self.batch = batch
        self.timeout = timeout
        self._buffer: list[dict] = []
        self.run_id = self._create_run(topology_snapshot)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.gateway}{path}",
            data=json.dumps(body).encode(),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def _create_run(self, snapshot: dict) -> str | None:
        try:
            return self._post("/v1/mesh/runs", {"topology": snapshot}).get("run_id")
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def __call__(self, event: MeshEvent) -> None:
        if self.run_id is None:
            return
        self._buffer.append(event.to_dict())
        if len(self._buffer) >= self.batch or event.type in {"delivered", "quiescent"}:
            self.flush()

    def flush(self, *, metrics: dict | None = None, done: bool = False) -> None:
        if self.run_id is None:
            return
        body: dict = {"events": self._buffer}
        if metrics is not None:
            body["metrics"] = metrics
        if done:
            body["done"] = True
        try:
            self._post(f"/v1/mesh/runs/{self.run_id}/events", body)
            self._buffer = []
        except (urllib.error.URLError, OSError, ValueError):
            pass  # the mesh keeps working; the dashboard just misses a beat
