import { useCallback, useEffect, useState } from 'react';

export type ThemeChoice = 'light' | 'dark';

const STORAGE_KEY = 'schooldom-theme';

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function getStoredTheme(): ThemeChoice | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === 'light' || v === 'dark' ? v : null;
  } catch {
    return null;
  }
}

function storeTheme(theme: ThemeChoice) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* private window / blocked storage - the toggle still works, it just won't persist */
  }
}

function resolveInitialTheme(): ThemeChoice {
  // index.html already set data-theme synchronously before paint (no FOUC) -
  // read that back rather than re-deciding, so this never disagrees with it.
  const attr = typeof document !== 'undefined' ? document.documentElement.getAttribute('data-theme') : null;
  if (attr === 'light' || attr === 'dark') return attr;
  return getStoredTheme() ?? (systemPrefersDark() ? 'dark' : 'light');
}

/** Light/dark toggle backed by localStorage, defaulting to the visitor's
 * prefers-color-scheme until they make an explicit choice - after which it
 * stops following system changes. Toggling sets [data-theme] on <html>,
 * which index.css's token blocks key off. */
export function useTheme() {
  const [theme, setTheme] = useState<ThemeChoice>(resolveInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (getStoredTheme()) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e: MediaQueryListEvent) => setTheme(e.matches ? 'dark' : 'light');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme(prev => {
      const next: ThemeChoice = prev === 'dark' ? 'light' : 'dark';
      storeTheme(next);
      return next;
    });
  }, []);

  return { theme, toggle };
}
