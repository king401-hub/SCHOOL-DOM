import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Check } from 'lucide-react';
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../i18n/config';

const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: 'English',
  fr: 'Français',
  ar: 'العربية',
  yo: 'Yorùbá',
  pt: 'Português',
};

interface LanguageSwitcherProps {
  className?: string;
  align?: 'left' | 'right';
}

export default function LanguageSwitcher({ className = '', align = 'right' }: LanguageSwitcherProps) {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const current = (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0] as SupportedLanguage;

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Change language"
        aria-expanded={open}
        className="h-9 px-3 rounded-xl border border-[var(--c-ink)]/10 flex items-center gap-1.5 text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all cursor-pointer shrink-0 text-xs font-semibold"
      >
        <Globe className="h-4 w-4" />
        <span className="uppercase">{current}</span>
      </button>
      {open && (
        <div
          className={`absolute top-full ${align === 'right' ? 'right-0' : 'left-0'} mt-2 w-44 rounded-2xl overflow-hidden shadow-xl z-50 sd-panel`}
        >
          {SUPPORTED_LANGUAGES.map(code => (
            <button
              key={code}
              onClick={() => { i18n.changeLanguage(code); setOpen(false); }}
              className="w-full flex items-center justify-between px-4 py-3 text-sm text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all cursor-pointer"
            >
              {LANGUAGE_LABELS[code]}
              {current === code && <Check className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--c-green)' }} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
