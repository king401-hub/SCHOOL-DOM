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

/** Shortest signed distance from `index` to `i` around the circular deck. */
function circularDiff(i: number, index: number) {
  let diff = i - index;
  if (diff > COUNT / 2) diff -= COUNT;
  if (diff < -COUNT / 2) diff += COUNT;
  return diff;
}

function slotStyle(diff: number, reduced: boolean) {
  if (diff === 0) return { x: 0, scale: 1, opacity: 1, rotateY: 0, zIndex: 30 };
  if (reduced) return { x: 0, scale: 1, opacity: 0, rotateY: 0, zIndex: 20 - Math.abs(diff) };
  const sign = diff > 0 ? 1 : -1;
  if (Math.abs(diff) === 1) return { x: sign * 56, scale: 0.9, opacity: 0.5, rotateY: sign * -8, zIndex: 20 };
  return { x: sign * 88, scale: 0.8, opacity: 0, rotateY: sign * -14, zIndex: 10 };
}

function TestimonialSlide({
  item, i, diff, reduced, onDragEnd,
}: { item: TestimonialData; i: number; diff: number; reduced: boolean; onDragEnd: (e: unknown, info: { offset: { x: number }; velocity: { x: number } }) => void }) {
  const { t } = useTranslation();
  const active = diff === 0;
  const style = slotStyle(diff, reduced);
  const sign = diff === 0 ? 0 : diff > 0 ? 1 : -1;

  return (
    <motion.div
      className="absolute inset-0 flex items-center justify-center"
      style={{ zIndex: style.zIndex, pointerEvents: active ? 'auto' : 'none' }}
      initial={reduced ? { opacity: 0 } : { x: sign * 130, scale: 0.75, opacity: 0, rotateY: sign * -16 }}
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
        className="w-full max-w-md rounded-[28px] p-7 sm:p-8"
        style={{
          background: active
            ? 'linear-gradient(165deg, rgba(255,255,255,0.09), rgba(255,255,255,0.02))'
            : 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.12)',
          boxShadow: active ? '0 30px 70px -22px rgba(0,0,0,0.55), 0 1px 0 rgba(255,255,255,0.08) inset' : 'none',
          backdropFilter: active ? 'blur(16px)' : 'none',
          WebkitBackdropFilter: active ? 'blur(16px)' : 'none',
        }}
      >
        <div className="flex items-start justify-between mb-5">
          <div className="flex">{[...Array(5)].map((_, s) => <Star key={s} className="h-3.5 w-3.5 fill-[#4ade80] text-[#4ade80]" />)}</div>
          <Quote className="h-5 w-5 opacity-20 text-white" />
        </div>
        <p className="text-[15px] leading-relaxed mb-6" style={{ color: 'rgba(255,255,255,0.92)' }}>
          "{t(`testimonials.quotes.${item.quoteKey}`)}"
        </p>
        <div className="flex items-center gap-3">
          <div
            className="h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
            style={{ background: `${item.color}22`, border: `1px solid ${item.color}55`, color: item.color }}
          >
            {item.initials}
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: '#f5f6fb' }}>{item.name}</p>
            <p className="text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{item.role}</p>
          </div>
        </div>
        <div className="mt-4 flex gap-2 flex-wrap">
          <span
            className="text-[9px] px-2 py-1 rounded-full border"
            style={{ color: item.color, background: `${item.color}12`, borderColor: `${item.color}35` }}
          >
            {t(`testimonials.schoolTypes.${item.schoolKey}`)}
          </span>
          <span className="text-[9px] px-2 py-1 rounded-full border" style={{ borderColor: 'rgba(255,255,255,0.14)', color: 'rgba(255,255,255,0.55)' }}>
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
      className="testimonial-dark-section keep-dark py-28 px-4 relative overflow-hidden"
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

      <div className="max-w-5xl mx-auto relative">
        <Reveal className="mb-14">
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
            className="relative mx-auto min-h-[400px] flex items-center justify-center focus:outline-none"
            style={{ maxWidth: 560, perspective: 1400 }}
            tabIndex={0}
            role="region"
            aria-roledescription="carousel"
            aria-label={t('testimonials.title')}
            onKeyDown={onKeyDown}
          >
            {visible.map(({ item, i, diff }) => (
              <TestimonialSlide key={i} item={item} i={i} diff={diff} reduced={reduced} onDragEnd={onDragEnd} />
            ))}

            <button
              type="button"
              aria-label="Previous testimonial"
              onClick={() => paginate(-1)}
              className="testimonial-nav-btn absolute left-0 sm:-left-4 top-1/2 -translate-y-1/2 z-40 h-10 w-10 rounded-full flex items-center justify-center"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              type="button"
              aria-label="Next testimonial"
              onClick={() => paginate(1)}
              className="testimonial-nav-btn absolute right-0 sm:-right-4 top-1/2 -translate-y-1/2 z-40 h-10 w-10 rounded-full flex items-center justify-center"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </Reveal>

        <div className="flex items-center justify-center gap-2 mt-8">
          {TESTIMONIALS.map((_, i) => (
            <button
              key={i}
              type="button"
              aria-label={`Go to testimonial ${i + 1}`}
              aria-current={i === index}
              onClick={() => goTo(i)}
              className="h-1.5 rounded-full transition-all"
              style={{ width: i === index ? 22 : 7, background: i === index ? '#4ade80' : 'rgba(255,255,255,0.25)' }}
            />
          ))}
        </div>

        {announceIdx !== null && (
          <div className="sr-only" aria-live="polite">
            {`Testimonial ${announceIdx + 1} of ${COUNT}: ${TESTIMONIALS[announceIdx].name}`}
          </div>
        )}
      </div>

      <Reveal className="text-center mt-14 relative" y={0} delay={0.3}>
        <div
          className="inline-flex items-center gap-3 px-6 py-3 rounded-2xl"
          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)' }}
        >
          <div className="flex">{[...Array(5)].map((_, s) => <Star key={s} className="h-4 w-4 fill-[#4ade80] text-[#4ade80]" />)}</div>
          <span className="font-bold text-lg" style={{ color: '#f5f6fb' }}>4.9 / 5</span>
          <span className="text-sm" style={{ color: 'rgba(255,255,255,0.55)' }}>{t('testimonials.ratingSummary')}</span>
        </div>
      </Reveal>
    </section>
  );
}
