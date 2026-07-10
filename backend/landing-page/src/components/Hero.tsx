import { useState, useEffect, useRef } from 'react';
import { ArrowRight, Play, TrendingUp, Users, DollarSign, BookOpen, CheckCircle, Bell, Star } from 'lucide-react';

interface HeroProps {
  onGetStarted: () => void;
  onSignIn: () => void;
  onDemo: () => void;
}

const PHRASES = ['K-12 Schools', 'Universities', 'Vocational Centers', 'Groups of Schools'];

function TypewriterText() {
  const [idx, setIdx] = useState(0);
  const [chars, setChars] = useState(0);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    const phrase = PHRASES[idx];
    const delay = deleting ? 40 : chars < phrase.length ? 80 : 1800;
    const t = setTimeout(() => {
      if (!deleting && chars < phrase.length) setChars(c => c + 1);
      else if (!deleting && chars === phrase.length) setDeleting(true);
      else if (deleting && chars > 0) setChars(c => c - 1);
      else { setDeleting(false); setIdx(i => (i + 1) % PHRASES.length); }
    }, delay);
    return () => clearTimeout(t);
  }, [idx, chars, deleting]);
  return (
    <span className="gradient-text font-display">
      {PHRASES[idx].slice(0, chars)}
      <span className="animate-pulse" style={{ color: '#22c55e' }}>|</span>
    </span>
  );
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
        const step = target / 60;
        const t = setInterval(() => {
          start += step;
          if (start >= target) { setCount(target); clearInterval(t); }
          else setCount(Math.floor(start));
        }, 20);
      }
    });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target]);
  return <span ref={ref}>{prefix}{count.toLocaleString()}{suffix}</span>;
}

