import { useEffect, useRef, useState, type ReactNode } from 'react';

interface RevealProps {
  children: ReactNode;
  /** Slide direction the element animates in from. */
  direction?: 'up' | 'left' | 'right';
  /** Stagger delay in ms before the reveal transition starts. */
  delay?: number;
  className?: string;
  /** Render as a different element (defaults to a div). */
  as?: 'div' | 'section' | 'span';
}

/**
 * Scroll-triggered reveal. Adds the `is-visible` class (see landing.css)
 * once the element scrolls into view, producing a slide + fade-in. Reveals
 * only once and self-cleans the observer. Honours prefers-reduced-motion
 * via the CSS rules in landing.css.
 */
export default function Reveal({
  children,
  direction = 'up',
  delay = 0,
  className = '',
  as: Tag = 'div',
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    // No IntersectionObserver (old browsers / SSR) → show immediately.
    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const directionClass =
    direction === 'left' ? 'reveal-left' : direction === 'right' ? 'reveal-right' : '';

  return (
    <Tag
      ref={ref as never}
      className={`reveal ${directionClass} ${visible ? 'is-visible' : ''} ${className}`.trim()}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
