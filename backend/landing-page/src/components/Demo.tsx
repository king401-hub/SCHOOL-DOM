import { useState, useEffect, useRef } from 'react';
import { Users, DollarSign, BookOpen, CheckCircle, TrendingUp, Bell } from 'lucide-react';

const NOTIFICATIONS = [
  { icon: DollarSign, msg: 'Payment received: ₦32,000', name: 'Bello Fatima', color: '#10b981' },
  { icon: CheckCircle, msg: 'Exam submitted: Biology SS2', name: 'Chidi Okonkwo', color: '#0ea5e9' },
  { icon: Users, msg: 'New student enrolled', name: 'Amina Yusuf', color: '#8b5cf6' },
  { icon: BookOpen, msg: 'Report card generated', name: 'Tunde Adeyemi', color: '#f59e0b' },
  { icon: Bell, msg: 'Attendance alert sent to parent', name: 'Ngozi Eze', color: '#ec4899' },
];

function LiveNotifications() {
  const [visible, setVisible] = useState<number[]>([]);
  useEffect(() => {
    let idx = 0;
    const add = () => {
      setVisible(prev => [...prev.slice(-3), idx % NOTIFICATIONS.length]);
      idx++;
    };
    add();
    const t = setInterval(add, 2200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="space-y-2">
      {visible.map((ni, i) => {
        const n = NOTIFICATIONS[ni];
        const Icon = n.icon;
        return (
          <div
            key={`${ni}-${i}`}
            className="flex items-center gap-3 p-3 rounded-xl border border-white/5"
            style={{
              background: 'rgba(255,255,255,0.03)',
              animation: 'slideInRight 0.4s ease forwards',
            }}
          >
            <div className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${n.color}20` }}>
              <Icon className="h-4 w-4" style={{ color: n.color }} />
            </div>
            <div className="min-w-0">
              <p className="text-white text-xs font-medium truncate">{n.msg}</p>
              <p className="text-slate-500 text-[10px]">{n.name}</p>
            </div>
            <div className="w-1.5 h-1.5 rounded-full shrink-0 animate-pulse" style={{ background: n.color }} />
          </div>
        );
      })}
    </div>
  );
}

function AnimatedChart() {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setProgress(p => (p >= 100 ? 0 : p + 1)), 50);
    return () => clearInterval(t);
  }, []);

  const bars = [72, 85, 65, 90, 78, 95, 82, 88, 70, 93, 80, 96];
  return (
    <div className="flex items-end gap-1.5 h-24">
      {bars.map((h, i) => (
        <div key={i} className="flex-1 rounded-sm relative overflow-hidden" style={{ height: '100%', background: 'rgba(255,255,255,0.05)' }}>
          <div
            className="absolute bottom-0 left-0 right-0 rounded-sm transition-all duration-500"
            style={{
              height: `${progress > 0 ? h : 0}%`,
              background: `linear-gradient(to top, #0ea5e9, #8b5cf6)`,
              opacity: 0.7 + (i % 3) * 0.1,
              transitionDelay: `${i * 50}ms`,
            }}
          />
        </div>
      ))}
    </div>
  );
}

export default function Demo() {
  const [active, setActive] = useState(0);
  const tabs = ['Finance', 'Attendance', 'Exams', 'Reports'];
  const sectionRef = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold: 0.1 });
    if (sectionRef.current) obs.observe(sectionRef.current);
    return () => obs.disconnect();
  }, []);

  return (
    <section id="demo" className="py-28 px-4 relative" ref={sectionRef}>
      <div className="max-w-7xl mx-auto">
        <div
          className="text-center mb-16 transition-all duration-700"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(30px)' }}
        >
          <span className="text-xs font-bold uppercase tracking-widest px-4 py-1.5 rounded-full border border-violet-500/30 text-violet-400 bg-violet-500/08 mb-4 inline-block">
            Live Simulation
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Watch your school{' '}
            <span style={{ background: 'linear-gradient(90deg, #8b5cf6, #ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              come alive
            </span>
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto">Real-time operations running inside your dashboard, right now.</p>
        </div>

        <div
          className="grid lg:grid-cols-2 gap-8 items-stretch transition-all duration-700 delay-200"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(30px)' }}
        >
          <div className="rounded-2xl border border-white/5 overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)' }}>
            <div className="flex border-b border-white/5">
              {tabs.map((t, i) => (
                <button
                  key={t}
                  onClick={() => setActive(i)}
                  className="flex-1 py-3 text-xs font-medium transition-all cursor-pointer"
                  style={{
                    color: active === i ? '#0ea5e9' : '#64748b',
                    borderBottom: active === i ? '2px solid #0ea5e9' : '2px solid transparent',
                    background: active === i ? 'rgba(14,165,233,0.05)' : 'transparent',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="p-5">
              <p className="text-slate-500 text-xs mb-3 uppercase tracking-wider">Term 2 Performance</p>
              <AnimatedChart />
              <div className="mt-4 grid grid-cols-3 gap-3">
                {[
                  { label: 'Avg Score', val: '78.4%', trend: '+5.2%' },
                  { label: 'Pass Rate', val: '94.1%', trend: '+2.8%' },
                  { label: 'Exams Run', val: '127', trend: '+41' },
                ].map(s => (
                  <div key={s.label} className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <p className="text-slate-500 text-[10px]">{s.label}</p>
                    <p className="text-white text-sm font-bold">{s.val}</p>
                    <p className="text-emerald-400 text-[10px]">{s.trend}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/5 overflow-hidden flex flex-col" style={{ background: 'rgba(255,255,255,0.02)' }}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-white text-xs font-semibold">Live Activity Feed</span>
              </div>
              <TrendingUp className="h-4 w-4 text-slate-500" />
            </div>
            <div className="p-5 flex-1">
              <LiveNotifications />
            </div>
          </div>
        </div>
      </div>
      <style>{`
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </section>
  );
}
