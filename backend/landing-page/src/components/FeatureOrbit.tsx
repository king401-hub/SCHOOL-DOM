import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useReducedMotion } from 'motion/react';
import { DollarSign, BookOpen, QrCode, FileText, Briefcase, MessageSquare, GraduationCap } from 'lucide-react';
import { useTilt } from '../lib/tilt';

type IconType = typeof DollarSign;
interface ModuleDef { icon: IconType; key: string; color: string }

const MODULES: ModuleDef[] = [
  { icon: DollarSign, key: 'features.grid.finance.title', color: '#1d6b3c' },
  { icon: BookOpen, key: 'features.grid.cbtEngine.title', color: '#2f7d4f' },
  { icon: QrCode, key: 'features.grid.attendance.title', color: '#4ade80' },
  { icon: FileText, key: 'features.grid.reportCards.title', color: '#206e3c' },
  { icon: Briefcase, key: 'features.grid.hr.title', color: '#35966a' },
  { icon: MessageSquare, key: 'features.grid.parentPortal.title', color: '#4fae7f' },
];

/** Tracks the container's own box so every radius/size below scales with it
 * instead of relying on hardcoded breakpoints - this is what keeps the
 * orbital arrangement intact (no overlap) from tablet widths up through a
 * large desktop hero column. */
function useMeasuredSize<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [size, setSize] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      const s = Math.min(width, height);
      if (s > 0) setSize(s);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

/**
 * SVG/CSS orbital feature wheel - replaces the former Three.js scene
 * (HeroScene3D.tsx). Continuous rotation and its exact counter-rotation are
 * two CSS animations of identical duration started together
 * (.fo-orbit-spin / .fo-orbit-counter), which keeps each module's icon and
 * label upright while the ring carrying it keeps turning - a free substitute
 * for per-frame counter-rotation in a 3D engine. Everything here animates
 * only transform/opacity/filter, all driven by CSS rather than JS, so the
 * whole scene costs nothing beyond a handful of composited layers - no WebGL
 * context, no render loop, no capability gating needed. The one real 3D
 * touch is the whole-wheel pointer-parallax tilt (useTilt, the same hook
 * used for card tilt elsewhere on this site), which is where the "depth and
 * perspective" the brief asked for actually lives - every ring/spoke/node
 * underneath stays flat and 2D, which is what keeps the labels perfectly
 * readable at every rotation angle (the thing the old wheel struggled with).
 */
