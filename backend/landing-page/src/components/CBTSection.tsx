import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Monitor, Wifi, WifiOff, Shield, Zap, CheckCircle, Download } from 'lucide-react';
import { Reveal } from '../lib/reveal';

const GREEN = 'var(--c-green)';
const GREEN_BRIGHT = '#4ade80';

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
    <div className="rounded-2xl overflow-hidden border border-white/8 shadow-2xl keep-dark"
      style={{ background: 'rgba(16,14,11,0.96)' }}>
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5" style={{ background: 'rgba(74,222,128,0.05)' }}>
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
                  style={{ background: i <= question ? GREEN_BRIGHT : 'rgba(255,255,255,0.06)' }} />
              ))}
            </div>
          </div>
          <div className="text-right">
            <p className="font-mono font-bold text-lg" style={{ color: timeLeft < 600 ? '#f87171' : GREEN_BRIGHT }}>{fmt(timeLeft)}</p>
            <p className="text-slate-600 text-[9px]">remaining</p>
          </div>
        </div>

        {/* Question */}
        <div className="rounded-xl p-4 mb-4" style={{ background: 'rgba(74,222,128,0.05)', border: '1px solid rgba(74,222,128,0.18)' }}>
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
                  background: isCorrect ? 'rgba(52,211,153,0.15)' : isSelected ? 'rgba(248,113,113,0.15)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${isCorrect ? 'rgba(52,211,153,0.5)' : isSelected ? 'rgba(248,113,113,0.5)' : 'rgba(255,255,255,0.07)'}`,
                  color: isCorrect ? '#34d399' : isSelected ? '#f87171' : '#94a3b8',
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
            <span className="flex items-center gap-1 text-[9px] text-emerald-400">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Auto-save on
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

interface CbtFeature { icon: typeof WifiOff; title: string; desc: string }

function buildFeatures(t: (key: string) => string): CbtFeature[] {
  return [
    { icon: WifiOff, title: t('cbt.features.offline.title'), desc: t('cbt.features.offline.desc') },
    { icon: Shield, title: t('cbt.features.antiCheat.title'), desc: t('cbt.features.antiCheat.desc') },
    { icon: Zap, title: t('cbt.features.sync.title'), desc: t('cbt.features.sync.desc') },
    { icon: Monitor, title: t('cbt.features.windows.title'), desc: t('cbt.features.windows.desc') },
    { icon: CheckCircle, title: t('cbt.features.marking.title'), desc: t('cbt.features.marking.desc') },
    { icon: Download, title: t('cbt.features.deploy.title'), desc: t('cbt.features.deploy.desc') },
  ];
}

export default function CBTSection() {
  const { t } = useTranslation();
  const FEATURES = buildFeatures(t);

  return (
    <section id="cbt" className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 80% 50%, rgba(var(--c-green-rgb),0.05) 0%, transparent 60%)' }} />

      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-14 items-center">
          {/* Left */}
          <Reveal x={-28} y={0}>
            <span className="badge mb-5">
              <Monitor className="h-3 w-3" /> {t('cbt.badge')}
            </span>
            <h2 className="font-display font-bold text-4xl sm:text-5xl text-[var(--c-ink)] leading-tight mb-5 tracking-tight">
              {t('cbt.title')}{' '}
              <span className="gradient-text-reverse">{t('cbt.titleHighlight')}</span>
            </h2>
            <p className="text-[var(--c-muted)] text-base leading-relaxed mb-8">
              {t('cbt.subtitle')}
            </p>

            <div className="grid grid-cols-2 gap-3 mb-8">
              {FEATURES.map(f => {
                const Icon = f.icon;
                return (
                  <div key={f.title} className="rounded-xl p-4 hover:border-[var(--c-green)]/25 transition-all sd-card">
                    <Icon className="h-5 w-5 mb-2" style={{ color: GREEN }} />
                    <p className="text-[var(--c-ink)] text-sm font-semibold mb-1">{f.title}</p>
                    <p className="text-[var(--c-muted)] text-xs leading-relaxed">{f.desc}</p>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl border text-sm"
                style={{ background: 'rgba(var(--c-green-rgb),0.06)', borderColor: 'rgba(var(--c-green-rgb),0.2)', color: GREEN }}>
                <Monitor className="h-4 w-4" />
                {t('cbt.includedBadge')}
              </div>
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl border border-[var(--c-ink)]/10 text-[var(--c-muted)] text-sm">
                <Wifi className="h-4 w-4 text-emerald-600" />
                {t('cbt.mobileSoon')}
              </div>
            </div>
          </Reveal>

          {/* Right: Mockup */}
          <Reveal x={28} y={0} delay={0.15}>
            <CBTAppMockup />
            <div className="mt-4 grid grid-cols-3 gap-3">
              {[
                { val: '127', label: t('cbt.statLiveSessions') },
                { val: '99.8%', label: t('cbt.statUptime') },
                { val: '2.8s', label: t('cbt.statSubmitSpeed') },
              ].map(s => (
                <div key={s.label} className="rounded-xl p-3 text-center sd-card">
                  <p className="font-display font-semibold text-xl" style={{ color: GREEN }}>{s.val}</p>
                  <p className="text-[var(--c-subtle)] text-[10px]">{s.label}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
