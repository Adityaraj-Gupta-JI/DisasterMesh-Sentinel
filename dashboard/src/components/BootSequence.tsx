/**
 * A short, purely cosmetic boot animation shown once on load. It does not test
 * or report on any real subsystem — it's a stylized flourish, not a diagnostic —
 * and it never blocks the app underneath from mounting or fetching data.
 */
import { useEffect, useState } from "react";

const STEPS = ["NETWORK", "MESH", "AI ENGINE", "DISPATCH"];
const STEP_MS = 160;
const FADE_MS = 280;

export function BootSequence() {
  const [readyCount, setReadyCount] = useState(0);
  const [fading, setFading] = useState(false);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (readyCount >= STEPS.length) {
      setFading(true);
      const t = setTimeout(() => setVisible(false), FADE_MS);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setReadyCount((n) => n + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [readyCount]);

  if (!visible) return null;

  return (
    <div className={`boot-sequence${fading ? " boot-fade" : ""}`} role="status" aria-live="polite">
      <div className="boot-panel">
        <p className="boot-title">DISASTERMESH SENTINEL</p>
        <p className="boot-sub">SYSTEM INITIALIZATION</p>
        <ul className="boot-checklist">
          {STEPS.map((step, i) => (
            <li key={step} className={i < readyCount ? "ready" : ""}>
              <span>{step}</span>
              <span className="boot-state">{i < readyCount ? "ONLINE" : "···"}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
