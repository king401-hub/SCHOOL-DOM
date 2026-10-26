import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Search, ArrowLeft } from 'lucide-react';

const CATEGORY_KEYS = ['pricing', 'cbt', 'finance', 'setup', 'security'] as const;
type CategoryKey = (typeof CATEGORY_KEYS)[number];

const CATEGORY_COLORS: Record<CategoryKey, string> = {
  pricing: '#c9a24e',
  cbt: '#c9a24e',
  finance: '#c9a24e',
  setup: '#c9a24e',
  security: '#c9a24e',
};

interface FaqItem { q: string; a: string }
interface FaqCategory { key: CategoryKey; category: string; color: string; items: FaqItem[] }

function buildFaqs(t: (key: string, options?: Record<string, unknown>) => any): FaqCategory[] {
  return CATEGORY_KEYS.map(key => ({
    key,
    category: t(`faq.categories.${key}`),
    color: CATEGORY_COLORS[key],
    items: t(`faq.items.${key}`, { returnObjects: true }) as FaqItem[],
  }));
}

function AccordionItem({ q, a, color }: { q: string; a: string; color: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-white/5 last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between py-4 text-left cursor-pointer gap-4"
      >
        <span className="text-white text-sm font-medium leading-relaxed">{q}</span>
        <ChevronDown
          className="h-4 w-4 shrink-0 transition-transform duration-200"
          style={{ color, transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        />
      </button>
      <div className="overflow-hidden transition-all duration-300" style={{ maxHeight: open ? 400 : 0 }}>
        <p className="text-slate-400 text-sm leading-relaxed pb-5">{a}</p>
      </div>
    </div>
  );
}

export default function FAQPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const catParam = searchParams.get('cat') ?? '';
  const initialCat: CategoryKey | 'all' = (CATEGORY_KEYS as readonly string[]).includes(catParam) ? (catParam as CategoryKey) : 'all';
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<CategoryKey | 'all'>(initialCat);

  const FAQS = buildFaqs(t);

  const filtered = FAQS.map(cat => ({
    ...cat,
    items: cat.items.filter(item =>
      !search || item.q.toLowerCase().includes(search.toLowerCase()) || item.a.toLowerCase().includes(search.toLowerCase())
    )
  })).filter(cat => (activeCategory === 'all' || cat.key === activeCategory) && cat.items.length > 0);

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(201,162,78,0.05) 0%, transparent 50%)' }} />

      <div className="max-w-3xl mx-auto">
        {/* Back */}
        <a href="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> {t('common.backToHome')}
        </a>

        {/* Header */}
        <div className="text-center mb-12">
          <span className="badge badge-green mb-4">{t('faq.badge')}</span>
          <h1 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            {t('faq.title')} <span className="gradient-text">{t('faq.titleHighlight')}</span>
          </h1>
          <p className="text-slate-400">{t('faq.intro')} <a href="/#/contact" className="hover:underline" style={{ color: '#c9a24e' }}>{t('faq.contactUs')}</a></p>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder={t('faq.searchPlaceholder')}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-11 pr-4 py-3.5 rounded-2xl text-sm sd-input placeholder-slate-600"
          />
        </div>

        {/* Category filters */}
        <div className="flex flex-wrap gap-2 mb-10">
          {([{ key: 'all' as const, label: t('faq.all') }, ...FAQS.map(c => ({ key: c.key, label: c.category }))]).map(cat => (
            <button
              key={cat.key}
              onClick={() => setActiveCategory(cat.key)}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer sd-card-2"
              style={{
                background: activeCategory === cat.key ? 'rgba(201,162,78,0.1)' : undefined,
                borderColor: activeCategory === cat.key ? 'rgba(201,162,78,0.3)' : undefined,
                color: activeCategory === cat.key ? '#c9a24e' : undefined,
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* FAQ sections */}
        <div className="space-y-8">
          {filtered.map(cat => (
            <div key={cat.key} className="rounded-2xl p-6 sd-card">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full" style={{ background: cat.color }} />
                <h2 className="font-bold text-sm" style={{ color: cat.color }}>{cat.category}</h2>
              </div>
              {cat.items.map(item => <AccordionItem key={item.q} q={item.q} a={item.a} color={cat.color} />)}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-16">
              <p className="text-slate-500">{t('faq.noResults')} <a href="/#/contact" className="hover:underline" style={{ color: '#c9a24e' }}>{t('faq.askDirectly')}</a></p>
            </div>
          )}
        </div>

        {/* Still have questions */}
        <div className="mt-14 rounded-2xl p-8 text-center"
          style={{ background: 'rgba(201,162,78,0.07)', border: '1px solid rgba(201,162,78,0.2)' }}>
          <h3 className="font-display font-semibold text-white text-xl mb-2">{t('faq.stillQuestionsTitle')}</h3>
          <p className="text-slate-400 text-sm mb-5">{t('faq.stillQuestionsSubtitle')}</p>
          <a href="/#/contact" className="btn-primary inline-flex">
            {t('faq.contactSupport')} <ArrowLeft className="h-4 w-4 rotate-180" />
          </a>
        </div>
      </div>
    </div>
  );
}
