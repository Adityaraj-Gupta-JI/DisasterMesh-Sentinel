"""In-process WebSocket fan-out for the coordinator dashboard.

Every event is a small signal ("something changed, refetch"), never a data
payload — the dashboard re-runs the same authoritative REST GET it already
trusts. This keeps the push channel simple and impossible to get out of sync
with the database: worst case, a dropped connection just means the existing
polling fallback catches up a little later, never a wrong or stale value
silently overwriting a correct one.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, organization_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[organization_id].add(ws)

    def disconnect(self, organization_id: str, ws: WebSocket) -> None:
        self._connections[organization_id].discard(ws)
        if not self._connections[organization_id]:
            self._connections.pop(organization_id, None)

    async def broadcast(self, organization_id: str, event: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(organization_id, ()):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(organization_id, ws)

    def broadcast_from_sync(self, organization_id: str, event: dict) -> None:
        """Fire-and-forget from a regular (non-async) route handler.

        Every mutation endpoint in this gateway is a plain ``def``, run by
        FastAPI in a worker thread — it cannot ``await`` directly. A missing
        or already-closed loop (e.g. under a test client) is a no-op, never
        a raised exception: a lost realtime nudge is harmless, since the
        dashboard's polling fallback still catches up.
        """
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(organization_id, event), self._loop)
        except RuntimeError:
            pass


manager = ConnectionManager()
