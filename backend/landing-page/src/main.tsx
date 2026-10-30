import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { initI18n } from './i18n/config';

// Only the detected language's bundle (plus English as the fallback) is
// fetched before the first render - see i18n/config.ts for why.
initI18n().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
