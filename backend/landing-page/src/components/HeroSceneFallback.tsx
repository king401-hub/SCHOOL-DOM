/**
 * Static, zero-WebGL stand-in for the hero's 3D scene. Shown on devices the
 * capability gate routes to 'fallback' (touch-primary, reduced-motion,
 * low-core, no WebGL2, save-data), and as the Suspense/error-boundary
 * fallback while - or if - the real scene loads. Occupies the same footprint
 * as the live scene so there is no layout jump when one replaces the other.
 */
export default function HeroSceneFallback() {
  return (
    <div className="relative w-full h-full">
      <div
        className="absolute rounded-[2.5rem]"
        style={{
          top: '14%', left: '10%', width: '62%', aspectRatio: '1 / 1',
          background: 'linear-gradient(135deg, rgba(var(--c-ink-rgb),0.10), rgba(var(--c-green-rgb),0.14) 55%, rgba(74,222,128,0.10))',
          border: '1px solid rgba(var(--c-ink-rgb),0.08)',
          boxShadow: '0 40px 100px -30px rgba(var(--c-green-rgb),0.25)',
          transform: 'rotate(-6deg)',
        }}
      />
      <div
        className="absolute rounded-[2rem]"
        style={{
          top: '38%', left: '46%', width: '34%', aspectRatio: '1 / 1',
          background: 'linear-gradient(135deg, rgba(var(--c-green-rgb),0.22), rgba(74,222,128,0.16))',
          border: '1px solid rgba(var(--c-green-rgb),0.18)',
          boxShadow: '0 24px 60px -20px rgba(var(--c-ink-rgb),0.2)',
          transform: 'rotate(10deg)',
        }}
      />
      <div
        className="absolute rounded-[1.4rem]"
        style={{
          bottom: '10%', left: '4%', width: '20%', aspectRatio: '1 / 1',
          background: 'linear-gradient(135deg, rgba(74,222,128,0.20), rgba(var(--c-green-rgb),0.10))',
          border: '1px solid rgba(74,222,128,0.22)',
          boxShadow: '0 16px 40px -16px rgba(var(--c-ink-rgb),0.18)',
          transform: 'rotate(-14deg)',
        }}
      />
    </div>
  );
}
