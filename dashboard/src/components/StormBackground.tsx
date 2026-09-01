/**
 * Animated night-storm background: drifting clouds, an occasional lightning strike,
 * and a reflective water plane. Purely decorative — non-interactive, `pointer-events:
 * none`, and z-indexed below every real dashboard control.
 *
 * Respects `prefers-reduced-motion` (a single static frame, no timers) and an
 * `enabled` prop backed by a persisted user toggle. Everything three.js-related is
 * created and disposed inside one effect keyed on [enabled, reducedMotion], which
 * keeps it safe under React 18 StrictMode's dev-mode double-invoke.
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { usePrefersReducedMotion } from "../hooks/useLocalStorageState";

const CLOUD_LAYERS = [
  { z: -40, opacity: 0.5, driftSpeed: 0.004, seed: 1, y: 6, scale: 60 },
  { z: -22, opacity: 0.65, driftSpeed: 0.009, seed: 2, y: 4, scale: 48 },
  { z: -10, opacity: 0.3, driftSpeed: 0.016, seed: 3, y: 10, scale: 34 },
];

const WATER_Y = -6;

/** A few soft radial-gradient stamps on an offscreen 2D canvas — cheap cloud noise. */
function createCloudTexture(seed: number): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  // Deep navy base, not neutral grey — the previous grey/brown tint was the main
  // reason the scene read as flat haze instead of a night storm.
  ctx.fillStyle = "rgba(8, 14, 28, 0)";
  ctx.fillRect(0, 0, size, size);

  let s = seed * 9301 + 49297;
  const rand = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };

  // Two passes instead of one uniform blur: a dark cloud mass first, then a
  // smaller, offset rim-highlight per blob (as if lit from the upper-left by
  // moonlight). Flat single-tone blobs were the main reason clouds read as
  // vague grey smudges instead of clouds with actual form.
  const blobs = Array.from({ length: 11 }, () => ({
    x: rand() * size,
    y: rand() * size * 0.7 + size * 0.05,
    r: 45 + rand() * 85,
  }));

  for (const { x, y, r } of blobs) {
    const alpha = 0.3 + rand() * 0.25;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(12, 16, 26, ${alpha})`);
    g.addColorStop(1, "rgba(12, 16, 26, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }

  for (const { x, y, r } of blobs) {
    const hx = x - r * 0.3;
    const hy = y - r * 0.35;
    const hr = r * 0.55;
    const alpha = 0.14 + rand() * 0.16;
    const g = ctx.createRadialGradient(hx, hy, 0, hx, hy, hr);
    g.addColorStop(0, `rgba(110, 130, 175, ${alpha})`);
    g.addColorStop(1, "rgba(110, 130, 175, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(2, 1);
  return texture;
}

/** Recursive midpoint displacement: a jagged bolt from `start` toward `end`. */
function generateBoltPoints(
  start: THREE.Vector3,
  end: THREE.Vector3,
  displace: number,
  depth: number,
): THREE.Vector3[] {
  if (depth <= 0) return [start, end];

  const mid = start.clone().lerp(end, 0.5);
  const dir = end.clone().sub(start).normalize();
  // Any vector not parallel to dir, crossed with dir, gives a perpendicular offset axis.
  const perp = new THREE.Vector3(-dir.y, dir.x, dir.z * 0.3).normalize();
  mid.addScaledVector(perp, (Math.random() - 0.5) * displace);

  const left = generateBoltPoints(start, mid, displace * 0.55, depth - 1);
  const right = generateBoltPoints(mid, end, displace * 0.55, depth - 1);
  return left.concat(right.slice(1));
}

function buildBoltLine(points: THREE.Vector3[], opacity: number): THREE.Line {
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({
    color: 0xd6e8ff,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  return new THREE.Line(geometry, material);
}

function disposeObject(obj: THREE.Object3D) {
  obj.traverse((child) => {
    if (child instanceof THREE.Mesh || child instanceof THREE.Line) {
      child.geometry.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((m) => {
        (m as THREE.MeshBasicMaterial).map?.dispose();
        m.dispose();
      });
    }
  });
}

export function StormBackground({ enabled }: { enabled: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const flashRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (!enabled) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(0, 6, 22);
    camera.lookAt(0, 2, 0);

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setSize(window.innerWidth, window.innerHeight);

    scene.add(new THREE.AmbientLight(0x1a2030, 0.7));
    const moonlight = new THREE.DirectionalLight(0x8fa8d0, 0.5);
    moonlight.position.set(-10, 20, 10);
    scene.add(moonlight);

    // ---- clouds --------------------------------------------------------------
    const cloudMeshes = CLOUD_LAYERS.map((layer) => {
      const texture = createCloudTexture(layer.seed);
      const geometry = new THREE.PlaneGeometry(layer.scale, layer.scale * 0.5);
      const material = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: layer.opacity,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(0, layer.y, layer.z);
      scene.add(mesh);
      return { mesh, texture, driftSpeed: layer.driftSpeed };
    });

    // ---- water -----------------------------------------------------------------
    // Pushed lower and made narrower/more transparent than the first pass, which
    // rendered as a flat grey slab dominating the lower half of the viewport.
    const waterGeometry = new THREE.PlaneGeometry(70, 18, 40, 16);
    const waterMaterial = new THREE.MeshStandardMaterial({
      color: 0x0b1424, // matches the body gradient's horizon-to-water band
      roughness: 0.3,
      metalness: 0.15,
      transparent: true,
      opacity: 0.55,
    });
    const water = new THREE.Mesh(waterGeometry, waterMaterial);
    water.rotation.x = -Math.PI / 2;
    water.position.y = WATER_Y;
    scene.add(water);

    // ---- reflection approximation: a mirrored, dimmer clone of the sky group ---
    const reflectionGroup = new THREE.Group();
    cloudMeshes.forEach(({ mesh }) => {
      const clone = mesh.clone();
      clone.material = (mesh.material as THREE.MeshBasicMaterial).clone();
      (clone.material as THREE.MeshBasicMaterial).opacity *= 0.4;
      reflectionGroup.add(clone);
    });
    reflectionGroup.position.set(0, 2 * WATER_Y, 0);
    reflectionGroup.scale.y = -1;
    scene.add(reflectionGroup);

    // ---- lightning ---------------------------------------------------------------
    const boltGroup = new THREE.Group();
    scene.add(boltGroup);
    let activeBolt: THREE.Line | null = null;
    let activeLight: THREE.PointLight | null = null;
    let strikeStart = 0;
    let strikeTimer: ReturnType<typeof setTimeout> | null = null;
    const STRIKE_DURATION_MS = 180;

    function clearActiveStrike() {
      if (activeBolt) {
        boltGroup.remove(activeBolt);
        disposeObject(activeBolt);
        activeBolt = null;
      }
      if (activeLight) {
        scene.remove(activeLight);
        activeLight = null;
      }
    }

    function fireStrike() {
      clearActiveStrike();
      const x = (Math.random() - 0.5) * 14;
      const start = new THREE.Vector3(x, 13, -15);
      const end = new THREE.Vector3(x + (Math.random() - 0.5) * 3, -1, -15);
      const points = generateBoltPoints(start, end, 3.5, 5);
      activeBolt = buildBoltLine(points, 1);
      boltGroup.add(activeBolt);

      activeLight = new THREE.PointLight(0xbcd4ff, 6, 40);
      activeLight.position.copy(start);
      scene.add(activeLight);

      strikeStart = performance.now();
      if (flashRef.current) flashRef.current.style.opacity = "0.12";
    }

    function scheduleNextStrike() {
      const delay = 4000 + Math.random() * 9000;
      strikeTimer = setTimeout(() => {
        fireStrike();
        scheduleNextStrike();
      }, delay);
    }

    // ---- reduced-motion: one static frame, no timers, no loop -------------------
    if (reducedMotion) {
      const points = generateBoltPoints(
        new THREE.Vector3(2, 13, -15),
        new THREE.Vector3(0, -1, -15),
        3.5,
        5,
      );
      const staticBolt = buildBoltLine(points, 0.7);
      boltGroup.add(staticBolt);
      renderer.render(scene, camera);

      return () => {
        renderer.dispose();
        waterGeometry.dispose();
        waterMaterial.dispose();
        disposeObject(boltGroup);
        disposeObject(reflectionGroup);
        cloudMeshes.forEach(({ mesh, texture }) => {
          mesh.geometry.dispose();
          (mesh.material as THREE.Material).dispose();
          texture.dispose();
        });
      };
    }

    // ---- full animated loop -------------------------------------------------------
    let rafId = 0;
    let running = true;
    let lastTime = performance.now();

    function onVisibilityChange() {
      if (document.hidden) {
        running = false;
        if (strikeTimer) clearTimeout(strikeTimer);
      } else if (!running) {
        running = true;
        lastTime = performance.now();
        scheduleNextStrike();
        rafId = requestAnimationFrame(animate);
      }
    }
    document.addEventListener("visibilitychange", onVisibilityChange);

    function onResize() {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }
    window.addEventListener("resize", onResize);

    // ---- mouse parallax (mouse-only: a touch drag is how the queue scrolls,
    // so touch pointers must never move the camera) -----------------------
    let targetX = 0;
    let targetY = 0;
    let camX = 0;
    let camY = 0;
    function onPointerMove(e: PointerEvent) {
      if (e.pointerType !== "mouse") return;
      targetX = (e.clientX / window.innerWidth) * 2 - 1;
      targetY = (e.clientY / window.innerHeight) * 2 - 1;
    }
    window.addEventListener("pointermove", onPointerMove);

    const waterPos = waterGeometry.attributes.position;
    function updateWater(elapsed: number) {
      for (let i = 0; i < waterPos.count; i++) {
        const x = waterPos.getX(i);
        const y = waterPos.getY(i);
        const wave = Math.sin(x * 0.3 + elapsed * 0.6) * 0.15 + Math.cos(y * 0.4 + elapsed * 0.4) * 0.1;
        waterPos.setZ(i, wave);
      }
      waterPos.needsUpdate = true;
    }

    function animate(now: number) {
      if (!running) return;
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      const elapsed = now / 1000;

      cloudMeshes.forEach(({ texture, driftSpeed }) => {
        texture.offset.x += dt * driftSpeed;
      });
      updateWater(elapsed);

      // Slow ease toward the cursor position — a drift, not a snap.
      camX += (targetX * 1.4 - camX) * 0.03;
      camY += (-targetY * 0.8 - camY) * 0.03;
      camera.position.x = camX;
      camera.position.y = 6 + camY;
      camera.lookAt(camX * 0.3, 2, 0);

      if (activeBolt) {
        const t = now - strikeStart;
        if (t > STRIKE_DURATION_MS) {
          clearActiveStrike();
          if (flashRef.current) flashRef.current.style.opacity = "0";
        } else {
          // A quick flicker envelope rather than a plain fade.
          const flicker = 0.5 + 0.5 * Math.abs(Math.sin(t * 0.4));
          const mat = activeBolt.material as THREE.LineBasicMaterial;
          mat.opacity = flicker;
          if (activeLight) activeLight.intensity = 6 * flicker;
          if (flashRef.current) flashRef.current.style.opacity = String(0.12 * flicker);
        }
      }

      renderer.render(scene, camera);
      rafId = requestAnimationFrame(animate);
    }

    scheduleNextStrike();
    rafId = requestAnimationFrame(animate);

    return () => {
      running = false;
      cancelAnimationFrame(rafId);
      if (strikeTimer) clearTimeout(strikeTimer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointerMove);
      clearActiveStrike();
      renderer.dispose();
      waterGeometry.dispose();
      waterMaterial.dispose();
      disposeObject(boltGroup);
      disposeObject(reflectionGroup);
      cloudMeshes.forEach(({ mesh, texture }) => {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
        texture.dispose();
      });
    };
  }, [enabled, reducedMotion]);

  if (!enabled) return null;

  return (
    <>
      <canvas ref={canvasRef} className="storm-bg" aria-hidden="true" />
      <div ref={flashRef} className="storm-flash" aria-hidden="true" />
    </>
  );
}
