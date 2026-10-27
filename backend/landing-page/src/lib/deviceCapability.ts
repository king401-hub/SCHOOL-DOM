export type DeviceTier = 'fallback' | 'low' | 'high';

function hasWebGL2(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!canvas.getContext('webgl2');
  } catch {
    return false;
  }
}

/**
 * One-time capability probe, run before the Three.js chunk is even requested,
 * so a device that clearly can't or shouldn't run it never pays the download
 * or GPU cost. 'fallback' renders a static CSS stand-in with zero WebGL.
 *
 * Touch-primary devices (phones/tablets) are routed to 'fallback' on purpose:
 * the live WebGL scene is a desktop/laptop flourish, not a crippled mobile
 * tier - this keeps the mobile experience light by construction instead of
 * shipping a GPU-bound scene there at all.
 */
export function detectDeviceTier(): DeviceTier {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return 'fallback';
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return 'fallback';

  const nav = navigator as Navigator & { connection?: { saveData?: boolean } };
  if (nav.connection?.saveData) return 'fallback';

  if (window.matchMedia('(pointer: coarse)').matches) return 'fallback';

  if (!hasWebGL2()) return 'fallback';

  const cores = navigator.hardwareConcurrency || 4;
  if (cores <= 2) return 'fallback';
  if (cores <= 4) return 'low';
  return 'high';
}
