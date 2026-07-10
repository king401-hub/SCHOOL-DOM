import { useEffect, useRef, useState, useCallback } from 'react';
import { ArrowRight, Bell, Users, BookOpen, TrendingUp, CheckCircle, Zap, Shield } from 'lucide-react';

const WORDS = ['Admission to Graduation', 'Fees to Settlement', 'Attendance to Results', 'CBT to Certification'];

function TypewriterText() {
  const [wordIdx, setWordIdx] = useState(0);
  const [displayed, setDisplayed] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const target = WORDS[wordIdx];
    const delay = deleting ? 30 : 60;
    const timer = setTimeout(() => {
      if (!deleting) {
        if (displayed.length < target.length) {
          setDisplayed(target.slice(0, displayed.length + 1));
        } else {
          setTimeout(() => setDeleting(true), 1800);
        }
      } else {
        if (displayed.length > 0) {
          setDisplayed(displayed.slice(0, -1));
        } else {
          setDeleting(false);
          setWordIdx(i => (i + 1) % WORDS.length);
        }
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [displayed, deleting, wordIdx]);

  return (
    <span
      className="block"
      style={{ background: 'linear-gradient(90deg, #0ea5e9, #10b981, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}
    >
      {displayed}<span className="animate-pulse">|</span>
    </span>
  );
}

function Tilt3DCard({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const handleMove = useCallback((e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    const rotX = (y - 0.5) * -20;
    const rotY = (x - 0.5) * 20;
    el.style.transform = `perspective(1000px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale(1.02)`;
  }, []);
  const handleLeave = () => {
    if (ref.current) ref.current.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)';
  };
  return (
    <div
      ref={ref}
      className={className}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      style={{ transition: 'transform 0.1s ease-out', transformStyle: 'preserve-3d' }}
    >
      {children}
    </div>
  );
}

function FloatingNotification({ icon: Icon, text, sub, color, delay }: { icon: any; text: string; sub: string; color: string; delay: string }) {
  return (
    <div
      className="absolute flex items-center gap-3 px-4 py-3 rounded-2xl border border-white/10 backdrop-blur-xl shadow-2xl"
      style={{
        background: 'rgba(2,8,23,0.8)',
        animation: `float 4s ease-in-out infinite`,
        animationDelay: delay,
      }}
    >
      <div className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: color }}>
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div>
        <p className="text-white text-xs font-semibold">{text}</p>
        <p className="text-slate-400 text-[10px]">{sub}</p>
      </div>
    </div>
  );
}

function DashboardMockup() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(i => (i + 1) % 100), 80);
    return () => clearInterval(t);
  }, []);

  const bars = [65, 80, 45, 90, 72, 88, 60, 95, 70, 85, 78, 92];
  const animated = bars.map((b, i) => Math.min(b, (tick / 100) * b * 1.2 + (i * 5)));

  return (
    <div
      className="w-full h-full rounded-2xl overflow-hidden border border-white/10"
      style={{ background: 'rgba(2,8,23,0.9)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
        <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
        <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
        <span className="text-slate-500 text-xs ml-2">Schooldom Dashboard</span>
      </div>

      <div className="p-4 grid grid-cols-2 gap-3">
        {[
          { label: 'Students', val: '1,284', color: '#0ea5e9', icon: Users },
          { label: 'Fee Rate', val: '₦2.4M', color: '#10b981', icon: TrendingUp },
          { label: 'Active CBT', val: '14', color: '#8b5cf6', icon: BookOpen },
          { label: 'Attendance', val: '94%', color: '#f59e0b', icon: CheckCircle },
        ].map(({ label, val, color, icon: Icon }) => (
          <div key={label} className="rounded-xl p-3 border border-white/5" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-slate-500 text-[10px]">{label}</span>
              <Icon className="h-3 w-3" style={{ color }} />
            </div>
            <p className="text-white text-sm font-bold">{val}</p>
          </div>
        ))}
      </div>

      <div className="px-4 pb-2">
        <p className="text-slate-500 text-[10px] mb-2">Exam Performance</p>
        <div className="flex items-end gap-1 h-16">
          {animated.map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-sm transition-all duration-75"
              style={{
                height: `${Math.max(4, h)}%`,
                background: `linear-gradient(to top, #0ea5e9, #6366f1)`,
                opacity: 0.7 + (i % 3) * 0.1,
              }}
            />
          ))}
        </div>
      </div>

      <div className="px-4 pb-4 mt-1 space-y-1.5">
        {['Adeola O. - Payment confirmed ✓', 'Exam: JSS2 Maths started →', 'Report card generated ✓'].map((line, i) => (
          <div
            key={i}
            className="flex items-center gap-2 text-[10px] text-slate-500 opacity-0"
            style={{ animation: `fadeInUp 0.5s ease forwards`, animationDelay: `${0.5 + i * 0.3}s` }}
          >
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

interface HeroProps {
  onGetStarted: () => void;
  onSignIn: () => void;
  onDemo: () => void;
}

export default function Hero({ onGetStarted, onSignIn, onDemo }: HeroProps) {
  const [count1, setCount1] = useState(0);
  const [count2, setCount2] = useState(0);
  const [count3, setCount3] = useState(0);

  useEffect(() => {
    const animate = (setter: (v: number) => void, target: number, duration: number) => {
      const start = Date.now();
      const tick = () => {
        const elapsed = Date.now() - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        setter(Math.floor(eased * target));
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    const t = setTimeout(() => {
      animate(setCount1, 250, 2000);
      animate(setCount2, 85000, 2500);
      animate(setCount3, 450, 2000);
    }, 400);
    return () => clearTimeout(t);
  }, []);

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center pt-28 pb-20 px-4 overflow-hidden">
      <div
        className="absolute inset-0 -z-10"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(14,165,233,0.15) 0%, transparent 60%)',
        }}
      />
      <div
        className="absolute inset-0 -z-10 opacity-20"
        style={{
          backgroundImage: `linear-gradient(rgba(14,165,233,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(14,165,233,0.3) 1px, transparent 1px)`,
          backgroundSize: '80px 80px',
          maskImage: 'radial-gradient(ellipse 80% 80% at 50% 0%, black 40%, transparent 100%)',
        }}
      />

      <div
        className="inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-full border border-cyan-500/30 text-cyan-400 mb-8"
        style={{
          background: 'rgba(14,165,233,0.08)',
          animation: 'fadeInUp 0.6s ease forwards',
        }}
      >
        <Zap className="h-3 w-3 fill-cyan-400" />
        Enterprise Resource Platform & Complete School Manager
        <Shield className="h-3 w-3" />
      </div>

      <div
        className="text-center max-w-5xl mx-auto"
        style={{ animation: 'fadeInUp 0.6s ease 0.1s forwards', opacity: 0 }}
      >
        <h1 className="font-bold text-4xl sm:text-5xl lg:text-7xl text-white leading-tight mb-4">
          Digitize Your School
          <br />
          Operations
          <br />
          from&nbsp;
        </h1>
        <h1 className="font-bold text-4xl sm:text-5xl lg:text-7xl leading-tight mb-8 min-h-[1.2em]">
          <TypewriterText />
        </h1>
        <p
          className="text-slate-400 text-base sm:text-lg max-w-2xl mx-auto mb-10 leading-relaxed"
          style={{ animation: 'fadeInUp 0.6s ease 0.3s forwards', opacity: 0 }}
        >
          Schooldom Academy is the unified school manager built to run and scale African schools — hybrid offline/online CBT, automated report cards, biometric attendance, parent fee gateways, and much more.
        </p>

        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
          style={{ animation: 'fadeInUp 0.6s ease 0.4s forwards', opacity: 0 }}
        >
          <button
            onClick={onGetStarted}
            className="group relative inline-flex items-center gap-2 px-8 py-4 rounded-2xl text-white font-bold text-base overflow-hidden cursor-pointer"
            style={{ background: 'linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%)' }}
          >
            <span className="relative z-10 flex items-center gap-2">
              Onboard Your School
              <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </span>
            <div className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-600 skew-x-12" />
          </button>

          <button
            onClick={onSignIn}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-2xl text-white font-bold text-base border border-white/10 hover:border-white/20 hover:bg-white/5 transition-all cursor-pointer"
          >
            Sign In
          </button>

          <button
            onClick={onDemo}
            className="inline-flex items-center gap-2 px-6 py-4 rounded-2xl text-slate-300 font-medium text-sm hover:text-white transition-colors cursor-pointer"
          >
            Explore Demo ↓
          </button>
        </div>

        <div
          className="flex flex-wrap items-center justify-center gap-8 sm:gap-12 mb-20 text-center"
          style={{ animation: 'fadeInUp 0.6s ease 0.5s forwards', opacity: 0 }}
        >
          <div>
            <p className="text-3xl font-bold text-white">{count1}+</p>
            <p className="text-slate-500 text-xs mt-1">Schools Onboarded</p>
          </div>
          <div className="hidden sm:block w-px h-8 bg-white/10" />
          <div>
            <p className="text-3xl font-bold text-white">{count2.toLocaleString()}+</p>
            <p className="text-slate-500 text-xs mt-1">Students Managed</p>
          </div>
          <div className="hidden sm:block w-px h-8 bg-white/10" />
          <div>
            <p className="text-3xl font-bold text-white">₦{count3}M+</p>
            <p className="text-slate-500 text-xs mt-1">Fees Processed</p>
          </div>
        </div>
      </div>

      <div
        className="relative w-full max-w-4xl mx-auto"
        style={{ animation: 'fadeInUp 0.8s ease 0.6s forwards', opacity: 0 }}
      >
        <Tilt3DCard className="relative w-full aspect-[16/9] max-h-[480px] rounded-2xl shadow-2xl shadow-cyan-500/10">
          <div
            className="absolute inset-0 rounded-2xl"
            style={{ background: 'linear-gradient(135deg, rgba(14,165,233,0.3), rgba(99,102,241,0.3), rgba(16,185,129,0.3))', padding: '1px' }}
          >
            <div className="w-full h-full rounded-2xl overflow-hidden" style={{ background: '#020817' }}>
              <DashboardMockup />
            </div>
          </div>

          <FloatingNotification
            icon={Bell}
            text="Fee Payment Received"
            sub="₦45,000 — Adeola Okafor"
            color="linear-gradient(135deg, #10b981, #0ea5e9)"
            delay="0s"
          />
          <div className="absolute -top-4 -left-4">
            <FloatingNotification
              icon={CheckCircle}
              text="Exam Published"
              sub="JSS2 Mathematics"
              color="linear-gradient(135deg, #8b5cf6, #ec4899)"
              delay="1.5s"
            />
          </div>
          <div className="absolute -bottom-4 right-8">
            <FloatingNotification
              icon={TrendingUp}
              text="Report Cards Ready"
              sub="Term 2 — 1,284 students"
              color="linear-gradient(135deg, #f59e0b, #ef4444)"
              delay="3s"
            />
          </div>
        </Tilt3DCard>

        <div
          className="absolute -inset-20 -z-10 rounded-full opacity-30"
          style={{ background: 'radial-gradient(circle, rgba(14,165,233,0.3) 0%, transparent 70%)', filter: 'blur(40px)' }}
        />
      </div>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-12px); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </section>
  );
}
