import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';

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
      return <a key={`${keyPrefix}-${i}`} href={`mailto:${MAIL}`} className="hover:underline" style={{ color: '#c9a24e' }}>{part}</a>;
    }
    if (part === NDPC) {
      return <a key={`${keyPrefix}-${i}`} href={`http://${NDPC}`} target="_blank" rel="noreferrer" className="hover:underline" style={{ color: '#c9a24e' }}>{part}</a>;
    }
    return part;
  });
}

function renderInline(text: string, keyPrefix: string): ReactNode {
  const boldParts = text.split(/(\*\*[^*]+\*\*)/g);
  return boldParts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${keyPrefix}-b-${i}`} className="text-white">{linkify(part.slice(2, -2), `${keyPrefix}-b-${i}`)}</strong>;
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
  const sections = t('privacy.sections', { returnObjects: true }) as PrivacySection[];

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(201,162,78,0.05) 0%, transparent 50%)' }} />

      <div className="max-w-3xl mx-auto">
        <a href="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> {t('common.backToHome')}
        </a>

        <div className="text-center mb-12">
          <span className="badge badge-green mb-4">{t('privacy.badge')}</span>
          <h1 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            {t('privacy.title')} <span className="gradient-text">{t('privacy.titleHighlight')}</span>
          </h1>
          <p className="text-slate-400">{t('privacy.lastUpdated')}</p>
        </div>

        <div className="rounded-2xl p-6 sd-card mb-6">
          <p className="text-slate-400 text-sm leading-relaxed">
            {t('privacy.intro')}
          </p>
        </div>

        <div className="space-y-6">
          {sections.map((section, sIdx) => (
            <div key={section.title} className="rounded-2xl p-6 sd-card">
              <h2 className="font-bold text-white text-lg mb-3">{section.title}</h2>
              <div className="text-slate-400 text-sm leading-relaxed space-y-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2 [&_li]:marker:text-[#c9a24e]">
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
          style={{ background: 'rgba(201,162,78,0.07)', border: '1px solid rgba(201,162,78,0.15)' }}>
          <h3 className="font-display font-black text-white text-xl mb-2">{t('privacy.questionsTitle')}</h3>
          <p className="text-slate-400 text-sm mb-5">{t('privacy.questionsSubtitle')}</p>
          <a href="/#/contact" className="btn-primary inline-flex">
            {t('privacy.contactUs')} <ArrowLeft className="h-4 w-4 rotate-180" />
          </a>
        </div>
      </div>
    </div>
  );
}
