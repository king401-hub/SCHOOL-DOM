import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { TrendingUp, Users, DollarSign, BookOpen, Zap, Shield, Globe, Award } from 'lucide-react';
import { Reveal, RevealGroup, revealItem } from '../lib/reveal';

const GREEN = 'var(--c-green)';

function AnimatedCounter({ target, prefix = '', suffix = '' }: { target: number; prefix?: string; suffix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !started.current) {
        started.current = true;
        let start = 0;
        const step = target / 80;
        const t = setInterval(() => {
          start += step;
          if (start >= target) { setCount(target); clearInterval(t); }
          else setCount(Math.floor(start));
        }, 18);
      }
    });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target]);
  return <span ref={ref}>{prefix}{count.toLocaleString()}{suffix}</span>;
}

function buildStats(t: (key: string) => string) {
  return [
    { icon: Users, value: 300, suffix: '+', label: t('demo.stats.schools.label'), desc: t('demo.stats.schools.desc') },
    { icon: BookOpen, value: 95000, suffix: '+', label: t('demo.stats.students.label'), desc: t('demo.stats.students.desc') },
    { icon: DollarSign, value: 450, prefix: '₦', suffix: 'M+', label: t('demo.stats.fees.label'), desc: t('demo.stats.fees.desc') },
    { icon: TrendingUp, value: 15000, suffix: '+', label: t('demo.stats.exams.label'), desc: t('demo.stats.exams.desc') },
    { icon: Award, value: 98, suffix: '%', label: t('demo.stats.retention.label'), desc: t('demo.stats.retention.desc') },
    { icon: Zap, value: 4, suffix: 'min', label: t('demo.stats.setup.label'), desc: t('demo.stats.setup.desc') },
  ];
}

const LOGOS = [
  'Royal Heights Schools', 'Greenfield Academy', 'Stars of Tomorrow', 'Excel Secondary',
  'Hope Foundation Schools', 'Covenant Academy', 'Prestige Group', 'New Dawn College',
  'Heritage Schools', 'Pinnacle Academy', 'Crown Secondary', 'Daystar High School',
];

export default function Demo() {
  const { t } = useTranslation();
  const STATS = buildStats(t);

  return (
    <section id="demo" className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 20% 50%, rgba(var(--c-green-rgb),0.04) 0%, transparent 60%)' }} />

      <div className="max-w-7xl mx-auto">
        {/* Heading */}
        <Reveal className="text-center mb-16">
          <span className="badge mb-4">
            <Globe className="h-3 w-3" /> {t('demo.badge')}
          </span>
          <h2 className="font-display font-bold text-4xl sm:text-5xl text-[var(--c-ink)] mb-4 tracking-tight">
            {t('demo.title')}{' '}
            <span className="gradient-text">{t('demo.titleHighlight')}</span>
          </h2>
          <p className="text-[var(--c-muted)] max-w-xl mx-auto">{t('demo.subtitle')}</p>
        </Reveal>

        {/* Stats grid */}
        <RevealGroup className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-20" stagger={0.08}>
          {STATS.map(s => {
            const Icon = s.icon;
            return (
              <motion.div key={s.label}
                variants={revealItem}
                whileHover={{ y: -5 }}
                transition={{ type: 'spring', stiffness: 300, damping: 22 }}
                className="premium-card p-6 relative overflow-hidden"
              >
                <Icon className="h-6 w-6 mb-3" style={{ color: GREEN }} />
                <p className="font-display font-semibold text-3xl sm:text-4xl mb-1" style={{ color: GREEN }}>
                  <AnimatedCounter target={s.value} prefix={s.prefix} suffix={s.suffix} />
                </p>
                <p className="text-[var(--c-ink)] font-semibold text-sm mb-1">{s.label}</p>
                <p className="text-[var(--c-subtle)] text-xs">{s.desc}</p>
              </motion.div>
            );
          })}
        </RevealGroup>

        {/* Logo marquee */}
        <Reveal duration={0.9} y={0}>
          <p className="text-center text-[var(--c-subtle)] text-xs uppercase tracking-widest mb-6 font-semibold">{t('demo.trustedByInstitutions')}</p>
          <div className="overflow-hidden" style={{ maskImage: 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)' }}>
            <div className="flex gap-6 animate-marquee-left" style={{ width: 'max-content' }}>
              {[...LOGOS, ...LOGOS].map((logo, i) => (
                <div key={i} className="flex items-center gap-2 px-5 py-3 rounded-xl shrink-0 sd-card">
                  <div className="w-2 h-2 rounded-full" style={{ background: GREEN }} />
                  <span className="text-[var(--c-muted)] text-xs font-medium whitespace-nowrap">{logo}</span>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        {/* Trust bar */}
        <Reveal className="mt-16 rounded-2xl p-6 flex flex-wrap items-center justify-center gap-8 sd-card" y={0} duration={0.9}>
          {[
            { icon: Shield, label: t('demo.trust.ndpa') },
            { icon: Globe, label: t('demo.trust.aws') },
            { icon: Zap, label: t('demo.trust.uptime') },
            { icon: Award, label: t('demo.trust.iso') },
          ].map(item => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="flex items-center gap-2">
                <Icon className="h-4 w-4" style={{ color: GREEN }} />
                <span className="text-[var(--c-muted)] text-sm">{item.label}</span>
              </div>
            );
          })}
        </Reveal>
      </div>
    </section>
  );
}
