/**
 * A subtle 3D tilt-toward-cursor effect for cards, driven entirely through CSS
 * custom properties so it never triggers a React re-render per mouse move.
 *
 * Mouse-only by design: a touch drag over a card is how the incident queue
 * scrolls, so touch pointers are ignored rather than hijacked into a tilt.
 * Also a no-op under prefers-reduced-motion.
 */
import { useCallback } from "react";

export function useCardTilt<T extends HTMLElement>() {
  return useCallback((el: T | null) => {
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const rect = el.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      el.style.setProperty("--tilt-x", `${(-py * 6).toFixed(2)}deg`);
      el.style.setProperty("--tilt-y", `${(px * 6).toFixed(2)}deg`);
    };
    const onLeave = () => {
      el.style.setProperty("--tilt-x", "0deg");
      el.style.setProperty("--tilt-y", "0deg");
    };

    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerleave", onLeave);
  }, []);
}