export default function FeatureOrbit() {
  const { t } = useTranslation();
  const reduced = useReducedMotion();
  const [hovered, setHovered] = useState<number | null>(null);
  const [boxRef, size] = useMeasuredSize<HTMLDivElement>(360);
  const tilt = useTilt<HTMLDivElement>(5);

  const n = MODULES.length;
  const radius = size * 0.35;
  const outerRadius = size * 0.46;
  const hub = size * 0.22;
  const node = size * 0.135;
  const half = size / 2;

  return (
    <div ref={boxRef} className="relative w-full h-full flex items-center justify-center" aria-hidden="true">
      <motion.div
        ref={tilt.ref}
        onMouseMove={tilt.onMouseMove}
        onMouseLeave={tilt.onMouseLeave}
        className="relative"
        style={{ width: size, height: size, ...(reduced ? {} : tilt.style) }}
      >
        {/* Decorative outer ring - slow independent counter-rotation, no
            modules on it, purely a depth/layering cue */}
        <div
          className={`absolute rounded-full border border-dashed ${reduced ? '' : 'fo-ring-reverse'}`}
          style={{
            inset: `${half - outerRadius}px`,
            borderColor: 'rgba(74,222,128,0.16)',
          }}
        />

        {/* Main circular orbital path - visible, flat, static */}
        <div
          className="absolute rounded-full"
          style={{
            inset: `${half - radius}px`,
            border: '1px solid rgba(74,222,128,0.28)',
            boxShadow: 'inset 0 0 30px rgba(74,222,128,0.08)',
          }}
        />

        {/* Small glowing energy points travelling the main ring at their own
            independent speed, separate from the modules' own orbit */}
        <div className={`absolute inset-0 ${reduced ? '' : 'fo-dots-spin'}`}>
          {[0, 1, 2].map((d) => (
            <div key={d} className="absolute top-1/2 left-1/2" style={{ transform: `rotate(${d * 120}deg)` }}>
              <div
                className="absolute rounded-full"
                style={{
                  width: 6, height: 6, top: -3, left: radius - 3,
                  background: '#4ade80',
                  boxShadow: '0 0 10px 2px rgba(74,222,128,0.75)',
                }}
              />
            </div>
          ))}
        </div>

        {/* Central hub - layered rings, glow, gentle breathing pulse */}
        <div
          className="absolute top-1/2 left-1/2"
          style={{ width: hub, height: hub, transform: 'translate(-50%, -50%)' }}
        >
          <div className={`relative w-full h-full flex items-center justify-center ${reduced ? '' : 'fo-hub-pulse'}`}>
            <div
              className="absolute inset-0 rounded-full"
              style={{ background: 'radial-gradient(circle, rgba(74,222,128,0.4), transparent 72%)', filter: 'blur(8px)' }}
            />
            <div className="absolute rounded-full" style={{ inset: hub * 0.13, border: '1px solid rgba(74,222,128,0.3)' }} />
            <div className="absolute rounded-full" style={{ inset: hub * 0.04, border: '1px solid rgba(74,222,128,0.5)' }} />
            <div
              className="relative rounded-full flex items-center justify-center"
              style={{
                width: hub * 0.6, height: hub * 0.6,
                background: 'linear-gradient(135deg, #14532d, #206e3c)',
                boxShadow: '0 0 22px rgba(74,222,128,0.55), inset 0 1px 0 rgba(255,255,255,0.18)',
              }}
            >
              <GraduationCap size={hub * 0.32} color="#eafff0" />
            </div>
          </div>
        </div>

        {/* Orbiting modules - one shared rotation drives the whole ring, each
            module's own content counter-rotates to stay upright */}
        <div className={`absolute inset-0 ${reduced ? '' : 'fo-orbit-spin'}`}>
          {MODULES.map((m, i) => {
            const angle = -90 + i * (360 / n);
            const Icon = m.icon;
            const isHovered = hovered === i;
            const curveY = i % 2 === 0 ? 9 : 25;
            return (
              <div key={m.key} className="absolute top-1/2 left-1/2" style={{ transform: `rotate(${angle}deg)` }}>
                {/* connector: a gentle curve, not a straight spoke, with a
                    flowing dashed light travelling along it */}
                <svg
                  className="absolute overflow-visible"
                  style={{ top: -17, left: 0, width: radius, height: 34, pointerEvents: 'none' }}
                >
                  <defs>
                    <linearGradient id={`fo-spoke-${i}`} x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#4ade80" stopOpacity="0" />
                      <stop offset="50%" stopColor="#4ade80" stopOpacity={isHovered ? 0.95 : 0.5} />
                      <stop offset="100%" stopColor={m.color} stopOpacity={isHovered ? 1 : 0.75} />
                    </linearGradient>
                  </defs>
                  <path
                    d={`M0,17 Q${radius * 0.5},${curveY} ${radius - node * 0.45},17`}
                    fill="none"
                    stroke={`url(#fo-spoke-${i})`}
                    strokeWidth={isHovered ? 2.4 : 1.5}
                    strokeLinecap="round"
                    strokeDasharray="7 9"
                    className={reduced ? '' : 'fo-spoke-flow'}
                    style={{ transition: 'stroke-width 0.25s ease' }}
                  />
                </svg>

                {/* module node, translated to the spoke's end. The spin
                    cancels over time (fo-orbit-counter undoes the ancestor's
                    continuous rotation), but that alone leaves each module
                    permanently tilted by its own static orbital angle - the
                    inner rotate(-angle) wrapper cancels that fixed offset so
                    every label renders upright regardless of position. */}
                <div className="absolute top-0 left-0" style={{ transform: `translateX(${radius}px)` }}>
                  <div style={{ transform: `rotate(${-angle}deg)` }}>
                  <div className={reduced ? '' : 'fo-orbit-counter'}>
                    <div
                      onMouseEnter={() => setHovered(i)}
                      onMouseLeave={() => setHovered(null)}
                      className="relative flex flex-col items-center gap-1.5"
                      style={{
                        transform: `translate(-50%, -50%) scale(${isHovered ? 1.16 : 1})`,
                        transition: 'transform 0.3s cubic-bezier(.2,.8,.2,1)',
                      }}
                    >
                      <span
                        className={`flex items-center justify-center rounded-full ${reduced ? '' : 'fo-module-float'}`}
                        style={{
                          width: node, height: node,
                          animationDelay: `${i * -1.4}s`,
                          background: `linear-gradient(135deg, rgba(255,255,255,0.1), ${m.color}30)`,
                          border: `1px solid ${isHovered ? `${m.color}99` : 'rgba(74,222,128,0.32)'}`,
                          boxShadow: isHovered
                            ? `0 0 24px ${m.color}70, inset 0 1px 0 rgba(255,255,255,0.25)`
                            : '0 0 12px rgba(74,222,128,0.18), inset 0 1px 0 rgba(255,255,255,0.15)',
                          backdropFilter: 'blur(6px)',
                        }}
                      >
                        <Icon size={node * 0.42} color={m.color} />
                      </span>
                      <span
                        className="px-2 py-0.5 rounded-full whitespace-nowrap overflow-hidden text-ellipsis font-semibold"
                        style={{
                          fontSize: 10,
                          color: '#eafff0',
                          background: 'rgba(10,20,14,0.62)',
                          border: `1px solid ${isHovered ? `${m.color}70` : 'rgba(74,222,128,0.22)'}`,
                          maxWidth: Math.min(140, Math.max(64, size * 0.26)),
                        }}
                        title={t(m.key)}
                      >
                        {t(m.key)}
                      </span>
                    </div>
                  </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
