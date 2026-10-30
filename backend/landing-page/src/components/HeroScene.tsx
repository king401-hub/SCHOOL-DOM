import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useIsPresent } from 'motion/react';
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
  // AnimatePresence (App.tsx) keeps the outgoing page mounted and fully
  // attached for the whole exit transition when navigating away (e.g. to
  // /signup). Its exiting branch renders through <Routes location={...}> with
  // a frozen, already-stale location prop (the standard react-router pattern
  // for keeping the old page's content visible through its own exit
  // animation), so useLocation() here would keep reporting "/" the entire
  // time and never catch the navigation. useIsPresent() is the correct signal
  // instead: it flips to false the instant AnimatePresence marks this branch
  // for removal, well before the exit animation finishes, so the Canvas stops
  // rendering (and starts tearing down) as soon as the exit begins rather
  // than ~400ms later alongside the removal of its own ancestor.
  //
  // Tearing down the Canvas here (for any reason - this exit, a tab close,
  // etc.) can still throw a one-off "Failed to execute 'removeChild' on
  // 'Node'" from deep inside React's own unmount pass: drei's <Html> labels
  // manage their own DOM portal attachment outside of React's tracked
  // children, and that specific interaction with this Canvas's unmount is a
  // known upstream quirk (reproduced identically regardless of teardown
  // sequencing). It's non-fatal - verified the page content is unaffected -
  // so it's narrowly suppressed in main.tsx's bootstrap rather than chased
  // further here.
  const isPresent = useIsPresent();

  useEffect(() => {
    const el = containerRef.current;
    if (!el || tier === 'fallback') return;
    const obs = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.05 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [tier]);

  return (
    <div ref={containerRef} className="absolute inset-0" aria-hidden="true">
      {tier === 'fallback' || !isPresent ? (
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
