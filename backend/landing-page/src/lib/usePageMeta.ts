import { useEffect } from 'react';

const SITE_NAME = 'Schooldom Academy';
const BASE_URL = 'https://schooldom.academy';

function upsertMeta(name: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('name', name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function upsertCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

/**
 * Per-route document.title + meta description + canonical link, for a
 * HashRouter SPA with only 5 routes - not worth a dependency like
 * react-helmet-async for this. Deliberately does NOT touch og: / twitter:
 * tags: those are read by share-preview bots (WhatsApp, Slack, Twitter...)
 * which fetch the URL and read the static HTML WITHOUT running JS, so
 * anything set here after mount would never be seen by them anyway - the
 * static defaults in index.html are what actually drives link previews,
 * and they'll always reflect the home page regardless of which route was
 * shared. Real per-route previews would need server-side rendering.
 */
export function usePageMeta(title: string, description: string, path: string) {
  useEffect(() => {
    document.title = path === '/' ? title : `${title} | ${SITE_NAME}`;
    upsertMeta('description', description);
    // Canonical still points at a /#path fragment, which search engines
    // generally don't index as a distinct page from the root - that's a
    // HashRouter limitation, not something this hook can fix.
    upsertCanonical(`${BASE_URL}/#${path}`);
  }, [title, description, path]);
}
