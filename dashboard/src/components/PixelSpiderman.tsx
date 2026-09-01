/**
 * A purely decorative, original pixel-art figure (not traced from any
 * copyrighted artwork, no official name/logo) that roams slowly across the
 * background — an "unseen watcher" easter egg, per earlier direction. Two
 * instances at different heights/speeds/delays so it reads as "here and
 * there" rather than one obvious repeating loop. Static under
 * prefers-reduced-motion (CSS handles that — see .pixel-spidey in app.css).
 */
const SPRITE_RECTS = (
  <>
    <rect x="14" y="0" width="56" height="7" fill="#0b0b12" />
    <rect x="7" y="7" width="7" height="7" fill="#0b0b12" />
    <rect x="14" y="7" width="56" height="7" fill="#e8362a" />
    <rect x="70" y="7" width="7" height="7" fill="#0b0b12" />
    <rect x="0" y="14" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="14" width="14" height="7" fill="#e8362a" />
    <rect x="21" y="14" width="7" height="7" fill="#ffffff" />
    <rect x="28" y="14" width="28" height="7" fill="#0b0b12" />
    <rect x="56" y="14" width="7" height="7" fill="#ffffff" />
    <rect x="63" y="14" width="14" height="7" fill="#e8362a" />
    <rect x="77" y="14" width="7" height="7" fill="#0b0b12" />
    <rect x="0" y="21" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="21" width="14" height="7" fill="#e8362a" />
    <rect x="21" y="21" width="7" height="7" fill="#ffffff" />
    <rect x="28" y="21" width="28" height="7" fill="#0b0b12" />
    <rect x="56" y="21" width="7" height="7" fill="#ffffff" />
    <rect x="63" y="21" width="14" height="7" fill="#e8362a" />
    <rect x="77" y="21" width="7" height="7" fill="#0b0b12" />
    <rect x="0" y="28" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="28" width="21" height="7" fill="#e8362a" />
    <rect x="28" y="28" width="28" height="7" fill="#0b0b12" />
    <rect x="56" y="28" width="21" height="7" fill="#e8362a" />
    <rect x="77" y="28" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="35" width="7" height="7" fill="#0b0b12" />
    <rect x="14" y="35" width="56" height="7" fill="#e8362a" />
    <rect x="70" y="35" width="7" height="7" fill="#0b0b12" />
    <rect x="0" y="42" width="7" height="7" fill="#e8362a" />
    <rect x="7" y="42" width="7" height="7" fill="#0b0b12" />
    <rect x="14" y="42" width="56" height="7" fill="#e8362a" />
    <rect x="70" y="42" width="7" height="7" fill="#0b0b12" />
    <rect x="77" y="42" width="7" height="7" fill="#e8362a" />
    <rect x="0" y="49" width="14" height="7" fill="#e8362a" />
    <rect x="14" y="49" width="7" height="7" fill="#0b0b12" />
    <rect x="21" y="49" width="42" height="7" fill="#e8362a" />
    <rect x="63" y="49" width="7" height="7" fill="#0b0b12" />
    <rect x="70" y="49" width="14" height="7" fill="#e8362a" />
    <rect x="14" y="56" width="7" height="7" fill="#0b0b12" />
    <rect x="21" y="56" width="14" height="7" fill="#1a2a6c" />
    <rect x="35" y="56" width="14" height="7" fill="#e8362a" />
    <rect x="49" y="56" width="14" height="7" fill="#1a2a6c" />
    <rect x="63" y="56" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="63" width="7" height="7" fill="#0b0b12" />
    <rect x="14" y="63" width="21" height="7" fill="#1a2a6c" />
    <rect x="35" y="63" width="14" height="7" fill="#e8362a" />
    <rect x="49" y="63" width="21" height="7" fill="#1a2a6c" />
    <rect x="70" y="63" width="7" height="7" fill="#0b0b12" />
    <rect x="0" y="70" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="70" width="28" height="7" fill="#1a2a6c" />
    <rect x="35" y="70" width="14" height="7" fill="#e8362a" />
    <rect x="49" y="70" width="28" height="7" fill="#1a2a6c" />
    <rect x="77" y="70" width="7" height="7" fill="#0b0b12" />
    <rect x="0" y="77" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="77" width="28" height="7" fill="#1a2a6c" />
    <rect x="35" y="77" width="14" height="7" fill="#e8362a" />
    <rect x="49" y="77" width="28" height="7" fill="#1a2a6c" />
    <rect x="77" y="77" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="84" width="7" height="7" fill="#0b0b12" />
    <rect x="14" y="84" width="21" height="7" fill="#1a2a6c" />
    <rect x="49" y="84" width="21" height="7" fill="#1a2a6c" />
    <rect x="70" y="84" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="91" width="7" height="7" fill="#0b0b12" />
    <rect x="14" y="91" width="21" height="7" fill="#1a2a6c" />
    <rect x="49" y="91" width="21" height="7" fill="#1a2a6c" />
    <rect x="70" y="91" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="98" width="14" height="7" fill="#0b0b12" />
    <rect x="14" y="98" width="14" height="7" fill="#1a2a6c" />
    <rect x="56" y="98" width="14" height="7" fill="#1a2a6c" />
    <rect x="70" y="98" width="7" height="7" fill="#0b0b12" />
    <rect x="7" y="105" width="14" height="7" fill="#0b0b12" />
    <rect x="21" y="105" width="7" height="7" fill="#1a2a6c" />
    <rect x="56" y="105" width="7" height="7" fill="#1a2a6c" />
    <rect x="63" y="105" width="14" height="7" fill="#0b0b12" />
  </>
);

function Sprite({ className }: { className: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 84 112"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {SPRITE_RECTS}
    </svg>
  );
}

export function PixelSpiderman() {
  return (
    <>
      <Sprite className="pixel-spidey pixel-spidey-a" />
      <Sprite className="pixel-spidey pixel-spidey-b" />
    </>
  );
}
