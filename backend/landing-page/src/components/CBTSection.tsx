import { useRef, useState, useEffect } from 'react';
import { Monitor, Wifi, WifiOff, Shield, Zap, CheckCircle, Download, ArrowRight } from 'lucide-react';

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

function CBTAppMockup() {
  const [question, setQuestion] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [timeLeft, setTimeLeft] = useState(5400);

  const questions = [
    { text: 'What is the chemical formula for water?', options: ['H₂O', 'CO₂', 'O₂', 'H₂SO₄'], correct: 0 },
    { text: 'Who wrote "Things Fall Apart"?', options: ['Wole Soyinka', 'Chinua Achebe', 'Ben Okri', 'Chimamanda Adichie'], correct: 1 },
    { text: 'What is the capital of Nigeria?', options: ['Lagos', 'Kano', 'Abuja', 'Port Harcourt'], correct: 2 },
  ];

  useEffect(() => {
    const t = setInterval(() => setTimeLeft(s => s > 0 ? s - 1 : 0), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => { setSelected(null); setQuestion(q => (q + 1) % questions.length); }, 3500);
    return () => clearTimeout(t);
  }, [question]);

  const fmt = (s: number) => `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  const q = questions[question];

  return (
    <div className="rounded-2xl overflow-hidden border border-white/8 shadow-2xl"
      style={{ background: 'rgba(10,15,30,0.95)', boxShadow: '0 30px 60px rgba(0,0,0,0.5), 0 0 40px rgba(14,165,233,0.08)' }}>
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5" style={{ background: 'rgba(14,165,233,0.05)' }}>
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500/70" />
          <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
          <div className="w-3 h-3 rounded-full bg-green-500/70" />
        </div>
        <span className="text-slate-400 text-xs mx-auto">Schooldom Desktop CBT — Chemistry SS3</span>
        <div className="flex items-center gap-1.5">
          <WifiOff className="h-3 w-3 text-orange-400" />
          <span className="text-orange-400 text-[9px]">Offline Mode</span>
        </div>
      </div>

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-slate-500 text-[10px] uppercase tracking-wider">Question {question + 1} of 40</p>
            <div className="flex gap-0.5 mt-1.5">
              {[...Array(20)].map((_, i) => (
                <div key={i} className="h-1.5 flex-1 rounded-full transition-all"
                  style={{ background: i < question ? '#22c55e' : i === question ? '#0ea5e9' : 'rgba(255,255,255,0.06)' }} />
              ))}
            </div>
          </div>
          <div className="text-right">
            <p className="font-mono font-bold text-lg" style={{ color: timeLeft < 600 ? '#ef4444' : '#0ea5e9' }}>{fmt(timeLeft)}</p>
            <p className="text-slate-600 text-[9px]">remaining</p>
          </div>
        </div>

        {/* Question */}
        <div className="rounded-xl p-4 mb-4" style={{ background: 'rgba(14,165,233,0.05)', border: '1px solid rgba(14,165,233,0.15)' }}>
          <p className="text-white text-sm font-medium leading-relaxed">{q.text}</p>
        </div>

        {/* Options */}
        <div className="grid grid-cols-2 gap-2">
          {q.options.map((opt, i) => {
            const isSelected = selected === i;
            const isCorrect = selected !== null && i === q.correct;
            return (
              <button
                key={i}
                onClick={() => setSelected(i)}
                className="rounded-xl p-3 text-left text-sm font-medium transition-all cursor-pointer"
                style={{
                  background: isCorrect ? 'rgba(34,197,94,0.15)' : isSelected ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${isCorrect ? 'rgba(34,197,94,0.5)' : isSelected ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.06)'}`,
                  color: isCorrect ? '#22c55e' : isSelected ? '#ef4444' : '#94a3b8',
                }}
              >
                <span className="text-[10px] opacity-60 mr-1">{String.fromCharCode(65 + i)}.</span> {opt}
              </button>
            );
          })}
        </div>

        {/* Status bar */}
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 text-[9px]" style={{ color: '#22c55e' }}>
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" /> Auto-save on
            </span>
            <span className="flex items-center gap-1 text-[9px] text-orange-400">
              <WifiOff className="h-2.5 w-2.5" /> Offline — syncs on reconnect
            </span>
          </div>
          <span className="text-slate-600 text-[9px] font-mono">SD-CBT v4.2.1</span>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  { icon: WifiOff, title: 'Fully Offline', desc: 'Exams run completely without internet. Zero dependency on connectivity.', color: '#f97316' },
  { icon: Shield, title: 'Anti-Cheat Built In', desc: 'Tab lock, copy-paste disable, and session monitoring baked in.', color: '#8b5cf6' },
  { icon: Zap, title: 'Instant Sync', desc: 'Auto-uploads results and logs the moment internet is restored.', color: '#0ea5e9' },
  { icon: Monitor, title: 'Windows 7+', desc: 'Compatible from Windows 7 to Windows 11. No upgrade required.', color: '#22c55e' },
  { icon: CheckCircle, title: 'Auto Marking', desc: 'Objective and theory sections graded instantly after submission.', color: '#10b981' },
  { icon: Download, title: 'Easy Deploy', desc: 'One-click school setup. Download, install, configure — done.', color: '#ec4899' },
];

