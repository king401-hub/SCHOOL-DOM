import { useState, useEffect, useRef } from 'react';
import { ArrowRight, Play, TrendingUp, Users, DollarSign, BookOpen, CheckCircle, Bell, Star, BarChart3 } from 'lucide-react';

interface HeroProps {
  onGetStarted: () => void;
  onSignIn: () => void;
  onDemo: () => void;
}

const PHRASES = ['K-12 Schools', 'Universities', 'Vocational Centers', 'Groups of Schools'];

function TypewriterCycle() {
  const [idx, setIdx] = useState(0);
  const [chars, setChars] = useState(0);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    const phrase = PHRASES[idx];
    const delay = deleting ? 35 : chars < phrase.length ? 75 : 1600;
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
      {PHRASES[idx].slice(0, chars)}<span className="opacity-60">|</span>
    </span>
  );
}

function AnimatedNum({ to, prefix = '', suffix = '' }: { to: number; prefix?: string; suffix?: string }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLElement>(null);
  const ran = useRef(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !ran.current) {
        ran.current = true;
        let n = 0;
        const step = to / 70;
        const t = setInterval(() => { n += step; if (n >= to) { setVal(to); clearInterval(t); } else setVal(Math.floor(n)); }, 18);
      }
    });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [to]);
  return <b ref={ref}>{prefix}{val.toLocaleString()}{suffix}</b>;
}

