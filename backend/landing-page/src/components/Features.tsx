import { useRef, useState, useEffect } from 'react';
import {
  BookOpen, DollarSign, Users, Fingerprint, FileText, MessageSquare,
  Brain, Briefcase, Monitor, ArrowRight, CheckCircle, TrendingUp, CreditCard, QrCode
} from 'lucide-react';

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

const FEATURES_GRID = [
  { icon: BookOpen, title: 'Hybrid CBT Engine', desc: 'Offline-first exam system. Students sit exams without internet. Auto-syncs when online.', color: '#0ea5e9', glow: 'rgba(14,165,233,0.2)' },
  { icon: DollarSign, title: 'Fee & Finance Ledger', desc: 'Complete bursary suite — collect fees, generate receipts, track balances, Paystack integration.', color: '#22c55e', glow: 'rgba(34,197,94,0.2)' },
  { icon: Users, title: 'Student Management', desc: 'Full student lifecycle from admission to graduation. Profiles, enrollments, transcripts.', color: '#8b5cf6', glow: 'rgba(139,92,246,0.2)' },
  { icon: Fingerprint, title: 'Biometric Attendance', desc: 'QR code + biometric scanning. Real-time dashboards. Parent SMS alerts.', color: '#f59e0b', glow: 'rgba(245,158,11,0.2)' },
  { icon: FileText, title: 'Auto Report Cards', desc: 'Generate professional report cards in seconds. Custom grading scales, remarks, PDFs.', color: '#ec4899', glow: 'rgba(236,72,153,0.2)' },
  { icon: MessageSquare, title: 'Parent Portal', desc: 'Parents track fees, results, attendance and communicate with teachers from mobile.', color: '#06b6d4', glow: 'rgba(6,182,212,0.2)' },
  { icon: Brain, title: 'AI Secretary', desc: 'AI-powered school assistant. Answers queries, schedules, generates documents automatically.', color: '#a855f7', glow: 'rgba(168,85,247,0.2)' },
  { icon: Briefcase, title: 'HR & Payroll', desc: 'Staff management, leave tracking, payroll computation, performance reviews.', color: '#14b8a6', glow: 'rgba(20,184,166,0.2)' },
  { icon: Monitor, title: 'Desktop CBT App', desc: 'Win7-compatible offline CBT app for schools with no internet infrastructure.', color: '#f97316', glow: 'rgba(249,115,22,0.2)' },
];

