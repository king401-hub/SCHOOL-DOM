import { useRef, useState, useEffect } from 'react';
import { BookOpen, DollarSign, Users, Fingerprint, FileText, MessageSquare, Brain, Briefcase, Monitor, ArrowRight } from 'lucide-react';

const FEATURES = [
  { icon: BookOpen, title: 'Hybrid CBT Engine', desc: 'Offline-first exam system. Students sit exams without internet. Auto-syncs when online.', color: '#0ea5e9', glow: 'rgba(14,165,233,0.3)' },
  { icon: DollarSign, title: 'Fee & Finance Ledger', desc: 'Complete bursary suite — collect fees, generate receipts, track outstanding balances, Paystack integration.', color: '#10b981', glow: 'rgba(16,185,129,0.3)' },
  { icon: Users, title: 'Student Management', desc: 'Full student lifecycle from admission to graduation. Profiles, enrollments, transcripts.', color: '#8b5cf6', glow: 'rgba(139,92,246,0.3)' },
  { icon: Fingerprint, title: 'Biometric Attendance', desc: 'QR code + biometric scanning. Real-time attendance dashboards. Parent SMS alerts.', color: '#f59e0b', glow: 'rgba(245,158,11,0.3)' },
  { icon: FileText, title: 'Auto Report Cards', desc: 'Generate professional report cards in seconds. Custom grading scales, remarks, PDFs.', color: '#ec4899', glow: 'rgba(236,72,153,0.3)' },
  { icon: MessageSquare, title: 'Parent Portal', desc: 'Parents track fees, results, attendance and communicate with teachers from mobile.', color: '#06b6d4', glow: 'rgba(6,182,212,0.3)' },
  { icon: Brain, title: 'AI Secretary', desc: 'AI-powered school assistant. Answers queries, schedules, generates documents automatically.', color: '#a855f7', glow: 'rgba(168,85,247,0.3)' },
  { icon: Briefcase, title: 'HR & Payroll', desc: 'Staff management, leave tracking, payroll computation, performance reviews.', color: '#14b8a6', glow: 'rgba(20,184,166,0.3)' },
  { icon: Monitor, title: 'Desktop CBT App', desc: 'Win7-compatible offline CBT app for schools with no internet infrastructure.', color: '#f97316', glow: 'rgba(249,115,22,0.3)' },
];

function FeatureCard({ feature, index, visible }: { feature: typeof FEATURES[0]; index: number; visible: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const { icon: Icon, title, desc, color, glow } = feature;

  const handleMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    el.style.setProperty('--mx', `${x}%`);
    el.style.setProperty('--my', `${y}%`);
  };

  return (
    <div
      ref={ref}
      className="group relative rounded-2xl p-6 border border-white/5 cursor-default overflow-hidden hover:border-white/10 hover:-translate-y-1"
      style={{
        background: 'rgba(255,255,255,0.02)',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(30px)',
        transition: `opacity 0.5s ease ${index * 60}ms, transform 0.5s ease ${index * 60}ms, border-color 0.3s, translate 0.3s`,
      }}
      onMouseMove={handleMove}
    >
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background: `radial-gradient(circle at var(--mx, 50%) var(--my, 50%), ${glow} 0%, transparent 60%)`,
        }}
      />

      <div
        className="h-12 w-12 rounded-xl flex items-center justify-center mb-4 shrink-0 group-hover:scale-110 transition-transform duration-300"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}
      >
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
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { threshold: 0.1 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  return (
    <section id="features" className="py-28 px-4 relative" ref={ref}>
      <div className="max-w-7xl mx-auto">
        <div
          className="text-center mb-16 transition-all duration-700"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(30px)' }}
        >
          <span
            className="text-xs font-bold uppercase tracking-widest px-4 py-1.5 rounded-full border mb-4 inline-block"
            style={{ color: '#0ea5e9', background: 'rgba(14,165,233,0.08)', borderColor: 'rgba(14,165,233,0.2)' }}
          >
            Enterprise Features
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-4">
            Everything your school needs
            <br />
            <span style={{ background: 'linear-gradient(90deg, #0ea5e9, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              in one platform
            </span>
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            From a single dashboard, manage every dimension of your school — academic, financial, operational.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => <FeatureCard key={f.title} feature={f} index={i} visible={visible} />)}
        </div>
      </div>
    </section>
  );
}
