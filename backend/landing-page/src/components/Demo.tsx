import { useRef, useState, useEffect } from 'react';
import { TrendingUp, Users, DollarSign, BookOpen, Zap, Shield, Globe, Award } from 'lucide-react';

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

const STATS = [
  { icon: Users, value: 300, suffix: '+', label: 'Schools Onboarded', desc: 'Across 26 Nigerian states', color: '#22c55e' },
  { icon: BookOpen, value: 95000, suffix: '+', label: 'Active Students', desc: 'Managed on the platform', color: '#0ea5e9' },
  { icon: DollarSign, value: 450, prefix: '₦', suffix: 'M+', label: 'Fees Processed', desc: 'Through Paystack & transfers', color: '#8b5cf6' },
  { icon: TrendingUp, value: 15000, suffix: '+', label: 'Exams Conducted', desc: 'Online and offline CBT', color: '#f59e0b' },
  { icon: Award, value: 98, suffix: '%', label: 'School Retention', desc: 'Schools that renewed', color: '#10b981' },
  { icon: Zap, value: 4, suffix: 'min', label: 'Setup Time', desc: 'Average onboarding time', color: '#ec4899' },
];

const LOGOS = [
  'Royal Heights Schools', 'Greenfield Academy', 'Stars of Tomorrow', 'Excel Secondary',
  'Hope Foundation Schools', 'Covenant Academy', 'Prestige Group', 'New Dawn College',
  'Heritage Schools', 'Pinnacle Academy', 'Crown Secondary', 'Daystar High School',
];

export default function Demo() {
  const { ref, visible } = useVisible(0.1);

  return (
    <section id="demo" ref={ref} className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 20% 50%, rgba(34,197,94,0.04) 0%, transparent 60%)' }} />

      <div className="max-w-7xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-16"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(24px)', transition: 'all 0.7s ease' }}>
          <span className="badge badge-green mb-4">
            <Globe className="h-3 w-3" /> Platform Impact
          </span>
          <h2 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            Numbers that speak{' '}
            <span className="gradient-text">for themselves</span>
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto">Real schools, real results. Here's the impact Schooldom is making across Nigeria.</p>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-20">
          {STATS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.label}
                className="premium-card p-6 relative overflow-hidden group"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'none' : 'translateY(24px)',
                  transition: `all 0.6s ease ${i * 80}ms`,
                }}
              >
                <div className="absolute -top-6 -right-6 w-24 h-24 rounded-full opacity-5"
                  style={{ background: s.color, filter: 'blur(20px)' }} />
                <Icon className="h-6 w-6 mb-3" style={{ color: s.color }} />
                <p className="font-display font-black text-3xl sm:text-4xl mb-1" style={{ color: s.color }}>
                  <AnimatedCounter target={s.value} prefix={s.prefix} suffix={s.suffix} />
                </p>
                <p className="text-white font-semibold text-sm mb-1">{s.label}</p>
                <p className="text-slate-500 text-xs">{s.desc}</p>
              </div>
            );
          })}
        </div>

        {/* Logo marquee */}
        <div style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.5s' }}>
          <p className="text-center text-slate-600 text-xs uppercase tracking-widest mb-6 font-semibold">Trusted by institutions like</p>
          <div className="overflow-hidden" style={{ maskImage: 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)' }}>
            <div className="flex gap-6 animate-marquee-left" style={{ width: 'max-content' }}>
              {[...LOGOS, ...LOGOS].map((logo, i) => (
                <div key={i} className="flex items-center gap-2 px-5 py-3 rounded-xl shrink-0 sd-card">
                  <div className="w-2 h-2 rounded-full" style={{ background: ['#22c55e', '#0ea5e9', '#8b5cf6', '#f59e0b'][i % 4] }} />
                  <span className="text-slate-400 text-xs font-medium whitespace-nowrap">{logo}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Shield trust bar */}
        <div className="mt-16 rounded-2xl p-6 flex flex-wrap items-center justify-center gap-8 sd-card"
          style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.7s' }}>
          {[
            { icon: Shield, label: 'NDPA Compliant', color: '#22c55e' },
            { icon: Globe, label: 'AWS West Africa', color: '#0ea5e9' },
            { icon: Zap, label: '99.9% Uptime SLA', color: '#8b5cf6' },
            { icon: Award, label: 'ISO 27001 Aligned', color: '#f59e0b' },
          ].map(t => {
            const Icon = t.icon;
            return (
              <div key={t.label} className="flex items-center gap-2">
                <Icon className="h-4 w-4" style={{ color: t.color }} />
                <span className="text-slate-400 text-sm">{t.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
