import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { Star, Quote } from 'lucide-react';
import { Reveal, RevealGroup, revealItem } from '../lib/reveal';

interface TestimonialData { name: string; role: string; quoteKey: string; schoolKey: string; studentsCount: number; initials: string; color: string }

const TESTIMONIALS: TestimonialData[] = [
  { name: 'Mr. Adewale Ogundimu', role: 'Principal, Greenfield Academy, Ibadan', quoteKey: 'adewale', schoolKey: 'k12', studentsCount: 1240, initials: 'AO', color: 'var(--c-green)' },
  { name: 'Mrs. Chidinma Eze', role: 'Bursar, Royal Heights Group of Schools, Enugu', quoteKey: 'chidinma', schoolKey: 'groupOf4', studentsCount: 3800, initials: 'CE', color: '#1d6b3c' },
  { name: 'Mr. Ibrahim Al-Hassan', role: "ICT Coordinator, Al-Noor International Academy, Kano", quoteKey: 'ibrahim', schoolKey: 'islamicSecondary', studentsCount: 680, initials: 'IH', color: '#2f7d4f' },
  { name: 'Mrs. Funmilayo Adesanya', role: 'Head Mistress, Sunrise Nursery & Primary, Lagos', quoteKey: 'funmilayo', schoolKey: 'k12', studentsCount: 420, initials: 'FA', color: '#166534' },
  { name: 'Dr. Emeka Okonkwo', role: 'Registrar, Covenant Vocational College, Owerri', quoteKey: 'emeka', schoolKey: 'vocationalCollege', studentsCount: 600, initials: 'EO', color: '#1f6b43' },
  { name: 'Mrs. Ngozi Okeke', role: 'Director, Prestige Group of Schools, Abuja', quoteKey: 'ngozi', schoolKey: 'groupOf5', studentsCount: 2100, initials: 'NO', color: '#0f3d24' },
  { name: 'Mr. Tunde Adeyemi', role: "Vice Principal, Bishop's Crown Secondary, Abeokuta", quoteKey: 'tunde', schoolKey: 'secondarySchool', studentsCount: 890, initials: 'TA', color: '#3a8f5c' },
  { name: 'Mrs. Halima Yusuf', role: 'Proprietress, New Horizon International, Kaduna', quoteKey: 'halima', schoolKey: 'k12', studentsCount: 560, initials: 'HY', color: '#276b42' },
];

function TestimonialCard({ item }: { item: TestimonialData }) {
  const { t } = useTranslation();
  return (
    <motion.div
      variants={revealItem}
      whileHover={{ y: -4 }}
      transition={{ type: 'spring', stiffness: 300, damping: 22 }}
      className="h-full flex flex-col rounded-2xl p-6 hover:border-[var(--c-green)]/20 transition-colors sd-card"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex">{[...Array(5)].map((_, i) => <Star key={i} className="h-3.5 w-3.5 fill-[var(--c-green)] text-[var(--c-green)]" />)}</div>
        <Quote className="h-5 w-5 opacity-15 text-[var(--c-ink)]" />
      </div>
      <p className="text-[var(--c-ink)] text-sm leading-relaxed mb-5 flex-1">"{t(`testimonials.quotes.${item.quoteKey}`)}"</p>
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
          style={{ background: `${item.color}18`, border: `1px solid ${item.color}35`, color: item.color }}>{item.initials}</div>
        <div>
          <p className="text-[var(--c-ink)] text-sm font-semibold">{item.name}</p>
          <p className="text-[var(--c-subtle)] text-[10px]">{item.role}</p>
        </div>
      </div>
      <div className="mt-4 flex gap-2 flex-wrap">
        <span className="text-[9px] px-2 py-1 rounded-full border" style={{ color: item.color, background: `${item.color}08`, borderColor: `${item.color}25` }}>{t(`testimonials.schoolTypes.${item.schoolKey}`)}</span>
        <span className="text-[9px] px-2 py-1 rounded-full border border-[var(--c-ink)]/8 text-[var(--c-subtle)]">{item.studentsCount.toLocaleString()} {t('testimonials.studentsLabel')}</span>
      </div>
    </motion.div>
  );
}

export default function Testimonials() {
  const { t } = useTranslation();

  return (
    <section id="testimonials" className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 100%, rgba(var(--c-green-rgb),0.05) 0%, transparent 60%)' }} />

      <div className="max-w-7xl mx-auto">
        <Reveal className="mb-14">
          <div className="text-center max-w-3xl mx-auto">
            <span className="badge badge-green mb-4"><Star className="h-3 w-3 fill-current" /> {t('testimonials.badge')}</span>
            <h2 className="font-display font-black text-4xl sm:text-5xl text-[var(--c-ink)] mb-4 tracking-tight">
              {t('testimonials.title')} <span className="gradient-text">{t('testimonials.titleHighlight')}</span>
            </h2>
            <p className="text-[var(--c-muted)]">{t('testimonials.subtitle')}</p>
          </div>
        </Reveal>

        <RevealGroup className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5" stagger={0.06} amount={0.1}>
          {TESTIMONIALS.map((item, i) => <TestimonialCard key={i} item={item} />)}
        </RevealGroup>
      </div>

      <Reveal className="text-center mt-12" y={0} delay={0.3}>
        <div className="inline-flex items-center gap-3 px-6 py-3 rounded-2xl sd-card">
          <div className="flex">{[...Array(5)].map((_, i) => <Star key={i} className="h-4 w-4 fill-[var(--c-green)] text-[var(--c-green)]" />)}</div>
          <span className="text-[var(--c-ink)] font-bold text-lg">4.9 / 5</span>
          <span className="text-[var(--c-subtle)] text-sm">{t('testimonials.ratingSummary')}</span>
        </div>
      </Reveal>
    </section>
  );
}
