import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from './locales/en.json';
import fr from './locales/fr.json';
import ar from './locales/ar.json';
import yo from './locales/yo.json';
import pt from './locales/pt.json';

export const SUPPORTED_LANGUAGES = ['en', 'fr', 'ar', 'yo', 'pt'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const RTL_LANGUAGES: SupportedLanguage[] = ['ar'];

// Keeps <html dir="rtl"> and lang in sync with whatever language is active,
// on first load and on every later change - Tailwind/flex layouts mirror
// automatically off dir, so this one line is most of what RTL needs.
function applyDocumentDirection(lng: string) {
  const isRtl = RTL_LANGUAGES.includes(lng as SupportedLanguage);
  document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
  document.documentElement.lang = lng;
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fr: { translation: fr },
      ar: { translation: ar },
      yo: { translation: yo },
      pt: { translation: pt },
    },
    fallbackLng: 'en',
    supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'schooldom-language',
      caches: ['localStorage'],
    },
  });

applyDocumentDirection(i18n.resolvedLanguage || i18n.language || 'en');
i18n.on('languageChanged', applyDocumentDirection);

export default i18n;
