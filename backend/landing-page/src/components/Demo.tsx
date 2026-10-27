import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { TrendingUp, Users, DollarSign, BookOpen, Zap, Shield, Globe, Award } from 'lucide-react';

const GREEN = '#14532d';

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
  const { ref, visible } = useVisible(0.1);
  const STATS = buildStats(t);

  return (
    <section id="demo" ref={ref} className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 20% 50%, rgba(20,83,45,0.04) 0%, transparent 60%)' }} />

      <div className="max-w-7xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-16"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(20px)', transition: 'all 0.7s ease' }}>
          <span className="badge mb-4">
            <Globe className="h-3 w-3" /> {t('demo.badge')}
          </span>
          <h2 className="font-display font-bold text-4xl sm:text-5xl text-[#141310] mb-4 tracking-tight">
            {t('demo.title')}{' '}
            <span className="gradient-text">{t('demo.titleHighlight')}</span>
          </h2>
          <p className="text-[#5b5750] max-w-xl mx-auto">{t('demo.subtitle')}</p>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-20">
          {STATS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.label}
                className="premium-card p-6 relative overflow-hidden"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'none' : 'translateY(20px)',
                  transition: `all 0.6s ease ${i * 80}ms`,
                }}
              >
                <Icon className="h-6 w-6 mb-3" style={{ color: GREEN }} />
                <p className="font-display font-semibold text-3xl sm:text-4xl mb-1" style={{ color: GREEN }}>
                  <AnimatedCounter target={s.value} prefix={s.prefix} suffix={s.suffix} />
                </p>
                <p className="text-[#141310] font-semibold text-sm mb-1">{s.label}</p>
                <p className="text-[#8a8378] text-xs">{s.desc}</p>
              </div>
            );
          })}
        </div>

        {/* Logo marquee */}
        <div style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.5s' }}>
          <p className="text-center text-[#8a8378] text-xs uppercase tracking-widest mb-6 font-semibold">{t('demo.trustedByInstitutions')}</p>
          <div className="overflow-hidden" style={{ maskImage: 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)' }}>
            <div className="flex gap-6 animate-marquee-left" style={{ width: 'max-content' }}>
              {[...LOGOS, ...LOGOS].map((logo, i) => (
                <div key={i} className="flex items-center gap-2 px-5 py-3 rounded-xl shrink-0 sd-card">
                  <div className="w-2 h-2 rounded-full" style={{ background: GREEN }} />
                  <span className="text-[#5b5750] text-xs font-medium whitespace-nowrap">{logo}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Trust bar */}
        <div className="mt-16 rounded-2xl p-6 flex flex-wrap items-center justify-center gap-8 sd-card"
          style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.7s' }}>
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
                <span className="text-[#5b5750] text-sm">{item.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
