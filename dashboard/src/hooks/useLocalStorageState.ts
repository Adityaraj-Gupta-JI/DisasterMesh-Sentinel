/**
 * Small, dependency-free preference storage.
 *
 * The dashboard has no settings/state-management library, and doesn't need one for a
 * single boolean toggle — this is the whole pattern.
 */
import { useEffect, useState } from "react";

export function useLocalStorageState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw !== null ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage can be unavailable (private browsing, quota) — the toggle still
      // works for the session, it just won't persist across reloads.
    }
  }, [key, value]);

  return [value, setValue] as const;
}

/** Live-updates if the OS-level setting changes mid-session, not just on load. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
