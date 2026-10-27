import { useRef, type MouseEvent } from 'react';
import { useMotionValue, useSpring, useReducedMotion } from 'motion/react';

/**
 * Real perspective-based tilt-on-hover: rotateX/rotateY driven by cursor
 * position within the element, spring-eased - not just a translateY lift.
 * Compose the returned style into a motion.div alongside any existing
 * whileHover/variants; rotateX/rotateY merge with other transform props.
 */
export function useTilt<T extends HTMLElement>(maxDeg = 7) {
  const reduced = useReducedMotion();
  const ref = useRef<T>(null);
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const rotateX = useSpring(rx, { stiffness: 220, damping: 20, mass: 0.4 });
  const rotateY = useSpring(ry, { stiffness: 220, damping: 20, mass: 0.4 });

  const onMouseMove = (e: MouseEvent) => {
    if (reduced) return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    ry.set(px * maxDeg * 2);
    rx.set(-py * maxDeg * 2);
  };
  const onMouseLeave = () => { rx.set(0); ry.set(0); };

  return {
    ref,
    onMouseMove,
    onMouseLeave,
    style: { rotateX, rotateY, transformPerspective: 900 },
  };
}
