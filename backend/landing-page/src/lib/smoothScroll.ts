import type Lenis from 'lenis';

let instance: Lenis | null = null;

export function setLenisInstance(lenis: Lenis | null) {
  instance = lenis;
}

export function smoothScrollTo(target: string, offset = 0) {
  if (instance) {
    instance.scrollTo(target, { offset, duration: 1.15 });
    return;
  }
  const el = typeof target === 'string' ? document.querySelector(target) : target;
  el?.scrollIntoView({ behavior: 'smooth' });
}
