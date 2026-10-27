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
          top: '8%', right: '4%', width: '56%', aspectRatio: '1 / 1',
          background: 'linear-gradient(135deg, rgba(20,19,16,0.10), rgba(20,83,45,0.14) 55%, rgba(74,222,128,0.10))',
          border: '1px solid rgba(20,19,16,0.08)',
          boxShadow: '0 40px 100px -30px rgba(20,83,45,0.25)',
          transform: 'rotate(-6deg)',
        }}
      />
      <div
        className="absolute rounded-[2rem]"
        style={{
          top: '24%', right: '18%', width: '28%', aspectRatio: '1 / 1',
          background: 'linear-gradient(135deg, rgba(20,83,45,0.22), rgba(74,222,128,0.16))',
          border: '1px solid rgba(20,83,45,0.18)',
          boxShadow: '0 24px 60px -20px rgba(20,19,16,0.2)',
          transform: 'rotate(10deg)',
        }}
      />
    </div>
  );
}
