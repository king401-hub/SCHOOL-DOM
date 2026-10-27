import { useState, useEffect, useRef, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, useMotionValue, useSpring, useReducedMotion } from 'motion/react';
import { ArrowRight, Play, TrendingUp, Users, DollarSign, BookOpen, CheckCircle, Bell, Star, BarChart3 } from 'lucide-react';
import { EASE } from '../lib/reveal';
import HeroScene from './HeroScene';

/** Masked word-by-word slide-up reveal for kinetic headline entrances. */
function SplitWords({ text, startDelay = 0, stagger = 0.045 }: { text: string; startDelay?: number; stagger?: number }) {
  const reduced = useReducedMotion();
  const words = text.split(' ');
  if (reduced) return <>{text}</>;
  return (
    <>
      {words.map((w, i) => (
        <span key={i} style={{ display: 'inline-block', overflow: 'hidden', verticalAlign: 'top', paddingBottom: '0.08em' }}>
          <motion.span
            style={{ display: 'inline-block' }}
            initial={{ y: '115%' }}
            animate={{ y: 0 }}
            transition={{ duration: 0.85, ease: EASE, delay: startDelay + i * stagger }}
          >
            {w}{i < words.length - 1 ? ' ' : ''}
          </motion.span>
        </span>
      ))}
    </>
  );
}

/** Translates an element a fraction of the way toward the cursor on hover, spring-back on leave. */
function useMagnetic<T extends HTMLElement>(strength = 0.3) {
  const reduced = useReducedMotion();
  const ref = useRef<T>(null);
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const x = useSpring(mx, { stiffness: 150, damping: 14, mass: 0.2 });
  const y = useSpring(my, { stiffness: 150, damping: 14, mass: 0.2 });
  const onMouseMove = (e: MouseEvent) => {
    if (reduced) return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    mx.set((e.clientX - r.left - r.width / 2) * strength);
    my.set((e.clientY - r.top - r.height / 2) * strength);
  };
  const onMouseLeave = () => { mx.set(0); my.set(0); };
  return { ref, style: { x, y }, onMouseMove, onMouseLeave };
}

/** Paper-grain texture: a faint fractal-noise overlay reinforcing the light paper surface. */
function GrainOverlay() {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none select-none" style={{ opacity: 0.035, mixBlendMode: 'multiply' }} aria-hidden="true">
      <filter id="heroGrain">
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
        <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.9 0" />
      </filter>
      <rect width="100%" height="100%" filter="url(#heroGrain)" />
    </svg>
  );
}

interface HeroProps {
  onSignIn: () => void;
  onDemo: () => void;
}

