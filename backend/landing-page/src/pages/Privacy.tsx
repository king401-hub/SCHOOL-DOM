import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { usePageMeta } from '../lib/usePageMeta';

const MAIL = 'enquiry@schooldom.academy';
const NDPC = 'ndpc.gov.ng';

// Translated Privacy sections are plain strings (so every locale file stays
// pure JSON, no embedded JSX) using a tiny **bold** convention plus two
// known-constant strings (the DPO email, the NDPC site) that get auto-linked
// wherever they appear - same two special links the original hand-written
// JSX had, just driven off the translated text instead of hardcoded markup.
function linkify(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(new RegExp(`(${MAIL}|${NDPC})`, 'g'));
  return parts.map((part, i) => {
    if (part === MAIL) {
      return <a key={`${keyPrefix}-${i}`} href={`mailto:${MAIL}`} className="hover:underline" style={{ color: 'var(--c-green)' }}>{part}</a>;
    }
    if (part === NDPC) {
      return <a key={`${keyPrefix}-${i}`} href={`http://${NDPC}`} target="_blank" rel="noreferrer" className="hover:underline" style={{ color: 'var(--c-green)' }}>{part}</a>;
    }
    return part;
  });
}

function renderInline(text: string, keyPrefix: string): ReactNode {
  const boldParts = text.split(/(\*\*[^*]+\*\*)/g);
  return boldParts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${keyPrefix}-b-${i}`} className="text-[var(--c-ink)]">{linkify(part.slice(2, -2), `${keyPrefix}-b-${i}`)}</strong>;
    }
    return <span key={`${keyPrefix}-s-${i}`}>{linkify(part, `${keyPrefix}-s-${i}`)}</span>;
  });
}

interface PrivacySection {
  title: string;
  paragraphs?: string[];
  list?: string[];
  paragraphsAfter?: string[];
}

export default function PrivacyPage() {
  const { t } = useTranslation();
  usePageMeta(`${t('privacy.title')} ${t('privacy.titleHighlight')}`, t('privacy.intro'), '/privacy');
  const sections = t('privacy.sections', { returnObjects: true }) as PrivacySection[];

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--c-green-rgb),0.06) 0%, transparent 50%)' }} />

      <div className="max-w-3xl mx-auto">
        <a href="/" className="inline-flex items-center gap-2 text-[var(--c-muted)] hover:text-[var(--c-ink)] text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> {t('common.backToHome')}
        </a>

        <div className="text-center mb-12">
          <span className="badge badge-green mb-4">{t('privacy.badge')}</span>
          <h1 className="font-display font-bold text-4xl sm:text-5xl text-[var(--c-ink)] mb-4 tracking-tight">
            {t('privacy.title')} <span className="gradient-text">{t('privacy.titleHighlight')}</span>
          </h1>
          <p className="text-[var(--c-muted)]">{t('privacy.lastUpdated')}</p>
        </div>

        <div className="rounded-2xl p-6 sd-card mb-6">
          <p className="text-[var(--c-muted)] text-sm leading-relaxed">
            {t('privacy.intro')}
          </p>
        </div>

        <div className="space-y-6">
          {sections.map((section, sIdx) => (
            <div key={section.title} className="rounded-2xl p-6 sd-card">
              <h2 className="font-bold text-[var(--c-ink)] text-lg mb-3">{section.title}</h2>
              <div className="text-[var(--c-muted)] text-sm leading-relaxed space-y-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2 [&_li]:marker:text-[var(--c-green)]">
                {(section.paragraphs || []).map((p, i) => (
                  <p key={`p-${i}`}>{renderInline(p, `s${sIdx}-p${i}`)}</p>
                ))}
                {section.list ? (
                  <ul>
                    {section.list.map((li, i) => (
                      <li key={`li-${i}`}>{renderInline(li, `s${sIdx}-li${i}`)}</li>
                    ))}
                  </ul>
                ) : null}
                {(section.paragraphsAfter || []).map((p, i) => (
                  <p key={`pa-${i}`}>{renderInline(p, `s${sIdx}-pa${i}`)}</p>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-10 rounded-2xl p-8 text-center"
          style={{ background: 'rgba(var(--c-green-rgb),0.06)', border: '1px solid rgba(var(--c-green-rgb),0.16)' }}>
          <h3 className="font-display font-black text-[var(--c-ink)] text-xl mb-2">{t('privacy.questionsTitle')}</h3>
          <p className="text-[var(--c-muted)] text-sm mb-5">{t('privacy.questionsSubtitle')}</p>
          <a href="/#/contact" className="btn-primary inline-flex">
            {t('privacy.contactUs')} <ArrowLeft className="h-4 w-4 rotate-180" />
          </a>
        </div>
      </div>
    </div>
  );
}