const SHOWCASE_SECTIONS = [
  {
    badge: 'Finance Module',
    badgeColor: '#22c55e',
    title: 'Collect fees, track every naira',
    desc: "Complete bursary management — generate invoices via SMS, collect payments through Paystack, issue receipts instantly, and track outstanding balances across every student.",
    points: ['Paystack + bank transfer integration', 'SMS invoice delivery', 'Automatic receipt generation', 'Outstanding balance alerts', 'Multi-term ledger history'],
    color: '#22c55e',
    preview: (
      <div className="rounded-2xl overflow-hidden border border-white/6" style={{ background: 'rgba(255,255,255,0.02)' }}>
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-white text-sm font-semibold">Fee Collection Dashboard</span>
          <span className="badge badge-green text-[9px]">Live</span>
        </div>
        <div className="p-4 space-y-3">
          {[
            { name: 'Adaugo Obi', amount: '₦75,000', status: 'Paid', color: '#22c55e' },
            { name: 'Emeka Nwachukwu', amount: '₦75,000', status: 'Partial', color: '#f59e0b' },
            { name: 'Halima Abdullahi', amount: '₦75,000', status: 'Pending', color: '#ef4444' },
            { name: 'Tunde Adeyemi', amount: '₦75,000', status: 'Paid', color: '#22c55e' },
          ].map((r, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-white/4 last:border-0">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
                  style={{ background: `${r.color}20`, color: r.color }}>{r.name[0]}</div>
                <div>
                  <p className="text-white text-xs font-medium">{r.name}</p>
                  <p className="text-slate-500 text-[10px]">Term 2 · SS3</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-white text-xs font-mono">{r.amount}</p>
                <span className="text-[9px] font-semibold" style={{ color: r.color }}>{r.status}</span>
              </div>
            </div>
          ))}
          <div className="grid grid-cols-3 gap-2 mt-2">
            {[
              { label: 'Collected', val: '₦6.2M', color: '#22c55e' },
              { label: 'Pending', val: '₦1.8M', color: '#f59e0b' },
              { label: 'Students', val: '842', color: '#0ea5e9' },
            ].map(s => (
              <div key={s.label} className="rounded-xl p-2.5 text-center" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <p className="font-bold font-mono text-sm" style={{ color: s.color }}>{s.val}</p>
                <p className="text-slate-600 text-[9px]">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
  {
    badge: 'CBT Module',
    badgeColor: '#0ea5e9',
    title: 'Run exams anywhere, online or offline',
    desc: "Our hybrid CBT engine lets students take exams without internet. Results auto-sync when connectivity is restored. Built for Nigerian school realities.",
    points: ['100% offline-capable exam engine', 'Auto-sync on reconnect', 'Anti-cheat & proctoring', 'Custom question banks', 'Instant result computation'],
    color: '#0ea5e9',
    preview: (
      <div className="rounded-2xl overflow-hidden border border-white/6" style={{ background: 'rgba(255,255,255,0.02)' }}>
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-white text-sm font-semibold">CBT — English SS3 (Term 2)</span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs" style={{ color: '#0ea5e9' }}>01:24:33</span>
            <span className="badge badge-blue text-[9px]">LIVE</span>
          </div>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-2 gap-3 mb-4">
            {[{ l: 'Active', v: '127', c: '#0ea5e9' }, { l: 'Submitted', v: '43', c: '#22c55e' }, { l: 'Avg Progress', v: '68%', c: '#8b5cf6' }, { l: 'Offline', v: '12', c: '#f59e0b' }].map(s => (
              <div key={s.l} className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <p className="text-slate-500 text-[9px]">{s.l}</p>
                <p className="font-bold text-lg font-mono" style={{ color: s.c }}>{s.v}</p>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <p className="text-slate-500 text-[9px] uppercase tracking-wider mb-2">Student Progress</p>
            {['Bello Fatima', 'Chidi Okonkwo', 'Ngozi Eze', 'Tunde A.'].map((name, i) => (
              <div key={name} className="flex items-center gap-3">
                <span className="text-slate-500 text-[9px] w-20 truncate">{name}</span>
                <div className="flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${[78, 95, 62, 88][i]}%`, background: 'linear-gradient(90deg, #22c55e, #0ea5e9)' }} />
                </div>
                <span className="text-[9px] font-mono w-8 text-right" style={{ color: '#0ea5e9' }}>{[78, 95, 62, 88][i]}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
  {
    badge: 'Attendance Module',
    badgeColor: '#8b5cf6',
    title: 'QR & biometric attendance in seconds',
    desc: "Students scan QR codes or touch fingerprint readers. Parents receive instant SMS when children arrive late or are absent. Real-time dashboard tracks every class.",
    points: ['QR code scanning', 'Fingerprint biometrics', 'Instant parent SMS alerts', 'Late arrival tracking', 'Monthly attendance analytics'],
    color: '#8b5cf6',
    preview: (
      <div className="rounded-2xl overflow-hidden border border-white/6" style={{ background: 'rgba(255,255,255,0.02)' }}>
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-white text-sm font-semibold">Attendance — JSS2A</span>
          <div className="flex items-center gap-1.5">
            <QrCode className="h-3.5 w-3.5 text-violet-400" />
            <span className="text-[9px] text-violet-400">Scanning</span>
          </div>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-4 gap-2 mb-4">
            {[{ l: 'Present', v: '38', c: '#22c55e' }, { l: 'Late', v: '3', c: '#f59e0b' }, { l: 'Absent', v: '4', c: '#ef4444' }, { l: 'Rate', v: '93%', c: '#8b5cf6' }].map(s => (
              <div key={s.l} className="rounded-xl p-2 text-center" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <p className="font-bold text-base font-mono" style={{ color: s.c }}>{s.v}</p>
                <p className="text-slate-600 text-[8px]">{s.l}</p>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {[
              { name: 'Adunola Okafor', time: '07:58 AM', status: 'Present', color: '#22c55e' },
              { name: 'Emeka Obi', time: '08:22 AM', status: 'Late', color: '#f59e0b' },
              { name: 'Fatima Bello', time: '07:55 AM', status: 'Present', color: '#22c55e' },
              { name: 'Gbenga Adeyemi', time: '--:--', status: 'Absent', color: '#ef4444' },
            ].map((r, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 border-b border-white/4 last:border-0">
                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: r.color }} />
                <span className="text-white text-[10px] flex-1">{r.name}</span>
                <span className="text-slate-500 text-[9px] font-mono">{r.time}</span>
                <span className="text-[9px] font-semibold" style={{ color: r.color }}>{r.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
];

function ShowcaseSection({ section, idx }: { section: typeof SHOWCASE_SECTIONS[0]; idx: number }) {
  const { ref, visible } = useVisible(0.15);
  const isEven = idx % 2 === 0;

  return (
    <div ref={ref} className={`grid lg:grid-cols-2 gap-12 items-center ${idx > 0 ? 'mt-24' : ''}`}>
      <div
        className={isEven ? 'order-1' : 'order-1 lg:order-2'}
        style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : `translateX(${isEven ? -30 : 30}px)`, transition: 'all 0.7s ease' }}
      >
        <span className="badge mb-4" style={{ color: section.badgeColor, background: `${section.badgeColor}12`, border: `1px solid ${section.badgeColor}30` }}>
          {section.badge}
        </span>
        <h3 className="font-display font-black text-3xl lg:text-4xl text-white mb-4 leading-tight">{section.title}</h3>
        <p className="text-slate-400 text-base leading-relaxed mb-6">{section.desc}</p>
        <ul className="space-y-2.5 mb-8">
          {section.points.map(p => (
            <li key={p} className="flex items-center gap-3 text-slate-300 text-sm">
              <CheckCircle className="h-4 w-4 shrink-0" style={{ color: section.color }} />
              {p}
            </li>
          ))}
        </ul>
        <button className="btn-ghost">
          Learn more <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      <div
        className={isEven ? 'order-2' : 'order-2 lg:order-1'}
        style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : `translateX(${isEven ? 30 : -30}px)`, transition: 'all 0.7s ease 0.15s' }}
      >
        {section.preview}
      </div>
    </div>
  );
}

function FeatureCard({ feature, index, visible }: { feature: typeof FEATURES_GRID[0]; index: number; visible: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const { icon: Icon, title, desc, color, glow } = feature;

  const handleMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${((e.clientX - rect.left) / rect.width) * 100}%`);
    el.style.setProperty('--my', `${((e.clientY - rect.top) / rect.height) * 100}%`);
  };

  return (
    <div ref={ref}
      className="group relative rounded-2xl p-6 border border-white/5 cursor-default overflow-hidden"
      style={{
        background: 'rgba(255,255,255,0.02)',
        opacity: visible ? 1 : 0,
        transform: visible ? 'none' : 'translateY(24px)',
        transition: `opacity 0.5s ease ${index * 60}ms, transform 0.5s ease ${index * 60}ms`,
      }}
      onMouseMove={handleMove}
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{ background: `radial-gradient(circle at var(--mx, 50%) var(--my, 50%), ${glow} 0%, transparent 60%)` }} />
      <div className="absolute inset-0 rounded-2xl border border-transparent group-hover:border-white/8 transition-all duration-300" />
      <div className="h-12 w-12 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300"
        style={{ background: `${color}14`, border: `1px solid ${color}25` }}>
        <Icon className="h-5 w-5" style={{ color }} />
      </div>
      <h3 className="text-white font-semibold text-base mb-2">{title}</h3>
      <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
      <div className="mt-4 flex items-center gap-1 text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity" style={{ color }}>
        Learn more <ArrowRight className="h-3 w-3" />
      </div>
    </div>
  );
}

export default function Features() {
  const gridRef = useRef<HTMLDivElement>(null);
  const [gridVisible, setGridVisible] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setGridVisible(true); }, { threshold: 0.05 });
    if (gridRef.current) obs.observe(gridRef.current);
    return () => obs.disconnect();
  }, []);

  return (
    <section id="features" className="py-28 px-4 relative">
      <div className="max-w-7xl mx-auto">
        {/* Showcase sections */}
        {SHOWCASE_SECTIONS.map((s, i) => <ShowcaseSection key={s.badge} section={s} idx={i} />)}

        {/* Section divider */}
        <div className="section-divider my-24" />

        {/* Feature grid */}
        <div ref={gridRef}>
          <div className="text-center mb-14"
            style={{ opacity: gridVisible ? 1 : 0, transform: gridVisible ? 'none' : 'translateY(24px)', transition: 'all 0.7s ease' }}>
            <span className="badge badge-blue mb-4">Full Platform</span>
            <h2 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
              Every tool your school needs{' '}
              <span className="gradient-text">in one place</span>
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">From a single dashboard, manage every dimension of your institution — academic, financial, and operational.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES_GRID.map((f, i) => <FeatureCard key={f.title} feature={f} index={i} visible={gridVisible} />)}
          </div>
        </div>
      </div>
    </section>
  );
}
