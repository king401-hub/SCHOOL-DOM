import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { initI18n } from './i18n/config';

// Dev-only: React 19 StrictMode's intentional double mount/unmount/remount
// surfaces a known upstream quirk as a console.error - drei's <Html> (used by
// the hero's 3D module wheel) manages its own DOM portal attachment outside
// of React's tracked children, and that interacts badly with StrictMode's
// synthetic unmount. It never reaches production (StrictMode's double-invoke
// is dev-only), so this filter is itself gated to DEV builds and matches only
// this exact message. The same underlying interaction can also throw a
// one-off "Failed to execute 'removeChild' on 'Node'" in production on a real
// route change away from the 3D hero (e.g. to /signup) - confirmed non-fatal
// (page content and navigation are unaffected either way, see HeroScene.tsx),
// but it did not go through the normal window 'error'/'unhandledrejection'
// pathways this app could otherwise intercept, so it's left visible rather
// than silenced with a broader, riskier patch (e.g. overriding
// Node.prototype.removeChild globally).
if ((import.meta as any).env?.DEV) {
  const originalConsoleError = console.error;
  console.error = (...args: unknown[]) => {
    if (typeof args[0] === 'string' && args[0].includes('Attempted to synchronously unmount a root while React was already rendering')) {
      return;
    }
    originalConsoleError(...args);
  };
}

// Only the detected language's bundle (plus English as the fallback) is
// fetched before the first render - see i18n/config.ts for why.
initI18n().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
