import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Star, Quote } from 'lucide-react';

interface TestimonialData { name: string; role: string; quoteKey: string; schoolKey: string; studentsCount: number; initials: string; color: string }

const TESTIMONIALS: TestimonialData[] = [
  { name: 'Mr. Adewale Ogundimu', role: 'Principal, Greenfield Academy, Ibadan', quoteKey: 'adewale', schoolKey: 'k12', studentsCount: 1240, initials: 'AO', color: '#14532d' },
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
    <div className="shrink-0 w-80 rounded-2xl p-6 mx-2 hover:border-[#14532d]/20 transition-all sd-card">
      <div className="flex items-start justify-between mb-4">
        <div className="flex">{[...Array(5)].map((_, i) => <Star key={i} className="h-3.5 w-3.5 fill-[#14532d] text-[#14532d]" />)}</div>
        <Quote className="h-5 w-5 opacity-15 text-[#141310]" />
      </div>
      <p className="text-[#3a362f] text-sm leading-relaxed mb-5">"{t(`testimonials.quotes.${item.quoteKey}`)}"</p>
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
          style={{ background: `${item.color}18`, border: `1px solid ${item.color}35`, color: item.color }}>{item.initials}</div>
        <div>
          <p className="text-[#141310] text-sm font-semibold">{item.name}</p>
          <p className="text-[#8a8378] text-[10px]">{item.role}</p>
        </div>
      </div>
      <div className="mt-4 flex gap-2 flex-wrap">
        <span className="text-[9px] px-2 py-1 rounded-full border" style={{ color: item.color, background: `${item.color}08`, borderColor: `${item.color}25` }}>{t(`testimonials.schoolTypes.${item.schoolKey}`)}</span>
        <span className="text-[9px] px-2 py-1 rounded-full border border-black/8 text-[#8a8378]">{item.studentsCount.toLocaleString()} {t('testimonials.studentsLabel')}</span>
      </div>
    </div>
  );
}

function useVisible(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

export default function Testimonials() {
  const { t } = useTranslation();
  const { ref, visible } = useVisible(0.1);
  const row1 = TESTIMONIALS.slice(0, 4);
  const row2 = TESTIMONIALS.slice(4);

  return (
    <section id="testimonials" ref={ref} className="py-28 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 100%, rgba(20,83,45,0.05) 0%, transparent 60%)' }} />

      <div className="mb-14 px-4"
        style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(24px)', transition: 'all 0.7s ease' }}>
        <div className="text-center max-w-3xl mx-auto">
          <span className="badge badge-green mb-4"><Star className="h-3 w-3 fill-current" /> {t('testimonials.badge')}</span>
          <h2 className="font-display font-black text-4xl sm:text-5xl text-[#141310] mb-4 tracking-tight">
            {t('testimonials.title')} <span className="gradient-text">{t('testimonials.titleHighlight')}</span>
          </h2>
          <p className="text-[#5b5750]">{t('testimonials.subtitle')}</p>
        </div>
      </div>

      <div className="overflow-hidden mb-4"
        style={{ maskImage: 'linear-gradient(90deg, transparent, black 8%, black 92%, transparent)', opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.3s' }}>
        <div className="flex animate-marquee-left" style={{ width: 'max-content' }}>
          {[...row1, ...row1].map((item, i) => <TestimonialCard key={i} item={item} />)}
        </div>
      </div>

      <div className="overflow-hidden"
        style={{ maskImage: 'linear-gradient(90deg, transparent, black 8%, black 92%, transparent)', opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.5s' }}>
        <div className="flex animate-marquee-right" style={{ width: 'max-content' }}>
          {[...row2, ...row2].map((item, i) => <TestimonialCard key={i} item={item} />)}
        </div>
      </div>

      <div className="text-center mt-12 px-4"
        style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.7s' }}>
        <div className="inline-flex items-center gap-3 px-6 py-3 rounded-2xl sd-card">
          <div className="flex">{[...Array(5)].map((_, i) => <Star key={i} className="h-4 w-4 fill-[#14532d] text-[#14532d]" />)}</div>
          <span className="text-[#141310] font-bold text-lg">4.9 / 5</span>
          <span className="text-[#8a8378] text-sm">{t('testimonials.ratingSummary')}</span>
        </div>
      </div>
    </section>
  );
}
