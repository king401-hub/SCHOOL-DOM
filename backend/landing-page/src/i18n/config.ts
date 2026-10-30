import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

export const SUPPORTED_LANGUAGES = ['en', 'fr', 'ar', 'yo', 'pt'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const RTL_LANGUAGES: SupportedLanguage[] = ['ar'];

// Each locale file (30-45KB raw) used to be imported eagerly here, so all 5
// landed in the main bundle even though a given visitor only ever needs one.
// Loading them as separate dynamic imports lets Vite split each into its own
// small chunk, fetched only when actually needed.
const LOCALE_LOADERS: Record<SupportedLanguage, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import('./locales/en.json'),
  fr: () => import('./locales/fr.json'),
  ar: () => import('./locales/ar.json'),
  yo: () => import('./locales/yo.json'),
  pt: () => import('./locales/pt.json'),
};

// Keeps <html dir="rtl"> and lang in sync with whatever language is active,
// on first load and on every later change - Tailwind/flex layouts mirror
// automatically off dir, so this one line is most of what RTL needs.
function applyDocumentDirection(lng: string) {
  const isRtl = RTL_LANGUAGES.includes(lng as SupportedLanguage);
  document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
  document.documentElement.lang = lng;
}

async function ensureLoaded(code: SupportedLanguage) {
  if (i18n.hasResourceBundle(code, 'translation')) return;
  const mod = await LOCALE_LOADERS[code]();
  i18n.addResourceBundle(code, 'translation', mod.default);
}

/** Loads a language's bundle on demand (used by LanguageSwitcher) and
 * switches to it once available. */
export async function loadLanguage(code: SupportedLanguage) {
  await ensureLoaded(code);
  await i18n.changeLanguage(code);
}

let initPromise: Promise<void> | null = null;

/** Detects the visitor's language, loads just that one bundle (plus English
 * as the fallbackLng safety net), and resolves once i18next is ready to
 * render - call this once from main.tsx before the first render. */
export function initI18n(): Promise<void> {
  if (initPromise) return initPromise;

  initPromise = (async () => {
    await i18n
      .use(LanguageDetector)
      .use(initReactI18next)
      .init({
        resources: {},
        fallbackLng: 'en',
        supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],
        interpolation: { escapeValue: false },
        detection: {
          order: ['localStorage', 'navigator'],
          lookupLocalStorage: 'schooldom-language',
          caches: ['localStorage'],
        },
      });

    const detected = (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0];
    const initial = (SUPPORTED_LANGUAGES as readonly string[]).includes(detected)
      ? (detected as SupportedLanguage)
      : 'en';

    await ensureLoaded(initial);
    if (initial !== 'en') await ensureLoaded('en');

    applyDocumentDirection(initial);
    i18n.on('languageChanged', (lng) => applyDocumentDirection(lng.split('-')[0]));
  })();

  return initPromise;
}

export default i18n;
