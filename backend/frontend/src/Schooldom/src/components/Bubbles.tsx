import { useMemo } from 'react';

interface BubblesProps {
  /** Number of bubbles to float. Kept low on small screens for performance. */
  count?: number;
}

/**
 * Live, lightweight floating-bubble background.
 *
 * Pure CSS animation (no canvas / rAF), `pointer-events-none` and pinned
 * behind the content, so it never interferes with interaction or layout and
 * stays cheap on mobile. Colors are brand-tinted and adapt to dark mode.
 */
export default function Bubbles({ count = 18 }: BubblesProps) {
  // Pre-compute randomized, stable bubble configs once per mount.
  const bubbles = useMemo(() => {
    const palette = [
      'rgba(0, 184, 240, 0.18)',   // brand-500
      'rgba(80, 213, 140, 0.16)',  // teal-brand-500
      'rgba(65, 211, 255, 0.14)',  // brand-400
    ];
    return Array.from({ length: count }, (_, i) => {
      const size = 14 + Math.random() * 60;          // px
      const left = Math.random() * 100;              // vw
      const duration = 14 + Math.random() * 16;      // s
      const delay = -Math.random() * 24;             // s (negative = mid-flight start)
      const drift = `${(Math.random() - 0.5) * 160}px`;
      return {
        key: i,
        size,
        left,
        duration,
        delay,
        drift,
        color: palette[i % palette.length],
      };
    });
  }, [count]);

  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 -z-10 overflow-hidden pointer-events-none select-none opacity-70 dark:opacity-40"
      id="background-bubbles"
    >
      {bubbles.map((b) => (
        <span
          key={b.key}
          className="absolute bottom-[-80px] rounded-full animate-float-up"
          style={{
            left: `${b.left}vw`,
            width: `${b.size}px`,
            height: `${b.size}px`,
            background: `radial-gradient(circle at 30% 30%, ${b.color}, transparent 72%)`,
            border: `1px solid ${b.color}`,
            animationDuration: `${b.duration}s`,
            animationDelay: `${b.delay}s`,
            // consumed by the float-up keyframes for horizontal drift
            ['--bubble-drift' as string]: b.drift,
          }}
        />
      ))}
    </div>
  );
}
