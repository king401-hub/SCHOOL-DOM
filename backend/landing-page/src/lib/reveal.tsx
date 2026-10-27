import type { CSSProperties, ReactNode } from 'react';
import { motion, useReducedMotion, type Variants } from 'motion/react';

export const EASE = [0.16, 1, 0.3, 1] as const;

interface RevealProps {
  children: ReactNode;
  delay?: number;
  y?: number;
  x?: number;
  className?: string;
  style?: CSSProperties;
  once?: boolean;
  amount?: number;
  duration?: number;
}

/** Single-element fade/slide-in, triggered when it scrolls into view. */
export function Reveal({ children, delay = 0, y = 24, x = 0, className, style, once = true, amount = 0.2, duration = 0.7 }: RevealProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      initial={reduced ? false : { opacity: 0, y, x }}
      whileInView={{ opacity: 1, y: 0, x: 0 }}
      viewport={{ once, amount }}
      transition={{ duration: reduced ? 0 : duration, delay: reduced ? 0 : delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

interface RevealGroupProps {
  children: ReactNode;
  className?: string;
  stagger?: number;
  delay?: number;
  once?: boolean;
  amount?: number;
}

/** Wraps a set of `revealItem`-tagged children and staggers their entrance. */
export function RevealGroup({ children, className, stagger = 0.08, delay = 0, once = true, amount = 0.15 }: RevealGroupProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : 'hidden'}
      whileInView="show"
      viewport={{ once, amount }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: reduced ? 0 : stagger, delayChildren: reduced ? 0 : delay } } }}
    >
      {children}
    </motion.div>
  );
}

export const revealItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
};