function DashboardMockup() {
  const [progress, setProgress] = useState(0);
  const [feed, setFeed] = useState(0);
  const bars = [65, 80, 72, 90, 85, 95, 78, 88, 70, 92, 83, 96];
  const feedItems = [
    { icon: DollarSign, msg: '₦42,000 payment received', color: '#22c55e', name: 'Bello F.' },
    { icon: CheckCircle, msg: 'CBT exam submitted', color: '#0ea5e9', name: 'Chidi O.' },
    { icon: Users, msg: 'New student enrolled', color: '#8b5cf6', name: 'Amina Y.' },
    { icon: Bell, msg: 'Attendance alert sent', color: '#f59e0b', name: 'Mrs. Eze' },
  ];
  useEffect(() => {
    const t = setInterval(() => setProgress(p => p >= 100 ? 0 : p + 1.5), 60);
    const f = setInterval(() => setFeed(i => (i + 1) % feedItems.length), 2500);
    return () => { clearInterval(t); clearInterval(f); };
  }, []);

  return (
    <div
      className="relative w-full rounded-2xl overflow-hidden border border-white/8 shadow-2xl"
      style={{
        background: 'rgba(10,15,30,0.9)',
        backdropFilter: 'blur(20px)',
        transform: 'perspective(1200px) rotateY(-5deg) rotateX(3deg)',
        boxShadow: '0 40px 80px rgba(0,0,0,0.5), 0 0 60px rgba(34,197,94,0.08), inset 0 1px 0 rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5" style={{ background: 'rgba(255,255,255,0.02)' }}>
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500/70" />
          <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
          <div className="w-3 h-3 rounded-full bg-green-500/70" />
        </div>
        <div className="flex-1 mx-3 h-6 rounded-lg flex items-center px-3" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <span className="text-slate-600 text-[10px] font-mono">schooldom.app/dashboard</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded-full" style={{ background: 'linear-gradient(135deg, #22c55e, #0ea5e9)' }} />
          <span className="text-white text-[10px]">Admin</span>
        </div>
      </div>

      <div className="flex" style={{ height: 340 }}>
        <div className="w-12 border-r border-white/5 flex flex-col items-center gap-3 pt-4" style={{ background: 'rgba(255,255,255,0.01)' }}>
          {[TrendingUp, Users, DollarSign, BookOpen, Bell].map((Icon, i) => (
            <div key={i} className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{
                background: i === 0 ? 'rgba(34,197,94,0.15)' : 'transparent',
                border: i === 0 ? '1px solid rgba(34,197,94,0.3)' : '1px solid transparent',
              }}>
              <Icon className="h-3.5 w-3.5" style={{ color: i === 0 ? '#22c55e' : '#475569' }} />
            </div>
          ))}
        </div>
        <div className="flex-1 p-4 flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Students', value: '1,842', delta: '+24', color: '#22c55e' },
              { label: 'Fees', value: '₦2.4M', delta: '+18%', color: '#0ea5e9' },
              { label: 'Avg Score', value: '78.4%', delta: '+5.2', color: '#8b5cf6' },
            ].map(s => (
              <div key={s.label} className="rounded-xl p-2.5" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <p className="text-slate-600 text-[9px] uppercase tracking-wider">{s.label}</p>
                <p className="text-white font-bold text-sm font-mono mt-0.5">{s.value}</p>
                <p className="text-[9px] mt-0.5" style={{ color: s.color }}>▲ {s.delta}</p>
              </div>
            ))}
          </div>
          <div className="flex-1 rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-500 text-[9px] uppercase tracking-wider">Term Performance</span>
              <span className="text-[9px] font-mono font-bold animate-pulse" style={{ color: '#22c55e' }}>● LIVE</span>
            </div>
            <div className="flex items-end gap-1 h-20">
              {bars.map((h, i) => (
                <div key={i} className="flex-1 rounded-sm relative overflow-hidden" style={{ height: '100%', background: 'rgba(255,255,255,0.04)' }}>
                  <div className="absolute bottom-0 left-0 right-0 rounded-sm transition-all duration-700"
                    style={{ height: `${progress > 0 ? h : 0}%`, background: 'linear-gradient(to top, #22c55e, #0ea5e9)', opacity: 0.6 + (i % 3) * 0.13, transitionDelay: `${i * 40}ms` }} />
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
            <div className="flex items-center gap-2 px-3 py-2 border-b border-white/4">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[9px] text-white font-semibold">Live Activity</span>
            </div>
            {feedItems.map((item, i) => {
              const Icon = item.icon;
              return (
                <div key={i} className="flex items-center gap-2 px-3 py-2 border-b border-white/3 last:border-0 transition-all duration-500"
                  style={{ opacity: i === feed ? 1 : 0.3, background: i === feed ? `${item.color}06` : 'transparent' }}>
                  <Icon className="h-3 w-3 shrink-0" style={{ color: item.color }} />
                  <span className="text-slate-400 text-[9px] flex-1 truncate">{item.msg}</span>
                  <span className="text-slate-600 text-[8px] shrink-0">{item.name}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Hero({ onGetStarted, onDemo }: HeroProps) {
  const [visible, setVisible] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVisible(true), 100); return () => clearTimeout(t); }, []);

  return (
    <section className="relative min-h-screen flex items-center pt-24 pb-16 px-4 overflow-hidden">
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[400px] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(34,197,94,0.05) 0%, transparent 70%)', filter: 'blur(40px)' }} />

      <div className="max-w-7xl mx-auto w-full">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(30px)', transition: 'all 0.8s ease' }}>
            <div className="inline-flex items-center gap-2 badge badge-green mb-6">
              <Star className="h-3 w-3 fill-current" />
              Africa's #1 School OS
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            </div>

            <h1 className="font-display font-black text-5xl sm:text-6xl lg:text-6xl xl:text-7xl leading-[1.05] tracking-tight mb-6">
              <span className="text-white block">The Complete</span>
              <span className="text-white block">School Platform</span>
              <span className="block mt-1">for <TypewriterText /></span>
            </h1>

            <p className="text-lg text-slate-400 leading-relaxed max-w-xl mb-8">
              From admissions to graduation — manage fees, run CBT exams, track attendance,
              generate report cards, and connect parents. One platform, every school.
            </p>

            <div className="flex flex-wrap gap-4 mb-10">
              <button onClick={onGetStarted} className="btn-primary">
                Get Started Free <ArrowRight className="h-4 w-4" />
              </button>
              <button onClick={onDemo} className="btn-ghost">
                <Play className="h-4 w-4" /> See Live Demo
              </button>
            </div>

            <div className="flex flex-wrap gap-6">
              {[
                { value: 300, suffix: '+', label: 'Schools', color: '#22c55e' },
                { value: 95000, suffix: '+', label: 'Students', color: '#0ea5e9' },
                { value: 450, prefix: '₦', suffix: 'M+', label: 'Processed', color: '#8b5cf6' },
              ].map(s => (
                <div key={s.label}>
                  <p className="font-display font-black text-2xl" style={{ color: s.color }}>
                    <AnimatedCounter target={s.value} prefix={s.prefix} suffix={s.suffix} />
                  </p>
                  <p className="text-slate-500 text-xs mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex items-center gap-3">
              <div className="flex -space-x-2">
                {['BG', 'AG', 'CO', 'EK', 'OS'].map((s, i) => (
                  <div key={i} className="w-8 h-8 rounded-full border-2 border-[#030712] flex items-center justify-center text-[9px] font-bold text-white"
                    style={{ background: ['#22c55e', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ec4899'][i], zIndex: 5 - i }}>
                    {s}
                  </div>
                ))}
              </div>
              <div>
                <div className="flex items-center gap-0.5">
                  {[...Array(5)].map((_, i) => <Star key={i} className="h-3 w-3 fill-yellow-400 text-yellow-400" />)}
                </div>
                <p className="text-slate-500 text-[10px]">Trusted by 300+ institutions</p>
              </div>
            </div>
          </div>

          {/* Dashboard */}
          <div className="relative" style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(30px) translateX(20px)', transition: 'all 0.9s ease 0.2s' }}>
            <DashboardMockup />

            {/* Floating cards */}
            {[
              {
                style: { top: -24, left: -24, animationDelay: '0s', animationDuration: '4s' },
                content: (
                  <div className="flex items-center gap-2">
                    <div className="h-7 w-7 rounded-lg flex items-center justify-center" style={{ background: 'rgba(34,197,94,0.15)' }}>
                      <DollarSign className="h-3.5 w-3.5" style={{ color: '#22c55e' }} />
                    </div>
                    <div><p className="text-white text-xs font-bold">₦2.4M</p><p className="text-slate-500 text-[9px]">Collected today</p></div>
                  </div>
                )
              },
              {
                style: { top: 30, right: -16, animationDelay: '0.8s', animationDuration: '5s' },
                content: (
                  <div className="flex items-center gap-2">
                    <div className="h-7 w-7 rounded-lg flex items-center justify-center" style={{ background: 'rgba(14,165,233,0.15)' }}>
                      <CheckCircle className="h-3.5 w-3.5" style={{ color: '#0ea5e9' }} />
                    </div>
                    <div><p className="text-white text-xs font-bold">127 Exams</p><p className="text-slate-500 text-[9px]">Running now</p></div>
                  </div>
                )
              },
              {
                style: { bottom: 80, right: -12, animationDelay: '1.5s', animationDuration: '4.5s' },
                content: (
                  <>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      <p className="text-white text-xs font-semibold">94.2% Attendance</p>
                    </div>
                    <div className="h-1.5 w-32 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                      <div className="h-full rounded-full" style={{ width: '94%', background: 'linear-gradient(90deg, #22c55e, #0ea5e9)' }} />
                    </div>
                  </>
                )
              },
            ].map((card, i) => (
              <div key={i}
                className="absolute rounded-2xl px-3 py-2.5 border border-white/8 shadow-xl animate-float"
                style={{ background: 'rgba(10,15,30,0.9)', backdropFilter: 'blur(20px)', ...card.style as React.CSSProperties }}>
                {card.content}
              </div>
            ))}

            <div className="absolute inset-0 -z-10 rounded-2xl"
              style={{ background: 'radial-gradient(ellipse at center, rgba(34,197,94,0.08) 0%, transparent 70%)', filter: 'blur(30px)', transform: 'scale(1.2)' }} />
          </div>
        </div>
      </div>
    </section>
  );
}
