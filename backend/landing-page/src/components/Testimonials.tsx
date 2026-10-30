import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useReducedMotion } from 'motion/react';
import { Star, Quote, ChevronLeft, ChevronRight } from 'lucide-react';
import { Reveal } from '../lib/reveal';

interface TestimonialData { name: string; role: string; quoteKey: string; schoolKey: string; studentsCount: number; initials: string; color: string }

const TESTIMONIALS: TestimonialData[] = [
  { name: 'Mr. Adewale Ogundimu', role: 'Principal, Greenfield Academy, Ibadan', quoteKey: 'adewale', schoolKey: 'k12', studentsCount: 1240, initials: 'AO', color: '#4ade80' },
  { name: 'Mrs. Chidinma Eze', role: 'Bursar, Royal Heights Group of Schools, Enugu', quoteKey: 'chidinma', schoolKey: 'groupOf4', studentsCount: 3800, initials: 'CE', color: '#34d399' },
  { name: 'Mr. Ibrahim Al-Hassan', role: "ICT Coordinator, Al-Noor International Academy, Kano", quoteKey: 'ibrahim', schoolKey: 'islamicSecondary', studentsCount: 680, initials: 'IH', color: '#6ee7b7' },
  { name: 'Mrs. Funmilayo Adesanya', role: 'Head Mistress, Sunrise Nursery & Primary, Lagos', quoteKey: 'funmilayo', schoolKey: 'k12', studentsCount: 420, initials: 'FA', color: '#4ade80' },
  { name: 'Dr. Emeka Okonkwo', role: 'Registrar, Covenant Vocational College, Owerri', quoteKey: 'emeka', schoolKey: 'vocationalCollege', studentsCount: 600, initials: 'EO', color: '#86efac' },
  { name: 'Mrs. Ngozi Okeke', role: 'Director, Prestige Group of Schools, Abuja', quoteKey: 'ngozi', schoolKey: 'groupOf5', studentsCount: 2100, initials: 'NO', color: '#34d399' },
  { name: 'Mr. Tunde Adeyemi', role: "Vice Principal, Bishop's Crown Secondary, Abeokuta", quoteKey: 'tunde', schoolKey: 'secondarySchool', studentsCount: 890, initials: 'TA', color: '#6ee7b7' },
  { name: 'Mrs. Halima Yusuf', role: 'Proprietress, New Horizon International, Kaduna', quoteKey: 'halima', schoolKey: 'k12', studentsCount: 560, initials: 'HY', color: '#4ade80' },
];

const COUNT = TESTIMONIALS.length;
const AUTOPLAY_MS = 6000;
const wrap = (n: number) => ((n % COUNT) + COUNT) % COUNT;

type Breakpoint = 'base' | 'sm' | 'lg' | 'xl';

function getBreakpoint(): Breakpoint {
  if (typeof window === 'undefined') return 'lg';
  const w = window.innerWidth;
  if (w >= 1280) return 'xl';
  if (w >= 1024) return 'lg';
  if (w >= 640) return 'sm';
  return 'base';
}

/** The much larger cards at lg/xl need proportionally larger peek offsets or
 * the adjacent-card preview effect disappears behind the active card. */