/* ── Full-width browser frame dashboard ─────────────────── */
function DashboardFrame() {
  const [prog, setProg] = useState(0);
  const [feed, setFeed] = useState(0);
  const bars = [62, 78, 55, 88, 73, 95, 66, 84, 71, 90, 80, 96];
  const feedItems = [
    { icon: DollarSign, msg: '₦42,000 payment received', sub: 'Bello Fatima', color: '#22c55e' },
    { icon: CheckCircle, msg: 'CBT exam submitted: Chemistry SS3', sub: 'Chidi Okonkwo', color: '#0ea5e9' },
    { icon: Users, msg: 'New student enrolled: JSS1', sub: 'Amina Yusuf', color: '#8b5cf6' },
    { icon: Bell, msg: 'Attendance alert sent to parent', sub: 'Ngozi Eze — JSS2A', color: '#f59e0b' },
    { icon: BookOpen, msg: 'Report card generated: SS3A', sub: 'Tunde Adeyemi', color: '#10b981' },
  ];
  useEffect(() => {
    const t = setInterval(() => setProg(p => (p >= 100 ? 0 : p + 2)), 60);
    const f = setInterval(() => setFeed(i => (i + 1) % feedItems.length), 2200);
    return () => { clearInterval(t); clearInterval(f); };
  }, []);

  return (
    <div
      className="w-full rounded-2xl overflow-hidden border border-white/10"
      style={{
        background: 'rgba(8,12,24,0.98)',
        boxShadow: '0 60px 120px rgba(0,0,0,0.7), 0 0 80px rgba(34,197,94,0.06), inset 0 1px 0 rgba(255,255,255,0.06)',
      }}
    >
      {/* Browser chrome */}
      <div className="flex items-center gap-3 px-5 py-3.5 border-b border-white/5"
        style={{ background: 'rgba(255,255,255,0.02)' }}>
        <div className="flex gap-1.5 shrink-0">
          <div className="w-3 h-3 rounded-full" style={{ background: '#ff5f57' }} />
          <div className="w-3 h-3 rounded-full" style={{ background: '#febc2e' }} />
          <div className="w-3 h-3 rounded-full" style={{ background: '#28c840' }} />
        </div>
        <div className="flex-1 flex items-center gap-2 px-4 py-1.5 rounded-lg mx-2"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.05)', maxWidth: 360 }}>
          <div className="w-2.5 h-2.5 rounded-full border border-white/20 shrink-0" />
          <span className="text-slate-500 text-xs font-mono">schooldom.app/dashboard</span>
        </div>
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-[10px] text-slate-500">Live</span>
          <div className="w-7 h-7 rounded-full ml-2 flex items-center justify-center text-xs font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #22c55e, #0ea5e9)' }}>A</div>
        </div>
      </div>

      {/* Dashboard body */}
      <div className="flex" style={{ height: 400 }}>
        {/* Sidebar */}
        <div className="w-14 shrink-0 border-r border-white/5 flex flex-col items-center gap-2 pt-5 pb-3"
          style={{ background: 'rgba(255,255,255,0.01)' }}>
          {[TrendingUp, Users, DollarSign, BookOpen, BarChart3, Bell].map((Icon, i) => (
            <button key={i}
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-all"
              style={{
                background: i === 0 ? 'rgba(34,197,94,0.15)' : 'transparent',
                border: i === 0 ? '1px solid rgba(34,197,94,0.3)' : '1px solid transparent',
              }}>
              <Icon className="h-4 w-4" style={{ color: i === 0 ? '#22c55e' : '#334155' }} />
            </button>
          ))}
        </div>

        {/* Main area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top stats bar */}
          <div className="flex items-center gap-3 px-5 py-3 border-b border-white/5 overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.01)' }}>
            <h2 className="text-white text-sm font-semibold mr-4 shrink-0 hidden sm:block">Overview</h2>
            {[
              { label: 'Students', val: '1,842', delta: '+24 this week', color: '#22c55e', cls: '' },
              { label: 'Fees Collected', val: '₦2.4M', delta: '+18% this term', color: '#0ea5e9', cls: '' },
              { label: 'Avg Score', val: '78.4%', delta: '+5.2pts', color: '#8b5cf6', cls: 'hidden md:flex' },
              { label: 'Exams Active', val: '127', delta: 'Right now', color: '#f59e0b', cls: 'hidden lg:flex' },
            ].map(s => (
              <div key={s.label} className={`flex items-center gap-3 px-4 py-2 rounded-xl shrink-0 ${s.cls}`}
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <div>
                  <p className="text-slate-500 text-[9px] uppercase tracking-wider">{s.label}</p>
                  <p className="text-white font-bold text-sm font-mono">{s.val}</p>
                </div>
                <p className="text-[9px] hidden sm:block" style={{ color: s.color }}>{s.delta}</p>
              </div>
            ))}
          </div>

          {/* Two column content */}
          <div className="flex flex-1 gap-0 overflow-hidden">
            {/* Chart */}
            <div className="flex-1 p-5 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-white text-xs font-semibold">Term 2 Performance</p>
                  <p className="text-slate-500 text-[10px]">Weekly exam score averages</p>
                </div>
                <div className="flex items-center gap-1.5 text-[9px] font-bold px-2 py-1 rounded-full"
                  style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />LIVE
                </div>
              </div>
              <div className="flex-1 flex items-end gap-1.5">
                {bars.map((h, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full rounded-t-md relative overflow-hidden" style={{ height: '100%', background: 'rgba(255,255,255,0.04)' }}>
                      <div className="absolute bottom-0 left-0 right-0 rounded-t-md transition-all duration-700"
                        style={{
                          height: `${prog > 0 ? h : 0}%`,
                          background: i % 3 === 0 ? 'linear-gradient(to top, #22c55e, #0ea5e9)' : i % 3 === 1 ? 'linear-gradient(to top, #0ea5e9, #8b5cf6)' : 'linear-gradient(to top, #22c55e, #10b981)',
                          opacity: 0.7,
                          transitionDelay: `${i * 35}ms`,
                        }} />
                    </div>
                    <span className="text-slate-700 text-[7px]">{['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'][i]}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Live feed */}
            <div className="w-72 shrink-0 border-l border-white/5 hidden md:flex flex-col">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-white text-xs font-semibold">Live Activity</span>
                <span className="ml-auto text-[9px] text-slate-500">{feedItems.length} events/min</span>
              </div>
              <div className="flex-1 overflow-hidden py-2">
                {feedItems.map((item, i) => {
                  const Icon = item.icon;
                  const isFocus = i === feed;
                  return (
                    <div key={i}
                      className="flex items-start gap-3 px-4 py-2.5 transition-all duration-500 border-b border-white/3 last:border-0"
                      style={{
                        background: isFocus ? `${item.color}07` : 'transparent',
                        opacity: isFocus ? 1 : 0.35,
                      }}>
                      <div className="h-7 w-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                        style={{ background: `${item.color}15` }}>
                        <Icon className="h-3.5 w-3.5" style={{ color: item.color }} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-white text-[10px] font-medium leading-snug">{item.msg}</p>
                        <p className="text-slate-600 text-[9px] mt-0.5">{item.sub}</p>
                      </div>
                      {isFocus && <div className="w-1.5 h-1.5 rounded-full mt-1 shrink-0 animate-pulse" style={{ background: item.color }} />}
                    </div>
                  );
                })}
              </div>
              {/* Bottom quick stats */}
              <div className="border-t border-white/5 p-3 grid grid-cols-2 gap-2">
                {[{ l: 'Pass Rate', v: '94%', c: '#22c55e' }, { l: 'Attendance', v: '91.2%', c: '#0ea5e9' }].map(s => (
                  <div key={s.l} className="rounded-lg p-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
                    <p className="text-slate-600 text-[8px]">{s.l}</p>
                    <p className="font-bold text-sm font-mono" style={{ color: s.c }}>{s.v}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Hero({ onGetStarted, onDemo }: HeroProps) {
  const [in_, setIn] = useState(false);
  useEffect(() => { setTimeout(() => setIn(true), 80); }, []);

  const anim = (delay = 0): React.CSSProperties => ({
    opacity: in_ ? 1 : 0,
    transform: in_ ? 'none' : 'translateY(20px)',
    transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms`,
  });

  return (
    <section className="relative pt-32 pb-0 overflow-hidden">
      {/* Background radial */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] pointer-events-none -z-0"
        style={{ background: 'radial-gradient(ellipse, rgba(34,197,94,0.07) 0%, rgba(14,165,233,0.04) 40%, transparent 70%)', filter: 'blur(40px)' }} />

      {/* Centered text block */}
      <div className="max-w-4xl mx-auto px-4 text-center relative z-10">
        {/* Badge */}
        <div style={anim(0)}>
          <span className="inline-flex items-center gap-2 badge badge-green mb-7">
            <Star className="h-3 w-3 fill-current" />
            Africa's #1 School Management Platform
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          </span>
        </div>

        {/* Headline */}
        <div style={anim(100)}>
          <h1 className="font-display font-black leading-[1.08] tracking-tight mb-6"
            style={{ fontSize: 'clamp(36px, 6vw, 80px)' }}>
            <span className="text-white block">The Complete</span>
            <span className="text-white block">School Platform for</span>
            <span className="block whitespace-nowrap" style={{ fontSize: 'clamp(28px, 5vw, 72px)', minHeight: '1.25em' }}>
              <TypewriterCycle />
            </span>
          </h1>
        </div>

        {/* Sub */}
        <div style={anim(200)}>
          <p className="text-slate-400 text-lg sm:text-xl leading-relaxed max-w-2xl mx-auto mb-10">
            Fees, CBT exams, attendance, report cards, payroll, and parent communication — all in one platform built for African schools.
          </p>
        </div>

        {/* CTAs */}
        <div style={anim(300)} className="flex flex-wrap gap-4 justify-center mb-12">
          <button onClick={onGetStarted} className="btn-primary text-base px-8 py-4">
            Get Started Free <ArrowRight className="h-4 w-4" />
          </button>
          <button onClick={onDemo} className="btn-ghost text-base px-8 py-4">
            <Play className="h-4 w-4" /> See Live Demo
          </button>
        </div>

        {/* Social proof */}
        <div style={anim(400)} className="flex flex-wrap items-center justify-center gap-6 mb-16">
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {['BG', 'AG', 'CO', 'EK', 'OS'].map((s, i) => (
                <div key={i} className="w-8 h-8 rounded-full border-2 border-[#030712] flex items-center justify-center text-[9px] font-bold text-white"
                  style={{ background: ['#22c55e', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ec4899'][i], zIndex: 5 - i }}>
                  {s}
                </div>
              ))}
            </div>
            <div className="text-left">
              <div className="flex items-center gap-0.5 mb-0.5">
                {[...Array(5)].map((_, i) => <Star key={i} className="h-3 w-3 fill-yellow-400 text-yellow-400" />)}
              </div>
              <p className="text-slate-500 text-xs">Trusted by 300+ Nigerian schools</p>
            </div>
          </div>
          <div className="w-px h-8 bg-white/8 hidden sm:block" />
          {[
            { v: 300, s: '+', l: 'Schools', c: '#22c55e' },
            { v: 95000, s: '+', l: 'Students', c: '#0ea5e9' },
            { v: 450, p: '₦', s: 'M+', l: 'Processed', c: '#8b5cf6' },
          ].map(stat => (
            <div key={stat.l} className="text-center">
              <p className="font-display font-black text-xl" style={{ color: stat.c }}>
                <AnimatedNum to={stat.v} prefix={stat.p} suffix={stat.s} />
              </p>
              <p className="text-slate-600 text-[10px]">{stat.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Full-width dashboard — no tilt, flows naturally */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 relative z-10"
        style={{ opacity: in_ ? 1 : 0, transform: in_ ? 'none' : 'translateY(40px)', transition: 'all 0.9s ease 0.4s' }}>

        {/* Floating stat chips above dashboard */}
        <div className="flex flex-wrap justify-between items-end mb-3 px-2 gap-3">
          {[
            { icon: DollarSign, label: '₦2.4M collected today', color: '#22c55e' },
            { icon: CheckCircle, label: '127 exams running now', color: '#0ea5e9' },
            { icon: Users, label: '94.2% attendance rate', color: '#8b5cf6' },
          ].map((chip, i) => {
            const Icon = chip.icon;
            return (
              <div key={i}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border animate-float"
                style={{
                  background: 'rgba(10,15,30,0.9)',
                  border: `1px solid ${chip.color}30`,
                  backdropFilter: 'blur(20px)',
                  animationDelay: `${i * 0.6}s`,
                  animationDuration: `${3.5 + i * 0.5}s`,
                }}>
                <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: chip.color }} />
                <span className="text-white text-xs font-semibold">{chip.label}</span>
                <div className="w-1.5 h-1.5 rounded-full animate-pulse shrink-0" style={{ background: chip.color }} />
              </div>
            );
          })}
        </div>

        <DashboardFrame />

        {/* Gradient fade at bottom of dashboard (disappears into next section) */}
        <div className="h-20 -mt-20 relative pointer-events-none"
          style={{ background: 'linear-gradient(to bottom, transparent, #030712)' }} />
      </div>
    </section>
  );
}