export default function CBTSection() {
  const { ref, visible } = useVisible(0.1);

  return (
    <section id="cbt" ref={ref} className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 80% 50%, rgba(14,165,233,0.05) 0%, transparent 60%)' }} />

      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-14 items-center">
          {/* Left */}
          <div style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateX(-30px)', transition: 'all 0.7s ease' }}>
            <span className="badge badge-blue mb-5">
              <Monitor className="h-3 w-3" /> Desktop CBT App
            </span>
            <h2 className="font-display font-black text-4xl sm:text-5xl text-white leading-tight mb-5">
              Exams that work even{' '}
              <span className="gradient-text-reverse">without internet</span>
            </h2>
            <p className="text-slate-400 text-base leading-relaxed mb-8">
              Our desktop CBT application is built for the Nigerian reality — schools with patchy internet, shared computers, and high-stakes exams. Students take exams offline; results sync automatically.
            </p>

            <div className="grid grid-cols-2 gap-3 mb-8">
              {FEATURES.map(f => {
                const Icon = f.icon;
                return (
                  <div key={f.title} className="rounded-xl p-4 border border-white/5 hover:border-white/10 transition-all"
                    style={{ background: 'rgba(255,255,255,0.02)' }}>
                    <Icon className="h-5 w-5 mb-2" style={{ color: f.color }} />
                    <p className="text-white text-sm font-semibold mb-1">{f.title}</p>
                    <p className="text-slate-500 text-xs leading-relaxed">{f.desc}</p>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl border text-sm"
                style={{ background: 'rgba(34,197,94,0.06)', borderColor: 'rgba(34,197,94,0.2)', color: '#22c55e' }}>
                <Monitor className="h-4 w-4" />
                Included with your Schooldom subscription
              </div>
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl border border-white/8 text-slate-400 text-sm">
                <Wifi className="h-4 w-4 text-green-400" />
                Mobile app coming soon
              </div>
            </div>
          </div>

          {/* Right: Mockup */}
          <div style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateX(30px)', transition: 'all 0.7s ease 0.15s' }}>
            <CBTAppMockup />
            <div className="mt-4 grid grid-cols-3 gap-3">
              {[
                { val: '127', label: 'Live sessions', color: '#0ea5e9' },
                { val: '99.8%', label: 'Uptime', color: '#22c55e' },
                { val: '2.8s', label: 'Submit speed', color: '#8b5cf6' },
              ].map(s => (
                <div key={s.label} className="rounded-xl p-3 text-center border border-white/5" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <p className="font-display font-black text-xl" style={{ color: s.color }}>{s.val}</p>
                  <p className="text-slate-500 text-[10px]">{s.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
