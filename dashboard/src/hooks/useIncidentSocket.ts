/**
 * Real-time push for the incident feed. Every message from the gateway is a
 * bare signal (`{"type": ..., "incident_id": ...}`) — never a data payload —
 * so on any message we just invalidate the same React Query caches the app
 * already trusts, rather than trying to merge a partial push payload into
 * the cache ourselves.
 *
 * A dropped/failed socket is not a hard failure: the caller's own polling
 * `refetchInterval` keeps working as a slower fallback, so this hook only
 * ever makes things faster when it's connected, never a single point of
 * failure when it isn't.
 */
import { useEffect } from "react";
import type { QueryClient } from "@tanstack/react-query";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "dev-coordinator-key";

export function useIncidentSocket(queryClient: QueryClient, onIncidentCreated?: () => void) {
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let closedByUs = false;
    let attempt = 0;

    function invalidateAll() {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["incident"] });
      queryClient.invalidateQueries({ queryKey: ["nodes"] });
    }

    function connect() {
      const wsUrl = `${API_URL.replace(/^http/, "ws")}/v1/ws/incidents?token=${API_KEY}`;
      socket = new WebSocket(wsUrl);

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          invalidateAll();
          if (data.type === "incident_created") onIncidentCreated?.();
        } catch {
          // A malformed message is not worth failing over — just refetch.
          invalidateAll();
        }
      };

      socket.onclose = () => {
        if (closedByUs) return;
        attempt += 1;
        const delay = Math.min(1000 * 2 ** attempt, 20000);
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    connect();

    return () => {
      closedByUs = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [queryClient, onIncidentCreated]);
}