function TypewriterCycle() {
  const { t } = useTranslation();
  const phrases = t('hero.phrases', { returnObjects: true }) as string[];
  const [idx, setIdx] = useState(0);
  const [chars, setChars] = useState(0);
  const [deleting, setDeleting] = useState(false);
  // Language can change mid-cycle (new phrase list, different lengths) -
  // clamp back into range rather than reading past the end of a shorter list.
  useEffect(() => {
    if (idx >= phrases.length) { setIdx(0); setChars(0); setDeleting(false); }
  }, [phrases, idx]);
  useEffect(() => {
    const phrase = phrases[idx] || '';
    const delay = deleting ? 35 : chars < phrase.length ? 75 : 1600;
    const t = setTimeout(() => {
      if (!deleting && chars < phrase.length) setChars(c => c + 1);
      else if (!deleting && chars === phrase.length) setDeleting(true);
      else if (deleting && chars > 0) setChars(c => c - 1);
      else { setDeleting(false); setIdx(i => (i + 1) % phrases.length); }
    }, delay);
    return () => clearTimeout(t);
  }, [idx, chars, deleting, phrases]);
  return (
    <span className="gradient-text font-display">
      {(phrases[idx] || '').slice(0, chars)}<span className="opacity-50">|</span>
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
    { icon: DollarSign, msg: '₦42,000 payment received', sub: 'Bello Fatima' },
    { icon: CheckCircle, msg: 'CBT exam submitted: Chemistry SS3', sub: 'Chidi Okonkwo' },
    { icon: Users, msg: 'New student enrolled: JSS1', sub: 'Amina Yusuf' },
    { icon: Bell, msg: 'Attendance alert sent to parent', sub: 'Ngozi Eze — JSS2A' },
    { icon: BookOpen, msg: 'Report card generated: SS3A', sub: 'Tunde Adeyemi' },
  ];
  useEffect(() => {
    const t = setInterval(() => setProg(p => (p >= 100 ? 0 : p + 2)), 60);
    const f = setInterval(() => setFeed(i => (i + 1) % feedItems.length), 2200);
    return () => { clearInterval(t); clearInterval(f); };
  }, []);

  return (
    <div
      className="w-full rounded-2xl overflow-hidden border border-white/10 keep-dark"
      style={{ background: 'rgba(14,12,10,0.98)', boxShadow: '0 50px 100px rgba(20,19,16,0.18)' }}
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
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)', maxWidth: 360 }}>
          <div className="w-2.5 h-2.5 rounded-full border border-white/20 shrink-0" />
          <span className="text-slate-500 text-xs font-mono">schooldom.app/dashboard</span>
        </div>
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-[10px] text-slate-500">Live</span>
          <div className="w-7 h-7 rounded-full ml-2 flex items-center justify-center text-xs font-bold"
            style={{ background: '#14532d', color: '#f5f4f1' }}>A</div>
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
                background: i === 0 ? 'rgba(20,83,45,0.18)' : 'transparent',
                border: i === 0 ? '1px solid rgba(20,83,45,0.35)' : '1px solid transparent',
              }}>
              <Icon className="h-4 w-4" style={{ color: i === 0 ? '#4ade80' : '#4a453d' }} />
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
              { label: 'Students', val: '1,842', delta: '+24 this week', cls: '' },
              { label: 'Fees Collected', val: '₦2.4M', delta: '+18% this term', cls: '' },
              { label: 'Avg Score', val: '78.4%', delta: '+5.2pts', cls: 'hidden md:flex' },
              { label: 'Exams Active', val: '127', delta: 'Right now', cls: 'hidden lg:flex' },
            ].map(s => (
              <div key={s.label} className={`flex items-center gap-3 px-4 py-2 rounded-xl shrink-0 ${s.cls}`}
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div>
                  <p className="text-slate-500 text-[9px] uppercase tracking-wider">{s.label}</p>
                  <p className="text-white font-bold text-sm font-mono">{s.val}</p>
                </div>
                <p className="text-[9px] hidden sm:block text-emerald-400">{s.delta}</p>
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
                  style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80', border: '1px solid rgba(74,222,128,0.25)' }}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#4ade80' }} />LIVE
                </div>
              </div>
              <div className="flex-1 flex items-end gap-1.5">
                {bars.map((h, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full rounded-t-md relative overflow-hidden" style={{ height: '100%', background: 'rgba(255,255,255,0.04)' }}>
                      <div className="absolute bottom-0 left-0 right-0 rounded-t-md transition-all duration-700"
                        style={{
                          height: `${prog > 0 ? h : 0}%`,
                          background: 'linear-gradient(to top, #14532d, #4ade80)',
                          opacity: 0.85,
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
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
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
                        background: isFocus ? 'rgba(74,222,128,0.06)' : 'transparent',
                        opacity: isFocus ? 1 : 0.35,
                      }}>
                      <div className="h-7 w-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                        style={{ background: 'rgba(74,222,128,0.12)' }}>
                        <Icon className="h-3.5 w-3.5" style={{ color: '#4ade80' }} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-white text-[10px] font-medium leading-snug">{item.msg}</p>
                        <p className="text-slate-600 text-[9px] mt-0.5">{item.sub}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
              {/* Bottom quick stats */}
              <div className="border-t border-white/5 p-3 grid grid-cols-2 gap-2">
                {[{ l: 'Pass Rate', v: '94%' }, { l: 'Attendance', v: '91.2%' }].map(s => (
                  <div key={s.l} className="rounded-lg p-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
                    <p className="text-slate-600 text-[8px]">{s.l}</p>
                    <p className="font-bold text-sm font-mono" style={{ color: '#4ade80' }}>{s.v}</p>
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

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE } },
};

export default function Hero({ onDemo }: HeroProps) {
  const { t } = useTranslation();
  const reduced = useReducedMotion();
  const ctaPrimary = useMagnetic<HTMLAnchorElement>(0.3);
  const ctaSecondary = useMagnetic<HTMLButtonElement>(0.3);

  const line1 = t('hero.titleLine1');
  const line1Words = reduced ? 0 : line1.split(' ').length;
  const line2Delay = 0.15 + line1Words * 0.045 + 0.08;

  return (
    <section className="relative pt-32 pb-0 overflow-hidden">
      <GrainOverlay />
      {/* Single, calm background wash - no particles, no aurora */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] pointer-events-none -z-0"
        style={{ background: 'radial-gradient(ellipse, rgba(20,83,45,0.07) 0%, transparent 65%)', filter: 'blur(50px)' }} />

      {/* Adaptive-quality 3D hero accent - a small corner object, not a full-bleed
          background: fixed box anchored to the top-right of the hero's text area
          (not the whole, much taller, section) so it reads as a floating accent
          instead of a dark wall sitting over the headline/CTAs. Desktop/laptop
          only; text sits above it (z-10). */}
      <div className="absolute hidden md:block pointer-events-none"
        style={{ top: '-30px', right: '-40px', width: 'min(46vw, 620px)', height: 'min(46vw, 620px)', zIndex: 1 }}>
        <HeroScene />
      </div>

      {/* Centered text block */}
      <motion.div
        className="max-w-4xl mx-auto px-4 text-center relative z-10"
        initial={reduced ? false : 'hidden'}
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.1 } } }}
      >
        {/* Badge */}
        <motion.div variants={fadeUp}>
          <span className="inline-flex items-center gap-2 badge mb-7">
            <Star className="h-3 w-3 fill-current" />
            {t('hero.badge')}
          </span>
        </motion.div>

        {/* Headline */}
        <motion.div variants={fadeUp}>
          <h1 className="font-display font-bold leading-[1.04] tracking-tight mb-6"
            style={{ fontSize: 'clamp(32px, 6.4vw, 80px)' }}>
            <span className="text-[#141310] block"><SplitWords text={line1} startDelay={0.15} /></span>
            <span className="text-[#141310] block"><SplitWords text={t('hero.titleLine2')} startDelay={line2Delay} /></span>
            <span className="block whitespace-nowrap" style={{ fontSize: 'clamp(23px, 5.3vw, 71px)', minHeight: '1.25em' }}>
              <TypewriterCycle />
            </span>
          </h1>
        </motion.div>

        {/* Sub */}
        <motion.div variants={fadeUp}>
          <p className="text-[#5b5750] text-lg sm:text-xl leading-relaxed max-w-2xl mx-auto mb-10">
            {t('hero.subtitle')}
          </p>
        </motion.div>

        {/* CTAs */}
        <motion.div variants={fadeUp} className="flex flex-wrap gap-4 justify-center mb-12">
          <motion.a
            ref={ctaPrimary.ref}
            href="/#/signup"
            className="btn-primary text-base px-8 py-4"
            style={ctaPrimary.style}
            onMouseMove={ctaPrimary.onMouseMove}
            onMouseLeave={ctaPrimary.onMouseLeave}
            whileTap={{ scale: 0.96 }}
          >
            {t('hero.ctaPrimary')} <ArrowRight className="h-4 w-4" />
          </motion.a>
          <motion.button
            ref={ctaSecondary.ref}
            onClick={onDemo}
            className="btn-ghost text-base px-8 py-4"
            style={ctaSecondary.style}
            onMouseMove={ctaSecondary.onMouseMove}
            onMouseLeave={ctaSecondary.onMouseLeave}
            whileTap={{ scale: 0.96 }}
          >
            <Play className="h-4 w-4" /> {t('hero.ctaSecondary')}
          </motion.button>
        </motion.div>

        {/* Social proof */}
        <motion.div variants={fadeUp} className="flex flex-wrap items-center justify-center gap-6 mb-16">
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {['BG', 'AG', 'CO', 'EK', 'OS'].map((s, i) => (
                <div key={i} className="w-8 h-8 rounded-full border-2 border-[#f5f4f1] flex items-center justify-center text-[9px] font-bold"
                  style={{ background: ['#14532d', '#1d6b3c', '#2f7d4f', '#4a8f62', '#6ba47d'][i], color: '#f5f4f1', zIndex: 5 - i }}>
                  {s}
                </div>
              ))}
            </div>
            <div className="text-left">
              <div className="flex items-center gap-0.5 mb-0.5">
                {[...Array(5)].map((_, i) => <Star key={i} className="h-3 w-3 fill-[#14532d] text-[#14532d]" />)}
              </div>
              <p className="text-[#5b5750] text-xs">{t('hero.trustedBy')}</p>
            </div>
          </div>
          <div className="w-px h-8 bg-black/10 hidden sm:block" />
          {[
            { v: 300, s: '+', l: t('hero.statSchools') },
            { v: 95000, s: '+', l: t('hero.statStudents') },
            { v: 450, p: '₦', s: 'M+', l: t('hero.statProcessed') },
          ].map(stat => (
            <div key={stat.l} className="text-center">
              <p className="font-display font-semibold text-xl" style={{ color: '#14532d' }}>
                <AnimatedNum to={stat.v} prefix={stat.p} suffix={stat.s} />
              </p>
              <p className="text-[#8a8378] text-[10px]">{stat.l}</p>
            </div>
          ))}
        </motion.div>
      </motion.div>

      {/* Full-width dashboard — no tilt, flows naturally */}
      <motion.div
        className="max-w-6xl mx-auto px-4 sm:px-6 relative z-10"
        initial={reduced ? false : { opacity: 0, y: 32 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.9, ease: EASE, delay: 0.4 }}
      >

        {/* Calm stat row above dashboard (static - no floating/bouncing) */}
        <div className="flex flex-wrap justify-center items-center gap-3 mb-4">
          {[
            { icon: DollarSign, label: t('hero.chipCollected') },
            { icon: CheckCircle, label: t('hero.chipExams') },
            { icon: Users, label: t('hero.chipAttendance') },
          ].map((chip, i) => {
            const Icon = chip.icon;
            return (
              <div key={i} className="inline-flex items-center gap-2 px-4 py-2 rounded-full sd-panel">
                <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: '#14532d' }} />
                <span className="text-[#141310] text-xs font-medium">{chip.label}</span>
              </div>
            );
          })}
        </div>

        <DashboardFrame />

        {/* Gradient fade at bottom of dashboard (disappears into next section) */}
        <div className="h-20 -mt-20 relative pointer-events-none hero-fade" />
      </motion.div>
    </section>
  );
}
