import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import HeroSceneFallback from './HeroSceneFallback';
import HeroSceneErrorBoundary from './HeroSceneErrorBoundary';
import { detectDeviceTier } from '../lib/deviceCapability';

const HeroScene3D = lazy(() => import('./HeroScene3D'));

/**
 * Hero visual wrapper: decides once (via detectDeviceTier) whether to even
 * fetch the Three.js chunk, pauses the live scene's render loop while it's
 * scrolled out of view, and converges every failure/loading/skip path onto
 * the same static HeroSceneFallback so there's never a layout jump or a
 * blank hole - only ever mounted at md+ widths (desktop/laptop), see Hero.tsx.
 */
export default function HeroScene() {
  const [tier] = useState(detectDeviceTier);
  const containerRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(true);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || tier === 'fallback') return;
    const obs = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.05 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [tier]);

  return (
    <div ref={containerRef} className="absolute inset-0" aria-hidden="true">
      {tier === 'fallback' ? (
        <HeroSceneFallback />
      ) : (
        <HeroSceneErrorBoundary fallback={<HeroSceneFallback />}>
          <Suspense fallback={<HeroSceneFallback />}>
            <HeroScene3D paused={!inView} />
          </Suspense>
        </HeroSceneErrorBoundary>
      )}
    </div>
  );
}