function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(getBreakpoint);
  useEffect(() => {
    const onResize = () => setBp(getBreakpoint());
    window.addEventListener('resize', onResize, { passive: true });
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return bp;
}

const PEEK: Record<Breakpoint, { d1: number; d2: number }> = {
  base: { d1: 50, d2: 90 },
  sm: { d1: 100, d2: 170 },
  lg: { d1: 180, d2: 300 },
  xl: { d1: 240, d2: 390 },
};

/** Shortest signed distance from `index` to `i` around the circular deck. */
function circularDiff(i: number, index: number) {
  let diff = i - index;
  if (diff > COUNT / 2) diff -= COUNT;
  if (diff < -COUNT / 2) diff += COUNT;
  return diff;
}

function slotStyle(diff: number, reduced: boolean, bp: Breakpoint) {
  if (diff === 0) return { x: 0, scale: 1, opacity: 1, rotateY: 0, zIndex: 30 };
  if (reduced) return { x: 0, scale: 1, opacity: 0, rotateY: 0, zIndex: 20 - Math.abs(diff) };
  const sign = diff > 0 ? 1 : -1;
  const { d1, d2 } = PEEK[bp];
  if (Math.abs(diff) === 1) return { x: sign * d1, scale: 0.9, opacity: 0.5, rotateY: sign * -8, zIndex: 20 };
  return { x: sign * d2, scale: 0.8, opacity: 0, rotateY: sign * -14, zIndex: 10 };
}

function TestimonialSlide({
  item, i, diff, reduced, bp, onDragEnd,
}: { item: TestimonialData; i: number; diff: number; reduced: boolean; bp: Breakpoint; onDragEnd: (e: unknown, info: { offset: { x: number }; velocity: { x: number } }) => void }) {
  const { t } = useTranslation();
  const active = diff === 0;
  const style = slotStyle(diff, reduced, bp);
  const sign = diff === 0 ? 0 : diff > 0 ? 1 : -1;

  return (
    <motion.div
      className="absolute inset-0 flex items-center justify-center"
      style={{ zIndex: style.zIndex, pointerEvents: active ? 'auto' : 'none' }}
      initial={reduced ? { opacity: 0 } : { x: sign * 260, scale: 0.75, opacity: 0, rotateY: sign * -16 }}
      animate={{ x: style.x, scale: style.scale, opacity: style.opacity, rotateY: style.rotateY }}
      transition={{ type: 'spring', stiffness: 260, damping: 28, mass: 0.9 }}
      drag={active && !reduced ? 'x' : false}
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.18}
      onDragEnd={active ? onDragEnd : undefined}
      aria-hidden={!active}
      role="group"
      aria-roledescription="slide"
      aria-label={`${i + 1} of ${COUNT}`}
    >
      <div
        className="w-[88vw] max-w-[380px] sm:max-w-[560px] lg:max-w-[700px] xl:max-w-[820px] rounded-[28px] sm:rounded-[32px] lg:rounded-[40px] p-7 sm:p-9 lg:p-12 xl:p-14"
        style={{
          background: active
            ? 'linear-gradient(165deg, rgba(255,255,255,0.09), rgba(255,255,255,0.02))'
            : 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.12)',
          boxShadow: active
            ? '0 40px 90px -24px rgba(0,0,0,0.55), 0 0 0 1px rgba(74,222,128,0.08), 0 1px 0 rgba(255,255,255,0.08) inset'
            : 'none',
          backdropFilter: active ? 'blur(16px)' : 'none',
          WebkitBackdropFilter: active ? 'blur(16px)' : 'none',
        }}
      >
        <div className="flex items-start justify-between mb-5 sm:mb-6 lg:mb-8">
          <div className="flex gap-0.5">{[...Array(5)].map((_, s) => <Star key={s} className="h-3.5 w-3.5 sm:h-4 sm:w-4 lg:h-5 lg:w-5 fill-[#4ade80] text-[#4ade80]" />)}</div>
          <Quote className="h-5 w-5 lg:h-7 lg:w-7 opacity-20 text-white" />
        </div>
        <p className="text-[15px] sm:text-lg lg:text-xl leading-relaxed mb-6 sm:mb-8 lg:mb-10" style={{ color: 'rgba(255,255,255,0.92)' }}>
          "{t(`testimonials.quotes.${item.quoteKey}`)}"
        </p>
        <div className="flex items-center gap-3 sm:gap-4">
          <div
            className="h-10 w-10 sm:h-12 sm:w-12 lg:h-14 lg:w-14 rounded-full flex items-center justify-center text-sm sm:text-base lg:text-lg font-bold shrink-0"
            style={{ background: `${item.color}22`, border: `1px solid ${item.color}55`, color: item.color }}
          >
            {item.initials}
          </div>
          <div>
            <p className="text-sm sm:text-base lg:text-lg font-semibold" style={{ color: '#f5f6fb' }}>{item.name}</p>
            <p className="text-[10px] sm:text-xs lg:text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>{item.role}</p>
          </div>
        </div>
        <div className="mt-4 sm:mt-5 lg:mt-6 flex gap-2 flex-wrap">
          <span
            className="text-[9px] sm:text-[10px] lg:text-xs px-2 py-1 sm:px-2.5 lg:px-3 lg:py-1.5 rounded-full border"
            style={{ color: item.color, background: `${item.color}12`, borderColor: `${item.color}35` }}
          >
            {t(`testimonials.schoolTypes.${item.schoolKey}`)}
          </span>
          <span className="text-[9px] sm:text-[10px] lg:text-xs px-2 py-1 sm:px-2.5 lg:px-3 lg:py-1.5 rounded-full border" style={{ borderColor: 'rgba(255,255,255,0.14)', color: 'rgba(255,255,255,0.55)' }}>
            {item.studentsCount.toLocaleString()} {t('testimonials.studentsLabel')}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

export default function Testimonials() {
  const { t } = useTranslation();
  const reduced = !!useReducedMotion();
  const bp = useBreakpoint();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [announceIdx, setAnnounceIdx] = useState<number | null>(null);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => setIndex((i) => wrap(i + 1)), AUTOPLAY_MS);
    return () => clearInterval(id);
  }, [paused]);

  const goTo = (i: number) => {
    setIndex(wrap(i));
    setAnnounceIdx(wrap(i));
  };
  const paginate = (dir: number) => goTo(index + dir);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); paginate(-1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); paginate(1); }
  };

  const onDragEnd = (_: unknown, info: { offset: { x: number }; velocity: { x: number } }) => {
    const threshold = 80;
    if (info.offset.x < -threshold || info.velocity.x < -400) paginate(1);
    else if (info.offset.x > threshold || info.velocity.x > 400) paginate(-1);
  };

  const visible = TESTIMONIALS
    .map((item, i) => ({ item, i, diff: circularDiff(i, index) }))
    .filter(({ diff }) => Math.abs(diff) <= 2);

  return (
    <section
      id="testimonials"
      className="testimonial-dark-section keep-dark relative overflow-hidden flex flex-col justify-center py-20 lg:py-24 lg:min-h-screen"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="testimonial-blob testimonial-blob-1" />
        <div className="testimonial-blob testimonial-blob-2" />
        <div className="testimonial-blob testimonial-blob-3" />
      </div>

      <div className="w-full max-w-[1800px] mx-auto px-4 sm:px-8 lg:px-12 xl:px-16 relative">
        <Reveal className="mb-12 lg:mb-16">
          <div className="text-center max-w-3xl mx-auto">
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-semibold tracking-wider uppercase mb-4"
              style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80', border: '1px solid rgba(74,222,128,0.3)' }}
            >
              <Star className="h-3 w-3 fill-current" /> {t('testimonials.badge')}
            </span>
            <h2 className="font-display font-black text-4xl sm:text-5xl mb-4 tracking-tight" style={{ color: '#f5f6fb' }}>
              {t('testimonials.title')}{' '}
              <span style={{ background: 'linear-gradient(90deg, #4ade80, #86efac)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
                {t('testimonials.titleHighlight')}
              </span>
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.6)' }}>{t('testimonials.subtitle')}</p>
          </div>
        </Reveal>

        <Reveal y={16} delay={0.1}>
          <div
            className="relative w-full mx-auto min-h-[380px] sm:min-h-[440px] lg:min-h-[560px] xl:min-h-[620px] flex items-center justify-center focus:outline-none"
            style={{ perspective: 1800 }}
            tabIndex={0}
            role="region"
            aria-roledescription="carousel"
            aria-label={t('testimonials.title')}
            onKeyDown={onKeyDown}
          >
            {visible.map(({ item, i, diff }) => (
              <TestimonialSlide key={i} item={item} i={i} diff={diff} reduced={reduced} bp={bp} onDragEnd={onDragEnd} />
            ))}

            <button
              type="button"
              aria-label="Previous testimonial"
              onClick={() => paginate(-1)}
              className="testimonial-nav-btn absolute left-2 sm:left-4 lg:left-10 xl:left-16 top-1/2 -translate-y-1/2 z-40 h-11 w-11 sm:h-12 sm:w-12 lg:h-14 lg:w-14 rounded-full flex items-center justify-center"
            >
              <ChevronLeft className="h-5 w-5 lg:h-6 lg:w-6" />
            </button>
            <button
              type="button"
              aria-label="Next testimonial"
              onClick={() => paginate(1)}
              className="testimonial-nav-btn absolute right-2 sm:right-4 lg:right-10 xl:right-16 top-1/2 -translate-y-1/2 z-40 h-11 w-11 sm:h-12 sm:w-12 lg:h-14 lg:w-14 rounded-full flex items-center justify-center"
            >
              <ChevronRight className="h-5 w-5 lg:h-6 lg:w-6" />
            </button>
          </div>
        </Reveal>

        <div className="flex items-center justify-center gap-2 mt-8 lg:mt-10">
          {TESTIMONIALS.map((_, i) => (
            <button
              key={i}
              type="button"
              aria-label={`Go to testimonial ${i + 1}`}
              aria-current={i === index}
              onClick={() => goTo(i)}
              className="h-1.5 lg:h-2 rounded-full transition-all"
              style={{ width: i === index ? 26 : 8, background: i === index ? '#4ade80' : 'rgba(255,255,255,0.25)' }}
            />
          ))}
        </div>

        {announceIdx !== null && (
          <div className="sr-only" aria-live="polite">
            {`Testimonial ${announceIdx + 1} of ${COUNT}: ${TESTIMONIALS[announceIdx].name}`}
          </div>
        )}

        <Reveal className="text-center mt-10 lg:mt-14 relative" y={0} delay={0.3}>
          <div
            className="inline-flex items-center gap-3 px-6 py-3 sm:px-7 sm:py-3.5 lg:px-8 lg:py-4 rounded-2xl"
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)' }}
          >
            <div className="flex">{[...Array(5)].map((_, s) => <Star key={s} className="h-4 w-4 lg:h-5 lg:w-5 fill-[#4ade80] text-[#4ade80]" />)}</div>
            <span className="font-bold text-lg lg:text-xl" style={{ color: '#f5f6fb' }}>4.9 / 5</span>
            <span className="text-sm" style={{ color: 'rgba(255,255,255,0.55)' }}>{t('testimonials.ratingSummary')}</span>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
